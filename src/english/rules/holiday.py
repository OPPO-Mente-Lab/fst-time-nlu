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
from ..word_level_pynini import string_file
from ..word_level_pynini import pynutil
from ..word_level_pynini import word_delete_space

from ...core.processor import Processor
from ...core.utils import get_abs_path
from .base.holiday_base import HolidayBaseRule


class HolidayRule(Processor):
    """Holiday rule processor"""

    def __init__(self):
        super().__init__(name="time_holiday")
        self.holiday_base = HolidayBaseRule()
        self.build_tagger()

    def build_tagger(self):
        delete = pynutil.delete
        insert = pynutil.insert
        # 使用词级delete_space
        delete_space = word_delete_space()
        # Load year prefix and day prefix data
        year_prefix = string_file(get_abs_path("../data/date/year_prefix.tsv"))
        day_prefix = string_file(get_abs_path("../data/date/day_prefix.tsv"))

        # Pattern 1: "year_prefix's festival"
        # e.g., "last year's christmas" -> offset_year: "-1" festival: "christmas"
        # e.g., "next year's new year's eve" -> offset_year: "1" festival: "new_years_eve"
        possessive_marker = delete("'s") | delete("'")

        pattern1 = (
            insert('offset_year:"')
            + year_prefix
            + insert('"')
            + delete_space
            + possessive_marker
            + delete_space
            + insert('festival:"')
            + self.holiday_base.festivals
            + insert('"')
        )

        # Pattern 2: Basic festival (without year modifier)
        pattern2 = self.holiday_base.build_rules()

        # Day prefix patterns (e.g., "on may day", "that day of christmas")
        day_prefix_tag = insert('day_prefix:"') + day_prefix + insert('"')

        # Combine patterns - more specific pattern first
        # Support optional year prefix and optional day prefix
        tagger = pattern1 | (
            day_prefix_tag.ques
            + delete_space.ques
            + pattern2
            + delete_space.ques
            + day_prefix_tag.ques
        )

        self.tagger = self.add_tokens(tagger)
