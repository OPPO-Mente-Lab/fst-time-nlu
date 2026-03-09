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

from pynini import union
from pynini.lib.pynutil import delete, insert

from ...core.processor import Processor
from ...core.utils import INPUT_LOWER_CASED
from .base.date_base import DateBaseRule
from .base.time_base import TimeBaseRule
from .base.relative_base import RelativeBaseRule


class DateIntervalRule(Processor):
    """
    Date interval rule processor for English

    Handles date range expressions like:
    - "from tomorrow to day after tomorrow"
    - "from March 3 to March 10" (date range)
    - "between Monday and Friday"
    - "from 2020 to 2025"
    """

    def __init__(self, input_case: str = INPUT_LOWER_CASED):
        super().__init__(name="date_interval")
        self.input_case = input_case

        # Build base rules
        self._date_base = DateBaseRule(input_case=input_case)
        self._time_base = TimeBaseRule(input_case=input_case)
        self._relative_base = RelativeBaseRule(input_case=input_case)

        # Build components
        self.year = self._date_base.build_year_rules()
        self.month = self._date_base.build_month_rules()
        self.date = self._date_base.build_date_rules()
        self.time = self._time_base.build_time_rules()
        self.relative = self._relative_base.build_std_rules()

        self.build_tagger()

    def build_tagger(self):
        """Build between time FST tagger"""

        # Build UTC time expressions
        utc_time = (
            (self.date + delete(" ").ques + self.time)  # Date + time
            | self.date  # Date only
            | self.year  # Year only
            | self.month  # Month only
            | self.time  # Time only
        )

        # Mark time types
        between_utc_time = utc_time + insert('raw_type:"utc"')
        between_relative_time = self.relative + insert('raw_type:"relative"')

        # Time range expressions
        between_time = between_utc_time | between_relative_time

        # Range connectors
        space = delete(" ").star

        # "from X to Y" pattern
        from_to = (
            delete("from").ques
            + space
            + between_time
            + space
            + (delete("to") | delete("until"))
            + space
            + between_time
        )

        # "between X and Y" pattern
        between_and = (
            delete("between") + space + between_time + space + delete("and") + space + between_time
        )

        # "X to Y" pattern (without from/between)
        direct_to = (
            between_time + space + (delete("to") | delete("-") | delete("~")) + space + between_time
        )

        # Combine all patterns
        between_patterns = from_to | between_and | direct_to

        # Add class wrapper
        tagger = self.add_tokens(between_patterns)
        self.tagger = tagger
