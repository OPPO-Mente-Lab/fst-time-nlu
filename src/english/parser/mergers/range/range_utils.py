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
from .....core.logger import get_logger
from ...time_utils import (
    skip_empty_tokens,
    skip_the_token,
    is_digit_sequence,
    parse_datetime_str,
    format_datetime_str,
    get_parser_and_parse,
)


class RangeUtils:
    """Utility functions for range merging operations"""

    def __init__(self, parsers):
        """
        Initialize range utils

        Args:
            parsers (dict): Dictionary containing various time parsers
        """
        self.parsers = parsers
        self.logger = get_logger(__name__)

    def apply_modifier_to_base_time(self, modifier_token, base_time):  # noqa: C901
        """
        Apply relative modifier to base_time

        Args:
            modifier_token (dict): Modifier token (time_relative or time_composite_relative)
            base_time (datetime): Base time

        Returns:
            datetime: Modified base time
        """
        try:
            # Handle time_relative
            if modifier_token.get("type") == "time_relative":
                offset_day = modifier_token.get("offset_day", "").strip('"')
                offset_year = modifier_token.get("offset_year", "").strip('"')
                offset_month = modifier_token.get("offset_month", "").strip('"')

                try:
                    day_offset = int(offset_day) if offset_day else 0
                    year_offset = int(offset_year) if offset_year else 0
                    month_offset = int(offset_month) if offset_month else 0

                    modified_time = base_time + timedelta(days=day_offset)
                    modified_time = modified_time + relativedelta(
                        years=year_offset, months=month_offset
                    )
                    return modified_time
                except (ValueError, TypeError):
                    pass

            # Handle time_composite_relative
            elif modifier_token.get("type") == "time_composite_relative":
                offset_year = modifier_token.get("offset_year", "").strip('"')
                offset_month = modifier_token.get("offset_month", "").strip('"')
                time_modifier = modifier_token.get("time_modifier", "").strip('"')
                ordinal_position = modifier_token.get("ordinal_position", "").strip('"')
                unit = modifier_token.get("unit", "").strip('"')

                try:
                    if offset_year:
                        year_offset = int(offset_year)
                        return base_time + relativedelta(years=year_offset)
                    elif offset_month:
                        month_offset = int(offset_month)
                        return base_time + relativedelta(months=month_offset)
                    elif time_modifier and unit:
                        # Handle time_modifier field (e.g., "last year" -> time_modifier: "-1", unit: "year")
                        modifier_value = int(time_modifier)
                        if unit == "year":
                            return base_time + relativedelta(years=modifier_value)
                        elif unit == "month":
                            return base_time + relativedelta(months=modifier_value)
                    elif ordinal_position and unit:
                        position = int(ordinal_position)
                        if unit == "year":
                            return base_time + relativedelta(years=position)
                        elif unit == "month":
                            return base_time + relativedelta(months=position)
                except (ValueError, TypeError):
                    pass

            return base_time

        except Exception as e:
            self.logger.debug(f"Error in apply_modifier_to_base_time: {e}")
            return base_time

    def parse_time_token(self, token, base_time):
        """
        Parse a time token using appropriate parser

        Args:
            token (dict): Time token
            base_time (datetime): Base time

        Returns:
            list: Parsed time result or None
        """
        try:
            token_type = token.get("type")
            return get_parser_and_parse(self.parsers, token_type, token, base_time)
        except Exception as e:
            self.logger.debug(f"Error in parse_time_token: {e}")
            return None

    def inherit_period_marker(self, start_token, end_token):
        """
        Inherit AM/PM period marker from end_token to start_token if needed

        Args:
            start_token (dict): Start time token
            end_token (dict): End time token

        Returns:
            dict: Modified start_token with inherited period marker
        """
        try:
            # Create a copy to avoid modifying the original
            start_token_copy = start_token.copy()

            # Check if end_token has period marker but start_token doesn't
            end_period = end_token.get("period", "").strip('"').lower()
            start_period = start_token.get("period", "").strip('"').lower()

            if end_period and not start_period:
                # Inherit the period marker
                start_token_copy["period"] = end_token["period"]

                # Additional logic: ensure start time aligns with end period marker
                start_hour = start_token.get("hour", "").strip('"')

                if start_hour:
                    try:
                        start_hour_int = int(start_hour)
                        # If end time is PM and start time hour < 12, start should also be PM
                        # If end time is AM and start time hour >= 12, start should also be AM
                        if end_period == "p.m." and start_hour_int < 12:
                            start_token_copy["period"] = end_token["period"]
                        elif end_period == "a.m." and start_hour_int >= 12:
                            start_token_copy["period"] = end_token["period"]
                    except (ValueError, TypeError):
                        pass

            return start_token_copy

        except Exception as e:
            self.logger.debug(f"Error in inherit_period_marker: {e}")
            return start_token

    def merge_time_range(  # noqa: C901
        self,
        start_token,
        end_token,
        modifier_token,
        base_time,
        prefix_modifier=False,
        start_modifier_token=None,
        end_modifier_token=None,
    ):
        """
        Merge time range from start_token to end_token

        Args:
            start_token (dict): Start time token
            end_token (dict): End time token
            modifier_token (dict): Optional relative modifier token
            base_time (datetime): Base time
            prefix_modifier (bool): If True, modifier is before the range (e.g., "last year april 3 to may 1")

        Returns:
            list: [[start_time_str, end_time_str]] or None
        """
        try:
            # Apply AM/PM inheritance: if end_token has period but start_token doesn't, inherit it
            start_token = self.inherit_period_marker(start_token, end_token)

            # Check if start_token has offset_year/offset_month (e.g., "last year april 3 to may 1")
            if (
                start_token.get("type") == "time_composite_relative"
                and ("offset_year" in start_token or "offset_month" in start_token)
            ) or (
                start_token.get("type") == "time_utc"
                and ("offset_year" in start_token or "offset_month" in start_token)
            ):
                # Extract modifier from start_token
                modifier_token = {
                    "type": "time_composite_relative",
                    "offset_year": start_token.get("offset_year", ""),
                    "offset_month": start_token.get("offset_month", ""),
                }
                # Extract pure time fields from start_token
                start_token_pure = {
                    k: v
                    for k, v in start_token.items()
                    if k not in ["offset_year", "offset_month", "ordinal_position", "unit"]
                }
                start_token_pure["type"] = "time_utc"  # Treat as time_utc after removing modifiers

                # Apply modifier to both times
                modified_base = self.apply_modifier_to_base_time(modifier_token, base_time)
                start_result = self.parse_time_token(start_token_pure, modified_base)
                end_result = self.parse_time_token(end_token, modified_base)
            # Check if end_token has offset_year/offset_month (e.g., "april 3 to may 1 last year")
            elif (
                end_token.get("type") == "time_composite_relative"
                and ("offset_year" in end_token or "offset_month" in end_token)
            ) or (
                end_token.get("type") == "time_utc"
                and ("offset_year" in end_token or "offset_month" in end_token)
            ):
                # Extract modifier from end_token
                modifier_token = {
                    "type": "time_composite_relative",
                    "offset_year": end_token.get("offset_year", ""),
                    "offset_month": end_token.get("offset_month", ""),
                }
                # Extract pure time fields from end_token
                end_token_pure = {
                    k: v
                    for k, v in end_token.items()
                    if k not in ["offset_year", "offset_month", "ordinal_position", "unit"]
                }
                end_token_pure["type"] = "time_utc"  # Treat as time_utc after removing modifiers

                # Apply modifier to both times
                modified_base = self.apply_modifier_to_base_time(modifier_token, base_time)
                start_result = self.parse_time_token(start_token, modified_base)
                end_result = self.parse_time_token(end_token_pure, modified_base)
            # If end_token is the same as modifier_token (e.g., "july 6 last year"),
            # we need to extract the pure time part and apply the modifier
            elif modifier_token and end_token is modifier_token:
                # Extract pure time fields from end_token
                end_token_pure = {
                    k: v
                    for k, v in end_token.items()
                    if k not in ["offset_year", "offset_month", "ordinal_position", "unit"]
                }
                end_token_pure["type"] = "time_utc"  # Treat as time_utc after removing modifiers

                # Apply modifier to both times
                modified_base = self.apply_modifier_to_base_time(modifier_token, base_time)
                start_result = self.parse_time_token(start_token, modified_base)
                end_result = self.parse_time_token(end_token_pure, modified_base)
            elif modifier_token:
                # Check if modifier_token is time_composite_relative with time_modifier field
                if (
                    modifier_token.get("type") == "time_composite_relative"
                    and "time_modifier" in modifier_token
                ):
                    # Apply modifier to both times
                    modified_base = self.apply_modifier_to_base_time(modifier_token, base_time)
                    start_result = self.parse_time_token(start_token, modified_base)
                    end_result = self.parse_time_token(end_token, modified_base)
                elif prefix_modifier:
                    # Prefix modifier applies to both times
                    modified_base = self.apply_modifier_to_base_time(modifier_token, base_time)
                    start_result = self.parse_time_token(start_token, modified_base)
                    end_result = self.parse_time_token(end_token, modified_base)
                else:
                    # Postfix modifier applies to both times
                    modified_base = self.apply_modifier_to_base_time(modifier_token, base_time)
                    start_result = self.parse_time_token(start_token, modified_base)
                    end_result = self.parse_time_token(end_token, modified_base)
            # Handle case where start and end have different modifiers (e.g., "august 20 last year to november 10 this year")
            elif start_modifier_token and end_modifier_token:
                # Apply different modifiers to start and end times
                start_modified_base = self.apply_modifier_to_base_time(
                    start_modifier_token, base_time
                )
                end_modified_base = self.apply_modifier_to_base_time(end_modifier_token, base_time)
                start_result = self.parse_time_token(start_token, start_modified_base)
                end_result = self.parse_time_token(end_token, end_modified_base)
            else:
                # No modifier
                start_result = self.parse_time_token(start_token, base_time)
                end_result = self.parse_time_token(end_token, base_time)

            if not start_result or not end_result:
                return None

            # Extract start and end times
            start_time_str = start_result[0][0]
            end_time_str = end_result[0][-1] if len(end_result[0]) > 1 else end_result[0][0]

            return [[start_time_str, end_time_str]]

        except Exception as e:
            self.logger.debug(f"Error in merge_time_range: {e}")
            return None

    def check_on_weekday_suffix(self, time_b_idx, tokens):
        """
        检查 time_B 后是否有 'on + weekday' 模式

        Returns:
            tuple: (weekday_token, jump_offset) or (None, 0)
        """
        n = len(tokens)
        idx = time_b_idx + 1

        # Skip empty tokens
        while idx < n and tokens[idx].get("type") == "token" and tokens[idx].get("value", "") == "":
            idx += 1

        if idx >= n:
            return None, 0

        # Check for "on" token
        if tokens[idx].get("type") == "token" and tokens[idx].get("value", "").lower() == "on":
            idx += 1
            # Skip empty tokens after "on"
            while (
                idx < n
                and tokens[idx].get("type") == "token"
                and tokens[idx].get("value", "") == ""
            ):
                idx += 1

            if idx < n and tokens[idx].get("type") == "time_weekday":
                return tokens[idx], idx + 1 - time_b_idx - 1

        # Check for direct weekday (without "on")
        if tokens[idx].get("type") == "time_weekday":
            return tokens[idx], idx + 1 - time_b_idx - 1

        return None, 0

    def check_weekday_prefix(self, i, tokens):
        """
        Check if there's a weekday token before the current position

        Args:
            i (int): Current token index
            tokens (list): List of tokens

        Returns:
            dict: Weekday token if found, None otherwise
        """
        try:
            # Look backwards from current position for weekday token
            for j in range(i - 1, -1, -1):
                token = tokens[j]
                if token.get("type") == "time_weekday":
                    return token
                # Skip empty tokens
                if token.get("type") == "token" and token.get("value", "").strip():
                    break

            return None

        except Exception as e:
            self.logger.debug(f"Error in check_weekday_prefix: {e}")
            return None

    def extract_day_from_incorrect_parsing(self, token):
        """
        Extract day value from incorrectly parsed token
        Handles cases where "13" was parsed as month='1', day='3'
        """
        if token.get("type") != "time_utc":
            return None

        month_str = token.get("month", "").strip('"')
        day_str = token.get("day", "").strip('"')

        # If we have both month and day, try to reconstruct the original number
        if month_str and day_str:
            try:
                # This handles cases like month='1', day='3' -> day=13
                reconstructed_day = int(month_str + day_str)
                return reconstructed_day
            except (ValueError, TypeError):
                pass

        # If we only have day, use it directly
        if day_str:
            try:
                return int(day_str)
            except (ValueError, TypeError):
                pass

        return None

    def is_from_day_to_day_of_month_pattern(self, i, tokens):  # noqa: C901
        """
        Check if this is a "from day to day of month" pattern
        that should be handled by _try_merge_from_day_to_day_month
        """
        n = len(tokens)
        if i >= n:
            return False

        # from (can be either time_connector or token)
        if not (
            (tokens[i].get("type") == "time_connector" and tokens[i].get("connector", "") == "from")
            or (tokens[i].get("type") == "token" and tokens[i].get("value", "").lower() == "from")
        ):
            return False

        # Skip empty tokens and find day_a
        day_a_idx = skip_empty_tokens(tokens, i + 1)
        if day_a_idx >= n:
            return False

        # If the first token is a time_utc with month and day (e.g., "june 9"),
        # it's NOT a "day to day" pattern - it's a "month day to month day" pattern
        day_a_token = tokens[day_a_idx]
        if day_a_token.get("type") == "time_utc":
            has_month = "month" in day_a_token
            has_day = "day" in day_a_token
            if has_month and has_day:
                return (
                    False  # This is a "month day to month day" pattern, not a "day to day" pattern
                )

        # Skip "the" token before day_a if present
        day_a_idx = skip_the_token(tokens, day_a_idx)
        if day_a_idx >= n:
            return False

        # Check if day_a is a digit sequence (can be split like '1', '3' for 13)
        is_day_a = is_digit_sequence(tokens, day_a_idx)

        if not is_day_a:
            return False

        # Skip empty tokens and find "to"
        to_idx = skip_empty_tokens(tokens, day_a_idx + 1)
        if to_idx >= n:
            return False

        # Check if it's "to" connector
        to_token = tokens[to_idx]
        if not (
            (to_token.get("type") == "time_connector" and to_token.get("connector", "") == "to")
            or (to_token.get("type") == "token" and to_token.get("value", "").lower() == "to")
        ):
            return False

        # Skip empty tokens and find day_b
        day_b_idx = skip_empty_tokens(tokens, to_idx + 1)
        if day_b_idx >= n:
            return False

        # Skip "the" token before day_b if present
        day_b_idx = skip_the_token(tokens, day_b_idx)
        if day_b_idx >= n:
            return False

        # Check if day_b is a digit sequence (can be split like '1', '5' for 15)
        is_day_b = is_digit_sequence(tokens, day_b_idx)

        if not is_day_b:
            return False

        # Check if day_b token already contains month (e.g., "15th of July")
        day_b_token = tokens[day_b_idx]
        if day_b_token.get("type") == "time_utc" and "month" in day_b_token:
            return True

        # Skip empty tokens and check if there's a month after day_b
        month_idx = skip_empty_tokens(tokens, day_b_idx + 1)
        if month_idx >= n:
            return False

        # Check if there's a month token
        month_token = tokens[month_idx]
        has_month = month_token.get("type") == "time_utc" and "month" in month_token

        return has_month

    def merge_time_range_with_weekday(
        self, start_token, end_token, weekday_token, modifier_token, base_time
    ):
        """
        合并时间范围和星期几

        Args:
            start_token: 开始时间token (e.g., 9:30)
            end_token: 结束时间token (e.g., 11:00)
            weekday_token: 星期几token (e.g., thursday)
            modifier_token: 可选的修饰符 (e.g., next, last)
            base_time: 基准时间

        Returns:
            [[start_time_str, end_time_str]] with weekday applied
        """
        try:
            # 1. Parse weekday to get the target date
            weekday_result = get_parser_and_parse(
                self.parsers, "time_weekday", weekday_token, base_time
            )
            if not weekday_result or not weekday_result[0]:
                return None

            # Extract the date from weekday result
            weekday_date_str = weekday_result[0][0]
            weekday_date = parse_datetime_str(weekday_date_str)

            # 2. Parse start and end times (these are hour:minute)
            start_result = self.parse_time_token(start_token, base_time)
            end_result = self.parse_time_token(end_token, base_time)

            if not start_result or not end_result:
                return None

            # Extract hour and minute from parsed times
            start_time_str = start_result[0][0]
            end_time_str = end_result[0][0]
            start_time = parse_datetime_str(start_time_str)
            end_time = parse_datetime_str(end_time_str)

            # 3. Combine weekday date with time range
            result_start = weekday_date.replace(
                hour=start_time.hour, minute=start_time.minute, second=0
            )
            result_end = weekday_date.replace(hour=end_time.hour, minute=end_time.minute, second=0)

            return [
                [
                    format_datetime_str(result_start),
                    format_datetime_str(result_end),
                ]
            ]

        except Exception as e:
            self.logger.debug(f"Error in merge_time_range_with_weekday: {e}")
            return None
