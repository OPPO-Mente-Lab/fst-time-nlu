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

from .base_parser import BaseParser


class RelativeParser(BaseParser):
    """
    相对时间解析器

    处理相对时间相关的时间表达式，如：
    - 去年、明年、上个月、下个月
    - 昨天、今天、明天
    - 相对时间+时间段组合
    """

    def __init__(self):
        """初始化相对时间解析器"""
        super().__init__()

    def parse(self, token, base_time):
        """
        解析相对时间表达式

        Args:
            token (dict): 时间表达式token
            base_time (datetime): 基准时间

        Returns:
            list: 时间范围列表，格式为 [[start_time_str, end_time_str]]
        """
        direction = self._determine_direction(token)
        time_num = self._get_time_num(token)
        time_offset_num = self._get_offset_time_num(token)
        base_time = self._apply_offset_time_num(base_time, time_offset_num, direction)

        if time_num:
            base_time = self._set_time_num(base_time, time_num)

        noon_str = token.get("noon")

        # 处理时间段
        if noon_str:
            return self._handle_noon_time(base_time, noon_str, time_num)

        # 处理具体时间与时间段结合
        if "hour" in time_num and noon_str:
            return self._handle_time_with_noon(base_time, time_num, noon_str)

        # 处理年月日
        return self._handle_relative_datetime(base_time, time_num, time_offset_num)

    def _handle_noon_time(self, base_time, noon_str, time_num):
        """
        处理时间段

        Args:
            base_time (datetime): 基准时间
            noon_str (str): 时间段字符串
            time_num (dict): 时间数字字典

        Returns:
            list: 时间范围列表
        """
        if "hour" not in time_num and "minute" not in time_num and "second" not in time_num:
            # 只有时间段，没有具体时间
            start_time, end_time = self._parse_noon(base_time, noon_str)
            return self._format_time_result(start_time, end_time)
        else:
            # 时间段与具体时间结合
            start_time, end_time = self._parse_noon(base_time, noon_str)
            if "hour" in time_num and "minute" not in time_num:
                if noon_str in self.noon_time and time_num["hour"] <= 12:
                    time_num["hour"] += 12
                    if time_num["hour"] >= 24:
                        time_num["hour"] -= 24
                        start_time = start_time.replace(day=start_time.day + 1)
                if noon_str == "中午" and time_num["hour"] < 11:
                    time_num["hour"] += 12
                target_time = start_time.replace(hour=time_num["hour"], minute=0)
                return [[target_time.strftime("%Y-%m-%dT%H:%M:%SZ")]]
            elif "hour" in time_num and "minute" in time_num:
                if noon_str in self.noon_time and time_num["hour"] < 12:
                    time_num["hour"] += 12
                target_time = start_time.replace(hour=time_num["hour"], minute=time_num["minute"])
                return [[target_time.strftime("%Y-%m-%dT%H:%M:%SZ")]]

    def _handle_time_with_noon(self, base_time, time_num, noon_str):
        """
        处理时间段与具体时间结合的情况

        Args:
            base_time (datetime): 基准时间
            time_num (dict): 时间数字字典
            noon_str (str): 时间段字符串

        Returns:
            list: 时间范围列表
        """
        if noon_str in self.noon_time:
            if time_num["hour"] < 12:
                time_num["hour"] += 12

        if "hour" not in time_num and "minute" not in time_num and "second" not in time_num:
            # 只有时间段，没有具体时间
            start_time, end_time = self._parse_noon(base_time, noon_str)
            return self._format_time_result(start_time, end_time)
        else:
            # 时间段与具体时间结合
            start_time, end_time = self._parse_noon(base_time, noon_str)

            if "hour" in time_num and "minute" not in time_num:
                if noon_str in self.noon_time and time_num["hour"] <= 12:
                    time_num["hour"] += 12
                    if time_num["hour"] >= 24:
                        time_num["hour"] -= 24
                        start_time = start_time.replace(day=start_time.day + 1)
                if noon_str == "中午" and time_num["hour"] < 11:
                    time_num["hour"] += 12
                target_time = start_time.replace(hour=time_num["hour"], minute=0)
                return self._format_time_result(target_time)
            elif "hour" in time_num and "minute" in time_num:
                if noon_str in self.noon_time and time_num["hour"] < 12:
                    time_num["hour"] += 12
                target_time = start_time.replace(hour=time_num["hour"], minute=time_num["minute"])
                return self._format_time_result(target_time)

        return []

    def _handle_relative_datetime(self, base_time, time_num, time_offset_num):  # noqa: C901
        """
        处理相对时间的年月日

        Args:
            base_time (datetime): 基准时间
            time_num (dict): 时间数字字典
            time_offset_num (dict): 时间偏移数字字典

        Returns:
            list: 时间范围列表
        """
        # 只有年 - 使用基类的年范围函数
        if ("year" in time_offset_num and len(time_offset_num) == 1 and time_num == {}) or (
            "year" in time_num and len(time_num) == 1 and time_offset_num == {}
        ):
            start_of_year, end_of_year = self._get_year_range(base_time)
            return self._format_time_result(start_of_year, end_of_year)

        # 只有月 - 使用基类的月范围函数
        if "month" in time_offset_num and len(time_offset_num) == 1 and time_num == {}:
            start_of_month, end_of_month = self._get_month_range(base_time)
            return self._format_time_result(start_of_month, end_of_month)

        # 只有周 - 使用基类的周范围函数
        if "week" in time_offset_num and len(time_offset_num) == 1 and time_num == {}:
            start_of_week, end_of_week = self._get_week_range(base_time)
            return self._format_time_result(start_of_week, end_of_week)

        # 年偏移+第N周：今年第37周
        # 注意：base_time已经在parse方法中通过_apply_offset_time_num应用了年份偏移
        if "year" in time_offset_num and "week_order" in time_num:
            week_order = time_num["week_order"]

            # base_time.year已经是应用偏移后的年份
            try:
                start_of_week, end_of_week = self._get_year_nth_week_range(
                    base_time.year, week_order
                )
                return self._format_time_result(start_of_week, end_of_week)
            except (ValueError, Exception):
                # 如果该年没有第N周，返回空
                return []

        # 年偏移+第N个月：今年第三个月
        # 注意：base_time已经在parse方法中通过_apply_offset_time_num应用了年份偏移
        if "year" in time_offset_num and "month_order" in time_num:
            month_order = time_num["month_order"]

            # 验证月份在1-12范围内
            if month_order < 1 or month_order > 12:
                return []

            try:
                # base_time.year已经是应用偏移后的年份
                start_of_month, end_of_month = self._get_month_range(base_time, month_order)
                return self._format_time_result(start_of_month, end_of_month)
            except (ValueError, Exception):
                return []

        # 年偏移+月：去年九月 - 使用基类的月范围函数
        if ("year" in time_offset_num and len(time_offset_num) == 1) and (
            "month" in time_num and len(time_num) == 1
        ):
            start_of_month, end_of_month = self._get_month_range(base_time, time_num["month"])
            return self._format_time_result(start_of_month, end_of_month)

        # 只有季度偏移：返回整个目标季度范围
        if "quarter" in time_offset_num and len(time_offset_num) == 1 and time_num == {}:
            start_of_quarter, end_of_quarter = self._get_quarter_range(base_time)
            return self._format_time_result(start_of_quarter, end_of_quarter)

        # 处理时间段 - 使用基类的天范围函数
        if "hour" not in time_num and "minute" not in time_num and "second" not in time_num:
            start_of_day, end_of_day = self._get_day_range(base_time)
            return self._format_time_result(start_of_day, end_of_day)
        elif "hour" in time_num and "minute" not in time_num and "second" not in time_num:
            start_of_day = base_time.replace(hour=time_num["hour"], minute=0, second=0)
            return self._format_time_result(start_of_day)
        elif "hour" in time_num and "minute" in time_num and "second" not in time_num:
            start_of_day = base_time.replace(
                hour=time_num["hour"], minute=time_num["minute"], second=0
            )
            return self._format_time_result(start_of_day)
        else:
            return self._format_time_result(base_time)
