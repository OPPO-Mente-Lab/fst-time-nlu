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
from ...merge_utils import (
    safe_parse,
    inherit_fields,
)


class Priority5Rules(BaseRule):
    """Priority 5: 格式和特殊模式、和连接等规则"""

    def try_merge(
        self, i: int, tokens: List[Dict[str, Any]], base_time: datetime
    ) -> Optional[Tuple[List, int]]:
        """
        Try to merge based on Priority 5 rules

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

        # 8c. ISO时间格式合并：time_utc + char('T') + time_utc + char('Z')
        # 例如："2024-12-31T00:00:00Z" -> 日期 + T + 时间 + Z
        result = self._merge_iso_time_format(i, tokens, base_time)
        if result is not None:
            return result

        # 8d. 多星期几周期合并：time_recurring + char('/'|'、'|'和') + time_weekday
        # 例如："每周六/周日" -> 每周六和每周日
        result = self._merge_multi_weekday_recurring(i, tokens, base_time)
        if result is not None:
            return result

        # 9-11. "和"连接的相关处理
        result = self._merge_and_connections(i, tokens, base_time)
        if result is not None:
            return result

        return None

    def _merge_iso_time_format(self, i, tokens, base_time):
        """
        合并ISO时间格式：time_utc + char('T') + time_utc + char('Z')
        例如："2024-12-31T00:00:00Z" -> 日期 + T + 时间 + Z
        """
        n = len(tokens)
        if i + 3 >= n:
            return None

        cur = tokens[i]
        t_char = tokens[i + 1]
        time_token = tokens[i + 2]
        z_char = tokens[i + 3]

        # 检查是否是ISO时间格式
        if (
            cur.get("type") == "time_utc"
            and "year" in cur
            and "month" in cur
            and "day" in cur
            and t_char.get("type") == "char"
            and t_char.get("value") == "T"
            and time_token.get("type") == "time_utc"
            and "hour" in time_token
            and z_char.get("type") == "char"
            and z_char.get("value") == "Z"
        ):

            try:
                # 合并日期和时间信息
                merged_token = dict(cur)
                merged_token.update(time_token)

                # 解析合并后的时间
                utc_parser = self.parsers.get("time_utc")
                if not utc_parser:
                    return None

                result = utc_parser.parse(merged_token, base_time)
                if not result or not result[0]:
                    return None

                return (result, 4)  # 跳过四个token

            except Exception as e:
                self.logger.debug(f"Error in _merge_iso_time_format: {e}")
                return None

        return None

    def _merge_multi_weekday_recurring(self, i, tokens, base_time):
        """
        处理多星期几的周期合并：time_recurring + char('/'|'、'|'和') + time_weekday
        例如："每周六/周日" -> 每周六和每周日
        """
        n = len(tokens)
        if i + 2 >= n:
            return None

        cur = tokens[i]
        connector = tokens[i + 1]
        weekday = tokens[i + 2]

        # 检查第一个token是否为time_recurring且包含week_day
        if (
            cur.get("type") != "time_recurring"
            or cur.get("recurring_type") != "week"
            or not cur.get("week_day")
        ):
            return None

        # 检查连接符
        if connector.get("type") != "char" or connector.get("value") not in [
            "/",
            "、",
            "和",
        ]:
            return None

        # 检查第三个token是否为time_weekday
        if weekday.get("type") != "time_weekday" or not weekday.get("week_day"):
            return None

        try:
            # 合并week_day
            first_weekday = cur.get("week_day")
            second_weekday = weekday.get("week_day")

            # 创建合并后的token
            merged_token = dict(cur)
            merged_token["week_day"] = f"{first_weekday},{second_weekday}"

            # 解析合并后的时间
            recurring_parser = self.parsers.get("time_recurring")
            if not recurring_parser:
                return None

            result = recurring_parser.parse(merged_token, base_time)
            if not result or not result[0]:
                return None

            return (result, 3)  # 跳过三个token

        except Exception as e:
            self.logger.debug(f"Error in _merge_multi_weekday_recurring: {e}")
            return None

    def _merge_and_connections(self, i, tokens, base_time):  # noqa: C901
        """合并"和"连接的相关处理"""
        n = len(tokens)
        cur = tokens[i]

        # 检查基本模式：X + char(数字) + and + time_utc(Y)
        j = i + 1
        if j >= n or tokens[j].get("type") != "char" or not tokens[j].get("value", "").isdigit():
            return None

        k = j + 1
        if k >= n or tokens[k].get("type") != "and":
            return None

        time_utc_idx = k + 1
        if time_utc_idx >= n or tokens[time_utc_idx].get("type") != "time_utc":
            return None

        right_token = tokens[time_utc_idx]

        # 情况1：time_relative + char(数字) + and + time_utc(month) → 省略月份
        if cur.get("type") == "time_relative" and "month" in right_token:
            left_tok = dict(cur)
            right_tok = dict(right_token)
            right_tok["type"] = "time_relative"

            # 继承相对时间信息
            inherit_fields(
                cur,
                right_tok,
                [
                    "offset_year",
                    "offset_month",
                    "offset_day",
                    "offset_direction",
                    "noon",
                ],
            )

            relative_parser = self.parsers.get("time_relative")
            if relative_parser:
                left_res = safe_parse(relative_parser, left_tok, base_time)
                right_res = safe_parse(relative_parser, right_tok, base_time)

                if left_res and right_res:
                    return (left_res + right_res, 4)

        # 情况2：time_relative + char(数字) + and + time_utc(hour) → 省略小时
        elif cur.get("type") == "time_relative" and "hour" in right_token:
            left_tok = dict(cur)
            right_tok = dict(right_token)
            right_tok["type"] = "time_relative"
            right_tok["hour"] = tokens[j].get("value")

            # 继承相对时间信息
            inherit_fields(
                cur,
                right_tok,
                [
                    "offset_year",
                    "offset_month",
                    "offset_day",
                    "offset_direction",
                    "noon",
                ],
            )

            relative_parser = self.parsers.get("time_relative")
            if relative_parser:
                left_res = safe_parse(relative_parser, left_tok, base_time)
                right_res = safe_parse(relative_parser, right_tok, base_time)

                if left_res and right_res:
                    return (left_res + right_res, 4)

        # 情况3：time_utc(noon) + char(数字) + and + time_utc(hour) → 省略小时
        elif cur.get("type") == "time_utc" and "noon" in cur and "hour" in right_token:
            left_tok = dict(cur)
            left_tok["hour"] = tokens[j].get("value")
            right_tok = dict(right_token)

            # 继承noon信息
            right_tok["noon"] = cur.get("noon")

            utc_parser = self.parsers.get("time_utc")
            if utc_parser:
                left_res = safe_parse(utc_parser, left_tok, base_time)
                right_res = safe_parse(utc_parser, right_tok, base_time)

                if left_res and right_res:
                    return (left_res + right_res, 4)

        return None
