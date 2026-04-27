# Copyright (c)  2025  OPPO Corporation.   (authors: Ming Yu, Liangliang Han)
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

"""
Quarter rule for English time expressions.
Handles quarter-related expressions like Q1, Q2, Q3, Q4, 1st quarter, etc.
"""

# 使用词级pynini
from ..word_level_pynini import string_file, string_map, accep, union
from ..word_level_pynini import pynutil
from ...core.processor import Processor
from ...core.utils import get_abs_path
from ..word_level_utils import word_delete_space


class QuarterRule(Processor):
    """Rule for quarter expressions"""

    def __init__(self, input_case: str = "lower_cased"):
        super().__init__("quarter_rule")
        self.input_case = input_case
        self.tagger = self.build_tagger()

    def build_tagger(self):
        """Build the tagger for quarter expressions"""
        delete = pynutil.delete
        insert = pynutil.insert
        delete_space = word_delete_space()

        # Load year data
        year_numeric = string_file(get_abs_path("../data/date/year_numeric.tsv"))

        # Quarter short forms: Q1, Q2, Q3, Q4
        quarter_short = string_map(
            [
                ("Q1", "1"),
                ("Q2", "2"),
                ("Q3", "3"),
                ("Q4", "4"),
                ("q1", "1"),
                ("q2", "2"),
                ("q3", "3"),
                ("q4", "4"),
            ]
        )

        # Quarter words: quarter, qtr
        quarter_word = union(accep("quarter"), accep("qtr"))

        # Ordinal words: first, second, third, fourth
        ordinal_words = string_map(
            [("first", "1"), ("second", "2"), ("third", "3"), ("fourth", "4")]
        )

        # Numeric ordinals: 1st, 2nd, 3rd, 4th
        # 分词后是: "1" + "st", "2" + "nd", "3" + "rd", "4" + "th"
        # 使用string_map将"1"+"st"映射为"1"，"2"+"nd"映射为"2"等
        ordinal_suffix = union(accep("st"), accep("nd"), accep("rd"), accep("th"))
        numeric_ordinal = (
            (delete("1") + delete_space.ques + delete(ordinal_suffix) + insert("1"))
            | (delete("2") + delete_space.ques + delete(ordinal_suffix) + insert("2"))
            | (delete("3") + delete_space.ques + delete(ordinal_suffix) + insert("3"))
            | (delete("4") + delete_space.ques + delete(ordinal_suffix) + insert("4"))
        )

        # Combined ordinal: word form or numeric form
        ordinal = ordinal_words | numeric_ordinal

        # Quarter patterns: ordinal + quarter word
        # e.g., "3rd quarter" -> "3" + "rd" + "quarter" -> quarter: "3"
        # 注意：quarter_word应该被删除，不输出
        ordinal_quarter_pattern = ordinal + delete_space + delete(quarter_word)

        # Combined quarter patterns
        quarter_patterns = quarter_short | ordinal_quarter_pattern

        # Tags
        quarter_tag = insert('quarter:"') + quarter_patterns + insert('"')
        year_tag = insert('year:"') + year_numeric + insert('"')

        # Optional "the" prefix
        optional_the = (delete("the") + delete_space).ques

        # Optional "of" connector
        optional_of = (delete_space + delete("of") + delete_space).ques

        # Pattern 1: Quarter only
        # e.g., "Q1" -> quarter: "1"
        # e.g., "3rd quarter" -> quarter: "3"
        # e.g., "the 3rd quarter" -> quarter: "3"
        pattern1 = optional_the + quarter_tag

        # Pattern 2: Quarter + year
        # e.g., "Q1 2018" -> quarter: "1" year: "2018"
        # e.g., "4th quarter 2018" -> quarter: "4" year: "2018"
        # e.g., "the 4th quarter 2018" -> quarter: "4" year: "2018"
        pattern2a = optional_the + quarter_tag + delete_space + year_tag

        # Pattern 3: Quarter + of + year
        # e.g., "the 4th qtr of 2018" -> quarter: "4" year: "2018"
        pattern2b = optional_the + quarter_tag + optional_of + year_tag

        # Pattern 4: Year + Quarter (2018Q4)
        pattern2c = year_tag + quarter_short

        # Combine all patterns
        tagger = (
            pattern2b  # the 4th qtr of 2018 (highest priority)
            | pattern2a  # Q1 2018, 3rd quarter 2018
            | pattern2c  # 2018Q4
            | pattern1  # Q1, 3rd quarter, the 3rd quarter
        )

        return self.add_tokens(tagger)
