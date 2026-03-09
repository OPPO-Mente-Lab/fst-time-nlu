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
    """Priority 1: 时期、单位、日期组件合并器处理"""

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

        # 0a. 时期合并器处理
        result = self.context_merger.period_merger.try_merge(i, tokens, base_time)
        if result is not None:
            return result

        # 0b. 单位合并器处理
        result = self.context_merger.unit_merger.try_merge(i, tokens, base_time)
        if result is not None:
            return result

        # 0c. 日期组件合并器处理
        result = self.context_merger.date_component_merger.try_merge(i, tokens, base_time)
        if result is not None:
            return result

        # 0d. 处理"这+unit+半+单位"模式（如：这两个半月）
        result = self._merge_zhe_unit_half_unit(i, tokens, base_time)
        if result is not None:
            return result

        return None

    def _merge_zhe_unit_half_unit(self, i, tokens, base_time):
        """
        处理"这+unit+半+单位"模式（如：这两个半月）
        """
        n = len(tokens)
        if i + 3 >= n:
            return None

        # 检查token序列：char('这') + unit + char('半') + char('单位')
        cur = tokens[i]
        unit_tok = tokens[i + 1]
        half_tok = tokens[i + 2]
        unit_char_tok = tokens[i + 3]

        # 检查第一个token是否为"这"
        if cur.get("type") != "char" or cur.get("value") != "这":
            return None

        # 检查第二个token是否为unit类型，且unit为"个"
        if unit_tok.get("type") != "unit" or unit_tok.get("unit") != "个":
            return None

        # 检查第三个token是否为"半"
        if half_tok.get("type") != "char" or half_tok.get("value") != "半":
            return None

        # 检查第四个token是否为时间单位
        unit_char = unit_char_tok.get("value")
        if unit_char not in ["月", "年", "天", "日"]:
            return None

        try:
            # 构造time_period token
            unit_value = int(unit_tok.get("value", "1"))

            # 映射单位
            unit_map = {"月": "month", "年": "year", "天": "day", "日": "day"}

            period_token = {
                "type": "time_period",
                "offset_direction": "-1",  # "这"表示过去
                "offset": str(unit_value),
                "unit": unit_map[unit_char],
                "fractional": "0.5",  # "半"
            }

            # 解析合并后的时间
            period_parser = self.parsers.get("time_period")
            if not period_parser:
                return None

            result = period_parser.parse(period_token, base_time)
            if not result or not result[0]:
                return None

            return (result, 4)  # 跳过四个token

        except Exception as e:
            self.logger.debug(f"Error in _merge_zhe_unit_half_unit: {e}")
            return None
