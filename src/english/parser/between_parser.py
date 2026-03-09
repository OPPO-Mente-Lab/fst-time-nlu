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

from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from .base_parser import BaseParser


class BetweenParser(BaseParser):
    """
    Between time parser for English

    Handles time range expressions like:
    - "from tomorrow to day after tomorrow"
    - "from 9 to 11" (time range)
    - "between X and Y"
    - "from 2020 to 2025"
    """

    def __init__(self):
        """Initialize between time parser"""
        super().__init__()

    def parse(self, token, base_time):
        """
        Parse between time expression

        Args:
            token (dict): Time expression token
            base_time (datetime): Base time reference

        Returns:
            list: Time range list in format [[start_time_str, end_time_str]]
        """
        raw_type = token.get("raw_type", "")

        if raw_type == "relative":
            # Handle relative time ranges like "tomorrow to day after tomorrow"
            return self._parse_relative_range(token, base_time)
        elif raw_type == "utc":
            # Handle UTC time ranges like "april 3 to may 1"
            return self._parse_utc_range(token, base_time)
        else:
            return []

    def _parse_relative_range(self, token, base_time):
        """Parse relative time range"""
        # For now, return a simple range based on offset_day
        offset_day = int(token.get("offset_day", "0").strip('"'))

        from datetime import timedelta

        start_time = base_time + timedelta(days=offset_day)
        end_time = start_time + timedelta(days=1)

        return self._format_time_result(start_time, end_time)

    def _parse_utc_range(self, token, base_time):
        """Parse UTC time range"""
        # Handle time range with start/end times (e.g., "14:40 to 15:10")
        if "start_hour" in token and "end_hour" in token:
            return self._parse_time_range(token, base_time)

        # Handle date range with month/day
        month = token.get("month", "").strip('"')
        day = token.get("day", "").strip('"')
        year = token.get("year", str(base_time.year)).strip('"')

        # Apply relative offsets
        if "offset_year" in token:
            try:
                year_offset = int(token["offset_year"].strip('"'))
                year = str(base_time.year + year_offset)
            except (ValueError, TypeError):
                pass

        if not month or not day:
            return []

        try:
            # Convert month name to number
            month_map = {
                "january": 1,
                "february": 2,
                "march": 3,
                "april": 4,
                "may": 5,
                "june": 6,
                "july": 7,
                "august": 8,
                "september": 9,
                "october": 10,
                "november": 11,
                "december": 12,
            }

            month_num = month_map.get(month.lower(), int(month))
            day_num = int(day)
            year_num = int(year)

            # Create start time (beginning of day)
            start_time = base_time.replace(
                year=year_num,
                month=month_num,
                day=day_num,
                hour=0,
                minute=0,
                second=0,
                microsecond=0,
            )

            # Create end time (end of day)
            end_time = start_time.replace(hour=23, minute=59, second=59, microsecond=999999)

            return self._format_time_result(start_time, end_time)

        except (ValueError, TypeError):
            return []

    def _parse_time_range(self, token, base_time):
        """Parse time range (e.g., '14:40 to 15:10')"""
        try:
            start_hour = int(token.get("start_hour", "0").strip('"'))
            start_minute = int(token.get("start_minute", "0").strip('"'))
            end_hour = int(token.get("end_hour", "0").strip('"'))
            end_minute = int(token.get("end_minute", "0").strip('"'))

            # Handle AM/PM periods
            start_period = token.get("start_period", "").strip('"')
            end_period = token.get("end_period", "").strip('"')

            if start_period == "p.m." and start_hour < 12:
                start_hour += 12
            if end_period == "p.m." and end_hour < 12:
                end_hour += 12

            # Apply relative day offset if present
            target_date = base_time
            if "offset_day" in token:
                try:
                    day_offset = int(token["offset_day"].strip('"'))
                    target_date = base_time + timedelta(days=day_offset)
                except (ValueError, TypeError):
                    pass

            # Create start and end times
            start_time = target_date.replace(
                hour=start_hour, minute=start_minute, second=0, microsecond=0
            )
            end_time = target_date.replace(
                hour=end_hour, minute=end_minute, second=59, microsecond=999999
            )

            return self._format_time_result(start_time, end_time)

        except (ValueError, TypeError):
            return []

    def _parse_time_range_from_tokens(self, start_token, end_token, base_time):
        """
        Parse a time range from start and end tokens

        Args:
            start_token (dict): Start time token
            end_token (dict): End time token
            base_time (datetime): Base time reference

        Returns:
            list: Time range list
        """
        # This would be implemented to parse the start and end times
        # and return the range between them
        return []
