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
    parse_datetime_str,
    format_datetime_str,
    create_day_range,
    get_parser_and_parse,
)


class PeriodMerger:
    """Merger for handling period-related time expressions"""

    def __init__(self, parsers, time_expression_merger=None):
        """
        Initialize period merger

        Args:
            parsers (dict): Dictionary containing various time parsers
            time_expression_merger: Reference to TimeExpressionMerger for accessing period methods
        """
        self.parsers = parsers
        self.logger = get_logger(__name__)
        self.time_expression_merger = time_expression_merger

    def merge_period_with_date(self, period_token, date_token, base_time):  # noqa: C901
        """
        Merge time_period with date/holiday/weekday
        Example: "morning of christmas day" -> christmas morning
        """
        try:
            period = period_token.get("noon", "").strip('"')

            # Parse date_token to get target date
            target_date = None

            if date_token.get("type") == "time_utc":
                # time_utc with month/day
                if "month" in date_token and "day" in date_token:
                    month_name = date_token.get("month", "").strip('"')
                    day = int(date_token.get("day", "1"))
                    month_num = month_name_to_number(month_name)
                    if month_num:
                        target_date = base_time.replace(
                            month=month_num,
                            day=day,
                            hour=0,
                            minute=0,
                            second=0,
                            microsecond=0,
                        )
                elif "year" in date_token:
                    year = int(date_token.get("year", "").strip('"'))
                    target_date = base_time.replace(
                        year=year,
                        month=1,
                        day=1,
                        hour=0,
                        minute=0,
                        second=0,
                        microsecond=0,
                    )

            elif date_token.get("type") == "time_holiday":
                # Parse holiday to get date
                holiday_parser = self.parsers.get("time_holiday")
                if holiday_parser:
                    holiday_result = holiday_parser.parse(date_token, base_time)
                    if holiday_result and len(holiday_result) > 0:
                        # Extract date from holiday result
                        holiday_time_str = holiday_result[0][0]  # Start time
                        from datetime import datetime

                        target_date = parse_datetime_str(holiday_time_str).replace(tzinfo=None)

            elif date_token.get("type") == "time_weekday":
                # Parse weekday to get date
                weekday_parser = self.parsers.get("time_weekday")
                if weekday_parser:
                    weekday_result = weekday_parser.parse(date_token, base_time)
                    if weekday_result and len(weekday_result) > 0:
                        # Extract date from weekday result
                        weekday_time_str = weekday_result[0][0]  # Start time
                        from datetime import datetime

                        target_date = parse_datetime_str(weekday_time_str).replace(tzinfo=None)

            if not target_date:
                return None

            # Apply period to that date
            if self.time_expression_merger:
                return self.time_expression_merger.apply_period_to_date(period, target_date)
            return None

        except Exception as e:
            self.logger.debug(f"Error in merge_period_with_date: {e}")
            return None

    def apply_period_modifier(self, period, modifier):  # noqa: C901
        """
        Apply modifier (early/late) to period
        Example: "early morning" -> 06:00-09:00 instead of 06:00-12:00
        """
        try:
            if modifier == "early":
                if period == "morning":
                    return (6, 0), (9, 0)  # 06:00-09:00
                elif period == "afternoon":
                    return (12, 0), (15, 0)  # 12:00-15:00
                elif period == "evening":
                    return (18, 0), (19, 30)  # 18:00-19:30
                elif period == "night":
                    return (21, 0), (22, 30)  # 21:00-22:30
            elif modifier == "late":
                if period == "morning":
                    return (9, 0), (12, 0)  # 09:00-12:00
                elif period == "afternoon":
                    return (15, 0), (18, 0)  # 15:00-18:00
                elif period == "evening":
                    return (19, 30), (21, 0)  # 19:30-21:00
                elif period == "night":
                    return (22, 30), (23, 59)  # 22:30-23:59

            # Default period ranges
            if period == "morning":
                return (6, 0), (12, 0)  # 06:00-12:00
            elif period == "afternoon":
                return (12, 0), (18, 0)  # 12:00-18:00
            elif period == "evening":
                return (18, 0), (21, 0)  # 18:00-21:00
            elif period == "night":
                return (21, 0), (23, 59)  # 21:00-23:59

            return None

        except Exception as e:
            self.logger.debug(f"Error in apply_period_modifier: {e}")
            return None

    def try_merge_period_of_year(self, i, tokens, base_time):  # noqa: C901
        """
        Merge token(end/beginning) + of + token(4-digit year)
        Example: "end of 2012" -> Nov-Dec 2012

        Args:
            i (int): Current token index
            tokens (list): List of tokens
            base_time (datetime): Base time reference

        Returns:
            tuple: (merged_results_list, jump_count) or None
        """
        try:
            n = len(tokens)
            if i + 2 >= n:
                return None

            cur = tokens[i]
            if cur.get("type") != "token":
                return None

            period_word = cur.get("value", "").lower()
            if period_word not in ["end", "beginning", "start"]:
                return None

            # Look for "of" token
            j = i + 1
            while (
                j < n
                and tokens[j].get("type") == "token"
                and tokens[j].get("value", "").strip() == ""
            ):
                j += 1

            if j >= n:
                return None

            of_token = tokens[j]
            if of_token.get("type") != "token" or of_token.get("value", "").lower() != "of":
                return None

            # Look for year token
            k = j + 1
            while (
                k < n
                and tokens[k].get("type") == "token"
                and tokens[k].get("value", "").strip() == ""
            ):
                k += 1

            if k >= n:
                return None

            year_token = tokens[k]
            if year_token.get("type") != "token":
                return None

            year_str = year_token.get("value", "").strip()
            if not (year_str.isdigit() and len(year_str) == 4):
                return None

            year = int(year_str)
            if not (1900 <= year <= 2099):
                return None

            # Calculate time range based on period
            from datetime import datetime

            if period_word in ["end"]:
                # End of year: November - December
                start_time = datetime(year, 11, 1, 0, 0, 0)
                end_time = datetime(year, 12, 31, 23, 59, 59)
            else:  # beginning or start
                # Beginning of year: January - February
                start_time = datetime(year, 1, 1, 0, 0, 0)
                end_time = datetime(year, 2, 28, 23, 59, 59)
                # Handle leap year
                if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0):
                    end_time = datetime(year, 2, 29, 23, 59, 59)

            result = [
                [
                    format_datetime_str(start_time),
                    format_datetime_str(end_time),
                ]
            ]

            return (result, k + 1)

        except Exception as e:
            self.logger.debug(f"Error in try_merge_period_of_year: {e}")
            return None

    def merge_weekday_period_with_month(self, weekday_token, month_token, base_time):
        """
        Merge time_weekday(week_period) with time_utc(month)
        Example: "last weekend of October" -> find last weekend in October
        """
        try:
            week_period = weekday_token.get("week_period", "").strip('"')
            offset_week = int(weekday_token.get("offset_week", 0))
            month_name = month_token.get("month", "").strip('"')

            # Map month name to number
            month_map = {
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

            month_num = month_map.get(month_name.lower())
            if not month_num:
                return None

            # Determine target year
            target_year = base_time.year
            if month_num < base_time.month:
                target_year += 1

            from datetime import datetime, timedelta
            import calendar

            if week_period == "weekend":
                # Find weekend (Saturday-Sunday) in the month
                if offset_week == -1:  # last weekend
                    # Find the last Saturday of the month
                    last_day = calendar.monthrange(target_year, month_num)[1]
                    last_date = datetime(target_year, month_num, last_day)

                    # Find the last Saturday
                    days_back = (last_date.weekday() - 5) % 7  # Saturday is 5
                    if days_back == 0 and last_date.weekday() != 5:
                        days_back = 7
                    last_saturday = last_date - timedelta(days=days_back)

                    # Weekend is Saturday to Sunday
                    saturday_start, _ = create_day_range(last_saturday)
                    _, sunday_end = create_day_range(last_saturday + timedelta(days=1))

                    return [
                        [
                            format_datetime_str(saturday_start),
                            format_datetime_str(sunday_end),
                        ]
                    ]
                else:  # first weekend
                    # Find the first Saturday of the month
                    first_date = datetime(target_year, month_num, 1)
                    days_forward = (5 - first_date.weekday()) % 7  # Saturday is 5
                    if days_forward == 0 and first_date.weekday() != 5:
                        days_forward = 7
                    first_saturday = first_date + timedelta(days=days_forward)

                    # Weekend is Saturday to Sunday
                    saturday_start, _ = create_day_range(first_saturday)
                    _, sunday_end = create_day_range(first_saturday + timedelta(days=1))

                    return [
                        [
                            format_datetime_str(saturday_start),
                            format_datetime_str(sunday_end),
                        ]
                    ]

            return None

        except Exception as e:
            self.logger.debug(f"Error in merge_weekday_period_with_month: {e}")
            return None
