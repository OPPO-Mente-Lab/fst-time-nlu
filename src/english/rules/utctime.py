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
from ..word_level_pynini import union, string_file, accep, closure
from ..word_level_pynini import pynutil
from ...core.processor import Processor
from ...core.utils import INPUT_LOWER_CASED, get_abs_path
from ..word_level_pynini import word_delete_space
from .base.date_base import DateBaseRule
from .base.time_base import TimeBaseRule


class UTCTimeRule(Processor):
    """
    English UTC time rule processor

    Handles absolute time expressions like:
    - "January 15, 2025"
    - "three thirty pm"
    - "the fifth of March"
    - "twenty twenty"
    """

    def __init__(self, input_case: str = INPUT_LOWER_CASED):
        super().__init__(name="time_utc")
        self.input_case = input_case
        self.date_base = DateBaseRule(input_case=input_case)
        self.time_base = TimeBaseRule(input_case=input_case)
        self.build_tagger()

    def build_tagger(self):
        """Build UTC time FST tagger"""

        # Add optional prepositions
        delete = pynutil.delete
        insert = pynutil.insert
        delete_space = word_delete_space()  # 使用词级delete_space
        optional_on = closure(delete("on") + delete_space, 0, 1)
        optional_in = closure(delete("in") + delete_space, 0, 1)

        # Cache frequently used graphs to avoid redundant constructions

        # Year only: "in 2021" -> year: "2021"
        # Following Chinese FST strategy: require context (preposition) to avoid false matches
        # e.g., "Pay ABC 2000" should not be recognized as year 2000
        # Word form years like "twenty twenty" are also disabled to avoid over-matching
        year_preposition = union(
            accep("in"),
            accep("since"),
            accep("during"),
            accep("before"),
            accep("after"),
            accep("until"),
            accep("from"),
            accep("by"),
            accep("the"),
        )

        # Numeric years REQUIRE preposition (not optional)
        # year_preposition是FST，pynutil.delete会自动处理FST参数
        year_only = (
            delete(year_preposition)
            + delete_space
            + insert('year:"')
            + self.date_base.year_numeric
            + insert('"')
        ).optimize()

        # Year with AD/BC suffix: "2014 AD" -> year: "2014" year_suffix: "AD"
        # Create year suffix patterns manually - handle both uppercase and lowercase
        ad_pattern = union("AD", "A.D.", "ad", "a.d.", "CE", "ce")
        bc_pattern = union("BC", "B.C.", "bc", "b.c.", "BCE", "bce")
        year_suffix_pattern = ad_pattern | bc_pattern

        year_with_suffix = (
            insert('year:"')
            + self.date_base.year_numeric
            + insert('"')
            + delete_space.ques
            + insert(' year_suffix:"')
            + year_suffix_pattern
            + insert('"')
        ).optimize()

        # Month only: "in january" -> month: "january"
        month_only = (optional_in + self.date_base.build_month_rules()).optimize()

        # Month + Year: "march 2026" -> month: "march" year: "2026"
        month_year = self.date_base.build_month_year_rules().optimize()

        # Month + Day: "january fifth" -> month: "january" day: "5"
        month_day = self.date_base.build_month_day_rules().optimize()

        # Day + Month (British): "the fifth of january" -> day: "5" month: "january"
        day_month = self.date_base.build_day_month_rules().optimize()

        # Full date with optional year
        # "january fifth twenty twelve" -> month: "january" day: "5" year: "2012"
        # "april 20 2021" -> month: "april" day: "20" year: "2021"
        full_date = self.date_base.build_date_rules().optimize()

        # Numeric date: "2021-09-21" -> year: "2021" month: "9" day: "21"
        numeric_date = self.date_base.build_numeric_date_rules().optimize()

        # Time only: "three thirty pm" -> hour: "3" minute: "30" period: "pm"
        time_only = self.time_base.build_time_rules().optimize()

        # Simple numeric time with strong context
        # Following Chinese FST strategy: require strong context markers
        # "9 o'clock" -> hour: "9" minute: "00" (has o'clock suffix)
        # NOTE: "at N" pattern is NOT handled here to avoid matching "Rat 6", etc.
        # Instead, it will be handled by ContextMerger to merge "at" token + number token
        oclock_keyword = (
            delete_space.ques + delete("o'clock")
            | delete_space.ques + delete("oclock")
            | delete_space + delete("o") + delete_space + delete("clock")
        )

        simple_hour_oclock = (
            insert('hour:"') + self.time_base.hour + insert('" minute:"00"') + oclock_keyword
        ).optimize()

        # Only use o'clock pattern
        simple_hour = simple_hour_oclock

        # Period + time: "noon 12 o'clock" -> noon: "noon" hour: "12" minute: "00"
        # This handles cases like "noon 12 o'clock", "morning 8 am", etc.
        from .period import PeriodRule

        # Extract period content from period_tag (remove the wrapper and extract the period value)
        # period_tag outputs: time_period { period: "noon" }
        # We need to extract just the period value and create noon: "noon"

        # Create a simple period pattern that outputs noon: "period_name"
        basic_periods = string_file(get_abs_path("../data/period/basic_periods.tsv"))

        period_with_time = (
            insert('noon:"')
            + basic_periods
            + insert('"')  # noon:"noon"
            + delete_space.ques  # Optional space
            + time_only  # hour: "12" minute: "00"
        ).optimize()

        # Time + in the + period: "3 in the morning" -> hour: "3" minute: "00" noon: "morning"
        # This handles cases like "3 in the morning", "3:20 in the afternoon", "3 o'clock in the afternoon"
        # Create specific patterns for different time formats

        # Pattern 1: "3 in the morning" (hour only)
        hour_only_with_period = (
            insert('hour:"')
            + self.time_base.hour_numeric
            + insert('"')
            + insert(' minute:"00"')
            + delete_space.ques  # Optional space
            + delete("in")
            + delete_space.ques  # "in"
            + delete("the").ques
            + delete_space.ques  # Optional "the"
            + insert('noon:"')
            + basic_periods
            + insert('"')  # noon:"morning"
        ).optimize()

        # Pattern 2: "3:20 in the afternoon" (hour:minute) - require 2-digit minutes
        # Create 2-digit minute pattern (00-59)
        minute_two_digit = union(*[accep(f"{i:02d}") for i in range(60)])  # 00-59

        hour_minute_with_period = (
            insert('hour:"')
            + self.time_base.hour_numeric
            + insert('"')
            + delete(":")  # Delete colon (word_delete handles single char tokens)
            + insert(' minute:"')
            + minute_two_digit
            + insert('"')
            + delete_space.ques  # Optional space
            + delete("in")
            + delete_space.ques  # "in"
            + delete("the").ques
            + delete_space.ques  # Optional "the"
            + insert('noon:"')
            + basic_periods
            + insert('"')  # noon:"afternoon"
        ).optimize()

        # Pattern 3: "3 o'clock in the afternoon" (hour with o'clock)
        hour_oclock_with_period = (
            insert('hour:"')
            + self.time_base.hour_numeric
            + insert('"')
            + insert(' minute:"00"')
            + delete_space.ques  # Optional space
            + delete("o'clock")
            + delete_space.ques  # "o'clock"
            + delete_space.ques  # Optional space
            + delete("in")
            + delete_space.ques  # "in"
            + delete("the").ques
            + delete_space.ques  # Optional "the"
            + insert('noon:"')
            + basic_periods
            + insert('"')  # noon:"afternoon"
        ).optimize()

        # Pattern 4: "tonight at 8 o'clock" (period + at + time)
        period_at_time = (
            insert('noon:"')
            + basic_periods
            + insert('"')  # noon:"tonight"
            + delete_space.ques  # Optional space
            + delete("at")
            + delete_space.ques  # "at"
            + insert('hour:"')
            + self.time_base.hour_numeric
            + insert('"')
            + insert(' minute:"00"')
            + closure(delete_space.ques + delete("o'clock"), 0, 1)  # Optional "o'clock"
        ).optimize()

        # Pattern 5: "in the evening at eight" (in the + period + at + time)
        in_the_period_at_time_word = (
            delete("in")
            + delete_space.ques  # "in"
            + delete("the").ques
            + delete_space.ques  # Optional "the"
            + insert('noon:"')
            + basic_periods
            + insert('"')  # noon:"evening"
            + delete_space.ques  # Optional space
            + delete("at")
            + delete_space.ques  # "at"
            + insert('hour:"')
            + self.time_base.time_words
            + insert('"')  # "eight"
            + insert(' minute:"00"')
        ).optimize()

        # Pattern 6: "in the morning at 9" (in the + period + at + numeric hour)
        in_the_period_at_time_numeric = (
            delete("in")
            + delete_space.ques  # "in"
            + delete("the").ques
            + delete_space.ques  # Optional "the"
            + insert('noon:"')
            + basic_periods
            + insert('"')  # noon:"morning"
            + delete_space.ques  # Optional space
            + delete("at")
            + delete_space.ques  # "at"
            + insert('hour:"')
            + self.time_base.hour_numeric
            + insert('"')  # "9"
            + insert(' minute:"00"')
        ).optimize()

        # Pattern 7: "in the afternoon at 2:30" (in the + period + at + HH:MM) - require 2-digit minutes
        in_the_period_at_time_hm = (
            delete("in")
            + delete_space.ques  # "in"
            + delete("the").ques
            + delete_space.ques  # Optional "the"
            + insert('noon:"')
            + basic_periods
            + insert('"')  # noon:"afternoon"
            + delete_space.ques  # Optional space
            + delete("at")
            + delete_space.ques  # "at"
            + insert('hour:"')
            + self.time_base.hour_numeric
            + insert('"')  # "2"
            + delete(":")  # Delete colon (word_delete handles single char tokens)
            + insert(' minute:"')
            + minute_two_digit
            + insert('"')  # "30" - require 2-digit
        ).optimize()

        # Combine all time + period patterns
        time_with_period = (
            hour_only_with_period
            | hour_minute_with_period
            | hour_oclock_with_period
            | period_at_time
            | in_the_period_at_time_word
            | in_the_period_at_time_numeric
            | in_the_period_at_time_hm
        )

        # Date + time combinations
        # "january fifth at three thirty pm"
        date_time = (
            full_date
            + delete(",").ques  # Optional comma (word_delete handles single char tokens)
            + delete_space.ques
            + (delete("at") + delete_space).ques  # Optional "at"
            + insert(" ")
            + time_only
        ).optimize()

        # Numeric date + time combinations
        # "2021-09-21 14:30" or "2021-09-21 at 2:30 pm"
        numeric_date_time = (
            numeric_date
            + delete(",").ques  # Optional comma (word_delete handles single char tokens)
            + delete_space.ques
            + (delete("at") + delete_space).ques  # Optional "at"
            + insert(" ")
            + time_only
        ).optimize()

        # Load year_prefix data for year modifiers
        year_prefix = string_file(get_abs_path("../data/date/year_prefix.tsv"))
        offset_year_tag = insert('offset_year:"') + year_prefix + insert('"')

        # Year modifier patterns - 只保留最常用的模式
        # Pattern: year_prefix + month + day (e.g., "last year august 20") - 最常用
        year_prefix_month_day = (
            offset_year_tag
            + delete_space
            + insert('month:"')
            + self.date_base.month
            + insert('"')
            + delete_space
            + insert('day:"')
            + self.date_base.day
            + insert('"')
        ).optimize()

        # Ordinal day only: "on the 2nd" -> day: "2"
        optional_the = closure(delete("the") + delete_space, 0, 1)
        ordinal_day_only = (
            optional_on
            + optional_the
            + insert('day:"')
            + self.time_base.ordinal_numeric
            + insert('"')
        ).optimize()

        # Dot-separated time patterns: H.M and H.M.S
        # e.g. "at 6.50" -> hour: "6" minute: "50"
        # e.g. "at 6.50.30" -> hour: "6" minute: "50" second: "30"
        # e.g. "at 650.650.6500" -> hour: "650" minute: "650" second: "6500" (will be validated in parser)

        # Create generic number patterns for dot-separated times
        # These will match hour with 1-4 digits, but require minutes/seconds to have leading zeros
        generic_digit = union(
            accep("0"),
            accep("1"),
            accep("2"),
            accep("3"),
            accep("4"),
            accep("5"),
            accep("6"),
            accep("7"),
            accep("8"),
            accep("9"),
        )
        # Match 1-4 digits to support cases like "6500"
        generic_number = (
            generic_digit + generic_digit.ques + generic_digit.ques + generic_digit.ques
        )

        # Require 2-digit minute/second with leading zeros when using dot as separator
        minute_two_digit = union(*[accep(f"{i:02d}") for i in range(60)])
        second_two_digit = minute_two_digit

        # IMPORTANT: Use accep directly for dots to ensure atomic matching
        # H.M.S format with mandatory "at" prefix to ensure atomic matching
        dot_time_atomic = (
            delete("at")
            + delete_space.ques  # "at "
            + insert('hour:"')
            + generic_number
            + insert('"')  # hour
            + delete(".")  # first dot (word_delete handles single char tokens)
            + insert(' minute:"')
            + minute_two_digit
            + insert('"')  # minute (require leading zero)
            + delete(".")  # second dot (word_delete handles single char tokens)
            + insert(' second:"')
            + second_two_digit
            + insert('"')  # second (require leading zero)
        ).optimize()

        # H.M.S format (without "at" prefix)
        dot_time_hms_noat = (
            insert('hour:"')
            + generic_number
            + insert('"')
            + delete(".")  # word_delete handles single char tokens
            + insert(' minute:"')
            + minute_two_digit
            + insert('"')
            + delete(".")  # word_delete handles single char tokens
            + insert(' second:"')
            + second_two_digit
            + insert('"')
        ).optimize()

        # H.M format (with "at" prefix)
        dot_time_hm_at = (
            delete("at")
            + delete_space.ques
            + insert('hour:"')
            + generic_number
            + insert('"')
            + delete(".")  # word_delete handles single char tokens
            + insert(' minute:"')
            + minute_two_digit
            + insert('"')
        ).optimize()

        # H.M format (without "at" prefix)
        dot_time_hm_noat = (
            insert('hour:"')
            + generic_number
            + insert('"')
            + delete(".")  # word_delete handles single char tokens
            + insert(' minute:"')
            + minute_two_digit
            + insert('"')
        ).optimize()

        # Combine all patterns (order by priority - most specific first)
        add_weight = pynutil.add_weight
        utc_time = union(
            add_weight(
                dot_time_atomic, 0.01
            ),  # Atomic dot-separated H.M.S with "at" (highest priority)
            add_weight(dot_time_hms_noat, 0.02),  # Dot-separated H.M.S without "at"
            add_weight(dot_time_hm_at, 0.03),  # Dot-separated H.M with "at"
            add_weight(dot_time_hm_noat, 0.04),  # Dot-separated H.M without "at"
            add_weight(numeric_date_time, 0.1),  # Numeric date+time
            add_weight(numeric_date, 0.05),  # Numeric date only (最高优先级)
            add_weight(date_time, 0.3),  # Date + time
            add_weight(
                time_with_period, 0.32
            ),  # Time + in the + period (3 in the morning) - HIGH priority
            add_weight(period_with_time, 0.35),  # Period + time (noon 12 o'clock)
            add_weight(full_date, 0.4),  # Full date (month + day + year)
            add_weight(
                year_prefix_month_day, 0.42
            ),  # Year_prefix + month + day (e.g., "last year august 20")
            add_weight(month_year, 0.45),  # Month + year (between full_date and month_day)
            add_weight(month_day, 0.5),  # Month + day
            add_weight(day_month, 0.6),  # Day + month (British)
            add_weight(ordinal_day_only, 0.65),  # Ordinal day (2nd, 3rd, etc.)
            add_weight(month_only, 0.7),  # Month only
            add_weight(time_only, 0.9),  # Time only (lower priority to avoid over-matching)
            add_weight(
                year_with_suffix, 0.8
            ),  # Year with AD/BC suffix (higher priority than year_only)
            add_weight(year_only, 0.9),  # Year only (much lower priority to avoid partial matches)
            add_weight(simple_hour, 0.95),  # Simple numeric hour (e.g., "9")
        ).optimize()

        # Add class wrapper and optimize - 直接使用词级pynutil.insert
        # 不使用self.add_tokens()，因为它可能在某些情况下使用错误的insert
        # 注意：TokenParser的parse_chars有bug，期望"name { "但实际只能匹配"name{ "或"name { "（有空格但会被parse_ws跳过）
        # 使用"time_utc { "格式，因为parse_ws会在parse_key后跳过空格，然后parse_chars匹配'{'
        tagger = (insert("time_utc { ") + utc_time + insert(" }")).optimize()

        # 确保符号表被保留（optimize可能丢失符号表）
        # 强制设置GlobalSymbolTable，确保词级FST兼容性
        from ..global_symbol_table import get_symbol_table

        sym = get_symbol_table()
        tagger.set_input_symbols(sym)
        tagger.set_output_symbols(sym)

        self.tagger = tagger
