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

from ...word_level_pynini import (
    string_file,
    accep,
    cross,
    union,
    compose,
    closure,
    optimize,
    string_map,
    Fst,
    Arc,
    Weight,
    SymbolTable,
    get_symbol_table,
    word_string_file,
    word_delete,
)

# 使用词级pynutil
from ...word_level_pynini import pynutil

from ....core.utils import (
    get_abs_path,
    num_to_word,
    INPUT_CASED,
    INPUT_LOWER_CASED,
    NEMO_ALPHA,
    NEMO_DIGIT,
    NEMO_SIGMA,
)

# 词级FST使用词级delete_space和delete_extra_space
from ...word_level_utils import word_delete_space, word_delete_extra_space

delete_space = word_delete_space()  # 词级版本
delete_extra_space = word_delete_extra_space()  # 词级版本


def _get_ordinal_graph(input_case: str = INPUT_LOWER_CASED, sym=None):
    """
    Transducer for ordinal numbers, e.g. first -> 1, second -> 2, twenty third -> 23, 8th -> 8
    """
    # 词级：使用word_string_file
    if sym is not None:
        graph_teen = word_string_file(get_abs_path("../../data/numbers/teen.tsv"))
        graph_digit = word_string_file(get_abs_path("../../data/numbers/digit.tsv"))
        ties_graph = word_string_file(get_abs_path("../../data/numbers/ties.tsv"))
        ordinal_exceptions = word_string_file(
            get_abs_path("../../data/numbers/ordinal_exceptions.tsv")
        )
    else:
        # 字符级：需要导入原始pynini（暂不支持，全部使用词级）
        raise NotImplementedError("字符级ordinal_graph已废弃，请使用词级FST")

    # Ordinal suffixes（词级）

    # Regular ordinals: digit + "th", e.g. "fourth" -> "4"
    ties = ties_graph + delete_space + (graph_digit | pynutil.insert("0"))
    graph = (graph_teen | ties) @ (closure(NEMO_DIGIT) + pynutil.delete("th"))

    # Numeric ordinals: 1st, 2nd, 3rd, 4th, etc. -> 1, 2, 3, 4, etc.
    # 使用词级accep替代字符级union
    digit = union(*[accep(str(i)) for i in range(10)])  # 0-9
    ordinal_suffix = union(accep("st"), accep("nd"), accep("rd"), accep("th"))
    numeric_ordinal = (
        (digit | (digit + delete_space.ques + digit))
        + delete_space.ques
        + pynutil.delete(ordinal_suffix)
    )

    # Combine word ordinals, regular ordinals, and numeric ordinals
    graph = ordinal_exceptions | graph | numeric_ordinal

    if input_case == INPUT_CASED:
        # Support capitalized input
        ordinal_exceptions_cased = word_string_file(
            get_abs_path("data/numbers/ordinal_exceptions_cased.tsv")
        )
        graph |= ordinal_exceptions_cased

    return graph


def _capitalize_graph(graph, input_case: str):
    """Helper to make graph accept capitalized input (词级版本)"""
    if input_case == INPUT_CASED:
        # 词级FST：由于Normalizer已经处理了大小写转换（转小写），
        # 且SymbolTable中通常包含大写和小写形式的词，
        # 这里简化处理：直接返回graph（因为预处理已转小写）
        # 如果需要支持大写，应该在SymbolTable中添加大写形式的词
        # 或者使用word_string_file加载包含大写形式的TSV文件
        return graph
    return graph


class DateBaseRule:
    """
    Base class for English date rules
    Provides building blocks for date expressions like:
    - january fifth twenty twelve
    - the fifth of january
    - 2025
    """

    def __init__(self, input_case: str = INPUT_LOWER_CASED):
        self.input_case = input_case

        # 获取全局SymbolTable（词级）
        self.sym = get_symbol_table()

        # Month names
        month_graph = word_string_file(get_abs_path("../../data/date/months.tsv"))
        if input_case == INPUT_CASED:
            month_graph |= word_string_file(get_abs_path("../../data/date/months_cased.tsv"))

        # Month abbreviations
        month_abbr = word_string_file(get_abs_path("../../data/date/month_abbr.tsv"))

        self.month = month_graph | month_abbr

        # Ordinal numbers for days (word form: "fifth")
        self.ordinal = _get_ordinal_graph(input_case, self.sym)

        # Ordinal words (first, second, third, etc.)
        ordinal_words = word_string_file(get_abs_path("../../data/date/ordinal_words.tsv"))
        self.ordinal = self.ordinal | ordinal_words

        # Numeric day (digit form: "5", "20")
        self.day_numeric = word_string_file(get_abs_path("../../data/date/day_numeric.tsv"))

        # Ordinal suffix (st, nd, rd, th) - 词级版本
        from ...word_level_pynini import accep, union
        from ...word_level_utils import word_delete_space
        from ...word_level_pynini import pynutil

        delete_space = word_delete_space()
        ordinal_suffix = union(accep("st"), accep("nd"), accep("rd"), accep("th"))

        # Numeric day with ordinal suffix: "20th", "1st", "2nd", "3rd"
        # 处理分词后 "20" + "th" 的情况，输出时删除后缀（只保留数字）
        day_numeric_with_suffix = (
            self.day_numeric + delete_space.ques + pynutil.delete(ordinal_suffix)
        )

        # Combined day: ordinal (word form), numeric only, or numeric with suffix
        self.day = self.ordinal | self.day_numeric | day_numeric_with_suffix

        # Year graph (twenty twenty -> 2020, or numeric 2021 -> 2021)
        self.year = self._build_year_graph()
        self.year_numeric = word_string_file(get_abs_path("../../data/date/year_numeric.tsv"))
        self.year_combined = self.year | self.year_numeric

        # Digit-based numbers
        self.cardinal = self._build_cardinal_graph()

        # Common delete patterns
        self.delete_of = word_delete("of")
        self.delete_the = word_delete("the")
        if input_case == INPUT_CASED:
            self.delete_the |= word_delete("The")

        self.delete_at = word_delete("at")
        if input_case == INPUT_CASED:
            self.delete_at |= word_delete("At")

        self.delete_comma = pynutil.delete(",")
        self.delete_hyphen = pynutil.delete("-") | pynutil.delete("/")

    def _build_cardinal_graph(self):
        """Build basic cardinal number graph for small numbers"""
        labels = [num_to_word(x) for x in range(1, 32)]  # Days 1-31
        if self.input_case == INPUT_CASED:
            labels += [x.capitalize() for x in labels]

        # Create mapping from words to digits
        cardinal_map = {num_to_word(x): str(x) for x in range(1, 32)}
        if self.input_case == INPUT_CASED:
            cardinal_map.update({num_to_word(x).capitalize(): str(x) for x in range(1, 32)})

        # Build FST
        fst = string_map(list(cardinal_map.items()))
        return fst

    def _build_year_graph(self):
        """Build year graph: twenty twenty -> 2020"""
        graph_teen = string_file(get_abs_path("../../data/numbers/teen.tsv"))
        graph_digit = string_file(get_abs_path("../../data/numbers/digit.tsv"))
        ties_graph = string_file(get_abs_path("../../data/numbers/ties.tsv"))

        # Support "oh/o" for zero
        zero = cross(union("oh", "o", "O", "Oh"), "0")
        graph_digits = zero + delete_space + graph_digit

        # Two-digit combinations
        ties = ties_graph + delete_space + (graph_digit | pynutil.insert("0"))

        # Build hundred component
        hundred = pynutil.delete("hundred")
        hundred_component = (graph_digit + delete_space + hundred) | pynutil.insert("0")
        hundred_component += delete_space
        hundred_component += graph_teen | ties | (pynutil.insert("0") + graph_digit)

        # Thousand format: "two thousand twenty" -> "2020"
        thousand = pynutil.delete("thousand")
        thousands_graph = graph_digit + delete_space + thousand + delete_space + hundred_component

        # Year with AD/BC suffix
        year_suffix = string_file(get_abs_path("../../data/year_suffix.tsv")).invert()

        # Combine all year formats
        year_graph = union(
            # 20 19, 40 12 (two parts)
            (graph_teen + delete_space + (ties | graph_digits | graph_teen)),
            (ties + delete_space + (ties | graph_digits | graph_teen)),
            # Full thousands
            thousands_graph,
            # With AD/BC - output both year and suffix
            (
                (graph_digit | graph_teen | ties | thousands_graph)
                + pynutil.insert(' year_suffix:"')
                + year_suffix
                + pynutil.insert('"')
            ),
        )

        if self.input_case == INPUT_CASED:
            year_graph = _capitalize_graph(year_graph, self.input_case)

        return year_graph

    def build_year_rules(self):
        """
        Build year-only rules
        e.g. "twenty twenty" -> year: "2020"
        e.g. "2014 AD" -> year: "2014" year_suffix: "AD"
        """
        # Year with suffix support
        year_suffix = string_file(get_abs_path("../../data/year_suffix.tsv")).invert()

        # Year without suffix
        year_without_suffix = pynutil.insert('year:"') + self.year + pynutil.insert('"')

        # Numeric year without suffix
        numeric_year_without_suffix = (
            pynutil.insert('year:"') + self.year_numeric + pynutil.insert('"')
        )

        # Year with suffix
        year_with_suffix = (
            pynutil.insert('year:"')
            + self.year
            + pynutil.insert('"')
            + delete_space
            + pynutil.insert(' year_suffix:"')
            + year_suffix
            + pynutil.insert('"')
        )

        # Numeric year with suffix
        numeric_year_with_suffix = (
            pynutil.insert('year:"')
            + self.year_numeric
            + pynutil.insert('"')
            + delete_space
            + pynutil.insert(' year_suffix:"')
            + year_suffix
            + pynutil.insert('"')
        )

        return (
            year_without_suffix
            | numeric_year_without_suffix
            | year_with_suffix
            | numeric_year_with_suffix
        )

    def build_month_rules(self):
        """
        Build month rules with proper tagging
        e.g. "january" -> month: "january"
        """
        month_tag = pynutil.insert('month:"') + self.month + pynutil.insert('"')
        return month_tag

    def build_month_year_rules(self):
        """
        Build month + year rules
        e.g. "march 2026" -> month: "march" year: "2026"
        e.g. "january twenty twenty" -> month: "january" year: "2020"
        """
        month_tag = pynutil.insert('month:"') + self.month + pynutil.insert('"')
        year_tag_word = pynutil.insert('year:"') + self.year + pynutil.insert('"')
        year_tag_numeric = pynutil.insert('year:"') + self.year_numeric + pynutil.insert('"')
        year_tag = year_tag_word | year_tag_numeric

        # "march 2026" or "january twenty twenty"
        graph = month_tag + delete_extra_space + year_tag
        return graph

    def build_day_rules(self):
        """
        Build day rules
        e.g. "fifth" -> "5", "twenty third" -> "23"
        """
        return self.ordinal

    def build_month_day_rules(self):
        """
        Build month + day rules
        e.g. "january fifth" -> month: "january" day: "5"
        e.g. "january 20" -> month: "january" day: "20"
        e.g. "january the fifth" -> month: "january" day: "5"
        e.g. "february the 15th" -> month: "february" day: "15"
        e.g. "Aug 8" -> month: "8" day: "8"
        e.g. "14april 2015" -> month: "4" day: "14"
        """
        month_tag = pynutil.insert('month:"') + self.month + pynutil.insert('"')
        day_tag = pynutil.insert('day:"') + self.day + pynutil.insert('"')

        # "january fifth" or "january 20" (with optional space)
        graph_with_space = month_tag + delete_extra_space + day_tag

        # "january the fifth" or "february the 15th" (with optional "the")
        graph_with_the = month_tag + delete_extra_space + self.delete_the + delete_space + day_tag

        # "Aug 8" or "14april" (compact format, space optional)
        graph_compact = month_tag + delete_space.ques + day_tag

        return graph_with_space | graph_with_the | graph_compact

    def build_day_month_rules(self):
        """
        Build day + month rules (British format)
        e.g. "the fifth of january" -> day: "5" month: "january"
        e.g. "the 20 of january" -> day: "20" month: "january"
        e.g. "15 of february" -> day: "15" month: "february"
        e.g. "first of march" -> day: "1" month: "march"
        """
        day_tag = pynutil.insert('day:"') + self.day + pynutil.insert('"')
        month_tag = pynutil.insert('month:"') + self.month + pynutil.insert('"')

        # "the fifth of january" or "the 20 of january"
        graph_with_the = (
            self.delete_the
            + delete_space
            + day_tag
            + delete_space
            + self.delete_of
            + delete_extra_space
            + month_tag
        )

        # "15 of february" or "first of march" (without "the")
        graph_without_the = day_tag + delete_space + self.delete_of + delete_extra_space + month_tag

        # Special dates: "the ides of march" -> day: "15" month: "march"
        special_dates = string_file(get_abs_path("../../data/date/special_dates.tsv"))
        special_day_tag = pynutil.insert('day:"') + special_dates + pynutil.insert('"')
        graph_special = (
            self.delete_the
            + delete_space
            + special_day_tag
            + delete_space
            + self.delete_of
            + delete_extra_space
            + month_tag
        )

        return graph_with_the | graph_without_the | graph_special

    def build_date_rules(self):
        """
        Build complete date rules
        e.g. "january fifth twenty twelve" -> month: "january" day: "5" year: "2012"
        e.g. "january 20 2021" -> month: "january" day: "20" year: "2021"
        e.g. "the fifth of january twenty twelve" -> day: "5" month: "january" year: "2012"
        """
        month_tag = pynutil.insert('month:"') + self.month + pynutil.insert('"')
        day_tag = pynutil.insert('day:"') + self.day + pynutil.insert('"')

        # Year tag (support both word and numeric forms)
        year_tag_word = pynutil.insert('year:"') + self.year + pynutil.insert('"')
        year_tag_numeric = pynutil.insert('year:"') + self.year_numeric + pynutil.insert('"')
        year_tag = year_tag_word | year_tag_numeric

        # Optional year
        optional_year = closure(delete_extra_space + year_tag, 0, 1)

        # Format 1: month day [year] - "january fifth 2025" or "january 20 2021"
        graph_mdy = month_tag + delete_extra_space + day_tag + optional_year

        # Format 2: the day of month [year] - "the fifth of january 2025"
        graph_dmy = (
            self.delete_the
            + delete_space
            + day_tag
            + delete_space
            + self.delete_of
            + delete_extra_space
            + month_tag
            + optional_year
        )

        # Combine both formats
        graph = graph_mdy | graph_dmy
        return graph

    def build_numeric_date_rules(self):
        """
        Build numeric date rules
        e.g. "2021-09-21" -> year: "2021" month: "9" day: "21"
        e.g. "2021/09/21" -> year: "2021" month: "9" day: "21"
        e.g. "09-21-2021" -> month: "9" day: "21" year: "2021"
        e.g. "09/21/2021" -> month: "9" day: "21" year: "2021"
        """
        # 使用词级union（已在文件顶部导入）
        # Year: 4 digits (1900-2099) and 2 digits (00-99)
        year_4digit = self.year_numeric
        year_2digit = union(*[accep(str(i).zfill(2)) for i in range(100)])

        # Month: 01-12 or 1-12
        month_numeric = string_file(get_abs_path("../../data/date/month_numeric.tsv"))

        # Day: 01-31 or 1-31
        day_numeric = self.day_numeric

        # Separators (support spaces around separators and dots) - 词级版本
        from ...word_level_pynini import word_delete_space

        delete_space = word_delete_space()
        separator = (
            (delete_space + word_delete("-") + delete_space)
            | (delete_space + word_delete("/") + delete_space)
            | (delete_space + word_delete(".") + delete_space)
            | word_delete("-")
            | word_delete("/")
            | word_delete(".")
        )

        # Year tags
        year_tag = pynutil.insert('year:"') + year_4digit + pynutil.insert('"')
        year_2digit_tag = pynutil.insert('year:"') + year_2digit + pynutil.insert('"')

        # Month tag (numeric)
        month_tag = pynutil.insert('month:"') + month_numeric + pynutil.insert('"')

        # Day tag (numeric)
        day_tag = pynutil.insert('day:"') + day_numeric + pynutil.insert('"')

        # Format: YYYY-MM-DD or YYYY/MM/DD
        graph_ymd = year_tag + separator + month_tag + separator + day_tag

        # Format: MM-DD-YYYY or MM/DD/YYYY
        graph_mdy = month_tag + separator + day_tag + separator + year_tag

        # Format: DD-MM-YYYY or DD/MM/YYYY
        graph_dmy = day_tag + separator + month_tag + separator + year_tag

        # Format: MM-DD or MM/DD (simple month-day without year)
        # Exclude decimal numbers like "2.5" by ensuring the pattern doesn't match decimals
        # Only match when the separator is NOT a dot (.) to avoid matching decimals
        # 词级版本
        non_dot_separator = (
            (delete_space + word_delete("-") + delete_space)
            | (delete_space + word_delete("/") + delete_space)
            | word_delete("-")
            | word_delete("/")
        )
        graph_md = month_tag + non_dot_separator + day_tag

        # Format: YYYY-MM or YYYY/MM (year-month)
        graph_ym = year_tag + separator + month_tag

        # Format: M/YYYY or M-YYYY (month-year)
        graph_my = month_tag + separator + year_tag

        # Format: MM/DD/YY or MM-DD-YY (2-digit year)
        graph_mdy_2y = month_tag + separator + day_tag + separator + year_2digit_tag

        # Format: DD/MM/YY or DD-MM-YY (2-digit year)
        graph_dmy_2y = day_tag + separator + month_tag + separator + year_2digit_tag

        # Format: DD/Month/YYYY or DD-Month-YYYY (mixed format)
        # e.g. "31/Oct/1974" -> day: "31" month: "10" year: "1974"
        mixed_day_tag = pynutil.insert('day:"') + day_numeric + pynutil.insert('"')
        mixed_month_tag = pynutil.insert('month:"') + self.month + pynutil.insert('"')
        graph_dmy_mixed = mixed_day_tag + separator + mixed_month_tag + separator + year_tag

        # Format: DD/Month/YY or DD-Month-YY (mixed format with 2-digit year)
        graph_dmy_mixed_2y = (
            mixed_day_tag + separator + mixed_month_tag + separator + year_2digit_tag
        )

        # Combine all formats, prioritize YYYY-MM-DD as it's ISO 8601 standard
        # 使用词级add_weight（pynutil已在文件顶部从word_level_pynini导入）
        graph = union(
            pynutil.add_weight(graph_ymd, 0.1),  # Highest priority for ISO format
            pynutil.add_weight(graph_mdy, 0.2),  # US format (4-digit year)
            pynutil.add_weight(graph_dmy, 0.3),  # European format (4-digit year)
            pynutil.add_weight(graph_ym, 0.4),  # Year-month format
            pynutil.add_weight(graph_my, 0.5),  # Month-year format
            pynutil.add_weight(graph_dmy_mixed, 0.55),  # Mixed format (DD/Month/YYYY)
            pynutil.add_weight(graph_mdy_2y, 0.6),  # US format (2-digit year)
            pynutil.add_weight(graph_dmy_2y, 0.7),  # European format (2-digit year)
            pynutil.add_weight(graph_dmy_mixed_2y, 0.75),  # Mixed format (DD/Month/YY)
            pynutil.add_weight(graph_md, 0.05),  # Simple M/D format (e.g., "2/15") - 最高优先级
        )

        return graph
