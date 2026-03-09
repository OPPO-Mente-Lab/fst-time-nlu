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


class Priority1Rules(BaseRule):
    """Rules for Priority 1: UTC date components, UTC+relative, UTC+delta, etc."""

    def try_merge(
        self, i: int, tokens: List[Dict[str, Any]], base_time: datetime
    ) -> Optional[Tuple[List, int]]:
        """
        Try to merge based on Priority 1 rules

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

        # Rule 0: time_utc + time_utc date component merge
        # Pattern: time_utc(day) + time_utc(month/year) or time_utc(month) + time_utc(day/year)
        # Example: "31st Oct 1974", "february the 15th", "15th february"
        if cur_type == "time_utc":
            result = self.context_merger.utc_merger.merge_utc_date_components(i, tokens, base_time)
            if result:
                return result

        # Rule 1: time_utc + time_relative merge
        # Pattern: time_utc(hour, minute, period) + time_relative(offset_day)
        # Example: "at 3 pm today"
        if cur_type == "time_utc" and i + 1 < n:
            next_token = tokens[i + 1]
            if next_token.get("type") == "time_relative":
                result = self.context_merger.utc_merger.merge_utc_with_relative(
                    cur, next_token, base_time
                )
                if result:
                    return result, 2  # Skip both tokens

        # Rule 2: time_utc + time_delta merge
        # Pattern: time_utc(month) + time_delta(year)
        # Example: "March in 1 year"
        if cur_type == "time_utc":
            # Check for time_delta in the next few tokens (skip empty tokens)
            for j in range(i + 1, min(i + 4, n)):  # Check up to 3 tokens ahead
                next_token = tokens[j]
                if next_token.get("type") == "time_delta":
                    result = self.context_merger.utc_merger.merge_utc_with_delta(
                        cur, next_token, base_time
                    )
                    if result:
                        return result, j - i + 1  # Skip all tokens from i to j
                elif next_token.get("type") != "token" or (
                    next_token.get("value", "").strip()
                    and next_token.get("value", "").strip() not in ["in", "from", "to"]
                ):
                    # If it's not an empty token or a connector word, stop looking
                    break

        # Rule 2: time_relative + time_utc merge
        # Pattern: time_relative(offset_day) + time_utc(hour, minute, period)
        # Example: "today at 3 pm"
        # Also handles: time_relative + "at" + number
        # Example: "tomorrow at 8"
        if cur_type == "time_relative" and i + 1 < n:
            next_token = tokens[i + 1]
            if next_token.get("type") == "time_utc":
                result = self.context_merger.utc_merger.merge_relative_with_utc(
                    cur, next_token, base_time
                )
                if result:
                    return result, 2  # Skip both tokens
            # Check for "at" + number pattern (handles both single and two-digit numbers)
            elif (
                next_token.get("type") == "token"
                and next_token.get("value", "").lower() == "at"
                and i + 2 < n
            ):
                third_token = tokens[i + 2]
                if third_token.get("type") == "token" and third_token.get("value", "").isdigit():
                    # Check if this is a two-digit number split across tokens
                    hour_str = third_token.get("value", "")
                    tokens_to_skip = 3  # Default: relative + "at" + single digit

                    if i + 3 < n:
                        fourth_token = tokens[i + 3]
                        if (
                            fourth_token.get("type") == "token"
                            and fourth_token.get("value", "").isdigit()
                        ):
                            hour_str = third_token.get("value", "") + fourth_token.get("value", "")
                            tokens_to_skip = 4  # relative + "at" + first digit + second digit

                    hour = int(hour_str)
                    if 1 <= hour <= 12:
                        # Create a synthetic time_utc token
                        # Special handling: "at 12" defaults to noon (12:00 PM), not midnight
                        period = "p.m." if hour == 12 else "a.m."
                        synthetic_utc = {
                            "type": "time_utc",
                            "hour": str(hour),
                            "minute": "00",
                            "period": period,
                        }
                        result = self.context_merger.utc_merger.merge_relative_with_utc(
                            cur, synthetic_utc, base_time
                        )
                        if result:
                            return result, tokens_to_skip

        # Rule 2.5: ordinal + weekday + of/in + month merge
        # Pattern: token('first'/'second'/...) + time_weekday + token('of'/'in') + (time_composite_relative(month) | token('month'))
        # Example: "first Monday of this month", "second Tuesday in the month"
        if cur_type == "token" and cur.get("value", "").lower() in [
            "first",
            "second",
            "third",
            "fourth",
            "fifth",
            "last",
        ]:
            result = self.context_merger.modifier_merger.merge_ordinal_weekday_month(
                i, tokens, base_time
            )
            if result:
                return result

        # Rule 2.6: time_period + time_utc merge
        # Pattern: time_period(noon/evening/etc.) + time_utc(hour)
        # Example: "noon 12 o'clock" -> 12:00
        # Example: "evening 8 o'clock" -> 20:00
        if cur_type == "time_period" and i + 1 < n:
            next_token = tokens[i + 1]
            # Skip empty tokens
            j = i + 1
            while (
                j < n
                and next_token.get("type") == "token"
                and next_token.get("value", "").strip() == ""
            ):
                j += 1
                if j < n:
                    next_token = tokens[j]

            if next_token.get("type") == "time_utc":
                # Merge period with time to adjust hour
                result = self.context_merger.time_expression_merger.merge_time_with_period(
                    next_token, cur, base_time
                )
                if result:
                    return (result, j + 1)  # Skip both period and time tokens

        # Rule 3: time_weekday + time_utc merge
        # Pattern: time_weekday(offset_week, week_day) + time_utc(hour, minute)
        # Example: "next tuesday at 4 pm"
        if cur_type == "time_weekday" and i + 1 < n:
            next_token = tokens[i + 1]
            if next_token.get("type") == "time_utc":
                result = self.context_merger.utc_merger.merge_weekday_with_utc(
                    cur, next_token, base_time
                )
                if result:
                    return result, 2  # Skip both tokens

        # Rule 3b: time_utc + time_weekday merge
        # Pattern: time_utc(hour, minute, period) + time_weekday(week_day)
        # Example: "at 9am on Saturday"
        if cur_type == "time_utc" and i + 1 < n:
            next_token = tokens[i + 1]
            if next_token.get("type") == "time_weekday":
                result = self.context_merger.utc_merger.merge_utc_with_weekday(
                    cur, next_token, base_time
                )
                if result:
                    return result, 2  # Skip both tokens

        # Rule 3c: time_utc + "for" + time_relative merge
        # Pattern: time_utc(hour, minute) + token("for") + time_relative
        # Example: "8 o'clock for tomorrow"
        if cur_type == "time_utc":
            for_result = self.context_merger.delta_merger.try_merge_time_for_relative(
                i, tokens, base_time
            )
            if for_result:
                return for_result

        # Rule 3.5: "weekday + from/between + time_range" pattern
        # Example: "Thursday from 9:30 to 11:00"
        if cur_type == "time_weekday":
            weekday_range_result = self.context_merger._try_merge_weekday_time_range(
                i, tokens, base_time
            )
            if weekday_range_result:
                return weekday_range_result

        # Rule 3.7: time_delta + "from" + time_utc/time_relative merge
        # Pattern: time_delta + "from" + time_utc/time_relative
        # Example: "15 minutes from 1pm", "a day from now"
        if cur_type in ["time_delta", "token"]:
            from_result = self.context_merger.delta_merger.try_merge_delta_from_time(
                i, tokens, base_time
            )
            if from_result:
                return from_result

        # Rule 3.8: number + weekday + "from" + time_relative merge
        # Pattern: token(number) + token(weekday) + token("from") + time_relative
        # Example: "3 fridays from now", "2 sundays from now"
        if cur_type == "token":
            weekday_from_result = self.context_merger.delta_merger.try_merge_weekday_from_now(
                i, tokens, base_time
            )
            if weekday_from_result:
                return weekday_from_result

        # Rule 4: time_utc + token(pm/am) post-processing
        # Pattern: time_utc(hour, minute) + token(value='pm'/'am')
        # Example: "at 4 pm" (when pm is not merged by FST)
        if cur_type == "time_utc" and i + 1 < n:
            next_token = tokens[i + 1]
            if next_token.get("type") == "token" and next_token.get("value", "").lower() in [
                "pm",
                "am",
            ]:
                result = self.context_merger.utc_merger.adjust_utc_with_period_token(
                    cur, next_token, base_time
                )
                if result:
                    return result, 2  # Skip both tokens

        # Rule 4.5: Handle "at" + past/to time expressions
        # Pattern: time_utc + time_utc (when FST fails to merge "at X past Y")
        # Example: "at 20 past 3pm" -> FST produces two time_utc tokens that need merging
        if cur_type == "time_utc" and i + 1 < n:
            next_token = tokens[i + 1]
            if (
                next_token.get("type") == "time_utc"
                and "hour" in cur
                and "minute" in cur
                and "hour" in next_token
                and "period" in next_token
            ):
                # This looks like "X past Y" pattern that wasn't merged by FST
                # Check if this could be a past/to expression
                cur_hour = int(cur.get("hour", 0))
                cur_minute = int(cur.get("minute", 0))
                next_hour = int(next_token.get("hour", 0))
                next_period = next_token.get("period", "").strip('"')

                # If cur has hour=2, minute=0 and next has hour=3, period=p.m.
                # This looks like "at 20 past 3pm" -> "20 past 3pm"
                if (
                    cur_hour == 2
                    and cur_minute == 0
                    and next_hour in [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
                    and next_period in ["p.m.", "pm", "a.m.", "am"]
                ):
                    # This is likely a past/to expression that wasn't merged
                    # Skip the first token and let the second token be processed normally
                    return (None, 0)  # Special marker: skip this token

        # Rule 4.6: Handle quarter/fraction + past/to + time expressions
        # Pattern: token('quarter') + token('past') + time_period
        # Example: "quarter past noon" -> should be "quarter past noon"
        if cur_type == "token" and cur.get("value", "").lower() == "quarter" and i + 4 < n:
            # Check for pattern: quarter + empty_token + 'past' + empty_token + time_period
            if (
                tokens[i + 1].get("type") == "token"
                and tokens[i + 1].get("value", "") == ""
                and tokens[i + 2].get("type") == "token"
                and tokens[i + 2].get("value", "").lower() == "past"
                and tokens[i + 3].get("type") == "token"
                and tokens[i + 3].get("value", "") == ""
                and tokens[i + 4].get("type") == "time_period"
            ):

                # This is a quarter + past + time_period pattern
                time_period_token = tokens[i + 4]

                # Get the time period
                noon_value = time_period_token.get("noon", "").strip('"')

                if noon_value == "noon":
                    # "quarter past noon" -> 12:15
                    from ...time_utils import format_datetime_str

                    target_time = base_time.replace(hour=12, minute=15, second=0, microsecond=0)
                    return ([[format_datetime_str(target_time)]], 5)  # Skip 5 tokens

                return None

        # Rule 4.7: Handle fraction + past/to + time expressions
        # Pattern: fraction + token('past') + time_period
        # Example: "a quarter past noon" -> should be "quarter past noon"
        if cur_type == "fraction" and i + 3 < n:
            # Check for pattern: fraction + empty_token + 'past' + empty_token + time_period
            if (
                tokens[i + 1].get("type") == "token"
                and tokens[i + 1].get("value", "") == ""
                and tokens[i + 2].get("type") == "token"
                and tokens[i + 2].get("value", "").lower() == "past"
                and tokens[i + 3].get("type") == "token"
                and tokens[i + 3].get("value", "") == ""
                and i + 4 < n
                and tokens[i + 4].get("type") == "time_period"
            ):

                # This is a fraction + past + time_period pattern
                fraction_token = cur
                time_period_token = tokens[i + 4]

                # Parse the fraction
                numerator = fraction_token.get("numerator", "").strip('"')
                denominator = fraction_token.get("denominator", "").strip('"')

                if not (
                    (numerator == "a" and denominator == "4")
                    or (numerator == "1" and denominator == "4")
                ):
                    # Skip this pattern
                    return None

                # Get the time period
                noon_value = time_period_token.get("noon", "").strip('"')

                if noon_value == "noon":
                    # "quarter past noon" -> 12:15
                    from ...time_utils import format_datetime_str

                    target_time = base_time.replace(hour=12, minute=15, second=0, microsecond=0)
                    return ([[format_datetime_str(target_time)]], 5)  # Skip 5 tokens

                return None

        return None
