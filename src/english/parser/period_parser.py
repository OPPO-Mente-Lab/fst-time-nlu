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

from datetime import timedelta
from .base_parser import BaseParser


class PeriodParser(BaseParser):
    """
    Time period parser for English

    Handles time period expressions like:
    - morning, afternoon, evening, night
    - breakfast, lunch, dinner
    - noon, midnight

    Uses the unified period_map defined in BaseParser (similar to Chinese noon_map)
    """

    def __init__(self):
        """Initialize time period parser"""
        super().__init__()

    def parse(self, token, base_time):
        """
        Parse time period expression

        Args:
            token (dict): Time expression token containing 'period' field
            base_time (datetime): Base time reference

        Returns:
            list: Time range list in format [[start_time_str, end_time_str]]
        """
        # Handle month period tokens (from PeriodRule with month_period + month)
        if token.get("month_period") and token.get("month"):
            # Delegate to UTCTimeParser for month period handling
            from .utctime_parser import UTCTimeParser

            utc_parser = UTCTimeParser()
            return utc_parser.parse(token, base_time)

        # Use noon field if available, fallback to period field
        period = (
            token.get("noon", "").strip('"').lower() or token.get("period", "").strip('"').lower()
        )

        if not period:
            return []

        # Use the unified _parse_period method from BaseParser
        start_time, end_time = self._parse_period(base_time, period)

        # If start and end are the same (e.g., midnight), return single point
        if start_time == end_time:
            return self._format_time_result(start_time)

        return self._format_time_result(start_time, end_time)
