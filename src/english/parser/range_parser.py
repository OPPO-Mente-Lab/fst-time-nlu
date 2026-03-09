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

from datetime import timedelta, datetime
from .base_parser import BaseParser


class RangeParser(BaseParser):
    """
    Time range expression parser for English

    Handles explicit time range expressions like:
    - "8 to 10 o'clock" (hour range)
    - "8 to 10" (hour range)
    """

    def __init__(self):
        """Initialize range parser"""
        super().__init__()

    def parse(self, token, base_time):  # noqa: C901
        """
        Parse time/date range expression

        Args:
            token (dict): Time/date expression token containing:
                         - For time ranges: start/end hour/minute fields, optional period (AM/PM) field, optional weekday field
                         - For date ranges: start/end day fields, month field
            base_time (datetime): Base time reference

        Returns:
            list: Time/date range list in format [[start_time_str, end_time_str]]
        """
        # Check if this is a UTC time range (has start_year, start_month, start_day fields)
        start_year_str = token.get("start_year", "").strip('"')
        start_month_str = token.get("start_month", "").strip('"')
        start_day_str = token.get("start_day", "").strip('"')
        end_year_str = token.get("end_year", "").strip('"')
        end_month_str = token.get("end_month", "").strip('"')
        end_day_str = token.get("end_day", "").strip('"')

        if (
            start_year_str
            and start_month_str
            and start_day_str
            and end_year_str
            and end_month_str
            and end_day_str
        ):
            return self._parse_utc_time_range(token, base_time)

        # Check if this is a date range (has month and day fields)
        month_str = token.get("month", "").strip('"')
        start_day_str = token.get("start_day", "").strip('"')
        end_day_str = token.get("end_day", "").strip('"')
        date_month_str = token.get("date_month", "").strip(
            '"'
        )  # For single hyphen date like "2-15"
        date_day_str = token.get("date_day", "").strip('"')  # For single hyphen date like "2-15"

        # Check for year modifiers (offset_year)
        start_offset_year = token.get("start_offset_year", "").strip('"')
        end_offset_year = token.get("end_offset_year", "").strip('"')
        offset_year = token.get("offset_year", "").strip('"')

        # If only one side has offset_year, apply it to both sides
        if start_offset_year and not end_offset_year:
            end_offset_year = start_offset_year
        elif end_offset_year and not start_offset_year:
            start_offset_year = end_offset_year
        elif offset_year and not start_offset_year and not end_offset_year:
            # Single offset_year applies to both sides
            start_offset_year = offset_year
            end_offset_year = offset_year

        if (month_str and start_day_str and end_day_str) or (
            token.get("start_month") and token.get("start_day") and token.get("end_day")
        ):
            return self._parse_date_range(token, base_time)
        elif date_month_str and date_day_str and not start_day_str and not end_day_str:
            # Single hyphen date like "2-15" (month-day)
            return self._parse_single_hyphen_date(token, base_time)

        # Otherwise, parse as time range
        start_hour_str = token.get("start_hour", "").strip('"')
        end_hour_str = token.get("end_hour", "").strip('"')

        if not start_hour_str or not end_hour_str:
            return []

        try:
            # Parse hours and minutes (handle both digits and words)
            start_hour = self._parse_hour(start_hour_str)
            end_hour = self._parse_hour(end_hour_str)

            # Parse minutes (default to 0 if not specified)
            start_minute_str = token.get("start_minute", "0").strip('"')
            end_minute_str = token.get("end_minute", "0").strip('"')
            start_minute = int(start_minute_str)
            end_minute = int(end_minute_str)

            # Parse seconds (default to 0 if not specified)
            start_second_str = token.get("start_second", "0").strip('"')
            end_second_str = token.get("end_second", "0").strip('"')
            start_second = int(start_second_str)
            end_second = int(end_second_str)

            # Handle AM/PM period
            # 首先检查是否有独立的 start_period 和 end_period（新的通用连字符模式）
            start_period = token.get("start_period", "").strip('"').lower()
            end_period = token.get("end_period", "").strip('"').lower()

            # 如果没有独立的period，检查是否有共享的period（旧模式）
            if not start_period and not end_period:
                period_raw = token.get("period", "").strip('"').lower()
                norm_period = period_raw.replace(".", "").replace(" ", "")
                if norm_period:
                    if norm_period == "pm" and start_hour > end_hour:
                        start_period = "am"
                        end_period = "pm"
                    else:
                        start_period = norm_period
                        end_period = norm_period
                else:
                    start_period = period_raw
                    end_period = period_raw

            # AM/PM继承逻辑：如果只有一侧有AM/PM，另一侧继承
            if not start_period and end_period:
                start_period = end_period
            elif start_period and not end_period:
                end_period = start_period

            # 应用AM/PM到起始时间
            if start_period in ["pm", "p.m.", "p m"]:
                if start_hour != 12:
                    start_hour += 12
            elif start_period in ["am", "a.m.", "a m"]:
                if start_hour == 12:
                    start_hour = 0

            # 应用AM/PM到结束时间
            if end_period in ["pm", "p.m.", "p m"]:
                if end_hour != 12:
                    end_hour += 12
            elif end_period in ["am", "a.m.", "a m"]:
                if end_hour == 12:
                    end_hour = 0

            # Handle weekday if present
            weekday_str = token.get("weekday", "").strip('"').lower()
            target_date = base_time
            if weekday_str:
                weekday_map = {
                    "monday": 0,
                    "tuesday": 1,
                    "wednesday": 2,
                    "thursday": 3,
                    "friday": 4,
                    "saturday": 5,
                    "sunday": 6,
                }
                if weekday_str in weekday_map:
                    target_weekday = weekday_map[weekday_str]
                    days_ahead = target_weekday - base_time.weekday()
                    if days_ahead < 0:
                        days_ahead += 7
                    target_date = base_time + timedelta(days=days_ahead)

            # Create start and end times on the target date
            start_time = target_date.replace(
                hour=start_hour, minute=start_minute, second=start_second, microsecond=0
            )
            end_time = target_date.replace(
                hour=end_hour, minute=end_minute, second=end_second, microsecond=0
            )

            # Handle cases where end_time might be on the next day
            if end_time <= start_time:
                end_time = end_time + timedelta(days=1)

            # Note: For hyphen time ranges like "9-11am",
            # the end time should be interpreted as the actual end time
            # e.g., "9-11am" means 9:00-11:00, not 9:00-12:00
            # The previous logic that added 1 hour was incorrect

            return self._format_time_result(start_time, end_time)

        except (ValueError, TypeError):
            return []

    def _parse_date_range(self, token, base_time):  # noqa: C901
        """
        Parse date range expression

        Args:
            token (dict): Date range token containing month/start_month, start_day, end_day fields
            base_time (datetime): Base time reference

        Returns:
            list: Date range list in format [[start_date_str, end_date_str]]
        """
        try:
            # 支持两种字段名：month 或 start_month
            month_str = token.get("month", "").strip('"').lower()
            if not month_str:
                month_str = token.get("start_month", "").strip('"').lower()

            # 支持 end_month 字段
            end_month_str = token.get("end_month", "").strip('"').lower()
            if not end_month_str:
                end_month_str = month_str  # 如果没有 end_month，使用 start_month

            start_day_str = token.get("start_day", "").strip('"')
            end_day_str = token.get("end_day", "").strip('"')

            # 支持直接的year字段（start_year和end_year）
            start_year_str = token.get("start_year", "").strip('"')
            end_year_str = token.get("end_year", "").strip('"')

            # Handle year modifiers from FST tags
            start_modifier = token.get("start_modifier", "").strip('"')
            end_modifier = token.get("end_modifier", "").strip('"')
            start_offset_year = token.get("start_offset_year", "").strip('"')
            end_offset_year = token.get("end_offset_year", "").strip('"')
            offset_year = token.get("offset_year", "").strip('"')

            # Parse modifiers to get year offsets
            if start_modifier:
                start_offset_year = start_modifier
            if end_modifier:
                end_offset_year = end_modifier

            # If only one side has offset_year, apply it to both sides
            if start_offset_year and not end_offset_year:
                end_offset_year = start_offset_year
            elif end_offset_year and not start_offset_year:
                start_offset_year = end_offset_year
            elif offset_year and not start_offset_year and not end_offset_year:
                # Single offset_year applies to both sides
                start_offset_year = offset_year
                end_offset_year = offset_year

            # Parse days (handle ordinals like "23rd", "26th")
            start_day = self._parse_day_number(start_day_str)
            end_day = self._parse_day_number(end_day_str)

            # Month name to number mapping (full names and abbreviations)
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
                # Month abbreviations
                "jan": 1,
                "feb": 2,
                "mar": 3,
                "apr": 4,
                "may": 5,
                "jun": 6,
                "jul": 7,
                "aug": 8,
                "sep": 9,
                "oct": 10,
                "nov": 11,
                "dec": 12,
            }

            if month_str not in month_map or end_month_str not in month_map:
                return []

            start_month_num = month_map[month_str]
            end_month_num = month_map[end_month_str]

            # Apply year: 优先使用直接的year字段，如果没有则使用modifier
            start_year = base_time.year
            end_year = base_time.year

            # 如果token中有直接的year字段，使用它们
            if start_year_str:
                try:
                    start_year = int(start_year_str)
                except (ValueError, TypeError):
                    pass
            elif start_offset_year:
                year_offset = self._parse_year_offset(start_offset_year)
                start_year += year_offset

            if end_year_str:
                try:
                    end_year = int(end_year_str)
                except (ValueError, TypeError):
                    pass
            elif end_offset_year:
                year_offset = self._parse_year_offset(end_offset_year)
                end_year += year_offset

            # Create start and end dates
            start_date = datetime(start_year, start_month_num, start_day, 0, 0, 0)
            end_date = datetime(end_year, end_month_num, end_day, 23, 59, 59)

            # Handle cases where the range might span to next year
            if end_date < start_date:
                end_date = datetime(end_year + 1, end_month_num, end_day, 23, 59, 59)

            return [
                [
                    start_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    end_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
                ]
            ]

        except (ValueError, TypeError):
            return []

    def _parse_single_hyphen_date(self, token, base_time):
        """
        Parse single hyphen date like "2-15" (month-day)

        Args:
            token (dict): Date token containing month and day fields
            base_time (datetime): Base time reference

        Returns:
            list: Date list in format [[date_str, date_str]]
        """
        try:
            month_str = token.get("date_month", "").strip('"')
            day_str = token.get("date_day", "").strip('"')

            # Parse month and day
            month_num = int(month_str)
            day_num = int(day_str)

            # Use base_time's year
            year = base_time.year

            # Create date
            target_date = datetime(year, month_num, day_num, 0, 0, 0)

            # Return as a single day range (start and end of the same day)
            start_time = target_date
            end_time = target_date.replace(hour=23, minute=59, second=59)

            return [
                [
                    start_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    end_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                ]
            ]

        except (ValueError, TypeError):
            return []

    def _parse_day_number(self, day_str):
        """
        Parse day number from string (handle ordinals like "23rd", "26th")

        Args:
            day_str (str): Day string (e.g., "23", "23rd", "26th")

        Returns:
            int: Day as integer
        """
        # Remove ordinal suffixes (st, nd, rd, th)
        import re

        day_clean = re.sub(r"(st|nd|rd|th)$", "", day_str.lower())
        return int(day_clean)

    def _parse_hour(self, hour_str):
        """
        Parse hour from string (digit or word)

        Args:
            hour_str (str): Hour string (e.g., "3", "six", "12")

        Returns:
            int: Hour as integer
        """
        # Word to number mapping
        word_map = {
            "one": 1,
            "two": 2,
            "three": 3,
            "four": 4,
            "five": 5,
            "six": 6,
            "seven": 7,
            "eight": 8,
            "nine": 9,
            "ten": 10,
            "eleven": 11,
            "twelve": 12,
        }

        hour_str_lower = hour_str.lower()
        if hour_str_lower in word_map:
            return word_map[hour_str_lower]
        else:
            return int(hour_str)

    def _parse_utc_time_range(self, token, base_time):
        """
        Parse UTC time range expression

        Args:
            token (dict): UTC time range token containing start_* and end_* fields
            base_time (datetime): Base time reference

        Returns:
            list: Time range list in format [[start_time_str, end_time_str]]
        """
        try:
            # Parse start time
            start_year = int(token.get("start_year", str(base_time.year)).strip('"'))
            start_month_str = token.get("start_month", "1").strip('"')
            start_day = int(token.get("start_day", "1").strip('"'))
            start_hour = int(token.get("start_hour", "0").strip('"'))
            start_minute = int(token.get("start_minute", "0").strip('"'))
            start_second = int(token.get("start_second", "0").strip('"'))

            # Parse end time
            end_year = int(token.get("end_year", str(base_time.year)).strip('"'))
            end_month_str = token.get("end_month", "").strip('"')
            if not end_month_str:  # 如果没有end_month，直接使用start_month
                end_month_str = start_month_str
            end_day = int(token.get("end_day", "1").strip('"'))
            end_hour = int(token.get("end_hour", "23").strip('"'))
            end_minute = int(token.get("end_minute", "59").strip('"'))
            end_second = int(token.get("end_second", "59").strip('"'))

            # Convert month names to numbers
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
                "jan": 1,
                "feb": 2,
                "mar": 3,
                "apr": 4,
                "may": 5,
                "jun": 6,
                "jul": 7,
                "aug": 8,
                "sep": 9,
                "oct": 10,
                "nov": 11,
                "dec": 12,
            }

            # 安全地转换月份名称到数字
            if start_month_str.lower() in month_map:
                start_month = month_map[start_month_str.lower()]
            else:
                start_month = int(start_month_str)

            if end_month_str.lower() in month_map:
                end_month = month_map[end_month_str.lower()]
            else:
                end_month = int(end_month_str)

            # Create datetime objects
            start_time = datetime(
                start_year,
                start_month,
                start_day,
                start_hour,
                start_minute,
                start_second,
            )
            end_time = datetime(end_year, end_month, end_day, end_hour, end_minute, end_second)

            # If only date is specified (no time), extend to end of day
            if not token.get("start_hour") and not token.get("start_minute"):
                start_time = start_time.replace(hour=0, minute=0, second=0)
            if not token.get("end_hour") and not token.get("end_minute"):
                end_time = end_time.replace(hour=23, minute=59, second=59)

            return self._format_time_result(start_time, end_time)

        except Exception:
            return []

    def _parse_month_day_range(self, token, base_time):
        """
        Parse Month Day - [Month] Day format
        Examples:
        - "July 13-15" → start_month: "july", start_day: "13", end_day: "15"
        - "July 13 - August 15" → start_month: "july", start_day: "13", end_month: "august", end_day: "15"
        """
        try:
            # Parse start month and day
            start_month_str = token.get("start_month", "").strip('"').lower()
            start_day_str = token.get("start_day", "").strip('"')
            start_day = int(start_day_str)

            # Parse end month and day
            end_month_str = (
                token.get("end_month", start_month_str).strip('"').lower()
            )  # 如果没有end_month，继承start_month
            end_day_str = token.get("end_day", "").strip('"')
            end_day = int(end_day_str)

            # Convert month names to numbers
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
                "jan": 1,
                "feb": 2,
                "mar": 3,
                "apr": 4,
                "may": 5,
                "jun": 6,
                "jul": 7,
                "aug": 8,
                "sep": 9,
                "oct": 10,
                "nov": 11,
                "dec": 12,
            }

            start_month = month_map.get(start_month_str, 1)
            end_month = month_map.get(end_month_str, start_month)

            # Use base_time year
            year = base_time.year

            # Create datetime objects
            start_time = datetime(year, start_month, start_day, 0, 0, 0)
            end_time = datetime(year, end_month, end_day, 23, 59, 59)

            return self._format_time_result(start_time, end_time)

        except (ValueError, TypeError):
            return []

    def _parse_year_offset(self, offset_str):
        """
        Parse year offset string (e.g., "last year" -> -1, "this year" -> 0, "next year" -> 1)

        Args:
            offset_str (str): Year offset string

        Returns:
            int: Year offset value
        """
        offset_str = offset_str.lower().strip()

        if offset_str in ["last year", "last"]:
            return -1
        elif offset_str in ["this year", "this"]:
            return 0
        elif offset_str in ["next year", "next"]:
            return 1
        else:
            # Try to parse as integer
            try:
                return int(offset_str)
            except ValueError:
                return 0
