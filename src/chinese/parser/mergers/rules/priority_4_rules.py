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
    build_range_from_endpoints,
    normalize_year_in_token,
    safe_parse_with_jump,
)


class Priority4Rules(BaseRule):
    """Priority 4: 节假日和时间组合规则"""

    def try_merge(
        self, i: int, tokens: List[Dict[str, Any]], base_time: datetime
    ) -> Optional[Tuple[List, int]]:
        """
        Try to merge based on Priority 4 rules

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

        # 8. time_utc(year) + time_holiday 相关处理
        result = self._merge_utc_year_holiday(i, tokens, base_time)
        if result is not None:
            return result

        # 8a. time_holiday + time_utc(noon) 相关处理
        # 例如："中秋节早上" -> 中秋节 + 早上
        result = self._merge_holiday_with_noon(i, tokens, base_time)
        if result is not None:
            return result

        # 8b. time_lunar + time_utc(noon, hour) 相关处理
        # 例如："农历8月十五晚8点" -> 农历8月15日 + 晚上8点
        result = self._merge_lunar_with_noon(i, tokens, base_time)
        if result is not None:
            return result

        # 8b2. time_utc(special_time) + time_utc(noon, hour) 相关处理
        # 例如："2025年第一天早上8点半" -> 2025-01-01 + 早上8点半
        result = self._merge_special_time_with_noon(i, tokens, base_time)
        if result is not None:
            return result

        return None

    def _merge_utc_year_holiday(self, i, tokens, base_time):  # noqa: C901
        """合并UTC年份+节假日相关处理"""
        n = len(tokens)
        cur = tokens[i]

        if not (cur.get("type") == "time_utc" and "year" in cur):
            return None

        j = i + 1
        if j >= n or tokens[j].get("type") != "time_holiday":
            return None

        # 情况1：time_utc(year) + time_holiday → 指定年份的节假日
        # 情况1a：time_utc(year) + time_holiday + time_utc(noon, hour, minute) → 指定年份节假日的具体时间
        if j + 1 < n and tokens[j + 1].get("type") == "time_utc" and "noon" in tokens[j + 1]:
            # 复合情况：年份 + 节假日 + 具体时间
            year_val = normalize_year_in_token(cur)
            if year_val is None:
                return None

            holiday_tok = dict(tokens[j])
            holiday_tok["year"] = str(year_val)

            # 解析节假日获取日期
            holiday_parser = self.parsers.get("time_holiday")
            if not holiday_parser:
                return None

            holiday_result = holiday_parser.parse(holiday_tok, base_time)
            if not holiday_result or not holiday_result[0]:
                return None

            # 获取节假日的日期
            holiday_date_str = holiday_result[0][0]
            holiday_date = datetime.fromisoformat(holiday_date_str.replace("Z", "+00:00"))

            # 构造带日期信息的时间token
            time_token = tokens[j + 1]
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

            return (time_result, 3)  # 跳过三个token

        elif (
            j + 1 >= n or tokens[j + 1].get("type") != "char" or tokens[j + 1].get("value") != "到"
        ):
            # 简单情况：单个节假日
            year_val = normalize_year_in_token(cur)
            if year_val is None:
                return None

            holiday_tok = dict(tokens[j])
            holiday_tok["year"] = str(year_val)

            holiday_parser = self.parsers.get("time_holiday")
            return safe_parse_with_jump(holiday_parser, holiday_tok, base_time, 2)

        # 情况2：time_utc(year) + time_holiday + 到 + time_utc(year) + time_holiday → 跨年节假日区间
        k = j + 1  # '到'
        second_utc_idx = k + 1  # 第二个time_utc
        second_holiday_idx = second_utc_idx + 1  # 第二个time_holiday

        if (
            second_utc_idx < n
            and tokens[second_utc_idx].get("type") == "time_utc"
            and "year" in tokens[second_utc_idx]
            and second_holiday_idx < n
            and tokens[second_holiday_idx].get("type") == "time_holiday"
        ):

            left_year = normalize_year_in_token(cur)
            right_year = normalize_year_in_token(tokens[second_utc_idx])

            if left_year is None or right_year is None:
                return None

            left_holiday = dict(tokens[j])
            right_holiday = dict(tokens[second_holiday_idx])

            holiday_parser = self.parsers.get("time_holiday")
            if holiday_parser:
                left_base = base_time.replace(year=left_year)
                right_base = base_time.replace(year=right_year)

                left_res = safe_parse(holiday_parser, left_holiday, left_base)
                right_res = safe_parse(holiday_parser, right_holiday, right_base)

                rng = build_range_from_endpoints(left_res, right_res)
                if rng:
                    return (rng, 5)

        return None

    def _merge_holiday_with_noon(self, i, tokens, base_time):
        """
        合并 time_holiday + time_utc(noon) 模式
        例如："中秋节早上" -> 中秋节 + 早上
        """
        n = len(tokens)
        if i + 1 >= n:
            return None

        cur = tokens[i]
        next_token = tokens[i + 1]

        # 检查是否是 time_holiday + time_utc(noon) 模式
        if (
            cur.get("type") == "time_holiday"
            and next_token.get("type") == "time_utc"
            and "noon" in next_token
        ):

            try:
                # 解析节假日获取日期
                holiday_parser = self.parsers.get("time_holiday")
                if not holiday_parser:
                    return None

                holiday_result = holiday_parser.parse(cur, base_time)
                if not holiday_result or not holiday_result[0]:
                    return None

                # 获取节假日的日期
                holiday_date_str = holiday_result[0][0]
                holiday_date = datetime.fromisoformat(holiday_date_str.replace("Z", "+00:00"))

                # 解析时间段获取时间范围
                noon_token = dict(next_token)
                noon_token["year"] = str(holiday_date.year)
                noon_token["month"] = str(holiday_date.month)
                noon_token["day"] = str(holiday_date.day)

                utc_parser = self.parsers.get("time_utc")
                if not utc_parser:
                    return None

                noon_result = utc_parser.parse(noon_token, base_time)
                if not noon_result or not noon_result[0]:
                    return None

                return (noon_result, 2)  # 跳过两个token

            except Exception as e:
                self.logger.debug(f"Error in _merge_holiday_with_noon: {e}")
                return None

        return None

    def _merge_lunar_with_noon(self, i, tokens, base_time):
        """
        合并 time_lunar + time_utc(noon, hour) 模式
        例如："农历8月十五晚8点" -> 农历8月15日 + 晚上8点
        """
        n = len(tokens)
        if i + 1 >= n:
            return None

        cur = tokens[i]
        next_token = tokens[i + 1]

        # 检查是否是 time_lunar + time_utc(noon, hour) 模式
        if (
            cur.get("type") == "time_lunar"
            and next_token.get("type") == "time_utc"
            and "hour" in next_token
        ):

            try:
                # 解析农历日期获取阳历日期
                lunar_parser = self.parsers.get("time_lunar")
                if not lunar_parser:
                    return None

                lunar_result = lunar_parser.parse(cur, base_time)
                if not lunar_result or not lunar_result[0]:
                    return None

                # 获取农历对应的阳历日期
                lunar_date_str = lunar_result[0][0]
                lunar_date = datetime.fromisoformat(lunar_date_str.replace("Z", "+00:00"))

                # 构造带日期信息的时间token
                time_with_date = dict(next_token)
                time_with_date["year"] = str(lunar_date.year)
                time_with_date["month"] = str(lunar_date.month)
                time_with_date["day"] = str(lunar_date.day)

                # 解析具体时间
                utc_parser = self.parsers.get("time_utc")
                if not utc_parser:
                    return None

                time_result = utc_parser.parse(time_with_date, base_time)
                if not time_result or not time_result[0]:
                    return None

                return (time_result, 2)  # 跳过两个token

            except Exception as e:
                self.logger.debug(f"Error in _merge_lunar_with_noon: {e}")
                return None

        return None

    def _merge_special_time_with_noon(self, i, tokens, base_time):
        """
        合并 time_utc(special_time) + time_utc(noon, hour) 模式
        例如："2025年第一天早上8点半" -> 2025-01-01T08:30:00Z
        """
        n = len(tokens)
        if i + 1 >= n:
            return None

        cur = tokens[i]
        next_token = tokens[i + 1]

        # 检查是否是 time_utc(special_time) + time_utc(noon/hour/minute) 模式
        if (
            cur.get("type") == "time_utc"
            and "special_time" in cur
            and next_token.get("type") == "time_utc"
            and ("noon" in next_token or "hour" in next_token or "minute" in next_token)
        ):

            try:
                # 先解析special_time获取日期
                utc_parser = self.parsers.get("time_utc")
                if not utc_parser:
                    return None

                special_result = utc_parser.parse(cur, base_time)
                if not special_result or not special_result[0]:
                    return None

                # 获取special_time对应的日期
                special_date_str = special_result[0][0]
                special_date = datetime.fromisoformat(special_date_str.replace("Z", "+00:00"))

                # 构造带日期信息的时间token（只添加日期字段，不带special_time）
                time_token = dict(next_token)
                time_token["year"] = str(special_date.year)
                time_token["month"] = str(special_date.month)
                time_token["day"] = str(special_date.day)

                # 解析带日期信息的时间
                time_result = utc_parser.parse(time_token, base_time)
                if not time_result or not time_result[0]:
                    return None

                return (time_result, 2)  # 跳过两个token

            except Exception as e:
                self.logger.debug(f"Error in _merge_special_time_with_noon: {e}")
                return None

        return None
