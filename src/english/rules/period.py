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
from ..word_level_pynini import string_file, union
from ..word_level_pynini import pynutil
from ..word_level_utils import word_delete_space
from ...core.processor import Processor
from ...core.utils import get_abs_path, INPUT_LOWER_CASED
from .base.date_base import DateBaseRule


class PeriodRule(Processor):
    """
    English time period rule processor

    Handles time period expressions like:
    - "morning", "afternoon", "evening", "night"
    - "lunch", "breakfast", "dinner"
    - "noon", "midnight"
    """

    def __init__(self, input_case: str = INPUT_LOWER_CASED):
        super().__init__(name="time_period")
        self.input_case = input_case
        self.build_tagger()

    def build_tagger(self):
        """Build time period FST tagger"""

        # Load basic time periods (morning, afternoon, evening, night, etc.)
        basic_periods = string_file(get_abs_path("../data/period/basic_periods.tsv"))

        # Load extended periods (early morning, late afternoon, lunchtime, etc.)
        extended_periods = string_file(get_abs_path("../data/period/extended_periods.tsv"))

        # Load seasonal periods (spring, summer, autumn, winter, fall)
        seasonal_periods = string_file(get_abs_path("../data/period/seasonal_periods.tsv"))

        # Load month period prefix (early, mid, late)
        month_period_prefix = string_file(get_abs_path("../data/period/month_period.tsv"))

        # Load year prefix (last year, next year, etc.)
        year_prefix = string_file(get_abs_path("../data/period/year_prefix.tsv"))

        # Load month names from DateBaseRule
        date_base = DateBaseRule(input_case=self.input_case)
        month_names = date_base.month  # Includes month names and abbreviations

        # Pattern: month_period + month
        # Example: "early March", "mid December", "late January"
        insert = pynutil.insert
        delete_space_fst = word_delete_space()  # 词级delete_space
        optional_space = delete_space_fst.ques  # 0 or 1 space token

        period_month_std = (
            insert('month_period:"')
            + month_period_prefix
            + insert('"')
            + optional_space
            + insert('month:"')
            + month_names
            + insert('"')
        )

        # Pattern: year_prefix + month_period + month
        # Example: "next year mid december", "last year early march"
        period_year_month_std = (
            insert('offset_year:"')
            + year_prefix
            + insert('"')
            + optional_space
            + insert('month_period:"')
            + month_period_prefix
            + insert('"')
            + optional_space
            + insert('month:"')
            + month_names
            + insert('"')
        )

        # Pattern: month_period + month + year_prefix
        # Example: "mid december next year", "early march last year"
        period_month_year_std = (
            insert('month_period:"')
            + month_period_prefix
            + insert('"')
            + optional_space
            + insert('month:"')
            + month_names
            + insert('"')
            + optional_space
            + insert('offset_year:"')
            + year_prefix
            + insert('"')
        )

        # Combine all period types
        all_periods = basic_periods | extended_periods | seasonal_periods

        # Create period tag (use noon attribute for consistency)
        # 注意：不使用空格，避免输出中包含空格token
        period_tag = insert('noon:"') + all_periods + insert('"')

        # Combine month period pattern with regular period patterns
        # Year+month period patterns have highest priority (comes first)
        combined_tagger = (
            period_year_month_std | period_month_year_std | period_month_std | period_tag
        )

        # Add class wrapper
        tagger = self.add_tokens(combined_tagger)
        self.tagger = tagger
