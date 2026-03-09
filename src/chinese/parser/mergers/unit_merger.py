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

from .base_merger import BaseMerger
from ..merge_utils import (
    safe_parse,
)
from dateutil.relativedelta import relativedelta


class UnitMerger(BaseMerger):
    """
    单位合并器 - 简化版

    负责处理单位和偏移相关的合并逻辑，包括：
    - 单位+时间差合并
    - 分数时间合并
    - 季度偏移合并
    """

    def try_merge(self, i, tokens, base_time):
        """
        尝试合并单位相关的表达式

        Args:
            i (int): 当前token索引
            tokens (list): token列表
            base_time (datetime): 基准时间

        Returns:
            tuple: (合并结果列表, 跳跃的token数量) 或 None
        """
        # 1. 单位+时间差合并
        result = self._merge_unit_delta(i, tokens, base_time)
        if result is not None:
            return result

        # 2. 单位+分数时间合并
        result = self._merge_unit_delta_fractional(i, tokens, base_time)
        if result is not None:
            return result

        # 3. 分数分钟合并
        result = self._merge_fractional_minutes(i, tokens, base_time)
        if result is not None:
            return result

        # 4. N个季度后/前
        result = self._merge_unit_quarter_direction(i, tokens, base_time)
        if result is not None:
            return result

        return None

    def _merge_unit_delta(self, i, tokens, base_time):  # noqa: C901
        """等价抽取：unit + time_delta 分数时间表达合并"""
        n = len(tokens)
        cur = tokens[i]
        if not (cur.get("type") == "unit" and "value" in cur and "unit" in cur):
            return None
        j = i + 1
        if j >= n or tokens[j].get("type") != "time_delta":
            return None

        try:
            unit_value = int(cur.get("value", "1"))
            unit_name = cur.get("unit", "")

            if unit_name == "个":
                delta_tok = dict(tokens[j])

                if "minute" in delta_tok:
                    minute_val = int(delta_tok.get("minute", "0"))
                    total_minutes = unit_value * 60 + minute_val
                    delta_tok["minute"] = str(total_minutes)
                elif "hour" in delta_tok:
                    hour_val = int(delta_tok.get("hour", "0"))
                    delta_tok["hour"] = str(unit_value + hour_val * 0.5)
                elif "day" in delta_tok:
                    day_val = int(delta_tok.get("day", "0"))
                    delta_tok["day"] = str(unit_value + day_val * 0.5)
                elif "month" in delta_tok:
                    month_val = int(delta_tok.get("month", "0"))
                    delta_tok["month"] = str(unit_value + month_val * 0.5)
                elif "year" in delta_tok:
                    year_val = int(delta_tok.get("year", "0"))
                    delta_tok["year"] = str(unit_value + year_val * 0.5)
                elif "second" in delta_tok and unit_name in ("分", "分钟"):
                    delta_tok["minute"] = str(unit_value)

                delta_parser = self.parsers["time_delta"]
                parsed = safe_parse(delta_parser, delta_tok, base_time)
                return (parsed or [], 2) if parsed else None
        except Exception:
            pass

        return None

    def _merge_unit_delta_fractional(self, i, tokens, base_time):  # noqa: C901
        """合并unit(数字+个) + time_delta(半+单位+前/后) → 完整的time_delta"""
        n = len(tokens)
        if i + 1 >= n:
            return None

        cur = tokens[i]
        next_token = tokens[i + 1]

        # 检查当前token是否为unit类型，且unit为"个"
        if cur.get("type") != "unit" or cur.get("unit") != "个":
            return None

        # 检查下一个token是否为time_delta类型
        if next_token.get("type") != "time_delta":
            return None

        try:
            # 获取unit中的数字值
            unit_value = int(cur.get("value", "1"))

            # 获取time_delta中的信息
            delta_unit = None
            delta_value = 0

            # 检查是否有fractional字段（表示"半"）
            if next_token.get("fractional"):
                # 有fractional字段，表示是"半+单位"的形式
                for field in ["year", "month", "day", "hour", "minute", "second"]:
                    if field in next_token:
                        delta_unit = field
                        delta_value = int(next_token.get(field, "0"))
                        break

                # 构造新的time_delta token，将unit_value和fractional结合
                new_delta_token = {
                    "type": "time_delta",
                    delta_unit: str(unit_value),
                    "fractional": next_token.get("fractional"),
                    "offset_direction": next_token.get("offset_direction"),
                }
            else:
                # 没有fractional字段，检查是否是"半小时"被转换为30分钟的情况
                if "minute" in next_token and int(next_token.get("minute", "0")) == 30:
                    # "半小时"被转换为30分钟，我们需要将其转换为0.5小时
                    new_delta_token = {
                        "type": "time_delta",
                        "hour": str(unit_value),
                        "fractional": "0.5",
                        "offset_direction": next_token.get("offset_direction"),
                    }
                else:
                    # 其他情况，直接使用原有的delta值
                    for field in ["year", "month", "day", "hour", "minute", "second"]:
                        if field in next_token:
                            delta_unit = field
                            delta_value = int(next_token.get(field, "0"))
                            break

                    new_delta_token = {
                        "type": "time_delta",
                        delta_unit: str(unit_value + delta_value),
                        "offset_direction": next_token.get("offset_direction"),
                    }

            # 解析新的token
            delta_parser = self.parsers.get("time_delta")
            parsed = safe_parse(delta_parser, new_delta_token, base_time)

            if parsed:
                return (parsed, 2)  # 消耗2个token
        except Exception:
            pass

        return None

    def _merge_fractional_minutes(self, i, tokens, base_time):  # noqa: C901
        """合并分数分钟处理：unit(分/分钟) + char('钟').ques + char('半') + (char('以').ques + char('前'|'后'))"""
        n = len(tokens)
        cur = tokens[i]
        if cur.get("type") != "unit":
            return None

        # 检查是否是 unit + time_delta 的情况（如：一分半钟前）
        if i + 1 < n and tokens[i + 1].get("type") == "time_delta":
            next_tok = tokens[i + 1]
            if (
                next_tok.get("second") == "30"
                and next_tok.get("offset_direction") in ("-1", "1")
                and not next_tok.get("minute")
            ):
                # 这是"X分半钟前/后"的情况，需要合并
                unit_value = int(cur.get("value", "1"))
                direction = int(next_tok.get("offset_direction", "1"))

                delta_tok = {
                    "type": "time_delta",
                    "minute": str(unit_value),
                    "second": "30",
                    "offset_direction": str(direction),
                }

                delta_parser = self.parsers.get("time_delta")
                parsed = safe_parse(delta_parser, delta_tok, base_time)

                if parsed:
                    return (parsed, 2)  # 消耗2个token
                return None

        try:
            unit_value = int(cur.get("value", "1"))
            unit_name = cur.get("unit", "")
            if unit_name not in ("分", "分钟"):
                return None

            j = i + 1
            # 检查下一个token是否是"半"或"钟"
            if j >= n or tokens[j].get("type") != "char":
                return None

            if tokens[j].get("value") == "半":
                # 模式1: unit(分) + char(半) + char(钟).ques + char(以).ques + char(前/后/内)
                k = j + 1
                has_zhong = (
                    k < n and tokens[k].get("type") == "char" and tokens[k].get("value") == "钟"
                )
                maybe_yi_idx = k + 1 if has_zhong else k

                has_yi = (
                    maybe_yi_idx < n
                    and tokens[maybe_yi_idx].get("type") == "char"
                    and tokens[maybe_yi_idx].get("value") == "以"
                )
                m = maybe_yi_idx + 1 if has_yi else maybe_yi_idx
            elif tokens[j].get("value") == "钟":
                # 模式2: unit(分) + char(钟) + char(半) + char(以).ques + char(前/后/内)
                k = j + 1
                if k >= n or tokens[k].get("type") != "char" or tokens[k].get("value") != "半":
                    return None

                maybe_yi_idx = k + 1
                has_yi = (
                    maybe_yi_idx < n
                    and tokens[maybe_yi_idx].get("type") == "char"
                    and tokens[maybe_yi_idx].get("value") == "以"
                )
                m = maybe_yi_idx + 1 if has_yi else maybe_yi_idx
                has_zhong = True  # 标记有"钟"字符
            else:
                return None

            if (
                m >= n
                or tokens[m].get("type") != "char"
                or tokens[m].get("value") not in ("前", "后", "内")
            ):
                return None

            if tokens[m].get("value") == "内":
                # 处理"以内"的情况，创建time_range
                range_tok = {
                    "type": "time_range",
                    "value": str(unit_value),
                    "fractional": "0.5",
                    "unit": "minute",
                    "range_type": "ago",
                }

                range_parser = self.parsers.get("time_range")
                parsed = safe_parse(range_parser, range_tok, base_time)

                if parsed:
                    consumed = 1  # unit
                    if has_zhong:
                        consumed += 1
                    consumed += 1  # 半
                    if has_yi:
                        consumed += 1
                    consumed += 1  # 内
                    return (parsed, consumed)
                return None
            else:
                # 处理"前"和"后"的情况
                direction = -1 if tokens[m].get("value") == "前" else 1
                delta_tok = {
                    "type": "time_delta",
                    "minute": str(unit_value),
                    "second": "30",
                    "offset_direction": str(direction),
                }

            delta_parser = self.parsers.get("time_delta")
            parsed = safe_parse(delta_parser, delta_tok, base_time)

            if parsed:
                consumed = 1  # unit
                if has_zhong:
                    consumed += 1
                consumed += 1  # 半
                if has_yi:
                    consumed += 1
                consumed += 1  # 前/后
                return (parsed, consumed)
        except Exception:
            pass

        return None

    def _merge_unit_quarter_direction(self, i, tokens, base_time):
        """
        合并: unit(N+个) + char(季) + char(度) + char(后/前)
        例如: 三个季度后
        """
        n = len(tokens)
        if i + 3 >= n:
            return None

        cur = tokens[i]
        tok1 = tokens[i + 1]
        tok2 = tokens[i + 2]
        tok3 = tokens[i + 3]

        # 检查模式: unit(个) + char(季) + char(度) + char(后/前)
        if (
            cur.get("type") == "unit"
            and cur.get("unit") == "个"
            and tok1.get("type") == "char"
            and tok1.get("value") == "季"
            and tok2.get("type") == "char"
            and tok2.get("value") == "度"
            and tok3.get("type") == "char"
            and tok3.get("value") in ["后", "前"]
        ):

            try:
                quarter_num = int(cur.get("value", "1"))
                direction = 1 if tok3.get("value") == "后" else -1

                # 计算目标季度
                months_offset = quarter_num * 3 * direction
                target_time = base_time + relativedelta(months=months_offset)

                # 获取目标季度的范围
                period_parser = self.parsers.get("time_period")
                start_of_quarter, end_of_quarter = period_parser._get_quarter_range(target_time)
                result = period_parser._format_time_result(start_of_quarter, end_of_quarter)

                if result:
                    return (result, 4)  # 消耗4个token
            except Exception:
                pass

        return None
