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
from typing import Optional, Tuple, List, Dict, Any


def easter_day(year):
    """
    Calculate Easter Sunday using the Computus algorithm (Anonymous Gregorian algorithm)

    Args:
        year (int): Year

    Returns:
        list: [month, day]
    """
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    ell = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * ell) // 451
    month = (h + ell - 7 * m + 114) // 31
    day = ((h + ell - 7 * m + 114) % 31) + 1
    return [int(month), int(day)]


def good_friday(year):
    """
    Calculate Good Friday (2 days before Easter)

    Args:
        year (int): Year

    Returns:
        list: [month, day]
    """
    easter_month, easter_day_num = easter_day(year)
    easter_date = datetime(year, easter_month, easter_day_num)
    good_friday_date = easter_date - timedelta(days=2)
    return [int(good_friday_date.month), int(good_friday_date.day)]


def fathers_day(year):
    """
    Calculate Father's Day (3rd Sunday in June for US)

    Args:
        year (int): Year

    Returns:
        list: [month, day]
    """
    # Find what day of week June 1st is (0=Monday, 6=Sunday)
    first_june = datetime(year, 6, 1)
    weekday = first_june.weekday()  # Monday is 0 and Sunday is 6

    # Calculate offset to reach the 3rd Sunday
    # If June 1 is Sunday, offset is 14; otherwise offset is (6 - weekday + 7) % 7 + 14
    offset = (6 - weekday + 7) % 7 + 14
    fathers_day_date = first_june + timedelta(days=offset)
    return [int(fathers_day_date.month), int(fathers_day_date.day)]


def mothers_day(year):
    """
    Calculate Mother's Day (2nd Sunday in May for US)

    Args:
        year (int): Year

    Returns:
        list: [month, day]
    """
    # Find what day of week May 1st is (0=Monday, 6=Sunday)
    first_may = datetime(year, 5, 1)
    weekday = first_may.weekday()  # Monday is 0 and Sunday is 6

    # Calculate offset to reach the 2nd Sunday
    # If May 1 is Sunday, offset is 7; otherwise offset is (6 - weekday + 7) % 7 + 7
    offset = (6 - weekday + 7) % 7 + 7
    mothers_day_date = first_may + timedelta(days=offset)
    return [int(mothers_day_date.month), int(mothers_day_date.day)]


def thanksgiving_day(year):
    """
    Calculate Thanksgiving Day (4th Thursday in November for US)

    Args:
        year (int): Year

    Returns:
        list: [month, day]
    """
    # Find what day of week November 1st is (0=Monday, 6=Sunday)
    first_nov = datetime(year, 11, 1)
    weekday = first_nov.weekday()  # Monday is 0 and Sunday is 6

    # Calculate offset to reach the 4th Thursday (Thursday is weekday 3)
    # If November 1 is Thursday, offset is 21; otherwise offset is (3 - weekday + 7) % 7 + 21
    offset = (3 - weekday + 7) % 7 + 21
    thanksgiving_date = first_nov + timedelta(days=offset)
    return [int(thanksgiving_date.month), int(thanksgiving_date.day)]


def memorial_day(year):
    """
    Calculate Memorial Day (last Monday in May for US)

    Args:
        year (int): Year

    Returns:
        list: [month, day]
    """
    # Start with May 31st and work backwards to find the last Monday
    last_may = datetime(year, 5, 31)
    weekday = last_may.weekday()  # Monday is 0 and Sunday is 6

    # Calculate how many days to go back to reach Monday
    days_back = (weekday - 0) % 7
    memorial_date = last_may - timedelta(days=days_back)
    return [int(memorial_date.month), int(memorial_date.day)]


def labor_day(year):
    """
    Calculate Labor Day (1st Monday in September for US)

    Args:
        year (int): Year

    Returns:
        list: [month, day]
    """
    # Find what day of week September 1st is
    first_sept = datetime(year, 9, 1)
    weekday = first_sept.weekday()  # Monday is 0 and Sunday is 6

    # Calculate offset to reach the 1st Monday
    # If September 1 is Monday, offset is 0; otherwise offset is (0 - weekday + 7) % 7
    offset = (0 - weekday + 7) % 7
    labor_day_date = first_sept + timedelta(days=offset)
    return [int(labor_day_date.month), int(labor_day_date.day)]


def mlk_day(year):
    """
    Calculate Martin Luther King Jr. Day (3rd Monday in January for US)

    Args:
        year (int): Year

    Returns:
        list: [month, day]
    """
    # Find what day of week January 1st is
    first_jan = datetime(year, 1, 1)
    weekday = first_jan.weekday()  # Monday is 0 and Sunday is 6

    # Calculate offset to reach the 3rd Monday
    # If January 1 is Monday, offset is 14; otherwise offset is (0 - weekday + 7) % 7 + 14
    offset = (0 - weekday + 7) % 7 + 14
    mlk_date = first_jan + timedelta(days=offset)
    return [int(mlk_date.month), int(mlk_date.day)]


def presidents_day(year):
    """
    Calculate Presidents' Day (3rd Monday in February for US)

    Args:
        year (int): Year

    Returns:
        list: [month, day]
    """
    # Find what day of week February 1st is
    first_feb = datetime(year, 2, 1)
    weekday = first_feb.weekday()  # Monday is 0 and Sunday is 6

    # Calculate offset to reach the 3rd Monday
    # If February 1 is Monday, offset is 14; otherwise offset is (0 - weekday + 7) % 7 + 14
    offset = (0 - weekday + 7) % 7 + 14
    presidents_date = first_feb + timedelta(days=offset)
    return [int(presidents_date.month), int(presidents_date.day)]


def black_friday(year):
    """
    Calculate Black Friday (day after Thanksgiving)

    Args:
        year (int): Year

    Returns:
        list: [month, day]
    """
    thanksgiving_month, thanksgiving_day_num = thanksgiving_day(year)
    thanksgiving_date = datetime(year, thanksgiving_month, thanksgiving_day_num)
    black_friday_date = thanksgiving_date + timedelta(days=1)
    return [int(black_friday_date.month), int(black_friday_date.day)]


def boss_day(year):
    """
    Calculate Boss's Day (October 16th, or closest weekday if it falls on weekend)

    Args:
        year (int): Year

    Returns:
        list: [month, day]
    """
    boss_date = datetime(year, 10, 16)
    weekday = boss_date.weekday()  # Monday is 0 and Sunday is 6

    # If it's Saturday (5), move to Friday (15th)
    # If it's Sunday (6), move to Monday (17th)
    if weekday == 5:  # Saturday
        boss_date = boss_date - timedelta(days=1)
    elif weekday == 6:  # Sunday
        boss_date = boss_date + timedelta(days=1)

    return [int(boss_date.month), int(boss_date.day)]


def easter_monday(year):
    """
    Calculate Easter Monday (day after Easter)

    Args:
        year (int): Year

    Returns:
        list: [month, day]
    """
    easter_month, easter_day_num = easter_day(year)
    easter_date = datetime(year, easter_month, easter_day_num)
    easter_monday_date = easter_date + timedelta(days=1)
    return [int(easter_monday_date.month), int(easter_monday_date.day)]


def maundy_thursday(year):
    """
    Calculate Maundy Thursday (3 days before Easter)

    Args:
        year (int): Year

    Returns:
        list: [month, day]
    """
    easter_month, easter_day_num = easter_day(year)
    easter_date = datetime(year, easter_month, easter_day_num)
    maundy_thursday_date = easter_date - timedelta(days=3)
    return [int(maundy_thursday_date.month), int(maundy_thursday_date.day)]


def pentecost(year):
    """
    Calculate Pentecost (49 days after Easter)

    Args:
        year (int): Year

    Returns:
        list: [month, day]
    """
    easter_month, easter_day_num = easter_day(year)
    easter_date = datetime(year, easter_month, easter_day_num)
    pentecost_date = easter_date + timedelta(days=49)
    return [int(pentecost_date.month), int(pentecost_date.day)]


def whit_monday(year):
    """
    Calculate Whit Monday (50 days after Easter)

    Args:
        year (int): Year

    Returns:
        list: [month, day]
    """
    easter_month, easter_day_num = easter_day(year)
    easter_date = datetime(year, easter_month, easter_day_num)
    whit_monday_date = easter_date + timedelta(days=50)
    return [int(whit_monday_date.month), int(whit_monday_date.day)]


def palm_sunday(year):
    """
    Calculate Palm Sunday (7 days before Easter)

    Args:
        year (int): Year

    Returns:
        list: [month, day]
    """
    easter_month, easter_day_num = easter_day(year)
    easter_date = datetime(year, easter_month, easter_day_num)
    palm_sunday_date = easter_date - timedelta(days=7)
    return [int(palm_sunday_date.month), int(palm_sunday_date.day)]


def trinity_sunday(year):
    """
    Calculate Trinity Sunday (56 days after Easter)

    Args:
        year (int): Year

    Returns:
        list: [month, day]
    """
    easter_month, easter_day_num = easter_day(year)
    easter_date = datetime(year, easter_month, easter_day_num)
    trinity_sunday_date = easter_date + timedelta(days=56)
    return [int(trinity_sunday_date.month), int(trinity_sunday_date.day)]


def shrove_tuesday(year):
    """
    Calculate Shrove Tuesday (47 days before Easter)

    Args:
        year (int): Year

    Returns:
        list: [month, day]
    """
    easter_month, easter_day_num = easter_day(year)
    easter_date = datetime(year, easter_month, easter_day_num)
    shrove_tuesday_date = easter_date - timedelta(days=47)
    return [int(shrove_tuesday_date.month), int(shrove_tuesday_date.day)]


def orthodox_easter(year):
    """
    Calculate Orthodox Easter using Julian calendar algorithm

    Args:
        year (int): Year

    Returns:
        list: [month, day]
    """
    # Julian Easter calculation (Meeus algorithm)
    a = year % 4
    b = year % 7
    c = year % 19
    d = (19 * c + 15) % 30
    e = (2 * a + 4 * b - d + 34) % 7
    month = (d + e + 114) // 31
    day = ((d + e + 114) % 31) + 1

    # Convert to Gregorian calendar (add 13 days for 20th-21st century)
    orthodox_date = datetime(year, int(month), int(day))
    gregorian_date = orthodox_date + timedelta(days=13)

    return [int(gregorian_date.month), int(gregorian_date.day)]


def orthodox_good_friday(year):
    """
    Calculate Orthodox Good Friday (2 days before Orthodox Easter)

    Args:
        year (int): Year

    Returns:
        list: [month, day]
    """
    orthodox_month, orthodox_day = orthodox_easter(year)
    orthodox_date = datetime(year, orthodox_month, orthodox_day)
    orthodox_good_friday_date = orthodox_date - timedelta(days=2)
    return [int(orthodox_good_friday_date.month), int(orthodox_good_friday_date.day)]


def clean_monday(year):
    """
    Calculate Clean Monday (48 days before Orthodox Easter)

    Args:
        year (int): Year

    Returns:
        list: [month, day]
    """
    orthodox_month, orthodox_day = orthodox_easter(year)
    orthodox_date = datetime(year, orthodox_month, orthodox_day)
    clean_monday_date = orthodox_date - timedelta(days=48)
    return [int(clean_monday_date.month), int(clean_monday_date.day)]


def lazarus_saturday(year):
    """
    Calculate Lazarus Saturday (8 days before Orthodox Easter)

    Args:
        year (int): Year

    Returns:
        list: [month, day]
    """
    orthodox_month, orthodox_day = orthodox_easter(year)
    orthodox_date = datetime(year, orthodox_month, orthodox_day)
    lazarus_saturday_date = orthodox_date - timedelta(days=8)
    return [int(lazarus_saturday_date.month), int(lazarus_saturday_date.day)]


def great_fast(year):
    """
    Calculate Great Fast period
    From Clean Monday to Great Saturday (1 day before Orthodox Easter)

    Args:
        year (int): Year

    Returns:
        tuple: (start_date, end_date) as (month, day) tuples
    """
    orthodox_month, orthodox_day = orthodox_easter(year)
    orthodox_date = datetime(year, orthodox_month, orthodox_day)

    # Great Fast starts on Clean Monday (48 days before Orthodox Easter)
    start_date = orthodox_date - timedelta(days=48)
    # Great Fast ends on Great Saturday (1 day before Orthodox Easter)
    end_date = orthodox_date - timedelta(days=1)

    return (
        [int(start_date.month), int(start_date.day)],
        [int(end_date.month), int(end_date.day)],
    )


# Token processing utility functions
def skip_empty_tokens(tokens, start_idx):
    """Skip empty tokens and return next non-empty token index"""
    n = len(tokens)
    idx = start_idx
    while idx < n and tokens[idx].get("type") == "token" and tokens[idx].get("value", "") == "":
        idx += 1
    return idx


def skip_the_token(tokens, start_idx):
    """Skip 'the' token if present"""
    if start_idx >= len(tokens):
        return start_idx

    if (
        tokens[start_idx].get("type") == "token"
        and tokens[start_idx].get("value", "").lower() == "the"
    ):
        # Skip "the" and any following empty tokens
        return skip_empty_tokens(tokens, start_idx + 1)

    return start_idx


def is_digit_sequence(tokens, start_idx):
    """Check if starting from start_idx, we have a sequence of digit tokens"""
    if start_idx >= len(tokens):
        return False

    token = tokens[start_idx]
    if token.get("type") == "time_utc" and "day" in token:
        return True

    # Check for digit tokens (may be split like '1', '3' for 13)
    if token.get("type") == "token" and token.get("value", "").isdigit():
        return True

    return False


def extract_day_value_from_tokens(tokens, start_idx):  # noqa: C901
    """Extract day value from potentially split number tokens"""
    import re

    if start_idx >= len(tokens):
        return None, start_idx

    token = tokens[start_idx]

    # If it's already a time_utc with day, extract it
    if token.get("type") == "time_utc" and "day" in token:
        day_str = token.get("day", "").strip('"')
        day_match = re.match(r"(\d+)", day_str)
        if day_match:
            return int(day_match.group(1)), start_idx + 1

    # If it's a token, check if it's a digit
    if token.get("type") == "token":
        value = token.get("value", "").strip()
        if value.isdigit():
            # Check if next token is also a digit (number was split)
            num_str = value
            next_idx = start_idx + 1
            while next_idx < len(tokens):
                next_token = tokens[next_idx]
                if next_token.get("type") == "token":
                    next_value = next_token.get("value", "").strip()
                    if next_value.isdigit():
                        num_str += next_value
                        next_idx += 1
                    else:
                        break
                else:
                    break

            try:
                return int(num_str), next_idx
            except ValueError:
                pass

    return None, start_idx


def extract_day_value(token):
    """Extract day value from token (handles both time_utc and token types)"""
    import re

    if token.get("type") == "time_utc" and "day" in token:
        try:
            day_str = token.get("day", "").strip('"')
            # Remove ordinal suffixes (st, nd, rd, th)
            day_match = re.match(r"(\d+)", day_str)
            if day_match:
                return int(day_match.group(1))
        except (ValueError, TypeError):
            pass
    elif token.get("type") == "token":
        try:
            value = token.get("value", "").strip()
            if value.isdigit():
                return int(value)
        except (ValueError, TypeError):
            pass
    return None


def get_month_range(base_time, month=None):
    """
    Get start and end time of a month

    Args:
        base_time (datetime): Base time reference
        month (int, optional): Specified month, if None use base_time's month

    Returns:
        tuple: (start_of_month, end_of_month)
    """
    if month is not None:
        base_time = base_time.replace(month=month)

    # Calculate last day of month
    if base_time.month in [1, 3, 5, 7, 8, 10, 12]:
        end_day = 31
    elif base_time.month in [4, 6, 9, 11]:
        end_day = 30
    elif base_time.year % 4 == 0:
        if base_time.year % 100 != 0 or base_time.year % 400 == 0:
            end_day = 29
        else:
            end_day = 28
    else:
        end_day = 28

    start_of_month = base_time.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    end_of_month = base_time.replace(day=end_day, hour=23, minute=59, second=59, microsecond=0)
    return start_of_month, end_of_month


def month_name_to_number(month_name):
    """Convert month name to number"""
    month_map = {
        "january": 1,
        "jan": 1,
        "february": 2,
        "feb": 2,
        "march": 3,
        "mar": 3,
        "april": 4,
        "apr": 4,
        "may": 5,
        "june": 6,
        "jun": 6,
        "july": 7,
        "jul": 7,
        "august": 8,
        "aug": 8,
        "september": 9,
        "sep": 9,
        "sept": 9,
        "october": 10,
        "oct": 10,
        "november": 11,
        "nov": 11,
        "december": 12,
        "dec": 12,
    }
    return month_map.get(month_name.lower())


# ============================================================================
# Date/Time String Processing Functions
# ============================================================================


def parse_datetime_str(date_str: str) -> datetime:
    """
    Parse ISO format datetime string (handles Z timezone)

    Args:
        date_str: ISO format datetime string (e.g., "2023-02-12T09:00:00Z")

    Returns:
        datetime: Parsed datetime object
    """
    return datetime.fromisoformat(date_str.replace("Z", "+00:00"))


def format_datetime_str(dt: datetime) -> str:
    """
    Format datetime to ISO string format

    Args:
        dt: datetime object

    Returns:
        str: ISO format string (e.g., "2023-02-12T09:00:00Z")
    """
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_datetime_from_str(time_str: str) -> datetime:
    """
    Parse datetime from ISO string format

    Args:
        time_str: ISO format datetime string

    Returns:
        datetime: Parsed datetime object
    """
    return datetime.strptime(time_str, "%Y-%m-%dT%H:%M:%SZ")


# ============================================================================
# Parser Helper Functions
# ============================================================================


def get_parser_and_parse(
    parsers: Dict[str, Any], token_type: str, token: Dict[str, Any], base_time: datetime
) -> Optional[List]:
    """
    Get parser and parse token with unified error handling

    Args:
        parsers: Dictionary containing various time parsers
        token_type: Type of token to parse
        token: Token dictionary to parse
        base_time: Base time reference

    Returns:
        Parsed result or None if parser not found
    """
    parser = parsers.get(token_type)
    if not parser:
        return None
    return parser.parse(token, base_time)


# ============================================================================
# Date Range Creation Functions
# ============================================================================


def create_day_range(date: datetime) -> Tuple[datetime, datetime]:
    """
    Create start and end time for a day

    Args:
        date: datetime object

    Returns:
        tuple: (start_of_day, end_of_day)
    """
    start = date.replace(hour=0, minute=0, second=0, microsecond=0)
    end = date.replace(hour=23, minute=59, second=59, microsecond=0)
    return start, end


# ============================================================================
# English Number Words Mapping
# ============================================================================

# Basic English number words mapping (0-10)
ENGLISH_NUMBER_WORDS_BASIC = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
}

# Extended English number words mapping (includes larger numbers)
ENGLISH_NUMBER_WORDS_EXTENDED = {
    **ENGLISH_NUMBER_WORDS_BASIC,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
    "hundred": 100,
    "thousand": 1000,
}


# ============================================================================
# Token Finding Helper Functions
# ============================================================================


def find_token_value(
    tokens: List[Dict[str, Any]], start_idx: int, target_value: str, max_lookahead: int = 4
) -> Optional[int]:
    """
    Find token with specific value, skipping empty tokens

    Args:
        tokens: List of tokens
        start_idx: Starting index to search from
        target_value: Target value to find (case-insensitive)
        max_lookahead: Maximum number of tokens to look ahead

    Returns:
        Index of found token or None if not found
    """
    n = len(tokens)
    target_lower = target_value.lower()
    for j in range(start_idx, min(start_idx + max_lookahead, n)):
        if (
            tokens[j].get("type") == "token"
            and tokens[j].get("value", "").strip().lower() == target_lower
        ):
            return j
        elif tokens[j].get("type") != "token" or tokens[j].get("value", "").strip():
            break
    return None


def find_token_by_type(
    tokens: List[Dict[str, Any]], start_idx: int, target_types: List[str], max_lookahead: int = 4
) -> Tuple[Optional[int], Optional[Dict[str, Any]]]:
    """
    Find token by type, skipping empty tokens

    Args:
        tokens: List of tokens
        start_idx: Starting index to search from
        target_types: List of target token types
        max_lookahead: Maximum number of tokens to look ahead

    Returns:
        tuple: (index, token) or (None, None) if not found
    """
    n = len(tokens)
    for j in range(start_idx, min(start_idx + max_lookahead, n)):
        token_type = tokens[j].get("type")
        if token_type in target_types:
            return j, tokens[j]
        elif token_type != "token" or tokens[j].get("value", "").strip():
            break
    return None, None
