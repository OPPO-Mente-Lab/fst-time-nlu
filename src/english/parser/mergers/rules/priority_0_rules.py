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


class Priority0Rules(BaseRule):
    """Rules for Priority 0: false recognition, at number, short time range, etc."""

    def try_merge(
        self, i: int, tokens: List[Dict[str, Any]], base_time: datetime
    ) -> Optional[Tuple[List, int]]:
        """
        Try to merge based on Priority 0 rules

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

        # Priority 0: Check for false time recognition (must come first)
        # If this is a time_utc token that's likely a false positive, skip it
        if cur_type == "time_utc" and self.context_merger._check_false_time_recognition(i, tokens):
            return (None, 0)  # Special marker: skip this token

        # Priority 0.2: Check for "at" + number pattern
        # Example: "at 9", "at 12" -> create time_utc token
        if cur_type == "token" and cur.get("value", "").lower() == "at":
            result = self.context_merger.time_expression_merger.merge_at_number(
                i, tokens, base_time
            )
            if result:
                return result

        # Priority 0.3: Check for "N-Npm" pattern (short time range with AM/PM)
        # Example: "3-4pm" should be interpreted as time range, not date
        if (
            cur_type == "time_utc"
            and self.context_merger.time_expression_merger.check_short_time_range_pattern(i, tokens)
        ):
            range_result = self.context_merger.time_expression_merger.try_merge_short_time_range(
                i, tokens, base_time
            )
            if range_result:
                return range_result

        # Priority 0.4: Check for "by" + future time pattern
        # Example: "by tomorrow", "by next Monday", "by the end of next month"
        if cur_type == "token" and cur.get("value", "").lower() == "by":
            result = self.context_merger.delta_merger.merge_by_future_time(i, tokens, base_time)
            if result:
                return result

        # Priority 0.5: Check for "for" + duration + "from" + time pattern
        # Example: "for 10 days from 18th Dec", "for 30 minutes from 4pm"
        if cur_type == "token" and cur.get("value", "").lower() == "for":
            result = self.context_merger.duration_merger.merge_for_duration_from_time(
                i, tokens, base_time
            )
            if result:
                return result

        # Priority 0.6: Check for "from" + time + "for" + duration pattern
        # Example: "from 18th Dec for 10 days", "from 4pm for thirty minutes"
        if cur_type == "token" and cur.get("value", "").lower() == "from":
            result = self.context_merger.duration_merger.merge_from_time_for_duration(
                i, tokens, base_time
            )
            if result:
                return result

        # Priority 0.7: Check for time + "for" + duration pattern
        # Example: "4pm for 30 mins", "18th Dec for 10 days"
        if cur_type in [
            "time_utc",
            "time_relative",
            "time_weekday",
            "time_holiday",
            "time_composite_relative",
        ]:
            result = self.context_merger.duration_merger.merge_time_for_duration(
                i, tokens, base_time
            )
            if result:
                return result

        # Priority 0.8: Check for duration + "from" + time pattern (offset calculation)
        # Example: "a year from Christmas", "3 days from tomorrow"
        if cur_type == "time_delta":
            result = self.context_merger.duration_merger.merge_duration_from_time(
                i, tokens, base_time
            )
            if result:
                return result

        # Priority 0.9: Check for "at" + past/to time patterns
        # Example: "at 20 past 3pm", "at 15 past noon"
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
                    result = self.context_merger._merge_number_minutes_past_period_single(
                        hour, period_token, base_time
                    )
                    if result:
                        return (
                            result,
                            5,
                        )  # Skip time + empty1 + past + empty2 + period tokens

        # Priority 0.5: Check for "on may day" context (single day instead of 5-day holiday)
        if (
            cur_type == "time_holiday"
            and self.context_merger.holiday_merger.check_on_holiday_context(i, tokens)
        ):
            return self.context_merger.holiday_merger.handle_on_holiday_single_day(
                i, tokens, base_time
            )

        # Priority 0.6: Check for "holiday in time_delta" pattern
        # Example: "thanksgiving in a year" -> apply year offset to holiday
        if cur_type == "time_holiday" and i + 2 < n:
            next_token = tokens[i + 1]
            delta_token = tokens[i + 2]
            if (
                next_token.get("type") == "token"
                and next_token.get("value", "").strip() == "in"
                and delta_token.get("type") == "time_delta"
                and delta_token.get("year")
            ):
                result = self.context_merger.holiday_merger.merge_holiday_with_time_delta(
                    cur, delta_token, base_time
                )
                if result:
                    return result, 3  # Skip holiday + 'in' + delta tokens

        # Priority 0.7: Check for "holiday time_delta" pattern (without 'in')
        # Example: "thanksgiving 3 years" -> apply year offset to holiday
        if cur_type == "time_holiday" and i + 1 < n:
            delta_token = tokens[i + 1]
            if delta_token.get("type") == "time_delta" and delta_token.get("year"):
                result = self.context_merger.holiday_merger.merge_holiday_with_time_delta(
                    cur, delta_token, base_time
                )
                if result:
                    return result, 2  # Skip holiday + delta tokens

        return None
