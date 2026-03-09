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
from ...time_utils import skip_empty_tokens
from .range_utils import RangeUtils


class FromToRangeMerger:
    """Merger for handling 'from time_A to time_B' patterns"""

    def __init__(self, parsers):
        """
        Initialize from-to range merger

        Args:
            parsers (dict): Dictionary containing various time parsers
        """
        self.parsers = parsers
        self.logger = get_logger(__name__)
        self.range_utils = RangeUtils(parsers)

    def try_merge(self, i, tokens, base_time):  # noqa: C901
        """
        Try to merge "from time_A to time_B [relative]" pattern

        Args:
            i (int): Current index (pointing to "from" token)
            tokens (list): Token list
            base_time (datetime): Base time

        Returns:
            tuple: (result, jump_count) or None
        """
        n = len(tokens)
        # Need at least: from + time_A + to + time_B = 4 tokens
        if i + 3 >= n:
            return None

        # Check if next token is a time token
        time_a_idx = i + 1
        # Skip empty tokens
        while (
            time_a_idx < n
            and tokens[time_a_idx].get("type") == "token"
            and tokens[time_a_idx].get("value", "") == ""
        ):
            time_a_idx += 1

        if time_a_idx >= n:
            return None

        time_a = tokens[time_a_idx]
        if time_a.get("type") not in [
            "time_utc",
            "time_composite_relative",
            "time_weekday",
            "time_relative",
        ]:
            return None

        # Check if this is a "from day to day of month" pattern
        # If so, let day_range_merger handle it
        if self.range_utils.is_from_day_to_day_of_month_pattern(i, tokens):
            return None

        # Look for "to" token after time_A, skipping any modifier tokens
        to_idx = time_a_idx + 1
        while to_idx < n:
            token = tokens[to_idx]
            if token.get("type") == "token" and token.get("value", "") == "":
                # Skip empty tokens
                to_idx += 1
            elif (token.get("type") == "token" and token.get("value", "").lower() == "to") or (
                token.get("type") == "time_connector" and token.get("connector", "") == "to"
            ):
                # Found "to" token
                break
            elif token.get("type") in ["time_relative", "time_composite_relative"]:
                # Skip modifier tokens (we'll handle them later)
                to_idx += 1
            else:
                # Not a valid token in the pattern
                return None

        if to_idx >= n:
            return None

        # Check if next token after "to" is a time token
        time_b_idx = to_idx + 1
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

        # Check for optional relative modifier after time_B
        # Also check if time_B itself has a modifier (e.g., "july 6 last year")
        modifier_token = None
        jump_count = time_b_idx + 1 - i  # Default: from i to time_b_idx (inclusive)

        # Check if time_B has offset_year or offset_month (it's already a composite_relative)
        if time_b.get("type") == "time_composite_relative" and (
            "offset_year" in time_b or "offset_month" in time_b
        ):
            # time_B already has a modifier, use it for the entire range
            modifier_token = time_b
        else:
            # Look for modifier token after time_B (skip empty tokens)
            modifier_idx = time_b_idx + 1
            while modifier_idx < n:
                token = tokens[modifier_idx]
                if token.get("type") == "token" and token.get("value", "") == "":
                    # Skip empty tokens
                    modifier_idx += 1
                elif token.get("type") in ["time_relative", "time_composite_relative"]:
                    # Found a modifier token
                    modifier_token = token
                    jump_count = modifier_idx + 1 - i
                    break
                else:
                    # Not a modifier token, stop looking
                    break

        # Check if time_A has a modifier after it (e.g., "august 20 last year")
        start_modifier_token = None
        if time_a.get("type") == "time_utc":
            # Look for modifier token after time_A but before "to"
            start_modifier_idx = time_a_idx + 1
            while start_modifier_idx < to_idx:
                token = tokens[start_modifier_idx]
                if token.get("type") == "token" and token.get("value", "") == "":
                    # Skip empty tokens
                    start_modifier_idx += 1
                elif token.get("type") in ["time_relative", "time_composite_relative"]:
                    # Found a modifier token for start time
                    start_modifier_token = token
                    break
                else:
                    # Not a modifier token, stop looking
                    break

        # Check if time_B has a modifier after it (e.g., "november 10 this year")
        end_modifier_token = None
        if time_b.get("type") == "time_utc":
            # Look for modifier token after time_B
            end_modifier_idx = time_b_idx + 1
            while end_modifier_idx < n:
                token = tokens[end_modifier_idx]
                if token.get("type") == "token" and token.get("value", "") == "":
                    # Skip empty tokens
                    end_modifier_idx += 1
                elif token.get("type") in ["time_relative", "time_composite_relative"]:
                    # Found a modifier token for end time
                    end_modifier_token = token
                    break
                else:
                    # Not a modifier token, stop looking
                    break

        # Check if time_A has offset_year or offset_month (e.g., "last year april 3 to may 1")
        if (
            time_a.get("type") == "time_composite_relative"
            and ("offset_year" in time_a or "offset_month" in time_a)
        ) or (
            time_a.get("type") == "time_utc"
            and ("offset_year" in time_a or "offset_month" in time_a)
        ):
            # time_A has a modifier, use it for the entire range
            modifier_token = time_a
        elif start_modifier_token and not end_modifier_token:
            # time_A has a separate modifier token (e.g., "august 20 last year")
            modifier_token = start_modifier_token

        # Check for weekday token BEFORE "from" (e.g., "Thursday from 9:30 to 11:00")
        weekday_token = self.range_utils.check_weekday_prefix(i, tokens)
        if weekday_token:
            # Apply weekday to the time range
            result = self.range_utils.merge_time_range_with_weekday(
                time_a, time_b, weekday_token, modifier_token, base_time
            )
            if result:
                return result, jump_count

        # Check for "on + weekday" pattern after time_B
        weekday_token, weekday_offset = self.range_utils.check_on_weekday_suffix(time_b_idx, tokens)
        if weekday_token:
            jump_count += weekday_offset
            # Apply weekday to the time range
            result = self.range_utils.merge_time_range_with_weekday(
                time_a, time_b, weekday_token, modifier_token, base_time
            )
            if result:
                return result, jump_count

        # Merge the range
        result = self.range_utils.merge_time_range(
            time_a,
            time_b,
            modifier_token,
            base_time,
            False,
            start_modifier_token,
            end_modifier_token,
        )
        if result:
            return result, jump_count

        return None
