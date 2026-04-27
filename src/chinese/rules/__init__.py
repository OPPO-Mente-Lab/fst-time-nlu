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
时间规则模块

提供各种时间表达式的识别和处理规则。
"""

from .between import BetweenRule
from .char import CharRule
from .delta import DeltaRule
from .holiday import HolidayRule
from .lunar import LunarRule
from .period import PeriodRule
from .postprocessor import PostProcessor
from .preprocessor import PreProcessor
from .relative import RelativeRule
from .utctime import UTCTimeRule
from .week import WeekRule
from .whitelist import WhitelistRule
from .decimal import DecimalRule
from .unit import UnitRule
from .verb_duration import VerbDurationRule
from .range import RangeRule
from .delta_time_attach import DeltaTimeAttachRule
from .recurring import RecurringRule

__all__ = [
    # 主要规则类
    "BetweenRule",
    "CharRule",
    "DeltaRule",
    "HolidayRule",
    "LunarRule",
    "PeriodRule",
    "PostProcessor",
    "PreProcessor",
    "RelativeRule",
    "UTCTimeRule",
    "WeekRule",
    "WhitelistRule",
    "DecimalRule",
    "UnitRule",
    "VerbDurationRule",
    "RangeRule",
    "DeltaTimeAttachRule",
    "RecurringRule",
]
