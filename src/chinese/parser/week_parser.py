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

from datetime import timedelta
from .base_parser import BaseParser


class WeekParser(BaseParser):
    """
    星期时间解析器

    处理与星期相关的时间表达式，如：
    - 周一、周二等具体星期
    - 本周、上周、下周
    - 周末
    - 星期+时间段组合
    """

    def __init__(self):
        """初始化星期解析器"""
        super().__init__()

    def parse(self, token, base_time):
        """
        解析星期相关的时间表达式

        Args:
            token (dict): 时间表达式token，包含week_day、offset_week、noon等字段
            base_time (datetime): 基准时间

        Returns:
            list: 时间范围列表，格式为 [[start_time_str, end_time_str]]
        """
        # 提取token中的关键信息
        week_day_raw = token.get("week_day", "").strip('"')
        week_offset_val = int(token.get("offset_week", 0))
        time_num = self._get_time_num(token)
        noon_str = token.get("noon")

        # 计算目标日期
        target_date = self._calculate_target_date(base_time, week_day_raw, week_offset_val)

        # 处理整周情况
        if week_day_raw == "":
            return self._handle_whole_week(target_date)

        # 处理周末情况
        if "," in week_day_raw:
            return self._handle_weekend(target_date, noon_str)

        # 处理带时间段（noon）的情况
        if noon_str:
            return self._handle_noon_with_time(target_date, noon_str, time_num)

        # 处理只有具体小时的情况
        if (
            time_num
            and "hour" in time_num
            and "minute" not in time_num
            and "second" not in time_num
        ):
            return self._handle_specific_hour(target_date, time_num)

        # 默认返回全天
        return self._get_day_range_formatted(target_date)

    def _calculate_target_date(self, base_time, week_day_raw, week_offset_val):
        """
        计算目标日期
        """
        current_weekday = base_time.weekday() + 1  # 1=周一, 7=周日
        if week_day_raw and "," not in week_day_raw:
            day_diff = int(week_day_raw) - current_weekday + week_offset_val * 7
        else:
            day_diff = 1 - current_weekday + week_offset_val * 7  # 默认周一
        return base_time + timedelta(days=day_diff)

    def _handle_whole_week(self, target_date):
        """
        处理整周情况，返回本周/上周/下周的周一到周日
        """
        start_date, _ = self._get_day_range(target_date)
        end_date = target_date + timedelta(days=6)
        _, end_date = self._get_day_range(end_date)
        return self._format_time_result(start_date, end_date)

    def _handle_weekend(self, base_time, noon_str):
        """
        处理周末情况（周六、周日）
        """
        sat_date = base_time + timedelta(days=5)
        sun_date = base_time + timedelta(days=6)

        if noon_str:
            # 周末下午这类的情况
            sat_start, sat_end = self._parse_noon(sat_date, noon_str)
            sun_start, sun_end = self._parse_noon(sun_date, noon_str)
            return [
                self._format_time_result(sat_start, sat_end)[0],
                self._format_time_result(sun_start, sun_end)[0],
            ]
        else:
            # 普通周末全天情况
            start_date, _ = self._get_day_range(sat_date)
            _, end_date = self._get_day_range(sun_date)
            return self._format_time_result(start_date, end_date)

    def _handle_noon_with_time(self, base_time, noon_str, time_num):
        """
        处理带时间段（noon）和具体时间的情况
        """
        if not time_num or (
            "hour" not in time_num and "minute" not in time_num and "second" not in time_num
        ):
            # 只有时间段，没有具体时间
            start_time, end_time = self._parse_noon(base_time, noon_str)
            return self._format_time_result(start_time, end_time)
        elif "hour" in time_num and "minute" not in time_num and "second" not in time_num:
            # 只有小时，没有分钟和秒
            start_time, _ = self._parse_noon(base_time, noon_str)
            if noon_str in self.noon_time:
                if time_num["hour"] < 12:
                    time_num["hour"] += 12
            target_time = start_time.replace(hour=time_num["hour"], minute=0)
            return self._format_time_result(target_time)
        elif "hour" in time_num and "minute" in time_num:
            # 有小时和分钟
            start_time, _ = self._parse_noon(base_time, noon_str)
            if noon_str in self.noon_time:
                if time_num["hour"] < 12:
                    time_num["hour"] += 12
            target_time = start_time.replace(hour=time_num["hour"], minute=time_num["minute"])
            return self._format_time_result(target_time)
        return self._get_day_range_formatted(base_time)  # Fallback

    def _handle_specific_hour(self, base_time, time_num):
        """
        处理只有具体小时的情况
        """
        start_of_day = base_time.replace(hour=time_num["hour"], minute=0, second=0)
        return self._format_time_result(start_of_day)

    def _get_day_range_formatted(self, target_date):
        """
        获取并格式化一天的开始和结束时间
        """
        start_of_day, end_of_day = self._get_day_range(target_date)
        return self._format_time_result(start_of_day, end_of_day)
