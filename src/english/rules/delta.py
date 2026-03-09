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

from pynini import string_file, union
from pynini.lib.pynutil import insert, delete

from ...core.processor import Processor
from ...core.utils import get_abs_path
from .base import DateBaseRule, TimeBaseRule


class DeltaRule(Processor):
    """English delta rule processor (aligned with Chinese FST)

    Handles time delta expressions like:
    - "10 years later" -> year: "10", offset_direction: "1"
    - "3 months ago" -> month: "3", offset_direction: "-1"
    - "2 weeks before" -> week: "2", offset_direction: "-1"
    - "5 days from now" -> day: "5", offset_direction: "1"
    - "in 2 hours" -> hour: "2", offset_direction: "1"
    - "30 minutes later" -> minute: "30", offset_direction: "1"
    """

    def __init__(self):
        super().__init__(name="time_delta")
        self.time_cnt = TimeBaseRule().build_time_cnt_rules()
        self.date_cnt = DateBaseRule().build_date_cnt_rule()

        # Build offset direction rules
        # Handle empty before_prefix file
        try:
            self.before_prefix = (
                insert('offset_direction:"')
                + string_file(get_abs_path("../data/delta/before_prefix.tsv"))
                + insert('"')
            )
        except FileNotFoundError:
            # Empty file - create empty FST
            self.before_prefix = union()

        self.before_suffix = (
            insert('offset_direction:"')
            + string_file(get_abs_path("../data/delta/before_suffix.tsv"))
            + insert('"')
        )
        self.after_prefix = (
            insert('offset_direction:"')
            + string_file(get_abs_path("../data/delta/after_prefix.tsv"))
            + insert('"')
        )
        self.after_suffix = (
            delete(" ").ques
            + insert('offset_direction:"')
            + string_file(get_abs_path("../data/delta/after_suffix.tsv"))
            + insert('"')
        )
        self.build_tagger()

    def build_tagger(self):
        """Build time delta rules (aligned with Chinese FST implementation)"""

        # Pattern 1: date_cnt + after_suffix (e.g., "10 years later")
        after_date = self.date_cnt + self.after_suffix

        # Pattern 2: date_cnt + before_suffix (e.g., "10 years ago")
        before_date = self.date_cnt + self.before_suffix

        # Pattern 3: after_prefix + date_cnt (e.g., "in 10 years")
        after_prefix_date = self.after_prefix + delete(" ").ques + self.date_cnt

        # Pattern 4: time_cnt + after_suffix (e.g., "2 hours later")
        after_time = self.time_cnt + self.after_suffix

        # Pattern 5: time_cnt + before_suffix (e.g., "2 hours ago")
        before_time = self.time_cnt + self.before_suffix

        # Pattern 6: after_prefix + time_cnt (e.g., "in 2 hours")
        after_prefix_time = self.after_prefix + delete(" ").ques + self.time_cnt

        # Pattern 7: compound time deltas (e.g., "2 hours and 18 minutes later")
        # Simplified version to reduce FST complexity
        compound_time = (
            self.time_cnt
            + delete(" ").ques
            + delete("and").ques
            + delete(" ").ques
            + self.time_cnt
            + self.after_suffix
        )

        # Combine all patterns (prioritize simpler patterns)
        tagger = self.add_tokens(
            after_date
            | before_date
            | after_prefix_date
            | after_time
            | before_time
            | after_prefix_time
            | compound_time
        )
        self.tagger = tagger
