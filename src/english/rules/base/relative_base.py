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
from ...word_level_pynini import (
    union,
    compose,
    closure,
    concat,
    optimize,
    Fst,
    accep,
    pynutil,
    get_symbol_table,
    word_string_file,
)

from ....core.utils import get_abs_path, INPUT_LOWER_CASED
from ...word_level_pynini import word_delete_space
from .date_base import DateBaseRule
from .time_base import TimeBaseRule


class RelativeBaseRule:
    """Relative time base rule class for English"""

    def __init__(self, input_case: str = INPUT_LOWER_CASED):
        self.input_case = input_case
        self.time = TimeBaseRule(input_case=input_case).build_time_rules()

        # 获取全局SymbolTable
        self.sym = get_symbol_table()

        # Load TSV files（使用词级版本）
        self.year_prefix = word_string_file(get_abs_path("../../data/date/year_prefix.tsv"))
        self.month_prefix = word_string_file(get_abs_path("../../data/date/month_prefix.tsv"))
        self.day_prefix = word_string_file(get_abs_path("../../data/date/day_prefix.tsv"))
        self.now_expressions = word_string_file(
            get_abs_path("../../data/relative/now_expressions.tsv")
        )
        self.weekday = word_string_file(get_abs_path("../../data/week/weekday.tsv"))
        self.week_prefix = word_string_file(get_abs_path("../../data/week/week_prefix.tsv"))

        # Load period data for combination
        basic_periods = word_string_file(get_abs_path("../../data/period/basic_periods.tsv"))
        extended_periods = word_string_file(get_abs_path("../../data/period/extended_periods.tsv"))
        self.periods = basic_periods | extended_periods

        # Load period boundaries (month/quarter/year beginning/end)
        self.period_boundaries = word_string_file(
            get_abs_path("../../data/date/period_boundaries.tsv")
        )

    def build_std_rules(self):
        """Build standard relative time rules"""
        # 使用词级delete_space
        delete_space = word_delete_space()
        # Possessive marker: 's or ' (for possessive forms like "today's", "tomorrow's")
        possessive = pynutil.delete("'s") | pynutil.delete("'")

        # 0. "Now" expressions (now, right now, just now, at the moment, ATM)
        # These represent the current moment (offset_day: "0" + offset_time: "0")
        now_expr = (
            pynutil.insert('offset_day:"')
            + self.now_expressions
            + pynutil.insert('" offset_time:"0"')
        )

        # 1. Specific year offset (last year / next year)
        specific_year_dates = (
            pynutil.insert('offset_year:"') + self.year_prefix + pynutil.insert('"')
        )

        # 2. Specific month offset (last month / next month)
        specific_month_dates = (
            pynutil.insert('offset_month:"') + self.month_prefix + pynutil.insert('"')
        )

        # 3. Specific day offset (yesterday / today / tomorrow)
        # 3.1. With possessive: yesterday's, today's, tomorrow's
        specific_day_dates_possessive = (
            pynutil.insert('offset_day:"')
            + self.day_prefix
            + pynutil.insert('"')
            + delete_space.ques
            + possessive
        )

        # 3.2. Without possessive: yesterday, today, tomorrow
        # Use direct TSV mapping for better word boundary handling
        specific_day_dates = (
            pynutil.insert('offset_day:"')
            + self.day_prefix
            + pynutil.insert('"')
            + delete_space.ques
        )

        # 3a. Special case: "tonight" with offset_day and is_tonight marker
        tonight = accep("tonight")
        tonight_marker = (
            pynutil.insert('offset_day:"0" is_tonight:"') + tonight + pynutil.insert('"')
        )

        # 3b. Special case: "tonight's" with possessive marker
        tonight_possessive = (
            pynutil.insert('offset_day:"0" is_tonight:"')
            + tonight
            + pynutil.insert('"')
            + delete_space.ques
            + possessive
        )

        # 4. Day + period (yesterday morning, tomorrow evening, etc.)
        day_with_period = (
            specific_day_dates
            + delete_space
            + pynutil.insert('noon:"')
            + self.periods
            + pynutil.insert('"')
        )

        # 4b. Day + period + possessive (tomorrow afternoon's, yesterday morning's, etc.)
        day_with_period_possessive = (
            specific_day_dates
            + delete_space
            + pynutil.insert('noon:"')
            + self.periods
            + pynutil.insert('"')
            + delete_space.ques
            + possessive
        )

        # 4a. Last/Next + period (last night, next morning, etc.)
        # Use existing time_modifiers.tsv for "last" and "next"
        last_next_prefix = word_string_file(get_abs_path("../../data/date/time_modifiers.tsv"))

        last_next_with_period = (
            pynutil.insert('offset_day:"')
            + last_next_prefix
            + pynutil.insert('"')
            + delete_space
            + pynutil.insert('noon:"')
            + self.periods
            + pynutil.insert('"')
        )

        # 5. Day + time (yesterday at 3pm, tomorrow 9:00)
        # 5a. Special case: tonight + time (mark with is_tonight)
        tonight_with_time = tonight_marker + delete_space + self.time | (
            self.time + delete_space + tonight_marker
        )

        # 5b. Regular day + time
        day_with_time = specific_day_dates + delete_space + self.time | (
            self.time + delete_space + specific_day_dates
        )

        # 5c. Day + period + time (tomorrow morning 8am, today afternoon 3pm)
        day_with_period_time = (
            specific_day_dates
            + delete_space
            + pynutil.insert('noon:"')
            + self.periods
            + pynutil.insert('"')
            + delete_space
            + self.time
        )

        # 6. Number + weekday + from now (3 fridays from now, two mondays from now)
        # Load number words for "two", "three", etc.
        number_words = word_string_file(get_abs_path("../../data/numbers/digit.tsv"))

        # Create weekday offset rules
        weekday_offset = (
            pynutil.insert('offset_week:"')
            + number_words
            + pynutil.insert('"')
            + delete_space
            + pynutil.insert('weekday:"')
            + self.weekday
            + pynutil.insert('"')
            + delete_space
            + pynutil.delete("from")
            + delete_space
            + pynutil.delete("now")
        )

        # 7. Period boundaries (month/quarter/year beginning/end)
        # 7a. Month boundaries: beginning of this month, end of last month, etc.
        month_boundaries = self._build_period_boundary_patterns("month")

        # 7b. Quarter boundaries: beginning of this quarter, end of last quarter, etc.
        quarter_boundaries = self._build_period_boundary_patterns("quarter")

        # 7c. Year boundaries: beginning of this year, end of last year, etc.
        year_boundaries = self._build_period_boundary_patterns("year")

        # Combine all relative time rules
        # Priority: more specific patterns first to avoid greedy matching issues
        relative_date = (
            now_expr  # now, right now, just now (highest priority)
            | month_boundaries  # beginning of this month, end of last month
            | quarter_boundaries  # beginning of this quarter, end of last quarter
            | year_boundaries  # beginning of this year, end of last year
            | weekday_offset  # 3 fridays from now (high priority)
            | day_with_period_time  # tomorrow morning 8am (most specific first)
            | day_with_period_possessive  # tomorrow afternoon's (very specific)
            | day_with_time  # yesterday 3pm
            | day_with_period  # yesterday morning
            | specific_day_dates  # yesterday, today, tomorrow
            | specific_day_dates_possessive  # yesterday's, today's, tomorrow's
            | tonight_possessive  # tonight's
            | tonight_marker  # tonight
            | specific_month_dates  # last month
            | specific_year_dates  # last year
            | last_next_with_period  # last night, next morning
            | tonight_with_time  # tonight 8:30 (least specific last)
        )

        return relative_date

    def _build_period_boundary_patterns(self, period_type):
        """
        Build period boundary patterns for month/quarter/year
        Examples: "beginning of this month", "end of last quarter", "at the beginning of next year"
        """
        # Get the appropriate prefix file based on period type
        if period_type == "month":
            period_prefix = self.month_prefix
            period_word = "month"
            offset_field = "offset_month"
        elif period_type == "quarter":
            period_prefix = self.year_prefix  # Use year_prefix for quarters too
            period_word = "quarter"
            offset_field = "offset_quarter"
        elif period_type == "year":
            period_prefix = self.year_prefix
            period_word = "year"
            offset_field = "offset_year"
        else:
            return accep("")  # Empty pattern for unknown types

        # 使用词级delete_space
        delete_space = word_delete_space()

        # Optional "at the"
        optional_at_the = closure(
            pynutil.delete("at") + delete_space + pynutil.delete("the") + delete_space,
            0,
            1,
        )

        # Optional "the"
        optional_the = closure(pynutil.delete("the") + delete_space, 0, 1)

        # Optional "around" modifier
        optional_around = closure(pynutil.delete("around") + delete_space, 0, 1)

        # Build beginning patterns: [at the] beginning of [the] [around] {prefix} {period}
        beginning_patterns = []
        for boundary_type in ["beginning", "start"]:
            boundary_of = (
                pynutil.delete(boundary_type) + delete_space + pynutil.delete("of") + delete_space
            )
            beginning_pattern = (
                optional_at_the
                + boundary_of
                + optional_the
                + optional_around
                + pynutil.insert(f'{offset_field}: "')
                + period_prefix
                + pynutil.insert('"')
                + delete_space
                + pynutil.delete(period_word)
                + pynutil.insert(f' {period_type}_period: "{period_type}beginning"')
            )
            beginning_patterns.append(beginning_pattern)

        # Build end patterns: [at the] end of [the] [around] {prefix} {period}
        end_patterns = []
        for boundary_type in ["end", "finish"]:
            boundary_of = (
                pynutil.delete(boundary_type) + delete_space + pynutil.delete("of") + delete_space
            )
            end_pattern = (
                optional_at_the
                + boundary_of
                + optional_the
                + optional_around
                + pynutil.insert(f'{offset_field}: "')
                + period_prefix
                + pynutil.insert('"')
                + delete_space
                + pynutil.delete(period_word)
                + pynutil.insert(f' {period_type}_period: "{period_type}end"')
            )
            end_patterns.append(end_pattern)

        # Combine all patterns
        all_patterns = beginning_patterns + end_patterns
        if all_patterns:
            return union(*all_patterns)
        else:
            return accep("")  # Empty pattern if no patterns
