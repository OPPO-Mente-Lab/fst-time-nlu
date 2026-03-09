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
from .....core.logger import get_logger
from ...time_utils import (
    get_month_range,
    month_name_to_number,
)


class OfInjectionMerger:
    """Merger for handling 'X of Y' injection patterns"""

    def __init__(self, parsers, context_merger):
        """
        Initialize of injection merger

        Args:
            parsers (dict): Dictionary containing various time parsers
            context_merger: Reference to ContextMerger for accessing methods
        """
        self.parsers = parsers
        self.context_merger = context_merger
        self.logger = get_logger(__name__)

    def try_merge(self, i, tokens, base_time):  # noqa: C901
        """Try to merge patterns of the form: X + 'of' + Y, by injecting Y's temporal
        context (year/month/week/quarter) into X.
        """
        n = len(tokens)
        if i >= n:
            return None
        left = tokens[i]
        # Look for 'of' or 'from' after left，允许中间出现如 'the'、'day' 等填充词
        j = i + 1
        SKIP_BETWEEN = {"", "the", "day", "weekday"}
        while (
            j < n
            and tokens[j].get("type") == "token"
            and tokens[j].get("value", "").strip().lower() in SKIP_BETWEEN
        ):
            j += 1
        if j >= n or tokens[j].get("type") != "token":
            return None
        connector = tokens[j].get("value", "").strip().lower()
        if connector not in ["of", "from"]:
            return None
        k = j + 1
        while (
            k < n and tokens[k].get("type") == "token" and tokens[k].get("value", "").strip() == ""
        ):
            k += 1
        if k >= n:
            return None
        right = tokens[k]

        try:
            # Case A: left is time_utc with day (e.g., "20th of next month", "15 of March")
            if left.get("type") == "time_utc" and "day" in left and "hour" not in left:
                day_str = left.get("day", "").strip('"')
                # Determine target year/month from right side
                target_year = None
                target_month = None

                # Right absolute month/year
                if right.get("type") == "time_utc":
                    if "year" in right:
                        target_year = int(right.get("year", "0").strip('"'))
                    if "month" in right:
                        target_month = month_name_to_number(right.get("month", "").strip('"'))

                # Right composite relative like next/last/this month/year
                elif right.get("type") == "time_composite_relative":
                    # infer unit if provided after as raw token (e.g., token 'month')
                    unit = right.get("unit", "").strip('"')
                    if not unit and k + 1 < n and tokens[k + 1].get("type") == "token":
                        maybe_unit = tokens[k + 1].get("value", "").lower()
                        if maybe_unit in ["month", "week", "year", "quarter"]:
                            unit = maybe_unit
                    time_modifier = right.get("time_modifier", "").strip('"')
                    if time_modifier and unit in ["month", "year"]:
                        try:
                            mod = int(time_modifier)
                        except ValueError:
                            mod = 0
                        if unit == "month":
                            shifted = base_time + relativedelta(months=mod)
                            target_year = shifted.year
                            target_month = shifted.month
                        elif unit == "year":
                            shifted = base_time + relativedelta(years=mod)
                            target_year = shifted.year

                # If only year known, and month not set, use left's month if any (rare), else base month
                if target_year is None and target_month is None:
                    return None
                # Build target date
                year = target_year if target_year is not None else base_time.year
                month = target_month if target_month is not None else base_time.month

                try:
                    target = datetime(year, month, int(day_str), 0, 0, 0)
                except ValueError:
                    # If day overflow, clamp to month end
                    tmp = datetime(year, month, 1)
                    _, m_end = get_month_range(tmp)
                    target = m_end.replace(hour=0, minute=0, second=0)
                start = target.replace(hour=0, minute=0, second=0, microsecond=0)
                end = target.replace(hour=23, minute=59, second=59, microsecond=0)
                return (
                    [
                        [
                            start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                            end.strftime("%Y-%m-%dT%H:%M:%SZ"),
                        ]
                    ],
                    (k - i + 1),
                )

            # Case B: left is month; right provides year -> month of year
            if (
                left.get("type") == "time_utc"
                and "month" in left
                and "year" not in left
                and "day" not in left
            ):
                year_str = None
                # Right is time_utc with year
                if right.get("type") == "time_utc" and "year" in right:
                    year_str = right["year"]
                # Right is token with 4-digit year
                elif right.get("type") == "token":
                    val = right.get("value", "").strip()
                    if val.isdigit() and len(val) == 4:
                        year_int = int(val)
                        if 1900 <= year_int <= 2099:
                            year_str = val

                if year_str:
                    synth = {
                        "type": "time_utc",
                        "month": left["month"],
                        "year": year_str,
                    }
                    utc_parser = self.parsers.get("time_utc")
                    if utc_parser:
                        res = utc_parser.parse(synth, base_time)
                        if res:
                            return (res, (k - i + 1))

            # Case C0: left is weekday; middle is "of"/"from"; right is relative week
            # e.g., "sunday from last week", "wednesday of next week"
            if left.get("type") == "time_weekday" and "week_day" in left:
                # Look for "of" or "from" token
                mid_idx = i + 1
                while mid_idx < k and tokens[mid_idx].get("type") == "token":
                    mid_val = tokens[mid_idx].get("value", "").strip().lower()
                    if mid_val in ["of", "from"]:
                        # Found connector, check if next is relative week
                        next_idx = mid_idx + 1
                        while (
                            next_idx <= k
                            and tokens[next_idx].get("type") == "token"
                            and tokens[next_idx].get("value", "").strip() == ""
                        ):
                            next_idx += 1

                        if next_idx <= k:
                            right_token = tokens[next_idx]
                            if right_token.get("type") in [
                                "time_weekday",
                                "time_composite_relative",
                            ]:
                                # Extract week offset
                                week_mod = 0
                                if (
                                    right_token.get("type") == "time_weekday"
                                    and "offset_week" in right_token
                                ):
                                    week_mod = int(right_token.get("offset_week", "0").strip('"'))
                                elif (
                                    right_token.get("type") == "time_composite_relative"
                                    and "time_modifier" in right_token
                                ):
                                    week_mod = int(right_token.get("time_modifier", "0").strip('"'))

                                # Calculate target weekday
                                target_base = base_time + timedelta(weeks=week_mod)
                                week_start = target_base - timedelta(days=target_base.weekday())

                                weekday_map = {
                                    "monday": 0,
                                    "tuesday": 1,
                                    "wednesday": 2,
                                    "thursday": 3,
                                    "friday": 4,
                                    "saturday": 5,
                                    "sunday": 6,
                                }
                                wd = left.get("week_day", "").strip('"').lower()
                                if wd in weekday_map:
                                    day_offset = weekday_map[wd]
                                    target_day = (week_start + timedelta(days=day_offset)).replace(
                                        hour=0, minute=0, second=0, microsecond=0
                                    )
                                    day_end = target_day.replace(
                                        hour=23, minute=59, second=59, microsecond=0
                                    )
                                    return (
                                        [
                                            [
                                                target_day.strftime("%Y-%m-%dT%H:%M:%SZ"),
                                                day_end.strftime("%Y-%m-%dT%H:%M:%SZ"),
                                            ]
                                        ],
                                        (next_idx - i + 1),
                                    )
                        break
                    mid_idx += 1

            # Case C-possessive: Handle "last week's sunday"
            # Pattern: time_weekday(offset_week) + ' + s + time_weekday(week_day)
            if left.get("type") == "time_weekday" and "offset_week" in left:
                mid_idx = i + 1
                has_possessive = False
                while mid_idx < k and tokens[mid_idx].get("type") == "token":
                    mid_val = tokens[mid_idx].get("value", "").strip()
                    if mid_val in ["'", "s"]:
                        mid_idx += 1
                        has_possessive = True
                        continue
                    elif mid_val == "":
                        mid_idx += 1
                        continue
                    else:
                        break

                if has_possessive and mid_idx <= k:
                    right_token = tokens[mid_idx]
                    if right_token.get("type") == "time_weekday" and "week_day" in right_token:
                        week_mod = int(left.get("offset_week", "0").strip('"'))
                        target_base = base_time + timedelta(weeks=week_mod)
                        week_start = target_base - timedelta(days=target_base.weekday())

                        weekday_map = {
                            "monday": 0,
                            "tuesday": 1,
                            "wednesday": 2,
                            "thursday": 3,
                            "friday": 4,
                            "saturday": 5,
                            "sunday": 6,
                        }
                        wd = right_token.get("week_day", "").strip('"').lower()
                        if wd in weekday_map:
                            day_offset = weekday_map[wd]
                            target_day = (week_start + timedelta(days=day_offset)).replace(
                                hour=0, minute=0, second=0, microsecond=0
                            )
                            day_end = target_day.replace(
                                hour=23, minute=59, second=59, microsecond=0
                            )
                            return (
                                [
                                    [
                                        target_day.strftime("%Y-%m-%dT%H:%M:%SZ"),
                                        day_end.strftime("%Y-%m-%dT%H:%M:%SZ"),
                                    ]
                                ],
                                (mid_idx - i + 1),
                            )

            # Case C: left is weekday; right is relative week (this/next/last week)
            if left.get("type") == "time_weekday" and (
                right.get("type") in ["time_weekday", "time_composite_relative"]
            ):
                # Determine target week base
                week_mod = 0
                if right.get("type") == "time_weekday" and "offset_week" in right:
                    try:
                        week_mod = int(right.get("offset_week", "0").strip('"'))
                    except ValueError:
                        week_mod = 0
                elif right.get("type") == "time_composite_relative":
                    tm = right.get("time_modifier", "").strip('"')
                    if tm:
                        try:
                            week_mod = int(tm)
                            # 如果 time_modifier=2，表示 "after next"，即下下周
                        except ValueError:
                            week_mod = 0
                target_base = base_time + timedelta(weeks=week_mod)
                # Compute that week range
                # Monday as start
                week_start = target_base - timedelta(days=target_base.weekday())
                # Find target weekday index
                weekday_map = {
                    "monday": 0,
                    "tuesday": 1,
                    "wednesday": 2,
                    "thursday": 3,
                    "friday": 4,
                    "saturday": 5,
                    "sunday": 6,
                }
                wd = left.get("week_day", "").strip('"').lower()
                if wd not in weekday_map:
                    return None
                day_offset = weekday_map[wd]
                target_day = (week_start + timedelta(days=day_offset)).replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
                day_end = target_day.replace(hour=23, minute=59, second=59, microsecond=0)
                return (
                    [
                        [
                            target_day.strftime("%Y-%m-%dT%H:%M:%SZ"),
                            day_end.strftime("%Y-%m-%dT%H:%M:%SZ"),
                        ]
                    ],
                    (k - i + 1),
                )

            # Case C2: left is weekday or weekday-like token; right is month -> e.g., "last monday of march"
            # 支持在 left 前一个非空 token 存在 time_composite_relative 指示 first/last（time_modifier 正负）
            # 允许从普通 token 中识别星期几名称（normalizer已将文本转为小写）
            # Also handle week_period (weekend) -> e.g., "last weekend of October 2017"
            if (
                left.get("type") in ["time_weekday", "token"]
                and right.get("type") == "time_utc"
                and "month" in right
                and "day" not in right
            ):
                # Check if this is a weekend case
                if left.get("type") == "time_weekday" and "week_period" in left:
                    week_period = left.get("week_period", "").strip('"').lower()
                    if week_period == "weekend":
                        # Handle "last weekend of Month Year"
                        # Extract position from offset_week
                        offset_week = left.get("offset_week", "0").strip('"')
                        try:
                            position = int(offset_week)  # -1 for last, 0 for this, 1 for next
                        except ValueError:
                            position = 0

                        month_name = right.get("month", "").strip('"')
                        month_num = month_name_to_number(month_name)
                        if not month_num:
                            return None

                        # Use year from right token if available
                        if "year" in right:
                            target_year = int(right.get("year", "").strip('"'))
                        else:
                            target_year = base_time.year

                        # Find last weekend of the month (Saturday-Sunday)
                        first_day = datetime(target_year, month_num, 1, 0, 0, 0)
                        _, end_of_month = get_month_range(first_day)

                        # Find last Sunday of the month
                        last_day = end_of_month
                        days_back = (last_day.weekday() - 6) % 7  # 6 = Sunday
                        last_sunday = last_day - relativedelta(days=days_back)
                        last_saturday = last_sunday - relativedelta(days=1)

                        start = last_saturday.replace(hour=0, minute=0, second=0, microsecond=0)
                        end = last_sunday.replace(hour=23, minute=59, second=59, microsecond=0)
                        return (
                            [
                                [
                                    start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                                    end.strftime("%Y-%m-%dT%H:%M:%SZ"),
                                ]
                            ],
                            (k - i + 1),
                        )

                # Extract weekday name
                week_day_str = None
                if left.get("type") == "token":
                    token_val = left.get("value", "").strip().lower()
                    weekday_names = [
                        "monday",
                        "tuesday",
                        "wednesday",
                        "thursday",
                        "friday",
                        "saturday",
                        "sunday",
                    ]
                    if token_val in weekday_names:
                        week_day_str = token_val
                else:
                    week_day_str = left.get("week_day", "").strip('"').lower()

                # Only proceed if we have a valid weekday
                if not week_day_str:
                    pass  # Skip this case, will fall through to other cases
                else:
                    # detect preceding composite modifier
                    position = 0  # 0 表示本月内第一个匹配，-1 表示最后一个
                    p = i - 1
                    while (
                        p >= 0
                        and tokens[p].get("type") == "token"
                        and tokens[p].get("value", "").strip() == ""
                    ):
                        p -= 1
                    if p >= 0 and tokens[p].get("type") == "time_composite_relative":
                        tm = tokens[p].get("time_modifier", "").strip('"')
                        if tm:
                            try:
                                tmi = int(tm)
                                # 约定：-1 -> last, 1 -> next(=first), 0 -> this(=first)
                                position = -1 if tmi < 0 else 1
                            except ValueError:
                                position = 0
                    # compute weekday in target month
                    month_name = right.get("month", "").strip('"')
                    month_num = month_name_to_number(month_name)
                    if not month_num:
                        return None

                    # Use year from right token if available, otherwise use base_time.year
                    if "year" in right:
                        target_year = int(right.get("year", "").strip('"'))
                    else:
                        target_year = base_time.year
                    # 若目标月已经过去且使用 "next" 也可以放到下一年，这里遵循简单语义：使用当前年
                    first_day = datetime(target_year, month_num, 1, 0, 0, 0)
                    # 找该月的所有该 weekday
                    weekday_map = {
                        "monday": 0,
                        "tuesday": 1,
                        "wednesday": 2,
                        "thursday": 3,
                        "friday": 4,
                        "saturday": 5,
                        "sunday": 6,
                    }
                    wd = week_day_str
                    if wd not in weekday_map:
                        return None
                    target_wd = weekday_map[wd]
                    # 首个该 weekday
                    delta = (target_wd - first_day.weekday()) % 7
                    first_occurrence = (
                        first_day if delta == 0 else first_day + relativedelta(days=delta)
                    )
                    if position == -1:
                        # 最后一个该 weekday：找到月末再回退
                        _, end_of_month = get_month_range(first_day)
                        last_day = end_of_month
                        back = (last_day.weekday() - target_wd) % 7
                        last_occurrence = last_day - relativedelta(days=back)
                        start = last_occurrence.replace(hour=0, minute=0, second=0, microsecond=0)
                        end = last_occurrence.replace(hour=23, minute=59, second=59, microsecond=0)
                        return (
                            [
                                [
                                    start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                                    end.strftime("%Y-%m-%dT%H:%M:%SZ"),
                                ]
                            ],
                            (k - (p if p >= 0 else i) + 1),
                        )
                    else:
                        # 默认第一个（或 next/this）
                        start = first_occurrence.replace(hour=0, minute=0, second=0, microsecond=0)
                        end = first_occurrence.replace(hour=23, minute=59, second=59, microsecond=0)
                        return (
                            [
                                [
                                    start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                                    end.strftime("%Y-%m-%dT%H:%M:%SZ"),
                                ]
                            ],
                            (k - i + 1),
                        )

            # Case D: left is quarter_rule; right provides year
            if left.get("type") == "quarter_rule":
                year_str = None
                # Right is time_utc with year
                if right.get("type") == "time_utc" and "year" in right:
                    year_str = right.get("year")
                # Right is token with 4-digit year
                elif right.get("type") == "token":
                    val = right.get("value", "").strip()
                    if val.isdigit() and len(val) == 4:
                        year_int = int(val)
                        if 1900 <= year_int <= 2099:
                            year_str = val

                if year_str:
                    quarter_parser = self.parsers.get("quarter_rule")
                    if quarter_parser:
                        synth = {
                            "type": "quarter_rule",
                            "quarter": left.get("quarter"),
                            "year": year_str,
                        }
                        res = quarter_parser.parse(synth, base_time)
                        if res:
                            return (res, (k - i + 1))

        except Exception as e:
            self.logger.debug(f"Error in try_merge: {e}")
            return None

        return None
