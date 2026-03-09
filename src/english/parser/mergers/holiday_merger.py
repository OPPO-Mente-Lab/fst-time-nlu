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
from ....core.logger import get_logger
from ..time_utils import parse_datetime_str, format_datetime_str, get_parser_and_parse


class HolidayMerger:
    """Merger for handling holiday-related time expressions"""

    def __init__(self, parsers):
        """
        Initialize holiday merger

        Args:
            parsers (dict): Dictionary containing various time parsers
        """
        self.parsers = parsers
        self.logger = get_logger(__name__)

    def merge_modifier_with_holiday(self, modifier_token, holiday_token, base_time):
        """
        Merge time_composite_relative(time_modifier) with time_holiday
        Example: "next new year's day" -> apply modifier to holiday

        Args:
            modifier_token (dict): Modifier token
            holiday_token (dict): Holiday token
            base_time (datetime): Base time

        Returns:
            list: Parsed holiday result or None
        """
        try:
            time_modifier = modifier_token.get("time_modifier", "").strip('"')
            if not time_modifier:
                return None

            modifier = int(time_modifier)

            # Parse the holiday first
            holiday_parser = self.parsers.get("time_holiday")
            if not holiday_parser:
                return None

            # Apply modifier to base_time
            if modifier > 0:
                # "next" - add 1 year
                modified_base = base_time.replace(year=base_time.year + 1)
            elif modifier < 0:
                # "last" - subtract 1 year
                modified_base = base_time.replace(year=base_time.year - 1)
            else:
                # "this" - use current year
                modified_base = base_time

            # Parse holiday with modified base time
            result = holiday_parser.parse(holiday_token, modified_base)
            return result

        except Exception as e:
            self.logger.debug(f"Error in merge_modifier_with_holiday: {e}")
            return None

    def merge_holiday_with_year(self, holiday_token, year_token, base_time):
        """
        Merge time_holiday with time_utc(year)
        Example: "halloween 2013" -> halloween in 2013

        Args:
            holiday_token (dict): Holiday token
            year_token (dict): Year token
            base_time (datetime): Base time

        Returns:
            list: Parsed holiday result or None
        """
        try:
            year_val = year_token.get("year", "").strip('"')
            if not year_val:
                return None

            year = int(year_val)
            # Expand two-digit years
            if year < 100:
                year = 2000 + year if year < 50 else 1900 + year

            # Parse the holiday with the specified year
            holiday_parser = self.parsers.get("time_holiday")
            if not holiday_parser:
                return None

            # Create a modified base time with the specified year
            modified_base = base_time.replace(year=year)

            # Parse holiday with modified base time
            result = holiday_parser.parse(holiday_token, modified_base)
            return result

        except Exception as e:
            self.logger.debug(f"Error in merge_holiday_with_year: {e}")
            return None

    def merge_holiday_with_time(self, holiday_token, time_token, base_time):
        """
        Merge time_holiday with time_utc(hour/minute/period)
        Example: "xmas at 6 pm" -> christmas at 6pm

        Args:
            holiday_token (dict): Holiday token
            time_token (dict): Time token
            base_time (datetime): Base time

        Returns:
            list: Parsed time result or None
        """
        try:
            # Parse the holiday first to get the date
            holiday_parser = self.parsers.get("time_holiday")
            if not holiday_parser:
                return None

            holiday_result = holiday_parser.parse(holiday_token, base_time)
            if not holiday_result or not holiday_result[0]:
                return None

            # Get the holiday date (use start time)
            holiday_date_str = holiday_result[0][0]
            holiday_date = parse_datetime_str(holiday_date_str)

            # Extract time components from time_token
            hour = time_token.get("hour", "").strip('"')
            minute = time_token.get("minute", "").strip('"')
            period = time_token.get("period", "").strip('"')

            if not hour:
                return None

            hour_val = int(hour)
            minute_val = int(minute) if minute else 0

            # Handle AM/PM
            if period:
                period_lower = period.lower()
                if period_lower in ["pm", "p.m."] and hour_val < 12:
                    hour_val += 12
                elif period_lower in ["am", "a.m."] and hour_val == 12:
                    hour_val = 0

            # Combine holiday date with time
            result_datetime = holiday_date.replace(
                hour=hour_val, minute=minute_val, second=0, microsecond=0
            )
            result_str = format_datetime_str(result_datetime)

            return [[result_str]]

        except Exception as e:
            self.logger.debug(f"Error in merge_holiday_with_time: {e}")
            return None

    def merge_period_with_holiday(self, period_token, holiday_token, base_time):
        """
        Merge time_period with time_holiday
        Example: "morning of xmas" -> christmas morning

        Args:
            period_token (dict): Period token
            holiday_token (dict): Holiday token
            base_time (datetime): Base time

        Returns:
            list: Parsed period result or None
        """
        try:
            # Parse the holiday first to get the date
            holiday_parser = self.parsers.get("time_holiday")
            if not holiday_parser:
                return None

            holiday_result = holiday_parser.parse(holiday_token, base_time)
            if not holiday_result or not holiday_result[0]:
                return None

            # Get the holiday date (use start time)
            holiday_date_str = holiday_result[0][0]
            holiday_date = parse_datetime_str(holiday_date_str)

            # Extract period from period_token
            period_str = period_token.get("noon", "").strip('"') or period_token.get(
                "period", ""
            ).strip('"')
            if not period_str:
                return None

            # Get period time range using the parser's method
            period_parser = self.parsers.get("time_period")
            if not period_parser:
                return None

            # Parse period to get time range
            period_result = period_parser.parse(period_token, holiday_date)
            if not period_result or not period_result[0]:
                return None

            return period_result

        except Exception as e:
            self.logger.debug(f"Error in merge_period_with_holiday: {e}")
            return None

    def merge_holiday_with_year_modifier(self, holiday_token, year_modifier_token, base_time):
        """
        Merge time_holiday with time_composite_relative(unit=year)
        Example: "black friday of this year" -> black friday in current year
        Example: "civil rights day of last year" -> mlk day in last year

        Args:
            holiday_token (dict): Holiday token
            year_modifier_token (dict): Year modifier token
            base_time (datetime): Base time

        Returns:
            list: Parsed holiday result or None
        """
        try:
            time_modifier = year_modifier_token.get("time_modifier", "").strip('"')
            unit = year_modifier_token.get("unit", "").strip('"')

            if unit != "year" or not time_modifier:
                return None

            modifier = int(time_modifier)

            # Parse the holiday with the modified year
            holiday_parser = self.parsers.get("time_holiday")
            if not holiday_parser:
                return None

            # Apply year offset to base_time
            modified_base = base_time.replace(year=base_time.year + modifier)

            # Parse holiday with modified base time
            result = holiday_parser.parse(holiday_token, modified_base)
            return result

        except Exception as e:
            self.logger.debug(f"Error in merge_holiday_with_year_modifier: {e}")
            return None

    def merge_delta_with_holiday(self, delta_token, holiday_token, base_time):
        """
        Merge time_delta with time_holiday
        Example: "three days after Easter" -> easter + 3 days

        Args:
            delta_token (dict): Delta token
            holiday_token (dict): Holiday token
            base_time (datetime): Base time

        Returns:
            list: Parsed delta result or None
        """
        try:
            # Parse the holiday first to get the date
            holiday_parser = self.parsers.get("time_holiday")
            if not holiday_parser:
                return None

            holiday_result = holiday_parser.parse(holiday_token, base_time)
            if not holiday_result or not holiday_result[0]:
                return None

            # Get the holiday date (use start time)
            holiday_date_str = holiday_result[0][0]
            holiday_date = parse_datetime_str(holiday_date_str)

            # Now apply the delta to this date
            delta_parser = self.parsers.get("time_delta")
            if not delta_parser:
                return None

            # Parse the delta with the holiday date as base time
            delta_result = delta_parser.parse(delta_token, holiday_date)
            if delta_result:
                return delta_result

            return None

        except Exception as e:
            self.logger.debug(f"Error in merge_delta_with_holiday: {e}")
            return None

    def merge_holiday_with_year_range(self, holiday_token, range_token, base_time):
        """
        Merge time_holiday with time_range(year)
        Example: "new year next year" -> apply year offset to holiday

        Args:
            holiday_token (dict): Holiday token
            range_token (dict): Range token
            base_time (datetime): Base time

        Returns:
            list: Parsed holiday result or None
        """
        try:
            offset_direction = range_token.get("offset_direction", "").strip('"')
            offset = range_token.get("offset", "").strip('"')
            unit = range_token.get("unit", "").strip('"')

            if unit != "year":
                return None

            try:
                direction = int(offset_direction)
                offset_value = int(offset)
                year_offset = direction * offset_value
            except (ValueError, TypeError):
                return None

            # Parse the holiday first
            holiday_parser = self.parsers.get("time_holiday")
            if not holiday_parser:
                return None

            # Apply year offset to base_time
            modified_base = base_time.replace(year=base_time.year + year_offset)

            # Parse holiday with modified base time
            result = holiday_parser.parse(holiday_token, modified_base)
            return result

        except Exception as e:
            self.logger.debug(f"Error in merge_holiday_with_year_range: {e}")
            return None

    def merge_holiday_with_time_delta(self, holiday_token, delta_token, base_time):
        """
        Merge time_holiday with time_delta(year)
        Example: "thanksgiving in a year" -> apply year offset to holiday

        Args:
            holiday_token (dict): Holiday token
            delta_token (dict): Delta token
            base_time (datetime): Base time

        Returns:
            list: Parsed holiday result or None
        """
        try:
            direction = delta_token.get("direction", "").strip('"')
            year_offset = int(delta_token.get("year", 0))

            if direction == "future":
                year_offset = year_offset
            elif direction == "past":
                year_offset = -year_offset
            else:
                return None

            # Parse the holiday first
            holiday_parser = self.parsers.get("time_holiday")
            if not holiday_parser:
                return None

            # Apply year offset to base_time
            modified_base = base_time.replace(year=base_time.year + year_offset)

            # Parse holiday with modified base time
            result = holiday_parser.parse(holiday_token, modified_base)
            return result

        except Exception as e:
            self.logger.debug(f"Error in merge_holiday_with_time_delta: {e}")
            return None

    def check_on_holiday_context(self, i, tokens):
        """
        Check if a holiday token is preceded by "on" to indicate single day context

        Args:
            i (int): Current token index
            tokens (list): List of tokens

        Returns:
            bool: True if this is an "on holiday" context
        """
        if i <= 0:
            return False

        # Look for "on" token before the holiday
        prev_token = tokens[i - 1]
        if (
            prev_token.get("type") == "token"
            and prev_token.get("value", "").strip().lower() == "on"
        ):
            return True

        # Also check for empty tokens (spaces) between "on" and holiday
        if i >= 2:
            prev_prev_token = tokens[i - 2]
            if (
                prev_prev_token.get("type") == "token"
                and prev_prev_token.get("value", "").strip().lower() == "on"
            ):
                return True

        return False

    def handle_on_holiday_single_day(self, i, tokens, base_time):
        """
        Handle "on holiday" context by returning only the first day of the holiday

        Args:
            i (int): Current token index
            tokens (list): List of tokens
            base_time (datetime): Base time reference

        Returns:
            tuple: (single_day_results, 1) or None
        """
        try:
            holiday_token = tokens[i]
            festival = holiday_token.get("festival", "").strip('"')

            # Only handle may_day for now
            if festival != "may_day":
                return None

            # Parse the holiday normally first
            holiday_parser = self.parsers.get("time_holiday")
            if not holiday_parser:
                return None

            full_results = holiday_parser.parse(holiday_token, base_time)
            if not full_results:
                return None

            # Extract just the first day (start of the holiday)
            first_result = full_results[0]
            if isinstance(first_result, list) and len(first_result) >= 2:
                start_time_str = first_result[0]
                # Convert to single day by using start time and end of day
                # Replace the time part to make it end of day (23:59:59)
                start_dt = parse_datetime_str(start_time_str)
                end_dt = start_dt.replace(hour=23, minute=59, second=59)
                end_time_str = format_datetime_str(end_dt)
                single_day_result = [start_time_str, end_time_str]
                return ([single_day_result], 1)

            return None

        except Exception as e:
            self.logger.debug(f"Error in handle_on_holiday_single_day: {e}")
            return None
