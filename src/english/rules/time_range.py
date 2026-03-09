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
from ..word_level_pynini import string_file, accep, union, word_delete_space
from ..word_level_pynini import pynutil

from ...core.processor import Processor
from ...core.utils import get_abs_path, INPUT_LOWER_CASED


class TimeRangeRule(Processor):
    """
    English time range rule processor

    Handles time range adverbs and expressions like:
    - "recently" (7 days ago to now)
    - "lately" (7 days ago to now)
    - "recent week" (past 7 days)
    - "recent 30 days" (past 30 days)
    - "past week" (past 7 days)
    - "past 30 days" (past 30 days)
    """

    def __init__(self, input_case: str = INPUT_LOWER_CASED):
        super().__init__(name="time_range")
        self.input_case = input_case
        self.build_tagger()

    def build_tagger(self):
        """Build time range FST tagger using TSV files (inspired by Chinese FST design)"""
        insert = pynutil.insert

        # Load TSV files - data-driven approach like Chinese FST
        range_prefix = string_file(get_abs_path("../data/period/range_prefix.tsv"))
        range_unit = string_file(get_abs_path("../data/period/range_unit.tsv"))
        range_word = string_file(get_abs_path("../data/period/range_word.tsv"))
        english_numbers = string_file(get_abs_path("../data/period/english_numbers.tsv"))

        # Load modifier + noun pattern files
        modifier_future = string_file(get_abs_path("../data/period/modifier_noun_future.tsv"))
        modifier_past = string_file(get_abs_path("../data/period/modifier_noun_past.tsv"))
        time_related_nouns = string_file(get_abs_path("../data/period/time_related_nouns.tsv"))

        # Support capitalized input if needed
        if self.input_case == INPUT_LOWER_CASED:
            # Add capitalized versions (direction mapping is handled by TSV file)
            range_prefix |= (
                accep("Recent")
                | accep("Past")
                | accep("Last")
                | accep("Next")
                | accep("Future")
                | accep("Within")
            )

        # Numbers: both digits and English words
        # 词级数字匹配：创建0-999的数字token union（词级FST中数字是完整token）
        # 对于更大的数字，可以扩展范围或使用更灵活的方法
        digit_tokens = [accep(str(i)) for i in range(1000)]  # 0-999
        digit_number = union(*digit_tokens)
        number = digit_number | english_numbers

        # Optional space (使用词级delete_space)
        delete_space = word_delete_space()
        optional_space = delete_space.ques

        # Build tags similar to Chinese FST
        range_prefix_tag = insert('offset_direction:"') + range_prefix + insert('"')
        range_unit_tag = insert('unit:"') + range_unit + insert('"')
        range_word_tag = insert('range_days:"') + range_word + insert('"')

        # Pattern 1: "recent three months" / "past two years" / "next five days"
        # prefix + number + unit
        range_with_number = (
            range_prefix_tag
            + optional_space
            + insert('offset:"')
            + number
            + insert('"')
            + optional_space
            + range_unit_tag
        )

        # Pattern 2: "recently" / "lately" (standalone words)
        range_word_only = range_word_tag

        # Pattern 3: "recent week" / "past month" (prefix + unit, assume 1)
        range_unit_only = (
            range_prefix_tag
            + optional_space
            + insert('offset:"1"')
            + optional_space
            + range_unit_tag
        )

        # Pattern 4: "subsequent itinerary" / "previous plan" / "upcoming schedule"
        # modifier + time_related_noun -> offset_direction: "1/-1", offset: "7", unit: "day"
        # Future modifiers: subsequent, upcoming, following, ensuing, succeeding, next, later
        modifier_future_tag = insert('offset_direction:"') + modifier_future + insert('"')
        # Past modifiers: previous, prior, preceding
        modifier_past_tag = insert('offset_direction:"') + modifier_past + insert('"')
        # Time related nouns: itinerary, plan, schedule (singular and plural)
        time_noun_tag = insert('unit:"') + time_related_nouns + insert('"')

        # Future: "subsequent itinerary" -> offset_direction: "1", offset: "7", unit: "day"
        range_modifier_noun_future = (
            modifier_future_tag
            + optional_space
            + insert('offset:"7"')
            + optional_space
            + time_noun_tag
        )

        # Past: "previous plan" -> offset_direction: "-1", offset: "7", unit: "day"
        range_modifier_noun_past = (
            modifier_past_tag
            + optional_space
            + insert('offset:"7"')
            + optional_space
            + time_noun_tag
        )

        range_modifier_noun = range_modifier_noun_future | range_modifier_noun_past

        # Combine all patterns - more specific first
        # Priority: range_with_number > range_unit_only > range_modifier_noun > range_word_only
        combined_tagger = (
            self.add_tokens(range_with_number)
            | self.add_tokens(range_unit_only)
            | self.add_tokens(range_modifier_noun)
            | self.add_tokens(range_word_only)
        )

        self.tagger = combined_tagger
