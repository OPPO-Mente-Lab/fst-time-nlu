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


class ToRangeMerger:
    """Merger for handling 'time_A to time_B' patterns (without 'from')"""

    def __init__(self, parsers):
        """
        Initialize to range merger

        Args:
            parsers (dict): Dictionary containing various time parsers
        """
        self.parsers = parsers
        self.logger = get_logger(__name__)
        self.range_utils = RangeUtils(parsers)

    def try_merge(self, i, tokens, base_time):  # noqa: C901
        """
        Try to merge "time_A to time_B [relative]" pattern (without "from")

        Args:
            i (int): Current index (pointing to time_A)
            tokens (list): Token list
            base_time (datetime): Base time

        Returns:
            tuple: (result, jump_count) or None
        """
        n = len(tokens)
        time_a = tokens[i]

        # Look for "to" token after time_A
        to_idx = i + 1
        # Skip empty tokens
        while (
            to_idx < n
            and tokens[to_idx].get("type") == "token"
            and tokens[to_idx].get("value", "") == ""
        ):
            to_idx += 1

        if to_idx >= n:
            return None

        to_token = tokens[to_idx]
        # Check for "to" connector (either as token or time_connector) or dash
        if not (
            (to_token.get("type") == "token" and to_token.get("value", "").lower() == "to")
            or (to_token.get("type") == "time_connector" and to_token.get("connector", "") == "to")
            or (to_token.get("type") == "token" and to_token.get("value", "") == "-")
        ):
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
        jump_count = time_b_idx + 1 - i

        # Check if time_B has offset_year or offset_month (it's already a composite_relative)
        if time_b.get("type") == "time_composite_relative" and (
            "offset_year" in time_b or "offset_month" in time_b
        ):
            # time_B already has a modifier, use it for the entire range
            modifier_token = time_b
        elif time_b_idx + 1 < n:
            next_token = tokens[time_b_idx + 1]
            if next_token.get("type") in ["time_relative", "time_composite_relative"]:
                modifier_token = next_token
                jump_count = time_b_idx + 2 - i

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
            time_a, time_b, modifier_token, base_time, False, None, None
        )
        if result:
            return result, jump_count

        return None
