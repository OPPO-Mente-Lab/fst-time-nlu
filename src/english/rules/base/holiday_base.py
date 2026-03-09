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

# 使用词级string_file
from ...word_level_pynini import word_string_file

# 使用词级pynutil
from ...word_level_pynini import pynutil
from ....core.utils import get_abs_path, INPUT_CASED

insert = pynutil.insert


class HolidayBaseRule:
    """Holiday base rule class"""

    def __init__(self, input_case=INPUT_CASED):
        self.input_case = input_case
        # Load festival data files (使用词级string_file)
        self.statutory_holidays = word_string_file(
            get_abs_path("../../data/holiday/statutory_holidays.tsv")
        )
        self.calendar_festivals = word_string_file(
            get_abs_path("../../data/holiday/calendar_festivals.tsv")
        )

        # Combined festival FST (reusable)
        self.festivals = self.statutory_holidays | self.calendar_festivals

    def build_rules(self):
        """Build holiday rules with festival tag"""
        # Use the festivals as-is - the normalizer will handle case conversion
        holiday = insert('festival:"') + self.festivals + insert('"')
        return holiday
