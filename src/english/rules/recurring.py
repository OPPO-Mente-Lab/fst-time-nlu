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

# 使用词级pynini
from ..word_level_pynini import string_file, union, accep
from ..word_level_pynini import pynutil

from ...core.processor import Processor
from ...core.utils import get_abs_path, INPUT_LOWER_CASED, INPUT_CASED
from .base.time_base import TimeBaseRule
from .base.week_base import WeekBaseRule


class RecurringRule(Processor):
    """Recurring time rule processor for English"""

    def __init__(self, input_case: str = INPUT_LOWER_CASED):
        super().__init__(name="time_recurring")
        self.input_case = input_case
        self.build_tagger()

    def build_tagger(self):
        """Build recurring time tagger"""
        delete = pynutil.delete
        insert = pynutil.insert

        # 导入词级delete_space
        from ..word_level_pynini import word_delete_space

        delete_space = word_delete_space()

        # 创建周期前缀匹配（简单方式：直接用union，不用string_file）
        # 参考time_delta规则的实现：直接delete字符串
        delete_recurring_prefix = delete(union("every", "each"))

        # 提取需要的子FST，而非完整规则tagger
        # 1. weekday子FST：只需要weekday匹配部分（约500状态），不需要week+period或week+time
        week_base = WeekBaseRule(input_case=self.input_case)
        weekday_full = string_file(get_abs_path("../data/week/weekdays_full.tsv"))
        weekday_abbr = string_file(get_abs_path("../data/week/weekdays_abbr.tsv"))
        if self.input_case == INPUT_CASED:
            weekday_full = weekday_full | week_base._capitalize_weekdays()
            weekday_abbr = weekday_abbr | week_base._capitalize_weekday_abbr()
        weekday_abbr_safe = weekday_abbr + union(" ", "")
        weekday = weekday_full | weekday_abbr_safe
        weekday_sub_fst = insert('week_day:"') + weekday + insert('"')

        # 2. time子FST：只需要time匹配部分（约3,000状态），不需要完整的utctime包括date
        time_base = TimeBaseRule(input_case=self.input_case)
        time_sub_fst = time_base.build_time_rules()

        # 3. period子FST：只需要basic periods数据
        basic_periods = string_file(get_abs_path("../data/period/basic_periods.tsv"))
        extended_periods = string_file(get_abs_path("../data/period/extended_periods.tsv"))
        all_periods = basic_periods | extended_periods
        period_sub_fst = insert('period:"') + all_periods + insert('"')

        # 构建数字规则
        # 词级FST：数字是完整token，不能使用.plus匹配多位数
        # 创建0-999的数字token union（类似TimeRangeRule）
        number_tokens = [accep(str(i)) for i in range(1000)]  # 0-999
        number = union(*number_tokens)

        # 定义时间范围所需的基础FST（参考RangeRule）
        hour_numeric = time_base.hour_numeric
        minute_two_digit = union(*[accep(f"{i:02d}") for i in range(60)])
        minute_with_padding = pynutil.add_weight(minute_two_digit, -0.5) | time_base.minute_numeric

        # 英文单词形式的小时（1-12）
        hour_words = union(
            accep("one"),
            accep("two"),
            accep("three"),
            accep("four"),
            accep("five"),
            accep("six"),
            accep("seven"),
            accep("eight"),
            accep("nine"),
            accep("ten"),
            accep("eleven"),
            accep("twelve"),
        )

        # 合并数字和英文单词形式的小时
        hour = hour_numeric | hour_words

        # Colon处理
        optional_space = delete_space.ques
        colon = optional_space + delete(":") + optional_space

        # 连接词
        to_connector = optional_space + delete(union("to", "till", "until")) + optional_space
        dash_connector = optional_space + delete("-") + optional_space
        range_connector = to_connector | dash_connector

        # AM/PM（支持多种格式）
        am_pm = union("am", "a.m.", "pm", "p.m.", "AM", "PM", "A.M.", "P.M.")
        optional_am_pm = (optional_space + insert('period:"') + am_pm + insert('"')).ques

        # 基本周期单位规则（使用词级delete FST）
        recurring_day = (
            delete_recurring_prefix
            + delete_space
            + insert('recurring_type:"day" ')
            + delete(union("day", "days"))
            + insert('unit:"day"')
        )

        recurring_week_unit = (
            delete_recurring_prefix
            + delete_space
            + insert('recurring_type:"week" ')
            + delete(union("week", "weeks"))
            + insert('unit:"week"')
        )

        recurring_month = (
            delete_recurring_prefix
            + delete_space
            + insert('recurring_type:"month" ')
            + delete(union("month", "months"))
            + insert('unit:"month"')
        )

        recurring_year = (
            delete_recurring_prefix
            + delete_space
            + insert('recurring_type:"year" ')
            + delete(union("year", "years"))
            + insert('unit:"year"')
        )

        recurring_hour = (
            delete_recurring_prefix
            + delete_space
            + insert('recurring_type:"hour" ')
            + delete(union("hour", "hours"))
            + insert('unit:"hour"')
        )

        recurring_quarter = (
            delete_recurring_prefix
            + delete_space
            + insert('recurring_type:"quarter" ')
            + delete(union("quarter", "quarters", "3 months"))
            + insert('unit:"quarter"')
        )

        # 复合周期规则
        # 每周+星期几：every monday, every tuesday
        recurring_week_day = (
            delete_recurring_prefix
            + delete_space
            + insert('recurring_type:"week" ')
            + weekday_sub_fst
        )

        # 每月+日期（简化版）：on every 8th day, every 5th day
        recurring_month_day_simple = (
            (delete("on") + delete_space).ques
            + delete_recurring_prefix
            + delete_space
            + insert('recurring_type:"month_day" ')
            + insert('day:"')
            + number
            + insert('"')
            + optional_space
            + delete(union("st", "nd", "rd", "th")).ques
            + optional_space
            + delete(union("day", "days")).ques
        )

        # 每月+日期：every 3rd of the month, every 15th of the month
        optional_space = delete_space.ques
        recurring_month_day = (
            delete_recurring_prefix
            + delete_space
            + insert('recurring_type:"month_day" ')
            + insert('day:"')
            + number
            + insert('"')
            + optional_space
            + delete(union("st", "nd", "rd", "th")).ques
            + optional_space
            + delete("of")
            + optional_space
            + delete("the")
            + optional_space
            + delete("month")
        )

        # 每年+月份：every january, every march
        recurring_year_month = (
            delete_recurring_prefix
            + delete_space
            + insert('recurring_type:"year_month" ')
            + insert('month:"')
            + string_file(get_abs_path("../data/date/months.tsv"))
            + insert('"')
        )

        # 每天+时间范围：every day from 7:30 to 9:30
        recurring_day_time_range = (
            delete_recurring_prefix
            + delete_space
            + insert('recurring_type:"day_time_range" ')
            + delete("day")
            + optional_space
            + delete("from")
            + optional_space
            + insert('start_hour:"')
            + hour
            + insert('"')
            + (colon + insert(' start_minute:"') + minute_with_padding + insert('"')).ques
            + optional_space
            + range_connector
            + insert('end_hour:"')
            + hour
            + insert('"')
            + (colon + insert(' end_minute:"') + minute_with_padding + insert('"')).ques
            + optional_am_pm
        )

        # 每天+时间：every day at 8 am, every day at 9:30
        recurring_day_time = (
            delete_recurring_prefix
            + delete_space
            + insert('recurring_type:"day_time" ')
            + delete("day")
            + optional_space
            + delete("at")
            + delete_space
            + time_sub_fst
        )

        # 合并所有周期规则（按优先级排序）
        tagger = self.add_tokens(
            # 第3层：复合型（优先级最高）
            recurring_day_time_range  # 新增：优先于recurring_day_time
            | recurring_day_time
            | recurring_month_day_simple
            | recurring_month_day
            | recurring_year_month  # 第1层：基本型  # noqa: W504, E261
            | recurring_hour
            | recurring_day
            | recurring_week_unit
            | recurring_month
            | recurring_quarter
            | recurring_year  # 原有规则（优先级最低）  # noqa: W504, E261
            | recurring_week_day  # every monday  # 原有的utc和period规则（使用子FST）  # noqa: W504, E261
            | (
                delete_recurring_prefix
                + delete_space
                + insert('recurring_type:"utc" ')
                + time_sub_fst  # UTC时间使用time规则即可
            )
            | (
                delete_recurring_prefix
                + delete_space
                + insert('recurring_type:"period" ')
                + period_sub_fst  # Period使用period数据即可
            )
        )
        self.tagger = tagger
