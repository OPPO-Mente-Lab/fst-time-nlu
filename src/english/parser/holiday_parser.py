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

import os
import json
import datetime

from ...core.logger import get_logger
from .time_utils import (
    fathers_day,
    mothers_day,
    thanksgiving_day,
    easter_day,
    good_friday,
    memorial_day,
    labor_day,
    mlk_day,
    presidents_day,
    black_friday,
    boss_day,
    easter_monday,
    maundy_thursday,
    pentecost,
    whit_monday,
    palm_sunday,
    trinity_sunday,
    shrove_tuesday,
    orthodox_easter,
    orthodox_good_friday,
    clean_monday,
    lazarus_saturday,
    great_fast,
)
from .base_parser import BaseParser


class HolidayParser(BaseParser):
    """
    Holiday time expression parser

    Handles various holiday-related time expressions, including:
    - Calendar holidays (New Year's Day, Valentine's Day, etc.)
    - Western holidays (Easter, Thanksgiving, etc.)
    - Statutory holidays (Independence Day, Christmas, etc.)
    """

    def __init__(self):
        """Initialize holiday parser"""
        super().__init__()
        self.logger = get_logger(__name__)

        # Calendar holiday configuration (fixed dates)
        self.calendar_holiday = {
            "new_year": [1, 1],
            "valentine": [2, 14],
            "womens_day": [3, 8],
            "arbor_day": [3, 12],
            "april_fools": [4, 1],
            "earth_day": [4, 22],
            "teachers_day": [9, 10],
            "halloween": [10, 31],
            "christmas": [12, 25],
            "christmas_eve": [12, 24],
            "new_years_eve": [12, 31],
            "st_patricks": [3, 17],
            "veterans_day": [11, 11],
            "world_vegan_day": [11, 1],
        }

        # Variable date holidays (calculated based on year)
        self.variable_holiday = {
            "mothers_day": mothers_day,
            "fathers_day": fathers_day,
            "thanksgiving": thanksgiving_day,
            "easter": easter_day,
            "good_friday": good_friday,
            "memorial_day": memorial_day,
            "labor_day": labor_day,
            "mlk_day": mlk_day,
            "presidents_day": presidents_day,
            "black_friday": black_friday,
            "boss_day": boss_day,
            "easter_monday": easter_monday,
            "maundy_thursday": maundy_thursday,
            "pentecost": pentecost,
            "whit_monday": whit_monday,
            "palm_sunday": palm_sunday,
            "trinity_sunday": trinity_sunday,
            "shrove_tuesday": shrove_tuesday,
            "orthodox_easter": orthodox_easter,
            "orthodox_good_friday": orthodox_good_friday,
            "clean_monday": clean_monday,
            "lazarus_saturday": lazarus_saturday,
            "great_fast": great_fast,
        }

        # Statutory holiday configuration (holidays defined in JSON file)
        self.statutory_holiday = {
            "independence_day": [7, 4],
            "christmas": [12, 25],
            "thanksgiving": thanksgiving_day,
            "new_year": [1, 1],
            "may_day": [5, 1],
            "chinese_new_year": None,  # Variable date, read from JSON
            "chinese_new_year_eve": None,  # Variable date, read from JSON
            "dragon_boat": None,  # Variable date, read from JSON
            "double_ninth": None,  # Variable date, read from JSON
            "mid_autumn": None,  # Variable date, read from JSON
        }

    def parse(self, token, base_time):
        """
        Parse holiday-related time expressions

        Args:
            token (dict): Time expression token
            base_time (datetime): Base time reference

        Returns:
            list: Time range list in format [[start_time_str, end_time_str]]
        """
        festival = token.get("festival", "").strip('"')
        day_prefix = token.get("day_prefix", "")
        day_offset = int(token.get("day_prefix", 0))

        # Check for general time modifier (from "previous", "next", etc.)
        time_offset = token.get("_time_offset", 0)
        if time_offset:
            # Apply year offset directly
            base_time = base_time.replace(year=base_time.year + time_offset)

        # Handle year information - if year is specified, use it directly
        if token.get("year"):
            year_val = int(token.get("year"))
            # Expand two-digit years
            if year_val < 100:
                year_val = 2000 + year_val if year_val < 50 else 1900 + year_val
            base_time = base_time.replace(year=year_val)
            # When year is explicitly specified, don't apply other offsets
            # Process based on holiday type directly
            if festival in self.variable_holiday:
                return self._handle_variable_holiday(festival, base_time, day_offset)
            elif festival in self.calendar_holiday:
                return self._handle_calendar_holiday(festival, base_time, day_offset)
            elif festival in self.statutory_holiday:
                return self._handle_statutory_holiday(festival, base_time, day_prefix, day_offset)
            else:
                return []

        # Calculate target year and time offset (only when no explicit year)
        direction = self._determine_direction(token)
        time_offset_num = self._get_offset_time_num(token)
        base_time = self._apply_offset_time_num(base_time, time_offset_num, direction)

        # Process based on holiday type
        if festival in self.variable_holiday:
            return self._handle_variable_holiday(festival, base_time, day_offset)
        elif festival in self.calendar_holiday:
            return self._handle_calendar_holiday(festival, base_time, day_offset)
        elif festival in self.statutory_holiday:
            return self._handle_statutory_holiday(festival, base_time, day_prefix, day_offset)
        else:
            return []

    def _handle_variable_holiday(self, festival, base_time, day_offset):
        """
        Handle variable date holidays

        Args:
            festival (str): Holiday name
            base_time (datetime): Base time reference
            day_offset (int): Day offset

        Returns:
            list: Time range list
        """
        # Get holiday calculation function
        calc_func = self.variable_holiday[festival]
        result = calc_func(base_time.year)

        # Handle special case for great_fast which returns a date range
        if festival == "great_fast":
            start_month, start_day = result[0]
            end_month, end_day = result[1]

            start_date = base_time.replace(month=start_month, day=start_day) + datetime.timedelta(
                days=day_offset
            )
            end_date = base_time.replace(month=end_month, day=end_day) + datetime.timedelta(
                days=day_offset
            )

            start_of_start_day, _ = self._get_day_range(start_date)
            _, end_of_end_day = self._get_day_range(end_date)

            return self._format_time_result(start_of_start_day, end_of_end_day)
        else:
            # Regular single-day holidays
            month, day = result
            target_date = base_time.replace(month=month, day=day) + datetime.timedelta(
                days=day_offset
            )
            start_of_day, end_of_day = self._get_day_range(target_date)
            return self._format_time_result(start_of_day, end_of_day)

    def _handle_calendar_holiday(self, festival, base_time, day_offset):
        """
        Handle calendar holidays

        Args:
            festival (str): Holiday name
            base_time (datetime): Base time reference
            day_offset (int): Day offset

        Returns:
            list: Time range list
        """
        month, day = self.calendar_holiday[festival]

        # Use base class day range function
        target_date = base_time.replace(month=month, day=day) + datetime.timedelta(days=day_offset)
        start_of_day, end_of_day = self._get_day_range(target_date)
        return self._format_time_result(start_of_day, end_of_day)

    def _handle_statutory_holiday(self, festival, base_time, day_prefix, day_offset):  # noqa: C901
        """
        Handle statutory holidays

        Args:
            festival (str): Holiday name
            base_time (datetime): Base time reference
            day_prefix (str): Day prefix
            day_offset (int): Day offset

        Returns:
            list: Time range list
        """
        # Read holiday configuration file
        json_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "../data/holiday/holidays.json"
        )

        try:
            with open(json_path, "r", encoding="utf-8") as f:
                holidays_data = json.load(f)
        except FileNotFoundError:
            self.logger.warning(f"Holiday data file not found: {json_path}")
            # Fall back to calculating from holiday definition
            if festival in self.variable_holiday:
                calc_func = self.variable_holiday[festival]
                month, day = calc_func(base_time.year)
            elif festival in self.calendar_holiday:
                month, day = self.calendar_holiday[festival]
            else:
                return []

            target_date = base_time.replace(month=month, day=day) + datetime.timedelta(
                days=day_offset
            )
            start_of_day, end_of_day = self._get_day_range(target_date)
            return self._format_time_result(start_of_day, end_of_day)

        # Get holiday data for corresponding year
        year_str = str(base_time.year)
        if year_str in holidays_data:  # Holiday time for recent five years
            holiday_info = holidays_data[year_str].get(festival)
            if not holiday_info:
                # Fallback if festival not found in specific year
                if festival in self.variable_holiday:
                    return self._handle_variable_holiday(festival, base_time, day_offset)
                elif festival in self.calendar_holiday:
                    return self._handle_calendar_holiday(festival, base_time, day_offset)
                return []

            start_date = holiday_info["start_time"]
            end_date = holiday_info["end_time"]
            start_time = datetime.datetime.strptime(start_date, "%Y-%m-%d").replace(
                hour=0, minute=0, second=0
            )
            end_time = datetime.datetime.strptime(end_date, "%Y-%m-%d").replace(
                hour=23, minute=59, second=59
            )
        else:  # Time for years outside recent five years
            holiday_info = holidays_data["normal"].get(festival)
            if not holiday_info:
                # Fallback if festival not found
                if festival in self.variable_holiday:
                    return self._handle_variable_holiday(festival, base_time, day_offset)
                elif festival in self.calendar_holiday:
                    return self._handle_calendar_holiday(festival, base_time, day_offset)
                return []

            start_date = holiday_info["start_time"]
            end_date = holiday_info["end_time"]
            start_time = datetime.datetime.strptime(start_date, "%Y-%m-%d").replace(
                year=base_time.year, hour=0, minute=0, second=0
            )
            end_time = datetime.datetime.strptime(end_date, "%Y-%m-%d").replace(
                year=base_time.year, hour=23, minute=59, second=59
            )

        # Handle day prefix (e.g., "independence day" refers to the day itself)
        if day_prefix:
            day_prefix = int(day_prefix)
            # Get the base date from statutory_holiday definition
            if festival in self.variable_holiday:
                calc_func = self.variable_holiday[festival]
                date_month, date_day = calc_func(base_time.year)
            elif festival in self.calendar_holiday:
                date_month, date_day = self.calendar_holiday[festival]
            else:
                date_month, date_day = self.statutory_holiday[festival]

            target_date = base_time.replace(month=date_month, day=date_day) + datetime.timedelta(
                days=day_prefix
            )
            start_of_day, end_of_day = self._get_day_range(target_date)
            return self._format_time_result(start_of_day, end_of_day)

        return self._format_time_result(start_time, end_time)

    def _determine_direction(self, token):
        """
        Determine time offset direction

        Args:
            token (dict): Time expression token

        Returns:
            int: Direction (1 for future, -1 for past, 0 for current)
        """
        if "offset_direction" in token:
            direction_str = str(token["offset_direction"]).strip('"')
            try:
                return int(direction_str)
            except (ValueError, TypeError):
                pass

        # Check for direction keywords
        if "direction" in token:
            direction = str(token["direction"]).strip('"').lower()
            if direction in ["next", "following", "upcoming"]:
                return 1
            elif direction in ["last", "previous", "past"]:
                return -1

        return 0

    def _get_offset_time_num(self, token):
        """
        Get time offset numbers from token

        Args:
            token (dict): Time expression token

        Returns:
            dict: Time offset dictionary
        """
        time_num = {}

        for key in ["year", "month", "week", "day", "hour", "minute", "second"]:
            offset_key = f"offset_{key}"
            if offset_key in token:
                try:
                    value = int(str(token[offset_key]).strip('"'))
                    time_num[key] = value
                except (ValueError, TypeError):
                    pass

        return time_num

    def _apply_offset_time_num(self, base_time, time_num, direction):
        """
        Apply time offset to base time

        Args:
            base_time (datetime): Base time reference
            time_num (dict): Time offset dictionary
            direction (int): Direction (1 for future, -1 for past, 0 for signed offset)

        Returns:
            datetime: Adjusted time
        """
        result_time = base_time

        # If direction is 0, offset values already contain sign information
        # If direction is non-zero, multiply offset by direction
        multiplier = direction if direction != 0 else 1

        # Apply year offset
        if "year" in time_num:
            result_time = result_time.replace(year=result_time.year + multiplier * time_num["year"])

        # Apply month offset
        if "month" in time_num:
            total_months = (
                result_time.year * 12 + result_time.month + multiplier * time_num["month"]
            )
            new_year = total_months // 12
            new_month = total_months % 12
            if new_month == 0:
                new_month = 12
                new_year -= 1
            result_time = result_time.replace(year=new_year, month=new_month)

        # Apply day/week offsets
        if "week" in time_num:
            result_time += datetime.timedelta(weeks=multiplier * time_num["week"])

        if "day" in time_num:
            result_time += datetime.timedelta(days=multiplier * time_num["day"])

        if "hour" in time_num:
            result_time += datetime.timedelta(hours=multiplier * time_num["hour"])

        if "minute" in time_num:
            result_time += datetime.timedelta(minutes=multiplier * time_num["minute"])

        if "second" in time_num:
            result_time += datetime.timedelta(seconds=multiplier * time_num["second"])

        return result_time
