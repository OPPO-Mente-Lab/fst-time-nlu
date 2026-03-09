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

from abc import ABC, abstractmethod
from datetime import datetime, timedelta
import re
from ...core.english_number_converter import convert_english_number


class BCYear:
    """Custom class to represent BC years"""

    def __init__(self, year):
        self.year = year
        self._bc_year = True

    def __str__(self):
        return f"-{self.year:04d}"

    def __repr__(self):
        return f"BCYear({self.year})"


class BaseParser(ABC):
    """
    Base class for English time expression parsers

    All time parsers should inherit from this class and implement unified interfaces and common functionality
    """

    # 年份范围限制（与中文FST保持一致）
    YEAR_MIN = 1900
    YEAR_MAX = 2100

    def __init__(self):
        """Initialize parser"""
        # Common time period vocabulary for English
        self.morning_time = ["morning", "am", "a.m.", "early morning", "dawn"]
        self.afternoon_time = ["afternoon", "pm", "p.m.", "evening", "night", "tonight"]
        self.noon_time = ["noon", "midday"]
        self.midnight_time = ["midnight", "late night"]

        # Period time map (similar to Chinese noon_map)
        # Format: (start_offset_day, start_hour, start_minute, start_second,
        #          end_offset_day, end_hour, end_minute, end_second)
        self.period_map = {
            # Basic time periods
            "morning": (
                0,
                5,
                0,
                0,
                0,
                12,
                0,
                0,
            ),  # 5:00 AM - 12:00 PM
            "afternoon": (0, 12, 0, 0, 0, 18, 0, 0),  # 12:00 PM - 6:00 PM
            "evening": (0, 18, 0, 0, 0, 22, 0, 0),  # 6:00 PM - 10:00 PM
            "night": (0, 18, 0, 0, 0, 23, 59, 59),  # 6:00 PM - 11:59:59 PM
            "tonight": (0, 18, 0, 0, 0, 23, 59, 59),  # 6:00 PM - 11:59:59 PM
            "noon": (0, 11, 30, 0, 0, 14, 0, 0),  # 11:30 AM - 2:00 PM
            "midday": (0, 11, 30, 0, 0, 14, 0, 0),  # 11:30 AM - 2:00 PM
            "midnight": (0, 0, 0, 0, 0, 0, 0, 0),  # 12:00 AM (single point)
            "dawn": (0, 5, 0, 0, 0, 7, 0, 0),  # 5:00 AM - 7:00 AM
            "sunrise": (0, 5, 0, 0, 0, 7, 0, 0),  # 5:00 AM - 7:00 AM
            "dusk": (0, 17, 0, 0, 0, 19, 0, 0),  # 5:00 PM - 7:00 PM
            "twilight": (0, 17, 30, 0, 0, 19, 30, 0),  # 5:30 PM - 7:30 PM
            # Meal times
            "breakfast": (0, 7, 0, 0, 0, 9, 0, 0),  # 7:00 AM - 9:00 AM
            "lunch": (0, 11, 30, 0, 0, 14, 0, 0),  # 11:30 AM - 2:00 PM
            "dinner": (0, 17, 30, 0, 0, 20, 0, 0),  # 5:30 PM - 8:00 PM
            # Extended periods
            "early_morning": (0, 5, 0, 0, 0, 8, 0, 0),  # 5:00 AM - 8:00 AM
            "early morning": (0, 5, 0, 0, 0, 8, 0, 0),  # 5:00 AM - 8:00 AM
            "late_morning": (0, 10, 0, 0, 0, 12, 0, 0),  # 10:00 AM - 12:00 PM
            "late morning": (0, 10, 0, 0, 0, 12, 0, 0),  # 10:00 AM - 12:00 PM
            "mid_morning": (0, 9, 0, 0, 0, 11, 0, 0),  # 9:00 AM - 11:00 AM
            "mid morning": (0, 9, 0, 0, 0, 11, 0, 0),  # 9:00 AM - 11:00 AM
            "early_afternoon": (0, 13, 0, 0, 0, 15, 0, 0),  # 1:00 PM - 3:00 PM
            "early afternoon": (0, 13, 0, 0, 0, 15, 0, 0),  # 1:00 PM - 3:00 PM
            "late_afternoon": (0, 15, 0, 0, 0, 18, 0, 0),  # 3:00 PM - 6:00 PM
            "late afternoon": (0, 15, 0, 0, 0, 18, 0, 0),  # 3:00 PM - 6:00 PM
            "mid_afternoon": (0, 14, 0, 0, 0, 16, 0, 0),  # 2:00 PM - 4:00 PM
            "mid afternoon": (0, 14, 0, 0, 0, 16, 0, 0),  # 2:00 PM - 4:00 PM
            "early_evening": (0, 18, 0, 0, 0, 20, 0, 0),  # 6:00 PM - 8:00 PM
            "early evening": (0, 18, 0, 0, 0, 20, 0, 0),  # 6:00 PM - 8:00 PM
            "late_evening": (0, 22, 0, 0, 0, 23, 59, 59),  # 10:00 PM - 11:59:59 PM
            "late evening": (0, 22, 0, 0, 0, 23, 59, 59),  # 10:00 PM - 11:59:59 PM
            "late_night": (0, 21, 0, 0, 1, 0, 0, 0),  # 9:00 PM - midnight (next day)
            "late night": (0, 21, 0, 0, 1, 0, 0, 0),  # 9:00 PM - midnight (next day)
            "early_night": (0, 18, 0, 0, 0, 21, 0, 0),  # 6:00 PM - 9:00 PM
            "early night": (0, 18, 0, 0, 0, 21, 0, 0),  # 6:00 PM - 9:00 PM
            # Day periods (外销新增)
            "early_hours": (0, 0, 0, 0, 0, 5, 0, 0),  # 12:00 AM - 5:00 AM
            "early hours": (0, 0, 0, 0, 0, 5, 0, 0),  # 12:00 AM - 5:00 AM
            "earlyhours": (0, 0, 0, 0, 0, 5, 0, 0),  # 12:00 AM - 5:00 AM (无空格版本)
            "daytime": (0, 5, 0, 0, 0, 18, 0, 0),  # 5:00 AM - 6:00 PM
            # Seasonal periods (will be handled specially in _parse_period)
            "spring": None,  # Special handling for seasons
            "summer": None,  # Special handling for seasons
            "autumn": None,  # Special handling for seasons
            "fall": None,  # Special handling for seasons (fall = autumn)
            "winter": None,  # Special handling for seasons
        }

        # Day of week mappings
        self.weekdays = {
            "monday": 0,
            "mon": 0,
            "tuesday": 1,
            "tue": 1,
            "tues": 1,
            "wednesday": 2,
            "wed": 2,
            "thursday": 3,
            "thu": 3,
            "thur": 3,
            "thurs": 3,
            "friday": 4,
            "fri": 4,
            "saturday": 5,
            "sat": 5,
            "sunday": 6,
            "sun": 6,
        }

        # Month mappings
        self.months = {
            "january": 1,
            "jan": 1,
            "february": 2,
            "feb": 2,
            "march": 3,
            "mar": 3,
            "april": 4,
            "apr": 4,
            "may": 5,
            "june": 6,
            "jun": 6,
            "july": 7,
            "jul": 7,
            "august": 8,
            "aug": 8,
            "september": 9,
            "sep": 9,
            "sept": 9,
            "october": 10,
            "oct": 10,
            "november": 11,
            "nov": 11,
            "december": 12,
            "dec": 12,
        }

    @abstractmethod
    def parse(self, token, base_time):
        """
        Abstract method for parsing time expressions

        Args:
            token (dict): Time expression token
            base_time (datetime): Base time reference

        Returns:
            list: Time range list in format [[start_time_str, end_time_str]]
        """
        pass

    def _format_time_result(self, start_time, end_time=None):
        """
        Format time result to standard format

        Args:
            start_time (datetime or BCYear): Start time
            end_time (datetime or BCYear, optional): End time, if None only return start time

        Returns:
            list: Formatted time result, returns empty list if year is outside 1900-2100 range
        """
        # Handle BC years - convert to datetime for unified checking
        if isinstance(start_time, BCYear):
            # BC years are always outside 1900-2100 range, return empty list
            return []

        # Check year range: 1900-2100
        if end_time is None:
            # Single time point: check start_time year
            if start_time.year < self.YEAR_MIN or start_time.year > self.YEAR_MAX:
                return []
            return [[start_time.strftime("%Y-%m-%dT%H:%M:%SZ")]]
        else:
            # Time range: check both start_time and end_time years
            if (
                start_time.year < self.YEAR_MIN
                or start_time.year > self.YEAR_MAX
                or end_time.year < self.YEAR_MIN
                or end_time.year > self.YEAR_MAX
            ):
                return []
            return [
                [
                    start_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    end_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                ]
            ]

    def _get_day_range(self, base_time):
        """
        Get start and end time of a day

        Args:
            base_time (datetime): Base time reference

        Returns:
            tuple: (start_of_day, end_of_day)
        """
        start_of_day = base_time.replace(hour=0, minute=0, second=0)
        end_of_day = base_time.replace(hour=23, minute=59, second=59)
        return start_of_day, end_of_day

    def _get_month_range(self, base_time, month=None):
        """
        Get start and end time of a month

        Args:
            base_time (datetime): Base time reference
            month (int, optional): Specified month, if None use base_time's month

        Returns:
            tuple: (start_of_month, end_of_month)
        """
        if month is not None:
            base_time = base_time.replace(month=month)

        # Calculate last day of month
        if base_time.month in [1, 3, 5, 7, 8, 10, 12]:
            end_day = 31
        elif base_time.month in [4, 6, 9, 11]:
            end_day = 30
        elif base_time.year % 4 == 0:
            if base_time.year % 100 != 0 or base_time.year % 400 == 0:
                end_day = 29
            else:
                end_day = 28
        else:
            end_day = 28

        start_of_month = base_time.replace(day=1, hour=0, minute=0, second=0)
        end_of_month = base_time.replace(day=end_day, hour=23, minute=59, second=59)
        return start_of_month, end_of_month

    def _get_year_range(self, base_time, year=None):
        """
        Get start and end time of a year

        Args:
            base_time (datetime): Base time reference
            year (int, optional): Specified year, if None use base_time's year (can be negative for BC years)

        Returns:
            tuple: (start_of_year, end_of_year)
        """
        if year is not None:
            if year < 0:
                # For BC years, return BCYear objects
                bc_year = BCYear(abs(year))
                return bc_year, bc_year
            else:
                base_time = base_time.replace(year=year)

        start_of_year = base_time.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        end_of_year = base_time.replace(
            month=12, day=31, hour=23, minute=59, second=59, microsecond=0
        )
        return start_of_year, end_of_year

    def _get_week_range(self, base_time):
        """
        Get start and end time of a week (Monday to Sunday)

        Args:
            base_time (datetime): Base time reference

        Returns:
            tuple: (start_of_week, end_of_week)
        """
        # Get Monday of the week
        days_since_monday = base_time.weekday()
        monday = base_time - timedelta(days=days_since_monday)
        start_of_week = monday.replace(hour=0, minute=0, second=0, microsecond=0)

        # Get Sunday of the week
        sunday = monday + timedelta(days=6)
        end_of_week = sunday.replace(hour=23, minute=59, second=59, microsecond=0)

        return start_of_week, end_of_week

    def _get_hour_range(self, base_time):
        """
        Get start and end time of an hour

        Args:
            base_time (datetime): Base time reference

        Returns:
            tuple: (start_of_hour, end_of_hour)
        """
        start_of_hour = base_time.replace(minute=0, second=0, microsecond=0)
        end_of_hour = base_time.replace(minute=59, second=59, microsecond=999999)
        return start_of_hour, end_of_hour

    def _get_minute_range(self, base_time):
        """
        Get start and end time of a minute

        Args:
            base_time (datetime): Base time reference

        Returns:
            tuple: (start_of_minute, end_of_minute)
        """
        start_of_minute = base_time.replace(second=0, microsecond=0)
        end_of_minute = base_time.replace(second=59, microsecond=999999)
        return start_of_minute, end_of_minute

    def _get_second_range(self, base_time):
        """
        Get start and end time of a second

        Args:
            base_time (datetime): Base time reference

        Returns:
            tuple: (start_of_second, end_of_second)
        """
        start_of_second = base_time.replace(microsecond=0)
        end_of_second = base_time.replace(microsecond=999999)
        return start_of_second, end_of_second

    def _parse_number(self, text):
        """
        Parse English number words to integers

        Args:
            text (str): Number text (e.g., "one", "two", "twenty-one")

        Returns:
            int or None: Parsed number or None if parsing fails
        """
        return convert_english_number(text)

    def _parse_ordinal(self, text):
        """
        Parse English ordinal numbers (1st, 2nd, 3rd, etc.)

        Args:
            text (str): Ordinal text

        Returns:
            int or None: Parsed ordinal number or None if parsing fails
        """
        if not text:
            return None

        text = text.lower().strip()

        # Handle numeric ordinals (1st, 2nd, 3rd, etc.)
        ordinal_pattern = re.compile(r"^(\d+)(?:st|nd|rd|th)$")
        match = ordinal_pattern.match(text)
        if match:
            return int(match.group(1))

        # Handle word ordinals
        ordinal_words = {
            "first": 1,
            "second": 2,
            "third": 3,
            "fourth": 4,
            "fifth": 5,
            "sixth": 6,
            "seventh": 7,
            "eighth": 8,
            "ninth": 9,
            "tenth": 10,
            "eleventh": 11,
            "twelfth": 12,
            "thirteenth": 13,
            "fourteenth": 14,
            "fifteenth": 15,
            "sixteenth": 16,
            "seventeenth": 17,
            "eighteenth": 18,
            "nineteenth": 19,
            "twentieth": 20,
            "twenty-first": 21,
            "twenty-second": 22,
            "twenty-third": 23,
            "twenty-fourth": 24,
            "twenty-fifth": 25,
            "twenty-sixth": 26,
            "twenty-seventh": 27,
            "twenty-eighth": 28,
            "twenty-ninth": 29,
            "thirtieth": 30,
            "thirty-first": 31,
        }

        return ordinal_words.get(text)

    def _get_weekday_date(self, base_time, target_weekday, direction="next"):
        """
        Get date for specific weekday relative to base time

        Args:
            base_time (datetime): Base time reference
            target_weekday (int): Target weekday (0=Monday, 6=Sunday)
            direction (str): "next", "previous", "this"

        Returns:
            datetime: Date for the target weekday
        """
        current_weekday = base_time.weekday()

        if direction == "next":
            days_ahead = target_weekday - current_weekday
            if days_ahead <= 0:  # Target day already happened this week
                days_ahead += 7
        elif direction == "previous":
            days_behind = current_weekday - target_weekday
            if days_behind <= 0:  # Target day hasn't happened this week
                days_behind += 7
            days_ahead = -days_behind
        else:  # "this"
            days_ahead = target_weekday - current_weekday

        return base_time + timedelta(days=days_ahead)

    def _convert_12_to_24_hour(self, hour, minute, period):
        """
        Convert 12-hour format to 24-hour format

        Args:
            hour (int): Hour in 12-hour format
            minute (int): Minute
            period (str): "am" or "pm"

        Returns:
            tuple: (hour_24, minute)
        """
        if period.lower() in ["am", "a.m."]:
            if hour == 12:
                hour = 0
        elif period.lower() in ["pm", "p.m."]:
            if hour != 12:
                hour += 12

        return hour, minute

    def _parse_time_components(self, token):
        """
        Extract time components from token

        Args:
            token (dict): Time token

        Returns:
            dict: Dictionary with extracted time components
        """
        components = {
            "year": None,
            "month": None,
            "day": None,
            "hour": None,
            "minute": None,
            "second": None,
            "weekday": None,
            "period": None,
        }

        # Extract available components from token
        for key in components.keys():
            if key in token:
                components[key] = token[key]

        return components

    def _get_time_num(self, token):  # noqa: C901
        """
        Extract time numbers from token

        Args:
            token (dict): Time expression token

        Returns:
            dict: Time number dictionary
        """
        time_num = {}

        # Parse hour (support decimal values like "2.5")
        if "hour" in token:
            hour_str = str(token["hour"]).strip('"').replace(" ", "")
            try:
                hour = float(hour_str)
                time_num["hour"] = hour
            except (ValueError, TypeError):
                pass

        # Parse minute (support decimal values like "2.5")
        if "minute" in token:
            minute_str = str(token["minute"]).strip('"').replace(" ", "")
            try:
                minute = float(minute_str)
                time_num["minute"] = minute
            except (ValueError, TypeError):
                pass

        # Parse second (support decimal values like "2.5")
        if "second" in token:
            second_str = str(token["second"]).strip('"').replace(" ", "")
            try:
                second = float(second_str)
                time_num["second"] = second
            except (ValueError, TypeError):
                pass

        # Parse period (am/pm only, not time periods like morning/afternoon)
        if "period" in token:
            period_str = str(token["period"]).strip('"')
            # Only include AM/PM periods, not time periods like morning/afternoon/evening
            if period_str.lower() in ["am", "pm", "a.m.", "p.m."]:
                time_num["period"] = period_str

        return time_num

    def _parse_period(self, base_time, period_str):
        """
        Parse time period string (similar to Chinese _parse_noon)

        Args:
            base_time (datetime): Base time reference
            period_str (str): Period string (e.g., 'morning', 'afternoon')

        Returns:
            tuple: (start_time, end_time)
        """
        if not period_str:
            return base_time, base_time

        # Normalize period string
        period_str = period_str.strip().strip('"').lower()

        # Check if it's a seasonal period
        if period_str in ["spring", "summer", "autumn", "fall", "winter"]:
            # Handle seasonal periods
            season = "autumn" if period_str == "fall" else period_str
            start_time, end_time = self._get_season_range(base_time.year, season)
            return start_time, end_time
        elif period_str == "season":
            # Handle generic "season" - use current season
            current_season = self._get_current_season(base_time)
            start_time, end_time = self._get_season_range(base_time.year, current_season)
            return start_time, end_time

        # Get period definition from map
        period_def = self.period_map.get(period_str)
        if not period_def:
            # Default to full day if period not found
            return self._get_day_range(base_time)

        # Unpack period definition
        (
            start_offset_day,
            start_hour,
            start_minute,
            start_second,
            end_offset_day,
            end_hour,
            end_minute,
            end_second,
        ) = period_def

        # Calculate start and end times
        start_base_time = base_time + timedelta(days=start_offset_day)
        end_base_time = base_time + timedelta(days=end_offset_day)

        start_time = start_base_time.replace(
            hour=start_hour, minute=start_minute, second=start_second, microsecond=0
        )
        end_time = end_base_time.replace(
            hour=end_hour, minute=end_minute, second=end_second, microsecond=0
        )

        return start_time, end_time

    def _calculate_equinox_solstice(self, year):
        """
        计算指定年份的春分、夏至、秋分、冬至日期

        使用简化的天文算法公式
        参考：2000-2099年的近似公式

        Args:
            year: 年份

        Returns:
            dict: {
                'spring_equinox': (month, day),
                'summer_solstice': (month, day),
                'autumn_equinox': (month, day),
                'winter_solstice': (month, day)
            }
        """
        if 2000 <= year <= 2099:
            # 使用简化公式计算（精度约±1天）
            y = year - 2000
            spring_day = 20 + y * 0.24219 - int(y / 4)
            summer_day = 21 + y * 0.24219 - int(y / 4)
            autumn_day = 23 + y * 0.24219 - int(y / 4)
            winter_day = 22 + y * 0.24219 - int(y / 4)
        else:
            # 其他年份使用固定近似值
            spring_day, summer_day = 20, 21
            autumn_day, winter_day = 23, 22

        return {
            "spring_equinox": (3, int(spring_day)),
            "summer_solstice": (6, int(summer_day)),
            "autumn_equinox": (9, int(autumn_day)),
            "winter_solstice": (12, int(winter_day)),
        }

    def _get_season_range(self, year, season):
        """
        根据年份和季节计算精确范围

        Args:
            year: 年份
            season: 季节 ('spring', 'summer', 'autumn', 'winter')

        Returns:
            (start_date, end_date) 元组
        """
        dates = self._calculate_equinox_solstice(year)

        if season == "spring":
            # 春分到夏至前一天
            start_m, start_d = dates["spring_equinox"]
            end_m, end_d = dates["summer_solstice"]
            end_d -= 1
            start = datetime(year, start_m, start_d, 0, 0, 0)
            end = datetime(year, end_m, end_d, 23, 59, 59)

        elif season == "summer":
            # 夏至到秋分前一天
            start_m, start_d = dates["summer_solstice"]
            end_m, end_d = dates["autumn_equinox"]
            end_d -= 1
            start = datetime(year, start_m, start_d, 0, 0, 0)
            end = datetime(year, end_m, end_d, 23, 59, 59)

        elif season == "autumn":
            # 秋分到冬至前一天
            start_m, start_d = dates["autumn_equinox"]
            end_m, end_d = dates["winter_solstice"]
            end_d -= 1
            start = datetime(year, start_m, start_d, 0, 0, 0)
            end = datetime(year, end_m, end_d, 23, 59, 59)

        elif season == "winter":
            # 冬至到次年春分前一天（跨年）
            # 冬季从当年的冬至开始
            start_m, start_d = dates["winter_solstice"]
            next_dates = self._calculate_equinox_solstice(year + 1)
            end_m, end_d = next_dates["spring_equinox"]
            end_d -= 1
            start = datetime(year, start_m, start_d, 0, 0, 0)
            end = datetime(year + 1, end_m, end_d, 23, 59, 59)

        return start, end

    def _get_current_season(self, base_time):
        """
        根据给定日期计算当前所处的季节

        Args:
            base_time: 基准时间

        Returns:
            str: 当前季节 ('spring', 'summer', 'autumn', 'winter')
        """
        year = base_time.year
        month = base_time.month
        day = base_time.day

        # 计算当年的二分二至日期
        dates = self._calculate_equinox_solstice(year)

        # 获取各个季节的开始日期
        spring_start = dates["spring_equinox"]
        summer_start = dates["summer_solstice"]
        autumn_start = dates["autumn_equinox"]
        winter_start = dates["winter_solstice"]

        # 将日期转换为可比较的格式
        current_date = (month, day)

        # 判断当前日期属于哪个季节
        if current_date >= spring_start and current_date < summer_start:
            return "spring"
        elif current_date >= summer_start and current_date < autumn_start:
            return "summer"
        elif current_date >= autumn_start and current_date < winter_start:
            return "autumn"
        else:
            # 冬季跨年，需要特殊处理
            # 如果当前日期在冬季开始之后，或者在新年的春季开始之前
            if current_date >= winter_start or current_date < spring_start:
                return "winter"
            else:
                return "spring"  # 默认情况

    def _get_month_nth_weekday(self, year, month, nth, weekday_name):
        """
        获取某月的第N个星期X

        Args:
            year: 年份
            month: 月份
            nth: 第几个（1-5, -1表示最后一个）
            weekday_name: 星期几名称（'monday', 'tuesday', ...）

        Returns:
            datetime: 目标日期
        """
        # 转换星期几名称为数字（0=Monday, 6=Sunday）
        weekday_map = {
            "monday": 0,
            "tuesday": 1,
            "wednesday": 2,
            "thursday": 3,
            "friday": 4,
            "saturday": 5,
            "sunday": 6,
        }
        target_weekday = weekday_map.get(weekday_name.lower(), 0)

        # 获取该月第一天
        first_day = datetime(year, month, 1)
        first_weekday = first_day.weekday()

        # 计算第一个目标星期几的日期
        days_until_target = (target_weekday - first_weekday) % 7
        first_occurrence = first_day + timedelta(days=days_until_target)

        if nth == -1:
            # 最后一个: 从月末往回找
            import calendar

            last_day = calendar.monthrange(year, month)[1]
            last_day_date = datetime(year, month, last_day)
            last_weekday = last_day_date.weekday()

            days_back = (last_weekday - target_weekday) % 7
            target_date = last_day_date - timedelta(days=days_back)
        else:
            # 计算第N个目标星期几
            target_date = first_occurrence + timedelta(weeks=nth - 1)

            # 确保仍在当月
            if target_date.month != month:
                raise ValueError(f"该月没有第{nth}个{weekday_name}")

        return target_date
