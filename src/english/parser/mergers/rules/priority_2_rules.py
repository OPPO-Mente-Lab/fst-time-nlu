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

from typing import Optional, Tuple, List, Dict, Any
from datetime import datetime
from .base_rule import BaseRule


class Priority2Rules(BaseRule):
    """Rules for Priority 2: holiday, period, weekday, modifier patterns"""

    def try_merge(
        self, i: int, tokens: List[Dict[str, Any]], base_time: datetime
    ) -> Optional[Tuple[List, int]]:
        """
        Try to merge based on Priority 2 rules

        Args:
            i: Current token index
            tokens: List of tokens
            base_time: Base time reference

        Returns:
            tuple: (merged_results_list, jump_count) or None
        """
        n = len(tokens)
        if i >= n:
            return None

        cur = tokens[i]
        cur_type = cur.get("type")

        # Rule 5: time_composite_relative(time_modifier) + time_holiday merge
        # Pattern: time_composite_relative(time_modifier='1'/'0') + time_holiday(festival)
        # Example: "next new year's day", "last christmas"
        if cur_type == "time_composite_relative" and i + 1 < n:
            next_token = tokens[i + 1]
            if (
                next_token.get("type") == "time_holiday"
                and "time_modifier" in cur
                and not cur.get("value")
                and not cur.get("unit")
            ):
                result = self.context_merger.holiday_merger.merge_modifier_with_holiday(
                    cur, next_token, base_time
                )
                if result:
                    return result, 2  # Skip both tokens

        # Rule 5b: time_holiday + time_utc(year) merge
        # Pattern: time_holiday(festival) + time_utc(year)
        # Example: "halloween 2013", "easter 2010", "black friday 2017"
        if cur_type == "time_holiday" and i + 1 < n:
            next_token = tokens[i + 1]
            if (
                next_token.get("type") == "time_utc"
                and "year" in next_token
                and "month" not in next_token
                and "day" not in next_token
            ):
                result = self.context_merger.holiday_merger.merge_holiday_with_year(
                    cur, next_token, base_time
                )
                if result:
                    return result, 2  # Skip both tokens

        # Rule 5c: time_holiday + time_utc(hour/minute/period) merge
        # Pattern: time_holiday(festival) + time_utc(hour, minute, period)
        # Example: "xmas at 6 pm" -> christmas at 6pm
        if cur_type == "time_holiday" and i + 1 < n:
            next_token = tokens[i + 1]
            if (
                next_token.get("type") == "time_utc"
                and "hour" in next_token
                and "year" not in next_token
            ):
                result = self.context_merger.holiday_merger.merge_holiday_with_time(
                    cur, next_token, base_time
                )
                if result:
                    return result, 2  # Skip both tokens

        # Rule 5d: time_period + "of" + time_holiday (+ year) merge
        # Pattern: time_period(noon) + token("of") + time_holiday(festival) (+ time_utc(year))
        # Example: "morning of xmas" -> christmas morning
        # Example: "morning of christmas 2013" -> christmas morning in 2013
        # Example: "morning of this christmas day" -> this christmas morning
        if cur_type == "time_period" and i + 2 < n:
            # Check for "of" token
            of_token = tokens[i + 1]
            next_token = tokens[i + 2]
            
            # Case 1: period + of + modifier + holiday (e.g., "morning of this christmas")
            if (
                of_token.get("type") == "token"
                and of_token.get("value", "").lower() == "of"
                and next_token.get("type") == "time_composite_relative"
                and i + 3 < n
            ):
                modifier_token = next_token
                holiday_token = tokens[i + 3]
                if holiday_token.get("type") == "time_holiday":
                    # Merge modifier with holiday first
                    merged_holiday = self.context_merger.holiday_merger.merge_modifier_with_holiday(
                        modifier_token, holiday_token, base_time
                    )
                    if merged_holiday and merged_holiday[0]:
                        # Get the holiday date
                        from ...time_utils import parse_datetime_str

                        holiday_date_str = merged_holiday[0][0]
                        holiday_date = parse_datetime_str(holiday_date_str)
                        # Now apply the period to this date
                        period_parser = self.parsers.get("time_period")
                        if period_parser:
                            period_result = period_parser.parse(cur, holiday_date)
                            if period_result:
                                return period_result, 4  # Skip all four tokens
            
            # Case 2: period + of + holiday (e.g., "morning of christmas")
            holiday_token = next_token
            if (
                of_token.get("type") == "token"
                and of_token.get("value", "").lower() == "of"
                and holiday_token.get("type") == "time_holiday"
            ):
                # Check if there's a year following the holiday
                if i + 3 < n:
                    year_token = tokens[i + 3]
                    if (
                        year_token.get("type") == "time_utc"
                        and "year" in year_token
                        and "month" not in year_token
                        and "day" not in year_token
                    ):
                        # Merge holiday with year first, then apply period
                        merged_holiday = self.context_merger.holiday_merger.merge_holiday_with_year(
                            holiday_token, year_token, base_time
                        )
                        if merged_holiday and merged_holiday[0]:
                            # Get the holiday date with year
                            from ...time_utils import parse_datetime_str

                            holiday_date_str = merged_holiday[0][0]
                            holiday_date = parse_datetime_str(holiday_date_str)
                            # Now apply the period to this date
                            period_parser = self.parsers.get("time_period")
                            if period_parser:
                                period_result = period_parser.parse(cur, holiday_date)
                                if period_result:
                                    return period_result, 4  # Skip all four tokens

                # No year, just merge period with holiday
                result = self.context_merger.holiday_merger.merge_period_with_holiday(
                    cur, holiday_token, base_time
                )
                if result:
                    return result, 3  # Skip all three tokens

        # Rule 5e: time_holiday + ["of"] + time_composite_relative(unit=year) merge
        # Pattern: time_holiday(festival) + [token("of")] + time_composite_relative(time_modifier, unit=year)
        # Example: "black friday of this year" -> black friday in current year
        # Example: "new year's day this year" -> new year's day in current year
        if cur_type == "time_holiday" and i + 1 < n:
            # Check for direct case: holiday + year_modifier (no "of")
            if (
                tokens[i + 1].get("type") == "time_composite_relative"
                and tokens[i + 1].get("unit", "").strip('"') == "year"
            ):
                result = self.context_merger.holiday_merger.merge_holiday_with_year_modifier(
                    cur, tokens[i + 1], base_time
                )
                if result:
                    return result, 2  # Skip both tokens

            # Check for "of" case: holiday + of + year_modifier
            elif i + 2 < n:
                of_token = tokens[i + 1]
                year_modifier_token = tokens[i + 2]
                if (
                    of_token.get("type") == "token"
                    and of_token.get("value", "").lower() == "of"
                    and year_modifier_token.get("type") == "time_composite_relative"
                    and year_modifier_token.get("unit", "").strip('"') == "year"
                ):
                    result = self.context_merger.holiday_merger.merge_holiday_with_year_modifier(
                        cur, year_modifier_token, base_time
                    )
                    if result:
                        return result, 3  # Skip all three tokens

        # Rule 5e2: time_holiday + token(4-digit year) merge
        # Pattern: time_holiday(festival) + token(4-digit number)
        # Example: "black friday 2017", "thanksgiving 2014"
        if cur_type == "time_holiday" and i + 1 < n:
            next_token = tokens[i + 1]
            if next_token.get("type") == "token":
                year_str = next_token.get("value", "").strip()
                # Check if it's a 4-digit year (1900-2099)
                if year_str.isdigit() and len(year_str) == 4:
                    year = int(year_str)
                    if 1900 <= year <= 2099:
                        # Create a synthetic time_composite_relative token
                        year_offset = year - base_time.year
                        synthetic_year_modifier = {
                            "type": "time_composite_relative",
                            "time_modifier": str(year_offset),
                            "unit": "year",
                        }
                        result = (
                            self.context_merger.holiday_merger.merge_holiday_with_year_modifier(
                                cur, synthetic_year_modifier, base_time
                            )
                        )
                        if result:
                            return result, 2  # Skip both tokens

        # Rule 5f: time_delta + time_holiday merge
        # Pattern: time_delta(day, direction) + time_holiday(festival)
        # Example: "three days after easter" -> easter + 3 days
        if cur_type == "time_delta" and i + 1 < n:
            next_token = tokens[i + 1]
            if next_token.get("type") == "time_holiday":
                result = self.context_merger.holiday_merger.merge_delta_with_holiday(
                    cur, next_token, base_time
                )
                if result:
                    return result, 2  # Skip both tokens

        # Rule 5g: token(end/beginning) + of + token(4-digit year) merge
        # Pattern: token("end"/"beginning") + token("of") + token(4-digit year)
        # Example: "end of 2012" -> Nov-Dec 2012, "beginning of 2017" -> Jan-Feb 2017
        if cur_type == "token":
            period_result = self.context_merger.period_merger.try_merge_period_of_year(
                i, tokens, base_time
            )
            if period_result:
                return period_result

        # Rule 6: time_composite_relative(time_modifier) + time_weekday merge
        # Pattern: time_composite_relative(time_modifier='1'/'0') + time_weekday
        # Example: "next monday", "last friday"
        if cur_type == "time_composite_relative" and i + 1 < n:
            next_token = tokens[i + 1]
            if (
                next_token.get("type") == "time_weekday"
                and "time_modifier" in cur
                and not cur.get("value")
                and not cur.get("unit")
            ):
                result = self.context_merger.modifier_merger.merge_modifier_with_weekday(
                    cur, next_token, base_time
                )
                if result:
                    return result, 2  # Skip both tokens

        # Rule 6b: time_utc(month) + time_composite_relative(time_modifier) merge
        # Pattern: time_utc(month) + time_composite_relative(time_modifier='2')
        # Example: "March after next" -> 2014-03 (base: 2013-02)
        if cur_type == "time_utc" and "month" in cur and "day" not in cur and i + 1 < n:
            next_token = tokens[i + 1]
            if (
                next_token.get("type") == "time_composite_relative"
                and "time_modifier" in next_token
            ):
                from ...time_utils import month_name_to_number, get_month_range, format_datetime_str

                time_mod_str = next_token.get("time_modifier", "").strip('"')
                try:
                    time_mod = int(time_mod_str)
                    if time_mod == 2:  # "after next"
                        month_name = cur.get("month", "").strip('"')
                        month_num = month_name_to_number(month_name)
                        if month_num:
                            target_year = base_time.year
                            # If current month >= target month, go to next year
                            if base_time.month >= month_num:
                                target_year += 1
                            # "after next" means one more year
                            target_year += 1

                            target_date = base_time.replace(
                                year=target_year, month=month_num, day=1
                            )
                            start, end = get_month_range(target_date)
                            return (
                                [
                                    [
                                        format_datetime_str(start),
                                        format_datetime_str(end),
                                    ]
                                ],
                                2,
                            )
                except (ValueError, TypeError):
                    pass

        # Rule 7: Handle "weekday after next after next" pattern
        # Pattern: time_weekday + time_composite_relative(relation='1') + time_composite_relative(time_modifier='1') + time_composite_relative(time_modifier='1')
        # Example: "monday after next after next" = 3 weeks from now on Monday
        if (
            cur_type == "time_weekday"
            and i + 1 < n
            and tokens[i + 1].get("type") == "time_composite_relative"
            and tokens[i + 1].get("relation", "").strip('"') == "1"
        ):

            # Check for multiple "after next" patterns
            j = i + 1
            after_next_count = 0

            # Count consecutive "after next" patterns
            while j < n:
                # Skip empty tokens
                while (
                    j < n and tokens[j].get("type") == "token" and tokens[j].get("value", "") == ""
                ):
                    j += 1

                # Check for "after" token
                if (
                    j < n
                    and tokens[j].get("type") == "token"
                    and tokens[j].get("value", "").lower() == "after"
                ):
                    j += 1
                    continue

                # Check for time_composite_relative with relation='1' or time_modifier='1'
                if (
                    j < n
                    and tokens[j].get("type") == "time_composite_relative"
                    and (
                        tokens[j].get("relation", "").strip('"') == "1"
                        or tokens[j].get("time_modifier", "").strip('"') == "1"
                    )
                ):
                    after_next_count += 1
                    j += 1
                else:
                    break

            if after_next_count >= 1:  # At least "after next"
                result = self.context_merger.modifier_merger.handle_weekday_after_next_multiple(
                    cur, after_next_count, base_time
                )
                if result:
                    return result

        # Rule 8: Handle "week after next" pattern
        # Pattern: token('week') + token('after') + time_composite_relative(time_modifier='1')
        # Example: "week after next"
        if cur_type == "token" and cur.get("value", "").lower() == "week":
            # Look for "after" token after "week"
            after_idx = i + 1
            while (
                after_idx < n
                and tokens[after_idx].get("type") == "token"
                and tokens[after_idx].get("value", "") == ""
            ):
                after_idx += 1

            if (
                after_idx < n
                and tokens[after_idx].get("type") == "token"
                and tokens[after_idx].get("value", "").lower() == "after"
            ):

                # Look for time_composite_relative after "after"
                next_idx = after_idx + 1
                while (
                    next_idx < n
                    and tokens[next_idx].get("type") == "token"
                    and tokens[next_idx].get("value", "") == ""
                ):
                    next_idx += 1

                if (
                    next_idx < n
                    and tokens[next_idx].get("type") == "time_composite_relative"
                    and tokens[next_idx].get("time_modifier", "").strip('"') == "1"
                ):
                    result = self.context_merger.modifier_merger.handle_week_after_next(base_time)
                    if result:
                        return (
                            result,
                            next_idx + 1 - i,
                        )  # Skip all tokens from i to next_idx

        # Rule 9: Handle "<MonthName> after next" pattern
        # Pattern: time_utc(month=...) + token('after') + time_composite_relative(time_modifier='1')
        # Example: "March after next" -> the March after the next occurrence of March
        if cur_type == "time_utc" and "month" in cur and "day" not in cur and "year" not in cur:
            # Look ahead for "after" and then a time_composite_relative with time_modifier='1'
            after_idx = i + 1
            while (
                after_idx < n
                and tokens[after_idx].get("type") == "token"
                and tokens[after_idx].get("value", "") == ""
            ):
                after_idx += 1

            if (
                after_idx < n
                and tokens[after_idx].get("type") == "token"
                and tokens[after_idx].get("value", "").lower() == "after"
            ):

                next_idx = after_idx + 1
                while (
                    next_idx < n
                    and tokens[next_idx].get("type") == "token"
                    and tokens[next_idx].get("value", "") == ""
                ):
                    next_idx += 1

                if (
                    next_idx < n
                    and tokens[next_idx].get("type") == "time_composite_relative"
                    and tokens[next_idx].get("time_modifier", "").strip('"') == "1"
                ):

                    month_name = cur.get("month", "").strip('"')
                    result = self.context_merger.modifier_merger.handle_named_month_after_next(
                        month_name, base_time
                    )
                    if result:
                        return result, next_idx + 1 - i

        # Rule 8: time_holiday + time_range merge
        # Pattern: time_holiday(festival) + time_range(offset_direction, offset, unit)
        # Example: "new year next year"
        if cur_type == "time_holiday" and i + 1 < n:
            next_token = tokens[i + 1]
            if (
                next_token.get("type") == "time_range"
                and next_token.get("unit", "").strip('"') == "year"
            ):
                result = self.context_merger.holiday_merger.merge_holiday_with_year_range(
                    cur, next_token, base_time
                )
                if result:
                    return result, 2  # Skip both tokens

        # Rule X: Generic "X of Y" injection pattern
        # Pattern: X + 'of'/'from' + Y, by injecting Y's temporal context into X
        # Example: "20th of next month", "15 of March", "sunday from last week"
        of_merge = self.context_merger._try_merge_of_injection(i, tokens, base_time)
        if of_merge:
            return of_merge

        return None
