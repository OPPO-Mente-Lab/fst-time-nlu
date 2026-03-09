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
from ..time_utils import (
    skip_empty_tokens,
    skip_the_token,
    is_digit_sequence,
    extract_day_value_from_tokens,
    extract_day_value,
    get_month_range,
    month_name_to_number,
    parse_datetime_str,
    format_datetime_str,
)
from .range.from_to_range_merger import FromToRangeMerger
from .range.between_range_merger import BetweenRangeMerger
from .range.to_range_merger import ToRangeMerger
from .range.prefix_range_merger import PrefixRangeMerger
from .range.compact_range_merger import CompactRangeMerger
from .range.day_range_merger import DayRangeMerger
from .range.range_utils import RangeUtils


class RangeMerger:
    """Merger for handling time range expressions"""

    def __init__(self, parsers):
        """
        Initialize range merger

        Args:
            parsers (dict): Dictionary containing various time parsers
        """
        self.parsers = parsers
        self.logger = get_logger(__name__)
        # Initialize sub-mergers
        self.from_to_merger = FromToRangeMerger(parsers)
        self.between_merger = BetweenRangeMerger(parsers)
        self.to_merger = ToRangeMerger(parsers)
        self.prefix_merger = PrefixRangeMerger(parsers)
        self.compact_merger = CompactRangeMerger(parsers)
        self.day_merger = DayRangeMerger(parsers)
        self.range_utils = RangeUtils(parsers)

    def try_merge(self, i, tokens, base_time):
        """
        Try to merge time range expressions

        Args:
            i (int): Current token index
            tokens (list): List of tokens
            base_time (datetime): Base time reference

        Returns:
            tuple: (merged_results_list, jump_count) or None
        """
        n = len(tokens)
        if i >= n:
            return None

        cur = tokens[i]
        cur_type = cur.get("type")

        # Rule 5: "from time_A to time_B [relative]" pattern
        if (cur_type == "token" and cur.get("value", "").lower() == "from") or (
            cur_type == "time_connector" and cur.get("connector", "") == "from"
        ):
            range_result = self.from_to_merger.try_merge(i, tokens, base_time)
            if range_result:
                return range_result

        # Rule 6: "between time_A and time_B" pattern
        if (cur_type == "token" and cur.get("value", "").lower() == "between") or (
            cur_type == "time_connector" and cur.get("connector", "") == "between"
        ):
            range_result = self.between_merger.try_merge(i, tokens, base_time)
            if range_result:
                return range_result

        # Rule 7: "[relative] time_A to time_B" pattern (prefix modifier)
        if cur_type == "time_composite_relative":
            range_result = self.prefix_merger.try_merge(i, tokens, base_time)
            if range_result:
                return range_result

        # Rule 7: "time_A to time_B [relative]" pattern (without "from")
        if cur_type in ["time_utc", "time_composite_relative"]:
            range_result = self.to_merger.try_merge(i, tokens, base_time)
            if range_result:
                return range_result

        # Rule 8: "day + to + day + month" pattern
        if cur_type in ["time_utc", "time_connector", "token"]:
            range_result = self.day_merger.try_merge(i, tokens, base_time)
            if range_result:
                return range_result

        # Rule 9: "compact date range" pattern
        if cur_type in ["time_utc", "time_connector"]:
            compact_result = self.compact_merger.try_merge(i, tokens, base_time)
            if compact_result:
                return compact_result

        return None

    def try_merge_weekday_time_range(self, i, tokens, base_time):
        """
        处理 "weekday + from/between + time_range" 模式

        Example: "Thursday from 9:30 to 11:00"
        """
        n = len(tokens)
        if i + 4 >= n:
            return None

        # Skip empty tokens
        idx = i + 1
        while idx < n and tokens[idx].get("type") == "token" and tokens[idx].get("value", "") == "":
            idx += 1

        if idx >= n:
            return None

        # Check for "from" or "between"
        connector = tokens[idx]
        if not (
            connector.get("type") == "time_connector"
            and connector.get("connector", "") in ["from", "between"]
        ):
            return None

        # Try to parse the time range starting from connector
        if connector.get("connector", "") == "from":
            range_result = self.from_to_merger.try_merge(idx, tokens, base_time)
        else:  # between
            range_result = self.between_merger.try_merge(idx, tokens, base_time)

        if not range_result:
            return None

        result, jump_count = range_result

        # Apply weekday to the parsed time range
        # Parse the time range result to extract start/end times
        # Then combine with weekday
        # (implementation similar to _merge_time_range_with_weekday)

        return result, jump_count + (idx - i)
