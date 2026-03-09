# Copyright (c) 2025 Ming Yu (yuming@oppo.com), Liangliang Han (hanliangliang@oppo.com)
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from ..word_level_pynini import string_file, union, pynutil

from ...core.processor import Processor
from ...core.utils import get_abs_path
from .base import DateBaseRule, TimeBaseRule
from .base.number_base import NumberBaseRule

delete = pynutil.delete
insert = pynutil.insert


class UTCTimeRule(Processor):
    """UTC时间规则处理器，处理如2025-01-01 12:00:00等UTC时间表达式"""

    def __init__(self):
        super().__init__(name="time_utc")
        self.year = DateBaseRule().build_year_rules()
        self.month = DateBaseRule().build_month_rules()
        self.date = DateBaseRule().build_date_rules()
        self.time = TimeBaseRule().build_time_rules()
        self.build_tagger()

    def build_tagger(self):
        # 构建"月份+第N周"规则
        number_rule = NumberBaseRule()
        chinese_number = number_rule.build_cn_number()

        # 阿拉伯数字（词级）
        arabic_digit = string_file(get_abs_path("../data/number/arabic_digit.tsv"))
        arabic_number = arabic_digit.plus

        # 数字（阿拉伯数字或中文数字）
        number = arabic_number | chinese_number

        # 加载星期几数据
        weekday = string_file(get_abs_path("../data/week/weekday.tsv"))

        # ==================== 构建ISO 8601标准格式识别 ====================
        # 格式: 2024-12-31T00:00:00Z 或 2024-12-31T00:00:00
        # 注意：中文tokenizer会将数字逐位拆分，所以需要用单个数字构建

        # 年份：4个独立的阿拉伯数字（如2024 -> '2','0','2','4'）
        iso_year = (
            insert('year: "')
            + arabic_digit
            + arabic_digit
            + arabic_digit
            + arabic_digit
            + insert('"')
        )

        # 月份：2个独立的阿拉伯数字（如12 -> '1','2'）
        iso_month = insert('month: "') + arabic_digit + arabic_digit + insert('"')

        # 日期：2个独立的阿拉伯数字（如31 -> '3','1'）
        iso_day = insert('day: "') + arabic_digit + arabic_digit + insert('"')

        # 小时：2个独立的阿拉伯数字（如08 -> '0','8'）
        iso_hour = insert('hour: "') + arabic_digit + arabic_digit + insert('"')

        # 分钟：2个独立的阿拉伯数字（如30 -> '3','0'）
        iso_minute = insert('minute: "') + arabic_digit + arabic_digit + insert('"')

        # 秒：2个独立的阿拉伯数字（如45 -> '4','5'）
        iso_second = insert('second: "') + arabic_digit + arabic_digit + insert('"')

        # ISO 8601完整格式：YYYY-MM-DDTHH:MM:SSZ 或 YYYY-MM-DDTHH:MM:SS
        iso_datetime = (
            iso_year
            + delete("-")
            + iso_month
            + delete("-")
            + iso_day
            + (delete("t") | delete("T"))
            + iso_hour
            + delete(":")
            + iso_minute
            + delete(":")
            + iso_second
            + (delete("z") | delete("Z")).ques  # Z时区标识可选
        )
        # ================================================================

        # 构建"月份+第N周"规则：月份 + (的).ques + 第 + 数字 + (个).ques + 周
        month_week = (
            self.month
            + delete("的").ques
            + delete("第")
            + insert('week_order: "')
            + number
            + insert('"')
            + delete("个").ques
            + (delete("周") | delete("星期") | delete("礼拜"))
        )

        # 构建"月份+第N个+星期X"规则：月份 + (的).ques + 第 + 数字 + 个 + 星期/周 + X
        month_nth_weekday = (
            self.month
            + delete("的").ques
            + delete("第")
            + insert('week_order: "')
            + number
            + insert('"')
            + delete("个").ques
            + (delete("星期") | delete("周") | delete("礼拜"))
            + insert('week_day: "')
            + weekday
            + insert('"')
        )

        # 构建"年+月份+第N周"规则
        year_month_week = self.year + delete("的").ques + month_week

        # 构建"年+月份+第N个+星期X"规则
        year_month_nth_weekday = self.year + delete("的").ques + month_nth_weekday

        # 构建"年+第N周"规则：21年第一个礼拜
        year_nth_week = (
            self.year
            + delete("的").ques
            + delete("第")
            + insert('week_order: "')
            + number
            + insert('"')
            + delete("个").ques
            + (delete("周") | delete("星期") | delete("礼拜"))
        )

        # 构建"年+第N个月"规则：2025年第九个月
        year_nth_month = (
            self.year
            + delete("的").ques
            + delete("第")
            + insert('month_order: "')
            + number
            + insert('"')
            + delete("个").ques
            + delete("月")
        )

        # 构建UTC时间表达式（优先级：更具体的规则在前）
        utc_time = (
            iso_datetime  # ISO 8601标准格式（最高优先级）
            | (self.date + (delete(" ") | delete("-")).ques + self.time)  # 公历日期+时间
            | year_month_nth_weekday
            | month_nth_weekday  # 月份+第N个星期X（优先）
            | year_month_week
            | month_week
            | year_nth_week
            | year_nth_month  # 年/月份+第N周/第N个月
            | self.date
            | self.year
            | self.month  # 公历日期
            | self.time
        )

        tagger = self.add_tokens(utc_time)
        self.tagger = tagger
