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
from ....core.logger import get_logger
from ..time_utils import (
    parse_datetime_str,
    format_datetime_str,
    parse_datetime_from_str,
    create_day_range,
    ENGLISH_NUMBER_WORDS_EXTENDED,
)


class DurationMerger:
    """Merger for handling duration-related time expressions"""

    def __init__(self, parsers):
        """
        Initialize duration merger

        Args:
            parsers (dict): Dictionary containing various time parsers
        """
        self.parsers = parsers
        self.logger = get_logger(__name__)

    def parse_duration(self, start_idx, tokens):  # noqa: C901
        """
        解析时间长度

        支持两种形式:
        1. time_delta token: {'type': 'time_delta', 'year': '1', 'direction': 'future'}
        2. 数字 + 单位: "10 days", "30 minutes", "3 hours"

        Args:
            start_idx (int): 开始解析的token索引
            tokens (list): token列表

        Returns:
            tuple: (duration_dict, consumed_tokens) or (None, 0)
            duration_dict: {'years': 0, 'months': 0, 'days': 0, 'hours': 0, 'minutes': 0, 'seconds': 0}
        """
        try:
            n = len(tokens)
            if start_idx >= n:
                return None, 0

            # 情况1: time_delta token
            if tokens[start_idx].get("type") == "time_delta":
                delta_token = tokens[start_idx]

                def safe_int(value, default=0):
                    """安全地转换字符串为整数"""
                    if value is None or value == "":
                        return default
                    try:
                        return int(value)
                    except (ValueError, TypeError):
                        return default

                duration = {
                    "years": safe_int(delta_token.get("year", 0)),
                    "months": safe_int(delta_token.get("month", 0)),
                    "days": safe_int(delta_token.get("day", 0)),
                    "hours": safe_int(delta_token.get("hour", 0)),
                    "minutes": safe_int(delta_token.get("minute", 0)),
                    "seconds": safe_int(delta_token.get("second", 0)),
                }
                return duration, 1

            # 情况2: 数字 + 单位
            # 收集数字部分
            number_parts = []
            idx = start_idx
            consumed = 0

            # 收集连续的数字token
            while idx < n and tokens[idx].get("type") == "token":
                value = tokens[idx].get("value", "").strip()
                if value.isdigit():
                    number_parts.append(value)
                    idx += 1
                    consumed += 1
                elif value == "":
                    idx += 1
                    consumed += 1
                else:
                    break

            # 如果没有找到数字token，尝试英文数字词
            if not number_parts:
                if idx < n and tokens[idx].get("type") == "token":
                    value = tokens[idx].get("value", "").strip().lower()
                    if value in ENGLISH_NUMBER_WORDS_EXTENDED:
                        number = ENGLISH_NUMBER_WORDS_EXTENDED[value]
                        idx += 1
                        consumed += 1
                    else:
                        return None, 0
                else:
                    return None, 0
            else:
                # 组合数字
                try:
                    number = int("".join(number_parts))
                except ValueError:
                    return None, 0

            # 查找单位
            if idx >= n:
                return None, 0

            unit_token = tokens[idx]
            if unit_token.get("type") != "token":
                return None, 0

            unit = unit_token.get("value", "").strip().lower()
            consumed += 1

            # 映射单位到duration字段
            duration = {
                "years": 0,
                "months": 0,
                "days": 0,
                "hours": 0,
                "minutes": 0,
                "seconds": 0,
            }

            if unit in ["year", "years", "yr", "yrs"]:
                duration["years"] = number
            elif unit in ["month", "months", "mo", "mos"]:
                duration["months"] = number
            elif unit in ["day", "days", "d"]:
                duration["days"] = number
            elif unit in ["hour", "hours", "hr", "hrs", "h"]:
                duration["hours"] = number
            elif unit in ["minute", "minutes", "min", "mins", "m"]:
                duration["minutes"] = number
            elif unit in ["second", "seconds", "sec", "secs", "s"]:
                duration["seconds"] = number
            else:
                return None, 0

            return duration, consumed

        except Exception as e:
            self.logger.debug(f"Error in parse_duration: {e}")
            return None, 0

    def parse_time_expression(self, time_tokens, base_time):  # noqa: C901
        """
        解析时间表达式tokens

        Args:
            time_tokens (list): 时间相关的tokens
            base_time (datetime): 基准时间

        Returns:
            list: 解析结果或None
        """
        try:
            if not time_tokens:
                return None

            # 尝试合并多个time_utc tokens
            merged_token = {}
            for token in time_tokens:
                if token.get("type") == "time_utc":
                    merged_token.update(token)

            if merged_token:
                # 使用UTCTimeParser解析合并后的token
                parser = self.parsers.get("time_utc")
                if parser:
                    result = parser.parse(merged_token, base_time)
                    if result and result[0]:
                        return result

            # 尝试使用现有的parsers解析单个token
            for token in time_tokens:
                token_type = token.get("type")
                if token_type in self.parsers:
                    parser = self.parsers[token_type]
                    result = parser.parse(token, base_time)
                    if result and result[0]:
                        return result

            return None

        except Exception as e:
            self.logger.debug(f"Error in parse_time_expression: {e}")
            return None

    def merge_for_duration_from_time(self, i, tokens, base_time):  # noqa: C901
        """
        合并"for 时间长度 from 时间点"
        例如: "for 10 days from 18th Dec", "for 30 minutes from 4pm"

        返回: 从时间点开始持续时间长度的时间段
        """
        try:
            n = len(tokens)
            if i >= n:
                return None

            # 1. 检查当前token是否是"for"
            if tokens[i].get("type") != "token" or tokens[i].get("value", "").lower() != "for":
                return None

            # 2. 解析时间长度
            duration, duration_consumed = self.parse_duration(i + 1, tokens)
            if duration is None:
                return None

            # 3. 查找"from"
            from_idx = i + 1 + duration_consumed
            while (
                from_idx < n
                and tokens[from_idx].get("type") == "token"
                and tokens[from_idx].get("value", "").strip() == ""
            ):
                from_idx += 1

            if (
                from_idx >= n
                or tokens[from_idx].get("type") != "token"
                or tokens[from_idx].get("value", "").lower() != "from"
            ):
                return None

            # 4. 解析时间点
            time_start_idx = from_idx + 1
            while (
                time_start_idx < n
                and tokens[time_start_idx].get("type") == "token"
                and tokens[time_start_idx].get("value", "").strip() == ""
            ):
                time_start_idx += 1

            if time_start_idx >= n:
                return None

            # 查找时间表达式的结束位置
            time_end_idx = time_start_idx
            while time_end_idx < n:
                token = tokens[time_end_idx]
                if token.get("type") in [
                    "time_utc",
                    "time_relative",
                    "time_weekday",
                    "time_holiday",
                    "time_composite_relative",
                ]:
                    time_end_idx += 1
                elif token.get("type") == "token" and token.get("value", "").strip() in [
                    "",
                    "th",
                    "st",
                    "nd",
                    "rd",
                ]:
                    time_end_idx += 1
                else:
                    break

            if time_end_idx == time_start_idx:
                return None

            # 合并时间tokens
            time_tokens = tokens[time_start_idx:time_end_idx]
            time_result = self.parse_time_expression(time_tokens, base_time)
            if not time_result:
                return None

            start_time_str = time_result[0][0]

            # 5. 计算结束时间
            start_time = parse_datetime_from_str(start_time_str)

            # 应用duration
            end_time = start_time
            if duration["years"]:
                end_time = end_time.replace(year=end_time.year + duration["years"])
            if duration["months"]:
                # 处理月份溢出
                new_month = end_time.month + duration["months"]
                while new_month > 12:
                    new_month -= 12
                    end_time = end_time.replace(year=end_time.year + 1)
                while new_month < 1:
                    new_month += 12
                    end_time = end_time.replace(year=end_time.year - 1)
                end_time = end_time.replace(month=new_month)
            if duration["days"]:
                end_time = end_time + timedelta(days=duration["days"])
            if duration["hours"]:
                end_time = end_time + timedelta(hours=duration["hours"])
            if duration["minutes"]:
                end_time = end_time + timedelta(minutes=duration["minutes"])
            if duration["seconds"]:
                end_time = end_time + timedelta(seconds=duration["seconds"])

            # 对于天数duration，结束时间应该是当天的23:59:59
            if (
                duration["days"] > 0
                and duration["hours"] == 0
                and duration["minutes"] == 0
                and duration["seconds"] == 0
            ):
                end_time = end_time.replace(hour=23, minute=59, second=59)

            result = [[start_time_str, format_datetime_str(end_time)]]
            consumed = time_end_idx - i

            return result, consumed

        except Exception as e:
            self.logger.debug(f"Error in merge_for_duration_from_time: {e}")
            return None

    def merge_from_time_for_duration(self, i, tokens, base_time):  # noqa: C901
        """
        合并"from 时间点 for 时间长度"
        例如: "from 18th Dec for 10 days", "from 4pm for thirty minutes"

        返回: 从时间点开始持续时间长度的时间段
        """
        try:
            n = len(tokens)
            if i >= n:
                return None

            # 1. 检查当前token是否是"from"
            if tokens[i].get("type") != "token" or tokens[i].get("value", "").lower() != "from":
                return None

            # 2. 解析时间点
            time_start_idx = i + 1
            while (
                time_start_idx < n
                and tokens[time_start_idx].get("type") == "token"
                and tokens[time_start_idx].get("value", "").strip() == ""
            ):
                time_start_idx += 1

            if time_start_idx >= n:
                return None

            # 查找时间表达式的结束位置
            time_end_idx = time_start_idx
            while time_end_idx < n:
                token = tokens[time_end_idx]
                if token.get("type") in [
                    "time_utc",
                    "time_relative",
                    "time_weekday",
                    "time_holiday",
                    "time_composite_relative",
                ]:
                    time_end_idx += 1
                elif token.get("type") == "token" and token.get("value", "").strip() in [
                    "",
                    "th",
                    "st",
                    "nd",
                    "rd",
                ]:
                    time_end_idx += 1
                else:
                    break

            if time_end_idx == time_start_idx:
                return None

            # 合并时间tokens
            time_tokens = tokens[time_start_idx:time_end_idx]
            time_result = self.parse_time_expression(time_tokens, base_time)
            if not time_result:
                return None

            start_time_str = time_result[0][0]

            # 3. 查找"for"
            for_idx = time_end_idx
            while (
                for_idx < n
                and tokens[for_idx].get("type") == "token"
                and tokens[for_idx].get("value", "").strip() == ""
            ):
                for_idx += 1

            if (
                for_idx >= n
                or tokens[for_idx].get("type") != "token"
                or tokens[for_idx].get("value", "").lower() != "for"
            ):
                return None

            # 4. 解析时间长度
            duration, duration_consumed = self.parse_duration(for_idx + 1, tokens)
            if duration is None:
                return None

            # 5. 计算结束时间
            from datetime import datetime, timedelta

            start_time = parse_datetime_from_str(start_time_str)

            # 应用duration
            end_time = start_time
            if duration["years"]:
                end_time = end_time.replace(year=end_time.year + duration["years"])
            if duration["months"]:
                # 处理月份溢出
                new_month = end_time.month + duration["months"]
                while new_month > 12:
                    new_month -= 12
                    end_time = end_time.replace(year=end_time.year + 1)
                while new_month < 1:
                    new_month += 12
                    end_time = end_time.replace(year=end_time.year - 1)
                end_time = end_time.replace(month=new_month)
            if duration["days"]:
                end_time = end_time + timedelta(days=duration["days"])
            if duration["hours"]:
                end_time = end_time + timedelta(hours=duration["hours"])
            if duration["minutes"]:
                end_time = end_time + timedelta(minutes=duration["minutes"])
            if duration["seconds"]:
                end_time = end_time + timedelta(seconds=duration["seconds"])

            # 对于天数duration，结束时间应该是当天的23:59:59
            if (
                duration["days"] > 0
                and duration["hours"] == 0
                and duration["minutes"] == 0
                and duration["seconds"] == 0
            ):
                end_time = end_time.replace(hour=23, minute=59, second=59)

            result = [[start_time_str, format_datetime_str(end_time)]]
            consumed = for_idx + 1 + duration_consumed - i

            return result, consumed

        except Exception as e:
            self.logger.debug(f"Error in merge_from_time_for_duration: {e}")
            return None

    def merge_time_for_duration(self, i, tokens, base_time):  # noqa: C901
        """
        合并"时间点 for 时间长度"
        例如: "4pm for 30 mins", "18th Dec for 10 days"

        返回: 从时间点开始持续时间长度的时间段
        """
        try:
            n = len(tokens)
            if i >= n:
                return None

            # 1. 检查当前token是否是时间类型
            if tokens[i].get("type") not in [
                "time_utc",
                "time_relative",
                "time_weekday",
                "time_holiday",
                "time_composite_relative",
            ]:
                return None

            # 查找时间表达式的结束位置
            time_end_idx = i
            while time_end_idx < n:
                token = tokens[time_end_idx]
                if token.get("type") in [
                    "time_utc",
                    "time_relative",
                    "time_weekday",
                    "time_holiday",
                    "time_composite_relative",
                ]:
                    time_end_idx += 1
                elif token.get("type") == "token" and token.get("value", "").strip() in [
                    "",
                    "th",
                    "st",
                    "nd",
                    "rd",
                ]:
                    time_end_idx += 1
                else:
                    break

            if time_end_idx == i:
                return None

            # 合并时间tokens
            time_tokens = tokens[i:time_end_idx]
            time_result = self.parse_time_expression(time_tokens, base_time)
            if not time_result:
                return None

            # 检查time_result的格式
            if not isinstance(time_result, list) or len(time_result) == 0:
                return None

            if not isinstance(time_result[0], list) or len(time_result[0]) == 0:
                return None

            start_time_str = time_result[0][0]

            # 2. 查找"for"
            for_idx = time_end_idx
            while (
                for_idx < n
                and tokens[for_idx].get("type") == "token"
                and tokens[for_idx].get("value", "").strip() == ""
            ):
                for_idx += 1

            if (
                for_idx >= n
                or tokens[for_idx].get("type") != "token"
                or tokens[for_idx].get("value", "").lower() != "for"
            ):
                return None

            # 3. 解析时间长度
            duration, duration_consumed = self.parse_duration(for_idx + 1, tokens)
            if duration is None:
                return None

            # 4. 计算结束时间
            from datetime import datetime, timedelta

            start_time = parse_datetime_from_str(start_time_str)

            # 应用duration
            end_time = start_time
            if duration["years"]:
                end_time = end_time.replace(year=end_time.year + duration["years"])
            if duration["months"]:
                # 处理月份溢出
                new_month = end_time.month + duration["months"]
                while new_month > 12:
                    new_month -= 12
                    end_time = end_time.replace(year=end_time.year + 1)
                while new_month < 1:
                    new_month += 12
                    end_time = end_time.replace(year=end_time.year - 1)
                end_time = end_time.replace(month=new_month)
            if duration["days"]:
                end_time = end_time + timedelta(days=duration["days"])
            if duration["hours"]:
                end_time = end_time + timedelta(hours=duration["hours"])
            if duration["minutes"]:
                end_time = end_time + timedelta(minutes=duration["minutes"])
            if duration["seconds"]:
                end_time = end_time + timedelta(seconds=duration["seconds"])

            result = [[start_time_str, format_datetime_str(end_time)]]
            consumed = for_idx + 1 + duration_consumed - i

            return result, consumed

        except Exception as e:
            self.logger.debug(f"Error in merge_time_for_duration: {e}")
            return None

    def merge_duration_from_time(self, i, tokens, base_time):  # noqa: C901
        """
        合并"时间长度 from 时间点"(偏移计算)
        例如: "a year from Christmas", "3 days from tomorrow"

        返回: 从时间点偏移时间长度后的时间点
        """
        try:
            n = len(tokens)
            if i >= n:
                return None

            # 1. 检查当前token是否是time_delta
            if tokens[i].get("type") != "time_delta":
                return None

            # 解析时间长度
            duration, duration_consumed = self.parse_duration(i, tokens)
            if duration is None:
                return None

            # 2. 查找"from"
            from_idx = i + duration_consumed
            while (
                from_idx < n
                and tokens[from_idx].get("type") == "token"
                and tokens[from_idx].get("value", "").strip() == ""
            ):
                from_idx += 1

            if (
                from_idx >= n
                or tokens[from_idx].get("type") != "token"
                or tokens[from_idx].get("value", "").lower() != "from"
            ):
                return None

            # 3. 解析时间点
            time_start_idx = from_idx + 1
            while (
                time_start_idx < n
                and tokens[time_start_idx].get("type") == "token"
                and tokens[time_start_idx].get("value", "").strip() == ""
            ):
                time_start_idx += 1

            if time_start_idx >= n:
                return None

            # 查找时间表达式的结束位置
            time_end_idx = time_start_idx
            while time_end_idx < n:
                token = tokens[time_end_idx]
                if token.get("type") in [
                    "time_utc",
                    "time_relative",
                    "time_weekday",
                    "time_holiday",
                    "time_composite_relative",
                ]:
                    time_end_idx += 1
                elif token.get("type") == "token" and token.get("value", "").strip() in [
                    "",
                    "th",
                    "st",
                    "nd",
                    "rd",
                ]:
                    time_end_idx += 1
                else:
                    break

            if time_end_idx == time_start_idx:
                return None

            # 合并时间tokens
            time_tokens = tokens[time_start_idx:time_end_idx]
            time_result = self.parse_time_expression(time_tokens, base_time)
            if not time_result:
                return None

            base_time_str = time_result[0][0]

            # 4. 计算偏移后的时间
            from datetime import datetime, timedelta

            base_datetime = parse_datetime_from_str(base_time_str)

            # 应用duration
            result_time = base_datetime
            if duration["years"]:
                result_time = result_time.replace(year=result_time.year + duration["years"])
            if duration["months"]:
                # 处理月份溢出
                new_month = result_time.month + duration["months"]
                while new_month > 12:
                    new_month -= 12
                    result_time = result_time.replace(year=result_time.year + 1)
                while new_month < 1:
                    new_month += 12
                    result_time = result_time.replace(year=result_time.year - 1)
                result_time = result_time.replace(month=new_month)
            if duration["days"]:
                result_time = result_time + timedelta(days=duration["days"])
            if duration["hours"]:
                result_time = result_time + timedelta(hours=duration["hours"])
            if duration["minutes"]:
                result_time = result_time + timedelta(minutes=duration["minutes"])
            if duration["seconds"]:
                result_time = result_time + timedelta(seconds=duration["seconds"])

            # 对于大于天的单位偏移，返回一整天的时间段
            if duration["years"] > 0 or duration["months"] > 0 or duration["days"] > 0:
                # 将结果时间重置为当天的00:00:00
                start_time, end_time = create_day_range(result_time)
                result = [
                    [
                        format_datetime_str(start_time),
                        format_datetime_str(end_time),
                    ]
                ]
            else:
                # 对于小时/分钟/秒的偏移，返回精确时间点
                result = [[format_datetime_str(result_time)]]

            consumed = time_end_idx - i
            return result, consumed

        except Exception as e:
            self.logger.debug(f"Error in merge_duration_from_time: {e}")
            return None
