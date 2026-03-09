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
from ...time_utils import month_name_to_number, format_datetime_str
from .range_utils import RangeUtils


class CompactRangeMerger:
    """Merger for handling compact date range patterns like 'July 13-15'"""

    def __init__(self, parsers):
        """
        Initialize compact range merger

        Args:
            parsers (dict): Dictionary containing various time parsers
        """
        self.parsers = parsers
        self.logger = get_logger(__name__)
        self.range_utils = RangeUtils(parsers)

    def try_merge(self, i, tokens, base_time):
        """
        Try to merge compact date range patterns like "July 13-15" or "from July 13-15"

        Args:
            i (int): Current index
            tokens (list): Token list
            base_time (datetime): Base time

        Returns:
            tuple: (result, jump_count) or None
        """
        n = len(tokens)
        if i >= n:
            return None

        # Pattern 1: "from July 13-15"
        if (
            i < n
            and tokens[i].get("type") == "time_connector"
            and tokens[i].get("connector", "") == "from"
        ):
            return self._try_merge_from_compact_date_range(i, tokens, base_time)

        # Pattern 2: "July 13-15" or "August 5-7"
        if i < n and tokens[i].get("type") == "time_utc" and "month" in tokens[i]:
            return self._try_merge_month_compact_date_range(i, tokens, base_time)

        return None

    def _try_merge_from_compact_date_range(self, i, tokens, base_time):
        """Handle 'from + month + day1 + dash + day2' pattern"""
        n = len(tokens)
        if i + 3 >= n:
            return None

        # from + month + day1 + dash + day2
        from_token = tokens[i]
        month_token = tokens[i + 1]
        day1_token = tokens[i + 2]
        day2_token = tokens[i + 3]

        # Check if we have the right pattern
        if not (
            (
                from_token.get("type") == "time_connector"
                and from_token.get("connector", "") == "from"
            )
            or (from_token.get("type") == "token" and from_token.get("value", "").lower() == "from")
        ):
            return None

        if not (month_token.get("type") == "time_utc" and "month" in month_token):
            return None

        # Check if day1 and day2 are incorrectly parsed (month+day instead of just day)
        day1 = self.range_utils.extract_day_from_incorrect_parsing(day1_token)
        day2 = self.range_utils.extract_day_from_incorrect_parsing(day2_token)

        if day1 is None or day2 is None:
            return None

        # Extract month
        month = month_token.get("month", "").strip('"')
        if not month:
            return None

        try:
            month_num = month_name_to_number(month)
            if not month_num:
                return None

            year = base_time.year

            # Create date range
            start_date = datetime(year, month_num, day1, 0, 0, 0)
            end_date = datetime(year, month_num, day2, 23, 59, 59)

            if end_date < start_date:
                start_date, end_date = end_date, start_date

            start_str = format_datetime_str(start_date)
            end_str = format_datetime_str(end_date)
            jump_count = 4  # from i to i+3 (inclusive)
            return [[start_str, end_str]], jump_count

        except Exception as e:
            self.logger.debug(f"Error in _try_merge_from_compact_date_range: {e}")
            return None

    def _try_merge_month_compact_date_range(self, i, tokens, base_time):  # noqa: C901
        """Handle 'month + day1 + dash + day2' pattern"""
        n = len(tokens)
        if i + 1 >= n:
            return None

        month_token = tokens[i]

        # Check if we have the right pattern
        if not (month_token.get("type") == "time_utc" and "month" in month_token):
            return None

        # Extract month from first token
        month = month_token.get("month", "").strip('"')
        if not month:
            return None

        # Pattern 1: "July 13-15" - both tokens have month and day
        if (
            "day" in month_token
            and i + 1 < n
            and tokens[i + 1].get("type") == "time_utc"
            and "month" in tokens[i + 1]
            and "day" in tokens[i + 1]
        ):

            day1_token = tokens[i + 1]

            # For "July 13-15", the tokens are:
            # Token 1: month='july', day='1' (July 1)
            # Token 2: month='3', day='15' (March 15)
            # We need to extract: day1=13, day2=15

            # Extract day1 from first token's day part
            day1_str = month_token.get("day", "").strip('"')
            if not day1_str:
                return None

            # Extract day2 from second token's day part
            day2_str = day1_token.get("day", "").strip('"')
            if not day2_str:
                return None

            # Extract the month part from second token to get the missing digit
            month2_str = day1_token.get("month", "").strip('"')
            if not month2_str:
                return None

            try:
                # Reconstruct day1: "1" + "3" = "13"
                day1 = int(day1_str + month2_str)
                day2 = int(day2_str)

                month_num = month_name_to_number(month)
                if not month_num:
                    return None

                year = base_time.year

                # Create date range
                start_date = datetime(year, month_num, day1, 0, 0, 0)
                end_date = datetime(year, month_num, day2, 23, 59, 59)

                if end_date < start_date:
                    start_date, end_date = end_date, start_date

                start_str = format_datetime_str(start_date)
                end_str = format_datetime_str(end_date)
                jump_count = 2  # from i to i+1 (inclusive)
                return [[start_str, end_str]], jump_count

            except Exception as e:
                self.logger.debug(f"Error in _try_merge_month_compact_date_range (pattern 1): {e}")
                return None

        # Pattern 2: "August 5-7" - first token has only month, second has month+day
        elif (
            i + 1 < n
            and "day" not in month_token  # First token has no day
            and tokens[i + 1].get("type") == "time_utc"
            and "month" in tokens[i + 1]
            and "day" in tokens[i + 1]
        ):

            day_token = tokens[i + 1]

            # For "August 5-7", the tokens are:
            # Token 1: month='august' (August)
            # Token 2: month='5', day='7' (May 7)
            # We need to extract: day1=5, day2=7

            # Extract day1 and day2 from second token
            day1_str = day_token.get("month", "").strip('"')
            day2_str = day_token.get("day", "").strip('"')

            if not day1_str or not day2_str:
                return None

            try:
                day1 = int(day1_str)
                day2 = int(day2_str)

                month_num = month_name_to_number(month)
                if not month_num:
                    return None

                year = base_time.year

                # Create date range
                start_date = datetime(year, month_num, day1, 0, 0, 0)
                end_date = datetime(year, month_num, day2, 23, 59, 59)

                if end_date < start_date:
                    start_date, end_date = end_date, start_date

                start_str = format_datetime_str(start_date)
                end_str = format_datetime_str(end_date)
                jump_count = 2  # from i to i+1 (inclusive)
                return [[start_str, end_str]], jump_count

            except Exception as e:
                self.logger.debug(f"Error in _try_merge_month_compact_date_range (pattern 2): {e}")
                return None

        return None
