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

import calendar
from .base_merger import BaseMerger
from ..merge_utils import (
    safe_parse,
    build_range_from_endpoints,
)
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from ....core.logger import get_logger


class PeriodMerger(BaseMerger):
    """
    时期合并器 - 简化版

    负责处理时期和节假日相关的合并逻辑，包括：
    - 完整时期范围合并
    - 节假日合并
    - 月初/月末处理
    """

    def __init__(self, parsers):
        """初始化时期合并器"""
        super().__init__(parsers)
        self.logger = get_logger(__name__)  # noqa: F841

    def try_merge(self, i, tokens, base_time):  # noqa: C901
        """
        尝试合并时期相关的表达式

        Args:
            i (int): 当前token索引
            tokens (list): token列表
            base_time (datetime): 基准时间

        Returns:
            tuple: (合并结果列表, 跳跃的token数量) 或 None
        """
        # 1. 完整时期范围合并
        result = self._merge_period_full_range(i, tokens, base_time)
        if result is not None:
            return result

        # 2. 阳历月初合并
        result = self._merge_utc_chu(i, tokens, base_time)
        if result is not None:
            return result

        # 3. 阳历年底合并
        result = self._merge_utc_di(i, tokens, base_time)
        if result is not None:
            return result

        # 4. 农历月初合并
        result = self._merge_lunar_chu(i, tokens, base_time)
        if result is not None:
            return result

        # 5. 旬期区间合并
        result = self._merge_period_range(i, tokens, base_time)
        if result is not None:
            return result

        # 6. 年份+季度+初/末（三元组合）
        result = self._merge_year_quarter_chu_mo(i, tokens, base_time)
        if result is not None:
            return result

        # 7. 季度+初/末
        result = self._merge_quarter_chu_mo(i, tokens, base_time)
        if result is not None:
            return result

        # 8. 年份+季节
        result = self._merge_year_season(i, tokens, base_time)
        if result is not None:
            return result

        # 9. 年份+半年
        result = self._merge_year_half_year(i, tokens, base_time)
        if result is not None:
            return result

        # 10. 年份+伊始
        result = self._merge_year_yishi(i, tokens, base_time)
        if result is not None:
            return result

        # 11. 相对年份+初/末
        result = self._merge_relative_year_chu_mo(i, tokens, base_time)
        if result is not None:
            return result

        # 12. 年份+前N个月/周/天合并
        # 例如："今年前两个月" → 今年1-2月
        result = self._merge_year_forward_period(i, tokens, base_time)
        if result is not None:
            return result

        return None

    def _merge_period_full_range(self, i, tokens, base_time):  # noqa: C901
        """
        处理"X + 这一年/月/周/天"等表达式，返回完整时间范围

        模式：time_period(offset_direction=0, offset=1, unit=year/month/week/day)

        基本用法：
        - "这一年" → 今年整年 (1月1日 - 12月31日)
        - "这一月" → 本月整月 (1日 - 月末)
        - "这一周" → 本周整周 (周一 - 周日)
        - "这一天" → 今天整天 (00:00:00 - 23:59:59)

        组合用法：
        - "2022年这一年" → 2022年整年
        - "去年这一年" → 去年整年
        - "明天这一天" → 明天整天
        - "后天这一天" → 后天整天
        - "上个月这一月" → 上个月整月
        """
        cur = tokens[i]

        # 检查是否匹配"这一X"模式
        if (
            cur.get("type") == "time_period"
            and cur.get("offset_direction") == "0"  # "这" = 当前
            and cur.get("offset") == "1"  # "一"
            and cur.get("unit") in ["year", "month", "week", "day"]
        ):

            try:
                unit = cur.get("unit")

                # 检查前面是否有时间修饰词
                year_val = None
                month_val = None
                day_offset = 0
                month_offset = 0
                year_offset = 0

                if i > 0:
                    prev_tok = tokens[i - 1]
                    prev_type = prev_tok.get("type")

                    # 1. 前面是具体年份：2022年这一年
                    if prev_type == "time_utc" and prev_tok.get("year"):
                        from ..merge_utils import normalize_year

                        year_val = normalize_year(int(prev_tok.get("year")))
                        if prev_tok.get("month"):
                            month_val = int(prev_tok.get("month"))

                    # 2. 前面是相对年份：去年这一年、明年这一年
                    elif prev_type == "time_relative" and prev_tok.get("offset_year"):
                        year_offset = int(prev_tok.get("offset_year"))
                        if prev_tok.get("month"):
                            month_val = int(prev_tok.get("month"))

                    # 3. 前面是相对月份：上个月这一月
                    elif prev_type == "time_relative" and prev_tok.get("offset_month"):
                        month_offset = int(prev_tok.get("offset_month"))

                    # 4. 前面是相对日期：明天这一天、后天这一天、昨天这一天
                    elif prev_type == "time_relative" and prev_tok.get("offset_day"):
                        day_offset = int(prev_tok.get("offset_day"))

                # 计算目标时间
                target_time = base_time

                # 应用偏移
                if year_offset != 0:
                    target_time = target_time + relativedelta(years=year_offset)
                if month_offset != 0:
                    target_time = target_time + relativedelta(months=month_offset)
                if day_offset != 0:
                    target_time = target_time + timedelta(days=day_offset)

                # 应用具体值
                if year_val is not None:
                    target_time = target_time.replace(year=year_val)
                if month_val is not None:
                    target_time = target_time.replace(month=month_val)

                # 根据单位返回完整范围
                period_parser = self.parsers.get("time_period")

                if unit == "year":
                    start_of_range, end_of_range = period_parser._get_year_range(target_time)
                elif unit == "month":
                    start_of_range, end_of_range = period_parser._get_month_range(target_time)
                elif unit == "week":
                    # 获取本周范围（周一到周日）
                    weekday = target_time.weekday()  # 0=Monday, 6=Sunday
                    start_of_range = target_time - timedelta(days=weekday)
                    start_of_range = start_of_range.replace(hour=0, minute=0, second=0)
                    end_of_range = start_of_range + timedelta(days=6)
                    end_of_range = end_of_range.replace(hour=23, minute=59, second=59)
                elif unit == "day":
                    start_of_range, end_of_range = period_parser._get_day_range(target_time)
                else:
                    return None

                result = period_parser._format_time_result(start_of_range, end_of_range)

                if result:
                    return (result, 1)  # 消耗1个token

            except Exception:
                pass

        # 检查是否匹配"这X个月/年/周/天"模式，转换为"过去X个月/年/周/天"
        if (
            cur.get("type") == "time_period"
            and cur.get("offset_direction") == "0"  # "这" = 当前
            and cur.get("offset")  # 有数字
            and cur.get("offset") != "1"  # 不是"一"
            and cur.get("unit") in ["year", "month", "week", "day"]
        ):

            try:
                unit = cur.get("unit")
                offset_num = int(cur.get("offset"))

                # 转换为"过去X个月/年/周/天"的效果
                # 创建新的token，模拟time_range类型
                range_token = {
                    "type": "time_range",
                    "value": str(offset_num),
                    "unit": unit,
                    "range_type": "ago",
                }

                # 使用time_range解析器处理
                range_parser = self.parsers["time_range"]
                parsed = safe_parse(range_parser, range_token, base_time)
                return (parsed or [], 1) if parsed else None

            except Exception:
                pass

        return None

    def _merge_utc_chu(self, i, tokens, base_time):
        """等价抽取：阳历月初合并"""
        n = len(tokens)
        cur = tokens[i]
        if not (cur.get("type") == "time_utc" and "month" in cur):
            return None
        j = i + 1
        if j >= n or not (tokens[j].get("type") == "char" and tokens[j].get("value") == "初"):
            return None

        period_tok = {
            "type": "time_period",
            "month": cur.get("month"),
            "year": cur.get("year"),
            "month_period": "earlymonth",
        }

        period_parser = self.parsers["time_period"]
        parsed = safe_parse(period_parser, period_tok, base_time)
        return (parsed or [], 2) if parsed else None

    def _merge_utc_di(self, i, tokens, base_time):
        """等价抽取：阳历年底合并"""
        n = len(tokens)
        cur = tokens[i]
        # 检查当前token是否是time_utc类型且有year字段
        if not (cur.get("type") == "time_utc" and "year" in cur):
            return None

        # 检查下一个token是否是'底'字符
        j = i + 1
        if j >= n or not (tokens[j].get("type") == "char" and tokens[j].get("value") == "底"):
            return None

        from ..merge_utils import normalize_year

        year_val = normalize_year(int(cur.get("year")))

        period_tok = {
            "type": "time_period",
            "year": str(year_val),
            "year_period": "lateyear",
        }

        period_parser = self.parsers["time_period"]
        parsed = safe_parse(period_parser, period_tok, base_time)
        return (parsed or [], 2) if parsed else None

    def _merge_lunar_chu(self, i, tokens, base_time):
        """等价抽取：农历月初合并"""
        n = len(tokens)
        cur = tokens[i]
        if not (cur.get("type") == "time_lunar" and "lunar_month" in cur):
            return None
        j = i + 1
        if j >= n or not (tokens[j].get("type") == "char" and tokens[j].get("value") == "初"):
            return None

        lunar_tok = dict(cur)
        lunar_tok["lunar_day"] = "1"  # 月初对应初一到初十，这里设为1
        lunar_tok["month_period"] = "earlymonth"  # 标记为月初

        lunar_parser = self.parsers["time_lunar"]
        parsed = safe_parse(lunar_parser, lunar_tok, base_time)
        return (parsed or [], 2) if parsed else None

    def _merge_period_range(self, i, tokens, base_time):  # noqa: C901
        """等价抽取：time_period 旬期区间合并"""
        n = len(tokens)
        cur = tokens[i]
        if not (cur.get("type") == "time_period"):
            return None
        j = i + 1
        if j >= n or not (
            tokens[j].get("type") == "char"
            and tokens[j].get("value") in {"到", "至", "~", "-", "—", "——"}
        ):
            return None
        k = j + 1

        # 情况A：完整time_period
        if k < n and tokens[k].get("type") == "time_period":
            left_has_period = "month_period" in cur
            right_has_period = "month_period" in tokens[k]
            if left_has_period and right_has_period:
                try:
                    right_tok = dict(tokens[k])
                    left_has_month = any(
                        key in cur for key in ("month", "year", "offset_month", "offset_year")
                    )
                    right_has_month = any(
                        key in right_tok for key in ("month", "year", "offset_month", "offset_year")
                    )

                    # 继承月份/年份信息
                    if left_has_month and not right_has_month:
                        for key in ("month", "year", "offset_month", "offset_year"):
                            if key in cur and key not in right_tok:
                                right_tok[key] = cur[key]

                    period_parser = self.parsers["time_period"]
                    left_res = safe_parse(period_parser, cur, base_time)
                    right_res = safe_parse(period_parser, right_tok, base_time)

                    rng = build_range_from_endpoints(left_res, right_res)
                    if rng:
                        return (rng, 3)
                except Exception:
                    pass

        # 情况B：time_period + 连接词 + char(旬期词)
        elif k < n and tokens[k].get("type") == "char":
            char_value = tokens[k].get("value", "")
            if char_value in {"上", "中", "下"}:
                try:
                    right_tok = dict(cur)
                    period_map = {
                        "上": "earlymonth",
                        "中": "midmonth",
                        "下": "latemonth",
                    }
                    right_tok["month_period"] = period_map.get(char_value, "earlymonth")

                    period_parser = self.parsers["time_period"]
                    left_res = safe_parse(period_parser, cur, base_time)
                    right_res = safe_parse(period_parser, right_tok, base_time)

                    rng = build_range_from_endpoints(left_res, right_res)
                    if rng:
                        return (rng, 3)
                except Exception:
                    pass

        return None

    def _merge_year_quarter_chu_mo(self, i, tokens, base_time):
        """
        合并年份+季度+初/末（三元组合）
        例如：2013年一季度末、去年四季度初
        """
        n = len(tokens)
        if i + 2 >= n:
            return None

        cur = tokens[i]
        next1 = tokens[i + 1]
        next2 = tokens[i + 2]

        # 检查是否是：time_utc/time_relative + time_period(quarter) + char(初/末)
        is_year = cur.get("type") in ["time_utc", "time_relative"]
        is_quarter = next1.get("type") == "time_period" and next1.get("quarter")
        is_chu_mo = next2.get("type") == "char" and next2.get("value") in ["初", "末"]

        if is_year and is_quarter and is_chu_mo:
            try:
                quarter = int(next1.get("quarter"))
                char_value = next2.get("value")

                # 计算季度对应的月份
                if char_value == "初":
                    target_month = (quarter - 1) * 3 + 1
                else:  # 末
                    target_month = quarter * 3

                # 应用年份偏移或绝对年份
                if cur.get("type") == "time_relative" and cur.get("offset_year"):
                    offset_year = int(cur.get("offset_year"))
                    target_time = base_time + relativedelta(years=offset_year)
                    target_time = target_time.replace(
                        month=target_month, day=1, hour=0, minute=0, second=0
                    )
                elif cur.get("type") == "time_utc" and cur.get("year"):
                    from ..merge_utils import normalize_year

                    year_val = normalize_year(int(cur.get("year")))
                    target_time = base_time.replace(
                        year=year_val,
                        month=target_month,
                        day=1,
                        hour=0,
                        minute=0,
                        second=0,
                    )
                else:
                    return None

                # 获取该月的范围
                period_parser = self.parsers.get("time_period")
                start_of_month, end_of_month = period_parser._get_month_range(target_time)
                result = period_parser._format_time_result(start_of_month, end_of_month)

                if result:
                    return (result, 3)  # 消耗3个token
            except Exception:
                pass

        return None

    def _merge_quarter_chu_mo(self, i, tokens, base_time):
        """
        合并季度+初/末
        例如：一季度末、二季度初
        """
        n = len(tokens)
        if i + 1 >= n:
            return None

        cur = tokens[i]
        next_tok = tokens[i + 1]

        # 检查当前token是否是季度
        is_quarter = cur.get("type") == "time_period" and cur.get("quarter")

        # 检查下一个token是否是'初'/'末'
        is_chu_mo = next_tok.get("type") == "char" and next_tok.get("value") in [
            "初",
            "末",
        ]

        if is_quarter and is_chu_mo:
            try:
                quarter = int(cur.get("quarter"))
                char_value = next_tok.get("value")

                # 计算季度对应的月份
                if char_value == "初":
                    target_month = (quarter - 1) * 3 + 1
                else:  # 末
                    target_month = quarter * 3

                # 使用当前年份
                target_time = base_time.replace(
                    month=target_month, day=1, hour=0, minute=0, second=0
                )

                # 获取该月的范围
                period_parser = self.parsers.get("time_period")
                start_of_month, end_of_month = period_parser._get_month_range(target_time)
                result = period_parser._format_time_result(start_of_month, end_of_month)

                if result:
                    return (result, 2)  # 消耗2个token
            except Exception:
                pass

        return None

    def _merge_relative_year_chu_mo(self, i, tokens, base_time):
        """
        合并相对年份+初/末
        例如：明年初、去年末
        """
        n = len(tokens)
        if i + 1 >= n:
            return None

        cur = tokens[i]
        next_tok = tokens[i + 1]

        # 检查当前token是否是相对年份
        is_relative_year = cur.get("type") == "time_relative" and cur.get("offset_year")

        # 检查下一个token是否是'初'/'末'
        is_chu_mo = next_tok.get("type") == "char" and next_tok.get("value") in [
            "初",
            "末",
        ]

        if is_relative_year and is_chu_mo:
            try:
                offset_year = int(cur.get("offset_year"))
                char_value = next_tok.get("value")

                # 计算目标年份
                target_time = base_time + relativedelta(years=offset_year)

                # 根据'初'/'末'设置月份
                if char_value == "初":
                    # 年初：1月1日到2月底
                    start_time = target_time.replace(month=1, day=1, hour=0, minute=0, second=0)
                    last_day_of_feb = calendar.monthrange(target_time.year, 2)[1]
                    end_time = target_time.replace(
                        month=2, day=last_day_of_feb, hour=23, minute=59, second=59
                    )
                    period_parser = self.parsers.get("time_period")
                    result = period_parser._format_time_result(start_time, end_time)
                else:  # 末
                    # 年末：11月1日到12月31日
                    start_time = target_time.replace(month=11, day=1, hour=0, minute=0, second=0)
                    end_time = target_time.replace(month=12, day=31, hour=23, minute=59, second=59)
                    period_parser = self.parsers.get("time_period")
                    result = period_parser._format_time_result(start_time, end_time)
                if result:
                    return (result, 2)  # 消耗2个token
            except Exception:
                pass

        return None

    def _merge_year_season(self, i, tokens, base_time):
        """
        合并年份+季节
        例如：2021年春季、明年夏天、今年秋
        """
        n = len(tokens)
        if i + 1 >= n:
            return None

        cur = tokens[i]
        next1 = tokens[i + 1]

        # 检查是否是年份+季节的组合
        if (
            cur.get("type") in ["time_utc", "time_relative"]
            and next1.get("type") == "time_period"
            and "season" in next1
        ):

            # 创建用于period parser的token
            merged_token = {"type": "time_period", "season": next1.get("season")}

            # 添加年份或年份偏移
            if cur.get("type") == "time_utc" and cur.get("year"):
                merged_token["year"] = cur.get("year")
            elif cur.get("type") == "time_relative" and cur.get("offset_year"):
                merged_token["offset_year"] = cur.get("offset_year")

            # 使用period parser解析季节
            parser = self.parsers.get("time_period")
            if parser:
                result = safe_parse(parser, merged_token, base_time)
                if result:
                    return (result, 2)  # 消耗2个token

        return None

    def _merge_year_half_year(self, i, tokens, base_time):
        """
        合并年份+半年
        例如：2021年上半年、明年下半年
        """
        n = len(tokens)
        if i + 1 >= n:
            return None

        cur = tokens[i]
        next1 = tokens[i + 1]

        # 检查是否是年份+半年的组合
        if (
            cur.get("type") in ["time_utc", "time_relative"]
            and next1.get("type") == "time_period"
            and "half_year" in next1
        ):

            # 创建用于period parser的token
            merged_token = {"type": "time_period", "half_year": next1.get("half_year")}

            # 添加年份或年份偏移
            if cur.get("type") == "time_utc" and cur.get("year"):
                merged_token["year"] = cur.get("year")
            elif cur.get("type") == "time_relative" and cur.get("offset_year"):
                merged_token["offset_year"] = cur.get("offset_year")

            # 使用period parser解析半年
            parser = self.parsers.get("time_period")
            if parser:
                result = safe_parse(parser, merged_token, base_time)
                if result:
                    return (result, 2)  # 消耗2个token

        return None

    def _merge_year_yishi(self, i, tokens, base_time):
        """
        合并年份+伊始
        例如：2022年伊始、明年伊始
        """
        n = len(tokens)
        if i + 1 >= n:
            return None

        cur = tokens[i]
        next1 = tokens[i + 1]

        # 检查是否是年份+伊始的组合
        if (
            cur.get("type") in ["time_utc", "time_relative"]
            and next1.get("type") == "time_period"
            and "yishi" in next1
        ):

            # 创建用于period parser的token
            merged_token = {"type": "time_period", "yishi": next1.get("yishi")}

            # 添加年份或年份偏移
            if cur.get("type") == "time_utc" and cur.get("year"):
                merged_token["year"] = cur.get("year")
            elif cur.get("type") == "time_relative" and cur.get("offset_year"):
                merged_token["offset_year"] = cur.get("offset_year")

            # 使用period parser解析伊始
            parser = self.parsers.get("time_period")
            if parser:
                result = safe_parse(parser, merged_token, base_time)
                if result:
                    return (result, 2)  # 消耗2个token

        return None

    def _merge_year_forward_period(self, i, tokens, base_time):
        """
        处理年份+前N个月/周/天：time_relative(offset_year) + time_period(offset_direction=-1, unit=month/week/day)
        例如："今年前两个月" → 今年1-2月
        
        泛化：适用于"今年/去年/明年 + 前N个月/周/天"的场景
        """
        n = len(tokens)
        if i + 1 >= n:
            return None

        cur = tokens[i]
        next1 = tokens[i + 1]

        # 检查：time_relative(有offset_year) + time_period(offset_direction=-1, unit=month/week/day)
        if (
            cur.get("type") == "time_relative"
            and cur.get("offset_year") is not None  # 有年份偏移
            and next1.get("type") == "time_period"
            and next1.get("offset_direction") == "-1"  # 前N个
            and next1.get("unit") in ["month", "week", "day"]  # 月/周/天
        ):
            try:
                from dateutil.relativedelta import relativedelta
                from datetime import timedelta

                # 计算目标年份
                year_offset = int(cur.get("offset_year", 0))
                target_year = base_time.year + year_offset

                # 将基准时间调整为该年的起始时间
                adjusted_base = base_time.replace(
                    year=target_year, month=1, day=1, hour=0, minute=0, second=0
                )

                # 计算"前N个月/周/天"的范围
                offset_num = int(next1.get("offset", 1))
                unit = next1.get("unit")

                if unit == "month":
                    start_time = adjusted_base  # 1月1日
                    # 计算N月的最后一天
                    end_month = offset_num
                    if end_month == 2:
                        # 2月需要处理闰年
                        last_day = 29 if calendar.isleap(target_year) else 28
                    else:
                        last_day = calendar.monthrange(target_year, end_month)[1]
                    end_time = adjusted_base.replace(month=end_month, day=last_day, hour=23, minute=59, second=59)
                elif unit == "week":
                    start_time = adjusted_base
                    end_time = adjusted_base + timedelta(weeks=offset_num) - timedelta(days=1)
                    end_time = end_time.replace(hour=23, minute=59, second=59)
                elif unit == "day":
                    start_time = adjusted_base
                    end_time = adjusted_base + timedelta(days=offset_num) - timedelta(days=1)
                    end_time = end_time.replace(hour=23, minute=59, second=59)
                else:
                    return None

                # 格式化结果
                period_parser = self.parsers.get("time_period")
                if period_parser:
                    result = period_parser._format_time_result(start_time, end_time)
                    if result:
                        return (result, 2)  # 消耗2个token
            except Exception as e:
                self.logger.debug(f"Error in _merge_year_forward_period: {e}")

        return None
