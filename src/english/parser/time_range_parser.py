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

from datetime import timedelta
from dateutil.relativedelta import relativedelta
from .base_parser import BaseParser


class TimeRangeParser(BaseParser):
    """
    Time range parser for English

    Handles time range adverbs and expressions like:
    - recently (7 days ago to now)
    - lately (7 days ago to now)
    - recent week (past 7 days)
    - recent 30 days (past 30 days)
    - past week (past 7 days)
    """

    def __init__(self):
        """Initialize time range parser"""
        super().__init__()

    def parse(self, token, base_time):
        """
        Parse time range expression

        Args:
            token (dict): Time expression token containing either:
                - 'range_days' field (for simple adverbs like "recently")
                - 'offset_direction', 'offset', 'unit' fields (for expressions like "recent three months")
            base_time (datetime): Base time reference

        Returns:
            list: Time range list in format [[start_time_str, end_time_str]]
        """
        # Check for new format first (offset_direction + offset + unit)
        if "offset_direction" in token and "offset" in token and "unit" in token:
            return self._parse_range_with_offset(token, base_time)

        # Fall back to old format (range_days)
        range_days_str = token.get("range_days", "").strip('"')

        if not range_days_str:
            return []

        try:
            # Parse the number of days
            range_days = int(range_days_str)

            # Calculate start time: N days ago at 00:00:00
            start_time = base_time - timedelta(days=range_days)
            start_time = start_time.replace(hour=0, minute=0, second=0, microsecond=0)

            # End time is the current base_time (or end of current day)
            end_time = base_time.replace(hour=23, minute=59, second=59, microsecond=0)

            return self._format_time_result(start_time, end_time)

        except (ValueError, TypeError):
            return []

    def _parse_range_with_offset(self, token, base_time):  # noqa: C901
        """
        Parse time range with offset direction, offset, and unit

        Args:
            token (dict): Token with 'offset_direction', 'offset', 'unit' fields
            base_time (datetime): Base time reference

        Returns:
            list: Time range list
        """
        try:
            offset_direction = token.get("offset_direction", "-1").strip('"')
            offset = int(token.get("offset", "1").strip('"'))
            unit = token.get("unit", "day").strip('"')

            # Determine if it's past (-1) or future (1)
            # Handle both numeric and string offset_direction
            if offset_direction in ["-1", "past", "last", "recent"]:
                direction = -1
            elif offset_direction in ["1", "future", "next", "upcoming", "within"]:
                direction = 1
            else:
                try:
                    direction = int(offset_direction)
                except (ValueError, TypeError):
                    direction = 1  # Default to future

            # Calculate the target time period
            # Following Chinese FST logic: recent/previous + time unit = from (now - time) to now
            # 参考中文FST逻辑：recent/previous + 时间段 = 从(现在-时间段)到现在
            if unit == "day":
                # 统一处理：返回从起点到终点的时间段
                if direction < 0:  # past/last/recent
                    start_time = base_time - timedelta(days=offset)
                    end_time = base_time
                else:  # next/future/upcoming
                    start_time = base_time
                    end_time = base_time + timedelta(days=offset)
            elif unit == "week":
                # 统一处理：返回从起点到终点的时间段
                if direction < 0:  # past/last/recent
                    start_time = base_time - timedelta(weeks=offset)
                    end_time = base_time
                else:  # next/future/upcoming
                    start_time = base_time
                    end_time = base_time + timedelta(weeks=offset)
            elif unit == "month":
                # 统一处理：返回从起点到终点的时间段
                if direction < 0:  # past/last/recent
                    start_time = base_time - relativedelta(months=offset)
                    end_time = base_time
                else:  # next/future/upcoming
                    start_time = base_time
                    end_time = base_time + relativedelta(months=offset)
            elif unit == "year":
                # 统一处理：返回从起点到终点的时间段
                if direction < 0:  # past/last/recent
                    start_time = base_time - relativedelta(years=offset)
                    end_time = base_time
                else:  # next/future/upcoming
                    start_time = base_time
                    end_time = base_time + relativedelta(years=offset)
            elif unit == "quarter":
                if offset == 1:
                    # 单数：返回目标时间点所在的整个季度范围
                    time_diff = relativedelta(months=3 * 1 * direction)
                    target_time = base_time + time_diff
                    # Compute the quarter month index (1,4,7,10)
                    q_idx = ((target_time.month - 1) // 3) * 3 + 1
                    start_of_quarter_month = target_time.replace(month=q_idx)
                    # Start and end via month range for start month, then add 2 months for end
                    start_time, _ = self._get_month_range(start_of_quarter_month)
                    # End month is start month + 2
                    from dateutil.relativedelta import relativedelta as _rd

                    end_month_time = start_of_quarter_month + _rd(months=2)
                    _, end_time = self._get_month_range(end_month_time)
                else:
                    # 多数：返回从起点到终点的时间段
                    if direction < 0:  # past/last/recent
                        start_time = base_time - relativedelta(months=3 * offset)
                        end_time = base_time
                    else:  # next/future/upcoming
                        start_time = base_time
                        end_time = base_time + relativedelta(months=3 * offset)
            elif unit == "hour":
                if offset == 1:
                    # 单数：返回从起点到终点的时间段（过去一小时到现在）
                    if direction < 0:  # past/last/recent
                        start_time = base_time - timedelta(hours=1)
                        end_time = base_time
                    else:  # next/future/upcoming
                        start_time = base_time
                        end_time = base_time + timedelta(hours=1)
                else:
                    # 多数：返回从起点到终点的时间段
                    if direction < 0:  # past/last/recent
                        start_time = base_time - timedelta(hours=offset)
                        end_time = base_time
                    else:  # next/future/upcoming
                        start_time = base_time
                        end_time = base_time + timedelta(hours=offset)
            elif unit == "minute":
                if offset == 1:
                    # 单数：返回从起点到终点的时间段（过去一分钟到现在）
                    if direction < 0:  # past/last/recent
                        start_time = base_time - timedelta(minutes=1)
                        end_time = base_time
                    else:  # next/future/upcoming
                        start_time = base_time
                        end_time = base_time + timedelta(minutes=1)
                else:
                    # 多数：返回从起点到终点的时间段
                    if direction < 0:  # past/last/recent
                        start_time = base_time - timedelta(minutes=offset)
                        end_time = base_time
                    else:  # next/future/upcoming
                        start_time = base_time
                        end_time = base_time + timedelta(minutes=offset)
            elif unit == "second":
                if offset == 1:
                    # 单数：返回从起点到终点的时间段（过去一秒到现在）
                    if direction < 0:  # past/last/recent
                        start_time = base_time - timedelta(seconds=1)
                        end_time = base_time
                    else:  # next/future/upcoming
                        start_time = base_time
                        end_time = base_time + timedelta(seconds=1)
                else:
                    # 多数：返回从起点到终点的时间段
                    if direction < 0:  # past/last/recent
                        start_time = base_time - timedelta(seconds=offset)
                        end_time = base_time
                    else:  # next/future/upcoming
                        start_time = base_time
                        end_time = base_time + timedelta(seconds=offset)
            else:
                return []

            return self._format_time_result(start_time, end_time)

        except (ValueError, TypeError):
            return []

    def _parse_range_with_unit(self, token, base_time):
        """
        Parse time range with value and unit (legacy format)

        Args:
            token (dict): Token with 'value', 'unit', 'range_type' fields
            base_time (datetime): Base time reference

        Returns:
            list: Time range list
        """
        try:
            value = int(token.get("value", "1").strip('"'))
            unit = token.get("unit", "day").strip('"')
            token.get("range_type", "ago").strip('"')  # legacy compatibility

            # Calculate start time based on unit
            if unit == "day":
                start_time = base_time - timedelta(days=value)
            elif unit == "week":
                start_time = base_time - timedelta(weeks=value)
            elif unit == "month":
                start_time = base_time - relativedelta(months=value)
            elif unit == "year":
                start_time = base_time - relativedelta(years=value)
            elif unit == "hour":
                start_time = base_time - timedelta(hours=value)
            elif unit == "minute":
                start_time = base_time - timedelta(minutes=value)
            elif unit == "second":
                start_time = base_time - timedelta(seconds=value)
            else:
                return []

            # Set start time to beginning of day but keep base_time hour
            start_time = start_time.replace(hour=base_time.hour, minute=0, second=0, microsecond=0)

            # End time is the base_time itself (not end of day)
            # "recent 30 days" means from 30 days ago to now (base_time)
            end_time = base_time

            return self._format_time_result(start_time, end_time)

        except (ValueError, TypeError):
            return []
