# Copyright (c) 2021, NVIDIA CORPORATION.  All rights reserved.
# Copyright 2015 and onwards Google, Inc.
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
    cross,
    invert,
    string_map,
    pynutil,
    get_symbol_table,
    word_string_file,
)

# pynutil已从word_level_pynini导入（词级版本）

from .cardinal import CardinalFst
from ....core.utils import (
    get_abs_path,
    num_to_word,
    INPUT_CASED,
    INPUT_LOWER_CASED,
)

# 词级delete_space和delete_extra_space
from ...word_level_pynini import word_delete_space, word_delete_extra_space
from ...word_level_utils import word_accep

# 词级insert_space（使用词级pynutil）
insert_space = pynutil.insert(" ")


class TimeBaseRule:
    """
    Base class for English time rules
    Provides building blocks for time expressions like:
    - twelve thirty -> hours: "12" minutes: "30"
    - quarter past two -> hours: "2" minutes: "15"
    - three o clock -> hours: "3" minutes: "00"
    """

    def __init__(self, input_case: str = INPUT_LOWER_CASED):
        self.input_case = input_case

        # 获取全局SymbolTable
        self.sym = get_symbol_table()

        # AM/PM suffix
        suffix_graph = word_string_file(get_abs_path("../../data/time/time_suffix.tsv"))
        if input_case == INPUT_CASED:
            suffix_graph |= word_string_file(get_abs_path("../../data/time/time_suffix_cased.tsv"))
        self.suffix = suffix_graph

        # Time zones
        time_zone_graph = invert(word_string_file(get_abs_path("../../data/time/time_zone.tsv")))
        if input_case == INPUT_CASED:
            time_zone_graph |= invert(
                word_string_file(get_abs_path("../../data/time/time_zone_cased.tsv"))
            )
        self.time_zone = time_zone_graph

        # Special time words
        self.to_hour = word_string_file(get_abs_path("../../data/time/to_hour.tsv"))
        self.minute_to = word_string_file(get_abs_path("../../data/time/minute_to.tsv"))

        # Time words (ten, twenty, thirty, etc.)
        self.time_words = word_string_file(get_abs_path("../../data/time/time_words.tsv"))

        # 创建词级delete_space和delete_extra_space FST（需要在cardinal之前创建）
        self.delete_space_fst = word_delete_space()
        self.delete_extra_space_fst = word_delete_extra_space()

        # Cardinal numbers (only for small numbers, with weight)
        # 临时方案：使用词级string_file构建简化的数字转换器，绕过字符级CardinalFst
        # TODO: 完整转换CardinalFst为词级FST
        # 已在文件开头导入词级pynutil
        # from pynini.lib import pynutil
        graph_digit = word_string_file(get_abs_path("../../data/numbers/digit.tsv"))
        graph_ties = word_string_file(get_abs_path("../../data/numbers/ties.tsv"))
        graph_teen = word_string_file(get_abs_path("../../data/numbers/teen.tsv"))
        graph_zero = word_string_file(get_abs_path("../../data/numbers/zero.tsv"))

        # 简化的cardinal：支持0-99的数字转换
        # 单个数字：digit (1-9)
        single_digit = graph_digit

        # 10-19：teen
        teen_numbers = graph_teen

        # 20-99：ties + optional digit
        ties_numbers = graph_ties + self.delete_space_fst.ques + (graph_digit | pynutil.insert("0"))

        # 组合：0-99
        simple_cardinal = graph_zero | single_digit | teen_numbers | ties_numbers
        cardinal = pynutil.add_weight(simple_cardinal, weight=-0.7)
        self.cardinal = cardinal  # Save for use in build_time_rules

        # Load numeric hour and minute data using data-driven approach (like Chinese FST)
        # Use the new digit TSV files for better time format recognition
        self.hour_digit = word_string_file(get_abs_path("../../data/time/digit/hour_digit.tsv"))
        self.minute_digit = word_string_file(get_abs_path("../../data/time/digit/minute_digit.tsv"))
        ordinal_digit = word_string_file(get_abs_path("../../data/time/digit/ordinal_digit.tsv"))

        # Add arabic digit support for better number matching (like Chinese FST)
        # 词级FST：数字是完整token，不能使用.plus匹配多位数
        # 对于时间组件，使用string_map创建精确匹配（0-59分钟，0-23小时）
        # For minutes: 0-59 (1-2 digits) - use string_map for explicit priority
        arabic_minute = string_map([(str(i), str(i)) for i in range(60)])
        # For hours: 0-23 (1-2 digits) - use string_map for explicit priority
        arabic_hour = string_map([(str(i), str(i)) for i in range(24)])

        # 通用数字支持（如果需要）：创建0-999的数字token union
        # 注意：当前代码中未使用arabic_number，如果将来需要可以取消注释
        # arabic_number_tokens = [accep(str(i)) for i in range(1000)]  # 0-999
        # arabic_number = union(*arabic_number_tokens)

        # Keep existing files for backward compatibility
        hour_simple = word_string_file(get_abs_path("../../data/numbers/hour_simple.tsv"))
        hour_padded = word_string_file(get_abs_path("../../data/numbers/hour_24.tsv"))
        minute_simple = word_string_file(get_abs_path("../../data/numbers/minute_simple.tsv"))
        minute_padded = word_string_file(get_abs_path("../../data/numbers/minute_numeric.tsv"))

        # Combine data-driven and existing approaches (add constrained arabic_number support like Chinese FST)
        self.hour_numeric = self.hour_digit | hour_simple | hour_padded | arabic_hour
        self.minute_numeric = self.minute_digit | minute_simple | minute_padded | arabic_minute
        self.ordinal_numeric = ordinal_digit

        # Build hour and minute graphs (word form)
        labels_hour = [num_to_word(x) for x in range(0, 24)]
        labels_minute_single = [num_to_word(x) for x in range(1, 10)]
        labels_minute_double = [num_to_word(x) for x in range(10, 60)]

        hour_words = union(*labels_hour) @ cardinal
        minute_single_words = union(*labels_minute_single) @ cardinal
        minute_double_words = union(*labels_minute_double) @ cardinal

        # Combine numeric and word forms for hours and minutes
        self.hour = self.hour_numeric | hour_words
        self.minute_single = minute_single_words  # Keep for specific patterns
        self.minute_double = self.minute_numeric | minute_double_words

        if input_case == INPUT_CASED:
            self.hour = self._capitalize_graph(self.hour)
            self.minute_double = self._capitalize_graph(self.minute_double)

        # Special minute words
        self.minute_verbose = cross("half", "30") | cross("quarter", "15")
        if input_case == INPUT_CASED:
            self.minute_verbose |= cross("Half", "30") | cross("Quarter", "15")

        # O'clock variations
        self.oclock = cross(union("o' clock", "o clock", "o'clock", "oclock", "hundred hours"), "")
        if input_case == INPUT_CASED:
            self.oclock |= cross(
                union("O' clock", "O clock", "O'clock", "Oclock", "Hundred hours"), ""
            )

        # Delete words (delete_space_fst已在上面创建)
        self.delete_past = pynutil.delete(union("past", "after"))
        self.delete_to = pynutil.delete(union("to", "till"))
        self.delete_min = closure(
            self.delete_space_fst + pynutil.delete(union("min", "mins", "minute", "minutes")),
            0,
            1,
        )

        if input_case == INPUT_CASED:
            self.delete_past |= pynutil.delete(union("Past", "After"))
            self.delete_to |= pynutil.delete(union("To", "Till"))

    def _capitalize_graph(self, graph):
        """Helper to support capitalized input"""
        if self.input_case == INPUT_CASED:
            # Simple approach: accept both versions
            return graph  # Already handled in cardinal
        return graph

    def build_time_rules(self):
        """
        Build complete time rules
        e.g. "twelve thirty" -> hours: "12" minutes: "30"
        e.g. "quarter past two" -> minutes: "15" hours: "2"
        e.g. "three o clock" -> hours: "3" minutes: "00"
        """

        hour_tag = pynutil.insert('hour:"') + self.hour + pynutil.insert('"')

        # Minute graph with special handling for leading zero
        minute_graph = (
            self.oclock + pynutil.insert("00")
            | pynutil.delete("o") + self.delete_space_fst + self.minute_single
            | self.minute_double
        )
        minute_tag = pynutil.insert('minute:"') + minute_graph + pynutil.insert('"')

        # Suffix (AM/PM) optional
        suffix_tag = pynutil.insert('period:"') + self.suffix + pynutil.insert('"')
        optional_suffix = closure(self.delete_space_fst + insert_space + suffix_tag, 0, 1)

        # Time zone optional
        zone_tag = pynutil.insert('zone:"') + self.time_zone + pynutil.insert('"')
        optional_zone = closure(self.delete_space_fst + insert_space + zone_tag, 0, 1)

        # Digit-only time with colon separator (e.g., "8:30", "08:30")
        # Use hour_digit and require 2-digit minutes to avoid "17:2" patterns
        digit_hour_tag = pynutil.insert('hour:"') + self.hour_digit + pynutil.insert('"')

        # Create minute pattern (00-59) for digit-only time format
        # 词级FST：使用word_accep确保符号表正确
        # 重要：分钟部分必须使用前导零格式（"00"-"59"），不允许单个数字（"0"-"9"）
        # 例如："5:01" ✓ 可以识别，"5:1" ✗ 不能识别

        # 只支持前导零格式：
        # - "00"-"09" (前导零格式)
        # - "10"-"59" (两位数格式)
        minute_digits = union(
            *[word_accep(f"{i:02d}") for i in range(60)]  # 00-59 (必须使用前导零格式)
        )
        digit_minute_tag = pynutil.insert('minute:"') + minute_digits + pynutil.insert('"')

        # 词级FST：删除单独的冒号token（':'已作为token存在于GlobalSymbolTable中）
        from ...word_level_pynini import accep

        colon_token = accep(":")
        colon_fullwidth = accep("：")
        colon_delete = pynutil.delete(colon_token) | pynutil.delete(colon_fullwidth)

        # Optional "at" prefix for time expressions (e.g., "at 12:30")
        optional_at = closure(pynutil.delete("at") + self.delete_space_fst, 0, 1)

        # "8:30" or "8:30 am" or "at 8:30" format
        graph_digit_hm = (
            optional_at  # Support "at 12:30" format
            + digit_hour_tag
            + colon_delete
            + digit_minute_tag
            + optional_suffix
            + optional_zone
        )

        # "8:30:45" or "8:30:45 am" or "at 8:30:45" format (with seconds)
        digit_second_tag = pynutil.insert('second:"') + self.minute_numeric + pynutil.insert('"')
        graph_digit_hms = (
            optional_at  # Support "at 12:30:45" format
            + digit_hour_tag
            + colon_delete
            + digit_minute_tag
            + colon_delete
            + digit_second_tag
            + optional_suffix
            + optional_zone
        )

        # "8 am" format (digit hour with required AM/PM, auto-add :00 for minutes)
        graph_digit_h_suffix = (
            digit_hour_tag
            + pynutil.insert(' minute:"00"')
            + self.delete_space_fst
            + insert_space
            + suffix_tag
            + optional_zone
        )

        # "at 4 pm" format (with optional "at" prefix and separate pm/am)
        # This handles cases where pm/am is not merged by other rules
        graph_at_digit_h_pm = (
            optional_at  # Support "at 4 pm" format
            + digit_hour_tag
            + pynutil.insert(' minute:"00"')
            + self.delete_space_fst
            + insert_space
            + suffix_tag
        )

        # Compact am/pm format: "7a", "7p", "3:18a", "3:15p"

        # Compact am/pm with minutes: "3:18a", "3:15p"

        # European time format: "9h30", "14h45"
        european_hm = (
            pynutil.insert('hour:"')
            + self.hour_numeric
            + pynutil.insert('"')
            + pynutil.delete("h")
            + pynutil.insert(' minute:"')
            + self.minute_numeric
            + pynutil.insert('"')
        )

        # Word time format: "ten thirty", "twelve zero three", "twelve oh three"
        word_hour_tag = pynutil.insert('hour:"') + self.time_words + pynutil.insert('"')
        word_minute_tag = pynutil.insert('minute:"') + self.time_words + pynutil.insert('"')

        # Generic handling for "zero/oh/o + digit" combinations
        zero_oh = union("zero", "oh", "o")
        digit_words = union("one", "two", "three", "four", "five", "six", "seven", "eight", "nine")

        # Generic digit to number mapping
        digit_to_number = union(
            cross("one", "1"),
            cross("two", "2"),
            cross("three", "3"),
            cross("four", "4"),
            cross("five", "5"),
            cross("six", "6"),
            cross("seven", "7"),
            cross("eight", "8"),
            cross("nine", "9"),
        )

        # Generic pattern: zero/oh/o + space + digit -> 0 + digit_number
        zero_digit_mappings = cross(
            zero_oh + self.delete_space_fst + digit_words,
            pynutil.insert("0") + digit_to_number,
        )

        # Generic pattern: zero/oh/o + hyphen + digit -> 0 + digit_number
        zero_digit_mappings_hyphen = cross(
            zero_oh + pynutil.delete("-") + digit_words,
            pynutil.insert("0") + digit_to_number,
        )

        zero_digit_combinations = (
            pynutil.insert('minute:"') + zero_digit_mappings + pynutil.insert('"')
        )

        # "ten thirty" format - REQUIRE context to avoid over-matching
        # Following Chinese FST strategy: require "at" prefix or AM/PM suffix
        graph_word_hm_with_at = (
            optional_at + word_hour_tag + self.delete_extra_space_fst + word_minute_tag + suffix_tag
        )

        # "ten-thirty" format (with hyphen) - also require context
        graph_word_hm_hyphen = (
            optional_at + word_hour_tag + pynutil.delete("-") + word_minute_tag + suffix_tag
        )

        # "twelve zero three" format (hour + zero + digit)
        graph_word_h_zero_digit = (
            word_hour_tag + self.delete_extra_space_fst + zero_digit_combinations
        )

        # "twelve-oh-three" format (hour + zero + digit with hyphen)
        zero_digit_combinations_hyphen = (
            pynutil.insert('minute:"') + zero_digit_mappings_hyphen + pynutil.insert('"')
        )
        graph_word_h_zero_digit_hyphen = (
            word_hour_tag + pynutil.delete("-") + zero_digit_combinations_hyphen
        )

        # "ten" format (hour only, default minute to 00)

        # Format 1: hour minute [suffix] [zone]
        # "two thirty" "two o eight" "two thirty five am"
        graph_hm = hour_tag + self.delete_extra_space_fst + minute_tag

        # Format 2: minute past hour
        # "ten past four" "quarter past four" "half past four" "6 minutes past 10"
        # IMPORTANT: For "twenty after 3pm", use time_words directly to ensure single token output ("20" not "2 0")
        # time_words already contains mappings like "twenty" -> "20" as single tokens
        minute_past_words = (
            self.time_words
        )  # Direct mapping from time_words.tsv (e.g., "twenty" -> "20")
        minute_past = union(
            self.minute_single,  # "one", "two", etc. via cardinal
            minute_past_words,  # "ten", "twenty", etc. via time_words.tsv (ensures single token output)
            self.minute_verbose,  # "half" -> "30", "quarter" -> "15"
        )

        # Add numeric minute support for past/to patterns
        minute_numeric_past = union(
            self.minute_numeric,  # "20", "15", etc.
            minute_past,  # "ten", "twenty", etc. (now uses time_words for single token output)
        )

        # Support both regular hours and period keywords (noon, midnight)
        # Use pynutil.insert to ensure correct format: period:"noon"
        noon_period = pynutil.insert('period:"') + accep("noon") + pynutil.insert('"')
        midnight_period = pynutil.insert('period:"') + accep("midnight") + pynutil.insert('"')
        hour_or_period = hour_tag | noon_period | midnight_period

        graph_m_past_h = (
            optional_at  # Support "at 15 past noon" format
            + pynutil.insert('minute:"')
            + minute_numeric_past
            + pynutil.insert('"')
            + self.delete_min
            + self.delete_space_fst
            + self.delete_past
            + self.delete_extra_space_fst
            + hour_or_period
        )

        # Format 3: quarter to hour (special case)
        # "quarter to two" -> minutes: "45" hours: "1" (previous hour)
        # "quarter minutes to two" -> minutes: "45" hours: "1"
        quarter_graph = accep("quarter")
        if self.input_case == INPUT_CASED:
            quarter_graph |= accep("Quarter")

        graph_quarter_to = (
            pynutil.insert('minute:"')
            + cross(quarter_graph, "45")
            + pynutil.insert('"')
            + self.delete_min
            + self.delete_space_fst
            + self.delete_to
            + self.delete_extra_space_fst
            + pynutil.insert('hour:"')
            + self.to_hour
            + pynutil.insert('"')
        )

        # Format 4: minute to hour [suffix]
        # "five to three pm" -> minutes: "55" hours: "2" (previous hour) period: "pm"
        # IMPORTANT: Only use WORD forms (not numeric) to avoid conflicts with "40 to 1" in "14:40 to 15:10"
        # Recreate word-only minute forms (since self.minute_double includes numeric)
        labels_minute_single = [num_to_word(x) for x in range(1, 10)]
        labels_minute_double = [num_to_word(x) for x in range(10, 60)]
        minute_single_words = union(*labels_minute_single) @ self.cardinal
        minute_double_words = union(*labels_minute_double) @ self.cardinal
        minute_words_only = minute_single_words | minute_double_words

        # Add numeric minute support for "to" patterns
        minute_numeric_to = union(
            self.minute_numeric,  # "20", "15", etc.
            minute_words_only @ self.minute_to,  # "ten", "twenty", etc.
        )

        graph_m_to_h = (
            pynutil.insert('minute:"')
            + minute_numeric_to
            + pynutil.insert('"')
            + self.delete_min
            + self.delete_space_fst
            + self.delete_to
            + self.delete_extra_space_fst
            + pynutil.insert('hour:"')
            + self.to_hour
            + pynutil.insert('"')
        )

        # Format 5: hour [o'clock] [suffix] [zone]
        # "three o clock" "two pm" "five am pst"
        # Special handling for o'clock with word hours
        oclock_with_space = self.delete_space_fst + self.oclock + pynutil.insert("00")
        graph_h = (
            hour_tag
            + self.delete_extra_space_fst
            + pynutil.insert('minute:"')
            + (pynutil.insert("00") | oclock_with_space | minute_graph)
            + pynutil.insert('"')
            + self.delete_space_fst
            + insert_space
            + suffix_tag
            + optional_zone
        )

        # Combine all formats with weights (lower weight = higher priority)
        # 使用词级add_weight（pynutil已在文件顶部从word_level_pynini导入）
        graph = union(
            pynutil.add_weight(
                graph_digit_hms, 0.005
            ),  # "8:30:45 am" - HIGHEST priority for HH:MM:SS format
            pynutil.add_weight(
                graph_m_past_h + optional_suffix + optional_zone, 0.008
            ),  # "ten past four", "at 15 past noon" - VERY HIGH priority for past
            pynutil.add_weight(
                graph_quarter_to + optional_suffix + optional_zone, 0.009
            ),  # "quarter to two" - VERY HIGH priority for to
            pynutil.add_weight(
                graph_digit_hm, 0.01
            ),  # "8:30 am" - HIGH priority to prevent "40 to 1" mismatches
            pynutil.add_weight(
                graph_m_to_h + optional_suffix + optional_zone, 0.012
            ),  # "five to three" (word form only) - HIGH priority for to
            pynutil.add_weight(
                graph_at_digit_h_pm, 0.02
            ),  # "at 4 pm" - HIGH priority for at + hour + pm/am
            # Compact am/pm formats removed - too easy to mismatch (e.g., "4a" could be seat number)
            # pynutil.add_weight(compact_am, 0.03),  # "7a" - compact am format
            # pynutil.add_weight(compact_pm, 0.03),  # "7p" - compact pm format
            # pynutil.add_weight(compact_hm_am, 0.04),  # "3:18a" - compact am with minutes
            # pynutil.add_weight(compact_hm_pm, 0.04),  # "3:15p" - compact pm with minutes
            pynutil.add_weight(european_hm, 0.045),  # "9h30" - European time format
            pynutil.add_weight(
                graph_word_hm_with_at, 0.05
            ),  # "at ten thirty pm" - word time format with context (higher priority)
            pynutil.add_weight(
                graph_word_hm_hyphen, 0.05
            ),  # "at ten-thirty pm" - word time with hyphen and context (higher priority)
            pynutil.add_weight(
                graph_word_h_zero_digit, 0.05
            ),  # "twelve zero three" - hour + zero + digit (higher priority)
            pynutil.add_weight(
                graph_word_h_zero_digit_hyphen, 0.05
            ),  # "twelve-oh-three" - hour + zero + digit with hyphen (higher priority)
            # Removed graph_word_h to avoid over-matching single number words like "three"
            pynutil.add_weight(graph_digit_h_suffix, 0.6),  # "8 am" - digit hour with AM/PM
            # Following Chinese FST strategy: require AM/PM suffix for space-separated numbers
            # "two thirty pm" -> OK, "3 30" -> NOT matched (too ambiguous)
            pynutil.add_weight(
                graph_hm + suffix_tag + optional_zone, 1.0
            ),  # "two thirty pm" - REQUIRE AM/PM
            pynutil.add_weight(graph_h, 1.5),  # "three pm"
        )

        # Dot-separated time patterns: H.M and H.M.S
        # Following Chinese FST strategy: use strict validation and require context
        # e.g. "at 6.50" -> hour: "6" minute: "50" (has "at" prefix)
        # e.g. "6.50 pm" -> hour: "6" minute: "50" (has AM/PM suffix)
        # e.g. "650.650" -> NOT matched (no context, numbers out of range)
        dot_delete = pynutil.delete(".")

        # Use validated hour/minute patterns (0-23 for hour, 0-59 for minute)
        # This prevents matching invalid times like "650.650"
        validated_hour_tag = pynutil.insert('hour:"') + self.hour_numeric + pynutil.insert('"')
        validated_minute_tag = (
            pynutil.insert('minute:"') + self.minute_numeric + pynutil.insert('"')
        )

        # Require "at" prefix for dot-separated times (following Chinese FST's context requirement)
        at_required = pynutil.delete("at") + self.delete_space_fst

        # H.M format: "at 6.50" -> hour: "6" minute: "50"
        graph_dot_hm = (
            at_required  # REQUIRE "at" prefix
            + validated_hour_tag
            + dot_delete
            + validated_minute_tag
            + optional_suffix
            + optional_zone
        )

        # H.M.S format: "at 6.50.30" -> hour: "6" minute: "50" second: "30"
        # For seconds, reuse minute_numeric (0-59 range)
        validated_second_tag = (
            pynutil.insert('second:"') + self.minute_numeric + pynutil.insert('"')
        )
        graph_dot_hms = (
            at_required  # REQUIRE "at" prefix
            + validated_hour_tag
            + dot_delete
            + validated_minute_tag
            + dot_delete
            + validated_second_tag
            + optional_suffix
            + optional_zone
        )

        # Add dot-separated patterns to the main graph with higher priority
        # 使用词级add_weight（pynutil已在文件顶部从word_level_pynini导入）
        graph = (
            graph | pynutil.add_weight(graph_dot_hm, 0.1) | pynutil.add_weight(graph_dot_hms, 0.1)
        )

        # Add optional trailing space deletion to match CharRule's behavior
        # This ensures time expressions can compete with CharRule in FST star repetition
        optional_trailing_space = pynutil.delete(" ").ques
        graph = graph + optional_trailing_space

        # 词级FST：确保符号表被设置（optimize可能丢失符号表）
        from ...global_symbol_table import get_symbol_table

        sym = get_symbol_table()
        graph.set_input_symbols(sym)
        graph.set_output_symbols(sym)

        return graph

    def build_time_cnt_rules(self):
        """
        Build time duration rules
        e.g. "two hours" -> hour: "2"
        e.g. "thirty minutes" -> minute: "30"
        e.g. "two hours thirty minutes" -> hour: "2" minute: "30"
        """
        # Expand number range to support 0-999 (for cases like "60 minutes", "90 minutes", "120 minutes")
        large_number = union(
            # 0-9: single digit
            union(*[accep(str(i)) for i in range(10)]),
            # 10-99: double digit
            union(*[accep(str(i)) for i in range(10, 100)]),
            # 100-999: triple digit
            union(*[accep(str(i)) for i in range(100, 1000)]),
        ).optimize()

        # Add decimal number support (e.g., "2.5", "1.5", "3.25", "0.5")
        # 词级FST：小数格式可能是"2" + "." + "5"三个token，或者"2.5"一个token
        # 创建常见的小数模式：整数部分（0-999）+ 小数点 + 小数部分（1-2位）
        # 整数部分：使用large_number（0-999）
        # 小数点：'.'作为token
        # 小数部分：创建0-99的union（支持"0.5", "0.05", "0.25"等）
        decimal_fraction_tokens = [
            accep(str(i).zfill(2) if i < 10 else str(i)) for i in range(100)
        ]  # 00-99 (包括"00", "05", "25")
        # 同时支持1位和2位小数部分（"5"和"05"）
        decimal_fraction_single = union(*[accep(str(i)) for i in range(10)])  # 0-9
        decimal_fraction = union(*decimal_fraction_tokens) | decimal_fraction_single

        # 匹配小数格式：整数 + '.' + 小数部分
        # 例如："2" + "." + "5" 或 "2.5"（如果分词器将其作为一个token）
        decimal_number = large_number + accep(".") + decimal_fraction

        # Combined number: integer or decimal
        number_with_decimal = large_number | decimal_number

        hour_tag = (
            pynutil.insert('hour:"') + (self.hour | number_with_decimal) + pynutil.insert('"')
        )
        minute_tag = (
            pynutil.insert('minute:"')
            + (self.minute_single | self.minute_double | number_with_decimal)
            + pynutil.insert('"')
        )
        second_tag = (
            pynutil.insert('second:"')
            + (self.minute_single | self.minute_double | number_with_decimal)
            + pynutil.insert('"')
        )

        # Year, month, week, and day tags (using hour as generic number rule)
        year_tag = (
            pynutil.insert('year:"') + (self.hour | number_with_decimal) + pynutil.insert('"')
        )
        month_tag = (
            pynutil.insert('month:"') + (self.hour | number_with_decimal) + pynutil.insert('"')
        )
        week_tag = (
            pynutil.insert('week:"') + (self.hour | number_with_decimal) + pynutil.insert('"')
        )
        day_tag = pynutil.insert('day:"') + (self.hour | number_with_decimal) + pynutil.insert('"')

        # Delete duration words (including abbreviations)
        delete_hour = pynutil.delete(union("hour", "hours", "hr", "hrs"))
        delete_minute = pynutil.delete(union("minute", "minutes", "min", "mins"))
        delete_second = pynutil.delete(union("second", "seconds", "sec", "secs"))
        delete_year = pynutil.delete(union("year", "years"))
        delete_month = pynutil.delete(union("month", "months"))
        delete_week = pynutil.delete(union("week", "weeks"))
        delete_day = pynutil.delete(union("day", "days"))

        if self.input_case == INPUT_CASED:
            delete_hour |= pynutil.delete(union("Hour", "Hours", "Hr", "Hrs"))
            delete_minute |= pynutil.delete(union("Minute", "Minutes", "Min", "Mins"))
            delete_second |= pynutil.delete(union("Second", "Seconds", "Sec", "Secs"))
            delete_year |= pynutil.delete(union("Year", "Years"))
            delete_month |= pynutil.delete(union("Month", "Months"))
            delete_week |= pynutil.delete(union("Week", "Weeks"))
            delete_day |= pynutil.delete(union("Day", "Days"))

        # Optional "more" modifier
        optional_more = (self.delete_space_fst + pynutil.delete("more")).ques

        # Build duration components (with optional "more" support)
        hour_cnt = (
            hour_tag + self.delete_space_fst + optional_more + self.delete_space_fst + delete_hour
        )
        minute_cnt = (
            minute_tag
            + self.delete_space_fst
            + optional_more
            + self.delete_space_fst
            + delete_minute
        )
        second_cnt = (
            second_tag
            + self.delete_space_fst
            + optional_more
            + self.delete_space_fst
            + delete_second
        )
        year_cnt = (
            year_tag + self.delete_space_fst + optional_more + self.delete_space_fst + delete_year
        )
        month_cnt = (
            month_tag + self.delete_space_fst + optional_more + self.delete_space_fst + delete_month
        )
        week_cnt = (
            week_tag + self.delete_space_fst + optional_more + self.delete_space_fst + delete_week
        )
        day_cnt = (
            day_tag + self.delete_space_fst + optional_more + self.delete_space_fst + delete_day
        )

        # "half an hour" -> 30 minutes
        # 注意：需要手动处理空格，因为word_delete不处理多词短语中的空格
        half_hour = pynutil.insert('minute:"30"') + (
            (
                pynutil.delete("half")
                + self.delete_space_fst.ques
                + pynutil.delete("an")
                + self.delete_space_fst.ques
                + pynutil.delete("hour")
            )
            | (pynutil.delete("half") + self.delete_space_fst.ques + pynutil.delete("hour"))
        )
        if self.input_case == INPUT_CASED:
            half_hour |= pynutil.insert('minute:"30"') + (
                (
                    pynutil.delete("Half")
                    + self.delete_space_fst.ques
                    + pynutil.delete("an")
                    + self.delete_space_fst.ques
                    + pynutil.delete("hour")
                )
                | (pynutil.delete("Half") + self.delete_space_fst.ques + pynutil.delete("hour"))
            )

        # Combinations
        hour_minute_cnt = hour_cnt + self.delete_extra_space_fst + minute_cnt
        hour_second_cnt = hour_cnt + self.delete_extra_space_fst + second_cnt
        minute_second_cnt = minute_cnt + self.delete_extra_space_fst + second_cnt
        hour_minute_second_cnt = (
            hour_cnt
            + self.delete_extra_space_fst
            + minute_cnt
            + self.delete_extra_space_fst
            + second_cnt
        )

        # Year, month, week, and day combinations
        year_month_cnt = year_cnt + self.delete_extra_space_fst + month_cnt
        year_hour_cnt = year_cnt + self.delete_extra_space_fst + hour_cnt
        year_minute_cnt = year_cnt + self.delete_extra_space_fst + minute_cnt
        year_week_cnt = year_cnt + self.delete_extra_space_fst + week_cnt
        year_day_cnt = year_cnt + self.delete_extra_space_fst + day_cnt
        month_hour_cnt = month_cnt + self.delete_extra_space_fst + hour_cnt
        month_minute_cnt = month_cnt + self.delete_extra_space_fst + minute_cnt
        month_week_cnt = month_cnt + self.delete_extra_space_fst + week_cnt
        month_day_cnt = month_cnt + self.delete_extra_space_fst + day_cnt
        week_hour_cnt = week_cnt + self.delete_extra_space_fst + hour_cnt
        week_minute_cnt = week_cnt + self.delete_extra_space_fst + minute_cnt
        week_day_cnt = week_cnt + self.delete_extra_space_fst + day_cnt
        day_hour_cnt = day_cnt + self.delete_extra_space_fst + hour_cnt
        day_minute_cnt = day_cnt + self.delete_extra_space_fst + minute_cnt

        graph = (
            hour_cnt
            | minute_cnt
            | second_cnt
            | year_cnt
            | month_cnt
            | week_cnt
            | day_cnt
            | hour_minute_cnt
            | hour_second_cnt
            | minute_second_cnt
            | hour_minute_second_cnt
            | year_month_cnt
            | year_hour_cnt
            | year_minute_cnt
            | year_week_cnt
            | year_day_cnt
            | month_hour_cnt
            | month_minute_cnt
            | month_week_cnt
            | month_day_cnt
            | week_hour_cnt
            | week_minute_cnt
            | week_day_cnt
            | day_hour_cnt
            | day_minute_cnt
            | half_hour
        )

        # 确保返回的FST有符号表
        sym = get_symbol_table()
        if graph.input_symbols() is None or graph.input_symbols() != sym:
            graph.set_input_symbols(sym)
            graph.set_output_symbols(sym)

        return graph
