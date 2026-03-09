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
from ..word_level_pynini import (
    string_file,
    union,
    closure,
    string_map,
    cross,
    accep,
    word_cross,
    word_delete,
)
from ..word_level_pynini import pynutil
from ..word_level_pynini import word_delete_space

from ...core.processor import Processor
from ...core.utils import get_abs_path, INPUT_LOWER_CASED
from .base.date_base import DateBaseRule


class CompositeRelativeRule(Processor):
    """
    Composite relative time rule processor
    Handles complex expressions like:
    - last day of february
    - first day of year 2020
    - day before/after [event]
    - last month of year 2000
    """

    def __init__(self, input_case: str = INPUT_LOWER_CASED):
        super().__init__(name="time_composite_relative")
        self.input_case = input_case

        # Build helper components for weekday patterns
        self.weekday_names = self._build_weekday_names()
        self.month_names = self._build_month_names()
        self.week_prefix = self._build_week_prefix()

        self.build_tagger()

    def build_tagger(self):
        """Build the tagger for composite relative time expressions"""
        delete = pynutil.delete
        insert = pynutil.insert
        # 使用词级delete_space
        delete_space = word_delete_space()

        # Load data files
        position = string_file(get_abs_path("../data/date/position_modifiers.tsv"))
        time_unit = string_file(get_abs_path("../data/date/time_units.tsv"))
        temporal_rel = string_file(get_abs_path("../data/date/temporal_relations.tsv"))
        ordinal_positions = string_file(get_abs_path("../data/date/ordinal_positions.tsv"))

        # Load month and year from date base
        month = string_file(get_abs_path("../data/date/months.tsv"))
        year_numeric = string_file(get_abs_path("../data/date/year_numeric.tsv"))

        # Load offset prefixes
        year_prefix = string_file(get_abs_path("../data/date/year_prefix.tsv"))
        month_prefix = string_file(get_abs_path("../data/date/month_prefix.tsv"))
        week_prefix = string_file(get_abs_path("../data/week/week_prefix.tsv"))

        # Load general time modifiers (for use with holidays, events, etc.)
        time_modifiers = string_file(get_abs_path("../data/date/time_modifiers.tsv"))

        # Load seasonal periods
        seasonal_periods = string_file(get_abs_path("../data/period/seasonal_periods.tsv"))

        # Import date base for day patterns
        date_base = DateBaseRule(self.input_case)

        # Load weekdays
        weekday_full = string_file(get_abs_path("../data/week/weekdays_full.tsv"))
        weekday_abbr = string_file(get_abs_path("../data/week/weekdays_abbr.tsv"))

        # 为缩写添加词边界
        from ...core.utils import create_word_boundary

        weekday_abbr_safe = weekday_abbr + create_word_boundary()
        weekday = weekday_full | weekday_abbr_safe

        # Load day ordinal suffix (1st, 2nd, 3rd, etc.)
        day_ordinal_suffix = string_file(get_abs_path("../data/date/day_ordinal_suffix.tsv"))

        # Combined day patterns: numeric, ordinal words, or ordinal with suffix
        day_combined = date_base.day | day_ordinal_suffix

        # Support time unit plural forms (for pattern21: "next two days", "previous two months")
        # Map plural forms to singular forms, using cross for word-level FST
        time_unit_plural = union(
            cross("days", "day"),
            cross("months", "month"),
            cross("weeks", "week"),
            cross("years", "year"),
        )

        # Tags
        position_tag = insert('position:"') + position + insert('"')
        ordinal_position_tag = insert('ordinal_position:"') + ordinal_positions + insert('"')
        unit_tag = insert('unit:"') + (time_unit | time_unit_plural) + insert('"')
        relation_tag = insert('relation:"') + temporal_rel + insert('"')
        month_tag = insert('month:"') + month + insert('"')
        year_tag = insert('year:"') + year_numeric + insert('"')
        day_tag = insert('day:"') + day_combined + insert('"')
        weekday_tag = insert('week_day:"') + weekday + insert('"')
        offset_month_tag = insert('offset_month:"') + month_prefix + insert('"')
        offset_week_tag = insert('offset_week:"') + week_prefix + insert('"')
        season_tag = insert('season:"') + seasonal_periods + insert('"')

        # Delete common words
        delete_of = delete("of")
        delete_year_word = delete("year")
        delete_the = delete("the")

        # Pattern 1: "last/first day of [month]"
        # e.g., "last day of september" -> position: "last" unit: "day" month: "september"
        pattern1 = (
            position_tag
            + delete_space
            + unit_tag
            + delete_space
            + delete_of
            + delete_space
            + month_tag
        )

        # Pattern 2: "last/first day of [month] [year]"
        # e.g., "last day of february 2020" -> position: "last" unit: "day" month: "february" year: "2020"
        pattern2 = (
            position_tag
            + delete_space
            + unit_tag
            + delete_space
            + delete_of
            + delete_space
            + month_tag
            + delete_space
            + year_tag
        )

        # Pattern 3: "last/first day of year [year]"
        # e.g., "last day of year 2000" -> position: "last" unit: "day" year: "2000"
        pattern3 = (
            position_tag
            + delete_space
            + unit_tag
            + delete_space
            + delete_of
            + delete_space
            + delete_year_word
            + delete_space
            + year_tag
        )

        # Pattern 4: "last/first month of year [year]"
        # e.g., "last month of year 2000" -> position: "last" unit: "month" year: "2000"
        pattern4 = (
            position_tag
            + delete_space
            + unit_tag
            + delete_space
            + delete_of
            + delete_space
            + delete_year_word
            + delete_space
            + year_tag
        )

        # Pattern 5: "day before/after [weekday/holiday/date]"
        # This will be handled separately as it needs to compose with other rules
        # For now, just tag the "day before/after" part
        day_word = delete("day")
        pattern5 = day_word + delete_space + relation_tag

        # Pattern 6: "[offset]'s" marker for possessive constructions
        # e.g., "last year's" or "next month's"
        # This creates a marker that will combine with the following token
        possessive_marker = delete("'s") | delete("'")

        # Year possessive: "last year's", "next year's"
        pattern6_year = (
            insert('modifier_year:"') + year_prefix + insert('"') + delete_space + possessive_marker
        )

        # Month possessive: "last month's", "next month's"
        pattern6_month = (
            insert('modifier_month:"')
            + month_prefix
            + insert('"')
            + delete_space
            + possessive_marker
        )

        # Pattern 9: "month month_offset"
        # e.g., "august next month" -> month: "august" offset_month: "1"
        pattern9 = month_tag + delete_space + offset_month_tag

        # Pattern 10: "day month_offset"
        # e.g., "20th last month" -> day: "20" offset_month: "-1"
        pattern10 = day_tag + delete_space + offset_month_tag

        # Pattern 10b: "month_offset" (simple last month / next month)
        # e.g., "last month" -> offset_month: "-1"
        # e.g., "next month" -> offset_month: "1"
        pattern10b = offset_month_tag

        # Pattern 11: "weekday week_offset"
        # e.g., "monday last week" -> week_day: "monday" offset_week: "-1"
        pattern11 = weekday_tag + delete_space + offset_week_tag

        # Pattern 11b: "weekday after next"
        # e.g., "wednesday after next" -> week_day: "wednesday" time_modifier: "2"
        # 词级FST：使用accep + delete_space处理多词短语
        after_next = delete("after") + delete_space.ques + delete("next") + insert("2")
        pattern11b = (
            weekday_tag + delete_space + insert('time_modifier:"') + after_next + insert('"')
        )

        # Pattern 11c: "month/year/week after next"
        # e.g., "march after next" -> month: "march" time_modifier: "2"
        # e.g., "year after next" -> unit: "year" time_modifier: "2"
        # 词级FST：使用accep + delete_space处理多词短语
        after_next_for_unit = delete("after") + delete_space.ques + delete("next") + insert("2")

        # month after next
        pattern11c_month = (
            month_tag + delete_space + insert('time_modifier:"') + after_next_for_unit + insert('"')
        )

        # year/week/day after next (using time_unit)
        pattern11c_unit = (
            unit_tag + delete_space + insert('time_modifier:"') + after_next_for_unit + insert('"')
        )

        # Pattern 12: "time_modifier" as standalone marker
        # e.g., "previous" -> time_modifier: "-1"
        # This will be combined with the following time token in the parser
        pattern12 = insert('time_modifier:"') + time_modifiers + insert('"')

        # Pattern 12a: "the time_modifier" as standalone marker
        # e.g., "the following" -> time_modifier: "1"
        # This will be combined with the following time token in the parser
        pattern12a = (
            delete_the + delete_space + insert('time_modifier:"') + time_modifiers + insert('"')
        )

        # Pattern 13: "ordinal_position day of [year]" (without "year" word)
        # e.g., "last day of 2017" -> ordinal_position: "-1" unit: "day" year: "2017"
        # e.g., "first day of 2020" -> ordinal_position: "1" unit: "day" year: "2020"
        day_word = cross("day", "day")
        pattern13 = (
            ordinal_position_tag
            + delete_space
            + insert('unit:"')
            + day_word
            + insert('"')
            + delete_space
            + delete_of
            + delete_space
            + year_tag
        )

        # Pattern 14: "ordinal_position day of [month]"
        # e.g., "second day of march" -> ordinal_position: "2" unit: "day" month: "march"
        pattern14 = (
            ordinal_position_tag
            + delete_space
            + insert('unit:"')
            + day_word
            + insert('"')
            + delete_space
            + delete_of
            + delete_space
            + month_tag
        )

        # Pattern 15: "ordinal_position day of [month] [year]"
        # e.g., "last day of february 2020" -> ordinal_position: "-1" unit: "day" month: "february" year: "2020"
        pattern15 = (
            ordinal_position_tag
            + delete_space
            + insert('unit:"')
            + day_word
            + insert('"')
            + delete_space
            + delete_of
            + delete_space
            + month_tag
            + delete_space
            + year_tag
        )

        # Pattern 16: "ordinal_position week of [month]"
        # e.g., "last week of june" -> ordinal_position: "-1" unit: "week" month: "june"
        week_word = cross("week", "week")
        pattern16 = (
            ordinal_position_tag
            + delete_space
            + insert('unit:"')
            + week_word
            + insert('"')
            + delete_space
            + delete_of
            + delete_space
            + month_tag
        )

        # Pattern 17: "ordinal_position week of [month] [year]"
        # e.g., "first week of january 2020" -> ordinal_position: "1" unit: "week" month: "january" year: "2020"
        pattern17 = (
            ordinal_position_tag
            + delete_space
            + insert('unit:"')
            + week_word
            + insert('"')
            + delete_space
            + delete_of
            + delete_space
            + month_tag
            + delete_space
            + year_tag
        )

        # Pattern 18: "ordinal_position month of [year]"
        # e.g., "last month of 2000" -> ordinal_position: "-1" unit: "month" year: "2000"
        month_word = cross("month", "month")
        pattern18 = (
            ordinal_position_tag
            + delete_space
            + insert('unit:"')
            + month_word
            + insert('"')
            + delete_space
            + delete_of
            + delete_space
            + year_tag
        )

        # Pattern 19: standalone "ordinal_position + unit" (day/week/month without "of")
        # e.g., "last day" -> ordinal_position: "-1" unit: "day"
        # e.g., "first week" -> ordinal_position: "1" unit: "week"
        pattern19 = ordinal_position_tag + delete_space + unit_tag

        # Pattern 20: "ordinal_position + unit + month" (without "of")
        # e.g., "last year september" -> ordinal_position: "-1" unit: "year" month: "september"
        # e.g., "next month january" -> ordinal_position: "1" unit: "month" month: "january"
        pattern20 = ordinal_position_tag + delete_space + unit_tag + delete_space + month_tag

        # Pattern 21: "time_modifier + 数字 + 时间单位"
        # e.g., "previous two months" -> time_modifier: "-1" value: "2" unit: "month"
        # e.g., "next three days" -> time_modifier: "1" value: "3" unit: "day"
        # Load cardinal numbers for the count
        # 词级FST：使用string_file加载digit.tsv（已转换为word_string_file）
        cardinal_numbers = string_file(get_abs_path("../data/numbers/digit.tsv"))
        # 为了确保数字匹配，也支持直接使用accep匹配单个数字
        # 这样可以匹配"2"、"3"等单个数字token
        numeric_digits = union(*[accep(str(i)) for i in range(10)])
        # 合并cardinal_numbers和numeric_digits
        all_numbers = cardinal_numbers | numeric_digits
        value_tag = pynutil.insert('value:"') + all_numbers + pynutil.insert('"')

        pattern21 = (
            insert('time_modifier:"')
            + time_modifiers
            + insert('"')
            + delete_space
            + value_tag
            + delete_space
            + unit_tag
        )

        # Pattern 22: time_modifier + unit (no value)
        # e.g., "this quarter" -> time_modifier: "0" unit: "quarter"
        # e.g., "next quarter" -> time_modifier: "1" unit: "quarter"
        # e.g., "last quarter" -> time_modifier: "-1" unit: "quarter"
        pattern22 = (
            insert('time_modifier:"') + time_modifiers + insert('"') + delete_space + unit_tag
        )

        # Pattern 23: weekday + of + week_offset
        # e.g., "wednesday of next week" -> week_day: "wednesday" offset_week: "1"
        # e.g., "monday of this week" -> week_day: "monday" offset_week: "0"
        weekday_only = insert('week_day:"') + self.weekday_names + insert('"')
        of_connector = delete_space + delete("of") + delete_space
        week_offset_expr = (
            insert('offset_week:"') + self.week_prefix + delete_space + delete("week") + insert('"')
        )

        pattern23 = weekday_only + of_connector + week_offset_expr

        # Pattern 24: week_offset + 's + weekday
        # e.g., "last week's sunday" -> offset_week: "-1" week_day: "sunday"
        # e.g., "next week's monday" -> offset_week: "1" week_day: "monday"
        possessive = delete_space.ques + word_delete("'s") + delete_space
        pattern24 = week_offset_expr + possessive + weekday_only

        # Pattern 25: time_modifier + weekday + of + month (+ year)
        # e.g., "last Monday of March" -> time_modifier: "-1" week_day: "monday" month: "march"
        # e.g., "first Sunday of March 2014" -> time_modifier: "1" week_day: "sunday" month: "march" year: "2014"
        time_modifier_tag = insert('time_modifier:"') + time_modifiers + insert('"')
        month_tag = insert('month:"') + self.month_names + insert('"')
        year_tag = delete_space + insert('year:"') + year_numeric + insert('"')

        pattern25 = (
            time_modifier_tag
            + delete_space
            + weekday_only
            + of_connector
            + month_tag
            + closure(year_tag, 0, 1)
        )

        # Pattern 26: ordinal + last + unit + of + year/month
        # e.g., "third last week of 2018" -> ordinal: "3" position: "last" unit: "week" year: "2018"
        # e.g., "second last day of May" -> ordinal: "2" position: "last" unit: "day" month: "may"
        # e.g., "2nd last week of October 2018" -> ordinal: "2" position: "last" unit: "week" month: "october" year: "2018"
        ordinal_numbers = string_file(get_abs_path("../data/numbers/ordinal_exceptions.tsv"))

        # Add support for numeric ordinals (1st, 2nd, 3rd, etc.)
        # 词级FST：分词后是"3" + "rd"，需要使用accep匹配词级token，然后删除后缀
        # 参考 date_base.py 的实现方式
        ordinal_suffix = union(accep("st"), accep("nd"), accep("rd"), accep("th"))

        # 为每个数字创建单独的匹配规则（词级版本）
        # 使用 accep 匹配数字词，然后删除后缀
        # accep(str(i)) 已经输出 str(i)，不需要额外的 insert
        # 例如："3" + "rd" -> "3"，"21" + "st" -> "21"
        numeric_ordinal_list = []
        for i in range(1, 32):
            numeric_ordinal_list.append(accep(str(i)) + delete_space.ques + delete(ordinal_suffix))
        numeric_ordinals = union(*numeric_ordinal_list)

        # Combine word ordinals and numeric ordinals
        all_ordinals = ordinal_numbers | numeric_ordinals
        ordinal_tag = insert('ordinal:"') + all_ordinals + insert('"')
        # 使用 delete('last') 确保只匹配 "last" 这个词，不能匹配空字符串
        last_word = delete_space + delete("last") + delete_space
        position_last_tag = insert('position:"last"')

        # Optional "the" at the beginning
        optional_the = closure(delete_space + delete("the") + delete_space, 0, 1)

        pattern26_year = (
            optional_the
            + ordinal_tag
            + last_word
            + position_last_tag
            + delete_space
            + insert('unit:"')
            + (time_unit | time_unit_plural)
            + insert('"')
            + delete_space
            + delete("of")
            + delete_space
            + insert('year:"')
            + year_numeric
            + insert('"')
        )

        pattern26_month = (
            optional_the
            + ordinal_tag
            + last_word
            + position_last_tag
            + delete_space
            + insert('unit:"')
            + (time_unit | time_unit_plural)
            + insert('"')
            + delete_space
            + delete("of")
            + delete_space
            + insert('month:"')
            + self.month_names
            + insert('"')
            + closure(delete_space + insert('year:"') + year_numeric + insert('"'), 0, 1)
        )

        pattern26 = pattern26_year | pattern26_month
        # 提高 Pattern 26 的优先级，确保 "ordinal + last + unit" 优先匹配
        pattern26 = pynutil.add_weight(pattern26, -0.5)

        # Pattern 27: time_modifier + unit + in + month + year
        # e.g., "last day in october 2015" -> time_modifier: "-1" unit: "day" month: "october" year: "2015"
        in_connector = delete_space + delete("in") + delete_space
        pattern27 = (
            time_modifier_tag
            + delete_space
            + unit_tag
            + in_connector
            + month_tag
            + delete_space
            + insert('year:"')
            + year_numeric
            + insert('"')
        )

        # Pattern 28: day + of + the + time_modifier + unit
        # e.g., "20th of the next month" -> day: "20" time_modifier: "1" unit: "month"
        # e.g., "15th of the previous month" -> day: "15" time_modifier: "-1" unit: "month"
        # 词级FST：使用accep匹配数字词，然后匹配可选的后缀
        day_numeric = union(*[accep(str(i)) for i in range(1, 32)])
        day_ordinal_suffix = union(accep("st"), accep("nd"), accep("rd"), accep("th"))
        day_ordinal = day_numeric + delete_space.ques + day_ordinal_suffix.ques
        day_tag = insert('day:"') + day_ordinal + insert('"')
        of_the = delete_space + delete("of") + delete_space + delete("the") + delete_space
        pattern28 = day_tag + of_the + time_modifier_tag + delete_space + unit_tag

        # Pattern 29: ordinal + weekday + of/in + month + year
        # e.g., "first tuesday of october" -> ordinal: "1" week_day: "tuesday" month: "october"
        # e.g., "third tuesday of september 2014" -> ordinal: "3" week_day: "tuesday" month: "september" year: "2014"
        weekday_names = string_file(get_abs_path("../data/week/weekday.tsv"))
        weekday_tag = insert('week_day:"') + weekday_names + insert('"')
        of_in_connector = (
            delete_space + delete("of") + delete_space | delete_space + delete("in") + delete_space
        )
        pattern29 = (
            ordinal_tag
            + delete_space
            + weekday_tag
            + of_in_connector
            + month_tag
            + closure(delete_space + insert('year:"') + year_numeric + insert('"'), 0, 1)
        )

        # Pattern 30: beginning/end of + time_modifier + unit
        # e.g., "beginning of this quarter" -> boundary: "beginning" time_modifier: "0" unit: "quarter"
        # e.g., "end of last month" -> boundary: "end" time_modifier: "-1" unit: "month"
        # e.g., "at the beginning of next year" -> boundary: "beginning" time_modifier: "1" unit: "year"

        # Optional "at the"
        optional_at_the = closure(delete("at") + delete_space + delete("the") + delete_space, 0, 1)

        # Optional "the"
        optional_the = closure(delete("the") + delete_space, 0, 1)

        # Boundary patterns
        beginning_patterns = []
        for boundary_type in ["beginning", "start"]:
            boundary_of = delete(boundary_type) + delete_space + delete("of") + delete_space
            beginning_pattern = (
                optional_at_the
                + boundary_of
                + optional_the
                + insert('boundary:"beginning"')
                + delete_space
                + time_modifier_tag
                + delete_space
                + unit_tag
            )
            beginning_patterns.append(beginning_pattern)

        end_patterns = []
        for boundary_type in ["end", "finish"]:
            boundary_of = delete(boundary_type) + delete_space + delete("of") + delete_space
            end_pattern = (
                optional_at_the
                + boundary_of
                + optional_the
                + insert('boundary:"end"')
                + delete_space
                + time_modifier_tag
                + delete_space
                + unit_tag
            )
            end_patterns.append(end_pattern)

        # Combine all boundary patterns
        pattern30 = union(*(beginning_patterns + end_patterns))

        # Pattern 30.5: beginning/end of + the + unit (without time_modifier)
        # e.g., "beginning of the month" -> boundary: "beginning" time_modifier: "0" unit: "month"
        # e.g., "end of the month" -> boundary: "end" time_modifier: "0" unit: "month"
        # e.g., "beginning of month" -> boundary: "beginning" time_modifier: "0" unit: "month"
        # e.g., "end of month" -> boundary: "end" time_modifier: "0" unit: "month"

        # Optional "at the"
        optional_at_the_simple = closure(
            delete("at") + delete_space + delete("the") + delete_space, 0, 1
        )

        # Optional "the"
        optional_the_simple = closure(delete("the") + delete_space, 0, 1)

        # Simple boundary patterns (without time_modifier, default to "0" = current)
        simple_beginning_patterns = []
        for boundary_type in ["beginning", "start"]:
            boundary_of = delete(boundary_type) + delete_space + delete("of") + delete_space
            simple_beginning_pattern = (
                optional_at_the_simple
                + boundary_of
                + optional_the_simple
                + insert('boundary:"beginning"')
                + delete_space
                + insert('time_modifier:"0"')
                + delete_space
                + unit_tag
            )
            simple_beginning_patterns.append(simple_beginning_pattern)

        simple_end_patterns = []
        for boundary_type in ["end", "finish"]:
            boundary_of = delete(boundary_type) + delete_space + delete("of") + delete_space
            simple_end_pattern = (
                optional_at_the_simple
                + boundary_of
                + optional_the_simple
                + insert('boundary:"end"')
                + delete_space
                + insert('time_modifier:"0"')
                + delete_space
                + unit_tag
            )
            simple_end_patterns.append(simple_end_pattern)

        # Combine simple boundary patterns
        pattern30_5 = union(*(simple_beginning_patterns + simple_end_patterns))

        # Pattern 30.6: BOM/EOM/EOY abbreviations
        # e.g., "BOM" -> boundary: "beginning" time_modifier: "0" unit: "month"
        # e.g., "EOM" -> boundary: "end" time_modifier: "0" unit: "month"
        # e.g., "EOY" -> boundary: "end" time_modifier: "0" unit: "year"
        # e.g., "the BOM" -> boundary: "beginning" time_modifier: "0" unit: "month"
        # e.g., "at the EOM" -> boundary: "end" time_modifier: "0" unit: "month"
        # e.g., "at the EOY" -> boundary: "end" time_modifier: "0" unit: "year"

        # Optional "at the" for abbreviations
        optional_at_the_abbr = closure(
            delete("at") + delete_space + delete("the") + delete_space, 0, 1
        )

        # Optional "the" for abbreviations
        optional_the_abbr = closure(delete("the") + delete_space, 0, 1)

        # BOM/EOM patterns
        bom_pattern = (
            optional_at_the_abbr
            + optional_the_abbr
            + delete("bom")
            + insert('boundary:"beginning"')
            + delete_space
            + insert('time_modifier:"0"')
            + delete_space
            + insert('unit:"month"')
        )

        eom_pattern = (
            optional_at_the_abbr
            + optional_the_abbr
            + (delete("EOM") | delete("eom"))
            + insert('boundary:"end"')
            + delete_space
            + insert('time_modifier:"0"')
            + delete_space
            + insert('unit:"month"')
        )

        eoy_pattern = (
            optional_at_the_abbr
            + optional_the_abbr
            + (delete("EOY") | delete("eoy"))
            + insert('boundary:"end"')
            + delete_space
            + insert('time_modifier:"0"')
            + delete_space
            + insert('unit:"year"')
        )

        eod_pattern = (
            optional_at_the_abbr
            + optional_the_abbr
            + delete("eod")
            + insert('boundary:"end"')
            + delete_space
            + insert('time_modifier:"0"')
            + delete_space
            + insert('unit:"day"')
        )

        # BOM/EOM/EOY/EOD pattern
        pattern30_6 = union(bom_pattern, eom_pattern, eoy_pattern, eod_pattern)

        # Pattern 30.7: by + beginning/end patterns (for time ranges)
        # e.g., "by EOM" -> boundary: "end" time_modifier: "0" unit: "month" range: "by"
        # e.g., "by the end of the month" -> boundary: "end" time_modifier: "0" unit: "month" range: "by"

        # "by" prefix for time ranges
        by_prefix = delete("by") + delete_space

        # By + BOM/EOM patterns
        by_bom_pattern = (
            by_prefix
            + optional_the_abbr
            + delete("bom")
            + insert('boundary:"beginning"')
            + delete_space
            + insert('time_modifier:"0"')
            + delete_space
            + insert('unit:"month"')
            + delete_space
            + insert('range:"by"')
        )

        by_eom_pattern = (
            by_prefix
            + optional_the_abbr
            + (delete("EOM") | delete("eom"))
            + insert('boundary:"end"')
            + delete_space
            + insert('time_modifier:"0"')
            + delete_space
            + insert('unit:"month"')
            + delete_space
            + insert('range:"by"')
        )

        by_eoy_pattern = (
            by_prefix
            + optional_the_abbr
            + (delete("EOY") | delete("eoy"))
            + insert('boundary:"end"')
            + delete_space
            + insert('time_modifier:"0"')
            + delete_space
            + insert('unit:"year"')
            + delete_space
            + insert('range:"by"')
        )

        by_eod_pattern = (
            by_prefix
            + optional_the_abbr
            + delete("eod")
            + insert('boundary:"end"')
            + delete_space
            + insert('time_modifier:"0"')
            + delete_space
            + insert('unit:"day"')
            + delete_space
            + insert('range:"by"')
        )

        # By + beginning/end of patterns
        by_simple_beginning_patterns = []
        for boundary_type in ["beginning", "start"]:
            boundary_of = delete(boundary_type) + delete_space + delete("of") + delete_space
            by_simple_beginning_pattern = (
                by_prefix
                + optional_the_simple  # Move "the" before boundary
                + boundary_of
                + optional_the_simple
                + insert('boundary:"beginning"')
                + delete_space
                + insert('time_modifier:"0"')
                + delete_space
                + unit_tag
                + delete_space
                + insert('range:"by"')
            )
            by_simple_beginning_patterns.append(by_simple_beginning_pattern)

        by_simple_end_patterns = []
        for boundary_type in ["end", "finish"]:
            boundary_of = delete(boundary_type) + delete_space + delete("of") + delete_space
            by_simple_end_pattern = (
                by_prefix
                + optional_the_simple  # Move "the" before boundary
                + boundary_of
                + optional_the_simple
                + insert('boundary:"end"')
                + delete_space
                + insert('time_modifier:"0"')
                + delete_space
                + unit_tag
                + delete_space
                + insert('range:"by"')
            )
            by_simple_end_patterns.append(by_simple_end_pattern)

        # Combine by patterns
        pattern30_7 = union(
            by_bom_pattern,
            by_eom_pattern,
            by_eoy_pattern,
            by_eod_pattern,
            *(by_simple_beginning_patterns + by_simple_end_patterns),
        )

        # Pattern 31: time_modifier + season
        # e.g., "this summer" -> time_modifier: "0" season: "summer"
        # e.g., "next winter" -> time_modifier: "1" season: "winter"
        # e.g., "last spring" -> time_modifier: "-1" season: "spring"
        pattern31 = time_modifier_tag + delete_space + season_tag

        # Pattern 32: current + season
        # e.g., "current summer" -> time_modifier: "0" season: "summer"
        current_season = (
            delete("current")
            + delete_space
            + insert('time_modifier:"0"')
            + delete_space
            + season_tag
        )

        # Pattern 33: past + season/seasons
        # e.g., "past season" -> time_modifier: "-1" season: "season"
        # e.g., "past seasons" -> time_modifier: "-1" season: "season"
        past_season = (
            delete("past") + delete_space + insert('time_modifier:"-1"') + delete_space + season_tag
        )

        # Pattern 34: season + in + year
        # e.g., "summer in 2012" -> season: "summer" year: "2012"
        season_in_year = season_tag + delete_space + delete("in") + delete_space + year_tag

        # Pattern 35: "N + weekdays + back/ago"
        # e.g., "2 thursdays back" -> value: "2" week_day: "thursday" direction: "-1"
        # e.g., "3 mondays ago" -> value: "3" week_day: "monday" direction: "-1"

        # Support weekday plural forms (词级FST：使用word_cross处理多词短语)
        weekdays_plural = union(
            word_cross("mondays", "monday"),
            word_cross("tuesdays", "tuesday"),
            word_cross("wednesdays", "wednesday"),
            word_cross("thursdays", "thursday"),
            word_cross("fridays", "friday"),
            word_cross("saturdays", "saturday"),
            word_cross("sundays", "sunday"),
        )

        # back/ago direction markers (词级FST：使用word_cross)
        back_ago = union(
            word_cross("back", "-1"),
            word_cross("ago", "-1"),
        )

        pattern35 = (
            value_tag
            + delete_space
            + insert('week_day:"')
            + (weekdays_plural | weekday_full | weekday_abbr_safe)
            + insert('"')
            + delete_space
            + insert('direction:"')
            + back_ago
            + insert('"')
        )

        # Combine all patterns (more specific first)
        # The order is critical - more specific patterns must come before general ones
        tagger = (
            pattern30  # beginning/end of + time_modifier + unit (highest priority)
            | pattern30_5  # beginning/end of + the + unit (without time_modifier)
            | pattern30_6  # BOM/EOM abbreviations
            | pattern30_7  # by + beginning/end patterns (for time ranges)
            | pattern31  # time_modifier + season (high priority)
            | current_season  # current + season
            | past_season  # past + season
            | season_in_year  # season + in + year (high priority)
            | pattern35  # N + weekdays + back/ago (high priority)
            | pattern26  # ordinal + last + unit + of + year/month (high priority, before pattern14/15/16/17)
            | pattern17  # ordinal week of month year (most specific)
            | pattern15  # ordinal day of month year
            | pattern2  # position + unit + month + year
            | pattern18  # ordinal month of year
            | pattern16  # ordinal week of month
            | pattern13  # ordinal day of year (no "year" word)
            | pattern3  # position + unit + year
            | pattern4  # position + unit + month + year
            | pattern14  # ordinal day of month
            | pattern20  # ordinal + unit + month (new pattern)
            | pattern21  # time_modifier + 数字 + 时间单位 (new pattern)
            | pattern22  # time_modifier + 时间单位 (no value) (new pattern)
            | pattern23  # weekday + of + week_offset (new pattern)
            | pattern24  # week_offset + 's + weekday (new pattern)
            | pattern25  # time_modifier + weekday + of + month (new pattern)
            | pattern27  # time_modifier + unit + in + month + year (new pattern)
            | pattern28  # day + of + the + time_modifier + unit (new pattern)
            | pattern29  # ordinal + weekday + of/in + month + year (new pattern)
            | pattern11b  # weekday + after next (higher priority)
            | pattern11c_month  # month + after next (higher priority)
            | pattern11c_unit  # year/week/day + after next (higher priority)
            | pattern11  # weekday + week_offset
            | pattern10b  # month_offset (simple last month / next month)
            | pattern10  # day + month_offset
            | pattern9  # month + month_offset
            | pattern19  # standalone ordinal + unit
            | pattern1  # position + unit + month
            | pattern6_year  # year possessive
            | pattern6_month  # month possessive
            | pattern12  # time modifier (standalone)
            | pattern12a  # the time modifier (standalone)
            | pattern5  # day before/after
        )

        self.tagger = self.add_tokens(tagger)

    def _build_weekday_names(self):
        """Build weekday names FST (word-level)"""
        return union(
            accep("monday"),
            accep("tuesday"),
            accep("wednesday"),
            accep("thursday"),
            accep("friday"),
            accep("saturday"),
            accep("sunday"),
        )

    def _build_month_names(self):
        """Build month names FST"""
        return string_file(get_abs_path("../data/date/months.tsv"))

    def _build_week_prefix(self):
        """Build week prefix FST (next, last, this)"""
        return string_file(get_abs_path("../data/week/week_prefix.tsv"))
