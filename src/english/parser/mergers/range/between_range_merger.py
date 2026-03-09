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

from .....core.logger import get_logger
from ...time_utils import (
    skip_empty_tokens,
    parse_datetime_str,
    format_datetime_str,
    get_parser_and_parse,
)
from .range_utils import RangeUtils


class BetweenRangeMerger:
    """Merger for handling 'between time_A and time_B' patterns"""

    def __init__(self, parsers):
        """
        Initialize between range merger

        Args:
            parsers (dict): Dictionary containing various time parsers
        """
        self.parsers = parsers
        self.logger = get_logger(__name__)
        self.range_utils = RangeUtils(parsers)

    def try_merge(self, i, tokens, base_time):  # noqa: C901
        """
        Try to merge "between time_A and time_B" pattern

        Args:
            i (int): Current index (pointing to "between" token)
            tokens (list): Token list
            base_time (datetime): Base time

        Returns:
            tuple: (result, jump_count) or None
        """
        n = len(tokens)
        # Need at least: between + time_A + and + time_B = 4 tokens
        if i + 3 >= n:
            return None

        # Check if next token is a time token
        time_a_idx = i + 1
        time_a = tokens[time_a_idx]
        if time_a.get("type") not in [
            "time_utc",
            "time_composite_relative",
            "time_weekday",
            "time_relative",
        ]:
            return None

        # Look for "and" token after time_A
        and_idx = time_a_idx + 1
        # Skip empty tokens
        while (
            and_idx < n
            and tokens[and_idx].get("type") == "token"
            and tokens[and_idx].get("value", "") == ""
        ):
            and_idx += 1

        if and_idx >= n:
            return None

        and_token = tokens[and_idx]
        # Check for "and" connector (either as token or time_connector)
        if not (
            (and_token.get("type") == "token" and and_token.get("value", "").lower() == "and")
            or (
                and_token.get("type") == "time_connector"
                and and_token.get("connector", "") == "and"
            )
        ):
            return None

        # Check if next token after "and" is a time token
        time_b_idx = and_idx + 1
        # Skip empty tokens
        while (
            time_b_idx < n
            and tokens[time_b_idx].get("type") == "token"
            and tokens[time_b_idx].get("value", "") == ""
        ):
            time_b_idx += 1

        if time_b_idx >= n:
            return None

        time_b = tokens[time_b_idx]
        if time_b.get("type") not in [
            "time_utc",
            "time_composite_relative",
            "time_weekday",
            "time_relative",
        ]:
            return None

        # Parse time_A and time_B
        try:
            result_a = get_parser_and_parse(self.parsers, time_a.get("type"), time_a, base_time)
            result_b = get_parser_and_parse(self.parsers, time_b.get("type"), time_b, base_time)

            if not result_a or not result_b or not result_a[0] or not result_b[0]:
                return None

            # Extract start and end times
            start_time_str = result_a[0][0]
            end_time_str = result_b[0][0]

            # Parse datetime strings
            start_time = parse_datetime_str(start_time_str)
            end_time = parse_datetime_str(end_time_str)

            # If end_time is before start_time, swap them
            if end_time < start_time:
                start_time, end_time = end_time, start_time

            # Check for "on + weekday" pattern after time_B
            weekday_token, weekday_offset = self.range_utils.check_on_weekday_suffix(
                time_b_idx, tokens
            )
            if weekday_token:
                # Apply weekday to the time range
                result = self.range_utils.merge_time_range_with_weekday(
                    time_a, time_b, weekday_token, None, base_time
                )
                if result:
                    jump_count = time_b_idx + 1 + weekday_offset - i
                    return result, jump_count

            # Format result as time range
            start_str = format_datetime_str(start_time)
            end_str = format_datetime_str(end_time)

            jump_count = time_b_idx + 1 - i  # from i to time_b_idx (inclusive)
            return [[start_str, end_str]], jump_count

        except Exception as e:
            self.logger.debug(f"Error in try_merge: {e}")
            return None
