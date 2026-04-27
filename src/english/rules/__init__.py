# Copyright (c)  2025  OPPO Corporation.   (authors: Ming Yu, Liangliang Han)
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

"""
English time rules module

Provides various time expression recognition and processing rules for English.
"""

from .utctime import UTCTimeRule
from .char import TokenRule
from .period import PeriodRule
from .week import WeekRule
from .relative import RelativeRule
from .holiday import HolidayRule
from .composite_relative import CompositeRelativeRule
from .time_range import TimeRangeRule
from .range import RangeRule
from .fraction import FractionRule
from .century import CenturyRule
from .whitelist import WhitelistRule
from .time_delta import TimeDeltaRule
from .quarter import QuarterRule
from .recurring import RecurringRule

__all__ = [
    # Main rule classes
    "UTCTimeRule",
    "TokenRule",
    "PeriodRule",
    "WeekRule",
    "RelativeRule",
    "HolidayRule",
    "CompositeRelativeRule",
    "TimeRangeRule",
    "RangeRule",
    "FractionRule",
    "CenturyRule",
    "WhitelistRule",
    "TimeDeltaRule",
    "QuarterRule",
    "RecurringRule",
]
