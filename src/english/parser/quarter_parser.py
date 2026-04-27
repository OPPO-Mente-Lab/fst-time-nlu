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
Quarter parser for English time expressions.
Handles parsing of quarter-related expressions.
"""

from datetime import datetime
from dateutil.relativedelta import relativedelta
from .base_parser import BaseParser
from ...core.logger import get_logger


class QuarterParser(BaseParser):
    """Parser for quarter expressions"""

    def __init__(self):
        """Initialize quarter parser"""
        super().__init__()
        self.logger = get_logger(__name__)

    def parse(self, token, base_time):
        """
        Parse quarter token

        Args:
            token (dict): Token with quarter and optional year fields
            base_time (datetime): Base time reference

        Returns:
            list: Time range list
        """
        try:
            quarter_str = token.get("quarter", "").strip('"')
            year_str = token.get("year", "").strip('"')

            if not quarter_str:
                return []

            quarter = int(quarter_str)

            # Determine target year
            if year_str:
                target_year = int(year_str)
            else:
                target_year = base_time.year

            # Calculate quarter start and end months
            # Q1: Jan-Mar (1-3), Q2: Apr-Jun (4-6), Q3: Jul-Sep (7-9), Q4: Oct-Dec (10-12)
            start_month = (quarter - 1) * 3 + 1
            end_month = quarter * 3

            # Create start and end dates
            start_date = datetime(target_year, start_month, 1, 0, 0, 0)
            end_date = datetime(target_year, end_month, 1, 0, 0, 0)

            # Get the last day of the end month
            if end_month == 12:
                next_month = datetime(target_year + 1, 1, 1)
            else:
                next_month = datetime(target_year, end_month + 1, 1)

            end_date = next_month - relativedelta(days=1)
            end_date = end_date.replace(hour=23, minute=59, second=59, microsecond=0)

            return self._format_time_result(start_date, end_date)

        except (ValueError, TypeError) as e:
            self.logger.debug(f"Error parsing quarter token: {e}")
            return []
