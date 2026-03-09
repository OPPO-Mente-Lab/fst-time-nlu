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
    month_name_to_number,
    get_month_range,
    parse_datetime_str,
    format_datetime_str,
    create_day_range,
    get_parser_and_parse,
)


class UTCMerger:
    """Merger for handling UTC-related time expressions"""

    def __init__(self, parsers, time_expression_merger=None):
        """
        Initialize UTC merger

        Args:
            parsers (dict): Dictionary containing various time parsers
            time_expression_merger: Reference to TimeExpressionMerger for accessing period merge methods
        """
        self.parsers = parsers
        self.logger = get_logger(__name__)
        self.time_expression_merger = time_expression_merger

    def merge_utc_with_relative(self, utc_token, relative_token, base_time):
        """
        Merge time_utc with time_relative
        Use relative date + utc time
        Also handles period adjustment if relative_token has noon field
        """
        try:
            # Parse the relative date first
            relative_parser = self.parsers.get("time_relative")
            if not relative_parser:
                return None

            relative_result = relative_parser.parse(relative_token, base_time)
            if not relative_result:
                return None

            # Get the date from relative result (start of range)
            relative_date_str = relative_result[0][0]
            relative_date = parse_datetime_str(relative_date_str)

            # Check if relative token has noon field (e.g., "tomorrow evening")
            noon_field = relative_token.get("noon", "").strip('"')
            if noon_field:
                # Create a synthetic period token and adjust hour
                period_token = {"noon": noon_field}
                if self.time_expression_merger:
                    adjusted_result = self.time_expression_merger.merge_time_with_period(
                        utc_token, period_token, relative_date
                    )
                    return adjusted_result

            # Parse the time from utc token using the relative date as base
            utc_parser = self.parsers.get("time_utc")
            if not utc_parser:
                return None

            time_result = utc_parser.parse(utc_token, relative_date)
            return time_result

        except Exception as e:
            self.logger.debug(f"Error in merge_utc_with_relative: {e}")
            return None

    def merge_relative_with_utc(self, relative_token, utc_token, base_time):
        """
        Merge time_relative with time_utc
        Use relative date + utc time (same as above, different order)
        """
        return self.merge_utc_with_relative(utc_token, relative_token, base_time)

    def merge_weekday_with_utc(self, weekday_token, utc_token, base_time):
        """
        Merge time_weekday with time_utc
        Use weekday date + utc time
        """
        try:
            # Parse the weekday date first
            weekday_parser = self.parsers.get("time_weekday")
            if not weekday_parser:
                return None

            weekday_result = weekday_parser.parse(weekday_token, base_time)
            if not weekday_result:
                return None

            # Get the date from weekday result (start of range)
            weekday_date_str = weekday_result[0][0]
            weekday_date = parse_datetime_str(weekday_date_str)

            # Parse the time from utc token using the weekday date as base
            utc_parser = self.parsers.get("time_utc")
            if not utc_parser:
                return None

            time_result = utc_parser.parse(utc_token, weekday_date)
            return time_result

        except Exception as e:
            self.logger.debug(f"Error in merge_weekday_with_utc: {e}")
            return None

    def merge_utc_with_weekday(self, utc_token, weekday_token, base_time):
        """
        Merge time_utc with time_weekday
        Use weekday date + utc time
        """
        try:
            # Parse the weekday date first
            weekday_parser = self.parsers.get("time_weekday")
            if not weekday_parser:
                return None

            weekday_result = weekday_parser.parse(weekday_token, base_time)
            if not weekday_result:
                return None

            # Get the date from weekday result (start of range)
            weekday_date_str = weekday_result[0][0]
            weekday_date = parse_datetime_str(weekday_date_str)

            # Parse the time from utc token using the weekday date as base
            utc_parser = self.parsers.get("time_utc")
            if not utc_parser:
                return None

            time_result = utc_parser.parse(utc_token, weekday_date)
            return time_result

        except Exception as e:
            self.logger.debug(f"Error in merge_utc_with_weekday: {e}")
            return None

    def merge_utc_with_delta(self, utc_token, delta_token, base_time):  # noqa: C901
        """
        Merge time_utc and time_delta tokens

        Args:
            utc_token (dict): UTC time token (e.g., month)
            delta_token (dict): Time delta token (e.g., year offset)
            base_time (datetime): Base time reference

        Returns:
            list: Merged time result or None
        """
        # Extract UTC components
        utc_month = utc_token.get("month", "").strip('"')
        utc_day = utc_token.get("day", "").strip('"')
        utc_year = utc_token.get("year", "").strip('"')

        # Extract delta components
        delta_direction = delta_token.get("direction", "").strip('"')
        delta_year = delta_token.get("year", "").strip('"')
        delta_month = delta_token.get("month", "").strip('"')
        delta_day = delta_token.get("day", "").strip('"')

        # Calculate target date
        target_date = base_time

        # Apply year delta
        if delta_year:
            try:
                years_delta = int(delta_year)
                if delta_direction == "future":
                    target_date = target_date + relativedelta(years=years_delta)
                elif delta_direction == "past":
                    target_date = target_date - relativedelta(years=years_delta)
            except (ValueError, TypeError):
                pass

        # Apply month delta
        if delta_month:
            try:
                months_delta = int(delta_month)
                if delta_direction == "future":
                    target_date = target_date + relativedelta(months=months_delta)
                elif delta_direction == "past":
                    target_date = target_date - relativedelta(months=months_delta)
            except (ValueError, TypeError):
                pass

        # Apply day delta
        if delta_day:
            try:
                days_delta = int(delta_day)
                if delta_direction == "future":
                    target_date = target_date + relativedelta(days=days_delta)
                elif delta_direction == "past":
                    target_date = target_date - relativedelta(days=days_delta)
            except (ValueError, TypeError):
                pass

        # Apply UTC components to target date
        if utc_year:
            try:
                target_date = target_date.replace(year=int(utc_year))
            except (ValueError, TypeError):
                pass

        if utc_month:
            try:
                month_num = month_name_to_number(utc_month)
                if month_num:
                    target_date = target_date.replace(month=month_num)
            except (ValueError, TypeError):
                pass

        if utc_day:
            try:
                target_date = target_date.replace(day=int(utc_day))
            except (ValueError, TypeError):
                pass

        # Return appropriate time range based on what components we have
        if utc_day:
            # Full date: return single day range
            start_of_day, end_of_day = create_day_range(target_date)
            return [
                [
                    format_datetime_str(start_of_day),
                    format_datetime_str(end_of_day),
                ]
            ]
        elif utc_month:
            # Month only: return full month range
            # Use the same logic as BaseParser._get_month_range for consistency
            start_of_month, end_of_month = get_month_range(target_date)
            return [
                [
                    format_datetime_str(start_of_month),
                    format_datetime_str(end_of_month),
                ]
            ]
        elif utc_year:
            # Year only: return full year range
            start_of_year = target_date.replace(
                month=1, day=1, hour=0, minute=0, second=0, microsecond=0
            )
            end_of_year = target_date.replace(
                month=12, day=31, hour=23, minute=59, second=59, microsecond=0
            )
            return [
                [
                    format_datetime_str(start_of_year),
                    format_datetime_str(end_of_year),
                ]
            ]

        return None

    def merge_utc_date_components(self, i, tokens, base_time):  # noqa: C901
        """
        Merge consecutive time_utc tokens that form a complete date
        Pattern: time_utc(day) + time_utc(month/year) or time_utc(month) + time_utc(day/year)
        Example: "31st Oct 1974" -> day=31 + month=10,year=1974
                 "february the 15th" -> month=2 + day=15
                 "15th february" -> day=15 + month=2

        Args:
            i (int): Current token index
            tokens (list): List of tokens
            base_time (datetime): Base time reference

        Returns:
            tuple: (merged_results, skip_count) or None
        """
        n = len(tokens)
        cur = tokens[i]

        # Skip merging if current token already has a complete date (month + day)
        # This prevents incorrect merging of complete dates in comma-separated lists
        # e.g., "October 27, 2019, October 27, November 17" should NOT merge the first two dates
        if "month" in cur and "day" in cur:
            return None

        # Collect consecutive time_utc tokens (skipping empty token separators and common separators)
        utc_tokens = [cur]
        j = i + 1

        # Separators that can appear between date components
        separators = ["", ",", "the", "of"]

        while j < n:
            # Skip separator tokens
            if (
                tokens[j].get("type") == "token"
                and tokens[j].get("value", "").strip().lower() in separators
            ):
                j += 1
                continue
            # Collect time_utc tokens
            if tokens[j].get("type") == "time_utc":
                utc_tokens.append(tokens[j])
                j += 1
            else:
                break

        # Need at least 2 time_utc tokens to merge
        if len(utc_tokens) < 2:
            return None

        # Merge all collected tokens into one
        merged = {}
        has_date_components = False

        for token in utc_tokens:
            # Copy date components
            if "year" in token:
                merged["year"] = token["year"]
                has_date_components = True
            if "month" in token:
                merged["month"] = token["month"]
                has_date_components = True
            if "day" in token:
                merged["day"] = token["day"]
                has_date_components = True

            # Copy time components - for time merging, combine hour and minute
            if "hour" in token:
                if "hour" not in merged:
                    merged["hour"] = token["hour"]
                else:
                    # Combine hours: "twelve zero three" -> hour=12, minute=03
                    # This is a special case for time merging
                    pass
            if "minute" in token:
                if "minute" not in merged:
                    merged["minute"] = token["minute"]
                else:
                    # For time merging, the second minute should be combined with the first hour
                    # "twelve zero three" -> hour=12, minute=03
                    first_hour = merged.get("hour", "0")
                    second_minute = token["minute"]
                    merged["minute"] = first_hour + second_minute.zfill(2)
            if "period" in token:
                merged["period"] = token["period"]
            if "noon" in token:
                merged["noon"] = token["noon"]

        # Only merge if we have date components or time components
        has_time_components = any("hour" in token or "minute" in token for token in utc_tokens)
        if not has_date_components and not has_time_components:
            return None

        # Set type
        merged["type"] = "time_utc"

        # Parse the merged token
        result = get_parser_and_parse(self.parsers, "time_utc", merged, base_time)
        if result:
            return (result, j - i)  # Skip all consumed tokens

        return None

    def adjust_utc_with_period_token(self, utc_token, period_token, base_time):
        """
        Adjust time_utc with a separate pm/am token
        """
        try:
            period_value = period_token.get("value", "").lower()
            if period_value not in ["pm", "am"]:
                return None

            # Create adjusted utc token with period
            adjusted_token = utc_token.copy()
            adjusted_token["period"] = f"{period_value}."

            # Parse with adjusted token
            utc_parser = self.parsers.get("time_utc")
            if not utc_parser:
                return None

            time_result = utc_parser.parse(adjusted_token, base_time)
            return time_result

        except Exception as e:
            self.logger.debug(f"Error in adjust_utc_with_period_token: {e}")
            return None

    def parse_time_token(self, token, base_time):
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
            self.logger.debug(f"Error in parse_time_token: {e}")
            return None

    def check_false_time_recognition(self, i, tokens):  # noqa: C901
        """
        Check if a time_utc token is likely a false positive (e.g., "at 3" in "at 363 hospital")

        Args:
            i (int): Current token index
            tokens (list): List of tokens

        Returns:
            bool: True if this is likely a false positive, False otherwise
        """
        if i >= len(tokens):
            return False

        cur = tokens[i]
        if cur.get("type") != "time_utc":
            return False

        # Check if this time_utc token has suspicious characteristics
        hour = cur.get("hour", "").strip('"')
        minute = cur.get("minute", "").strip('"')
        period = cur.get("period", "").strip('"')

        # Condition 1: No period (am/pm) - suspicious for simple "at X" patterns
        has_period = bool(period and period.lower() in ["am", "pm", "a.m.", "p.m."])

        # Condition 2: No minute or minute is '00' - suspicious for simple "at X" patterns
        has_meaningful_minute = bool(minute and minute != "00")

        # Condition 3: Check if followed by numeric tokens or location-related words
        followed_by_digits = False
        followed_by_location = False
        if i + 1 < len(tokens):
            next_token = tokens[i + 1]
            if (
                next_token.get("type") == "token"
                and next_token.get("value", "").strip()
                and next_token.get("value", "").strip().isdigit()
            ):
                followed_by_digits = True

        # Check for location-related words in the next few tokens
        location_keywords = [
            "street",
            "avenue",
            "road",
            "hospital",
            "hotel",
            "room",
            "flight",
            "gate",
            "terminal",
            "building",
            "floor",
            "level",
        ]
        for j in range(i + 1, min(i + 4, len(tokens))):  # Check next 3 tokens
            token = tokens[j]
            if (
                token.get("type") == "token"
                and token.get("value", "").strip().lower() in location_keywords
            ):
                followed_by_location = True
                break

        # Condition 4: Check if the hour is in a reasonable range but context doesn't support it
        try:
            hour_val = int(hour)
            reasonable_hour = 1 <= hour_val <= 24
        except (ValueError, TypeError):
            reasonable_hour = False

        # Check for "N-Npm" pattern: if this looks like a date but is followed by am/pm
        # Example: "3-4pm" should be interpreted as time range, not date
        # This should NOT be marked as false positive
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
                    # This is likely a time range, not a date - do NOT mark as false positive
                    return False
            except (ValueError, TypeError):
                pass

        # If it's a simple "at X" pattern (no period, no meaningful minute)
        # AND it's followed by digits or location words, it's likely a false positive
        if (
            not has_period
            and not has_meaningful_minute
            and (followed_by_digits or followed_by_location)
            and reasonable_hour
        ):
            return True

        return False
