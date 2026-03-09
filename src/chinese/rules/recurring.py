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
from .base import PeriodBaseRule, RelativeBaseRule
from .week import WeekRule
from .utctime import UTCTimeRule
from .holiday import HolidayRule
from .period import PeriodRule
from .base.number_base import NumberBaseRule


insert = pynutil.insert
delete = pynutil.delete


class RecurringRule(Processor):
    """周期时间规则处理器"""

    def __init__(self):
        super().__init__(name="time_recurring")
        self.build_tagger()

    def build_tagger(self):
        # 加载周期前缀数据
        recurring_prefix = string_file(get_abs_path("../data/recurring/recurring_prefix.tsv"))

        # 获取其他规则的时间表达式
        week_rule = WeekRule()
        utc_rule = UTCTimeRule()
        holiday_rule = HolidayRule()
        period_rule = PeriodRule()

        # 构建数字规则
        number_rule = NumberBaseRule()
        chinese_number = number_rule.build_cn_number()
        arabic = string_file(get_abs_path("../data/number/arabic_digit.tsv")).plus
        number = arabic | chinese_number

        # 构建周期规则：每/每个 + 时间表达式
        recurring_week = (
            insert('recurring_type: "week" ') + delete(recurring_prefix) + week_rule.tagger
        )

        recurring_utc = (
            insert('recurring_type: "utc" ') + delete(recurring_prefix) + utc_rule.tagger
        )

        recurring_holiday = (
            insert('recurring_type: "holiday" ') + delete(recurring_prefix) + holiday_rule.tagger
        )

        # 添加对"天"、"年"、"月"等单位的支持
        recurring_day = (
            insert('recurring_type: "day" ')
            + delete(recurring_prefix)
            + delete("天")
            + insert('unit: "day"')
        )

        # 添加对"日"的支持（等同于"天"）
        recurring_day_alt = (
            insert('recurring_type: "day" ')
            + delete(recurring_prefix)
            + delete("日")
            + insert('unit: "day"')
        )

        recurring_year = (
            insert('recurring_type: "year" ')
            + delete(recurring_prefix)
            + delete("年")
            + insert('unit: "year"')
        )

        recurring_month = (
            insert('recurring_type: "month" ')
            + delete(recurring_prefix)
            + delete("月")
            + insert('unit: "month"')
        )

        # 添加每小时规则
        recurring_hour = (
            insert('recurring_type: "hour" ')
            + delete(recurring_prefix)
            + delete("小时")
            + insert('unit: "hour"')
        )

        # 添加每周规则
        recurring_week_unit = (
            insert('recurring_type: "week" ')
            + delete(recurring_prefix)
            + delete(union("周", "星期", "礼拜"))
            + insert('unit: "week"')
        )

        # 添加每季度规则
        recurring_quarter = (
            insert('recurring_type: "quarter" ')
            + delete(recurring_prefix)
            + delete(union("季度", "季"))
            + insert('unit: "quarter"')
        )

        # 间隔型周期：每 + 数字 + 单位
        recurring_interval = (
            insert('recurring_type: "interval" ')
            + delete(recurring_prefix)
            + insert('interval: "')
            + number
            + insert('"')
            + delete("个").ques  # "个"是可选的
            + insert('unit: "')
            + string_file(get_abs_path("../data/period/period_unit.tsv"))
            + insert('"')
        )

        # 间隔型周期+时间：每 + 数字 + 单位 + 时间
        recurring_interval_time = (
            insert('recurring_type: "interval_time" ')
            + delete(recurring_prefix)
            + insert('interval: "')
            + number
            + insert('"')
            + delete("个").ques  # "个"是可选的
            + insert('unit: "')
            + string_file(get_abs_path("../data/period/period_unit.tsv"))
            + insert('"')
            + utc_rule.tagger
        )

        # 添加对"每天+时间"的支持
        recurring_day_time = (
            insert('recurring_type: "day_time" ')
            + delete(recurring_prefix)
            + delete("天")
            + utc_rule.tagger
        )

        # 添加对"每年+时间"的支持
        recurring_year_time = (
            insert('recurring_type: "year_time" ')
            + delete(recurring_prefix)
            + delete("年")
            + utc_rule.tagger
        )

        # 添加对"每月+时间"的支持
        recurring_month_time = (
            insert('recurring_type: "month_time" ')
            + delete(recurring_prefix)
            + delete("月")
            + utc_rule.tagger
        )

        # 添加对"每年+节假日"的支持
        recurring_year_holiday = (
            insert('recurring_type: "year_holiday" ')
            + delete(recurring_prefix)
            + delete("年")
            + holiday_rule.tagger
        )

        # 添加对"每年+季节"的支持
        recurring_year_season = (
            insert('recurring_type: "year_season" ')
            + delete(recurring_prefix)
            + delete("年")
            + period_rule.tagger
        )

        # 复合型周期规则

        # 每月 + 日期：每月三号
        recurring_month_day = (
            insert('recurring_type: "month_day" ')
            + delete(recurring_prefix)
            + delete("月")
            + insert('day: "')
            + number
            + insert('"')
            + delete(union("号", "日"))
        )

        # 每周 + 星期几：每周一、每周六
        recurring_week_day = (
            insert('recurring_type: "week_day" ')
            + delete(recurring_prefix)
            + delete(union("周", "星期", "礼拜"))
            + insert('week_day: "')
            + string_file(get_abs_path("../data/week/weekday.tsv"))
            + insert('"')
        )

        # 每年 + 月份：每年三月
        recurring_year_month = (
            insert('recurring_type: "year_month" ')
            + delete(recurring_prefix)
            + delete("年")
            + insert('month: "')
            + number
            + insert('"')
            + delete("月")
        )

        # 合并所有周期规则（按优先级排序）
        tagger = self.add_tokens(
            recurring_day_time  # 第3层：复合型（优先级最高）
            | recurring_month_day
            | recurring_week_day
            | recurring_year_month
            | recurring_year_holiday
            | recurring_year_season  # 每年+季节
            | recurring_year_time
            | recurring_month_time
            | recurring_interval_time  # 间隔型+时间
            | recurring_interval  # 第2层：间隔型（优先级高于utc规则）
            | recurring_hour  # 第1层：基本型
            | recurring_day
            | recurring_day_alt  # 每日（等同于每天）
            | recurring_week_unit
            | recurring_month
            | recurring_quarter
            | recurring_year
            | recurring_week  # 原有规则（优先级最低）
            | recurring_utc
            | recurring_holiday
        )
        self.tagger = tagger
