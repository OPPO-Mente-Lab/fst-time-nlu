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

from datetime import datetime

from .parser import (
    UTCTimeParser,
    PeriodParser,
    WeekParser,
    RelativeParser,
    HolidayParser,
    CompositeRelativeParser,
    TimeRangeParser,
    RangeParser,
    CenturyParser,
    TimeDeltaParser,
    QuarterParser,
    RecurringParser,
)
from .parser.context_merger import ContextMerger
from ..core.token_parser import TokenParser
from ..core.logger import get_logger


class TimeParser:
    """Convert FST tag results to actual datetime values for English"""

    def __init__(self):
        """
        Initialize English time parser
        """
        self.logger = get_logger(__name__)
        # Initialize all parsers
        self.parsers = {
            "time_utc": UTCTimeParser(),
            "time_period": PeriodParser(),
            "time_weekday": WeekParser(),
            "time_relative": RelativeParser(),
            "time_holiday": HolidayParser(),
            "time_composite_relative": CompositeRelativeParser(),
            "time_range": TimeRangeParser(),
            "time_range_expr": RangeParser(),
            "time_century": CenturyParser(),
            "time_delta": TimeDeltaParser(),
            "quarter_rule": QuarterParser(),
            "time_recurring": RecurringParser(),
        }

        # Initialize context merger for complex time expression merging
        self.context_merger = ContextMerger(self.parsers)

    def _parse_tokens(self, tag_str: str):
        """Parse FST output string into token dict list"""
        parser = TokenParser()
        parser.parse(tag_str)

        tokens = []
        for tok in parser.tokens:
            t_dict = {"type": tok.name}
            t_dict.update(tok.members)
            tokens.append(t_dict)
        return tokens

    def merge_time_parser(self, last_time, new_time):
        """Merge time parser results, sharing all offset_* parameters"""
        return [last_time[0], new_time[-1]]

    def _preprocess_tokens(self, tokens):  # noqa: C901
        """
        Preprocess tokens to fix misclassified char tokens that should be time tokens

        Args:
            tokens (list): List of tokens

        Returns:
            list: Preprocessed tokens
        """
        # Month names mapping
        MONTH_NAMES = {
            "january": "january",
            "february": "february",
            "march": "march",
            "april": "april",
            "may": "may",
            "june": "june",
            "july": "july",
            "august": "august",
            "september": "september",
            "october": "october",
            "november": "november",
            "december": "december",
            "jan": "january",
            "feb": "february",
            "mar": "march",
            "apr": "april",
            "jun": "june",
            "jul": "july",
            "aug": "august",
            "sep": "september",
            "sept": "september",
            "oct": "october",
            "nov": "november",
            "dec": "december",
        }

        processed = []
        last_had_period = False  # Track if last token had period info

        for i, token in enumerate(tokens):
            if token.get("type") == "token":
                value = token.get("value", "").lower()

                # Skip empty char tokens but keep period tracking
                if not value:
                    # Don't append, but don't reset last_had_period either
                    continue

                # Check if this is a month name
                if value in MONTH_NAMES:
                    processed.append({"type": "time_utc", "month": MONTH_NAMES[value]})
                    last_had_period = False
                # Check if this is a number (1-24) after a period token
                elif value.isdigit() and last_had_period:
                    hour_val = int(value)
                    if 1 <= hour_val <= 24:
                        processed.append({"type": "time_utc", "hour": value, "minute": "00"})
                    else:
                        processed.append(token)
                    last_had_period = False
                # Check if this is a weekday/weekend token
                elif value in ["weekend", "weekends"]:
                    processed.append({"type": "time_weekday", "week_period": "weekend"})
                    last_had_period = False
                elif value in ["weekday", "weekdays"]:
                    processed.append({"type": "time_weekday", "week_period": "weekday"})
                    last_had_period = False
                # Check if this is a relative day token (including possessive forms)
                elif value in ["yesterday", "yesterday's"]:
                    processed.append({"type": "time_relative", "offset_day": "-1"})
                    last_had_period = False
                elif value in ["today", "today's"]:
                    processed.append({"type": "time_relative", "offset_day": "0"})
                    last_had_period = False
                elif value in ["tomorrow", "tomorrow's"]:
                    processed.append({"type": "time_relative", "offset_day": "1"})
                    last_had_period = False
                else:
                    processed.append(token)
                    last_had_period = False
            else:
                # Check if this token has period info
                if token.get("type") in ["time_relative", "time_weekday"] and "period" in token:
                    last_had_period = True
                else:
                    last_had_period = False
                processed.append(token)

        return processed

    def _adjust_hour_by_period(self, hour, period_name):  # noqa: C901
        """
        Adjust hour based on period context (morning, afternoon, evening, night)

        Args:
            hour (int): Original hour (usually 1-12)
            period_name (str): Period name (morning, afternoon, evening, night, etc.)

        Returns:
            int: Adjusted hour in 24-hour format
        """
        period_lower = period_name.lower()

        # Period time ranges and adjustment logic:
        # morning: 6-12 (AM)
        # afternoon: 12-18 (PM, but use 12-hour base)
        # evening: 18-21 (PM)
        # night: 21-24 (PM)
        # noon/midday: 12
        # midnight: 0

        if period_lower in ["morning", "am", "a.m."]:
            # Morning: 6-12
            # If hour is 1-5, it's likely 7-11 (add 6)
            # If hour is 6-11, keep it
            # If hour is 12, it's noon (keep 12)
            if 1 <= hour <= 5:
                return hour + 6  # 1→7, 2→8, 3→9, 4→10, 5→11
            elif hour == 12:
                return 0  # 12am = midnight (0:00)
            else:
                return hour  # 6-11 stay as is

        elif period_lower in ["afternoon", "pm", "p.m."]:
            # Afternoon: 12-18 (12pm-6pm)
            # If hour is 1-6, it's 13-18 (add 12)
            # If hour is 12, it's 24 (midnight next day)
            if 1 <= hour <= 6:
                return hour + 12  # 1→13, 2→14, 3→15, 4→16, 5→17, 6→18
            elif hour == 12:
                return 24  # 12pm = 24:00 (next day 0:00)
            else:
                return hour

        elif period_lower in ["evening"]:
            # Evening: 18-21 (6pm-9pm)
            # If hour is 1-9, it's likely 19-21 or 18-20
            # Map: 6→18, 7→19, 8→20, 9→21
            if 1 <= hour <= 3:
                return hour + 18  # 1→19, 2→20, 3→21
            elif 6 <= hour <= 9:
                return hour + 12  # 6→18, 7→19, 8→20, 9→21
            elif hour == 12:
                return 18  # evening 12 means 6pm
            else:
                return hour + 12

        elif period_lower in ["night"]:
            # Night: 21-24 (9pm-12am)
            # Map: 7→19, 8→20, 9→21, 10→22, 11→23, 12→24
            if 1 <= hour <= 3:
                return hour + 21  # 1→22, 2→23, 3→24
            elif 7 <= hour <= 11:
                return hour + 12  # 7→19, 8→20, 9→21, 10→22, 11→23
            elif hour == 12:
                return 0  # midnight
            else:
                return hour + 12

        elif period_lower in ["noon", "midday"]:
            return 12

        elif period_lower in ["midnight"]:
            return 0

        # Default: return as is
        return hour

    def _apply_period_position_modifier(self, result, modifier):
        """
        Apply period position modifier (beginning/middle/end) to time range

        Args:
            result: Time range result [[start, end]]
            modifier: Position modifier string (beginning/start/early/end/late/middle/mid)

        Returns:
            Modified time range
        """
        if not result or not result[0] or len(result[0]) != 2:
            return result

        start_str, end_str = result[0]
        start_time = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
        end_time = datetime.fromisoformat(end_str.replace("Z", "+00:00"))

        # Calculate the duration
        duration = end_time - start_time

        if modifier in ["end", "late"]:
            # Last third or last month of the period
            if duration.days > 60:  # For year: November-December
                new_start = start_time.replace(
                    month=11, day=1, hour=0, minute=0, second=0, microsecond=0
                )
            elif duration.days > 20:  # For month: last 10 days
                new_start = start_time.replace(day=21, hour=0, minute=0, second=0, microsecond=0)
            else:  # For shorter periods: last third
                new_start = start_time + duration * 2 // 3
            return [[new_start.strftime("%Y-%m-%dT%H:%M:%SZ"), end_str]]

        elif modifier in ["beginning", "start", "early"]:
            # First third or first 10 days of the period
            if duration.days > 60:  # For year: January-February
                import calendar

                last_day_of_feb = calendar.monthrange(start_time.year, 2)[1]
                new_end = start_time.replace(
                    month=2,
                    day=last_day_of_feb,
                    hour=23,
                    minute=59,
                    second=59,
                    microsecond=0,
                )
            elif duration.days > 20:  # For month: first 10 days
                new_end = start_time.replace(day=10, hour=23, minute=59, second=59, microsecond=0)
            else:  # For shorter periods: first third
                new_end = start_time + duration // 3
            return [[start_str, new_end.strftime("%Y-%m-%dT%H:%M:%SZ")]]

        elif modifier in ["middle", "mid"]:
            # Middle third of the period
            third = duration // 3
            new_start = start_time + third
            new_end = end_time - third
            return [
                [
                    new_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    new_end.strftime("%Y-%m-%dT%H:%M:%SZ"),
                ]
            ]

        return result

    def _is_periodic_expression(self, tokens):
        """
        Check if the token sequence represents a periodic expression

        Args:
            tokens (list): List of tagged tokens

        Returns:
            bool: True if this is a periodic expression (should return empty result)
        """
        if not tokens:
            return False

        # Check for "every" + time expression patterns
        for i, token in enumerate(tokens):
            if token.get("type") == "token" and token.get("value", "").strip().lower() == "every":

                # Look for time-related tokens after "every"
                for j in range(i + 1, len(tokens)):
                    next_token = tokens[j]
                    if next_token.get("type") in [
                        "time_weekday",
                        "time_relative",
                        "time_utc",
                        "time_holiday",
                    ]:
                        return True
                    # Skip empty tokens
                    if (
                        next_token.get("type") == "token"
                        and next_token.get("value", "").strip() == ""
                    ):
                        continue
                    # If we hit a non-empty non-time token, stop looking
                    break

        return False

    def parse_tag_to_datetime(self, tokens: list, base_time="2025-01-21 08:00:00"):  # noqa: C901
        """
        Parse tagged tokens to datetime values

        Args:
            tokens (list): List of tagged tokens or tag string
            base_time (str): Base time reference in ISO format

        Returns:
            list: List of parsed datetime results
        """
        if isinstance(tokens, str):
            tokens = self._parse_tokens(tokens)

        # Check for periodic expressions (like "every monday", "every day", etc.)
        # These should return empty results as they represent frequency, not specific times
        # Check for periodic expressions (now handled by RecurringRule FST)
        # if self._is_periodic_expression(tokens):
        #     return []

        if not tokens:
            return []

        # Preprocess tokens: convert char tokens that should be time tokens
        tokens = self._preprocess_tokens(tokens)

        # Convert base_time string to datetime if needed
        if isinstance(base_time, str):
            if base_time.endswith("Z"):
                base_time = datetime.fromisoformat(base_time.replace("Z", "+00:00"))
            else:
                base_time = datetime.fromisoformat(base_time)

        results = []
        relation_offset = None  # Track relation offset from "day before/after"
        year_modifier = None  # Track year modifier from "last year's", etc.
        month_modifier = None  # Track month modifier from "last month's", etc.
        time_modifier = None  # Track general time modifier from "previous", "next", etc.
        last_weekday_result = None  # Track last weekday result for merging with time
        last_relative_result = None  # Track last relative result for merging with time
        last_period_info = None  # Track period info for merging with time (date, period_name)

        # Time range tracking for "from X to Y" patterns
        in_range = False  # Are we inside a "from...to" pattern?
        range_start_time = None  # Start time of the range
        range_start_token = None  # Start token (to re-parse if needed)
        range_start_base_time = None  # Base time used for start token
        waiting_for_to = False  # Are we waiting for "to" keyword?
        just_merged_range = False  # Just completed a range merge?
        range_start_token_for_modifier = None  # Save start token for applying later modifiers
        range_end_token_for_modifier = None  # Save end token for applying later modifiers

        # Time modifier keywords that can appear as char tokens
        TIME_MODIFIER_KEYWORDS = {
            "previous": -1,
            "last": -1,
            "this": 0,
            "current": 0,
            "next": 1,
            "following": 1,
            "upcoming": 1,
        }

        # Period modifiers (beginning/middle/end of time periods)
        period_position_modifier = None  # Track "beginning/end of" modifiers

        i = 0
        while i < len(tokens):
            token = tokens[i]
            # Handle case where token might be a list instead of dict
            if not isinstance(token, dict):
                # Skip non-dict tokens (should not happen, but handle gracefully)
                i += 1
                continue
            token_type = token.get("type", "")

            # Priority: Try context merger first for complex time expression merging
            merged = self.context_merger.try_merge(i, tokens, base_time)
            if merged is not None:
                merged_results, jump = merged
                # Special case: (None, 0) means skip this token (false positive detection)
                if merged_results is None and jump == 0:
                    i += 1
                    continue
                results.extend(merged_results)
                i += jump
                continue

            # Check if we just merged a range and this token is a modifier that should apply to it
            if just_merged_range and token_type == "time_relative" and results:
                # Apply this modifier to the last (just merged) range
                last_range = results.pop()
                # Re-parse both start and end with the new modifier
                if range_start_token_for_modifier and range_end_token_for_modifier:
                    # Calculate modified base time from the relative token
                    offset_day_str = token.get("offset_day", "").strip('"')
                    if offset_day_str:
                        try:
                            from datetime import timedelta

                            day_offset = int(offset_day_str)
                            modified_base_time = base_time + timedelta(days=day_offset)

                            # Re-parse both tokens
                            start_parser = self.parsers.get(
                                range_start_token_for_modifier.get("type")
                            )
                            end_parser = self.parsers.get(range_end_token_for_modifier.get("type"))

                            if start_parser and end_parser:
                                re_parsed_start = start_parser.parse(
                                    range_start_token_for_modifier, modified_base_time
                                )
                                re_parsed_end = end_parser.parse(
                                    range_end_token_for_modifier, modified_base_time
                                )

                                if re_parsed_start and re_parsed_end:
                                    start_time_str = re_parsed_start[0][0]
                                    end_time_str = (
                                        re_parsed_end[0][-1]
                                        if len(re_parsed_end[0]) > 1
                                        else re_parsed_end[0][0]
                                    )
                                    results.append([start_time_str, end_time_str])
                                else:
                                    results.append(last_range)  # Fallback
                            else:
                                results.append(last_range)  # Fallback
                        except Exception as e:
                            self.logger.debug(f"Error applying modifier to range: {e}")
                            pass
                            results.append(last_range)  # Fallback
                    else:
                        results.append(last_range)  # No offset, keep original
                else:
                    results.append(last_range)  # No tokens saved, keep original

                # Reset flags
                just_merged_range = False
                range_start_token_for_modifier = None
                range_end_token_for_modifier = None
                i += 1
                continue

            # Reset just_merged_range if we encounter a non-modifier token
            if just_merged_range and token_type != "time_relative":
                just_merged_range = False
                range_start_token_for_modifier = None
                range_end_token_for_modifier = None

            # Check if this is a char token that's actually a time modifier
            if token_type == "token":
                value = token.get("value", "").strip().lower()

                # Skip empty char tokens (artifacts from FST space handling)
                if not value:
                    i += 1
                    continue

                # Check for period position modifiers: "beginning/start/early/end/late of"
                if value in [
                    "beginning",
                    "start",
                    "early",
                    "end",
                    "late",
                    "middle",
                    "mid",
                ]:
                    # Look ahead for "of" keyword, skipping empty tokens
                    j = i + 1
                    while j < len(tokens) and not tokens[j].get("value", "").strip():
                        j += 1
                    if j < len(tokens) and tokens[j].get("value", "").strip().lower() == "of":
                        period_position_modifier = value
                        i = j + 1  # Skip to after "of"
                        continue

                # Check for "from" keyword - start of time range
                if value == "from" and not in_range:
                    in_range = True
                    waiting_for_to = True
                    i += 1
                    continue

                # Check for "to" keyword - middle of time range or start of implicit range
                if value == "to":
                    if waiting_for_to:
                        # We're in "from...to" pattern
                        waiting_for_to = False
                    elif not in_range and results:
                        # Only treat as time range if the previous token was a time token
                        # and the next token is likely to be a time token
                        prev_was_time = False
                        next_is_time = False

                        # Check if previous token was a time token
                        if i > 0:
                            prev_token = tokens[i - 1]
                            prev_was_time = prev_token.get("type", "").startswith("time_")

                        # Check if next token is likely to be a time token
                        if i + 1 < len(tokens):
                            next_token = tokens[i + 1]
                            next_is_time = next_token.get("type", "").startswith("time_")

                        # Only enter range mode if both conditions are met
                        if prev_was_time and next_is_time:
                            # Implicit range pattern "X to Y" (without "from")
                            in_range = True
                            waiting_for_to = False
                            # The last result is our range start
                            range_start_time = results.pop()  # Remove it from results
                            # Find the last time token before "to"
                            for j in range(i - 1, -1, -1):
                                if tokens[j].get("type", "").startswith("time_"):
                                    range_start_token = tokens[j].copy()
                                    range_start_base_time = base_time  # Assume base_time for now
                                    break
                    i += 1
                    continue

                if value in TIME_MODIFIER_KEYWORDS:
                    # This is a time modifier - save it and continue
                    time_modifier = TIME_MODIFIER_KEYWORDS[value]
                    i += 1
                    continue

            # Check if this is a composite_relative with relation
            if token_type == "time_composite_relative" and "relation" in token:
                # This is "day before/after" - save the offset and continue
                relation = token.get("relation", "").strip('"')
                try:
                    relation_offset = int(relation)
                except (ValueError, TypeError):
                    relation_offset = None
                i += 1
                continue

            # Check if this is a year/month modifier (possessive)
            if token_type == "time_composite_relative":
                # Parse the composite relative token directly
                parser = self.parsers.get(token_type)
                if parser:
                    result = parser.parse(token, base_time)

                    # Apply period position modifier if present
                    if result and period_position_modifier:
                        result = self._apply_period_position_modifier(
                            result, period_position_modifier
                        )
                        period_position_modifier = None  # Reset after use

                    if result:
                        results.extend(result)
                i += 1
                continue

            if "time_modifier" in token:
                # General time modifier (for holidays, events, etc.)
                modifier = token.get("time_modifier", "").strip('"')
                try:
                    time_modifier = int(modifier)

                    # Special case: "week after next/last" pattern
                    # Check if previous tokens are "week" + "after"
                    if i >= 2:
                        prev_token_1 = tokens[i - 1]
                        prev_token_2 = tokens[i - 2]
                        if (
                            prev_token_1.get("type") == "token"
                            and prev_token_1.get("value", "").lower() == "after"
                            and prev_token_2.get("type") == "token"
                            and prev_token_2.get("value", "").lower() == "week"
                        ):
                            # This is "week after next/last"
                            # Parse it as a week offset
                            # time_modifier=1 means "next", so "week after next" = next next week = offset_week=2
                            # time_modifier=-1 means "last", so "week after last" = last last week = offset_week=-2
                            week_offset = (
                                time_modifier + 1 if time_modifier > 0 else time_modifier - 1
                            )
                            week_token = {
                                "type": "time_weekday",
                                "offset_week": str(week_offset),
                            }
                            week_parser = self.parsers.get("time_weekday")
                            if week_parser:
                                week_result = week_parser.parse(week_token, base_time)
                                if week_result:
                                    results.extend(week_result)
                            time_modifier = None  # Reset
                            i += 1
                            continue
                except (ValueError, TypeError):
                    time_modifier = None
                i += 1
                continue

            # Skip fraction tokens (non-time tokens to prevent misrecognition)
            if token_type == "fraction":
                i += 1
                continue

            # Skip whitelist tokens (phrases that should not be parsed as time)
            if token_type == "whitelist":
                i += 1
                continue

            # Find appropriate parser for this token type
            parser = self.parsers.get(token_type)
            if parser:
                try:
                    # Check if this is a time_utc after a time_weekday or time_relative
                    # If so, merge them into a single time point
                    if token_type == "time_utc":
                        # Case 1: After a period (e.g., "tomorrow evening 8")
                        if last_period_info is not None:
                            base_date, period_name = last_period_info
                            # Adjust hour based on period
                            hour = int(token.get("hour", 0))

                            # Adjust hour based on period context
                            adjusted_hour = self._adjust_hour_by_period(hour, period_name)

                            # Handle 24:00 case (convert to next day 0:00)
                            if adjusted_hour == 24:
                                # Add one day to base_date and set hour to 0
                                from datetime import timedelta

                                adjusted_date = base_date + timedelta(days=1)
                                adjusted_hour = 0
                            else:
                                adjusted_date = base_date

                            # Create adjusted token
                            adjusted_token = token.copy()
                            adjusted_token["hour"] = str(adjusted_hour)

                            # Parse with adjusted hour and date
                            time_result = parser.parse(adjusted_token, adjusted_date)
                            if time_result:
                                results.pop()  # Remove the period result
                                results.extend(time_result)
                                last_period_info = None
                                i += 1
                                continue

                        # Case 2: After a weekday (e.g., "next monday at 4 pm")
                        elif last_weekday_result is not None:
                            # Get the weekday date (start of range)
                            weekday_date_str = last_weekday_result[0][0]
                            weekday_date = datetime.fromisoformat(
                                weekday_date_str.replace("Z", "+00:00")
                            )

                            # Parse the time from the utc token
                            time_result = parser.parse(token, weekday_date)
                            if time_result:
                                # Replace last weekday result with merged time
                                results.pop()  # Remove the weekday result
                                results.extend(time_result)
                                last_weekday_result = None
                                i += 1
                                continue

                        # Case 3: After a relative date (e.g., "tomorrow at 3 pm")
                        # Only merge if the relative token was the immediately previous time token
                        elif (
                            last_relative_result is not None
                            and self._should_merge_relative_with_utc(i, tokens)
                        ):
                            # Get the relative date (start of range)
                            relative_date_str = last_relative_result[0][0]
                            relative_date = datetime.fromisoformat(
                                relative_date_str.replace("Z", "+00:00")
                            )

                            # Parse the time from the utc token
                            time_result = parser.parse(token, relative_date)
                            if time_result:
                                # Replace last relative result with merged time
                                results.pop()  # Remove the relative result
                                results.extend(time_result)
                                last_relative_result = None
                                i += 1
                                continue

                    # Apply modifiers to base_time if needed
                    modified_base_time = base_time
                    if year_modifier is not None:
                        modified_base_time = modified_base_time.replace(
                            year=modified_base_time.year + year_modifier
                        )
                        year_modifier = None  # Reset after use
                    elif month_modifier is not None:
                        # Calculate new year and month
                        total_months = (
                            modified_base_time.year * 12 + modified_base_time.month + month_modifier
                        )
                        new_year = total_months // 12
                        new_month = total_months % 12
                        if new_month == 0:
                            new_month = 12
                            new_year -= 1
                        modified_base_time = modified_base_time.replace(
                            year=new_year, month=new_month
                        )
                        month_modifier = None  # Reset after use
                    elif time_modifier is not None:
                        # Apply general time modifier (for holidays, etc.)
                        # Add as a token attribute for the parser to handle
                        token["_time_offset"] = time_modifier
                        time_modifier = None  # Reset after use

                    # For holidays, if we have a relation_offset (from "day before/after"),
                    # convert it to day_prefix instead of applying it to the result range
                    if token_type == "time_holiday" and relation_offset is not None:
                        # Set day_prefix in token if not already set
                        if "day_prefix" not in token or not token.get("day_prefix"):
                            token["day_prefix"] = str(relation_offset)
                        relation_offset = None  # Reset after use

                    result = parser.parse(token, modified_base_time)

                    # Apply period position modifier if present
                    if result and period_position_modifier:
                        result = self._apply_period_position_modifier(
                            result, period_position_modifier
                        )
                        period_position_modifier = None  # Reset after use

                    if result:
                        # Apply relation offset if we have one
                        if relation_offset is not None:
                            # Add day offset to the result
                            from datetime import timedelta

                            offset_results = []
                            for time_range in result:
                                if isinstance(time_range, dict):
                                    # Skip intermediate results
                                    continue
                                if len(time_range) == 2:
                                    start = datetime.fromisoformat(
                                        time_range[0].replace("Z", "+00:00")
                                    )
                                    end = datetime.fromisoformat(
                                        time_range[1].replace("Z", "+00:00")
                                    )
                                    new_start = start + timedelta(days=relation_offset)
                                    new_end = end + timedelta(days=relation_offset)
                                    offset_results.append(
                                        [
                                            new_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                                            new_end.strftime("%Y-%m-%dT%H:%M:%SZ"),
                                        ]
                                    )
                            results.extend(offset_results)
                            relation_offset = None  # Reset after use
                        elif in_range:
                            # We're in a "from...to" range pattern
                            if waiting_for_to:
                                # This is the start time (after "from", before "to")
                                range_start_time = result[0] if result else None
                                range_start_token = token.copy()  # Save the original token
                                range_start_base_time = (
                                    modified_base_time  # Save the base time used
                                )
                            else:
                                # This is the end time (after "to")
                                if range_start_time and result:
                                    # Check if we need to re-parse the start time with the same modifier
                                    # This happens when the end time has a modifier
                                    needs_reparse = False
                                    reparse_base_time = modified_base_time

                                    # Check 1: modified_base_time changed
                                    if (
                                        modified_base_time != base_time
                                        and range_start_base_time == base_time
                                    ):
                                        needs_reparse = True

                                    # Check 2: end token has offset fields (offset_year, offset_month, offset_day)
                                    # These indicate time modifiers that should apply to the whole range
                                    # BUT: don't reparse if start token has is_tonight marker (it's already correct)
                                    if (
                                        token.get("offset_year")
                                        or token.get("offset_month")
                                        or token.get("offset_day")
                                    ) and not range_start_token.get("is_tonight"):
                                        needs_reparse = True
                                        # If token has offsets but modified_base_time wasn't changed (for composite_relative),
                                        # we need to manually calculate the base time
                                        if modified_base_time == base_time:
                                            reparse_base_time = base_time
                                            if "offset_year" in token:
                                                try:
                                                    year_offset = int(
                                                        token["offset_year"].strip('"')
                                                    )
                                                    reparse_base_time = reparse_base_time.replace(
                                                        year=reparse_base_time.year + year_offset
                                                    )
                                                except (
                                                    ValueError,
                                                    TypeError,
                                                    AttributeError,
                                                ):
                                                    pass
                                            if "offset_month" in token:
                                                try:
                                                    month_offset = int(
                                                        token["offset_month"].strip('"')
                                                    )
                                                    total_months = (
                                                        reparse_base_time.year * 12
                                                        + reparse_base_time.month
                                                        + month_offset
                                                    )
                                                    new_year = total_months // 12
                                                    new_month = total_months % 12
                                                    if new_month == 0:
                                                        new_month = 12
                                                        new_year -= 1
                                                    reparse_base_time = reparse_base_time.replace(
                                                        year=new_year,
                                                        month=new_month,
                                                    )
                                                except (
                                                    ValueError,
                                                    TypeError,
                                                    AttributeError,
                                                ):
                                                    pass
                                            if "offset_day" in token:
                                                try:
                                                    from datetime import timedelta

                                                    day_offset = int(token["offset_day"].strip('"'))
                                                    reparse_base_time = (
                                                        reparse_base_time
                                                        + timedelta(days=day_offset)
                                                    )
                                                except (
                                                    ValueError,
                                                    TypeError,
                                                    AttributeError,
                                                ):
                                                    pass

                                    if needs_reparse:
                                        # Re-parse the start token with the modified base time
                                        try:
                                            start_parser = self.parsers.get(
                                                range_start_token.get("type")
                                            )
                                            if start_parser:
                                                re_parsed_start = start_parser.parse(
                                                    range_start_token, reparse_base_time
                                                )
                                                if re_parsed_start:
                                                    range_start_time = re_parsed_start[0]
                                        except Exception as e:
                                            self.logger.debug(f"Error re-parsing start token: {e}")
                                            pass

                                    # Merge the range: take start of range_start_time and end of result
                                    start_time_str = range_start_time[
                                        0
                                    ]  # First element of start range
                                    end_time_str = (
                                        result[0][-1] if len(result[0]) > 1 else result[0][0]
                                    )  # Last element of end range
                                    results.append([start_time_str, end_time_str])

                                    # Set flag for potential modifier application
                                    just_merged_range = True
                                    range_start_token_for_modifier = (
                                        range_start_token.copy() if range_start_token else None
                                    )
                                    range_end_token_for_modifier = token.copy()

                                    # Reset range tracking
                                    in_range = False
                                    range_start_time = None
                                    range_start_token = None
                                    range_start_base_time = None
                                    waiting_for_to = False
                                else:
                                    # Fallback: just add the result
                                    results.extend(result)
                        else:
                            results.extend(result)
                            # Track weekday, relative, and period results for potential merging with time
                            if token_type == "time_weekday":
                                last_weekday_result = result
                                # Check if weekday has period info
                                if "period" in token and result:
                                    date_str = result[0][0]
                                    date_obj = datetime.fromisoformat(
                                        date_str.replace("Z", "+00:00")
                                    )
                                    period_name = token.get("period", "").strip('"')
                                    last_period_info = (date_obj, period_name)
                            elif token_type == "time_relative":
                                last_relative_result = result
                                # Check if relative has period info
                                if "period" in token and result:
                                    date_str = result[0][0]
                                    date_obj = datetime.fromisoformat(
                                        date_str.replace("Z", "+00:00")
                                    )
                                    period_name = token.get("period", "").strip('"')
                                    last_period_info = (date_obj, period_name)
                except Exception as e:
                    self.logger.debug(f"Error parsing token {token_type}: {e}")
                    pass
            else:
                # Skip logging for known non-time token types that don't require parsing
                # 'token' and 'time_connector' are expected non-time tokens
                # 'list' might be a false positive from FST output (e.g., "list { value: ... }")
                # Skip logging for these to reduce noise
                skip_types = ["token", "time_connector", "list", "char"]
                if token_type not in skip_types:
                    self.logger.debug(f"No parser found for token type: {token_type}")
                    pass

            i += 1

        # Handle incomplete range (e.g., "from last week" without "to")
        # If we're still waiting for "to" at the end, add the range_start_time to results
        if in_range and waiting_for_to and range_start_time is not None:
            results.append(range_start_time)

        return results

    def _should_merge_relative_with_utc(self, utc_token_index, tokens):
        """
        Check if a time_utc token should be merged with the previous time_relative token.
        Only merge if they are close enough (no significant content in between).

        Args:
            utc_token_index (int): Index of the time_utc token
            tokens (list): List of all tokens

        Returns:
            bool: True if should merge, False otherwise
        """
        # Look backwards for the most recent time_relative token
        for i in range(utc_token_index - 1, -1, -1):
            token = tokens[i]
            if token.get("type") == "time_relative":
                # Found the time_relative token
                # Check if there are only empty tokens or simple connectors between them
                gap_tokens = tokens[i + 1 : utc_token_index]

                # Count non-empty, non-connector tokens
                significant_tokens = 0
                for gap_token in gap_tokens:
                    if gap_token.get("type") == "token":
                        value = gap_token.get("value", "").strip().lower()
                        # Skip empty tokens and simple connectors
                        if value and value not in [
                            "at",
                            "on",
                            "in",
                            "of",
                            "the",
                            "a",
                            "an",
                            "is",
                            "was",
                            "will",
                            "be",
                        ]:
                            significant_tokens += 1
                    elif gap_token.get("type", "").startswith("time_"):
                        # If there's another time token in between, don't merge
                        return False

                # Only merge if there are no significant tokens in between
                return significant_tokens == 0

            elif token.get("type", "").startswith("time_"):
                # Found another time token before the relative, don't merge
                return False

        return False

    def parse_single_expression(
        self, expression: str, base_time="2025-01-21 08:00:00"
    ):  # noqa: C901
        """
        Parse a single time expression

        Args:
            expression (str): Time expression text
            base_time (str): Base time reference

        Returns:
            list: Parsed datetime results
        """
        # This would typically be used with FST tagging first
        # For now, we'll try to identify the expression type manually

        expression = expression.lower().strip()

        # Convert base_time string to datetime if needed
        if isinstance(base_time, str):
            if base_time.endswith("Z"):
                base_time = datetime.fromisoformat(base_time.replace("Z", "+00:00"))
            else:
                base_time = datetime.fromisoformat(base_time)

        # Create a simple token based on common patterns
        token = {"type": "", "text": expression}

        # Try to identify token type based on keywords
        if any(word in expression for word in ["tomorrow", "yesterday", "today", "next", "last"]):
            token["type"] = "time_relative"
            token["relative"] = expression
        elif any(
            word in expression
            for word in [
                "monday",
                "tuesday",
                "wednesday",
                "thursday",
                "friday",
                "saturday",
                "sunday",
            ]
        ):
            token["type"] = "time_weekday"
            # Extract weekday and direction
            words = expression.split()
            for word in words:
                if word in [
                    "monday",
                    "tuesday",
                    "wednesday",
                    "thursday",
                    "friday",
                    "saturday",
                    "sunday",
                ]:
                    token["weekday"] = word
                if word in ["next", "last", "this"]:
                    token["direction"] = word
        elif any(
            word in expression for word in ["morning", "afternoon", "evening", "night", "noon"]
        ):
            token["type"] = "time_period"
            token["period"] = expression
        elif any(
            word in expression for word in ["christmas", "easter", "thanksgiving", "halloween"]
        ):
            token["type"] = "time_holiday"
            token["holiday"] = expression
        elif "ago" in expression or expression.startswith("in "):
            token["type"] = "time_delta"
            # Parse delta components
            words = expression.split()
            if expression.startswith("in "):
                token["direction"] = "in"
                token["amount"] = words[1] if len(words) > 1 else "1"
                token["unit"] = words[2] if len(words) > 2 else "day"
            elif "ago" in expression:
                token["direction"] = "ago"
                token["amount"] = words[0] if words else "1"
                token["unit"] = words[1] if len(words) > 1 else "day"

        # Try to parse with appropriate parser
        if token["type"] and token["type"] in self.parsers:
            parser = self.parsers[token["type"]]
            try:
                return parser.parse(token, base_time)
            except Exception as e:
                self.logger.debug(f"Error parsing expression '{expression}': {e}")
                pass
                return []

        return []
