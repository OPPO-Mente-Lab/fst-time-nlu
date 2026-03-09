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


class WeekParser(BaseParser):
    """
    Week time parser

    Handles week-related time expressions such as:
    - monday, tuesday, etc. (specific weekdays)
    - this week, last week, next week
    - weekend
    - weekday + time combinations
    """

    def __init__(self):
        """Initialize week parser"""
        super().__init__()

    def parse(self, token, base_time):  # noqa: C901
        """
        Parse week-related time expressions

        Args:
            token (dict): Time expression token containing week_day, offset_week, period, etc.
            base_time (datetime): Base time reference

        Returns:
            list: Time range list in format [[start_time_str, end_time_str]]
        """
        # Extract key information from token
        week_day_raw = token.get("week_day", "").strip('"')
        week_offset_raw = token.get("offset_week", "0").strip('"')
        week_period_raw = token.get("week_period", "").strip('"')
        time_num = self._get_time_num(token)
        # Use noon field if available, fallback to period field
        period_str = token.get("noon", "").strip('"') or token.get("period", "").strip('"')

        # Parse week offset
        try:
            week_offset_val = int(week_offset_raw)
        except (ValueError, TypeError):
            week_offset_val = 0

        # Handle week periods (weekend, weekday)
        # Note: Due to FST output format, week_period may be parsed as 'period' field
        # when the field name contains spaces (e.g., "week _ period" -> "period")
        # So we check both 'week_period' and 'period' fields
        if week_period_raw:
            return self._handle_week_period(base_time, week_period_raw, week_offset_val, period_str)
        # Fallback: if period_str is "weekend" or "weekday" and no week_day, treat as week_period
        elif (
            period_str
            and period_str.lower() in ["weekend", "weekends", "weekday", "weekdays"]
            and not week_day_raw
        ):
            return self._handle_week_period(base_time, period_str.lower(), week_offset_val, "")

        # Calculate target date
        target_date = self._calculate_target_date(base_time, week_day_raw, week_offset_val)

        # Handle comma-separated weekdays (like "5,6" for weekend)
        if target_date is None and week_day_raw and "," in week_day_raw:
            return self._handle_weekend(base_time, week_offset_val, period_str)

        # Handle whole week situation (no specific day)
        if not week_day_raw:
            return self._handle_whole_week(target_date)

        # Handle with time period (morning, afternoon, etc.)
        # Use unified _parse_period from BaseParser
        # But skip if period_str is AM/PM (handled in time_num)
        if period_str and period_str.lower() not in ["am", "pm", "a.m.", "p.m."]:
            start_time, end_time = self._parse_period(target_date, period_str)
            if start_time == end_time:
                return self._format_time_result(start_time)
            return self._format_time_result(start_time, end_time)

        # Handle with specific hour only
        if (
            time_num
            and "hour" in time_num
            and "minute" not in time_num
            and "second" not in time_num
        ):
            return self._handle_specific_hour(target_date, time_num)

        # Handle with complete time
        if time_num and "hour" in time_num:
            return self._handle_with_time(target_date, time_num)

        # Default: return full day
        return self._get_day_range_formatted(target_date)

    def _calculate_target_date(self, base_time, week_day_raw, week_offset_val):
        """
        Calculate target date based on weekday and offset
        """
        # Get current weekday (0=Monday, 6=Sunday)
        current_weekday = base_time.weekday()

        if week_day_raw:
            # Handle comma-separated weekdays (like "5,6" for weekend)
            if "," in week_day_raw:
                # This is a weekend or multi-day period - return None to handle separately
                return None
            # Handle both weekday names and numeric strings
            elif week_day_raw.isdigit():
                # Direct numeric mapping (0=monday, 1=tuesday, ..., 6=sunday)
                target_weekday = int(week_day_raw)
            else:
                # Map weekday name to number
                target_weekday = self.weekdays.get(week_day_raw.lower(), 0)
            # Calculate day difference
            # For week_offset_val = 0 (this week), use the same week's weekday
            # For week_offset_val != 0, use the specified week offset
            if week_offset_val == 0:
                # "this monday" or "monday" - use the same week's weekday
                day_diff = target_weekday - current_weekday
                # If target day has passed, it's still in the same week (negative day_diff)
            else:
                # "next monday" or "last monday" - use the specified offset
                day_diff = target_weekday - current_weekday + week_offset_val * 7
        else:
            # Default to Monday of the target week
            day_diff = -current_weekday + week_offset_val * 7

        return base_time + timedelta(days=day_diff)

    def _handle_weekend(self, base_time, week_offset_val, period_str):
        """
        Handle weekend case (Saturday and Sunday)
        """
        # Calculate the target week
        current_weekday = base_time.weekday()
        monday_offset = -current_weekday + week_offset_val * 7
        target_monday = base_time + timedelta(days=monday_offset)

        # Saturday and Sunday
        sat_date = target_monday + timedelta(days=5)
        sun_date = target_monday + timedelta(days=6)

        if period_str:
            # Weekend with time period (e.g., "weekend morning")
            sat_start, sat_end = self._parse_period(sat_date, period_str)
            sun_start, sun_end = self._parse_period(sun_date, period_str)
            return [
                self._format_time_result(sat_start, sat_end)[0],
                self._format_time_result(sun_start, sun_end)[0],
            ]
        else:
            # Normal weekend full days
            start_date, _ = self._get_day_range(sat_date)
            _, end_date = self._get_day_range(sun_date)
            return self._format_time_result(start_date, end_date)

    def _handle_whole_week(self, target_date):
        """
        Handle whole week situation, return Monday to Sunday
        """
        # target_date should already be Monday of the target week
        start_date, _ = self._get_day_range(target_date)
        end_date = target_date + timedelta(days=6)
        _, end_date = self._get_day_range(end_date)
        return self._format_time_result(start_date, end_date)

    def _handle_week_period(self, base_time, week_period, week_offset_val, period_str):
        """
        Handle week periods like weekend, weekday
        """
        # Calculate the target week
        current_weekday = base_time.weekday()
        monday_offset = -current_weekday + week_offset_val * 7
        target_monday = base_time + timedelta(days=monday_offset)

        if week_period in ["weekend", "weekends"]:
            # Saturday and Sunday
            sat_date = target_monday + timedelta(days=5)
            sun_date = target_monday + timedelta(days=6)

            if period_str:
                # Weekend afternoon, etc.
                sat_start, sat_end = self._parse_period(sat_date, period_str)
                sun_start, sun_end = self._parse_period(sun_date, period_str)
                return [
                    self._format_time_result(sat_start, sat_end)[0],
                    self._format_time_result(sun_start, sun_end)[0],
                ]
            else:
                # Normal weekend full days
                start_date, _ = self._get_day_range(sat_date)
                _, end_date = self._get_day_range(sun_date)
                return self._format_time_result(start_date, end_date)

        elif week_period in ["weekday", "weekdays"]:
            # Monday to Friday
            start_date, _ = self._get_day_range(target_monday)
            fri_date = target_monday + timedelta(days=4)
            _, end_date = self._get_day_range(fri_date)
            return self._format_time_result(start_date, end_date)

        elif week_period in ["weekbeginning"]:
            # Monday 00:00:00 to Tuesday 23:59:59
            mon_date = target_monday
            tue_date = target_monday + timedelta(days=1)

            if period_str:
                # Week beginning afternoon, etc.
                mon_start, mon_end = self._parse_period(mon_date, period_str)
                tue_start, tue_end = self._parse_period(tue_date, period_str)
                return [
                    self._format_time_result(mon_start, mon_end)[0],
                    self._format_time_result(tue_start, tue_end)[0],
                ]
            else:
                # Normal week beginning: Monday 00:00:00 to Tuesday 23:59:59
                start_date, _ = self._get_day_range(mon_date)
                _, end_date = self._get_day_range(tue_date)
                return self._format_time_result(start_date, end_date)

        # Default: treat as whole week
        return self._handle_whole_week(target_monday)

    def _handle_specific_hour(self, base_time, time_num):
        """
        Handle specific hour only
        """
        hour = time_num.get("hour", 0)
        # Handle AM/PM period
        period = time_num.get("period", "").strip('"').lower()
        if period in ["pm", "p.m."] and hour < 12:
            hour += 12
        elif period in ["am", "a.m."] and hour == 12:
            hour = 0

        start_of_hour = base_time.replace(hour=hour, minute=0, second=0, microsecond=0)
        return self._format_time_result(start_of_hour)

    def _handle_with_time(self, base_time, time_num):
        """
        Handle with complete time (hour and minute)
        """
        hour = int(time_num.get("hour", 0))
        minute = int(time_num.get("minute", 0))

        # Handle AM/PM period
        period = time_num.get("period", "").strip('"').lower()
        if period in ["pm", "p.m."] and hour < 12:
            hour += 12
        elif period in ["am", "a.m."] and hour == 12:
            hour = 0

        target_time = base_time.replace(hour=hour, minute=minute, second=0, microsecond=0)
        return self._format_time_result(target_time)

    def _get_day_range_formatted(self, target_date):
        """
        Get and format start and end times of a day
        """
        start_of_day, end_of_day = self._get_day_range(target_date)
        return self._format_time_result(start_of_day, end_of_day)
