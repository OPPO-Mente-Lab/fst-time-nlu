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
from ..word_level_pynini import string_file, closure
from ..word_level_pynini import pynutil
from ..word_level_pynini import word_delete_space

from ...core.processor import Processor
from ...core.utils import INPUT_LOWER_CASED, INPUT_CASED, get_abs_path
from .base import TimeBaseRule, WeekBaseRule


class WeekRule(Processor):
    """Week rule processor, handles week-related time expressions"""

    def __init__(self, input_case: str = INPUT_CASED):
        super().__init__(name="time_weekday")
        self.input_case = input_case
        self.weekday = WeekBaseRule(input_case=input_case).build_rules()
        self.time = TimeBaseRule(input_case=input_case).build_time_rules()
        self.period = self._build_period_rules()
        self.build_tagger(input_case=input_case)

    def _build_period_rules(self):
        """Build period rules for combination with weekday"""
        insert = pynutil.insert
        # Load period data files
        basic_periods = string_file(get_abs_path("../data/period/basic_periods.tsv"))
        extended_periods = string_file(get_abs_path("../data/period/extended_periods.tsv"))

        # Combine all periods
        all_periods = basic_periods | extended_periods

        # Create period tag (use noon attribute for consistency)
        period_tag = insert('noon:"') + all_periods + insert('"')

        return period_tag

    def build_tagger(self, input_case: str = INPUT_CASED):
        """Build the tagger combining weekday, time, and period rules"""
        # 使用词级delete_space
        delete_space = word_delete_space()
        # Add optional 'on' prefix for weekdays
        # 使用更严格的匹配：'on' 后面必须跟空格
        optional_on = closure(pynutil.delete("on") + delete_space, 0, 1)

        # Combine weekday with optional period or time
        # Priority: weekday + period, weekday + time, weekday only

        # Add strict word boundary handling for weekdays
        # Remove the explicit delete_space requirement, as boundary is now in weekday itself
        weekday_with_period = optional_on + self.weekday + delete_space + self.period
        weekday_with_time = optional_on + self.weekday + delete_space + self.time
        weekday_standalone = optional_on + self.weekday

        tagger = (
            weekday_with_period
            | weekday_with_time
            | weekday_standalone  # Standalone weekday with optional 'on'
        )
        self.tagger = self.add_tokens(tagger)
