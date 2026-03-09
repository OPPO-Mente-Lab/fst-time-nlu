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
from ...merge_utils import normalize_year


class Priority0Rules(BaseRule):
    """Priority 0: 最高优先级规则 - 之前/之后、未来时间+之前等"""

    def try_merge(
        self, i: int, tokens: List[Dict[str, Any]], base_time: datetime
    ) -> Optional[Tuple[List, int]]:
        """
        Try to merge based on Priority 0 rules

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

        cur = tokens[i]
        t = cur.get("type")

        # -1. 之前/之后 + 时间表达式 → 只保留后面的时间
        # 例如：之前重阳节、之后春节
        if cur.get("type") == "time_period" and cur.get("period_word") in ["-7", "7"]:
            result = self._merge_before_after_with_time(i, tokens, base_time)
            if result is not None:
                return result

        # 0. 未来时间 + 之前/以前/前 → 从现在到未来时间的范围
        if t in ["time_relative", "time_utc", "time_period"]:
            result = self._merge_future_time_before(i, tokens, base_time)
            if result is not None:
                return result

        return None

    def _merge_before_after_with_time(self, i, tokens, base_time):
        """
        合并"之前/之后" + 时间表达式
        例如：之前重阳节、之后春节、之前的中秋节

        语义：当"之前/之后"单独出现在时间词前面时,通常是修饰语,应该忽略"之前/之后",只保留后面的时间
        """
        n = len(tokens)
        if i >= n:
            return None

        cur = tokens[i]

        # 检查当前token是否是"之前/之后"(period_word为-7或7)
        if cur.get("type") != "time_period" or cur.get("period_word") not in [
            "-7",
            "7",
        ]:
            return None

        # 查找下一个非空token
        next_idx = i + 1
        while next_idx < n:
            next_token = tokens[next_idx]
            # 跳过char类型的"的"
            if next_token.get("type") == "char" and next_token.get("value") == "的":
                next_idx += 1
                continue
            # 找到下一个时间token
            if next_token.get("type") in [
                "time_holiday",
                "time_relative",
                "time_utc",
                "time_weekday",
                "time_period",
                "time_between",
            ]:
                # 解析后面的时间token
                parser = self.parsers.get(next_token.get("type"))
                if parser:
                    result = parser.parse(next_token, base_time)
                    if result:
                        # 返回后面时间的结果,忽略"之前/之后"
                        consumed = next_idx - i + 1
                        return (result, consumed)
                return None
            # 遇到其他类型token,停止查找
            break

        return None

    def _merge_future_time_before(self, i, tokens, base_time):  # noqa: C901
        """
        合并未来时间 + 之前/以前/前
        例如：明年6月之前、后天之前、下个月前、明年初之前、明年底前、年底前

        语义：从现在到未来时间点的起始点（对于"明年底前"等）或结束点（对于"年底前"等period）
        """
        n = len(tokens)
        if i + 1 >= n:
            return None

        cur = tokens[i]
        cur_type = cur.get("type")

        # 只处理time_relative、time_utc和time_period类型
        if cur_type not in ["time_relative", "time_utc", "time_period"]:
            return None

        # 检查下一个token是否是"前"、"之前"或"以前"
        next1 = tokens[i + 1]

        # 检查是否是"前"
        is_before = False
        consumed = 2
        merged_token = None

        if next1.get("type") == "char" and next1.get("value") == "前":
            is_before = True
            consumed = 2
            merged_token = cur
        # 检查是否是"之前"或"以前"
        elif next1.get("type") == "char" and next1.get("value") in ["之", "以"] and i + 2 < n:
            next2 = tokens[i + 2]
            if next2.get("type") == "char" and next2.get("value") == "前":
                is_before = True
                consumed = 3
                merged_token = cur
        # 检查是否是"之前"(time_period形式 - 单独识别的"之前")
        elif next1.get("type") == "time_period" and next1.get("period_word") == "-7":
            is_before = True
            consumed = 2
            merged_token = cur
        # 特殊情况：time_relative + time_delta{month, offset_direction:-1}
        # 例如："明年" + "6月之前"（被识别为一个time_delta）
        elif (
            cur_type == "time_relative"
            and next1.get("type") == "time_delta"
            and next1.get("offset_direction") == "-1"
            and next1.get("month")
        ):
            # 构造合并后的token
            merged_token = dict(cur)
            merged_token["month"] = next1.get("month")
            merged_token["day"] = "1"
            is_before = True
            consumed = 2

        if is_before and merged_token:
            # 判断是否为未来时间并解析
            # 对于merged_token，需要根据其类型选择parser
            token_type = merged_token.get("type", cur_type)
            parser = self.parsers.get(token_type)
            if not parser:
                return None

            # 先解析时间
            result = parser.parse(merged_token, base_time)
            if not result or len(result) == 0 or len(result[0]) == 0:
                return None

            # 判断是否为未来时间
            is_future = False
            if token_type == "time_period":
                # 对于time_period，检查是否是"年底"等未来period
                year_period = merged_token.get("year_period")
                if year_period == "lateyear":  # 年底
                    if base_time.month < 12 or (base_time.month == 12 and base_time.day < 31):
                        is_future = True
            elif token_type == "time_relative":
                # 对于time_relative，检查offset
                offset_year = int(merged_token.get("offset_year", 0))
                offset_month = int(merged_token.get("offset_month", 0))
                offset_day = int(merged_token.get("offset_day", 0))
                if offset_year > 0 or offset_month > 0 or offset_day > 0:
                    is_future = True
                # 对于offset_year=0（今年），如果有month，需要比较
                elif offset_year == 0 and merged_token.get("month"):
                    try:
                        month = int(merged_token.get("month"))
                        if month > base_time.month:
                            is_future = True
                        elif month == base_time.month and merged_token.get("day"):
                            day = int(merged_token.get("day"))
                            if day > base_time.day:
                                is_future = True
                    except Exception:
                        pass
            elif token_type == "time_utc":
                # 对于time_utc，比较年份
                if merged_token.get("year"):
                    try:
                        year = normalize_year(int(merged_token.get("year")))
                        if year > base_time.year:
                            is_future = True
                        elif year == base_time.year:
                            # 同年，比较月份
                            if merged_token.get("month"):
                                month = int(merged_token.get("month"))
                                if month > base_time.month:
                                    is_future = True
                                elif month == base_time.month and merged_token.get("day"):
                                    day = int(merged_token.get("day"))
                                    if day > base_time.day:
                                        is_future = True
                    except Exception:
                        pass

            if is_future:
                # 从现在到未来时间的起始点
                start_str = base_time.strftime("%Y-%m-%dT%H:%M:%SZ")
                end_str = result[0][0]  # 取起始时间
                return ([[start_str, end_str]], consumed)

        # 复杂情况：中间有其他token，如"明年"+"底"+"前"
        # 查找"前"的位置
        for j in range(i + 1, min(i + 4, n)):
            # 检查是否是"前"标记(char形式或time_period形式)
            is_before_marker = (
                tokens[j].get("type") == "char" and tokens[j].get("value") == "前"
            ) or (tokens[j].get("type") == "time_period" and tokens[j].get("period_word") == "-7")

            if is_before_marker:
                # 找到了"前"，检查中间是否有"底"或"初"
                has_di = False
                has_chu = False
                for k in range(i + 1, j):
                    if tokens[k].get("type") == "char":
                        if tokens[k].get("value") == "底":
                            has_di = True
                        elif tokens[k].get("value") == "初":
                            has_chu = True

                if has_di or has_chu:
                    # 构造新token
                    if cur_type == "time_relative":
                        offset_year = int(cur.get("offset_year", 0))
                        if offset_year >= 0:  # 今年或未来
                            merged_token = dict(cur)
                            if has_di:
                                merged_token["month"] = "11"  # 年底(11-12月)的起始点是11月1日
                                merged_token["day"] = "1"
                            elif has_chu:
                                merged_token["month"] = "1"
                                merged_token["day"] = "1"

                            # 判断是否为未来
                            if offset_year > 0:
                                is_future = True
                            else:  # offset_year == 0，今年
                                month = int(merged_token.get("month", 1))
                                is_future = month > base_time.month or (
                                    month == base_time.month
                                    and int(merged_token.get("day", 1)) > base_time.day
                                )

                            if is_future:
                                # 解析并返回
                                parser = self.parsers.get("time_relative")
                                if parser:
                                    result = parser.parse(merged_token, base_time)
                                    if result and len(result) > 0 and len(result[0]) > 0:
                                        start_str = base_time.strftime("%Y-%m-%dT%H:%M:%SZ")
                                        end_str = result[0][0]  # 取起始时间
                                        return ([[start_str, end_str]], j - i + 1)
                break

        return None
