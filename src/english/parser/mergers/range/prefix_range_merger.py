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


class PrefixRangeMerger:
    """Merger for handling '[relative] time_A to time_B' patterns (prefix modifier)"""

    def __init__(self, parsers):
        """
        Initialize prefix range merger

        Args:
            parsers (dict): Dictionary containing various time parsers
        """
        self.parsers = parsers
        self.logger = get_logger(__name__)
        self.range_utils = RangeUtils(parsers)

    def try_merge(self, i, tokens, base_time):  # noqa: C901
        """
        Try to merge "[relative] time_A to time_B" pattern (prefix modifier)

        Args:
            i (int): Current index (pointing to relative modifier)
            tokens (list): Token list
            base_time (datetime): Base time

        Returns:
            tuple: (result, jump_count) or None
        """
        n = len(tokens)
        modifier_token = tokens[i]

        # Check if this is a year/month modifier (not a complete date)
        if (
            "ordinal_position" in modifier_token
            or "offset_year" in modifier_token
            or "offset_month" in modifier_token
        ):
            # Look for time_A after modifier
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
            if time_a.get("type") not in ["time_utc", "time_composite_relative"]:
                return None

            # Look for "to" token
            to_idx = time_a_idx + 1
            while (
                to_idx < n
                and tokens[to_idx].get("type") == "token"
                and tokens[to_idx].get("value", "") == ""
            ):
                to_idx += 1

            if (
                to_idx >= n
                or tokens[to_idx].get("type") != "token"
                or tokens[to_idx].get("value", "").lower() != "to"
            ):
                return None

            # Look for time_B
            time_b_idx = to_idx + 1
            while (
                time_b_idx < n
                and tokens[time_b_idx].get("type") == "token"
                and tokens[time_b_idx].get("value", "") == ""
            ):
                time_b_idx += 1

            if time_b_idx >= n:
                return None

            time_b = tokens[time_b_idx]
            if time_b.get("type") not in ["time_utc", "time_composite_relative"]:
                return None

            # Merge the range with prefix modifier
            result = self.range_utils.merge_time_range(
                time_a, time_b, modifier_token, base_time, prefix_modifier=True
            )
            if result:
                jump_count = time_b_idx + 1 - i
                return result, jump_count

        return None
