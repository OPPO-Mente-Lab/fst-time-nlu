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
    adjust_base_for_relative,
    safe_parse,
    normalize_year,
)


class Priority3Rules(BaseRule):
    """Priority 3: year-only、和连接、相对时间+月份区间等规则"""

    def try_merge(
        self, i: int, tokens: List[Dict[str, Any]], base_time: datetime
    ) -> Optional[Tuple[List, int]]:
        """
        Try to merge based on Priority 3 rules

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

        # 1. year-only 合并（排除special_time，因为special_time有专门的合并逻辑）
        if (
            t == "time_utc"
            and "year" in cur
            and "month" not in cur
            and "day" not in cur
            and "special_time" not in cur
        ):
            # 检查下一个token是否是'底'，如果是，则调用_merge_utc_di (已迁移到PeriodMerger)
            # 尝试年份+季度（含三元合并：年+季度+初/末）(已迁移到DateComponentMerger)

            return self._handle_year_only_merge(i, tokens, base_time)

        # 4. "和"连接的继承
        result = self._merge_and_inheritance(i, tokens, base_time)
        if result is not None:
            return result

        # 6. time_relative + time_between(hour) + time_between(month) → 省略月份区间
        result = self._merge_relative_hour_month_range(i, tokens, base_time)
        if result is not None:
            return result

        # 7. time_utc(year) + time_between(hour) + time_between(month) → 年份+省略月份区间
        result = self._merge_utc_year_hour_month_range(i, tokens, base_time)
        if result is not None:
            return result

        # 8. time_relative(noon) + time_utc(noon, hour) → 时段词冲突，优先精确时间
        result = self._merge_relative_utc_noon_conflict(i, tokens, base_time)
        if result is not None:
            return result

        return None

    def _handle_year_only_merge(self, i, tokens, base_time):  # noqa: C901
        """处理year-only合并逻辑"""
        n = len(tokens)
        cur = tokens[i]
        yv = int(cur.get("year"))

        # 检查是否是年份+年初/年末的情况
        if i + 1 < n and tokens[i + 1].get("type") == "char":
            char_value = tokens[i + 1].get("value")
            if char_value in ["初", "末"]:
                # 标准化年份
                norm_year = normalize_year(yv)

                # 构造年份时间段token
                period_tok = {
                    "type": "time_period",
                    "year": str(norm_year),
                    "year_period": "earlyyear" if char_value == "初" else "lateyear",
                }

                # 解析年份时间段
                period_parser = self.parsers["time_period"]
                parsed = period_parser.parse(period_tok, base_time)
                return (parsed or [], 2)  # 消耗2个token

        # 跳过char类型的token
        j = i + 1
        while j < n and tokens[j].get("type") == "char":
            j += 1
        if j >= n:
            return None
        nxt = tokens[j]

        if nxt.get("type") == "time_utc" and "month" in nxt and "day" in nxt and "year" not in nxt:
            combined = dict(nxt)
            combined["year"] = str(yv)
            parsed = self.parsers["time_utc"].parse(combined, base_time)
            return (parsed or [], j - i + 1)

        # year + time_period(quarter) → 指定年份的季度
        if nxt.get("type") == "time_period" and "quarter" in nxt and "year" not in nxt:
            try:
                # 标准化两位数年份
                norm_year = normalize_year(yv)
                period_tok = dict(nxt)
                period_tok["year"] = str(norm_year)
                parsed = self.parsers["time_period"].parse(period_tok, base_time)
                return (parsed or [], j - i + 1)
            except Exception:
                pass

        # year + holiday → 指定年份的节假日
        # year + holiday + time_utc(noon, hour, minute) → 指定年份节假日的具体时间
        if nxt.get("type") == "time_holiday":
            try:
                # 扩展年份
                if yv < 100:
                    yv = normalize_year(yv)

                # 检查是否有第三个token是time_utc(noon, hour, minute)
                k = j + 1
                while k < n and tokens[k].get("type") == "char":
                    k += 1

                if k < n and tokens[k].get("type") == "time_utc" and "noon" in tokens[k]:
                    # 复合情况：年份 + 节假日 + 具体时间
                    holiday_tok = dict(nxt)
                    holiday_tok["year"] = str(yv)

                    # 创建包含正确年份的基准时间
                    modified_base_time = base_time.replace(year=yv)

                    # 解析节假日获取日期
                    holiday_parser = self.parsers["time_holiday"]
                    holiday_result = holiday_parser.parse(holiday_tok, modified_base_time)
                    if not holiday_result or not holiday_result[0]:
                        return None

                    # 获取节假日的日期
                    holiday_date_str = holiday_result[0][0]
                    holiday_date = datetime.fromisoformat(holiday_date_str.replace("Z", "+00:00"))

                    # 构造带日期信息的时间token
                    time_token = tokens[k]
                    time_with_date = dict(time_token)
                    time_with_date["year"] = str(holiday_date.year)
                    time_with_date["month"] = str(holiday_date.month)
                    time_with_date["day"] = str(holiday_date.day)

                    # 解析具体时间
                    utc_parser = self.parsers.get("time_utc")
                    if not utc_parser:
                        return None

                    time_result = utc_parser.parse(time_with_date, base_time)
                    if not time_result or not time_result[0]:
                        return None

                    return (time_result, k - i + 1)  # 跳过所有相关token
                else:
                    # 简单情况：年份 + 节假日
                    holiday_tok = dict(nxt)
                    holiday_tok["year"] = str(yv)

                    # 创建包含正确年份的基准时间
                    modified_base_time = base_time.replace(year=yv)

                    # 解析节假日
                    holiday_parser = self.parsers["time_holiday"]
                    parsed = holiday_parser.parse(holiday_tok, modified_base_time)
                    return (parsed or [], j - i + 1)
            except Exception:
                pass

        # year + holiday + 到 + year + holiday → 跨年节假日区间
        if (
            nxt.get("type") == "time_holiday"
            and i + 4 < n
            and tokens[i + 2].get("type") == "char"
            and tokens[i + 2].get("value") == "到"
            and tokens[i + 3].get("type") == "time_utc"
            and "year" in tokens[i + 3]
            and tokens[i + 4].get("type") == "time_holiday"
        ):
            try:
                left_holiday = dict(nxt)
                right_year = int(tokens[i + 3].get("year"))
                right_holiday = dict(tokens[i + 4])

                # 解析两端
                holiday_parser = self.parsers["time_holiday"]
                left_base = base_time.replace(year=yv)
                right_base = base_time.replace(year=right_year)

                left_res = holiday_parser.parse(left_holiday, left_base) or []
                right_res = holiday_parser.parse(right_holiday, right_base) or []

                if left_res and right_res and left_res[0] and right_res[0]:
                    # 取左边时间的左端点，右边时间的右端点
                    left_start = left_res[0][0]  # 左边时间的开始
                    right_end = (
                        right_res[0][1] if len(right_res[0]) > 1 else right_res[0][0]
                    )  # 右边时间的结束
                    return ([[left_start, right_end]], 5)
            except Exception:
                pass

        if nxt.get("type") == "time_holiday":
            parsed = self.parsers["time_holiday"].parse(nxt, base_time.replace(year=yv))
            return (parsed or [], j - i + 1)

        if nxt.get("type") == "time_lunar":
            parsed = self.parsers["time_lunar"].parse(nxt, base_time.replace(year=yv))
            return (parsed or [], j - i + 1)

        if nxt.get("type") == "time_period" and "quarter" in nxt:
            q_tok = dict(nxt)
            q_tok["year"] = str(yv)
            parsed = self.parsers["time_period"].parse(q_tok, base_time)
            return (parsed or [], j - i + 1)

        # 处理 year + time_between(hour) + time_between(month) → year + month_range
        if (
            j < n
            and tokens[j].get("type") == "time_between"
            and "hour" in tokens[j]
            and j + 1 < n
            and tokens[j + 1].get("type") == "time_between"
            and "month" in tokens[j + 1]
        ):
            try:
                # 重新解释hour为month
                hour_tok = dict(tokens[j])
                month_tok = dict(tokens[j + 1])

                # 构造年份+月份区间token
                range_tok = {
                    "type": "time_between",
                    "raw_type": "utc",
                    "year": str(yv),
                    "month": hour_tok.get("hour"),
                    "month_end": month_tok.get("month"),
                }

                # 解析区间
                between_parser = self.parsers["time_between"]
                parsed = between_parser.parse(range_tok, base_time)
                return (parsed or [], j + 1 - i + 1)
            except Exception:
                pass

        return None

    def _merge_and_inheritance(self, i, tokens, base_time):  # noqa: C901
        """等价抽取：和连接的继承逻辑"""
        n = len(tokens)
        cur = tokens[i]
        j = i + 1
        if j >= n or tokens[j].get("type") != "and":
            return None
        k = j + 1
        if k >= n:
            return None

        # time_utc + and + time_utc
        if cur.get("type") == "time_utc" and tokens[k].get("type") == "time_utc":
            try:
                inherit_keys = [
                    "noon",
                    "year",
                    "month",
                    "day",
                    "offset_day",
                    "offset_direction",
                ]
                for key in inherit_keys:
                    if key in cur and key not in tokens[k]:
                        tokens[k][key] = cur[key]
            except Exception:
                pass
            return None

        # time_relative + and + time_utc/time_relative
        if cur.get("type") == "time_relative" and tokens[k].get("type") in (
            "time_utc",
            "time_relative",
        ):
            try:
                right = tokens[k]
                right["type"] = "time_relative"
                for key in (
                    "offset_year",
                    "offset_month",
                    "offset_day",
                    "offset_direction",
                    "noon",
                ):
                    if key in cur and key not in right:
                        right[key] = cur[key]
            except Exception:
                pass
            return None

        return None

    def _merge_relative_utc_noon_conflict(self, i, tokens, base_time):
        """
        处理时段词冲突：time_relative(有noon) + time_utc(有noon且更精确)
        例如："明天早上凌晨3:00" → 优先使用"凌晨3:00"，继承"明天"的日期偏移

        泛化：适用于所有"相对日期+时段词+精确时间"的场景
        """
        n = len(tokens)
        if i + 1 >= n:
            return None

        cur = tokens[i]
        next1 = tokens[i + 1]

        # 检查：time_relative(有noon和日期偏移) + time_utc(有noon和hour)
        if (
            cur.get("type") == "time_relative"
            and cur.get("noon")  # 有时段词
            and (
                cur.get("offset_day") or cur.get("offset_month") or cur.get("offset_year")
            )  # 有日期偏移
            and next1.get("type") == "time_utc"
            and next1.get("noon")  # 也有时段词
            and next1.get("hour")  # 有精确小时，更精确
        ):
            try:
                # 优先使用time_utc的精确时间，继承time_relative的日期偏移
                merged_token = dict(next1)  # 以time_utc为基础
                # 继承日期偏移
                if cur.get("offset_day"):
                    merged_token["offset_day"] = cur.get("offset_day")
                if cur.get("offset_month"):
                    merged_token["offset_month"] = cur.get("offset_month")
                if cur.get("offset_year"):
                    merged_token["offset_year"] = cur.get("offset_year")

                # 解析合并后的token
                utc_parser = self.parsers.get("time_utc")
                if utc_parser:
                    result = utc_parser.parse(merged_token, base_time)
                    if result:
                        return (result, 2)  # 消耗2个token
            except Exception as e:
                self.logger.debug(f"Error in _merge_relative_utc_noon_conflict: {e}")

        return None

    def _merge_relative_hour_month_range(self, i, tokens, base_time):
        """等价抽取：相对时间 + hour + month 区间合并"""
        n = len(tokens)
        cur = tokens[i]
        if not (cur.get("type") == "time_relative"):
            return None
        j = i + 1
        k = j + 1
        if not (j < n and tokens[j].get("type") == "time_between" and "hour" in tokens[j]):
            return None
        if not (k < n and tokens[k].get("type") == "time_between" and "month" in tokens[k]):
            return None

        try:
            hour_tok = dict(tokens[j])
            month_tok = dict(tokens[k])

            range_tok = {
                "type": "time_between",
                "raw_type": "utc",
                "month": hour_tok.get("hour"),
                "month_end": month_tok.get("month"),
            }

            relative_parser = self.parsers["time_relative"]
            adjusted_base = adjust_base_for_relative(cur, base_time, relative_parser)

            between_parser = self.parsers["time_between"]
            parsed = safe_parse(between_parser, range_tok, adjusted_base)
            return (parsed or [], 3) if parsed else None
        except Exception:
            pass

        return None

    def _merge_utc_year_hour_month_range(self, i, tokens, base_time):
        """等价抽取：UTC年份 + hour + month 区间合并"""
        n = len(tokens)
        cur = tokens[i]
        if not (cur.get("type") == "time_utc" and "year" in cur):
            return None
        j = i + 1
        k = j + 1
        if not (j < n and tokens[j].get("type") == "time_between" and "hour" in tokens[j]):
            return None
        if not (k < n and tokens[k].get("type") == "time_between" and "month" in tokens[k]):
            return None

        try:
            hour_tok = dict(tokens[j])
            month_tok = dict(tokens[k])

            range_tok = {
                "type": "time_between",
                "raw_type": "utc",
                "year": cur.get("year"),
                "month": hour_tok.get("hour"),
                "month_end": month_tok.get("month"),
            }

            between_parser = self.parsers["time_between"]
            parsed = safe_parse(between_parser, range_tok, base_time)
            return (parsed or [], 3) if parsed else None
        except Exception:
            pass

        return None
