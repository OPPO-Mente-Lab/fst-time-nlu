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


class Priority4Rules(BaseRule):
    """Rules for Priority 4: period, past/to time expressions, and other complex rules"""

    def try_merge(
        self, i: int, tokens: List[Dict[str, Any]], base_time: datetime
    ) -> Optional[Tuple[List, int]]:
        """
        Try to merge based on Priority 4 rules

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

        # Rule 10: weekday(week_period) + of + month pattern
        # Pattern: time_weekday(week_period, offset_week) + token('of') + time_utc(month)
        # Example: "last weekend of October"
        if cur_type == "time_weekday" and i + 2 < n:
            of_token = tokens[i + 1]
            month_token = tokens[i + 2]

            if (
                of_token.get("type") == "token"
                and of_token.get("value", "").strip() == "of"
                and month_token.get("type") == "time_utc"
                and "month" in month_token
            ):

                result = self.context_merger.period_merger.merge_weekday_period_with_month(
                    cur, month_token, base_time
                )
                if result:
                    return result, 3  # Skip weekday + of + month tokens

        # Rule X1: time_period + of + (time_utc | time_holiday | time_weekday) merge
        # Pattern: time_period(noon) + token("of") + (time_utc | time_holiday | time_weekday)
        # Example: "morning of christmas day", "morning of the 15th of february"
        if cur_type == "time_period" and i + 2 < n:
            # Look for "of" token
            j = i + 1
            while (
                j < n
                and tokens[j].get("type") == "token"
                and tokens[j].get("value", "").strip() == ""
            ):
                j += 1

            if (
                j < n
                and tokens[j].get("type") == "token"
                and tokens[j].get("value", "").lower() == "of"
            ):
                # Look for date/holiday/weekday after "of"
                k = j + 1
                while (
                    k < n
                    and tokens[k].get("type") == "token"
                    and tokens[k].get("value", "").strip() == ""
                ):
                    k += 1

                if k < n:
                    # Check for single date token
                    date_token = tokens[k]
                    if date_token.get("type") in [
                        "time_utc",
                        "time_holiday",
                        "time_weekday",
                    ]:
                        result = self.context_merger.period_merger.merge_period_with_date(
                            cur, date_token, base_time
                        )
                        if result:
                            return (result, k + 1)  # Skip period + of + date tokens

                    # Check for composite relative + holiday pattern (e.g., "this christmas day")
                    elif (
                        k + 1 < n
                        and date_token.get("type") == "time_composite_relative"
                        and tokens[k + 1].get("type") == "time_holiday"
                    ):
                        # Merge composite relative with holiday first
                        holiday_token = tokens[k + 1]
                        # Create a synthetic holiday token with year modifier
                        synthetic_holiday = {
                            "type": "time_holiday",
                            "festival": holiday_token.get("festival"),
                            "time_modifier": date_token.get("time_modifier"),
                            "unit": "year",
                        }
                        result = self.context_merger.period_merger.merge_period_with_date(
                            cur, synthetic_holiday, base_time
                        )
                        if result:
                            return (
                                result,
                                k + 2,
                            )  # Skip period + of + composite_relative + holiday tokens

        # Rule 11: time_utc + in + the + time_period pattern
        # Pattern: time_utc(hour, minute) + token('in') + token('the') + time_period(noon)
        # Example: "3 o'clock in the afternoon" -> 3 PM (15:00)
        if cur_type == "time_utc" and i + 3 < n:
            in_token = tokens[i + 1]
            the_token = tokens[i + 2]
            period_token = tokens[i + 3]

            if (
                in_token.get("type") == "token"
                and in_token.get("value", "").strip() == "in"
                and the_token.get("type") == "token"
                and the_token.get("value", "").strip() == "the"
                and period_token.get("type") == "time_period"
                and "noon" in period_token
            ):

                result = self.context_merger.time_expression_merger.merge_time_with_period(
                    cur, period_token, base_time
                )
                if result:
                    return result, 4  # Skip time + in + the + period tokens

        # Rule X2: (time_utc | time_weekday) + [in/the] + time_period merge
        # Pattern: (time_utc | time_weekday) + token('in') + token('the') + time_period(noon)
        # Example: "february 15th in the morning", "monday in the morning"
        # Also handles: "february the 15th in the morning" (month + day + period)
        if cur_type in ["time_utc", "time_weekday"] and i + 3 < n:
            # Check if this is month+day+period pattern
            if cur_type == "time_utc" and "month" in cur and "day" not in cur:
                # Look for day token after empty tokens
                j = i + 1
                while (
                    j < n
                    and tokens[j].get("type") == "token"
                    and tokens[j].get("value", "").strip() == ""
                ):
                    j += 1

                if (
                    j < n
                    and tokens[j].get("type") == "time_utc"
                    and "day" in tokens[j]
                    and "month" not in tokens[j]
                ):
                    # This is "month + day + in + the + period" pattern
                    month_token = cur
                    day_token = tokens[j]

                    # Skip empty tokens to find "in"
                    k = j + 1
                    while (
                        k < n
                        and tokens[k].get("type") == "token"
                        and tokens[k].get("value", "").strip() == ""
                    ):
                        k += 1

                    if (
                        k < n
                        and tokens[k].get("type") == "token"
                        and tokens[k].get("value", "").strip() == "in"
                    ):
                        # Skip empty tokens to find "the"
                        the_idx = k + 1
                        while (
                            the_idx < n
                            and tokens[the_idx].get("type") == "token"
                            and tokens[the_idx].get("value", "").strip() == ""
                        ):
                            the_idx += 1

                        if (
                            the_idx < n
                            and tokens[the_idx].get("type") == "token"
                            and tokens[the_idx].get("value", "").strip() == "the"
                        ):
                            # Skip empty tokens to find period
                            m = the_idx + 1
                            while (
                                m < n
                                and tokens[m].get("type") == "token"
                                and tokens[m].get("value", "").strip() == ""
                            ):
                                m += 1

                            if (
                                m < n
                                and tokens[m].get("type") == "time_period"
                                and "noon" in tokens[m]
                            ):
                                # Merge month + day + period
                                merged_date = {**month_token, **day_token}
                                period_token = tokens[m]
                                result = self.context_merger.time_expression_merger.merge_time_with_period(
                                    merged_date, period_token, base_time
                                )
                                if result:
                                    return (
                                        result,
                                        m + 1,
                                    )  # Skip month + day + in + the + period tokens

            # Handle regular time_utc/time_weekday + in + the + period pattern
            else:
                # Skip empty tokens to find "in"
                j = i + 1
                while (
                    j < n
                    and tokens[j].get("type") == "token"
                    and tokens[j].get("value", "").strip() == ""
                ):
                    j += 1

                if (
                    j < n
                    and tokens[j].get("type") == "token"
                    and tokens[j].get("value", "").strip() == "in"
                ):
                    # Skip empty tokens to find "the"
                    k = j + 1
                    while (
                        k < n
                        and tokens[k].get("type") == "token"
                        and tokens[k].get("value", "").strip() == ""
                    ):
                        k += 1

                    if (
                        k < n
                        and tokens[k].get("type") == "token"
                        and tokens[k].get("value", "").strip() == "the"
                    ):
                        # Skip empty tokens to find period
                        the_idx = k + 1
                        while (
                            the_idx < n
                            and tokens[the_idx].get("type") == "token"
                            and tokens[the_idx].get("value", "").strip() == ""
                        ):
                            the_idx += 1

                        if (
                            the_idx < n
                            and tokens[the_idx].get("type") == "time_period"
                            and "noon" in tokens[the_idx]
                        ):
                            period_token = tokens[the_idx]
                            result = (
                                self.context_merger.time_expression_merger.merge_time_with_period(
                                    cur, period_token, base_time
                                )
                            )
                            if result:
                                return (
                                    result,
                                    the_idx + 1,
                                )  # Skip time + in + the + period tokens

        # Rule X3: time_weekday + [early/late] + [in/the] + time_period merge
        # Pattern: time_weekday + token('early'/'late') + token('in') + token('the') + time_period(noon)
        # Example: "monday early in the morning" -> 06:00-09:00
        if cur_type == "time_weekday" and i + 4 < n:
            early_late_token = tokens[i + 1]
            in_token = tokens[i + 2]
            the_token = tokens[i + 3]
            period_token = tokens[i + 4]

            if (
                early_late_token.get("type") == "token"
                and early_late_token.get("value", "").strip() in ["early", "late"]
                and in_token.get("type") == "token"
                and in_token.get("value", "").strip() == "in"
                and the_token.get("type") == "token"
                and the_token.get("value", "").strip() == "the"
                and period_token.get("type") == "time_period"
                and "noon" in period_token
            ):

                # Apply modifier to period
                period = period_token.get("noon", "").strip('"')
                modifier = early_late_token.get("value", "").strip()
                period_ranges = self.context_merger.period_merger.apply_period_modifier(
                    period, modifier
                )

                if period_ranges:
                    # Parse weekday to get target date
                    weekday_parser = self.parsers.get("time_weekday")
                    if weekday_parser:
                        weekday_result = weekday_parser.parse(cur, base_time)
                        if weekday_result and len(weekday_result) > 0:
                            # Extract date from weekday result
                            from ...time_utils import parse_datetime_str, format_datetime_str

                            weekday_time_str = weekday_result[0][0]  # Start time
                            target_date = parse_datetime_str(weekday_time_str)

                            # Apply modified period to target date
                            (start_hour, start_min), (end_hour, end_min) = period_ranges
                            start_time = target_date.replace(
                                hour=start_hour, minute=start_min, second=0
                            )
                            end_time = target_date.replace(hour=end_hour, minute=end_min, second=0)

                            result = [
                                [
                                    format_datetime_str(start_time),
                                    format_datetime_str(end_time),
                                ]
                            ]
                            if result:
                                return (
                                    result,
                                    5,
                                )  # Skip weekday + early/late + in + the + period tokens

        # Rule 12: time_utc + past + time_utc pattern
        # Pattern: time_utc(hour, minute) + token('past') + time_utc(hour, period)
        # Example: "at 20 past 3pm" -> 15:20
        if cur_type == "time_utc" and i + 2 < n:
            past_token = tokens[i + 1]
            target_time_token = tokens[i + 2]

            if (
                past_token.get("type") == "token"
                and past_token.get("value", "").strip() == "past"
                and target_time_token.get("type") == "time_utc"
                and "hour" in target_time_token
            ):

                # Check if first token represents minutes (hour <= 12 and minute == 0)
                first_hour = int(cur.get("hour", 0))
                first_minute = int(cur.get("minute", 0))
                if first_minute == 0 and first_hour <= 12:
                    # Treat first token as minutes
                    result = self.context_merger.time_expression_merger.merge_past_time(
                        cur, target_time_token, base_time
                    )
                    if result:
                        return result, 3  # Skip minute + past + target_time tokens

        # Rule 13: time_utc + to + time_utc pattern
        # Pattern: time_utc(minute) + token('to') + time_utc(hour, period)
        # Example: "at 20 to 4pm" -> 15:40
        if cur_type == "time_utc" and i + 2 < n:
            to_token = tokens[i + 1]
            target_time_token = tokens[i + 2]

            if (
                to_token.get("type") == "token"
                and to_token.get("value", "").strip() == "to"
                and target_time_token.get("type") == "time_utc"
                and "hour" in target_time_token
            ):

                result = self.context_merger.time_expression_merger.merge_to_time(
                    cur, target_time_token, base_time
                )
                if result:
                    return result, 3  # Skip minute + to + target_time tokens

        # Rule 14: fraction + past + time_period pattern
        # Pattern: fraction + token('past') + time_period(noon)
        # Example: "a quarter past noon" -> 12:15
        if cur_type == "fraction" and i + 2 < n:
            past_token = tokens[i + 1]
            period_token = tokens[i + 2]

            if (
                past_token.get("type") == "token"
                and past_token.get("value", "").strip() == "past"
                and period_token.get("type") == "time_period"
                and "noon" in period_token
            ):

                result = self.context_merger.time_expression_merger.merge_fraction_past_period(
                    cur, period_token, base_time
                )
                if result:
                    return result, 3  # Skip fraction + past + period tokens

        # Rule 15: fraction + to + time_period pattern
        # Pattern: fraction + token('to') + time_period(noon)
        # Example: "a quarter to noon" -> 11:45
        if cur_type == "fraction" and i + 2 < n:
            to_token = tokens[i + 1]
            period_token = tokens[i + 2]

            if (
                to_token.get("type") == "token"
                and to_token.get("value", "").strip() == "to"
                and period_token.get("type") == "time_period"
                and "noon" in period_token
            ):

                result = self.context_merger.time_expression_merger.merge_fraction_to_period(
                    cur, period_token, base_time
                )
                if result:
                    return result, 3  # Skip fraction + to + period tokens

        # Rule 16: number + minutes + past + time_period pattern
        # Pattern: token(number1) + token(number2) + token('minutes') + token('past') + time_period(noon)
        # Example: "15 minutes past noon" -> 12:15
        if cur_type == "token" and i + 4 < n:
            num1_token = cur
            num2_token = tokens[i + 1]
            minutes_token = tokens[i + 2]
            past_token = tokens[i + 3]
            period_token = tokens[i + 4]

            if (
                num1_token.get("type") == "token"
                and num1_token.get("value", "").isdigit()
                and num2_token.get("type") == "token"
                and num2_token.get("value", "").isdigit()
                and minutes_token.get("type") == "token"
                and minutes_token.get("value", "").strip() == "minutes"
                and past_token.get("type") == "token"
                and past_token.get("value", "").strip() == "past"
                and period_token.get("type") == "time_period"
                and "noon" in period_token
            ):

                result = (
                    self.context_merger.time_expression_merger.merge_number_minutes_past_period(
                        num1_token, num2_token, period_token, base_time
                    )
                )
                if result:
                    return (
                        result,
                        5,
                    )  # Skip num1 + num2 + minutes + past + period tokens

        # Rule 17: at + time_utc + past + time_utc pattern
        # Pattern: token('at') + time_utc(hour, minute) + token('past') + time_utc(hour, period)
        # Example: "at 20 past 3pm" -> 15:20
        if cur_type == "token" and cur.get("value", "").strip() == "at" and i + 3 < n:
            time1_token = tokens[i + 1]
            past_token = tokens[i + 2]
            time2_token = tokens[i + 3]

            if (
                time1_token.get("type") == "time_utc"
                and "hour" in time1_token
                and past_token.get("type") == "token"
                and past_token.get("value", "").strip() == "past"
                and time2_token.get("type") == "time_utc"
                and "hour" in time2_token
            ):

                # Check if first time represents minutes (hour <= 12 and minute == 0)
                first_hour = int(time1_token.get("hour", 0))
                first_minute = int(time1_token.get("minute", 0))
                if first_minute == 0 and first_hour <= 12:
                    # Treat first time as minutes
                    result = self.context_merger.time_expression_merger.merge_past_time(
                        time1_token, time2_token, base_time
                    )
                    if result:
                        return result, 4  # Skip at + time1 + past + time2 tokens

        # Rule 18: at + time_utc + past + time_period pattern
        # Pattern: token('at') + time_utc(hour, minute) + token('past') + time_period(noon)
        # Example: "at 15 past noon" -> 12:15
        if cur_type == "token" and cur.get("value", "").strip() == "at" and i + 3 < n:
            time_token = tokens[i + 1]
            past_token = tokens[i + 2]
            period_token = tokens[i + 3]

            if (
                time_token.get("type") == "time_utc"
                and "hour" in time_token
                and past_token.get("type") == "token"
                and past_token.get("value", "").strip() == "past"
                and period_token.get("type") == "time_period"
                and "noon" in period_token
            ):

                # Check if time represents minutes (hour <= 12 and minute == 0)
                hour = int(time_token.get("hour", 0))
                minute = int(time_token.get("minute", 0))
                if minute == 0 and hour <= 12:
                    # Treat hour as minutes
                    result = self.context_merger.time_expression_merger.merge_number_minutes_past_period_single(
                        hour, period_token, base_time
                    )
                    if result:
                        return result, 4  # Skip at + time + past + period tokens

        # Rule 19: time_utc + empty + past + empty + time_period pattern (from "at 15 past noon")
        # Pattern: time_utc(hour, minute) + token('') + token('past') + token('') + time_period(noon)
        # Example: "at 15 past noon" -> 12:15
        if cur_type == "time_utc" and "hour" in cur and i + 4 < n:
            empty1_token = tokens[i + 1]
            past_token = tokens[i + 2]
            empty2_token = tokens[i + 3]
            period_token = tokens[i + 4]

            if (
                empty1_token.get("type") == "token"
                and empty1_token.get("value", "").strip() == ""
                and past_token.get("type") == "token"
                and past_token.get("value", "").strip() == "past"
                and empty2_token.get("type") == "token"
                and empty2_token.get("value", "").strip() == ""
                and period_token.get("type") == "time_period"
                and "noon" in period_token
            ):

                # Check if time represents minutes (minute == 0)
                hour = int(cur.get("hour", 0))
                minute = int(cur.get("minute", 0))
                if minute == 0:
                    # Treat hour as minutes
                    result = self.context_merger.time_expression_merger.merge_number_minutes_past_period_single(
                        hour, period_token, base_time
                    )
                    if result:
                        return (
                            result,
                            5,
                        )  # Skip time + empty1 + past + empty2 + period tokens

        return None
