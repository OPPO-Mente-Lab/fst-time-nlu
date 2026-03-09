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
from dateutil.relativedelta import relativedelta
from .base_parser import BaseParser


class TimeDeltaParser(BaseParser):
    """
    Time delta parser for English

    Handles time delta expressions such as:
    - in 10 minutes
    - 5 hours later
    - 30 seconds from now
    - half an hour
    - an hour and a half
    """

    def __init__(self):
        """Initialize time delta parser"""
        super().__init__()

    def parse(self, token, base_time):  # noqa: C901
        """
        Parse time delta expression

        Args:
            token (dict): Time delta token containing direction, hour, minute, second
            base_time (datetime): Base time reference

        Returns:
            list: Time point list in format [[time_str]]
        """
        # Extract direction
        direction = token.get("direction", "future").strip('"')

        # Extract time components
        time_num = self._get_time_num(token)

        # Check for year/month/week/day fields directly in token
        year_val = token.get("year", "").strip('"')
        month_val = token.get("month", "").strip('"')
        week_val = token.get("week", "").strip('"')
        day_val = token.get("day", "").strip('"')

        # Calculate target time
        target_time = base_time

        # Handle year/month with relativedelta
        if year_val:
            try:
                years = float(year_val)
                if years != 0:
                    sign = 1 if direction == "future" else -1
                    abs_years = abs(years)
                    integer_years = int(abs_years)
                    fractional_year = abs_years - integer_years

                    if integer_years:
                        target_time = target_time + relativedelta(years=sign * integer_years)

                    if fractional_year:
                        months_from_year = fractional_year * 12
                        integer_months = int(months_from_year)
                        fractional_month = months_from_year - integer_months

                        if integer_months:
                            target_time = target_time + relativedelta(months=sign * integer_months)

                        if fractional_month:
                            days_from_month = fractional_month * 30
                            target_time = target_time + timedelta(days=sign * days_from_month)

                    start_of_day, end_of_day = self._get_day_range(target_time)
                    return self._format_time_result(start_of_day, end_of_day)
            except (ValueError, TypeError):
                pass

        if month_val:
            try:
                months = float(month_val)
                if months != 0:
                    sign = 1 if direction == "future" else -1
                    abs_months = abs(months)
                    integer_months = int(abs_months)
                    fractional_month = abs_months - integer_months

                    if integer_months:
                        target_time = target_time + relativedelta(months=sign * integer_months)

                    if fractional_month:
                        days_from_month = fractional_month * 30
                        target_time = target_time + timedelta(days=sign * days_from_month)

                    start_of_day, end_of_day = self._get_day_range(target_time)
                    return self._format_time_result(start_of_day, end_of_day)
            except (ValueError, TypeError):
                pass

        # Handle week/day with relativedelta (return single day)
        if week_val:
            try:
                weeks = float(week_val)
                if weeks != 0:
                    if direction == "past":
                        weeks = -weeks
                    target_time = target_time + timedelta(weeks=weeks)
                    start_of_day, end_of_day = self._get_day_range(target_time)
                    return self._format_time_result(start_of_day, end_of_day)
            except (ValueError, TypeError):
                pass

        if day_val:
            try:
                days = float(day_val)
                if days != 0:
                    if direction == "past":
                        days = -days
                    target_time = target_time + timedelta(days=days)
                    start_of_day, end_of_day = self._get_day_range(target_time)
                    return self._format_time_result(start_of_day, end_of_day)
            except (ValueError, TypeError):
                pass

        # Handle hour/minute/second with timedelta (support decimal values)
        delta = timedelta()

        if "hour" in time_num:
            delta += timedelta(hours=float(time_num["hour"]))

        if "minute" in time_num:
            delta += timedelta(minutes=float(time_num["minute"]))

        if "second" in time_num:
            delta += timedelta(seconds=float(time_num["second"]))

        if delta.total_seconds() > 0:
            if direction == "future":
                target_time = base_time + delta
            else:
                target_time = base_time - delta

            # Return single time point for hour/minute/second deltas
            return self._format_time_result(target_time)

        return []
