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
from ..time_utils import parse_datetime_str, format_datetime_str

from ....core.logger import get_logger


class TimeExpressionMerger:
    """Merger for handling time expression patterns like past/to, fraction, etc."""

    def __init__(self, parsers, context_merger=None):
        """
        Initialize time expression merger

        Args:
            parsers (dict): Dictionary containing various time parsers
            context_merger: Reference to ContextMerger for accessing UTC merge methods
        """
        self.parsers = parsers
        self.logger = get_logger(__name__)
        self.context_merger = context_merger

    def merge_time_with_period(self, time_token, period_token, base_time):  # noqa: C901
        """
        Merge time_utc with time_period to adjust hour based on period
        Example: "3 o'clock in the afternoon" -> 15:00
        Example: "february 15th in the morning" -> 2013-02-15T06:00:00Z to 2013-02-15T12:00:00Z
        """
        try:
            period = period_token.get("noon", "").strip('"')

            # If time_token has month/day, apply period to that specific date
            if "month" in time_token or "day" in time_token:
                # Parse the date first
                utc_parser = self.parsers.get("time_utc")
                if utc_parser:
                    date_result = utc_parser.parse(time_token, base_time)
                    if date_result and len(date_result) > 0:
                        # Extract date from result
                        date_time_str = date_result[0][0]  # Start time
                        from datetime import datetime

                        target_date = parse_datetime_str(date_time_str).replace(tzinfo=None)

                        # Apply period to that date
                        return self.apply_period_to_date(period, target_date)
                return None

            # Handle time-only tokens (hour/minute)
            hour = int(time_token.get("hour", 0))
            minute = int(time_token.get("minute", 0))

            # Adjust hour based on period
            # Following Chinese FST logic: afternoon/evening/night add 12 to hours < 12
            if period == "morning":
                # Morning: 1-11 AM (no change needed for 1-11)
                if hour == 12:
                    hour = 0  # 12 AM = midnight
            elif period in ["afternoon", "evening", "night", "tonight"]:
                # Afternoon/Evening/Night: add 12 to hours < 12
                if hour < 12:
                    hour += 12
                # hour == 12 remains as 12 (12:00 PM)
            elif period == "noon":
                # Noon: 12 PM
                hour = 12
            elif period == "midnight":
                # Midnight: 12 AM
                hour = 0

            # Create target time
            target_time = base_time.replace(hour=hour, minute=minute, second=0, microsecond=0)
            return [[format_datetime_str(target_time)]]

        except Exception as e:
            self.logger.debug(f"Error in merge_time_with_period: {e}")
            return None

    def merge_past_time(self, minute_token, target_time_token, base_time):
        """
        Merge minute + past + target_time
        Example: "20 past 3pm" -> 15:20
        """
        try:
            # Handle case where minute_token is actually hour:minute format
            if minute_token.get("minute", 0) == 0:
                # Treat hour as minutes (e.g., "20" -> 20 minutes)
                minutes = int(minute_token.get("hour", 0))
            else:
                minutes = int(minute_token.get("minute", 0))

            target_hour = int(target_time_token.get("hour", 0))
            target_period = target_time_token.get("period", "").strip('"')

            # Convert target hour to 24-hour format
            if target_period.upper() in ["PM", "P.M."]:
                if target_hour != 12:
                    target_hour += 12
            elif target_period.upper() in ["AM", "A.M."]:
                if target_hour == 12:
                    target_hour = 0

            # Calculate final time
            final_hour = target_hour
            final_minute = minutes

            # Create target time
            target_time = base_time.replace(
                hour=final_hour, minute=final_minute, second=0, microsecond=0
            )
            return [[format_datetime_str(target_time)]]

        except Exception as e:
            self.logger.debug(f"Error in merge_past_time: {e}")
            return None

    def merge_to_time(self, minute_token, target_time_token, base_time):
        """
        Merge minute + to + target_time
        Example: "20 to 4pm" -> 15:40
        """
        try:
            minutes = int(minute_token.get("minute", 0))
            target_hour = int(target_time_token.get("hour", 0))
            target_period = target_time_token.get("period", "").strip('"')

            # Convert target hour to 24-hour format
            if target_period.upper() in ["PM", "P.M."]:
                if target_hour != 12:
                    target_hour += 12
            elif target_period.upper() in ["AM", "A.M."]:
                if target_hour == 12:
                    target_hour = 0

            # Calculate final time (subtract minutes from target hour)
            final_hour = target_hour
            final_minute = 60 - minutes

            # Handle hour rollback
            if final_minute >= 60:
                final_minute -= 60
                final_hour += 1
            if final_hour >= 24:
                final_hour -= 24

            # Create target time
            target_time = base_time.replace(
                hour=final_hour, minute=final_minute, second=0, microsecond=0
            )
            return [[format_datetime_str(target_time)]]

        except Exception as e:
            self.logger.debug(f"Error in merge_to_time: {e}")
            return None

    def merge_fraction_past_period(self, fraction_token, period_token, base_time):
        """
        Merge fraction + past + time_period
        Example: "a quarter past noon" -> 12:15
        """
        try:
            numerator = fraction_token.get("numerator", "").strip('"')
            denominator = int(fraction_token.get("denominator", 1))
            period = period_token.get("noon", "").strip('"')

            # Calculate minutes based on fraction
            if numerator.lower() == "a" and denominator == 4:
                minutes = 15  # quarter = 15 minutes
            elif numerator.lower() == "a" and denominator == 2:
                minutes = 30  # half = 30 minutes
            else:
                minutes = 60 // denominator  # general case

            # Determine base hour based on period
            if period == "noon":
                base_hour = 12
            elif period == "midnight":
                base_hour = 0
            else:
                return None

            # Calculate final time
            final_hour = base_hour
            final_minute = minutes

            # Create target time
            target_time = base_time.replace(
                hour=final_hour, minute=final_minute, second=0, microsecond=0
            )
            return [[format_datetime_str(target_time)]]

        except Exception as e:
            self.logger.debug(f"Error in merge_fraction_past_period: {e}")
            return None

    def merge_fraction_to_period(self, fraction_token, period_token, base_time):  # noqa: C901
        """
        Merge fraction + to + time_period
        Example: "a quarter to noon" -> 11:45
        """
        try:
            numerator = fraction_token.get("numerator", "").strip('"')
            denominator = int(fraction_token.get("denominator", 1))
            period = period_token.get("noon", "").strip('"')

            # Calculate minutes based on fraction
            if numerator.lower() == "a" and denominator == 4:
                minutes = 15  # quarter = 15 minutes
            elif numerator.lower() == "a" and denominator == 2:
                minutes = 30  # half = 30 minutes
            else:
                minutes = 60 // denominator  # general case

            # Determine base hour based on period
            if period == "noon":
                base_hour = 12
            elif period == "midnight":
                base_hour = 0
            else:
                return None

            # Calculate final time (subtract minutes from base hour)
            # For "to", we go back in time from the target hour
            final_hour = base_hour
            final_minute = 0 - minutes  # Start from 0 minutes and subtract

            # Handle hour rollback when final_minute becomes negative
            if final_minute < 0:
                final_minute += 60
                final_hour -= 1
            elif final_minute >= 60:
                final_minute -= 60
                final_hour += 1
            if final_hour >= 24:
                final_hour -= 24
            elif final_hour < 0:
                final_hour += 24

            # Create target time
            target_time = base_time.replace(
                hour=final_hour, minute=final_minute, second=0, microsecond=0
            )
            return [[format_datetime_str(target_time)]]

        except Exception as e:
            self.logger.debug(f"Error in merge_fraction_to_period: {e}")
            return None

    def merge_number_minutes_past_period(self, num1_token, num2_token, period_token, base_time):
        """
        Merge number + minutes + past + time_period
        Example: "15 minutes past noon" -> 12:15
        """
        try:
            num1 = int(num1_token.get("value", 0))
            num2 = int(num2_token.get("value", 0))
            minutes = num1 * 10 + num2  # Combine digits (e.g., "1" + "5" = 15)
            period = period_token.get("noon", "").strip('"')

            # Determine base hour based on period
            if period == "noon":
                base_hour = 12
            elif period == "midnight":
                base_hour = 0
            else:
                return None

            # Calculate final time
            final_hour = base_hour
            final_minute = minutes

            # Create target time
            target_time = base_time.replace(
                hour=final_hour, minute=final_minute, second=0, microsecond=0
            )
            return [[format_datetime_str(target_time)]]

        except Exception as e:
            self.logger.debug(f"Error in merge_number_minutes_past_period: {e}")
            return None

    def merge_number_minutes_past_period_single(self, minutes, period_token, base_time):
        """
        Merge single number + past + time_period
        Example: "15 past noon" -> 12:15
        """
        try:
            period = period_token.get("noon", "").strip('"')

            # Determine base hour based on period
            if period == "noon":
                base_hour = 12
            elif period == "midnight":
                base_hour = 0
            else:
                return None

            # Calculate final time
            final_hour = base_hour
            final_minute = minutes

            # Create target time
            target_time = base_time.replace(
                hour=final_hour, minute=final_minute, second=0, microsecond=0
            )
            return [[format_datetime_str(target_time)]]

        except Exception as e:
            self.logger.debug(f"Error in merge_number_minutes_past_period_single: {e}")
            return None

    def merge_at_number(self, i, tokens, base_time):  # noqa: C901
        """
        Merge "at" + number pattern
        Example: "at 9", "at 12" -> time_utc token

        Logic:
        1. Check if current token is "at"
        2. Check if next token is a number (1-12)
        3. Check if previous token is NOT a time expression (to avoid conflicts with Rule 2)
        4. Create a time_utc token with hour and default AM period

        Args:
            i (int): Current token index
            tokens (list): List of tokens
            base_time (datetime): Base time reference

        Returns:
            tuple: (merged_results_list, jump_count) or None
        """
        try:
            n = len(tokens)
            if i + 1 >= n:
                return None

            cur = tokens[i]
            next_tok = tokens[i + 1]

            # Check if current token is "at"
            if cur.get("type") != "token" or cur.get("value", "").lower() != "at":
                return None

            # Check if previous token is a time expression
            # If so, skip this merge and let Rule 2 handle it
            if i > 0:
                prev_tok = tokens[i - 1]
                prev_type = prev_tok.get("type", "")
                # Skip if previous token is a time-related type
                if prev_type in [
                    "time_relative",
                    "time_weekday",
                    "time_holiday",
                    "time_composite_relative",
                    "time_utc",
                    "time_range_expr",
                ]:
                    return None
                # Also skip if previous token is an empty string (word boundary)
                if prev_type == "token" and prev_tok.get("value", "").strip() == "":
                    # Check the token before the empty one
                    if i > 1:
                        prev_prev_tok = tokens[i - 2]
                        prev_prev_type = prev_prev_tok.get("type", "")
                        if prev_prev_type in [
                            "time_relative",
                            "time_weekday",
                            "time_holiday",
                            "time_composite_relative",
                            "time_utc",
                            "time_range_expr",
                        ]:
                            return None

            # Check if next token is a number (1-12)
            # Handle both single digit and two-digit numbers split across tokens
            if next_tok.get("type") != "token":
                return None

            next_value = next_tok.get("value", "")
            if not next_value.isdigit():
                return None

            # Check if this is a two-digit number split across tokens (e.g., "1" and "2" for "12")
            hour_str = next_value
            tokens_consumed = 2  # Default: "at" + single digit

            if i + 2 < n:
                third_tok = tokens[i + 2]
                # Check if third token is also a digit (for two-digit hours like "12")
                if third_tok.get("type") == "token" and third_tok.get("value", "").isdigit():
                    hour_str = next_value + third_tok.get("value", "")
                    tokens_consumed = 3  # "at" + first digit + second digit

            hour = int(hour_str)
            if hour < 1 or hour > 12:
                return None

            # Check if there's a relative token after the number (e.g., "at 9 today")
            # Skip empty tokens to find the next meaningful token
            relative_idx = i + tokens_consumed
            while (
                relative_idx < n
                and tokens[relative_idx].get("type") == "token"
                and tokens[relative_idx].get("value", "").strip() == ""
            ):
                relative_idx += 1

            if relative_idx < n:
                relative_tok = tokens[relative_idx]
                if relative_tok.get("type") in ["time_relative", "time_weekday"]:
                    # Create synthetic time_utc token
                    period = "p.m." if hour == 12 else "a.m."
                    synthetic_utc = {
                        "type": "time_utc",
                        "hour": str(hour),
                        "minute": "00",
                        "period": period,
                    }
                    # Merge with relative token
                    if self.context_merger:
                        if relative_tok.get("type") == "time_relative":
                            result = self.context_merger._merge_utc_with_relative(
                                synthetic_utc, relative_tok, base_time
                            )
                        else:  # time_weekday
                            result = self.context_merger._merge_utc_with_weekday(
                                synthetic_utc, relative_tok, base_time
                            )

                        if result:
                            return (
                                result,
                                relative_idx + 1,
                            )  # Skip all tokens including relative

            # No relative token found, create standalone time
            # Special handling: "at 12" defaults to noon (12:00 PM), not midnight
            # Other hours default to AM
            period = "p.m." if hour == 12 else "a.m."
            merged_token = {
                "type": "time_utc",
                "hour": str(hour),
                "minute": "00",
                "period": period,
            }

            # Parse the merged token
            parser = self.parsers.get("time_utc")
            if parser:
                result = parser.parse(merged_token, base_time)
                if result:
                    return (result, i + tokens_consumed)  # result is already a list

            return None

        except Exception as e:
            self.logger.debug(f"Error in merge_at_number: {e}")
            return None

    def check_short_time_range_pattern(self, i, tokens):  # noqa: C901
        """
        Check if current token is part of "N-Npm" pattern

        Args:
            i (int): Current token index
            tokens (list): List of tokens

        Returns:
            bool: True if this is a short time range pattern
        """
        if i >= len(tokens):
            return False

        cur = tokens[i]
        if cur.get("type") != "time_utc":
            return False

        # Pattern 1: Check if this looks like a date (has month and day) followed by am/pm
        if (
            cur.get("month")
            and cur.get("day")
            and i + 1 < len(tokens)
            and tokens[i + 1].get("type") == "token"
            and tokens[i + 1].get("value", "").strip().lower() in ["am", "pm", "a.m.", "p.m."]
        ):

            # Check if month and day values are reasonable for time range (both <= 24)
            try:
                month_val = int(cur.get("month", "").strip('"'))
                day_val = int(cur.get("day", "").strip('"'))
                if month_val <= 24 and day_val <= 24:
                    return True
            except (ValueError, TypeError):
                pass

        # Pattern 2: Check if this has month, day, hour, minute, and period (e.g., "9-11am")
        # This pattern suggests month=9, day=11, hour=1, minute=0, period=am
        if (
            cur.get("month")
            and cur.get("day")
            and cur.get("hour")
            and cur.get("minute")
            and cur.get("period")
        ):

            try:
                month_val = int(cur.get("month", "").strip('"'))
                day_val = int(cur.get("day", "").strip('"'))
                hour_val = int(cur.get("hour", "").strip('"'))
                minute_val = int(cur.get("minute", "").strip('"'))

                # If month and day are reasonable for time range (both <= 24)
                # and hour/minute suggest this is a misinterpreted time range
                if month_val <= 24 and day_val <= 24 and hour_val <= 12 and minute_val == 0:
                    return True
            except (ValueError, TypeError):
                pass

        return False

    def try_merge_short_time_range(self, i, tokens, base_time):  # noqa: C901
        """
        Try to merge "N-Npm" pattern into time range

        Args:
            i (int): Current token index (pointing to time_utc token)
            tokens (list): List of tokens
            base_time (datetime): Base time

        Returns:
            tuple: (result, jump_count) or None
        """
        try:
            cur = tokens[i]

            # Pattern 1: month+day followed by separate period token
            if (
                cur.get("month")
                and cur.get("day")
                and i + 1 < len(tokens)
                and tokens[i + 1].get("type") == "token"
                and tokens[i + 1].get("value", "").strip().lower() in ["am", "pm", "a.m.", "p.m."]
            ):

                period_token = tokens[i + 1]
                start_hour = int(cur.get("month", "").strip('"'))
                end_hour = int(cur.get("day", "").strip('"'))
                period = period_token.get("value", "").strip().lower()

                # Convert to 24-hour format
                if period in ["pm", "p.m."]:
                    if start_hour < 12:
                        start_hour += 12
                    if end_hour < 12:
                        end_hour += 12

                # Create start and end times
                start_time = base_time.replace(hour=start_hour, minute=0, second=0, microsecond=0)
                end_time = base_time.replace(hour=end_hour, minute=0, second=0, microsecond=0)

                # Handle case where end time might be next day (e.g., 22 to 02)
                if end_time <= start_time:
                    end_time = end_time + timedelta(days=1)

                result = [
                    [
                        format_datetime_str(start_time),
                        format_datetime_str(end_time),
                    ]
                ]

                return result, 2  # Skip 2 tokens: time_utc + period

            # Pattern 2: month+day+hour+minute+period all in one token (e.g., "9-11am")
            elif (
                cur.get("month")
                and cur.get("day")
                and cur.get("hour")
                and cur.get("minute")
                and cur.get("period")
            ):

                start_hour = int(cur.get("month", "").strip('"'))
                end_hour = int(cur.get("day", "").strip('"'))
                period = cur.get("period", "").strip('"').lower()

                # Convert to 24-hour format
                if period in ["pm", "p.m."]:
                    if start_hour < 12:
                        start_hour += 12
                    if end_hour < 12:
                        end_hour += 12

                # Create start and end times
                start_time = base_time.replace(hour=start_hour, minute=0, second=0, microsecond=0)
                end_time = base_time.replace(hour=end_hour, minute=0, second=0, microsecond=0)

                # Handle case where end time might be next day (e.g., 22 to 02)
                if end_time <= start_time:
                    end_time = end_time + timedelta(days=1)

                result = [
                    [
                        format_datetime_str(start_time),
                        format_datetime_str(end_time),
                    ]
                ]

                return result, 1  # Skip 1 token: time_utc

            return None

        except Exception as e:
            self.logger.debug(f"Error in try_merge_short_time_range: {e}")
            return None

    def apply_period_to_date(self, period, target_date):
        """
        Apply period to a specific date
        Example: morning + 2023-12-25 -> 2023-12-25T06:00:00Z to 2023-12-25T12:00:00Z
        """
        try:
            from datetime import datetime

            if period == "morning":
                start_time = target_date.replace(hour=6, minute=0, second=0)
                end_time = target_date.replace(hour=12, minute=0, second=0)
            elif period == "afternoon":
                start_time = target_date.replace(hour=12, minute=0, second=0)
                end_time = target_date.replace(hour=18, minute=0, second=0)
            elif period == "evening":
                start_time = target_date.replace(hour=18, minute=0, second=0)
                end_time = target_date.replace(hour=21, minute=0, second=0)
            elif period == "night":
                start_time = target_date.replace(hour=21, minute=0, second=0)
                end_time = target_date.replace(hour=23, minute=59, second=59)
            elif period == "tonight":
                start_time = target_date.replace(hour=18, minute=0, second=0)
                end_time = target_date.replace(hour=23, minute=59, second=59)
            elif period == "noon":
                start_time = target_date.replace(hour=12, minute=0, second=0)
                end_time = target_date.replace(hour=12, minute=0, second=0)
            elif period == "midnight":
                start_time, end_time = create_day_range(target_date)
            else:
                return None

            return [
                [
                    format_datetime_str(start_time),
                    format_datetime_str(end_time),
                ]
            ]

        except Exception as e:
            self.logger.debug(f"Error in apply_period_to_date: {e}")
            return None
