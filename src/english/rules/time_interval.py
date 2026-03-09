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

from pynini import accep, union
from pynini.lib.pynutil import insert, delete
from ...core.processor import Processor
from ...core.utils import INPUT_LOWER_CASED


class TimeIntervalRule(Processor):
    """
    English time interval rule processor

    Handles explicit time range expressions like:
    - "8 to 10 o'clock" (hour range)
    - "8 to 10" (hour range without o'clock)
    - "from 2pm to 5pm" (explicit time range with periods)
    """

    def __init__(self, input_case: str = INPUT_LOWER_CASED):
        super().__init__(name="time_interval")
        self.input_case = input_case
        self.build_tagger()

    def build_tagger(self):
        """Build time range FST tagger"""

        # Hour numbers (1-12 or 00-23)
        hour_1_12 = union(*[accep(str(i)) for i in range(1, 13)])
        hour_0_23 = union(*[accep(str(i)) for i in range(0, 24)])
        hour = hour_1_12 | hour_0_23

        # Optional space
        optional_space = delete(self.SPACE).ques

        # "to" connector
        to_connector = optional_space + delete(accep("to")) + optional_space

        # o'clock variations
        oclock = union(accep("oclock"), accep("o'clock"), accep("o clock"))

        # Pattern 1: "8 to 10 o'clock" or "8 to 10 oclock"
        # This captures hour ranges with o'clock
        hour_range_oclock = (
            insert('start_hour:"')
            + hour
            + insert('"')
            + to_connector
            + insert('end_hour:"')
            + hour
            + insert('"')
            + optional_space
            + delete(oclock)
        )

        # Pattern 2: "8 to 10" (simple hour range without o'clock)
        # Disabled for now to avoid conflicts with "14:31 to 15:00" style ranges
        # These should be handled by from...to logic in TimeParser
        # hour_range_simple = (
        #     insert('start_hour:"') +
        #     hour +
        #     insert('"') +
        #     to_connector +
        #     insert('end_hour:"') +
        #     hour +
        #     insert('"')
        # )

        # Combine patterns (only use oclock pattern for now)
        range_expr = hour_range_oclock  # | hour_range_simple

        # Add class wrapper
        tagger = self.add_tokens(range_expr)
        self.tagger = tagger
