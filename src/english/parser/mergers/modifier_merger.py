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
    month_name_to_number,
    create_day_range,
    parse_datetime_str,
    format_datetime_str,
)


class ModifierMerger:
    """Merger for handling modifier-related time expressions"""

    def __init__(self, parsers):
        """
        Initialize modifier merger

        Args:
            parsers (dict): Dictionary containing various time parsers
        """
        self.parsers = parsers
        self.logger = get_logger(__name__)

    def merge_modifier_with_weekday(self, modifier_token, weekday_token, base_time):
        """
        Merge time_composite_relative(time_modifier) with time_weekday
        Example: "next monday" -> apply modifier to weekday
        """
        try:
            time_modifier = modifier_token.get("time_modifier", "").strip('"')
            if not time_modifier:
                return None

            modifier = int(time_modifier)

            # Parse the weekday first
            weekday_parser = self.parsers.get("time_weekday")
            if not weekday_parser:
                return None

            # Apply modifier to base_time
            if modifier > 0:
                # "next" - add 1 week
                from datetime import timedelta

                modified_base = base_time + timedelta(weeks=1)
            elif modifier < 0:
                # "last" - subtract 1 week
                from datetime import timedelta

                modified_base = base_time + timedelta(weeks=-1)
            else:
                # "this" - use current week
                modified_base = base_time

            # Parse weekday with modified base time
            result = weekday_parser.parse(weekday_token, modified_base)
            return result

        except Exception as e:
            self.logger.debug(f"Error in merge_modifier_with_weekday: {e}")
            return None

    def handle_week_after_next(self, base_time):
        """
        Handle "week after next" pattern
        Based on the test case, this means 2 weeks from now
        """
        try:
            from datetime import timedelta

            # "week after next" = 2 weeks from now
            target_date = base_time + timedelta(weeks=2)

            # Get the start and end of that week (Monday to Sunday)
            # Find Monday of that week
            days_since_monday = target_date.weekday()
            week_start = target_date - timedelta(days=days_since_monday)
            week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)

            # Find Sunday of that week
            week_end = week_start + timedelta(days=6, hours=23, minutes=59, seconds=59)

            return [
                [
                    format_datetime_str(week_start),
                    format_datetime_str(week_end),
                ]
            ]

        except Exception as e:
            self.logger.debug(f"Error in handle_week_after_next: {e}")
            return None

    def handle_named_month_after_next(self, month_name, base_time):
        """
        Handle "<MonthName> after next" pattern.
        Semantics: the next occurrence of <MonthName> relative to base_time is in the same year if not passed,
        otherwise next year. "after next" means the occurrence after that, i.e., +1 additional year.
        Return the full month range of that target month.
        """
        try:
            month_map = {
                "january": 1,
                "jan": 1,
                "february": 2,
                "feb": 2,
                "march": 3,
                "mar": 3,
                "april": 4,
                "apr": 4,
                "may": 5,
                "june": 6,
                "jun": 6,
                "july": 7,
                "jul": 7,
                "august": 8,
                "aug": 8,
                "september": 9,
                "sep": 9,
                "sept": 9,
                "october": 10,
                "oct": 10,
                "november": 11,
                "nov": 11,
                "december": 12,
                "dec": 12,
            }
            target_month = month_map.get(month_name.lower())
            if not target_month:
                return None

            # Determine the next occurrence year of the month relative to base_time
            year = base_time.year
            if target_month < base_time.month or (
                target_month == base_time.month and base_time.day > 1
            ):
                # The month of this year has passed (or we're inside the month but after the first day), so next occurrence is next year
                next_occurrence_year = year + 1
            else:
                next_occurrence_year = year

            # "after next" means one occurrence after the next occurrence => +1 year
            target_year = next_occurrence_year + 1

            # Compute month range
            from datetime import datetime

            start_of_month = base_time.replace(
                year=target_year,
                month=target_month,
                day=1,
                hour=0,
                minute=0,
                second=0,
                microsecond=0,
            )

            # Find last day of month
            if target_month in [1, 3, 5, 7, 8, 10, 12]:
                end_day = 31
            elif target_month in [4, 6, 9, 11]:
                end_day = 30
            else:
                # February leap year check
                y = target_year
                if (y % 4 == 0) and ((y % 100 != 0) or (y % 400 == 0)):
                    end_day = 29
                else:
                    end_day = 28

            end_of_month = base_time.replace(
                year=target_year,
                month=target_month,
                day=end_day,
                hour=23,
                minute=59,
                second=59,
                microsecond=0,
            )

            return [
                [
                    format_datetime_str(start_of_month),
                    format_datetime_str(end_of_month),
                ]
            ]
        except Exception as e:
            self.logger.debug(f"Error in handle_named_month_after_next: {e}")
            return None

    def try_merge_time_with_year_modifier(self, i, tokens, base_time):  # noqa: C901
        """
        Try to merge "time + year modifier" pattern
        Example: "june 9 last year", "august 20 this year"

        Args:
            i (int): Current index (pointing to time_utc token)
            tokens (list): Token list
            base_time (datetime): Base time

        Returns:
            tuple: (result, jump_count) or None
        """
        n = len(tokens)
        if i + 1 >= n:
            return None

        time_token = tokens[i]
        if time_token.get("type") != "time_utc":
            return None

        # Look for year modifier after time token
        modifier_idx = i + 1
        # Skip empty tokens
        while (
            modifier_idx < n
            and tokens[modifier_idx].get("type") == "token"
            and tokens[modifier_idx].get("value", "") == ""
        ):
            modifier_idx += 1

        if modifier_idx >= n:
            return None

        modifier_token = tokens[modifier_idx]
        if modifier_token.get("type") not in [
            "time_relative",
            "time_composite_relative",
        ]:
            return None

        # Check if it's a year modifier
        if modifier_token.get("type") == "time_composite_relative":
            unit = modifier_token.get("unit", "")
            if unit != "year":
                return None
        elif modifier_token.get("type") == "time_relative":
            # Check if it's a year-related modifier
            if "year" not in str(modifier_token.get("value", "")).lower():
                return None

        # Apply modifier to time token
        try:
            modified_base = self.apply_modifier_to_base_time(modifier_token, base_time)
            result = self._parse_time_token(time_token, modified_base)
            if result:
                return result, modifier_idx + 1 - i
        except Exception as e:
            self.logger.debug(f"Error in try_merge_time_with_year_modifier: {e}")
            return None

        return None

    def apply_modifier_to_base_time(self, modifier_token, base_time):  # noqa: C901
        """
        Apply relative modifier to base_time

        Args:
            modifier_token (dict): Modifier token (time_relative or time_composite_relative)
            base_time (datetime): Base time

        Returns:
            datetime: Modified base time
        """
        try:
            # Handle time_relative
            if modifier_token.get("type") == "time_relative":
                offset_day = modifier_token.get("offset_day", "").strip('"')
                offset_year = modifier_token.get("offset_year", "").strip('"')
                offset_month = modifier_token.get("offset_month", "").strip('"')

                try:
                    day_offset = int(offset_day) if offset_day else 0
                    year_offset = int(offset_year) if offset_year else 0
                    month_offset = int(offset_month) if offset_month else 0

                    from datetime import timedelta

                    modified_time = base_time + timedelta(days=day_offset)
                    modified_time = modified_time + relativedelta(
                        years=year_offset, months=month_offset
                    )
                    return modified_time
                except (ValueError, TypeError):
                    pass

            # Handle time_composite_relative
            elif modifier_token.get("type") == "time_composite_relative":
                offset_year = modifier_token.get("offset_year", "").strip('"')
                offset_month = modifier_token.get("offset_month", "").strip('"')
                time_modifier = modifier_token.get("time_modifier", "").strip('"')
                ordinal_position = modifier_token.get("ordinal_position", "").strip('"')
                unit = modifier_token.get("unit", "").strip('"')

                try:
                    if offset_year:
                        year_offset = int(offset_year)
                        return base_time + relativedelta(years=year_offset)
                    elif offset_month:
                        month_offset = int(offset_month)
                        return base_time + relativedelta(months=month_offset)
                    elif time_modifier and unit:
                        # Handle time_modifier field (e.g., "last year" -> time_modifier: "-1", unit: "year")
                        modifier_value = int(time_modifier)
                        if unit == "year":
                            return base_time + relativedelta(years=modifier_value)
                        elif unit == "month":
                            return base_time + relativedelta(months=modifier_value)
                    elif ordinal_position and unit:
                        position = int(ordinal_position)
                        if unit == "year":
                            return base_time + relativedelta(years=position)
                        elif unit == "month":
                            return base_time + relativedelta(months=position)
                except (ValueError, TypeError):
                    pass

            return base_time

        except Exception as e:
            self.logger.debug(f"Error in apply_modifier_to_base_time: {e}")
            return base_time

    def handle_weekday_after_next_multiple(self, weekday_token, after_next_count, base_time):
        """
        Handle "weekday after next after next" pattern

        Args:
            weekday_token (dict): Weekday token (e.g., monday)
            after_next_count (int): Number of "after next" patterns
            base_time (datetime): Base time reference

        Returns:
            tuple: (single_day_results, 1) or None
        """
        try:
            from datetime import datetime, timedelta

            weekday = weekday_token.get("week_day", "").strip('"').lower()
            if not weekday:
                return None

            # Calculate target date
            # Find the next occurrence of the target weekday first
            weekday_map = {
                "monday": 0,
                "tuesday": 1,
                "wednesday": 2,
                "thursday": 3,
                "friday": 4,
                "saturday": 5,
                "sunday": 6,
            }

            if weekday not in weekday_map:
                return None

            target_weekday = weekday_map[weekday]
            current_weekday = base_time.weekday()

            # Find the next occurrence of target weekday
            days_until_target = (target_weekday - current_weekday) % 7
            if days_until_target == 0:
                days_until_target = 7  # If today is the target weekday, find next week's

            # Start from the next occurrence of target weekday
            next_target = base_time + timedelta(days=days_until_target)

            # Add (after_next_count - 1) more weeks
            # "after next" means 1 occurrence after the next one
            # So "monday after next after next" with 3 "after next" tokens = next monday + 2 weeks
            final_date = next_target + timedelta(weeks=after_next_count - 1)

            # Return single day - format as time range
            start_of_day, end_of_day = create_day_range(final_date)

            start_str = format_datetime_str(start_of_day)
            end_str = format_datetime_str(end_of_day)

            single_day_result = [start_str, end_str]
            return ([single_day_result], 1)

        except Exception as e:
            self.logger.debug(f"Error in handle_weekday_after_next_multiple: {e}")
            return None

    def merge_ordinal_weekday_month(self, i, tokens, base_time):  # noqa: C901
        """
        合并"序数词 + 星期几 + of/in + 月份"
        例如: "first Monday of this month", "second Tuesday in the month"

        Pattern:
          - token('first'/'second'/...)
          - time_weekday(week_day)
          - token('of'/'in')
          - time_composite_relative(unit='month') 或 token('the'/'this') + token('month')

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

            # 1. 解析序数词
            ordinal_map = {
                "first": 1,
                "second": 2,
                "third": 3,
                "fourth": 4,
                "fifth": 5,
                "last": -1,
            }

            ordinal_token = tokens[i]
            ordinal_value = ordinal_token.get("value", "").lower()
            nth = ordinal_map.get(ordinal_value)

            if nth is None:
                return None

            # 2. 检查下一个token是否是time_weekday
            if i + 1 >= n:
                return None

            weekday_token = tokens[i + 1]
            if weekday_token.get("type") != "time_weekday":
                return None

            week_day = weekday_token.get("week_day", "").strip('"').lower()
            if not week_day:
                return None

            # 3. 查找"of"或"in"连接词
            connector_idx = i + 2
            while connector_idx < n and tokens[connector_idx].get("type") == "token":
                connector_value = tokens[connector_idx].get("value", "").strip().lower()
                if connector_value in ["of", "in"]:
                    break
                elif connector_value == "":
                    connector_idx += 1
                    continue
                else:
                    return None

            if connector_idx >= n:
                return None

            # 4. 确定目标月份
            month_token_idx = connector_idx + 1
            target_month = None
            target_year = base_time.year
            consumed_tokens = 0

            # 跳过空token
            while (
                month_token_idx < n
                and tokens[month_token_idx].get("type") == "token"
                and tokens[month_token_idx].get("value", "").strip() == ""
            ):
                month_token_idx += 1

            if month_token_idx >= n:
                return None

            month_token = tokens[month_token_idx]

            # 情况1: time_composite_relative(unit='month')
            if (
                month_token.get("type") == "time_composite_relative"
                and month_token.get("unit") == "month"
            ):
                time_modifier = int(month_token.get("time_modifier", "0"))
                target_month = base_time.month + time_modifier
                consumed_tokens = month_token_idx - i + 1

                # 处理跨年
                while target_month > 12:
                    target_month -= 12
                    target_year += 1
                while target_month < 1:
                    target_month += 12
                    target_year -= 1

            # 情况2: token('the'/'this') + token('month')
            elif month_token.get("type") == "token":
                month_value = month_token.get("value", "").lower()
                if month_value in ["the", "this"]:
                    # 检查下一个token是否是'month'
                    next_month_idx = month_token_idx + 1
                    while (
                        next_month_idx < n
                        and tokens[next_month_idx].get("type") == "token"
                        and tokens[next_month_idx].get("value", "").strip() == ""
                    ):
                        next_month_idx += 1

                    if (
                        next_month_idx < n
                        and tokens[next_month_idx].get("type") == "token"
                        and tokens[next_month_idx].get("value", "").lower() == "month"
                    ):
                        target_month = base_time.month
                        consumed_tokens = next_month_idx - i + 1
                    else:
                        return None
                elif month_value == "month":
                    target_month = base_time.month
                    consumed_tokens = month_token_idx - i + 1
                else:
                    return None

            else:
                return None

            if target_month is None:
                return None

            # 5. 调用base_parser的_get_month_nth_weekday计算目标日期
            try:
                # 获取base_parser实例
                base_parser = self.parsers.get("time_utc")  # 使用任意parser获取base_parser
                if hasattr(base_parser, "_get_month_nth_weekday"):
                    target_date = base_parser._get_month_nth_weekday(
                        target_year, target_month, nth, week_day
                    )
                else:
                    # 如果base_parser没有这个方法，直接在这里实现
                    from datetime import datetime, timedelta
                    import calendar

                    # 转换星期几名称为数字（0=Monday, 6=Sunday）
                    weekday_map = {
                        "monday": 0,
                        "tuesday": 1,
                        "wednesday": 2,
                        "thursday": 3,
                        "friday": 4,
                        "saturday": 5,
                        "sunday": 6,
                    }
                    target_weekday = weekday_map.get(week_day.lower(), 0)

                    # 获取该月第一天
                    first_day = datetime(target_year, target_month, 1)
                    first_weekday = first_day.weekday()

                    # 计算第一个目标星期几的日期
                    days_until_target = (target_weekday - first_weekday) % 7
                    first_occurrence = first_day + timedelta(days=days_until_target)

                    if nth == -1:
                        # 最后一个: 从月末往回找
                        last_day = calendar.monthrange(target_year, target_month)[1]
                        last_day_date = datetime(target_year, target_month, last_day)
                        last_weekday = last_day_date.weekday()

                        days_back = (last_weekday - target_weekday) % 7
                        target_date = last_day_date - timedelta(days=days_back)
                    else:
                        # 计算第N个目标星期几
                        target_date = first_occurrence + timedelta(weeks=nth - 1)

                        # 确保仍在当月
                        if target_date.month != target_month:
                            raise ValueError(f"该月没有第{nth}个{week_day}")

                # 6. 返回格式化结果
                start_of_day = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
                end_of_day = target_date.replace(hour=23, minute=59, second=59, microsecond=0)

                result = [
                    [
                        format_datetime_str(start_of_day),
                        format_datetime_str(end_of_day),
                    ]
                ]

                return result, consumed_tokens

            except (ValueError, Exception) as e:
                self.logger.debug(f"Error calculating month nth weekday: {e}")
                return None

        except Exception as e:
            self.logger.debug(f"Error in merge_ordinal_weekday_month: {e}")
            return None

    def _parse_time_token(self, token, base_time):
        """
        Parse a time token using appropriate parser

        Args:
            token (dict): Time token
            base_time (datetime): Base time

        Returns:
            list: Parsed time result or None
        """
        try:
            token_type = token.get("type")
            parser = self.parsers.get(token_type)

            if not parser:
                return None

            return parser.parse(token, base_time)

        except Exception as e:
            self.logger.debug(f"Error in _parse_time_token: {e}")
            return None
