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

from datetime import datetime
from .....core.logger import get_logger
from ...time_utils import (
    skip_empty_tokens,
    skip_the_token,
    extract_day_value_from_tokens,
    extract_day_value,
    month_name_to_number,
    format_datetime_str,
)
from .range_utils import RangeUtils


class DayRangeMerger:
    """Merger for handling 'day + to + day + month' patterns"""

    def __init__(self, parsers):
        """
        Initialize day range merger

        Args:
            parsers (dict): Dictionary containing various time parsers
        """
        self.parsers = parsers
        self.logger = get_logger(__name__)
        self.range_utils = RangeUtils(parsers)

    def try_merge(self, i, tokens, base_time):
        """
        Try to merge "day + to + day + month" or "from + day + to + day + month" pattern

        Args:
            i (int): Current index
            tokens (list): Token list
            base_time (datetime): Base time

        Returns:
            tuple: (result, jump_count) or None
        """
        n = len(tokens)

        # Pattern 1: "from + day + to + day + month"
        # Example: "from 13th to 15th July"
        if i < n and (
            (tokens[i].get("type") == "time_connector" and tokens[i].get("connector", "") == "from")
            or (tokens[i].get("type") == "token" and tokens[i].get("value", "").lower() == "from")
        ):
            return self._try_merge_from_day_to_day_month(i, tokens, base_time)

        # Pattern 2: "month + day + to + day"
        # Example: "July 13 to 15"
        if i < n and tokens[i].get("type") == "time_utc" and "month" in tokens[i]:
            return self._try_merge_month_day_to_day(i, tokens, base_time)

        # Pattern 3: "day + to + day + month"
        # Example: "13th to 15th July"
        if i < n and tokens[i].get("type") == "time_utc" and "day" in tokens[i]:
            return self._try_merge_day_to_day_month_direct(i, tokens, base_time)

        return None

    def _try_merge_from_day_to_day_month(self, i, tokens, base_time):  # noqa: C901
        """Handle 'from + day + to + day + month' pattern"""
        n = len(tokens)
        if i >= n:
            return None

        # from (can be either time_connector or token)
        from_token = tokens[i]
        if not (
            (
                from_token.get("type") == "time_connector"
                and from_token.get("connector", "") == "from"
            )
            or (from_token.get("type") == "token" and from_token.get("value", "").lower() == "from")
        ):
            return None

        # Skip empty tokens and find day_a
        day_a_idx = skip_empty_tokens(tokens, i + 1)
        if day_a_idx >= n:
            return None

        # Skip "the" token before day_a if present
        day_a_idx = skip_the_token(tokens, day_a_idx)
        if day_a_idx >= n:
            return None

        # Extract day_a value (handles split numbers)
        day_a, day_a_end_idx = extract_day_value_from_tokens(tokens, day_a_idx)
        if day_a is None:
            return None

        # Skip empty tokens and find "to"
        to_idx = skip_empty_tokens(tokens, day_a_end_idx)
        if to_idx >= n:
            return None

        # Check if it's "to" connector
        to_token = tokens[to_idx]
        if not (
            (to_token.get("type") == "time_connector" and to_token.get("connector", "") == "to")
            or (to_token.get("type") == "token" and to_token.get("value", "").lower() == "to")
        ):
            return None

        # Skip empty tokens and find day_b
        day_b_idx = skip_empty_tokens(tokens, to_idx + 1)
        if day_b_idx >= n:
            return None

        # Skip "the" token before day_b if present
        day_b_idx = skip_the_token(tokens, day_b_idx)
        if day_b_idx >= n:
            return None

        # Extract day_b value (handles split numbers)
        day_b, day_b_end_idx = extract_day_value_from_tokens(tokens, day_b_idx)
        if day_b is None:
            return None

        # Check if day_b token already contains month (e.g., "15th of July")
        day_b_token = tokens[day_b_idx]
        month = None
        if day_b_token.get("type") == "time_utc" and "month" in day_b_token:
            month = day_b_token.get("month", "").strip('"')
            month_idx = day_b_end_idx  # No need to look further
        else:
            # Skip empty tokens and find month
            month_idx = skip_empty_tokens(tokens, day_b_end_idx)
            if month_idx >= n:
                return None

            # Extract month
            month_token = tokens[month_idx]
            month = month_token.get("month", "").strip('"')

        if not month:
            return None

        # Check for year modifier after month
        year_offset = 0
        modifier_idx = month_idx + 1
        while modifier_idx < n:
            token = tokens[modifier_idx]
            if token.get("type") == "token" and token.get("value", "") == "":
                # Skip empty tokens
                modifier_idx += 1
            elif token.get("type") == "time_composite_relative" and "time_modifier" in token:
                # Found a year modifier
                time_modifier = token.get("time_modifier", "").strip('"')
                unit = token.get("unit", "").strip('"')
                if unit == "year":
                    try:
                        year_offset = int(time_modifier)
                    except (ValueError, TypeError):
                        pass
                modifier_idx += 1
            else:
                # Not a modifier token, stop looking
                break

        try:
            month_num = month_name_to_number(month)
            if not month_num:
                return None

            year = base_time.year + year_offset

            # Create date range
            start_date = datetime(year, month_num, day_a, 0, 0, 0)
            end_date = datetime(year, month_num, day_b, 23, 59, 59)

            if end_date < start_date:
                start_date, end_date = end_date, start_date

            start_str = format_datetime_str(start_date)
            end_str = format_datetime_str(end_date)
            jump_count = modifier_idx - i  # from i to modifier_idx (exclusive)
            return [[start_str, end_str]], jump_count

        except Exception as e:
            self.logger.debug(f"Error in _try_merge_from_day_to_day_month: {e}")
            return None

    def _try_merge_month_day_to_day(self, i, tokens, base_time):  # noqa: C901
        """Handle 'month + day + to + day' pattern"""
        n = len(tokens)
        if i >= n:
            return None

        # month (already merged with first day)
        month_day_token = tokens[i]
        if not (
            month_day_token.get("type") == "time_utc"
            and "month" in month_day_token
            and "day" in month_day_token
        ):
            return None

        # Skip empty tokens and find "to"
        to_idx = skip_empty_tokens(tokens, i + 1)
        if to_idx >= n:
            return None

        # Check if it's "to" connector
        to_token = tokens[to_idx]
        if not (
            (to_token.get("type") == "time_connector" and to_token.get("connector", "") == "to")
            or (to_token.get("type") == "token" and to_token.get("value", "").lower() == "to")
        ):
            return None

        # Skip empty tokens and find day_b (might be split)
        day_b_start_idx = skip_empty_tokens(tokens, to_idx + 1)
        if day_b_start_idx >= n:
            return None

        # Extract day_b value (handles split numbers)
        day_b, day_b_end_idx = extract_day_value_from_tokens(tokens, day_b_start_idx)
        if day_b is None:
            return None

        # Extract day_a and month from first token
        day_a = extract_day_value(month_day_token)
        month = month_day_token.get("month", "").strip('"')

        if day_a is None or not month:
            return None

        try:
            month_num = month_name_to_number(month)
            if not month_num:
                return None

            year = base_time.year

            # Create date range
            start_date = datetime(year, month_num, day_a, 0, 0, 0)
            end_date = datetime(year, month_num, day_b, 23, 59, 59)

            if end_date < start_date:
                start_date, end_date = end_date, start_date

            start_str = format_datetime_str(start_date)
            end_str = format_datetime_str(end_date)
            jump_count = day_b_end_idx - i  # from i to day_b_end_idx (exclusive)
            return [[start_str, end_str]], jump_count

        except Exception as e:
            self.logger.debug(f"Error in _try_merge_month_day_to_day: {e}")
            return None

    def _try_merge_day_to_day_month_direct(self, i, tokens, base_time):  # noqa: C901
        """Handle 'day + to + day + month' pattern"""
        n = len(tokens)
        if i >= n:
            return None

        # day_a
        day_a_token = tokens[i]
        if not (day_a_token.get("type") == "time_utc" and "day" in day_a_token):
            return None

        # Skip empty tokens and find "to"
        to_idx = skip_empty_tokens(tokens, i + 1)
        if to_idx >= n:
            return None

        # Check if it's "to" connector
        to_token = tokens[to_idx]
        if not (
            (to_token.get("type") == "time_connector" and to_token.get("connector", "") == "to")
            or (to_token.get("type") == "token" and to_token.get("value", "").lower() == "to")
        ):
            return None

        # Skip empty tokens and find day_b
        day_b_idx = skip_empty_tokens(tokens, to_idx + 1)
        if day_b_idx >= n:
            return None

        # Skip "the" token before day_b if present
        day_b_idx = skip_the_token(tokens, day_b_idx)
        if day_b_idx >= n:
            return None

        # Extract day_b value (handles split numbers)
        day_b, day_b_end_idx = extract_day_value_from_tokens(tokens, day_b_idx)
        if day_b is None:
            return None

        # Skip empty tokens and find month
        month_idx = skip_empty_tokens(tokens, day_b_end_idx)
        if month_idx >= n:
            return None

        # Extract day_a and month
        day_a = extract_day_value(day_a_token)
        month_token = tokens[month_idx]
        month = month_token.get("month", "").strip('"')

        if day_a is None or not month:
            return None

        try:
            month_num = month_name_to_number(month)
            if not month_num:
                return None

            year = base_time.year

            # Create date range
            start_date = datetime(year, month_num, day_a, 0, 0, 0)
            end_date = datetime(year, month_num, day_b, 23, 59, 59)

            if end_date < start_date:
                start_date, end_date = end_date, start_date

            start_str = format_datetime_str(start_date)
            end_str = format_datetime_str(end_date)
            jump_count = month_idx + 1 - i  # from i to month_idx (inclusive)
            return [[start_str, end_str]], jump_count

        except Exception as e:
            self.logger.debug(f"Error in _try_merge_day_to_day_month_direct: {e}")
            return None
