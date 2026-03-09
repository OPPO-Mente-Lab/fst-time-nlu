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
    build_range_from_endpoints,
    safe_parse_with_jump,
)
from dateutil.relativedelta import relativedelta


class DateComponentMerger(BaseMerger):
    """
    日期组件合并器 - 简化版

    负责处理日期组件相关的合并逻辑，包括：
    - 星期几相关合并
    - 年份季度合并
    - 日期组件组合
    """

    def __init__(self, parsers):
        super().__init__(parsers)
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

    def try_merge(self, i, tokens, base_time):
        """
        尝试合并日期组件相关的表达式

        Args:
            i (int): 当前token索引
            tokens (list): token列表
            base_time (datetime): 基准时间

        Returns:
            tuple: (合并结果列表, 跳跃的token数量) 或 None
        """
        # 1. 年份+季度合并
        result = self._merge_year_quarter(i, tokens, base_time)
        if result is not None:
            return result

        # 2. 星期几到现在的合并
        result = self._merge_weekday_to_now(i, tokens, base_time)
        if result is not None:
            return result

        # 3. 星期相关组合
        result = self._merge_weekday_combinations(i, tokens, base_time)
        if result is not None:
            return result

        # 4. 相对月份+第N周
        result = self._merge_relative_month_week(i, tokens, base_time)
        if result is not None:
            return result

        # 5. 相对年份+月份+第N周
        result = self._merge_relative_year_month_week(i, tokens, base_time)
        if result is not None:
            return result

        return None

    def _merge_year_quarter(self, i, tokens, base_time):
        """
        合并年份+季度：
        - time_utc(year) + time_period(quarter) → 带年份的季度
        - time_relative(offset_year) + time_period(quarter) → 相对年份的季度

        例如：
        - "2022年首季度" → time_utc(year=2022) + time_period(quarter=1)
        - "明年一季度" → time_relative(offset_year=1) + time_period(quarter=1)
        - "22年一季度" → time_utc(year=22) + time_period(quarter=1)
        """
        n = len(tokens)
        if i + 1 >= n:
            return None

        cur = tokens[i]
        next1 = tokens[i + 1]

        # 检查是否是年份+季度的组合
        if (
            cur.get("type") in ["time_utc", "time_relative"]
            and next1.get("type") == "time_period"
            and "quarter" in next1
        ):

            # 创建用于period parser的token
            merged_token = {"type": "time_period", "quarter": next1.get("quarter")}

            # 添加年份或年份偏移
            if cur.get("type") == "time_utc" and cur.get("year"):
                merged_token["year"] = cur.get("year")
            elif cur.get("type") == "time_relative" and cur.get("offset_year"):
                merged_token["offset_year"] = cur.get("offset_year")

            # 使用period parser解析季度
            parser = self.parsers.get("time_period")
            if parser:
                result = safe_parse(parser, merged_token, base_time)
                if result:
                    return (result, 2)  # 消耗2个token

        return None

    def _merge_weekday_to_now(self, i, tokens, base_time):
        """等价抽取：time_weekday + time_between(hour) + 到 + 现在"""
        n = len(tokens)
        cur = tokens[i]
        if not (cur.get("type") == "time_weekday" and i + 3 < n):
            return None

        mid = tokens[i + 1]
        conn = tokens[i + 2]
        right = tokens[i + 3]

        right_is_now = (right.get("type") == "time_utc" and right.get("noon") == "现在") or (
            right.get("type") == "time_between" and right.get("noon") == "现在"
        )

        if not (
            mid.get("type") == "time_between"
            and "hour" in mid
            and conn.get("type") == "char"
            and conn.get("value") == "到"
            and right_is_now
        ):
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
                return ([[left_start, right_end]], 4)
        except Exception:
            pass

        return None

    def _merge_weekday_combinations(self, i, tokens, base_time):
        """合并weekday相关组合：offset_week + week_day 和 区间形式"""
        n = len(tokens)
        cur = tokens[i]

        # 检查是否是time_weekday且有offset_week
        if not (cur.get("type") == "time_weekday" and "offset_week" in cur):
            return None

        # 情况1：time_weekday(offset_week) + time_weekday(week_day) + 到 + time_weekday(...) → 区间
        if (
            i + 3 < n
            and tokens[i + 1].get("type") == "time_weekday"
            and "week_day" in tokens[i + 1]
            and tokens[i + 2].get("type") == "char"
            and tokens[i + 2].get("value") == "到"
            and tokens[i + 3].get("type") == "time_weekday"
        ):

            left_weekday_tok = {
                "type": "time_weekday",
                "offset_week": cur.get("offset_week"),
                "week_day": tokens[i + 1].get("week_day"),
            }
            right_weekday_tok = dict(tokens[i + 3])

            week_parser = self.parsers.get("time_weekday")
            if week_parser:
                left_res = safe_parse(week_parser, left_weekday_tok, base_time)
                right_res = safe_parse(week_parser, right_weekday_tok, base_time)

                rng = build_range_from_endpoints(left_res, right_res)
                if rng:
                    return (rng, 4)

        # 情况2：time_weekday(offset_week) + time_weekday(week_day) → 单一周的指定星期
        elif (
            i + 1 < n
            and tokens[i + 1].get("type") == "time_weekday"
            and "week_day" in tokens[i + 1]
        ):

            left_weekday_tok = {
                "type": "time_weekday",
                "offset_week": cur.get("offset_week"),
                "week_day": tokens[i + 1].get("week_day"),
            }

            week_parser = self.parsers.get("time_weekday")
            return safe_parse_with_jump(week_parser, left_weekday_tok, base_time, 2)

        return None

    def _merge_relative_month_week(self, i, tokens, base_time):
        """
        合并相对月份+第N周
        例如：本月第2周、下月第三周
        """
        n = len(tokens)
        if i + 3 >= n:
            return None

        cur = tokens[i]
        next_tok = tokens[i + 1]
        third_tok = tokens[i + 2]
        fourth_tok = tokens[i + 3]

        # 检查是否是相对月份
        is_relative_month = cur.get("type") == "time_relative" and cur.get("offset_month")

        # 检查是否是"第N周"模式
        is_di_week = (
            next_tok.get("type") == "char"
            and next_tok.get("value") == "第"
            and third_tok.get("type") == "char"
            and fourth_tok.get("type") == "char"
            and fourth_tok.get("value") in ["周", "星期", "礼拜"]
        )

        if is_relative_month and is_di_week:
            try:
                # 获取周数
                week_num_str = third_tok.get("value")
                if week_num_str in self.chinese_num_map:
                    week_num = self.chinese_num_map[week_num_str]
                else:
                    week_num = int(week_num_str)

                # 获取月份偏移
                offset_month = int(cur.get("offset_month"))

                # 计算目标月份
                target_time = base_time + relativedelta(months=offset_month)
                target_year = target_time.year
                target_month = target_time.month

                # 使用base_parser的方法计算第N周
                utc_parser = self.parsers.get("time_utc")
                start_of_week, end_of_week = utc_parser._get_month_nth_week_range(
                    target_year, target_month, week_num
                )

                result = utc_parser._format_time_result(start_of_week, end_of_week)
                if result:
                    return (result, 4)  # 消耗4个token
            except Exception:
                pass

        return None

    def _merge_relative_year_month_week(self, i, tokens, base_time):
        """
        合并相对年份+月份+第N周
        例如：今年三月第三周、明年七月第2周
        """
        n = len(tokens)
        if i + 1 >= n:
            return None

        cur = tokens[i]
        next_tok = tokens[i + 1]

        # 检查是否是相对年份
        is_relative_year = cur.get("type") == "time_relative" and cur.get("offset_year")

        # 检查下一个token是否是月份+第N周
        is_month_week = (
            next_tok.get("type") == "time_utc"
            and next_tok.get("month")
            and next_tok.get("week_order")
        )

        if is_relative_year and is_month_week:
            try:
                # 获取年份偏移
                offset_year = int(cur.get("offset_year"))

                # 获取月份和周数
                month = int(next_tok.get("month"))
                week_order = int(next_tok.get("week_order"))

                # 计算目标年份
                target_time = base_time + relativedelta(years=offset_year)
                target_year = target_time.year

                # 使用base_parser的方法计算第N周
                utc_parser = self.parsers.get("time_utc")
                start_of_week, end_of_week = utc_parser._get_month_nth_week_range(
                    target_year, month, week_order
                )

                result = utc_parser._format_time_result(start_of_week, end_of_week)
                if result:
                    return (result, 2)  # 消耗2个token
            except Exception:
                pass

        return None
