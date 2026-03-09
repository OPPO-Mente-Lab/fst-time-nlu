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

from ...core.processor import Processor
from ...core.utils import get_abs_path
from ..word_level_pynini import string_file, pynutil
from .base import DateBaseRule, LunarBaseRule, RelativeBaseRule, TimeBaseRule

delete = pynutil.delete
insert = pynutil.insert


class BetweenRule(Processor):
    def __init__(self):
        super().__init__(name="time_between")
        # 构建基础规则与组件实例，便于引用细粒度模式
        self.relative = RelativeBaseRule().build_std_rules()

        self._date_base = DateBaseRule()
        self.year = self._date_base.build_year_rules()
        self.month = self._date_base.build_month_rules()
        self.date = self._date_base.build_date_rules()

        self._time_base = TimeBaseRule()
        self.time = self._time_base.build_time_rules()

        # 农历相关
        self.lunar_date = LunarBaseRule().build_date_rules()
        self.lunar_month = LunarBaseRule().build_month_rules()
        self.lunar_monthday = LunarBaseRule().build_monthday_rules()
        self.lunar_jieqi = LunarBaseRule().build_jieqi_rules()

        self.build_tagger()

    def build_tagger(self):
        # 构建UTC时间表达式
        utc_time = (
            (self.date + (delete(" ") | delete("-")).ques + self.time)  # 公历日期+时间
            | self.date
            | self.year
            | self.month  # 公历日期
            | self.time
        )

        lunar_time = (
            (self.lunar_date + self.time)
            | self.lunar_date
            | self.lunar_month
            | self.lunar_monthday
            | self.lunar_jieqi
        )

        # 时间范围连接符（允许两侧可选空格）
        space = delete(" ").star
        to_core = (
            delete("-")
            | delete("－")
            | delete("~")
            | delete("～")
            | delete("——")
            | delete("—")
            | delete("到")
            | delete("至")
        )
        to = space + to_core + space

        # 基于单位的单token范围规则（最高优先级）
        # 这些规则匹配"数字-数字+单位"模式，如"2024-2025年"
        number_digit = string_file(get_abs_path("../data/number/arabic_digit.tsv"))
        digit = number_digit.plus

        # 数字位数定义
        year_digit = number_digit + number_digit + number_digit + number_digit  # 4位年份

        # 年份范围：2024-2025年
        year_range = (
            insert('year: "')
            + digit
            + insert('"')
            + space
            + delete("-")
            + space
            + insert('year2: "')
            + digit
            + insert('"')
            + delete("年")
            + insert("raw_type: utc")
        )

        # 无单位的年份范围：2024-2025
        year_range_no_unit = (
            insert('year: "')
            + year_digit
            + insert('"')
            + space
            + delete("-")
            + space
            + insert('year2: "')
            + year_digit
            + insert('"')
            + insert("raw_type: utc")
        )

        # 月份范围：1-3月
        month_range = (
            insert('month: "')
            + digit
            + insert('"')
            + space
            + delete("-")
            + space
            + insert('month2: "')
            + digit
            + insert('"')
            + delete("月")
            + insert("raw_type: utc")
        )

        # 日期范围：1-3日/号
        day_range = (
            insert('day: "')
            + digit
            + insert('"')
            + space
            + delete("-")
            + space
            + insert('day2: "')
            + digit
            + insert('"')
            + (delete("日") | delete("号"))
            + insert("raw_type: utc")
        )

        # 小时范围：9-11点/时
        hour_range = (
            self._time_base.noon_std.ques
            + insert('hour: "')
            + digit
            + insert('"')
            + space
            + delete("-")
            + space
            + insert('hour2: "')
            + digit
            + insert('"')
            + (delete("点") | delete("时"))
            + insert("raw_type: utc")
        )

        # 合并所有基于单位的范围（按优先级排序）
        unit_based_range = (
            year_range
            | month_range
            | day_range
            | hour_range  # 带单位（最高优先级）
            | year_range_no_unit  # 4位年份无单位（次高优先级）
            # 注意：不添加1-2位数字的无单位范围规则，保持由UTCTimeRule处理
        )

        # 标记时间类型
        between_utc_time = utc_time + insert("raw_type: utc")
        between_relative_time = self.relative + insert("raw_type: relative")
        between_lunar_time = lunar_time + insert("raw_type: lunar")

        # 限制hour_head_shared只匹配1-2位数字，避免匹配年份数字
        short_digit = number_digit + number_digit.ques  # 只匹配0-99
        hour_head_shared = (
            self._time_base.noon_std.ques
            + insert('hour: "')
            + short_digit
            + insert('"')
            + insert("raw_type: utc")
        )

        # 纳入between端点可选集合
        between_time = (
            between_utc_time | between_relative_time | between_lunar_time | hour_head_shared
        )

        # 专用规则：相对年偏移 + 月.日 到 月.日（整体识别为单token范围）
        # 例：去年8.20到11.10 / 明年8.20至11.10 / 今年的8.20-11.10
        # 新增：去年8.20到今年11月10（两端都有年份前缀）
        year_prefix = string_file(get_abs_path("../data/date/year_prefix.tsv"))
        month_digit = string_file(get_abs_path("../data/date/digit/month_digit.tsv"))
        day_digit = string_file(get_abs_path("../data/date/digit/day_digit.tsv"))

        rel_year = insert('offset_year: "') + year_prefix + insert('"')
        md_left = (
            insert('month: "')
            + month_digit
            + insert('"')
            + delete(".")
            + insert('day: "')
            + day_digit
            + insert('"')
        )
        md_right = (
            insert('month2: "')
            + month_digit
            + insert('"')
            + delete(".")
            + insert('day2: "')
            + day_digit
            + insert('"')
        )
        de_opt = delete("的").ques

        # 原规则：左边有年份，右边无年份
        rel_year_md_to_md = (
            rel_year
            + delete("年").ques
            + de_opt
            + md_left
            + to
            + md_right
            + insert('raw_type: "relative"')
        )

        # 新规则：两端都有年份前缀（如：去年8.20到今年11月10）
        # 右边的年份也用offset_year字段，parser会自动处理
        md_right_with_year = (
            insert('offset_year2: "')
            + year_prefix
            + insert('"')
            + delete("年").ques
            + de_opt
            + insert('month2: "')
            + month_digit
            + insert('"')
            + (delete("月") | delete(".")).ques
            + insert('day2: "')
            + day_digit
            + insert('"')
        )
        rel_year_md_to_rel_year_md = (
            rel_year
            + delete("年").ques
            + de_opt
            + md_left
            + to
            + md_right_with_year
            + insert('raw_type: "relative"')
        )

        # 单token范围具有更高优先级
        tagger = (
            self.add_tokens(unit_based_range)  # 单token范围（最高优先级）
            | self.add_tokens(rel_year_md_to_rel_year_md)  # 去年8.20到今年11月10（两端都有年份）
            | self.add_tokens(rel_year_md_to_md)  # 去年8.20到11.10（整体识别）
            | (self.add_tokens(between_time) + to + self.add_tokens(between_time))  # 通用：左到右
        )
        self.tagger = tagger
