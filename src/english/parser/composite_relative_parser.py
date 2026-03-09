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

from .base_parser import BaseParser


class CompositeRelativeParser(BaseParser):
    """
    Composite relative time parser
    Handles complex relative expressions like:
    - last day of february 2020
    - first day of year 2000
    - last month of year 2000
    - day before/after [event]
    """

    MONTH_MAP = {
        "january": 1,
        "february": 2,
        "march": 3,
        "april": 4,
        "may": 5,
        "june": 6,
        "july": 7,
        "august": 8,
        "september": 9,
        "october": 10,
        "november": 11,
        "december": 12,
    }

    WEEKDAY_MAP = {
        "monday": 0,
        "tuesday": 1,
        "wednesday": 2,
        "thursday": 3,
        "friday": 4,
        "saturday": 5,
        "sunday": 6,
        "mon": 0,
        "tue": 1,
        "wed": 2,
        "thu": 3,
        "fri": 4,
        "sat": 5,
        "sun": 6,
    }

    def parse(self, token, base_time):  # noqa: C901
        """
        Parse composite relative time token

        Args:
            token (dict): Token containing position, unit, and target info
            base_time (datetime): Base time reference

        Returns:
            list: Time range in UTC format
        """
        # Extract all relevant fields
        position = token.get("position", "").strip('"')
        ordinal_position = token.get("ordinal_position", "").strip('"')
        ordinal = token.get("ordinal", "").strip('"')  # For "ordinal + last" patterns
        unit = token.get("unit", "").strip('"')
        month_str = token.get("month", "").strip('"')
        day_str = token.get("day", "").strip('"')
        year_str = token.get("year", "").strip('"')
        week_day = token.get("week_day", "").strip('"')
        relation = token.get("relation", "").strip('"')
        boundary = token.get("boundary", "").strip('"')  # For "beginning/end of" patterns
        range_type = token.get("range", "").strip('"')  # For "by" range patterns

        # Get offsets
        offset_year = token.get("offset_year", "").strip('"')
        offset_month = token.get("offset_month", "").strip('"')
        offset_week = token.get("offset_week", "").strip('"')

        # Get modifiers (for possessive forms like "last year's")
        modifier_year = token.get("modifier_year", "").strip('"')
        modifier_month = token.get("modifier_month", "").strip('"')
        time_modifier = token.get("time_modifier", "").strip('"')

        # Get season field
        season = token.get("season", "").strip('"')

        # Get year field (for season + year patterns)
        year = token.get("year", "").strip('"')

        # Get value and direction fields (for "N weekdays back/ago" patterns)
        value_str = token.get("value", "").strip('"')
        direction = token.get("direction", "").strip('"')

        # Handle modifier fields first (for possessive forms like "last year's")
        if modifier_year:
            try:

                years_delta = int(modifier_year)
                target_date = base_time.replace(year=base_time.year + years_delta)
                start_of_year, end_of_year = self._get_year_range(target_date)
                return self._format_time_result(start_of_year, end_of_year)
            except (ValueError, TypeError):
                pass

        if modifier_month:
            try:

                months_delta = int(modifier_month)
                target_date = base_time + relativedelta(months=months_delta)
                start_of_month, end_of_month = self._get_month_range(target_date)
                return self._format_time_result(start_of_month, end_of_month)
            except (ValueError, TypeError):
                pass

        # Handle boundary patterns (beginning/end of + time_modifier + unit)
        # e.g., "beginning of this quarter" -> boundary: "beginning" time_modifier: "0" unit: "quarter"
        if boundary and time_modifier and unit:
            return self._handle_boundary_pattern(
                base_time, boundary, time_modifier, unit, range_type
            )

        # Handle "N + weekdays + back/ago" pattern
        # e.g., "2 thursdays back" -> value: "2" week_day: "thursday" direction: "-1"
        if week_day and value_str and direction:
            try:
                direction_val = int(direction)
                count = int(value_str)
                weekday_num = self.WEEKDAY_MAP.get(week_day.lower())

                if weekday_num is None or direction_val >= 0:
                    return []

                # 从当前日期往回数第N个指定星期
                # 算法：从 base_time 往回找，遇到指定星期就计数
                current_date = base_time
                found_count = 0

                while found_count < count:
                    # 往回走一天
                    current_date = current_date - timedelta(days=1)
                    # 检查是否是目标星期
                    if current_date.weekday() == weekday_num:
                        found_count += 1

                # current_date 现在是第N个目标星期
                target_day = current_date.replace(hour=0, minute=0, second=0, microsecond=0)
                day_end = target_day.replace(hour=23, minute=59, second=59, microsecond=0)
                return self._format_time_result(target_day, day_end)

            except (ValueError, TypeError):
                pass

        # Handle weekday + time_modifier (e.g., "wednesday after next")
        # But not if there's a month (that's handled by Pattern 2 below)
        if week_day and time_modifier and not month_str:
            try:
                from datetime import timedelta as _td

                week_mod = int(time_modifier)

                weekday_map = {
                    "monday": 0,
                    "tuesday": 1,
                    "wednesday": 2,
                    "thursday": 3,
                    "friday": 4,
                    "saturday": 5,
                    "sunday": 6,
                }
                wd = week_day.lower()
                if wd not in weekday_map:
                    return []

                target_wd = weekday_map[wd]

                # 计算逻辑：
                # - time_modifier=1: "next friday" = 找到下一个指定weekday
                # - time_modifier=2: "friday after next" = 找到下一个指定weekday，然后再加上1周

                # 找到下一个指定weekday
                current_wd = base_time.weekday()
                days_until_target = (target_wd - current_wd) % 7
                if days_until_target == 0:
                    # 如果今天就是目标weekday，则取下周的
                    days_until_target = 7

                next_target = base_time + _td(days=days_until_target)

                # 如果是"after next"（time_modifier=2），则再加上1周
                if week_mod == 2:
                    next_target = next_target + _td(weeks=1)
                elif week_mod > 2:
                    # 如果是"after next after next"等，加上(week_mod-1)周
                    next_target = next_target + _td(weeks=week_mod - 1)

                target_day = next_target.replace(hour=0, minute=0, second=0, microsecond=0)
                day_end = target_day.replace(hour=23, minute=59, second=59, microsecond=0)
                return self._format_time_result(target_day, day_end)
            except (ValueError, TypeError):
                pass

        # Handle standalone offset_week (e.g., "the week after next")
        if offset_week and not week_day and not month_str:
            try:
                from datetime import timedelta as _td

                week_mod = int(offset_week)
                target_base = base_time + _td(weeks=week_mod)
                week_start = (target_base - _td(days=target_base.weekday())).replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
                week_end = week_start + _td(days=6, hours=23, minutes=59, seconds=59)
                return self._format_time_result(week_start, week_end)
            except (ValueError, TypeError):
                pass

        # NEW Pattern 1: Handle "weekday of week_offset" (e.g., "wednesday of next week")
        if week_day and offset_week and not month_str:
            try:
                from datetime import timedelta as _td

                week_mod = int(offset_week)
                target_base = base_time + _td(weeks=week_mod)
                week_start = target_base - _td(days=target_base.weekday())

                weekday_map = {
                    "monday": 0,
                    "tuesday": 1,
                    "wednesday": 2,
                    "thursday": 3,
                    "friday": 4,
                    "saturday": 5,
                    "sunday": 6,
                }
                wd = week_day.lower()
                if wd in weekday_map:
                    day_offset = weekday_map[wd]
                    target_day = (week_start + _td(days=day_offset)).replace(
                        hour=0, minute=0, second=0, microsecond=0
                    )
                    day_end = target_day.replace(hour=23, minute=59, second=59, microsecond=0)
                    return self._format_time_result(target_day, day_end)
            except (ValueError, TypeError):
                pass

        # NEW Pattern 2: Handle "time_modifier + weekday + of + month" (e.g., "last Monday of March")
        if time_modifier and week_day and month_str:
            try:
                from datetime import datetime as _dt

                month_num = self.MONTH_MAP.get(month_str.lower())
                if not month_num:
                    return []

                # Determine target year
                target_year = base_time.year
                if year_str:
                    target_year = int(year_str)
                # For "last Monday of March", we want March of the current year
                # If we're already past March, we might want next year's March
                # But for now, let's use current year

                # Calculate the target weekday in the month
                first_day = _dt(target_year, month_num, 1, 0, 0, 0)

                weekday_map = {
                    "monday": 0,
                    "tuesday": 1,
                    "wednesday": 2,
                    "thursday": 3,
                    "friday": 4,
                    "saturday": 5,
                    "sunday": 6,
                }
                wd = week_day.lower()
                if wd not in weekday_map:
                    return []

                target_wd = weekday_map[wd]

                # Find the first occurrence of the weekday in the month
                delta = (target_wd - first_day.weekday()) % 7
                first_occurrence = (
                    first_day if delta == 0 else first_day + relativedelta(days=delta)
                )

                # Determine if we want first or last occurrence
                modifier_val = int(time_modifier)
                if modifier_val < 0:  # "last"
                    # Find the last occurrence: go to end of month and work backwards
                    _, end_of_month = self._get_month_range(first_day)
                    last_day = end_of_month
                    back = (last_day.weekday() - target_wd) % 7
                    last_occurrence = last_day - relativedelta(days=back)
                    target_day = last_occurrence
                else:  # "first" or "next"
                    target_day = first_occurrence

                start = target_day.replace(hour=0, minute=0, second=0, microsecond=0)
                end = target_day.replace(hour=23, minute=59, second=59, microsecond=0)
                return self._format_time_result(start, end)
            except (ValueError, TypeError):
                pass

        # NEW Case: month + time_modifier (e.g., "March after next", "April next")
        if month_str and time_modifier and not unit and not day_str and not year_str:
            month = self.MONTH_MAP.get(month_str.lower())
            if not month:
                return []
            try:
                modifier_val = int(time_modifier)
            except (ValueError, TypeError):
                modifier_val = None

            if modifier_val is not None:
                from datetime import datetime as _dt

                base_index = base_time.year * 12 + (base_time.month - 1)
                month_index = base_time.year * 12 + (month - 1)

                if modifier_val >= 1:
                    first_future = month_index
                    if first_future <= base_index:
                        first_future += 12
                    target_index = first_future + (modifier_val - 1) * 12
                elif modifier_val == 0:
                    target_index = month_index
                    if target_index < base_index:
                        target_index += 12
                else:  # modifier_val <= -1 (e.g., "last March")
                    last_past = month_index
                    if last_past >= base_index:
                        last_past -= 12
                    target_index = last_past + (modifier_val + 1) * 12

                target_year = target_index // 12
                target_month = target_index % 12 + 1

                try:
                    target_anchor = _dt(target_year, target_month, 1)
                except ValueError:
                    return []

                start, end = self._get_month_range(target_anchor)
                return self._format_time_result(start, end)

        # NEW Case: month + day + year_offset
        # e.g., "august 20 last year"
        if month_str and day_str and offset_year:
            month = self.MONTH_MAP.get(month_str.lower())
            if not month:
                return []
            try:
                day = int(day_str)
                year_offset = int(offset_year)

                target_date = base_time.replace(
                    year=base_time.year + year_offset,
                    month=month,
                    day=day,
                    hour=0,
                    minute=0,
                    second=0,
                )
                return self._format_time_result(
                    target_date, target_date.replace(hour=23, minute=59, second=59)
                )
            except (ValueError, TypeError):
                return []

        # NEW Case: month + year_offset
        # e.g., "august last year"
        if month_str and offset_year and not day_str:
            month = self.MONTH_MAP.get(month_str.lower())
            if not month:
                return []
            try:
                year_offset = int(offset_year)
                target_date = base_time.replace(year=base_time.year + year_offset, month=month)
                start, end = self._get_month_range(target_date)
                return self._format_time_result(start, end)
            except (ValueError, TypeError):
                return []

        # NEW Case: ordinal_position + unit + month
        # e.g., "last year september" -> ordinal_position: "-1" unit: "year" month: "september"
        if ordinal_position and unit and month_str and not day_str:
            month = self.MONTH_MAP.get(month_str.lower())
            if not month:
                return []
            try:
                position = int(ordinal_position)
                if unit == "year":
                    # Calculate target year
                    target_year = base_time.year + position
                    target_date = base_time.replace(year=target_year, month=month)
                    start, end = self._get_month_range(target_date)
                    return self._format_time_result(start, end)
                elif unit == "month":
                    # Calculate target month
                    total_months = base_time.year * 12 + base_time.month + position
                    target_year = total_months // 12
                    target_month = total_months % 12
                    if target_month == 0:
                        target_month = 12
                        target_year -= 1
                    target_date = base_time.replace(year=target_year, month=target_month)
                    start, end = self._get_month_range(target_date)
                    return self._format_time_result(start, end)
            except (ValueError, TypeError):
                return []

        # NEW Case: time_modifier + value + unit
        # e.g., "previous two months" -> time_modifier: "-1" value: "2" unit: "month"
        # e.g., "next three days" -> time_modifier: "1" value: "3" unit: "day"
        time_modifier = token.get("time_modifier", "").strip('"')
        value_str = token.get("value", "").strip('"')

        # Handle simple time_modifier without value/unit (e.g., "next", "last")
        # These are typically used as modifiers for other time expressions
        # But exclude cases where we have a season field
        if (
            time_modifier
            and not value_str
            and not unit
            and not day_str
            and not month_str
            and not season
        ):
            # For simple modifiers like "next" or "last", we can't determine the unit
            # This should be handled by the context merger or other parsers
            # Return empty result to indicate this needs context
            return []

        # NEW Case: time_modifier + unit (no value)
        # e.g., "this quarter" -> time_modifier: "0" unit: "quarter"
        # e.g., "next quarter" -> time_modifier: "1" unit: "quarter"
        # e.g., "last quarter" -> time_modifier: "-1" unit: "quarter"
        if time_modifier and unit and not value_str and not day_str and not month_str:
            try:
                modifier = int(time_modifier)

                if unit == "day":
                    # Calculate target date
                    target_date = base_time + timedelta(days=modifier)
                    start, end = self._get_day_range(target_date)
                    return self._format_time_result(start, end)
                elif unit == "week":
                    # Calculate target date
                    target_date = base_time + timedelta(weeks=modifier)
                    start, end = self._get_week_range(target_date)
                    return self._format_time_result(start, end)
                elif unit == "month":
                    # Calculate target date
                    total_months = base_time.year * 12 + base_time.month + modifier
                    target_year = total_months // 12
                    target_month = total_months % 12
                    if target_month == 0:
                        target_month = 12
                        target_year -= 1
                    target_date = base_time.replace(year=target_year, month=target_month)
                    start, end = self._get_month_range(target_date)
                    return self._format_time_result(start, end)
                elif unit == "year":
                    # Calculate target date
                    target_date = base_time.replace(year=base_time.year + modifier)
                    start, end = self._get_year_range(target_date)
                    return self._format_time_result(start, end)
                elif unit == "quarter":
                    # Each quarter = 3 months

                    shifted = base_time + relativedelta(months=3 * modifier)
                    # Align to quarter start month (1,4,7,10)
                    q_idx = ((shifted.month - 1) // 3) * 3 + 1
                    quarter_start = shifted.replace(month=q_idx)
                    start, _ = self._get_month_range(quarter_start)
                    end_month_time = quarter_start + relativedelta(months=2)
                    _, end = self._get_month_range(end_month_time)
                    return self._format_time_result(start, end)
            except (ValueError, TypeError):
                return []

        # NEW Pattern: Handle "time_modifier + unit + in + month + year"
        # e.g., "last day in october 2015" -> time_modifier: "-1" unit: "day" month: "october" year: "2015"
        if time_modifier and unit and month_str and year_str:
            try:
                modifier = int(time_modifier)
                month_num = self.MONTH_MAP.get(month_str.lower())
                year = int(year_str)

                if not month_num:
                    return []

                if unit == "day":
                    if modifier == -1:  # "last day"
                        # Last day of the month
                        target_date = datetime(year, month_num, 1)
                        _, last_day = self._get_month_range(target_date)
                        day_start = last_day.replace(hour=0, minute=0, second=0, microsecond=0)
                        day_end = last_day.replace(hour=23, minute=59, second=59, microsecond=0)
                        return self._format_time_result(day_start, day_end)
                    elif modifier == 1:  # "next day" (first day of next month)
                        # First day of the month
                        first_day = datetime(year, month_num, 1, 0, 0, 0)
                        day_end = first_day.replace(hour=23, minute=59, second=59, microsecond=0)
                        return self._format_time_result(first_day, day_end)
                elif unit == "week":
                    if modifier == -1:  # "last week"
                        # Last week of the month
                        target_date = datetime(year, month_num, 1)
                        start_of_month, end_of_month = self._get_month_range(target_date)

                        # Find the last Sunday of the month
                        days_back = (end_of_month.weekday() + 1) % 7
                        last_sunday = end_of_month - timedelta(days=days_back)
                        last_monday = last_sunday - timedelta(days=6)

                        week_start = last_monday.replace(hour=0, minute=0, second=0, microsecond=0)
                        week_end = last_sunday.replace(hour=23, minute=59, second=59, microsecond=0)
                        return self._format_time_result(week_start, week_end)
                    elif modifier == 1:  # "next week" (first week of next month)
                        # First week of the month
                        first_day = datetime(year, month_num, 1, 0, 0, 0)

                        # Find the first Monday of the month
                        days_until_monday = (7 - first_day.weekday()) % 7
                        if days_until_monday == 0 and first_day.weekday() == 0:
                            first_monday = first_day
                        else:
                            first_monday = first_day + timedelta(days=days_until_monday)

                        first_sunday = first_monday + timedelta(days=6)
                        week_start = first_monday.replace(hour=0, minute=0, second=0, microsecond=0)
                        week_end = first_sunday.replace(
                            hour=23, minute=59, second=59, microsecond=0
                        )
                        return self._format_time_result(week_start, week_end)

            except (ValueError, TypeError):
                pass

        # NEW Pattern: Handle "day + of + the + time_modifier + unit"
        # e.g., "20th of the next month" -> day: "20" time_modifier: "1" unit: "month"
        # e.g., "15th of the previous month" -> day: "15" time_modifier: "-1" unit: "month"
        if day_str and time_modifier and unit and not month_str and not year_str:
            try:
                # Extract numeric part from ordinal day (e.g., "20th" -> "20")
                import re

                day_match = re.match(r"(\d+)", day_str)
                if not day_match:
                    return []
                day = int(day_match.group(1))
                modifier = int(time_modifier)

                if unit == "month":
                    # Calculate target month

                    target_date = base_time + relativedelta(months=modifier)
                    target_year = target_date.year
                    target_month = target_date.month

                    # Create the target day
                    try:
                        target_day = datetime(target_year, target_month, day, 0, 0, 0)
                        day_end = target_day.replace(hour=23, minute=59, second=59, microsecond=0)
                        return self._format_time_result(target_day, day_end)
                    except ValueError:
                        # Invalid day for the month (e.g., Feb 30), return empty
                        return []
                elif unit == "year":
                    # Calculate target year
                    target_year = base_time.year + modifier

                    # Create the target day
                    try:
                        target_day = datetime(target_year, base_time.month, day, 0, 0, 0)
                        day_end = target_day.replace(hour=23, minute=59, second=59, microsecond=0)
                        return self._format_time_result(target_day, day_end)
                    except ValueError:
                        # Invalid day for the month (e.g., Feb 30), return empty
                        return []

            except (ValueError, TypeError):
                pass

        # NEW Pattern: Handle "ordinal + weekday + of/in + month + year"
        # e.g., "first tuesday of october" -> ordinal: "1" week_day: "tuesday" month: "october"
        # e.g., "third tuesday of september 2014" -> ordinal: "3" week_day: "tuesday" month: "september" year: "2014"
        if ordinal and week_day and month_str and not day_str and not unit:
            try:
                ordinal_num = int(ordinal)
                month_num = self.MONTH_MAP.get(month_str.lower())

                if not month_num:
                    return []

                # Determine year
                target_year = base_time.year
                if year_str:
                    target_year = int(year_str)

                # Get the first day of the month
                first_day = datetime(target_year, month_num, 1, 0, 0, 0)

                # Map weekday to number (week_day can be either name or number)
                if week_day.isdigit():
                    # week_day is already a number (0-6)
                    target_wd = int(week_day)
                else:
                    # week_day is a name, map to number
                    weekday_map = {
                        "monday": 0,
                        "tuesday": 1,
                        "wednesday": 2,
                        "thursday": 3,
                        "friday": 4,
                        "saturday": 5,
                        "sunday": 6,
                    }
                    wd = week_day.lower()
                    if wd not in weekday_map:
                        return []
                    target_wd = weekday_map[wd]

                if target_wd < 0 or target_wd > 6:
                    return []

                # Find the first occurrence of the weekday in the month
                delta = (target_wd - first_day.weekday()) % 7
                first_occurrence = first_day if delta == 0 else first_day + timedelta(days=delta)

                # Find the Nth occurrence
                if ordinal_num > 0:
                    # Find the Nth occurrence (1st, 2nd, 3rd, etc.)
                    target_day = first_occurrence + timedelta(weeks=(ordinal_num - 1))

                    # Check if the target day is still in the same month
                    if target_day.month == month_num:
                        day_start = target_day.replace(hour=0, minute=0, second=0, microsecond=0)
                        day_end = target_day.replace(hour=23, minute=59, second=59, microsecond=0)
                        return self._format_time_result(day_start, day_end)
                    else:
                        # The Nth occurrence doesn't exist in this month
                        return []
                else:
                    # Invalid ordinal
                    return []

            except (ValueError, TypeError):
                pass

        if time_modifier and value_str and unit and not day_str and not month_str:
            try:
                modifier = int(time_modifier)
                value = int(value_str)

                # Following Chinese FST logic: previous/next + value + unit = from (now +/- value*unit) to now
                # 参考中文FST逻辑：previous/next + 数值 + 单位 = 从(现在 +/- 数值*单位)到现在
                if unit == "day":
                    # Calculate time range from start to end
                    if modifier < 0:  # previous/last
                        start_time = base_time + timedelta(days=modifier * value)
                        end_time = base_time
                    else:  # next
                        start_time = base_time
                        end_time = base_time + timedelta(days=modifier * value)
                    return self._format_time_result(start_time, end_time)
                elif unit == "week":
                    # Calculate time range from start to end
                    if modifier < 0:  # previous/last
                        start_time = base_time + timedelta(weeks=modifier * value)
                        end_time = base_time
                    else:  # next
                        start_time = base_time
                        end_time = base_time + timedelta(weeks=modifier * value)
                    return self._format_time_result(start_time, end_time)
                elif unit == "month":
                    # Calculate time range from start to end

                    if modifier < 0:  # previous/last
                        start_time = base_time + relativedelta(months=modifier * value)
                        end_time = base_time
                    else:  # next
                        start_time = base_time
                        end_time = base_time + relativedelta(months=modifier * value)
                    return self._format_time_result(start_time, end_time)
                elif unit == "year":
                    # Calculate time range from start to end

                    if modifier < 0:  # previous/last
                        start_time = base_time + relativedelta(years=modifier * value)
                        end_time = base_time
                    else:  # next
                        start_time = base_time
                        end_time = base_time + relativedelta(years=modifier * value)
                    return self._format_time_result(start_time, end_time)
                elif unit == "quarter":
                    # Each quarter = 3 months

                    shifted = base_time + relativedelta(months=3 * modifier * value)
                    # Align to quarter start month (1,4,7,10)
                    q_idx = ((shifted.month - 1) // 3) * 3 + 1
                    quarter_start = shifted.replace(month=q_idx)
                    start, _ = self._get_month_range(quarter_start)
                    end_month_time = quarter_start + relativedelta(months=2)
                    _, end = self._get_month_range(end_month_time)
                    return self._format_time_result(start, end)
            except (ValueError, TypeError):
                return []

        # NEW Case: day + month_offset
        # e.g., "20th last month"
        if day_str and offset_month and not month_str:
            try:
                day = int(day_str)
                month_offset = int(offset_month)

                # Calculate target month
                total_months = base_time.year * 12 + base_time.month + month_offset
                target_year = total_months // 12
                target_month = total_months % 12
                if target_month == 0:
                    target_month = 12
                    target_year -= 1

                target_date = base_time.replace(
                    year=target_year,
                    month=target_month,
                    day=day,
                    hour=0,
                    minute=0,
                    second=0,
                )
                return self._format_time_result(
                    target_date, target_date.replace(hour=23, minute=59, second=59)
                )
            except (ValueError, TypeError):
                return []

        # NEW Case: weekday + week_offset
        # e.g., "monday last week"
        if week_day and offset_week:
            try:
                weekday_num = self.WEEKDAY_MAP.get(week_day.lower())
                if weekday_num is None:
                    return []

                week_offset = int(offset_week)

                # Calculate target date
                # Find the target weekday in the target week
                current_weekday = base_time.weekday()
                days_to_target = weekday_num - current_weekday
                days_to_target += week_offset * 7

                target_date = base_time + timedelta(days=days_to_target)
                target_date = target_date.replace(hour=0, minute=0, second=0)

                return self._format_time_result(
                    target_date, target_date.replace(hour=23, minute=59, second=59)
                )
            except (ValueError, TypeError):
                return []

        # NEW Case: ordinal_position + unit + year
        # e.g., "last day of 2017" -> ordinal_position: "-1" unit: "day" year: "2017"
        if ordinal_position and unit == "day" and year_str and not month_str:
            try:
                ordinal = int(ordinal_position)
                year = int(year_str)

                if ordinal == -1:  # last day
                    # Last day of the year (Dec 31)
                    last_day = datetime(year, 12, 31, 0, 0, 0)
                    return self._format_time_result(
                        last_day, last_day.replace(hour=23, minute=59, second=59)
                    )
                elif ordinal > 0:  # first, second, third, etc.
                    # Nth day of the year (Jan 1 + ordinal - 1 days)
                    target_day = datetime(year, 1, 1, 0, 0, 0) + timedelta(days=ordinal - 1)
                    return self._format_time_result(
                        target_day, target_day.replace(hour=23, minute=59, second=59)
                    )
            except (ValueError, TypeError):
                pass

        # NEW Case: ordinal_position + unit + month + year (for week)
        # e.g., "first week of january 2020"
        if ordinal_position and unit == "week" and month_str and year_str:
            try:
                ordinal = int(ordinal_position)
                month = self.MONTH_MAP.get(month_str.lower())
                year = int(year_str)
                if not month:
                    return []

                # Calculate the target week
                start_of_month = datetime(year, month, 1, 0, 0, 0)
                start, end = self._get_month_range(start_of_month)

                if ordinal == -1:  # last week
                    # Find the last week of the month (last 7 days)
                    week_start = end.replace(hour=0, minute=0, second=0) - timedelta(days=6)
                    return self._format_time_result(week_start, end)
                elif ordinal > 0:
                    # Week indexing starts from the Monday of the week containing the first day of the month
                    first_week_start = start_of_month - timedelta(days=start_of_month.weekday())
                    week_start = first_week_start + timedelta(weeks=ordinal - 1)
                    week_end = week_start + timedelta(days=6, hours=23, minutes=59, seconds=59)

                    if week_start > end:
                        return []

                    week_start_clamped = max(week_start, start)
                    week_end_clamped = min(week_end, end)

                    return self._format_time_result(week_start_clamped, week_end_clamped)
            except (ValueError, TypeError):
                pass

        # NEW Case: ordinal_position + unit + month (for week)
        # e.g., "last week of june"
        if ordinal_position and unit == "week" and month_str and not year_str:
            try:
                ordinal = int(ordinal_position)
                month = self.MONTH_MAP.get(month_str.lower())
                if not month:
                    return []

                # Determine year
                year = base_time.year
                if month < base_time.month and ordinal > 0:
                    year += 1

                # Calculate the target week
                start_of_month = datetime(year, month, 1, 0, 0, 0)
                start, end = self._get_month_range(start_of_month)

                if ordinal == -1:  # last week
                    # Find the last week of the month
                    week_start = end.replace(hour=0, minute=0, second=0) - timedelta(days=6)
                    return self._format_time_result(week_start, end)
                elif ordinal > 0:
                    first_week_start = start_of_month - timedelta(days=start_of_month.weekday())
                    week_start = first_week_start + timedelta(weeks=ordinal - 1)
                    week_end = week_start + timedelta(days=6, hours=23, minutes=59, seconds=59)

                    if week_start > end:
                        return []

                    week_start_clamped = max(week_start, start)
                    week_end_clamped = min(week_end, end)

                    return self._format_time_result(week_start_clamped, week_end_clamped)
            except (ValueError, TypeError):
                pass

        # NEW Case: ordinal_position + unit + year (for month)
        # e.g., "last month of 2000"
        if ordinal_position and unit == "month" and year_str and not month_str:
            try:
                ordinal = int(ordinal_position)
                year = int(year_str)

                if ordinal == -1:  # last month (December)
                    start = datetime(year, 12, 1, 0, 0, 0)
                    end = datetime(year, 12, 31, 23, 59, 59)
                    return self._format_time_result(start, end)
                elif ordinal > 0 and ordinal <= 12:
                    # Nth month of the year
                    month = ordinal
                    target_date = datetime(year, month, 1, 0, 0, 0)
                    start, end = self._get_month_range(target_date)
                    return self._format_time_result(start, end)
            except (ValueError, TypeError):
                pass

        # NEW Case: standalone ordinal_position + unit (no "of ...")
        # e.g., "last day", "first week", "second month"
        if ordinal_position and unit and not month_str and not year_str:
            try:
                ordinal = int(ordinal_position)

                if unit == "day":
                    if ordinal == -1:  # last day (yesterday)
                        target = base_time - timedelta(days=1)
                        return self._format_time_result(
                            target.replace(hour=0, minute=0, second=0),
                            target.replace(hour=23, minute=59, second=59),
                        )
                    elif ordinal > 0:
                        # Nth day of current month
                        target = base_time.replace(day=ordinal, hour=0, minute=0, second=0)
                        return self._format_time_result(
                            target, target.replace(hour=23, minute=59, second=59)
                        )

                elif unit == "week":
                    if ordinal == -1:  # last week
                        week_start = base_time - timedelta(days=base_time.weekday() + 7)
                        week_start = week_start.replace(hour=0, minute=0, second=0)
                        week_end = week_start + timedelta(days=6, hours=23, minutes=59, seconds=59)
                        return self._format_time_result(week_start, week_end)
                    elif ordinal > 0:
                        # Nth week of current month
                        start_of_month = base_time.replace(day=1, hour=0, minute=0, second=0)
                        week_start = start_of_month + timedelta(days=(ordinal - 1) * 7)
                        _, month_end = self._get_month_range(base_time)
                        week_end = min(
                            week_start + timedelta(days=6, hours=23, minutes=59, seconds=59),
                            month_end,
                        )
                        return self._format_time_result(week_start, week_end)

                elif unit == "month":
                    if ordinal == -1:  # last month
                        total_months = base_time.year * 12 + base_time.month - 1
                        target_year = total_months // 12
                        target_month = total_months % 12
                        if target_month == 0:
                            target_month = 12
                            target_year -= 1
                        target = base_time.replace(year=target_year, month=target_month)
                        start, end = self._get_month_range(target)
                        return self._format_time_result(start, end)
                    elif ordinal > 0 and ordinal <= 12:
                        # Nth month of current year
                        target = base_time.replace(month=ordinal)
                        start, end = self._get_month_range(target)
                        return self._format_time_result(start, end)

                elif unit == "year":
                    if ordinal == -1:  # last year
                        target = base_time.replace(year=base_time.year - 1)
                        start, end = self._get_year_range(target)
                        return self._format_time_result(start, end)
                    elif ordinal == 0:  # this year
                        start, end = self._get_year_range(base_time)
                        return self._format_time_result(start, end)
                    elif ordinal == 1:  # next year
                        target = base_time.replace(year=base_time.year + 1)
                        start, end = self._get_year_range(target)
                        return self._format_time_result(start, end)
                elif unit == "quarter":
                    # Handle ordinal quarter (e.g., "third quarter", "3rd qtr")
                    if ordinal > 0 and ordinal <= 4:
                        # Calculate the target quarter

                        # Get current quarter
                        current_quarter = ((base_time.month - 1) // 3) + 1
                        # Calculate target quarter
                        target_quarter = ordinal
                        # Calculate months to shift
                        months_to_shift = (target_quarter - current_quarter) * 3
                        target_date = base_time + relativedelta(months=months_to_shift)
                        # Align to quarter start month (1,4,7,10)
                        q_idx = ((target_date.month - 1) // 3) * 3 + 1
                        quarter_start = target_date.replace(month=q_idx)
                        start, _ = self._get_month_range(quarter_start)
                        end_month_time = quarter_start + relativedelta(months=2)
                        _, end = self._get_month_range(end_month_time)
                        return self._format_time_result(start, end)
            except (ValueError, TypeError):
                pass

        # NEW Case: ordinal_position + unit + month [+ year] (for day)
        # e.g., "second day of march" or "last day of february 2020"
        if ordinal_position and unit == "day" and month_str:
            try:
                ordinal = int(ordinal_position)
                month = self.MONTH_MAP.get(month_str.lower())
                if not month:
                    return []

                # Determine year
                if year_str:
                    year = int(year_str)
                else:
                    year = base_time.year
                    # If month has passed, might use next year
                    if month < base_time.month and ordinal > 0:
                        year += 1

                if ordinal == -1:  # last day
                    # Last day of the month
                    start, end = self._get_month_range(base_time.replace(year=year, month=month))
                    last_day_start = end.replace(hour=0, minute=0, second=0)
                    last_day_end = end
                    return self._format_time_result(last_day_start, last_day_end)
                elif ordinal > 0:  # first, second, third, etc.
                    # Nth day of the month
                    target_day = datetime(year, month, ordinal, 0, 0, 0)
                    return self._format_time_result(
                        target_day, target_day.replace(hour=23, minute=59, second=59)
                    )
            except (ValueError, TypeError):
                pass

        # NEW Case: position + unit + month + year (for week)
        # e.g., "first week of january 2020" using position instead of ordinal_position
        # NOTE: Skip if ordinal is present (handled by "ordinal + last" pattern)
        if position and unit == "week" and month_str and year_str and not ordinal:
            try:
                # Map position to ordinal value
                pos_map = {"first": 1, "last": -1}
                ordinal_val = pos_map.get(position, 0)
                if ordinal_val == 0:
                    return []

                month = self.MONTH_MAP.get(month_str.lower())
                year = int(year_str)
                if not month:
                    return []

                start_of_month = datetime(year, month, 1, 0, 0, 0)
                start, end = self._get_month_range(start_of_month)

                if ordinal_val == -1:  # last week
                    # Find the last Sunday of the month
                    days_back = (end.weekday() + 1) % 7
                    last_sunday = end - timedelta(days=days_back)
                    last_monday = last_sunday - timedelta(days=6)

                    week_start = last_monday.replace(hour=0, minute=0, second=0, microsecond=0)
                    week_end = last_sunday.replace(hour=23, minute=59, second=59, microsecond=0)
                    return self._format_time_result(week_start, week_end)
                elif ordinal_val > 0:
                    # Week indexing starts from the Monday of the week containing the first day of the month
                    first_day = datetime(year, month, 1, 0, 0, 0)
                    first_week_start = first_day - timedelta(days=first_day.weekday())
                    week_start = first_week_start + timedelta(weeks=ordinal_val - 1)
                    week_end = week_start + timedelta(days=6, hours=23, minutes=59, seconds=59)

                    if week_start > end:
                        return []

                    week_start_clamped = max(week_start, start)
                    week_end_clamped = min(week_end, end)

                    return self._format_time_result(week_start_clamped, week_end_clamped)
            except (ValueError, TypeError):
                pass

        # NEW Case: position + unit + month (for week)
        # e.g., "last week of june" using position instead of ordinal_position
        # NOTE: Skip if ordinal is present (handled by "ordinal + last" pattern)
        if position and unit == "week" and month_str and not year_str and not ordinal:
            try:
                pos_map = {"first": 1, "last": -1}
                ordinal_val = pos_map.get(position, 0)
                if ordinal_val == 0:
                    return []

                month = self.MONTH_MAP.get(month_str.lower())
                if not month:
                    return []

                year = base_time.year
                if month < base_time.month and ordinal_val > 0:
                    year += 1

                start_of_month = datetime(year, month, 1, 0, 0, 0)
                start, end = self._get_month_range(start_of_month)

                if ordinal_val == -1:  # last week
                    week_start = end.replace(hour=0, minute=0, second=0) - timedelta(days=6)
                    return self._format_time_result(week_start, end)
                elif ordinal_val > 0:
                    first_week_start = start_of_month - timedelta(days=start_of_month.weekday())
                    week_start = first_week_start + timedelta(weeks=ordinal_val - 1)
                    week_end = week_start + timedelta(days=6, hours=23, minutes=59, seconds=59)

                    if week_start > end:
                        return []

                    week_start_clamped = max(week_start, start)
                    week_end_clamped = min(week_end, end)

                    return self._format_time_result(week_start_clamped, week_end_clamped)
            except (ValueError, TypeError):
                pass

        # NEW Pattern: Handle "ordinal + last + unit + of + time"
        # e.g., "third last week of 2018", "second last day of May"
        # This must come BEFORE the "position + unit + month" check
        if ordinal and position == "last" and unit:
            try:
                ordinal_num = int(ordinal)

                if unit == "week" and month_str:
                    # Find the Nth last week of the month
                    month_num = self.MONTH_MAP.get(month_str.lower())
                    if not month_num:
                        return []

                    # Determine year
                    target_year = base_time.year
                    if year_str:
                        target_year = int(year_str)

                    # Get the month range
                    target_date = datetime(target_year, month_num, 1)
                    start_of_month, end_of_month = self._get_month_range(target_date)

                    # Find the last Sunday of the month
                    days_back = (end_of_month.weekday() + 1) % 7
                    last_sunday = end_of_month - timedelta(days=days_back)

                    # Go back (ordinal_num - 1) weeks
                    target_sunday = last_sunday - timedelta(weeks=(ordinal_num - 1))
                    target_monday = target_sunday - timedelta(days=6)

                    # Set full day range
                    week_start = target_monday.replace(hour=0, minute=0, second=0, microsecond=0)
                    week_end = target_sunday.replace(hour=23, minute=59, second=59, microsecond=0)

                    return self._format_time_result(week_start, week_end)

                elif unit == "week" and year_str:
                    # Find the Nth last week of the year
                    target_year = int(year_str)
                    last_day_of_year = datetime(target_year, 12, 31)

                    # Find the last Sunday of the year
                    days_back = (last_day_of_year.weekday() + 1) % 7
                    last_sunday = last_day_of_year - timedelta(days=days_back)

                    # Go back (ordinal_num - 1) weeks
                    target_sunday = last_sunday - timedelta(weeks=(ordinal_num - 1))
                    target_monday = target_sunday - timedelta(days=6)

                    # Set full day range
                    week_start = target_monday.replace(hour=0, minute=0, second=0, microsecond=0)
                    week_end = target_sunday.replace(hour=23, minute=59, second=59, microsecond=0)

                    return self._format_time_result(week_start, week_end)

                elif unit == "day" and month_str:
                    # Find the Nth last day of the month
                    month_num = self.MONTH_MAP.get(month_str.lower())
                    if not month_num:
                        return []

                    # Determine year
                    target_year = base_time.year
                    if year_str:
                        target_year = int(year_str)

                    target_date = datetime(target_year, month_num, 1)
                    _, last_day = self._get_month_range(target_date)

                    # For "second last day", ordinal_num=2, we go back 1 day (2-1=1)
                    # For "fifth last day", ordinal_num=5, we go back 4 days (5-1=4)
                    target_day = last_day - timedelta(days=(ordinal_num - 1))
                    # Reset to start of day
                    day_start = target_day.replace(hour=0, minute=0, second=0, microsecond=0)
                    day_end = target_day.replace(hour=23, minute=59, second=59, microsecond=0)
                    return self._format_time_result(day_start, day_end)

            except (ValueError, TypeError):
                pass

        # Case 1: position + unit + month [+ year] (for day)
        # e.g., "last day of february 2020"
        if position and unit == "day" and month_str:
            month = self.MONTH_MAP.get(month_str.lower())
            if not month:
                return []

            # Determine year
            if year_str:
                year = int(year_str)
            else:
                year = base_time.year
                # If month has passed, use next year for "next" or current year for "last"
                if month < base_time.month and position == "first":
                    year += 1

            if unit == "day":
                if position == "last":
                    # Last day of the month
                    start, end = self._get_month_range(base_time.replace(year=year, month=month))
                    # Get just the last day
                    last_day_start = end.replace(hour=0, minute=0, second=0)
                    last_day_end = end
                    result = self._format_time_result(last_day_start, last_day_end)
                    return result
                elif position == "first":
                    # First day of the month
                    first_day = base_time.replace(
                        year=year, month=month, day=1, hour=0, minute=0, second=0
                    )
                    result = self._format_time_result(
                        first_day, first_day.replace(hour=23, minute=59, second=59)
                    )
                    return result

        # Case 2: position + unit + year
        # e.g., "last day of year 2000", "last month of year 2000"
        elif position and unit and year_str:
            year = int(year_str)

            if unit == "day":
                if position == "last":
                    # Last day of the year (Dec 31)
                    last_day = datetime(year, 12, 31, 0, 0, 0)
                    return self._format_time_result(
                        last_day, last_day.replace(hour=23, minute=59, second=59)
                    )
                elif position == "first":
                    # First day of the year (Jan 1)
                    first_day = datetime(year, 1, 1, 0, 0, 0)
                    return self._format_time_result(
                        first_day, first_day.replace(hour=23, minute=59, second=59)
                    )

            elif unit == "month":
                if position == "last":
                    # Last month of the year (December)
                    start = datetime(year, 12, 1, 0, 0, 0)
                    end = datetime(year, 12, 31, 23, 59, 59)
                    return self._format_time_result(start, end)
                elif position == "first":
                    # First month of the year (January)
                    start = datetime(year, 1, 1, 0, 0, 0)
                    end = datetime(year, 1, 31, 23, 59, 59)
                    return self._format_time_result(start, end)

        # Case 3: relation (day before/after)
        # This needs to be combined with the next token
        # Return a marker for now
        elif relation:
            offset = int(relation)
            return [{"relation_offset": offset}]

        # NEW Case: Handle season + year
        # e.g., "summer in 2012" -> season: "summer" year: "2012"
        if season and year and not time_modifier:
            try:
                year_val = int(year)
                # Expand two-digit years
                if year_val < 100:
                    year_val = 2000 + year_val if year_val < 50 else 1900 + year_val

                # Calculate season range for the specified year
                start_time, end_time = self._get_season_range(year_val, season)

                return self._format_time_result(start_time, end_time)

            except (ValueError, TypeError):
                pass

        # NEW Case: Handle season with time_modifier
        # e.g., "this summer" -> time_modifier: "0" season: "summer"
        # e.g., "next winter" -> time_modifier: "1" season: "winter"
        # e.g., "last spring" -> time_modifier: "-1" season: "spring"
        # e.g., "this season" -> time_modifier: "0" season: "season"
        if season and time_modifier is not None and time_modifier != "":
            try:

                modifier = int(time_modifier)

                if season == "season":
                    # Handle generic "season" - need to determine which season based on modifier
                    if modifier == 0:
                        # "this season" - current season
                        current_season = self._get_current_season(base_time)
                        if current_season == "winter":
                            # For winter, use the year when winter starts (previous year)
                            start_time, end_time = self._get_season_range(
                                base_time.year - 1, current_season
                            )
                        else:
                            start_time, end_time = self._get_season_range(
                                base_time.year, current_season
                            )
                    elif modifier == 1:
                        # "next season" - next season
                        current_season = self._get_current_season(base_time)
                        next_season = self._get_next_season(current_season)
                        if current_season == "winter":
                            # If current season is winter, next season (spring) is in the same year
                            start_time, end_time = self._get_season_range(
                                base_time.year, next_season
                            )
                        else:
                            start_time, end_time = self._get_season_range(
                                base_time.year, next_season
                            )
                    elif modifier == -1:
                        # "last season" - previous season
                        current_season = self._get_current_season(base_time)
                        prev_season = self._get_previous_season(current_season)
                        if current_season == "winter":
                            # If current season is winter, previous season (autumn) is in the previous year
                            start_time, end_time = self._get_season_range(
                                base_time.year - 1, prev_season
                            )
                        elif current_season == "spring":
                            # If current season is spring, previous season (winter) is in the previous year
                            start_time, end_time = self._get_season_range(
                                base_time.year - 1, prev_season
                            )
                        else:
                            start_time, end_time = self._get_season_range(
                                base_time.year, prev_season
                            )
                    else:
                        # For other modifiers, calculate based on season offset
                        current_season = self._get_current_season(base_time)
                        target_season = self._get_season_by_offset(current_season, modifier)
                        target_year = base_time.year + (
                            modifier // 4
                        )  # Approximate year adjustment
                        start_time, end_time = self._get_season_range(target_year, target_season)
                else:
                    # Handle specific season names
                    target_year = base_time.year + modifier
                    start_time, end_time = self._get_season_range(target_year, season)

                return self._format_time_result(start_time, end_time)

            except (ValueError, TypeError):
                pass

        return []

    def _get_week_range(self, base_time):
        """Get start and end of week for a given date"""
        # Get start of week (Monday)
        days_since_monday = base_time.weekday()
        start_of_week = base_time - timedelta(days=days_since_monday)
        start_of_week = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)

        # Get end of week (Sunday)
        end_of_week = start_of_week + timedelta(days=6)
        end_of_week = end_of_week.replace(hour=23, minute=59, second=59, microsecond=0)

        return start_of_week, end_of_week

    def _get_next_season(self, current_season):
        """获取下一个季节"""
        season_order = ["spring", "summer", "autumn", "winter"]
        current_index = season_order.index(current_season)
        next_index = (current_index + 1) % 4
        return season_order[next_index]

    def _get_previous_season(self, current_season):
        """获取上一个季节"""
        season_order = ["spring", "summer", "autumn", "winter"]
        current_index = season_order.index(current_season)
        prev_index = (current_index - 1) % 4
        return season_order[prev_index]

    def _get_season_by_offset(self, current_season, offset):
        """根据偏移量获取目标季节"""
        season_order = ["spring", "summer", "autumn", "winter"]
        current_index = season_order.index(current_season)
        target_index = (current_index + offset) % 4
        return season_order[target_index]

    def _handle_boundary_pattern(  # noqa: C901
        self, base_time, boundary, time_modifier, unit, range_type=None
    ):
        """
        Handle boundary patterns (beginning/end of + time_modifier + unit)
        e.g., "beginning of this quarter" -> boundary: "beginning" time_modifier: "0" unit: "quarter"
        e.g., "by EOM" -> boundary: "end" time_modifier: "0" unit: "month" range_type: "by"
        """
        try:
            # Calculate target date based on time_modifier and unit
            modifier = int(time_modifier)
            target_date = base_time

            if unit == "month":
                target_date = target_date + relativedelta(months=modifier)
            elif unit == "quarter":
                # For quarters, we need to calculate the target quarter first
                # modifier: 0 = this quarter, 1 = next quarter, -1 = last quarter
                current_quarter = (base_time.month - 1) // 3 + 1
                target_quarter = current_quarter + modifier
                target_year = base_time.year

                # Handle year boundaries
                while target_quarter > 4:
                    target_quarter -= 4
                    target_year += 1
                while target_quarter < 1:
                    target_quarter += 4
                    target_year -= 1

                # Calculate the first month of the target quarter
                target_month = (target_quarter - 1) * 3 + 1
                target_date = target_date.replace(year=target_year, month=target_month, day=1)
            elif unit == "year":
                target_date = target_date + relativedelta(years=modifier)
            elif unit == "week":
                target_date = target_date + timedelta(weeks=modifier)
            elif unit == "day":
                target_date = target_date + timedelta(days=modifier)
            else:
                return []

            # Handle boundary type
            if boundary == "beginning":
                if unit == "month":
                    # Month beginning: 1st to 10th of the month
                    start_date = target_date.replace(
                        day=1, hour=0, minute=0, second=0, microsecond=0
                    )
                    end_date = target_date.replace(
                        day=10, hour=23, minute=59, second=59, microsecond=0
                    )
                    result = self._format_time_result(start_date, end_date)

                    # Handle range_type (e.g., "by" for time ranges)
                    if range_type == "by":
                        # For "by" ranges, return from base_time to the target boundary
                        return self._format_time_result(base_time, end_date)
                    return result
                elif unit == "quarter":
                    # Quarter beginning: first month of the quarter
                    quarter_start_month = ((target_date.month - 1) // 3) * 3 + 1
                    start_date = target_date.replace(
                        month=quarter_start_month,
                        day=1,
                        hour=0,
                        minute=0,
                        second=0,
                        microsecond=0,
                    )
                    end_date = target_date.replace(
                        month=quarter_start_month,
                        day=31,
                        hour=23,
                        minute=59,
                        second=59,
                        microsecond=0,
                    )
                    # Handle months with fewer than 31 days
                    try:
                        result = self._format_time_result(start_date, end_date)
                    except ValueError:
                        if quarter_start_month in [4, 6, 9, 11]:  # 30-day months
                            end_date = end_date.replace(day=30)
                        elif quarter_start_month == 2:  # February
                            if target_date.year % 4 == 0 and (
                                target_date.year % 100 != 0 or target_date.year % 400 == 0
                            ):
                                end_date = end_date.replace(day=29)  # Leap year
                            else:
                                end_date = end_date.replace(day=28)  # Regular year
                        result = self._format_time_result(start_date, end_date)

                    # Handle range_type (e.g., "by" for time ranges)
                    if range_type == "by":
                        # For "by" ranges, return from base_time to the target boundary
                        return self._format_time_result(base_time, end_date)
                    return result
                elif unit == "year":
                    # Year beginning: January-February (1-2月)
                    import calendar

                    last_day_of_feb = calendar.monthrange(target_date.year, 2)[1]
                    start_date = target_date.replace(
                        month=1, day=1, hour=0, minute=0, second=0, microsecond=0
                    )
                    end_date = target_date.replace(
                        month=2,
                        day=last_day_of_feb,
                        hour=23,
                        minute=59,
                        second=59,
                        microsecond=0,
                    )
                    result = self._format_time_result(start_date, end_date)

                    # Handle range_type (e.g., "by" for time ranges)
                    if range_type == "by":
                        # For "by" ranges, return from base_time to the target boundary
                        return self._format_time_result(base_time, end_date)
                    return result
                elif unit == "week":
                    # Week beginning: Monday to Wednesday of the week
                    # Get Monday of the target week
                    days_since_monday = target_date.weekday()
                    monday = target_date - timedelta(days=days_since_monday)
                    start_date = monday.replace(hour=0, minute=0, second=0, microsecond=0)
                    # Week beginning: Monday to Wednesday
                    wednesday = monday + timedelta(days=2)
                    end_date = wednesday.replace(hour=23, minute=59, second=59, microsecond=0)
                    result = self._format_time_result(start_date, end_date)

                    # Handle range_type (e.g., "by" for time ranges)
                    if range_type == "by":
                        # For "by" ranges, return from base_time to the target boundary
                        return self._format_time_result(base_time, end_date)
                    return result
                elif unit == "day":
                    # Day beginning: start of the day (00:00:00)
                    start_date = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
                    end_date = target_date.replace(hour=23, minute=59, second=59, microsecond=0)
                    result = self._format_time_result(start_date, end_date)

                    # Handle range_type (e.g., "by" for time ranges)
                    if range_type == "by":
                        # For "by" ranges, return from base_time to the target boundary
                        return self._format_time_result(base_time, end_date)
                    return result

            elif boundary == "end":
                if unit == "month":
                    # Month end: 21st to last day of the month
                    start_date = target_date.replace(
                        day=21, hour=0, minute=0, second=0, microsecond=0
                    )
                    # Get last day of month
                    if target_date.month == 12:
                        next_month = target_date.replace(year=target_date.year + 1, month=1, day=1)
                    else:
                        next_month = target_date.replace(month=target_date.month + 1, day=1)
                    last_day = next_month - timedelta(days=1)
                    end_date = last_day.replace(hour=23, minute=59, second=59, microsecond=0)
                    result = self._format_time_result(start_date, end_date)

                    # Handle range_type (e.g., "by" for time ranges)
                    if range_type == "by":
                        # For "by" ranges, return from base_time to the target boundary
                        # For "by end of month", use the start of the month end period (21st)
                        return self._format_time_result(base_time, start_date)
                    return result
                elif unit == "quarter":
                    # Quarter end: last month of the quarter
                    # target_date is already set to the first month of the target quarter
                    quarter_end_month = target_date.month + 2  # Last month of the quarter
                    start_date = target_date.replace(
                        month=quarter_end_month,
                        day=1,
                        hour=0,
                        minute=0,
                        second=0,
                        microsecond=0,
                    )

                    # Get the last day of the month safely
                    if quarter_end_month == 12:
                        next_month = target_date.replace(year=target_date.year + 1, month=1, day=1)
                    else:
                        next_month = target_date.replace(month=quarter_end_month + 1, day=1)
                    last_day = next_month - timedelta(days=1)
                    end_date = last_day.replace(hour=23, minute=59, second=59, microsecond=0)

                    result = self._format_time_result(start_date, end_date)

                    # Handle range_type (e.g., "by" for time ranges)
                    if range_type == "by":
                        # For "by" ranges, return from base_time to the target boundary
                        # For "by end of quarter", use the start of the quarter end period (first day of last month)
                        return self._format_time_result(base_time, start_date)
                    return result
                elif unit == "year":
                    # Year end: November-December (11-12月)
                    start_date = target_date.replace(
                        month=11, day=1, hour=0, minute=0, second=0, microsecond=0
                    )
                    end_date = target_date.replace(
                        month=12, day=31, hour=23, minute=59, second=59, microsecond=0
                    )
                    result = self._format_time_result(start_date, end_date)

                    # Handle range_type (e.g., "by" for time ranges)
                    if range_type == "by":
                        # For "by" ranges, return from base_time to the target boundary
                        # For "by end of year", use the start of the year end period (November 1st)
                        return self._format_time_result(base_time, start_date)
                    return result
                elif unit == "week":
                    # Week end: weekend (Saturday and Sunday) of the target week
                    # Get Monday of the target week
                    days_since_monday = target_date.weekday()
                    monday = target_date - timedelta(days=days_since_monday)
                    # Weekend: Saturday (Monday + 5 days) and Sunday (Monday + 6 days)
                    saturday = monday + timedelta(days=5)
                    sunday = monday + timedelta(days=6)
                    start_date = saturday.replace(hour=0, minute=0, second=0, microsecond=0)
                    end_date = sunday.replace(hour=23, minute=59, second=59, microsecond=0)
                    result = self._format_time_result(start_date, end_date)

                    # Handle range_type (e.g., "by" for time ranges)
                    if range_type == "by":
                        # For "by" ranges, return from base_time to the target boundary
                        # For "by end of week", use the start of the weekend (Saturday)
                        return self._format_time_result(base_time, start_date)
                    return result
                elif unit == "day":
                    # Day end: end of the day (23:59:59)
                    start_date = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
                    end_date = target_date.replace(hour=23, minute=59, second=59, microsecond=0)
                    result = self._format_time_result(start_date, end_date)

                    # Handle range_type (e.g., "by" for time ranges)
                    if range_type == "by":
                        # For "by" ranges, return from base_time to the target boundary
                        # For "by end of day", use the end of the day (23:59:59)
                        return self._format_time_result(base_time, end_date)
                    return result

            return []

        except (ValueError, TypeError):
            return []
