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

from datetime import datetime, timedelta, timezone
from dateutil.relativedelta import relativedelta
from ....core.logger import get_logger
from ..time_utils import (
    parse_datetime_str,
    format_datetime_str,
    parse_datetime_from_str,
    create_day_range,
    ENGLISH_NUMBER_WORDS_BASIC,
)


class DeltaMerger:
    """Merger for handling delta-related time expressions"""

    def __init__(self, parsers, utc_merger=None):
        """
        Initialize delta merger

        Args:
            parsers (dict): Dictionary containing various time parsers
            utc_merger: Reference to UTCMerger for accessing UTC merge methods
        """
        self.parsers = parsers
        self.logger = get_logger(__name__)
        self.utc_merger = utc_merger

    def try_merge_delta_from_time(self, i, tokens, base_time):  # noqa: C901
        """
        Merge time_delta + "from" + time_utc/time_relative pattern

        Examples:
            - "15 minutes from 1pm"
            - "3 years from today"
            - "a day from now"

        Args:
            i: Current token index
            tokens: Token list
            base_time: Base time reference

        Returns:
            (result, skip_count) or None
        """
        n = len(tokens)

        # Handle two cases:
        # 1. time_delta token (e.g., "a day")
        # 2. number + unit tokens (e.g., "15 minutes")

        delta_token = None
        delta_end_idx = i

        if tokens[i].get("type") == "time_delta":
            # Case 1: Direct time_delta token
            delta_token = tokens[i]
        else:
            # Case 2: Try to parse number + unit pattern
            delta_token, delta_end_idx = self.parse_number_unit_delta(i, tokens)
            if delta_token is None:
                return None

        # Look for "from" keyword in next few tokens
        from_idx = None
        for j in range(delta_end_idx + 1, min(delta_end_idx + 4, n)):
            if tokens[j].get("type") == "token" and tokens[j].get("value", "").lower() == "from":
                from_idx = j
                break
            elif tokens[j].get("type") != "token" or tokens[j].get("value", "").strip():
                break

        if from_idx is None:
            return None

        # Look for time_utc or time_relative after "from"
        time_token = None
        time_idx = None
        for j in range(from_idx + 1, min(from_idx + 4, n)):
            token_type = tokens[j].get("type")
            if token_type in ["time_utc", "time_relative"]:
                time_token = tokens[j]
                time_idx = j
                break
            elif token_type != "token" or tokens[j].get("value", "").strip():
                break

        if time_token is None:
            return None

        # Parse the base time first
        time_type = time_token.get("type")
        time_parser = self.parsers.get(time_type)
        if not time_parser:
            return None

        time_result = time_parser.parse(time_token, base_time)
        if not time_result or not time_result[0]:
            return None

        # Use the start time as new base
        new_base_str = time_result[0][0]
        new_base = parse_datetime_str(new_base_str)

        # Apply delta to new base
        delta_parser = self.parsers.get("time_delta")
        if not delta_parser:
            return None

        result = delta_parser.parse(delta_token, new_base)
        if result:
            return result, time_idx - i + 1

        return None

    def try_merge_weekday_from_now(self, i, tokens, base_time):  # noqa: C901
        """
        Merge number + weekday + "from" + time_relative pattern

        Examples:
            - "3 fridays from now" → 第3个星期五
            - "2 sundays from now" → 第2个星期天

        Counting rule:
            - If today < target weekday: this week's target counts as 1st
            - If today >= target weekday: next week's target counts as 1st

        Args:
            i: Current token index
            tokens: Token list
            base_time: Base time reference

        Returns:
            (result, skip_count) or None
        """
        n = len(tokens)

        # Check if current token is a number
        num_token = tokens[i]
        num_value = num_token.get("value", "")

        # Try to parse as number
        try:
            if num_value.isdigit():
                count = int(num_value)
            else:
                # Try word numbers (three, two, etc.)
                count = ENGLISH_NUMBER_WORDS_BASIC.get(num_value.lower())
                if count is None:
                    return None
        except Exception:
            return None

        # Look for weekday word
        weekday_idx = None
        weekday_name = None
        weekday_map = {
            "monday": 0,
            "mondays": 0,
            "tuesday": 1,
            "tuesdays": 1,
            "wednesday": 2,
            "wednesdays": 2,
            "thursday": 3,
            "thursdays": 3,
            "friday": 4,
            "fridays": 4,
            "saturday": 5,
            "saturdays": 5,
            "sunday": 6,
            "sundays": 6,
        }

        for j in range(i + 1, min(i + 4, n)):
            token_value = tokens[j].get("value", "").lower()
            if token_value in weekday_map:
                weekday_idx = j
                weekday_name = weekday_map[token_value]
                break
            elif tokens[j].get("type") != "token" or token_value.strip():
                break

        if weekday_idx is None:
            return None

        # Look for "from"
        from_idx = None
        for j in range(weekday_idx + 1, min(weekday_idx + 4, n)):
            if tokens[j].get("type") == "token" and tokens[j].get("value", "").lower() == "from":
                from_idx = j
                break
            elif tokens[j].get("type") != "token" or tokens[j].get("value", "").strip():
                break

        if from_idx is None:
            return None

        # Look for time_relative (now/today)
        time_idx = None
        for j in range(from_idx + 1, min(from_idx + 4, n)):
            if tokens[j].get("type") == "time_relative":
                time_idx = j
                break
            elif tokens[j].get("type") != "token" or tokens[j].get("value", "").strip():
                break

        if time_idx is None:
            return None

        # Calculate the Nth occurrence of target weekday
        if not isinstance(base_time, datetime):
            base_time = parse_datetime_str(base_time)

        current_weekday = base_time.weekday()  # 0=Monday, 6=Sunday
        target_weekday = weekday_name

        # Calculate days to first occurrence
        if current_weekday < target_weekday:
            # Target is later this week
            days_to_first = target_weekday - current_weekday
        else:
            # Target is next week
            days_to_first = 7 - current_weekday + target_weekday

        # Calculate days to Nth occurrence
        total_days = days_to_first + (count - 1) * 7

        result_date = base_time + timedelta(days=total_days)
        result_date, end_date = create_day_range(result_date)

        result_str = format_datetime_str(result_date)
        end_str = format_datetime_str(end_date)

        return [[result_str, end_str]], time_idx - i + 1

    def parse_number_unit_delta(self, i, tokens):  # noqa: C901
        """
        Parse number + unit pattern into time_delta token

        Examples:
            - "15 minutes" → {'type': 'time_delta', 'minute': '15'}
            - "3 years" → {'type': 'time_delta', 'year': '3'}
            - "a day" → {'type': 'time_delta', 'day': '1'}

        Args:
            i: Starting token index
            tokens: Token list

        Returns:
            (delta_token, end_index) or (None, None)
        """
        n = len(tokens)

        # Try to parse number (handle multi-digit numbers like "15" = "1" + "5")
        num_value = None
        num_end_idx = i

        # Check if current token is a number
        if tokens[i].get("type") == "token":
            value = tokens[i].get("value", "")
            if value.isdigit():
                # Try to build multi-digit number
                num_str = value
                j = i + 1
                while j < n and tokens[j].get("type") == "token":
                    next_value = tokens[j].get("value", "")
                    if next_value.isdigit():
                        num_str += next_value
                        num_end_idx = j
                        j += 1
                    elif next_value.strip() == "":
                        # Skip empty tokens
                        j += 1
                    else:
                        break

                num_value = int(num_str)
            else:
                # Try word numbers
                word_to_num = {
                    "a": 1,
                    "an": 1,
                    "one": 1,
                    "two": 2,
                    "three": 3,
                    "four": 4,
                    "five": 5,
                    "six": 6,
                    "seven": 7,
                    "eight": 8,
                    "nine": 9,
                    "ten": 10,
                }
                num_value = word_to_num.get(value.lower())

        if num_value is None:
            return None, None

        # Look for unit in next few tokens (starting from after the number)
        unit_map = {
            "minute": "minute",
            "minutes": "minute",
            "hour": "hour",
            "hours": "hour",
            "day": "day",
            "days": "day",
            "week": "week",
            "weeks": "week",
            "month": "month",
            "months": "month",
            "year": "year",
            "years": "year",
        }

        unit = None
        unit_idx = None

        for j in range(num_end_idx + 1, min(num_end_idx + 4, n)):
            if tokens[j].get("type") == "token":
                value = tokens[j].get("value", "").lower()
                if value in unit_map:
                    unit = unit_map[value]
                    unit_idx = j
                    break
            elif tokens[j].get("type") != "token" or tokens[j].get("value", "").strip():
                break

        if unit is None:
            return None, None

        # Create time_delta token
        delta_token = {"type": "time_delta", unit: str(num_value)}

        return delta_token, unit_idx

    def try_merge_time_for_relative(self, i, tokens, base_time):  # noqa: C901
        """
        Merge time_utc + "for" + time_relative
        Example: "8 o'clock for tomorrow" -> tomorrow 8:00

        Args:
            i (int): Current token index
            tokens (list): List of tokens
            base_time (datetime): Base time reference

        Returns:
            tuple: (merged_results_list, jump_count) or None
        """
        try:
            n = len(tokens)
            if i + 2 >= n:
                return None

            cur = tokens[i]
            if cur.get("type") != "time_utc":
                return None

            # Look for "for" token (skip empty tokens and non-time words like "alarm")
            j = i + 1
            while j < n:
                tok = tokens[j]
                if tok.get("type") == "token":
                    val = tok.get("value", "").strip()
                    if val == "for":
                        break  # Found "for"
                    elif val == "" or val in ["alarm", "reminder", "meeting", "event"]:
                        j += 1  # Skip these words
                        continue
                    else:
                        return None  # Other words, not a match
                else:
                    return None  # Non-token type
                j += 1

            if j >= n:
                return None

            for_token = tokens[j]
            if for_token.get("type") != "token" or for_token.get("value", "").lower() != "for":
                return None

            # Look for relative token (skip empty tokens)
            k = j + 1
            while (
                k < n
                and tokens[k].get("type") == "token"
                and tokens[k].get("value", "").strip() == ""
            ):
                k += 1

            if k >= n:
                return None

            relative_token = tokens[k]
            if relative_token.get("type") not in ["time_relative", "time_weekday"]:
                return None

            # Merge time_utc with relative
            if self.utc_merger:
                if relative_token.get("type") == "time_relative":
                    result = self.utc_merger.merge_utc_with_relative(cur, relative_token, base_time)
                else:  # time_weekday
                    result = self.utc_merger.merge_utc_with_weekday(cur, relative_token, base_time)
            else:
                return None

            if result:
                return (result, k + 1)  # Skip all tokens from i to k

            return None

        except Exception as e:
            self.logger.debug(f"Error in try_merge_time_for_relative: {e}")
            return None

    def merge_by_future_time(self, i, tokens, base_time):  # noqa: C901
        """
        合并"by + 未来时间"的表达
        例如: "by tomorrow", "by next Monday", "by the end of next month"

        逻辑:
        1. 检查当前token是否是"by"
        2. 查找下一个时间token
        3. 解析该时间token
        4. 判断是否为未来时间
        5. 如果是未来时间,返回从base_time到该时间的起始点

        Args:
            i (int): Current token index
            tokens (list): List of tokens
            base_time (datetime): Base time reference

        Returns:
            tuple: (result, jump_count) or None
        """
        try:
            n = len(tokens)
            if i >= n:
                return None

            # 1. 检查当前token是否是"by"
            cur = tokens[i]
            if cur.get("type") != "token" or cur.get("value", "").lower() != "by":
                return None

            # 2. 查找下一个时间token
            time_token_idx = i + 1
            # 跳过空token和"the"等
            while time_token_idx < n and tokens[time_token_idx].get("type") == "token":
                token_value = tokens[time_token_idx].get("value", "").strip().lower()
                if token_value in ["", "the", "a", "an"]:
                    time_token_idx += 1
                    continue
                else:
                    break

            if time_token_idx >= n:
                return None

            time_token = tokens[time_token_idx]
            time_type = time_token.get("type")

            # 3. 检查是否是时间类型
            if time_type not in [
                "time_relative",
                "time_weekday",
                "time_utc",
                "time_composite_relative",
                "time_holiday",
            ]:
                return None

            # 4. 避免重复处理: 如果已经有range="by"标记,让原有逻辑处理
            if time_token.get("range") == "by":
                return None

            # 5. 解析该时间token
            parser = self.parsers.get(time_type)
            if not parser:
                return None

            result = parser.parse(time_token, base_time)
            if not result or not result[0]:
                return None

            # 6. 判断是否为未来时间
            from datetime import datetime

            start_str = result[0][0]

            # Parse the start time
            try:
                start_time = parse_datetime_from_str(start_str)
                # 确保时区信息一致
                if start_time.tzinfo is None:
                    from datetime import timezone

                    start_time = start_time.replace(tzinfo=timezone.utc)
            except Exception:
                return None

            # 检查是否是未来时间
            if start_time <= base_time:
                return None

            # 7. 特殊处理: 如果是boundary表达,使用起始点而不是结束点
            if time_type == "time_composite_relative" and time_token.get("boundary"):
                boundary = time_token.get("boundary")
                if boundary == "end":
                    # 对于"end"边界,使用起始点
                    # 例如: "by the end of next month" -> 从现在到下月21日
                    # result已经是时间段,取起始点
                    start_str = result[0][0]

            # 8. 返回从base_time到该时间的起始点
            result = [[format_datetime_str(base_time), start_str]]
            consumed = time_token_idx - i + 1

            return result, consumed

        except Exception as e:
            self.logger.debug(f"Error in merge_by_future_time: {e}")
            return None
