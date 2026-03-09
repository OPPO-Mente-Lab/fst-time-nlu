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
from .base_parser import BaseParser
from ...core.logger import get_logger


class UTCTimeParser(BaseParser):
    """
    UTC time parser for English absolute time expressions

    Handles various absolute time formats like:
    - "January 15, 2025 at 3:30 PM"
    - "the fifth of March"
    - "twenty twenty"
    - "three thirty pm"
    """

    def __init__(self):
        """Initialize UTC time parser"""
        super().__init__()
        self.logger = get_logger(__name__)

    def parse(self, token, base_time):
        """
        Parse UTC time expression

        Args:
            token (dict): Time expression token
            base_time (datetime): Base time reference

        Returns:
            list: Time range list in format [[start_time_str, end_time_str]]
        """
        if not isinstance(base_time, datetime):
            base_time = datetime.fromisoformat(base_time.replace("Z", "+00:00"))

        # Handle time_period tokens (from PeriodRule)
        # These tokens contain month_period and month attributes
        if token.get("month_period") and token.get("month"):
            time_num = self._get_time_num(token)
            if time_num:
                month_period = token.get("month_period")
                return self._handle_month_period(base_time, time_num, month_period)
            return []

        # Extract time components
        time_num = self._get_time_num(token)

        # If time_num is empty (due to validation failure), return empty result
        if not time_num:
            return []

        period = token.get("period")
        noon = token.get("noon")  # Handle period + time combinations like "noon 12 o'clock"
        month_period = token.get("month_period")  # Handle early/mid/late month expressions

        # Apply basic time fields
        base_time = self._set_time_num(base_time, time_num)

        # Handle month period (early/mid/late month)
        if month_period and "month" in time_num:
            return self._handle_month_period(base_time, time_num, month_period)

        # Handle "X past noon/midnight" patterns (highest priority)
        if period and ("minute" in time_num or "hour" in time_num):
            result = self._handle_past_period_time(base_time, time_num, period)
            if result:
                return result

        # Handle period + time combinations (noon 12 o'clock, morning 8 am, etc.)
        if noon and ("hour" in time_num or "minute" in time_num):
            return self._handle_noon_with_time(base_time, time_num, noon)

        # Handle time period (AM/PM)
        if period:
            return self._handle_time_with_period(base_time, time_num, period)

        # Handle date and/or time
        return self._handle_utc_datetime(base_time, time_num)

    def _handle_time_with_period(self, base_time, time_num, period):
        """
        Handle time with AM/PM period

        Args:
            base_time (datetime): Base time reference
            time_num (dict): Time number dictionary
            period (str): Time period (am/pm/a.m./p.m.)

        Returns:
            list: Time range list
        """
        if "hour" in time_num:
            hour = time_num["hour"]
            minute = time_num.get("minute", 0)
            second = time_num.get("second", 0)

            # Convert 12-hour to 24-hour format
            hour, minute = self._convert_12_to_24_hour(hour, minute, period)

            # Check if date fields are present in time_num
            year = time_num.get("year", base_time.year)
            month = time_num.get("month", base_time.month)
            day = time_num.get("day", base_time.day)

            try:
                # Handle 24:00 case (convert to next day 0:00)
                if hour == 24:
                    from datetime import timedelta

                    result_time = base_time.replace(
                        year=year,
                        month=month,
                        day=day,
                        hour=0,
                        minute=minute,
                        second=second,
                    )
                    result_time = result_time + timedelta(days=1)
                else:
                    result_time = base_time.replace(
                        year=year,
                        month=month,
                        day=day,
                        hour=hour,
                        minute=minute,
                        second=second,
                    )
                return self._format_time_result(result_time)
            except ValueError:
                # Invalid time combination
                return []

        # Only period without time
        return self._handle_time_period_only(base_time, period)

    def _handle_past_period_time(self, base_time, time_num, period):
        """
        Handle "X past noon/midnight" patterns
        e.g. "15 past noon" -> 12:15
        e.g. "a quarter past noon" -> 12:15

        Args:
            base_time (datetime): Base time reference
            time_num (dict): Time number dictionary
            period (str): Time period (noon/midnight)

        Returns:
            list: Time range list or empty list if not applicable
        """
        period_lower = period.lower()

        # Only handle noon/midnight with minute component
        if period_lower in ["noon", "midnight"] and "minute" in time_num:
            minute = time_num["minute"]

            # Get date components
            year = time_num.get("year", base_time.year)
            month = time_num.get("month", base_time.month)
            day = time_num.get("day", base_time.day)

            try:
                if period_lower == "noon":
                    # noon = 12:00, add minutes
                    target_time = base_time.replace(
                        year=year,
                        month=month,
                        day=day,
                        hour=12,
                        minute=minute,
                        second=0,
                        microsecond=0,
                    )
                elif period_lower == "midnight":
                    # midnight = 00:00, add minutes
                    target_time = base_time.replace(
                        year=year,
                        month=month,
                        day=day,
                        hour=0,
                        minute=minute,
                        second=0,
                        microsecond=0,
                    )

                return self._format_time_result(target_time)
            except ValueError:
                # Invalid time combination
                return []

        # Not a past period pattern, return empty to continue with other handlers
        return []

    def _handle_time_period_only(self, base_time, period):
        """
        Handle only time period without specific time

        Args:
            base_time (datetime): Base time reference
            period (str): Time period string

        Returns:
            list: Time range list
        """
        period_lower = period.lower().replace(".", "")

        if period_lower in ["am", "a.m.", "morning"]:
            start = base_time.replace(hour=6, minute=0, second=0)
            end = base_time.replace(hour=11, minute=59, second=59)
            return self._format_time_result(start, end)
        elif period_lower in ["pm", "p.m.", "afternoon", "evening"]:
            start = base_time.replace(hour=12, minute=0, second=0)
            end = base_time.replace(hour=23, minute=59, second=59)
            return self._format_time_result(start, end)
        elif period_lower in ["noon", "midday"]:
            result = base_time.replace(hour=12, minute=0, second=0)
            return self._format_time_result(result)
        elif period_lower in ["midnight"]:
            result = base_time.replace(hour=0, minute=0, second=0)
            return self._format_time_result(result)

        return []

    def _handle_noon_with_time(self, base_time, time_num, noon):
        """
        Handle period + time combinations like "noon 12 o'clock", "morning 8 am"

        Args:
            base_time (datetime): Base time reference
            time_num (dict): Time number dictionary
            noon (str): Period string (noon, morning, afternoon, etc.)

        Returns:
            list: Time range list
        """
        if "hour" in time_num:
            hour = time_num["hour"]
            minute = time_num.get("minute", 0)
            second = time_num.get("second", 0)

            # Handle period-specific time adjustments (similar to Chinese FST)
            noon_lower = noon.lower()

            # For afternoon/evening/night periods, if hour < 12, add 12 hours
            # Note: hour == 12 should remain as 12 (12:15 in the afternoon = 12:15, not 00:15)
            if noon_lower in ["afternoon", "evening", "night", "tonight"] and hour < 12:
                hour += 12
                if hour >= 24:
                    hour -= 24
                    base_time = base_time + timedelta(days=1)

            # For noon/midday, if hour < 12, add 12 hours
            elif noon_lower in ["noon", "midday"] and hour < 12:
                hour += 12

            # For morning, keep hour as is (no adjustment needed)
            # Morning is typically 6am-12pm, so hour values 1-12 are correct
            # No special handling needed for morning

            try:
                result_time = base_time.replace(hour=hour, minute=minute, second=second)
                return self._format_time_result(result_time)
            except ValueError:
                return []

        return []

    def _handle_utc_datetime(self, base_time, time_num):
        """
        Handle UTC datetime (date and/or time components)

        Args:
            base_time (datetime): Base time reference
            time_num (dict): Time number dictionary

        Returns:
            list: Time range list
        """
        has_date = "year" in time_num or "month" in time_num or "day" in time_num
        has_time = "hour" in time_num or "minute" in time_num or "second" in time_num

        if has_date and has_time:
            return self._handle_full_datetime(base_time, time_num)
        elif has_date:
            return self._handle_date_only(base_time, time_num)
        elif has_time:
            return self._handle_time_only(base_time, time_num)

        return []

    def _handle_date_only(self, base_time, time_num):
        """
        Handle date-only expressions

        Args:
            base_time (datetime): Base time reference
            time_num (dict): Time number dictionary

        Returns:
            list: Time range list
        """
        try:
            # Year only
            if "year" in time_num and "month" not in time_num and "day" not in time_num:
                year_suffix = time_num.get("year_suffix")
                year = self._normalize_year(time_num["year"], year_suffix)
                start_of_year, end_of_year = self._get_year_range(base_time, year)
                return self._format_time_result(start_of_year, end_of_year)

            # Year + Month
            if "year" in time_num and "month" in time_num and "day" not in time_num:
                year_suffix = time_num.get("year_suffix")
                year = self._normalize_year(time_num["year"], year_suffix)
                month = time_num["month"]
                target_date = base_time.replace(year=year, month=month, day=1)
                start_of_month, end_of_month = self._get_month_range(target_date, month)
                return self._format_time_result(start_of_month, end_of_month)

            # Month only
            if "month" in time_num and "day" not in time_num and "year" not in time_num:
                month = time_num["month"]
                start_of_month, end_of_month = self._get_month_range(base_time, month)
                return self._format_time_result(start_of_month, end_of_month)

            # Day only (current month)
            if "day" in time_num and "month" not in time_num and "year" not in time_num:
                day = time_num["day"]
                target_date = base_time.replace(day=day)
                start_of_day, end_of_day = self._get_day_range(target_date)
                return self._format_time_result(start_of_day, end_of_day)

            # Month + Day (current year)
            if "month" in time_num and "day" in time_num and "year" not in time_num:
                month = time_num["month"]
                day = time_num["day"]
                target_date = base_time.replace(month=month, day=day)
                start_of_day, end_of_day = self._get_day_range(target_date)
                return self._format_time_result(start_of_day, end_of_day)

            # Year + Month + Day
            if "year" in time_num and "month" in time_num and "day" in time_num:
                year_suffix = time_num.get("year_suffix")
                year = self._normalize_year(time_num["year"], year_suffix)
                month = time_num["month"]
                day = time_num["day"]
                target_date = base_time.replace(year=year, month=month, day=day)
                start_of_day, end_of_day = self._get_day_range(target_date)
                return self._format_time_result(start_of_day, end_of_day)

        except ValueError as e:
            # Handle invalid date combinations
            self.logger.debug(f"Error parsing date: {e}")
            return []

        return []

    def _handle_time_only(self, base_time, time_num):
        """
        Handle time-only expressions

        Args:
            base_time (datetime): Base time reference
            time_num (dict): Time number dictionary

        Returns:
            list: Time range list
        """
        hour = time_num.get("hour", base_time.hour)
        minute = time_num.get("minute", 0)
        second = time_num.get("second", 0)

        try:
            result_time = base_time.replace(hour=hour, minute=minute, second=second)
            return self._format_time_result(result_time)
        except ValueError as e:
            self.logger.debug(f"Error parsing time: {e}")
            return []

    def _handle_full_datetime(self, base_time, time_num):
        """
        Handle full datetime (both date and time components)

        Args:
            base_time (datetime): Base time reference
            time_num (dict): Time number dictionary

        Returns:
            list: Time range list
        """
        try:
            # Build date component
            if "year" in time_num:
                year_suffix = time_num.get("year_suffix")
                year = self._normalize_year(time_num["year"], year_suffix)
            else:
                year = base_time.year
            month = time_num.get("month", base_time.month)
            day = time_num.get("day", base_time.day)

            # Build time component
            hour = time_num.get("hour", 0)
            minute = time_num.get("minute", 0)
            second = time_num.get("second", 0)

            result_time = base_time.replace(
                year=year, month=month, day=day, hour=hour, minute=minute, second=second
            )
            return self._format_time_result(result_time)

        except ValueError as e:
            self.logger.debug(f"Error parsing full datetime: {e}")
            return []

    def _normalize_year(self, year, year_suffix=None):
        """
        Normalize year to 4-digit format with BC/AD suffix handling

        Args:
            year (int): Year value
            year_suffix (str): Year suffix (BC, AD, BCE, CE)

        Returns:
            int: Normalized year (negative for BC/BCE, positive for AD/CE)
        """
        if year < 100:
            # Two-digit year: assume 20xx for 00-29, 19xx for 30-99
            if year <= 29:
                normalized_year = 2000 + year
            else:
                normalized_year = 1900 + year
        else:
            normalized_year = year

        # Handle BC/AD suffix
        if year_suffix:
            suffix_upper = year_suffix.upper()
            if suffix_upper in ["BC", "B.C.", "BCE"]:
                # BC/BCE: return negative year
                return -normalized_year
            elif suffix_upper in ["AD", "A.D.", "CE"]:
                # AD/CE: return positive year (default)
                return normalized_year

        return normalized_year

    def _get_time_num(self, token):  # noqa: C901
        """
        Extract time numbers from token

        Args:
            token (dict): Time expression token

        Returns:
            dict: Time number dictionary
        """
        time_num = {}

        # Parse year
        if "year" in token:
            year_str = str(token["year"]).strip()
            year = self._parse_number(year_str)
            if year is not None:
                time_num["year"] = year

        # Parse year suffix (BC/AD)
        if "year_suffix" in token:
            year_suffix = str(token["year_suffix"]).strip()
            time_num["year_suffix"] = year_suffix

        # Parse year offset (next year, last year, etc.)
        if "offset_year" in token:
            offset_year_str = str(token["offset_year"]).strip()
            # Handle negative numbers directly since convert_english_number doesn't support them
            if offset_year_str.startswith("-"):
                try:
                    time_num["offset_year"] = int(offset_year_str)
                except ValueError:
                    pass
            else:
                offset_year = self._parse_number(offset_year_str)
                if offset_year is not None:
                    time_num["offset_year"] = offset_year

        # Parse month
        if "month" in token:
            month_str = str(token["month"]).strip()
            month = self._parse_month(month_str)
            if month is not None:
                time_num["month"] = month

        # Parse day
        if "day" in token:
            day_str = str(token["day"]).strip()
            day = self._parse_day(day_str)
            if day is not None:
                time_num["day"] = day

        # Parse hour
        if "hour" in token:
            hour_str = str(token["hour"]).strip()
            hour = self._parse_number(hour_str)
            if hour is not None:
                # Validate hour range (0-23)
                if 0 <= hour <= 23:
                    time_num["hour"] = hour
                else:
                    # Hour out of range, return empty result
                    return {}

        # Parse minute
        if "minute" in token:
            minute_str = str(token["minute"]).strip()
            minute = self._parse_number(minute_str)
            if minute is not None:
                # Validate minute range (0-59)
                if 0 <= minute <= 59:
                    time_num["minute"] = minute
                else:
                    # Minute out of range, return empty result
                    return {}

        # Parse second
        if "second" in token:
            second_str = str(token["second"]).strip()
            second = self._parse_number(second_str)
            if second is not None:
                # Validate second range (0-59)
                if 0 <= second <= 59:
                    time_num["second"] = second
                else:
                    # Second out of range, return empty result
                    return {}

        return time_num

    def _set_time_num(self, base_time, time_num):
        """
        Apply time numbers to base time (placeholder, actual setting done in handlers)

        Args:
            base_time (datetime): Base time reference
            time_num (dict): Time number dictionary

        Returns:
            datetime: Updated base time
        """
        # This is a placeholder - actual time setting is done in specific handlers
        return base_time

    def _parse_month(self, month_str):
        """
        Parse month from string

        Args:
            month_str (str): Month string (name or number)

        Returns:
            int or None: Month number (1-12) or None if parsing fails
        """
        if not month_str:
            return None

        month_str = str(month_str).lower().strip()

        # Try direct number
        if month_str.isdigit():
            month = int(month_str)
            return month if 1 <= month <= 12 else None

        # Try month names
        return self.months.get(month_str)

    def _parse_day(self, day_str):
        """
        Parse day from string

        Args:
            day_str (str): Day string (number or ordinal)

        Returns:
            int or None: Day number (1-31) or None if parsing fails
        """
        if not day_str:
            return None

        day_str = str(day_str).strip()

        # Try direct number
        if day_str.isdigit():
            day = int(day_str)
            return day if 1 <= day <= 31 else None

        # Try ordinal
        day = self._parse_ordinal(day_str)
        return day if day and 1 <= day <= 31 else None

    def _convert_12_to_24_hour(self, hour, minute, period):
        """
        Convert 12-hour format to 24-hour format

        Args:
            hour (int): Hour in 12-hour format
            minute (int): Minute
            period (str): AM/PM indicator

        Returns:
            tuple: (hour, minute) in 24-hour format
        """
        period_lower = period.lower().replace(".", "")

        if period_lower in ["am", "a.m."]:
            if hour == 12:
                hour = 0  # 12am = midnight (0:00)
        elif period_lower in ["pm", "p.m."]:
            if hour == 12:
                hour = 12  # 12pm = noon (12:00), not 24:00
            else:
                hour += 12  # 1pm = 13:00, 2pm = 14:00, etc.

        return hour, minute

    def _handle_month_period(self, base_time, time_num, month_period):
        """
        Handle early/mid/late month expressions

        Following Chinese FST implementation for month periods:
        - earlymonth: 1st to 10th
        - midmonth: 11th to 20th
        - latemonth: 21st to end of month

        Args:
            base_time (datetime): Base time reference
            time_num (dict): Time number dictionary
            month_period (str): Month period identifier (earlymonth/midmonth/latemonth)

        Returns:
            list: Time range list
        """
        try:
            # Get year and month
            year = time_num.get("year", base_time.year)
            if "year" in time_num:
                year_suffix = time_num.get("year_suffix")
                year = self._normalize_year(year, year_suffix)

            # Handle year offset (from year_prefix like "next year", "last year")
            offset_year = time_num.get("offset_year")
            if offset_year is not None:
                year_offset = int(offset_year)
                year = base_time.year + year_offset

            month = time_num["month"]

            # Create target date for the month
            target_time = base_time.replace(year=year, month=month, day=1)

            # Apply month period ranges
            if month_period == "earlymonth":
                # Early month: 1st to 10th
                start_time = target_time.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                end_time = target_time.replace(day=10, hour=23, minute=59, second=59, microsecond=0)
            elif month_period == "midmonth":
                # Mid month: 11th to 20th
                start_time = target_time.replace(day=11, hour=0, minute=0, second=0, microsecond=0)
                end_time = target_time.replace(day=20, hour=23, minute=59, second=59, microsecond=0)
            elif month_period == "latemonth":
                # Late month: 21st to end of month
                start_time = target_time.replace(day=21, hour=0, minute=0, second=0, microsecond=0)
                # Get the last day of the month
                _, end_of_month = self._get_month_range(target_time, month)
                end_time = end_of_month
            else:
                return []

            return self._format_time_result(start_time, end_time)

        except Exception as e:
            self.logger.debug(f"Error in _handle_month_period: {e}")
            return []
