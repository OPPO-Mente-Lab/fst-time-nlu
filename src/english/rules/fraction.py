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
from ..word_level_pynini import string_file, union, word_delete_space
from ..word_level_pynini import pynutil

from ...core.processor import Processor
from ...core.utils import get_abs_path


class FractionRule(Processor):
    """
    Fraction rule processor
    Handles fraction expressions to prevent them from being recognized as time
    e.g., "one tenth" -> fraction (not time 1:10)
          "two thirds" -> fraction (not time)
          "a quarter" -> fraction (not time)
    """

    def __init__(self):
        super().__init__(name="fraction")
        self.build_tagger()

    def build_tagger(self):
        insert = pynutil.insert
        delete_space = word_delete_space()  # 使用词级delete_space
        # Load numerators (basic numbers)
        numerator_words = string_file(get_abs_path("../data/numbers/digit.tsv"))
        numerator_words |= string_file(get_abs_path("../data/numbers/ties.tsv"))
        numerator_words |= string_file(get_abs_path("../data/numbers/teen.tsv"))

        # Special numerator: "a" or "an" = 1
        a_or_an = union(
            "a",
            "an",
            "one",
            "two",
            "three",
            "four",
            "five",
            "six",
            "seven",
            "eight",
            "nine",
            "ten",
        )

        # Load denominators (fraction words)
        denominator = string_file(get_abs_path("../data/numbers/fraction_denominators.tsv"))

        # Pattern: [numerator] + [denominator]
        # e.g., "one tenth", "two thirds", "a quarter", "three fifths"
        # Note: We don't match standalone "half" or "quarter" to avoid conflicts with time expressions
        # like "quarter past two" or "half past three"
        fraction_pattern = (
            insert('numerator:"')
            + a_or_an
            + insert('"')
            + delete_space
            + insert('denominator:"')
            + denominator
            + insert('"')
        )

        self.tagger = self.add_tokens(fraction_pattern)
