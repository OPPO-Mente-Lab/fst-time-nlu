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


class RelativeParser(BaseParser):
    """
    Relative time parser for English

    Handles relative time expressions such as:
    - last year, this year, next year
    - last month, this month, next month
    - yesterday, today, tomorrow
    - yesterday morning, tomorrow evening (relative day + period)
    """

    def __init__(self):
        """Initialize relative time parser"""
        super().__init__()

    def parse(self, token, base_time):  # noqa: C901
        """
        Parse relative time expression

        Args:
            token (dict): Time expression token
            base_time (datetime): Base time reference

        Returns:
            list: Time range list in format [[start_time_str, end_time_str]]
        """
        # Extract offset information
        offset_year = token.get("offset_year", "").strip('"')
        offset_month = token.get("offset_month", "").strip('"')
        offset_quarter = token.get("offset_quarter", "").strip('"')
        offset_day = token.get("offset_day", "").strip('"')
        offset_time = token.get("offset_time", "").strip('"')
        offset_week = token.get("offset_week", "").strip('"')
        weekday = token.get("weekday", "").strip('"')

        # Extract period boundary information
        month_period = token.get("month_period", "").strip('"')
        quarter_period = token.get("quarter_period", "").strip('"')
        year_period = token.get("year_period", "").strip('"')

        # Extract time and period information
        time_num = self._get_time_num(token)
        # Use noon field if available, fallback to period field
        period_str = token.get("noon", "").strip('"') or token.get("period", "").strip('"')

        # Special case: "now" expressions (offset_time: "0")
        # Return the current moment based on base_time
        if offset_time == "0" and offset_day == "0":
            # Use base_time as the "now" time point
            return self._format_time_result(base_time)

        # Calculate the target date based on offsets
        target_date = base_time

        if offset_year:
            try:
                years_delta = int(offset_year)
                target_date = target_date + relativedelta(years=years_delta)
            except (ValueError, TypeError):
                pass

        if offset_month:
            try:
                months_delta = int(offset_month)
                target_date = target_date + relativedelta(months=months_delta)
            except (ValueError, TypeError):
                pass

        if offset_quarter:
            try:
                quarters_delta = int(offset_quarter)
                target_date = target_date + relativedelta(months=quarters_delta * 3)
            except (ValueError, TypeError):
                pass

        if offset_day:
            try:
                days_delta = int(offset_day)
                target_date = target_date + timedelta(days=days_delta)
            except (ValueError, TypeError):
                pass

        # Handle weekday offset (e.g., "3 fridays from now")
        if offset_week and weekday:
            try:
                weeks_delta = int(offset_week)
                target_weekday = int(weekday)

                # Calculate the Nth occurrence of target weekday from today
                # Counting rule: from today start counting towards future
                current_weekday = target_date.weekday()  # Monday=0, Sunday=6

                # Calculate days to first occurrence
                if current_weekday < target_weekday:
                    # Target is later this week
                    days_to_first = target_weekday - current_weekday
                else:
                    # Target is next week
                    days_to_first = 7 - current_weekday + target_weekday

                # Calculate days to Nth occurrence
                total_days = days_to_first + (weeks_delta - 1) * 7
                target_date = target_date + timedelta(days=total_days)

            except (ValueError, TypeError):
                pass

        # Handle different cases
        # Case 0: Period boundaries (highest priority)
        # Case 0a: Month boundaries (beginning of this month, end of last month)
        if offset_month and month_period:
            return self._handle_month_boundary(target_date, month_period)

        # Case 0b: Quarter boundaries (beginning of this quarter, end of last quarter)
        if offset_quarter and quarter_period:
            return self._handle_quarter_boundary(target_date, quarter_period)

        # Case 0c: Year boundaries (beginning of this year, end of last year)
        if offset_year and year_period:
            return self._handle_year_boundary(target_date, year_period)

        # Case 1: Year only (last year, this year, next year)
        if offset_year and not offset_month and not offset_day and not period_str and not time_num:
            start_of_year, end_of_year = self._get_year_range(target_date)
            return self._format_time_result(start_of_year, end_of_year)

        # Case 2: Month only (last month, this month, next month)
        if offset_month and not offset_day and not period_str and not time_num:
            start_of_month, end_of_month = self._get_month_range(target_date)
            return self._format_time_result(start_of_month, end_of_month)

        # Case 3: Weekday offset (3 fridays from now, two mondays from now)
        if offset_week and weekday and not offset_day and not period_str and not time_num:
            # Return the full day range for the target weekday
            start_of_day = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_of_day = target_date.replace(hour=23, minute=59, second=59, microsecond=999999)
            return self._format_time_result(start_of_day, end_of_day)

        # Case 4: Day + period + time (tomorrow morning 8am, today afternoon 3pm)
        # This should have the highest priority for complex expressions
        if offset_day and period_str and time_num:
            if "hour" in time_num:
                hour = int(time_num.get("hour", 0))
                minute = int(time_num.get("minute", 0))

                # Handle AM/PM period
                period = time_num.get("period", "").strip('"')
                if period in ["pm", "p.m.", "PM", "P.M."] and hour < 12:
                    hour += 12
                elif period in ["am", "a.m.", "AM", "A.M."] and hour == 12:
                    hour = 0

                # Handle time period (evening, afternoon, etc.) - similar to Chinese FST
                # Evening and night periods should add 12 hours for hours <= 12
                if period_str.lower() in ["evening", "night", "tonight"] and hour <= 12:
                    hour += 12
                    if hour >= 24:
                        hour -= 24
                        target_date = target_date + timedelta(days=1)

                target_time = target_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
                return self._format_time_result(target_time)

        # Case 4: Day + time (yesterday 3pm, tomorrow at 9:00, tonight 8:30)
        # This should have higher priority than day + period to handle "tomorrow 4pm" correctly
        if offset_day and time_num:
            if "hour" in time_num:
                hour = int(time_num.get("hour", 0))
                minute = int(time_num.get("minute", 0))

                # Handle AM/PM period
                period = time_num.get("period", "").strip('"')
                if period in ["pm", "p.m.", "PM", "P.M."] and hour < 12:
                    hour += 12
                elif period in ["am", "a.m.", "AM", "A.M."] and hour == 12:
                    hour = 0

                # Special handling for "tonight" + time
                # If is_tonight marker is present and hour < 18, assume PM (evening)
                is_tonight = token.get("is_tonight", "").strip('"')
                if is_tonight and hour < 18:
                    # If hour is 1-11, assume PM (add 12)
                    # If hour is 12-17, keep as is
                    if hour < 12:
                        hour += 12

                target_time = target_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
                return self._format_time_result(target_time)

        # Case 5: Day + period (yesterday morning, tomorrow evening)
        # Only handle period if it's not part of a time expression
        if offset_day and period_str and not time_num:
            start_time, end_time = self._parse_period(target_date, period_str)
            if start_time == end_time:
                return self._format_time_result(start_time)
            return self._format_time_result(start_time, end_time)

        # Case 5.5: Special handling for "tonight" without time
        # If is_tonight marker is present and no time specified, return evening range (18:00-23:59)
        is_tonight = token.get("is_tonight", "").strip('"')
        if is_tonight and offset_day and not time_num and not period_str:
            from datetime import datetime

            start_time = target_date.replace(hour=18, minute=0, second=0, microsecond=0)
            end_time = target_date.replace(hour=23, minute=59, second=59, microsecond=0)
            return self._format_time_result(start_time, end_time)

        # Case 6: Day only (yesterday, today, tomorrow)
        if offset_day:
            start_of_day, end_of_day = self._get_day_range(target_date)
            return self._format_time_result(start_of_day, end_of_day)

        # Default: return full day range
        start_of_day, end_of_day = self._get_day_range(target_date)
        return self._format_time_result(start_of_day, end_of_day)

    def _handle_month_boundary(self, target_date, month_period):
        """
        Handle month boundary periods (monthbeginning, monthend)
        """
        if month_period == "monthbeginning":
            # Month beginning: 1st to 10th of the month
            start_date = target_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            end_date = target_date.replace(day=10, hour=23, minute=59, second=59, microsecond=0)
            return self._format_time_result(start_date, end_date)
        elif month_period == "monthend":
            # Month end: 21st to last day of the month
            start_date = target_date.replace(day=21, hour=0, minute=0, second=0, microsecond=0)
            # Get last day of month
            if target_date.month == 12:
                next_month = target_date.replace(year=target_date.year + 1, month=1, day=1)
            else:
                next_month = target_date.replace(month=target_date.month + 1, day=1)
            last_day = next_month - timedelta(days=1)
            end_date = last_day.replace(hour=23, minute=59, second=59, microsecond=0)
            return self._format_time_result(start_date, end_date)
        else:
            # Default: return full month
            start_of_month, end_of_month = self._get_month_range(target_date)
            return self._format_time_result(start_of_month, end_of_month)

    def _handle_quarter_boundary(self, target_date, quarter_period):  # noqa: C901
        """
        Handle quarter boundary periods (quarterbeginning, quarterend)
        """
        if quarter_period == "quarterbeginning":
            # Quarter beginning: first month of the quarter
            quarter_start_month = ((target_date.month - 1) // 3) * 3 + 1
            start_date = target_date.replace(
                month=quarter_start_month,
                day=1,
                hour=0,
                minute=0,
                second=0,
                microsecond=0,
            )
            end_date = target_date.replace(
                month=quarter_start_month,
                day=31,
                hour=23,
                minute=59,
                second=59,
                microsecond=0,
            )
            # Handle months with fewer than 31 days
            try:
                return self._format_time_result(start_date, end_date)
            except ValueError:
                # Adjust for months with 30 days or February
                if quarter_start_month in [4, 6, 9, 11]:  # 30-day months
                    end_date = end_date.replace(day=30)
                elif quarter_start_month == 2:  # February
                    if target_date.year % 4 == 0 and (
                        target_date.year % 100 != 0 or target_date.year % 400 == 0
                    ):
                        end_date = end_date.replace(day=29)  # Leap year
                    else:
                        end_date = end_date.replace(day=28)  # Regular year
                return self._format_time_result(start_date, end_date)
        elif quarter_period == "quarterend":
            # Quarter end: last month of the quarter
            quarter_end_month = ((target_date.month - 1) // 3) * 3 + 3
            start_date = target_date.replace(
                month=quarter_end_month,
                day=1,
                hour=0,
                minute=0,
                second=0,
                microsecond=0,
            )
            end_date = target_date.replace(
                month=quarter_end_month,
                day=31,
                hour=23,
                minute=59,
                second=59,
                microsecond=0,
            )
            # Handle months with fewer than 31 days
            try:
                return self._format_time_result(start_date, end_date)
            except ValueError:
                # Adjust for months with 30 days or February
                if quarter_end_month in [4, 6, 9, 11]:  # 30-day months
                    end_date = end_date.replace(day=30)
                elif quarter_end_month == 2:  # February
                    if target_date.year % 4 == 0 and (
                        target_date.year % 100 != 0 or target_date.year % 400 == 0
                    ):
                        end_date = end_date.replace(day=29)  # Leap year
                    else:
                        end_date = end_date.replace(day=28)  # Regular year
                return self._format_time_result(start_date, end_date)
        else:
            # Default: return full quarter
            quarter_start_month = ((target_date.month - 1) // 3) * 3 + 1
            quarter_end_month = quarter_start_month + 2
            start_date = target_date.replace(
                month=quarter_start_month,
                day=1,
                hour=0,
                minute=0,
                second=0,
                microsecond=0,
            )
            end_date = target_date.replace(
                month=quarter_end_month,
                day=31,
                hour=23,
                minute=59,
                second=59,
                microsecond=0,
            )
            # Handle months with fewer than 31 days
            try:
                return self._format_time_result(start_date, end_date)
            except ValueError:
                # Adjust for months with 30 days
                if quarter_end_month in [4, 6, 9, 11]:  # 30-day months
                    end_date = end_date.replace(day=30)
                return self._format_time_result(start_date, end_date)

    def _handle_year_boundary(self, target_date, year_period):
        """
        Handle year boundary periods (yearbeginning, yearend)
        """
        if year_period == "yearbeginning":
            # Year beginning: January-February (1-2月)
            start_date = target_date.replace(
                month=1, day=1, hour=0, minute=0, second=0, microsecond=0
            )
            # Calculate last day of February (handle leap years)
            import calendar

            last_day_of_feb = calendar.monthrange(target_date.year, 2)[1]
            end_date = target_date.replace(
                month=2,
                day=last_day_of_feb,
                hour=23,
                minute=59,
                second=59,
                microsecond=0,
            )
            return self._format_time_result(start_date, end_date)
        elif year_period == "yearend":
            # Year end: November-December (11-12月)
            start_date = target_date.replace(
                month=11, day=1, hour=0, minute=0, second=0, microsecond=0
            )
            end_date = target_date.replace(
                month=12, day=31, hour=23, minute=59, second=59, microsecond=0
            )
            return self._format_time_result(start_date, end_date)
        else:
            # Default: return full year
            start_of_year, end_of_year = self._get_year_range(target_date)
            return self._format_time_result(start_of_year, end_of_year)
