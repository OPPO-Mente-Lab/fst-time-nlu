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


class DeltaParser(BaseParser):
    """
    English delta parser (aligned with Chinese FST)

    Handles time delta expressions such as:
    - 10 years later
    - 3 months ago
    - 2 weeks before
    - 5 days from now
    - in 2 hours
    - 30 minutes later
    """

    def __init__(self):
        """Initialize delta parser"""
        super().__init__()

    def parse(self, token, base_time):  # noqa: C901
        """
        Parse time delta expression

        Args:
            token (dict): Time delta token containing direction, year, month, week, day, hour, minute, second
            base_time (datetime): Base time reference

        Returns:
            list: Time range list in format [[start_time_str, end_time_str]]
        """
        # Extract direction from token
        direction = 1  # Default to future
        if "offset_direction" in token:
            try:
                direction = int(token["offset_direction"].strip('"'))
            except (ValueError, TypeError):
                direction = 1

        # Extract time numbers from token
        time_num = {}
        for field in ["year", "month", "week", "day", "hour", "minute", "second"]:
            if field in token:
                try:
                    time_num[field] = int(token[field].strip('"'))
                except (ValueError, TypeError):
                    pass

        # Handle fractional time (e.g., "an hour and a half")
        if "fractional" in token:
            try:
                fractional = float(token["fractional"].strip('"'))
                # Apply fractional to the largest time unit present
                if "hour" in time_num:
                    time_num["hour"] += fractional
                elif "minute" in time_num:
                    time_num["minute"] += fractional * 60  # Convert to minutes
                elif "day" in time_num:
                    time_num["day"] += fractional
                elif "week" in time_num:
                    time_num["week"] += fractional
                elif "month" in time_num:
                    time_num["month"] += fractional
                elif "year" in time_num:
                    time_num["year"] += fractional
            except (ValueError, TypeError):
                pass

        # Apply offset based on direction
        if "offset_direction" in token:
            # Use offset approach (e.g., "10 years later")
            base_time = self._apply_offset_time_num(base_time, time_num, direction)
        else:
            # Use set approach (e.g., set to specific time)
            base_time = self._set_time_num(base_time, time_num)

        # Handle different time units
        return self._handle_time_units(base_time, time_num)

    def _handle_time_units(self, base_time, time_num):
        """
        Handle different time units based on what's in time_num

        Args:
            base_time (datetime): Base time reference
            time_num (dict): Time number dictionary

        Returns:
            list: Time range list
        """
        # Year delta handling (e.g., "10 years later")
        if "year" in time_num:
            return self._handle_year_delta(base_time)

        # Month delta handling (e.g., "3 months ago")
        if "month" in time_num:
            return self._handle_month_delta(base_time)

        # Week delta handling (e.g., "2 weeks before")
        if "week" in time_num:
            return self._handle_week_delta(base_time)

        # Day delta handling (e.g., "5 days from now")
        if "day" in time_num:
            return self._handle_day_delta(base_time)

        # Handle hour/minute/second
        return self._handle_time_delta(base_time, time_num)

    def _apply_offset_time_num(self, base_time, time_num, direction):
        """
        Apply time offset to base time

        Args:
            base_time (datetime): Base time reference
            time_num (dict): Time number dictionary
            direction (int): Direction (1 for future, -1 for past)

        Returns:
            datetime: Modified base time
        """
        from dateutil.relativedelta import relativedelta

        result_time = base_time

        # Apply year offset
        if "year" in time_num:
            years = time_num["year"] * direction
            result_time = result_time + relativedelta(years=years)

        # Apply month offset
        if "month" in time_num:
            months = time_num["month"] * direction
            result_time = result_time + relativedelta(months=months)

        # Apply week offset
        if "week" in time_num:
            weeks = time_num["week"] * direction
            result_time = result_time + timedelta(weeks=weeks)

        # Apply day offset
        if "day" in time_num:
            days = time_num["day"] * direction
            result_time = result_time + timedelta(days=days)

        # Apply hour offset
        if "hour" in time_num:
            hours = time_num["hour"] * direction
            result_time = result_time + timedelta(hours=hours)

        # Apply minute offset
        if "minute" in time_num:
            minutes = time_num["minute"] * direction
            result_time = result_time + timedelta(minutes=minutes)

        # Apply second offset
        if "second" in time_num:
            seconds = time_num["second"] * direction
            result_time = result_time + timedelta(seconds=seconds)

        return result_time

    def _set_time_num(self, base_time, time_num):
        """
        Set specific time components

        Args:
            base_time (datetime): Base time reference
            time_num (dict): Time number dictionary

        Returns:
            datetime: Modified base time
        """
        result_time = base_time

        # Set year
        if "year" in time_num:
            result_time = result_time.replace(year=time_num["year"])

        # Set month
        if "month" in time_num:
            result_time = result_time.replace(month=time_num["month"])

        # Set day
        if "day" in time_num:
            result_time = result_time.replace(day=time_num["day"])

        # Set hour
        if "hour" in time_num:
            result_time = result_time.replace(hour=time_num["hour"])

        # Set minute
        if "minute" in time_num:
            result_time = result_time.replace(minute=time_num["minute"])

        # Set second
        if "second" in time_num:
            result_time = result_time.replace(second=time_num["second"])

        return result_time

    def _handle_year_delta(self, base_time):
        """
        Handle year delta

        Args:
            base_time (datetime): Base time reference

        Returns:
            list: Full year range (00:00:00 to 23:59:59)
        """
        # Return full year range
        start_of_year, end_of_year = self._get_year_range(base_time)
        return self._format_time_result(start_of_year, end_of_year)

    def _handle_month_delta(self, base_time):
        """
        Handle month delta

        Args:
            base_time (datetime): Base time reference

        Returns:
            list: Full month range (00:00:00 to 23:59:59)
        """
        # Return full month range
        start_of_month, end_of_month = self._get_month_range(base_time)
        return self._format_time_result(start_of_month, end_of_month)

    def _handle_day_delta(self, base_time):
        """
        Handle day delta

        Args:
            base_time (datetime): Base time reference

        Returns:
            list: Full day range (00:00:00 to 23:59:59)
        """
        # Return full day range
        start_of_day, end_of_day = self._get_day_range(base_time)
        return self._format_time_result(start_of_day, end_of_day)

    def _handle_week_delta(self, base_time):
        """
        Handle week delta, return full day range (00:00:00 to 23:59:59)
        """
        # Return full day range
        start_of_day, end_of_day = self._get_day_range(base_time)
        return self._format_time_result(start_of_day, end_of_day)

    def _handle_time_delta(self, base_time, time_num):
        """
        Handle hour/minute/second delta

        Args:
            base_time (datetime): Base time reference
            time_num (dict): Time number dictionary

        Returns:
            list: Time range list
        """
        # No hour/minute/second, return full day
        if "hour" not in time_num and "minute" not in time_num and "second" not in time_num:
            start_of_day, end_of_day = self._get_day_range(base_time)
            return self._format_time_result(start_of_day, end_of_day)

        # Only minute, no hour and second
        elif "hour" not in time_num and "minute" in time_num and "second" not in time_num:
            # Keep original seconds, don't reset to 0
            return self._format_time_result(base_time)

        # Has hour and minute, no second
        elif "hour" in time_num and "minute" in time_num and "second" not in time_num:
            # Keep original seconds, don't reset to 0
            return self._format_time_result(base_time)

        # Other cases, return current time
        else:
            return self._format_time_result(base_time)
