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
from dateutil.relativedelta import relativedelta
from .merge_utils import (
    adjust_base_for_relative,
    inherit_noon,
    build_utc_token,
    safe_parse,
    build_range_from_endpoints,
    inherit_fields,
    check_token_sequence,
    safe_parse_with_jump,
    normalize_year_in_token,
)
from .mergers.period_merger import PeriodMerger
from .mergers.unit_merger import UnitMerger
from .mergers.date_component_merger import DateComponentMerger
from .mergers.rules.priority_0_rules import Priority0Rules
from .mergers.rules.priority_1_rules import Priority1Rules
from .mergers.rules.priority_2_rules import Priority2Rules
from .mergers.rules.priority_3_rules import Priority3Rules
from .mergers.rules.priority_4_rules import Priority4Rules
from .mergers.rules.priority_5_rules import Priority5Rules
from ...core.logger import get_logger


class ContextMerger:
    """上下文合并器，处理复杂的时间表达式合并逻辑"""

    def __init__(self, parsers):
        """
        初始化上下文合并器

        Args:
            parsers (dict): 解析器字典，包含各种时间解析器
        """
        self.parsers = parsers
        self.logger = get_logger(__name__)

        # 中文数字映射
        self.chinese_num_map = {
            "一": 1,
            "二": 2,
            "三": 3,
            "四": 4,
            "五": 5,
            "六": 6,
            "七": 7,
            "八": 8,
            "九": 9,
            "十": 10,
            "十一": 11,
            "十二": 12,
            "十三": 13,
            "十四": 14,
            "十五": 15,
            "十六": 16,
            "十七": 17,
            "十八": 18,
            "十九": 19,
            "二十": 20,
        }

        # 初始化子合并器
        self.period_merger = PeriodMerger(parsers)
        self.unit_merger = UnitMerger(parsers)
        self.date_component_merger = DateComponentMerger(parsers)

        # 初始化优先级规则处理器
        self.rule_processors = [
            Priority0Rules(self),
            Priority1Rules(self),
            Priority2Rules(self),
            Priority3Rules(self),
            Priority4Rules(self),
            Priority5Rules(self),
        ]

    def try_merge(self, i, tokens, base_time):  # noqa: C901
        """
        尝试合并tokens中的时间表达式

        Args:
            i (int): 当前token索引
            tokens (list): token列表
            base_time (datetime): 基准时间

        Returns:
            tuple: (合并结果列表, 跳跃的token数量) 或 None
        """
        n = len(tokens)
        if i >= n:
            return None

        # 按优先级遍历规则处理器
        for rule_processor in self.rule_processors:
            result = rule_processor.try_merge(i, tokens, base_time)
            if result is not None:
                return result

        return None
