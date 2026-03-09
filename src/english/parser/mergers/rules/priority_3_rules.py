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
from datetime import datetime, timedelta
from .base_rule import BaseRule


class Priority3Rules(BaseRule):
    """Rules for Priority 3: range, duration, time_range_expr patterns"""

    def try_merge(
        self, i: int, tokens: List[Dict[str, Any]], base_time: datetime
    ) -> Optional[Tuple[List, int]]:
        """
        Try to merge based on Priority 3 rules

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

        # Rule 8.7: "the <unit> after next" pattern (must come BEFORE Rule 7!)
        # Pattern: time_composite_relative(time_modifier='2') (when FST recognizes "the week after next")
        # Example: "the week after next", "the day after next", "the month after next", "the year after next"
        if (
            cur_type == "time_composite_relative"
            and cur.get("time_modifier", "").strip('"') == "2"
            and cur.get("unit", "").strip('"') == "week"
            and not cur.get("week_day", "").strip('"')
        ):
            # This is likely "the week after next" that was recognized by FST
            # Convert to offset_week: "2" and let CompositeRelativeParser handle it
            synthetic_token = {"type": "time_composite_relative", "offset_week": "2"}
            composite_parser = self.parsers.get("time_composite_relative")
            if composite_parser:
                result = composite_parser.parse(synthetic_token, base_time)
                if result:
                    return result, 1

        # Rule 7: "[relative] time_A to time_B" pattern (prefix modifier)
        # Example: "last year april 3 to may 1"
        # This must come BEFORE Rule 6 to avoid being consumed by it
        if cur_type == "time_composite_relative":
            range_result = self.context_merger.range_merger.try_merge(i, tokens, base_time)
            if range_result:
                return range_result

        # Rule 5: "from time_A to time_B [relative]" pattern
        # Example: "from 14:40 to 15:10 tomorrow"
        if (cur_type == "token" and cur.get("value", "").lower() == "from") or (
            cur_type == "time_connector" and cur.get("connector", "") == "from"
        ):
            range_result = self.context_merger.range_merger.try_merge(i, tokens, base_time)
            if range_result:
                return range_result

        # Rule 6: "between time_A and time_B" pattern
        # Example: "between 9:30 and 11:00"
        if (cur_type == "token" and cur.get("value", "").lower() == "between") or (
            cur_type == "time_connector" and cur.get("connector", "") == "between"
        ):
            range_result = self.context_merger.range_merger.try_merge(i, tokens, base_time)
            if range_result:
                return range_result

        # Rule 6.5: "time + year modifier" pattern
        # Example: "june 9 last year", "august 20 this year"
        if cur_type == "time_utc" and i + 1 < n:
            year_modifier_result = (
                self.context_merger.modifier_merger.try_merge_time_with_year_modifier(
                    i, tokens, base_time
                )
            )
            if year_modifier_result:
                return year_modifier_result

        # Rule 7: "time_A to time_B [relative]" pattern (without "from")
        # Example: "april 3 to may 1"
        if cur_type in ["time_utc", "time_composite_relative"]:
            range_result = self.context_merger.range_merger.try_merge(i, tokens, base_time)
            if range_result:
                return range_result

        # Rule 8: "day + to + day + month" pattern
        # Example: "from 13th to 15th July", "July 13 to 15"
        if cur_type in ["time_utc", "time_connector", "token"]:
            range_result = self.context_merger.range_merger.try_merge(i, tokens, base_time)
            if range_result:
                return range_result

        # Rule 9: "compact date range" pattern
        # Example: "July 13-15", "from July 13-15"
        if cur_type in ["time_utc", "time_connector"]:
            compact_result = self.context_merger.range_merger.try_merge(i, tokens, base_time)
            if compact_result:
                return compact_result

        # Rule 8.4: time_range_expr + on + weekday pattern
        # Pattern: time_range_expr + token('on') + time_weekday
        # Example: "9:30 till 11:00 on Thursday"
        if cur_type == "time_range_expr" and i + 2 < n:
            on_token = tokens[i + 1]
            weekday_token = tokens[i + 2]

            if (
                on_token.get("type") == "token"
                and on_token.get("value", "").strip() == "on"
                and weekday_token.get("type") == "time_weekday"
            ):

                # Parse the range expression first
                range_parser = self.parsers.get("time_range_expr")
                if range_parser:
                    range_result = range_parser.parse(cur, base_time)
                    if range_result and range_result[0]:
                        # Apply weekday to the time range
                        weekday_str = weekday_token.get("week_day", "").strip('"')
                        offset_week = int(weekday_token.get("offset_week", "0").strip('"'))

                        # Calculate target weekday
                        target_base = base_time + timedelta(weeks=offset_week)

                        weekday_map = {
                            "monday": 0,
                            "tuesday": 1,
                            "wednesday": 2,
                            "thursday": 3,
                            "friday": 4,
                            "saturday": 5,
                            "sunday": 6,
                        }
                        wd = weekday_str.lower()
                        if wd in weekday_map:
                            target_weekday = weekday_map[wd]
                            days_ahead = target_weekday - target_base.weekday()
                            if days_ahead < 0:
                                days_ahead += 7

                            target_date = target_base + timedelta(days=days_ahead)

                            # Parse the start and end times from range result
                            from ...time_utils import parse_datetime_str, format_datetime_str

                            start_str = range_result[0][0]
                            end_str = range_result[0][1]
                            start_time = parse_datetime_str(start_str)
                            end_time = parse_datetime_str(end_str)

                            # Apply the target date to the times
                            result_start = target_date.replace(
                                hour=start_time.hour,
                                minute=start_time.minute,
                                second=start_time.second,
                                microsecond=0,
                            )
                            result_end = target_date.replace(
                                hour=end_time.hour,
                                minute=end_time.minute,
                                second=end_time.second,
                                microsecond=0,
                            )

                            return [
                                [
                                    format_datetime_str(result_start),
                                    format_datetime_str(result_end),
                                ]
                            ], 3

        # Rule 8.5: weekday + time_range_expr pattern
        # Pattern: time_weekday + time_range_expr
        # Example: "Thursday from 9:30 to 11:00" (atomic range from FST)
        if cur_type == "time_weekday" and i + 1 < n:
            next_token = tokens[i + 1]
            if next_token.get("type") == "time_range_expr":
                # Parse the range expression first
                range_parser = self.parsers.get("time_range_expr")
                if range_parser:
                    range_result = range_parser.parse(next_token, base_time)
                    if range_result and range_result[0]:
                        # Apply weekday to the time range
                        weekday_str = cur.get("week_day", "").strip('"')
                        offset_week = int(cur.get("offset_week", "0").strip('"'))

                        # Calculate target weekday
                        target_base = base_time + timedelta(weeks=offset_week)

                        weekday_map = {
                            "monday": 0,
                            "tuesday": 1,
                            "wednesday": 2,
                            "thursday": 3,
                            "friday": 4,
                            "saturday": 5,
                            "sunday": 6,
                        }
                        wd = weekday_str.lower()
                        if wd in weekday_map:
                            target_weekday = weekday_map[wd]
                            days_ahead = target_weekday - target_base.weekday()
                            if days_ahead < 0:
                                days_ahead += 7

                            target_date = target_base + timedelta(days=days_ahead)

                            # Parse the start and end times from range result
                            from ...time_utils import parse_datetime_str, format_datetime_str

                            start_str = range_result[0][0]
                            end_str = range_result[0][1]
                            start_time = parse_datetime_str(start_str)
                            end_time = parse_datetime_str(end_str)

                            # Apply the target date to the times
                            result_start = target_date.replace(
                                hour=start_time.hour,
                                minute=start_time.minute,
                                second=start_time.second,
                                microsecond=0,
                            )
                            result_end = target_date.replace(
                                hour=end_time.hour,
                                minute=end_time.minute,
                                second=end_time.second,
                                microsecond=0,
                            )

                            return [
                                [
                                    format_datetime_str(result_start),
                                    format_datetime_str(result_end),
                                ]
                            ], 2

        # Rule 8.6: time_range_expr + time_relative pattern
        # Pattern: time_range_expr + time_relative
        # Example: "from 14:40 to 15:10 tomorrow"
        if cur_type == "time_range_expr" and i + 1 < n:
            # Skip empty tokens
            next_idx = i + 1
            while (
                next_idx < n
                and tokens[next_idx].get("type") == "token"
                and tokens[next_idx].get("value", "").strip() == ""
            ):
                next_idx += 1

            if next_idx < n:
                next_token = tokens[next_idx]
                if next_token.get("type") == "time_relative":
                    # Parse the range expression first
                    range_parser = self.parsers.get("time_range_expr")
                    if range_parser:
                        range_result = range_parser.parse(cur, base_time)
                        if range_result and range_result[0]:
                            from ...time_utils import parse_datetime_str, format_datetime_str

                            # Get offset_day from relative token
                            offset_day = int(next_token.get("offset_day", "0").strip('"'))

                            target_date = base_time + timedelta(days=offset_day)

                            # Extract start and end times from range
                            start_str = range_result[0][0]
                            end_str = range_result[0][1]
                            start_time = parse_datetime_str(start_str)
                            end_time = parse_datetime_str(end_str)

                            # Apply the target date to the times
                            result_start = target_date.replace(
                                hour=start_time.hour,
                                minute=start_time.minute,
                                second=start_time.second,
                                microsecond=0,
                            )
                            result_end = target_date.replace(
                                hour=end_time.hour,
                                minute=end_time.minute,
                                second=end_time.second,
                                microsecond=0,
                            )

                            return [
                                [
                                    format_datetime_str(result_start),
                                    format_datetime_str(result_end),
                                ]
                            ], next_idx + 1

        # Rule 9: weekday + from + time + to + time pattern
        # Pattern: time_weekday + token('from') + time_utc + token('to') + time_utc
        # Example: "Thursday from 9:30 to 11:00"
        if cur_type == "time_weekday" and i + 4 < n:
            from_token = tokens[i + 1]
            time_a_token = tokens[i + 2]
            to_token = tokens[i + 3]
            time_b_token = tokens[i + 4]

            if (
                from_token.get("type") == "token"
                and from_token.get("value", "").strip() == "from"
                and time_a_token.get("type") == "time_utc"
                and to_token.get("type") == "token"
                and to_token.get("value", "").strip() == "to"
                and time_b_token.get("type") == "time_utc"
            ):

                # Use existing _merge_time_range_with_weekday method
                result = self.context_merger.range_merger.range_utils.merge_time_range_with_weekday(
                    time_a_token, time_b_token, cur, None, base_time
                )
                if result:
                    return (
                        result,
                        5,
                    )  # Skip weekday + from + time_a + to + time_b tokens

        return None
