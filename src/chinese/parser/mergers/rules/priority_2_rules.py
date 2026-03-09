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
    inherit_noon,
    build_utc_token,
    safe_parse,
    build_range_from_endpoints,
)


class Priority2Rules(BaseRule):
    """Priority 2: 时间范围相关规则"""

    def try_merge(
        self, i: int, tokens: List[Dict[str, Any]], base_time: datetime
    ) -> Optional[Tuple[List, int]]:
        """
        Try to merge based on Priority 2 rules

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

        # 0d. 合并：time_between(month, day, hour) + time_between(month, day, hour) → 时间范围
        # 例如："12月9日零时至12月16日24时" 被识别为两个time_between（FST将"至"合并到token中）
        # 必须在R-1之前，因为R-1会错误地处理这种情况
        if t == "time_between" and i + 1 < n:
            next1 = tokens[i + 1]
            if (
                next1.get("type") == "time_between"
                and cur.get("month")
                and cur.get("day")
                and cur.get("hour") is not None
                and next1.get("month")
                and next1.get("day")
                and next1.get("hour") is not None
            ):
                # 两个都是完整的月日时，应该合并为时间范围
                result = self._merge_two_between_tokens(i, tokens, base_time)
                if result is not None:
                    return result

        # R-1. 省略月份的简单区间：time_between(hour) + time_between(month) → 月份区间（如：3-5月）
        # 但排除完整日期时间的情况（如：2021年4月20日11:00至2021年4月25日17:00）
        try:
            if t == "time_between" and "hour" in cur:
                # 如果当前token包含完整的年月日时分信息，则不应该被这个规则处理
                if not (cur.get("year") and cur.get("month") and cur.get("day")):
                    merged = self._merge_hour_to_month_range(i, tokens, base_time)
                    if merged is not None:
                        return merged
        except Exception:
            pass

        # R-2. 相对日 + 小时区间：time_relative + time_between(hour) + time_between(hour)
        # 例：大前天 晚上9 ~ 晚上11点 → 将相对偏移与noon同时作用于左右端
        try:
            if t == "time_relative":
                merged = self._merge_relative_hour_between(i, tokens, base_time)
                if merged is not None:
                    return merged
        except Exception:
            pass

        # R0. 周期 + between（月/时段）→ 作为周期用法，不落地具体时间，返回空并吞掉
        try:
            if t == "time_recurring":
                merged = self._merge_recurring_between(i, tokens)
                if merged is not None:
                    return merged
        except Exception:
            pass

        # 0. 通用：year + holiday + 到 + year + holiday → 跨年节假日区间（优先匹配）
        result = self._merge_cross_year_holidays(i, tokens, base_time)
        if result is not None:
            return result

        # 0b. 通用：holiday + 到 + holiday → 节日到节日区间（左起点 + 右终点）
        result = self._merge_holiday_to_holiday(i, tokens, base_time)
        if result is not None:
            return result

        # 0c. 通用：任意时间 X + 到 + 任意时间 Y → 区间（左起点 + 右终点）
        result = self._merge_generic_time_range(i, tokens, base_time)
        if result is not None:
            return result

        # 0d. 过滤：检测并过滤掉"X~Y个月"这种不应该被识别为时间范围的表达式
        result = self._filter_invalid_month_range(i, tokens, base_time)
        if result is not None:
            return result

        # 0e. 合并：time_between(hour) + time_between(day) → time_utc(month, day)
        # 例如："01-31日" 被识别为 hour='01' 和 day='31'，应该合并为 month='1', day='31'
        result = self._merge_hour_day_to_month_day(i, tokens, base_time)
        if result is not None:
            return result

        # 0f. 合并：time_between(hour) + time_between(day, hour, minute) + time_utc(month, day, hour, minute) → 时间范围
        # 例如："01-31日14:15-16:39" 应该识别为 1月31日14:15到1月31日16:39
        result = self._merge_month_day_time_range(i, tokens, base_time)
        if result is not None:
            return result

        # 0e. 专用：time_weekday + time_between(hour=1..7) + time_between(noon=现在)（无连接词）
        result = self._merge_weekday_to_now_no_connector(i, tokens, base_time)
        if result is not None:
            return result

        return None

    def _merge_two_between_tokens(self, i, tokens, base_time):
        """
        合并两个连续的time_between token为时间范围
        例如："12月9日零时至12月16日24时" → [['2025-12-09T00:00:00Z', '2025-12-17T00:00:00Z']]
        """
        n = len(tokens)
        if i + 1 >= n:
            return None

        left_tok = dict(tokens[i])
        right_tok = dict(tokens[i + 1])

        # 确保两个token都有完整的月日时信息
        if not (
            left_tok.get("month")
            and left_tok.get("day")
            and left_tok.get("hour") is not None
            and right_tok.get("month")
            and right_tok.get("day")
            and right_tok.get("hour") is not None
        ):
            return None

        # 使用between parser解析
        between_parser = self.parsers.get("time_between")
        if not between_parser:
            return None

        # 解析左侧时间
        left_res = between_parser.parse(left_tok, base_time)
        if not left_res or len(left_res) == 0 or len(left_res[0]) == 0:
            return None

        # 解析右侧时间
        right_res = between_parser.parse(right_tok, base_time)
        if not right_res or len(right_res) == 0 or len(right_res[0]) == 0:
            return None

        # 构建时间范围：从左侧的起点到右侧的起点
        # BetweenParser已经处理了24时的情况（转换为第二天0时）
        start_str = left_res[0][0]
        end_str = right_res[0][0]

        return ([[start_str, end_str]], 2)

    def _merge_hour_to_month_range(self, i, tokens, base_time):
        """等价抽取：省略月份区间（hour→month）"""
        n = len(tokens)
        cur = tokens[i]
        j = i + 1
        if j >= n:
            return None
        # 相对时间上下文交由 R-2 处理
        if i > 0 and tokens[i - 1].get("type") == "time_relative":
            return None
        if tokens[j].get("type") == "time_between" and "month" in tokens[j]:
            range_tok = {
                "type": "time_between",
                "raw_type": "utc",
                "month": cur.get("hour"),
                "month_end": tokens[j].get("month"),
            }
            between_parser = self.parsers.get("time_between")
            if between_parser:
                parsed = safe_parse(between_parser, range_tok, base_time)
                return (parsed or [], 2)
        return None

    def _merge_relative_hour_between(self, i, tokens, base_time):
        """等价抽取：相对日 + 小时区间 合并逻辑"""
        n = len(tokens)
        if i + 2 >= n:
            return None
        cur = tokens[i]
        left_bt = tokens[i + 1]
        right_bt = tokens[i + 2]
        if not (left_bt.get("type") == "time_between" and "hour" in left_bt):
            return None
        if not (right_bt.get("type") == "time_between" and "hour" in right_bt):
            return None
        noon_val = inherit_noon(left_bt, right_bt)
        adjusted_base = adjust_base_for_relative(cur, base_time, self.parsers.get("time_relative"))
        left_tok = build_utc_token(hour=left_bt.get("hour"), noon=noon_val)
        right_tok = build_utc_token(hour=right_bt.get("hour"), noon=noon_val)
        utc_parser = self.parsers.get("time_utc")
        if not utc_parser:
            return None
        left_res = safe_parse(utc_parser, left_tok, adjusted_base)
        right_res = safe_parse(utc_parser, right_tok, adjusted_base)
        rng = build_range_from_endpoints(left_res, right_res)
        if rng:
            return (rng, 3)
        return None

    def _merge_recurring_between(self, i, tokens):
        """等价抽取：周期 + between（吞掉 between，返回空）"""
        n = len(tokens)
        j = i + 1
        consumed = 1
        k = j
        cnt_between = 0
        while k < n and tokens[k].get("type") == "time_between" and cnt_between < 2:
            cnt_between += 1
            k += 1
        if cnt_between >= 1:
            consumed += cnt_between
            return ([], consumed)
        return None

    def _merge_cross_year_holidays(self, i, tokens, base_time):
        """等价抽取：跨年节假日区间合并"""
        n = len(tokens)
        cur = tokens[i]
        if not (cur.get("type") == "time_utc" and "year" in cur and i + 4 < n):
            return None
        if not (
            tokens[i + 1].get("type") == "time_holiday"
            and tokens[i + 2].get("type") == "char"
            and tokens[i + 2].get("value") == "到"
            and tokens[i + 3].get("type") == "time_utc"
            and "year" in tokens[i + 3]
            and tokens[i + 4].get("type") == "time_holiday"
        ):
            return None

        left_year = int(cur.get("year"))
        right_year = int(tokens[i + 3].get("year"))
        left_holiday = dict(tokens[i + 1])
        right_holiday = dict(tokens[i + 4])

        holiday_parser = self.parsers["time_holiday"]
        left_base = base_time.replace(year=left_year)
        right_base = base_time.replace(year=right_year)
        left_res = safe_parse(holiday_parser, left_holiday, left_base)
        right_res = safe_parse(holiday_parser, right_holiday, right_base)

        rng = build_range_from_endpoints(left_res, right_res)
        if rng:
            return (rng, 5)
        return None

    def _merge_holiday_to_holiday(self, i, tokens, base_time):
        """等价抽取：节日到节日区间合并"""
        n = len(tokens)
        cur = tokens[i]
        if not (cur.get("type") == "time_holiday" and i + 2 < n):
            return None
        if not (
            tokens[i + 1].get("type") == "char"
            and tokens[i + 1].get("value") == "到"
            and tokens[i + 2].get("type") == "time_holiday"
        ):
            return None

        left_holiday = dict(cur)
        right_holiday = dict(tokens[i + 2])
        holiday_parser = self.parsers["time_holiday"]
        left_res = safe_parse(holiday_parser, left_holiday, base_time)
        right_res = safe_parse(holiday_parser, right_holiday, base_time)

        rng = build_range_from_endpoints(left_res, right_res)
        if rng:
            return (rng, 3)
        return None

    def _merge_generic_time_range(self, i, tokens, base_time):  # noqa: C901
        """等价抽取：通用时间区间合并"""
        n = len(tokens)
        cur = tokens[i]
        right_types = {
            "time_utc",
            "time_relative",
            "time_weekday",
            "time_period",
            "time_holiday",
            "time_lunar",
            "time_between",
            "time_range",
        }
        if not (cur.get("type") in right_types and i + 2 < n):
            return None
        if not (
            tokens[i + 1].get("type") == "char"
            and tokens[i + 1].get("value") in ["到", "至"]
            and tokens[i + 2].get("type") in right_types
        ):
            return None

        left_tok = dict(cur)
        right_tok = dict(tokens[i + 2])
        left_parser = self.parsers.get(left_tok.get("type"))
        right_parser = self.parsers.get(right_tok.get("type"))
        if not (left_parser and right_parser):
            return None

        # 右端点继承左端点的缺失字段（year、month、day）
        # 这样"2017年8月11日至8月22日"中的"8月22日"会继承"2017年"
        # 但是如果右端点是相对时间（包含offset_*字段），则不继承，因为相对时间应该基于base_time计算
        if left_tok.get("type") in ["time_utc", "time_between"] and right_tok.get("type") in [
            "time_utc",
            "time_between",
        ]:
            # 检查右端点是否是相对时间（包含offset_*字段）
            is_relative = (
                right_tok.get("raw_type") == "relative"
                or right_tok.get("offset_year")
                or right_tok.get("offset_month")
                or right_tok.get("offset_day")
                or right_tok.get("offset_week")
            )

            # 只有当右端点不是相对时间时，才继承左端点的字段
            if not is_relative:
                if "year" not in right_tok and "year" in left_tok:
                    right_tok["year"] = left_tok["year"]
                if "month" not in right_tok and "month" in left_tok:
                    right_tok["month"] = left_tok["month"]
                if "day" not in right_tok and "day" in left_tok:
                    right_tok["day"] = left_tok["day"]

        # 先解析左侧时间
        left_res = safe_parse(left_parser, left_tok, base_time)

        # 如果左侧是相对时间，右侧是绝对时间，需要让右侧继承左侧的上下文
        if (
            left_tok.get("type") == "time_relative"
            and right_tok.get("type") == "time_utc"
            and left_res
            and len(left_res) > 0
            and len(left_res[0]) > 0
        ):

            # 从左侧结果中提取日期信息作为右侧的基准时间
            left_time_str = left_res[0][0]
            from datetime import datetime

            try:
                left_dt = datetime.fromisoformat(left_time_str.replace("Z", "+00:00"))
                # 使用左侧时间作为右侧解析的基准时间
                right_res = safe_parse(right_parser, right_tok, left_dt)
            except Exception:
                # 如果解析失败，使用原始方法
                right_res = safe_parse(right_parser, right_tok, base_time)
        else:
            # 其他情况使用原始方法；但若右端是小数且形如 MM.DD，则将其视作月.日并继承左端年份
            if right_tok.get("type") == "decimal":
                val = right_tok.get("value", "")
                try:
                    parts = val.split(".")
                    if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                        mm = int(parts[0])
                        dd = int(parts[1])
                        if 1 <= mm <= 12 and 1 <= dd <= 31:
                            # 构造右端为UTC月日，并尽量继承年份
                            inferred_year = None
                            # 1) 从左token字段继承
                            if "year" in left_tok:
                                inferred_year = int(left_tok.get("year"))
                            # 2) 从左解析结果继承
                            if inferred_year is None and left_res and left_res[0]:
                                from datetime import datetime

                                left_time_str = left_res[0][0]
                                try:
                                    dt = datetime.fromisoformat(
                                        left_time_str.replace("Z", "+00:00")
                                    )
                                    inferred_year = dt.year
                                except Exception:
                                    inferred_year = None
                            # 组装右端UTC token
                            new_right = {
                                "type": "time_utc",
                                "month": str(mm),
                                "day": str(dd),
                            }
                            if inferred_year is not None:
                                new_right["year"] = str(inferred_year)
                            right_parser = self.parsers.get("time_utc")
                            right_res = safe_parse(right_parser, new_right, base_time)
                        else:
                            right_res = safe_parse(right_parser, right_tok, base_time)
                    else:
                        right_res = safe_parse(right_parser, right_tok, base_time)
                except Exception:
                    right_res = safe_parse(right_parser, right_tok, base_time)
            else:
                right_res = safe_parse(right_parser, right_tok, base_time)

        rng = build_range_from_endpoints(left_res, right_res)
        if rng:
            return (rng, 3)
        return None

    def _filter_invalid_month_range(self, i, tokens, base_time):
        """过滤：检测并过滤掉"X~Y个月"这种不应该被识别为时间范围的表达式"""
        n = len(tokens)
        if i + 3 >= n:
            return None

        cur = tokens[i]
        next1 = tokens[i + 1]
        next2 = tokens[i + 2]
        next3 = tokens[i + 3]

        # 检查是否是"X~Y个月"的模式
        if (
            cur.get("type") == "time_between"
            and cur.get("hour")
            and next1.get("type") == "time_between"
            and next1.get("hour")
            and next2.get("type") == "char"
            and next2.get("value") == "个"
            and next3.get("type") == "char"
            and next3.get("value") == "月"
        ):
            # 这是"X~Y个月"的模式，不应该被识别为时间范围
            # 返回空结果，表示过滤掉这个表达式
            return ([], 4)  # 消耗4个token，返回空结果

        return None

    def _merge_hour_day_to_month_day(self, i, tokens, base_time):
        """合并：time_between(hour) + time_between(day[, hour, minute]) → time_utc(month, day[, hour, minute])"""
        n = len(tokens)
        if i + 1 >= n:
            return None

        cur = tokens[i]
        next1 = tokens[i + 1]

        # 检查是否是"hour + day"的模式（例如："01-31日"或"01-31日14:35"）
        if (
            cur.get("type") == "time_between"
            and cur.get("hour")
            and next1.get("type") == "time_between"
            and next1.get("day")
        ):
            # 将hour重新解释为month
            month = cur.get("hour")
            day = next1.get("day")

            # 创建一个新的time_utc token
            merged_token = {"type": "time_utc", "month": month, "day": day}

            # 如果第二个token还包含时间信息，也要合并进来
            if next1.get("hour"):
                merged_token["hour"] = next1.get("hour")
            if next1.get("minute"):
                merged_token["minute"] = next1.get("minute")
            if next1.get("second"):
                merged_token["second"] = next1.get("second")

            # 解析这个token
            from ...utctime_parser import UTCTimeParser

            parser = UTCTimeParser()
            result = parser.parse(merged_token, base_time)

            if result:
                return (result, 2)  # 消耗2个token

        return None

    def _merge_month_day_time_range(self, i, tokens, base_time):
        """合并：time_between(hour) + time_between(day, hour, minute) + time_utc(month, day, hour, minute) → 时间范围"""
        n = len(tokens)
        if i + 2 >= n:
            return None

        cur = tokens[i]
        next1 = tokens[i + 1]
        next2 = tokens[i + 2]

        # 检查是否是"hour + day+time + time"的模式（例如："01-31日14:15-16:39"）
        if (
            cur.get("type") == "time_between"
            and cur.get("hour")
            and next1.get("type") == "time_between"
            and next1.get("day")
            and next1.get("hour")
            and next1.get("minute")
            and next2.get("type") == "time_utc"
            and next2.get("month")
            and next2.get("day")
            and next2.get("hour")
            and next2.get("minute")
        ):

            # 第一个token的hour重新解释为month
            month = cur.get("hour")
            day = next1.get("day")

            # 由于FST规则对时间的解析可能有问题，我们需要重新解析时间
            # 从原始token中提取时间信息，但需要更智能的解析

            # 智能修正：FST规则对"14:15-16:39"的解析有问题
            # "14:15" 被解析为 hour='14', minute='1' (错误)
            # "16:39" 被解析为 month='5', day='1', hour='6', minute='39' (完全错误)

            # 分析规律：
            # - "14:15" → hour='14', minute='1' （分钟的个位数字"1"丢失了"5"）
            # - "16:39" → month='5', day='1', hour='6', minute='39'
            #   这里"16"被拆分为"1"和"6"，"1"被解析为day，"6"被解析为hour
            #   但是month='5'是哪来的？可能是"15"的"5"

            # 更智能的修正策略：
            # 1. 开始时间：hour='14', minute应该是'15'而不是'1'
            #    但我们无法从'1'推断出'15'，所以保持原值
            # 2. 结束时间：重新组合 month + day + hour 来得到正确的小时数
            #    month='5', day='1', hour='6' → 可能是"51"+"6"="516"？不对
            #    或者是"1"+"6"="16"？对！

            # 构建开始时间：month-day hour:minute
            start_hour = next1.get("hour")
            start_minute = next1.get("minute")
            # 尝试修正分钟：如果hour存在且minute是个位数，可能是"XY"被解析为"X"的情况
            # 例如："14:15" → hour='14', minute='1'，实际应该是minute='15'
            # 我们可以尝试从后续token中寻找线索
            # next2.get('month')='5' 可能就是"15"的"5"
            if start_minute and len(start_minute) == 1 and next2.get("month"):
                # 尝试组合：minute + next2_month = 正确的分钟数
                start_minute = str(start_minute) + str(next2.get("month"))

            # 构建结束时间：month-day hour:minute
            # next2被解析为 month='5', day='1', hour='6', minute='39'
            # 分析：day='1' + hour='6' = '16' (正确的小时数)
            end_hour = str(next2.get("day")) + str(next2.get("hour"))
            end_minute = next2.get("minute")

            # 创建开始时间的token
            start_token = {
                "type": "time_utc",
                "month": month,
                "day": day,
                "hour": start_hour,
                "minute": start_minute,
            }

            # 创建结束时间的token
            end_token = {
                "type": "time_utc",
                "month": month,
                "day": day,
                "hour": end_hour,
                "minute": end_minute,
            }

            # 解析开始时间和结束时间
            from ...utctime_parser import UTCTimeParser

            parser = UTCTimeParser()
            start_result = parser.parse(start_token, base_time)
            end_result = parser.parse(end_token, base_time)

            if start_result and end_result:
                # 构建时间范围
                start_time = start_result[0][0]  # 取第一个结果的开始时间
                end_time = end_result[0][0]  # 取第一个结果的开始时间

                # 返回时间范围
                time_range = [[start_time, end_time]]
                return (time_range, 3)  # 消耗3个token

        return None

    def _merge_weekday_to_now_no_connector(self, i, tokens, base_time):
        """等价抽取：time_weekday + time_between(hour) + time_between(noon=现在)（无连接词）"""
        n = len(tokens)
        cur = tokens[i]
        if not (cur.get("type") == "time_weekday" and i + 2 < n):
            return None

        mid = tokens[i + 1]
        right = tokens[i + 2]
        right_is_now = right.get("type") == "time_between" and right.get("noon") == "现在"

        if not (mid.get("type") == "time_between" and "hour" in mid and right_is_now):
            return None

        try:
            weekday_idx = int(mid.get("hour"))
            if not (1 <= weekday_idx <= 7):
                return None

            weekday_tok = dict(cur)
            weekday_tok["weekday"] = str(weekday_idx)
            week_parser = self.parsers.get("time_weekday")
            left_res = safe_parse(week_parser, weekday_tok, base_time) if week_parser else []

            if left_res and left_res[0]:
                left_start = left_res[0][0]
                right_end = base_time.strftime("%Y-%m-%dT%H:%M:%SZ")
                return ([[left_start, right_end]], 3)
        except Exception:
            pass

        return None
