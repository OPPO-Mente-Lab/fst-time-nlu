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


class UTCTimeParser(BaseParser):
    """
    UTC时间解析器

    处理UTC时间相关的时间表达式，如：
    - 具体日期时间（2023年12月25日）
    - 年月日时分秒的各种组合
    - 时间段与具体时间的结合
    """

    def __init__(self):
        """初始化UTC时间解析器"""
        super().__init__()

    def parse(self, token, base_time):
        """
        解析UTC时间表达式

        Args:
            token (dict): 时间表达式token
            base_time (datetime): 基准时间

        Returns:
            list: 时间范围列表，格式为 [[start_time_str, end_time_str]]
        """
        # 检查是否为紧凑格式，需要进行范围验证
        if token.get("compact_format"):
            if not self._validate_compact_date(token):
                return []  # 验证失败，返回空结果

        # 处理"年+第N个月"的情况
        month_order = token.get("month_order")
        if month_order:
            # 如果有年份但没有月份，说明是"年+第N个月"
            if token.get("year") and not token.get("month"):
                return self._handle_year_month(token, base_time)

        # 处理"年+第N周"或"月份+第N周"的情况
        week_order = token.get("week_order")
        if week_order:
            # 如果有年份但没有月份，说明是"年+第N周"
            if token.get("year") and not token.get("month"):
                return self._handle_year_week(token, base_time)
            # 否则是"月份+第N周"或"月份+第N个星期X"
            return self._handle_month_week(token, base_time)

        # 提取基本时间字段
        time_num = self._get_time_num(token)
        # 记录是否为24时，基类会将其进位到次日0时
        hour_is_24 = "hour" in time_num and time_num["hour"] == 24
        noon_str = token.get("noon")
        past_key = token.get("past_key", "")
        special_time = token.get("special_time", "")

        # 应用基本时间字段（基类将 hour==24 进位到次日0时）
        base_time = self._set_time_num(base_time, time_num)
        # 若原始为24时，直接返回该时间点，避免后续再次基于hour计算而重复进位
        if hour_is_24:
            return self._format_time_result(base_time)

        # 处理时间段
        if noon_str:
            return self._handle_noon_time(base_time, noon_str, time_num)

        # 处理年月日时分秒
        return self._handle_utc_datetime(base_time, time_num, past_key, special_time)

    def _handle_noon_time(self, base_time, noon_str, time_num):  # noqa: C901
        """
        处理时间段

        Args:
            base_time (datetime): 基准时间
            noon_str (str): 时间段字符串
            time_num (dict): 时间数字字典

        Returns:
            list: 时间范围列表
        """
        if noon_str == "现在":
            return self._format_time_result(base_time)
        elif "hour" not in time_num and "minute" not in time_num and "second" not in time_num:
            # 只有时间段，没有具体时间
            start_time, end_time = self._parse_noon(base_time, noon_str)
            if start_time == end_time:
                return self._format_time_result(start_time)
            return self._format_time_result(start_time, end_time)
        else:
            # 时间段与具体时间结合
            start_time, end_time = self._parse_noon(base_time, noon_str)

            # 处理下午时间
            if noon_str in self.noon_time and time_num["hour"] <= 12:
                time_num["hour"] += 12
                if time_num["hour"] >= 24:
                    time_num["hour"] -= 24
                    start_time = start_time + timedelta(days=1)
            if noon_str == "中午" and time_num["hour"] < 11:
                time_num["hour"] += 12

            if "hour" in time_num and "minute" not in time_num:
                if time_num["hour"] >= 24:
                    time_num["hour"] -= 24
                    start_time = start_time + timedelta(days=1)
                target_time = start_time.replace(hour=time_num["hour"], minute=0)
                return self._format_time_result(target_time)
            elif "hour" in time_num and "minute" in time_num and "second" in time_num:
                if time_num["hour"] >= 24:
                    time_num["hour"] -= 24
                    start_time = start_time + timedelta(days=1)
                target_time = start_time.replace(
                    hour=time_num["hour"],
                    minute=time_num["minute"],
                    second=time_num["second"],
                )
                return self._format_time_result(target_time)
            elif "hour" in time_num and "minute" in time_num:
                if time_num["hour"] >= 24:
                    time_num["hour"] -= 24
                    start_time = start_time + timedelta(days=1)
                target_time = start_time.replace(hour=time_num["hour"], minute=time_num["minute"])
                return self._format_time_result(target_time)

        return []

    def _handle_utc_datetime(self, base_time, time_num, past_key, special_time):
        """
        处理UTC时间的年月日时分秒

        Args:
            base_time (datetime): 基准时间
            time_num (dict): 时间数字字典
            past_key (str): 过去时间标识
            special_time (str): 特殊时间标识

        Returns:
            list: 时间范围列表
        """
        # 处理年月日情况
        if "hour" not in time_num and "minute" not in time_num and "second" not in time_num:
            return self._handle_utc_date_only(base_time, time_num, special_time)

        # 处理年月日时分秒情况
        return self._handle_utc_datetime_full(base_time, time_num, past_key)

    def _handle_utc_date_only(self, base_time, time_num, special_time):  # noqa: C901
        """
        处理UTC年月日（无时分秒）

        Args:
            base_time (datetime): 基准时间
            time_num (dict): 时间数字字典
            special_time (str): 特殊时间标识

        Returns:
            list: 时间范围列表
        """
        # 只有年 - 使用基类的年范围函数
        if "year" in time_num and "month" not in time_num and "day" not in time_num:
            time_num["year"] = self._normalize_year(time_num["year"])
            if special_time == "firstday":
                start_of_day = base_time.replace(
                    year=time_num["year"], month=1, day=1, hour=0, minute=0, second=0
                )
                end_of_day = base_time.replace(
                    year=time_num["year"], month=1, day=1, hour=23, minute=59, second=59
                )
            elif special_time == "lastday":
                start_of_day = base_time.replace(
                    year=time_num["year"], month=12, day=31, hour=0, minute=0, second=0
                )
                end_of_day = base_time.replace(
                    year=time_num["year"],
                    month=12,
                    day=31,
                    hour=23,
                    minute=59,
                    second=59,
                )
            elif special_time == "lastmonth":
                start_of_day = base_time.replace(
                    year=time_num["year"], month=12, day=1, hour=0, minute=0, second=0
                )
                end_of_day = base_time.replace(
                    year=time_num["year"],
                    month=12,
                    day=31,
                    hour=23,
                    minute=59,
                    second=59,
                )
            else:
                start_of_year, end_of_year = self._get_year_range(base_time, time_num["year"])
                return self._format_time_result(start_of_year, end_of_year)
            return self._format_time_result(start_of_day, end_of_day)

        # 只有年，月 - 使用基类的月范围函数
        if "year" in time_num and "month" in time_num and "day" not in time_num:
            time_num["year"] = self._normalize_year(time_num["year"])
            if special_time == "lastday":
                # 特殊处理最后一天
                if time_num["month"] in [1, 3, 5, 7, 8, 10, 12]:
                    end_day = 31
                elif time_num["month"] in [4, 6, 9, 11]:
                    end_day = 30
                elif time_num["year"] % 4 == 0:
                    if time_num["year"] % 100 != 0 or time_num["year"] % 400 == 0:
                        end_day = 29
                    else:
                        end_day = 28
                else:
                    end_day = 28
                start_of_day = base_time.replace(
                    year=time_num["year"],
                    month=time_num["month"],
                    day=end_day,
                    hour=0,
                    minute=0,
                    second=0,
                )
                end_of_day = base_time.replace(
                    year=time_num["year"],
                    month=time_num["month"],
                    day=end_day,
                    hour=23,
                    minute=59,
                    second=59,
                )
            else:
                target_date = base_time.replace(year=time_num["year"])
                start_of_month, end_of_month = self._get_month_range(target_date, time_num["month"])
                return self._format_time_result(start_of_month, end_of_month)
            return self._format_time_result(start_of_day, end_of_day)

        # 只有月 - 使用基类的月范围函数
        if "month" in time_num and "day" not in time_num:
            if special_time == "lastday":
                # 特殊处理最后一天
                if time_num["month"] in [1, 3, 5, 7, 8, 10, 12]:
                    end_day = 31
                elif time_num["month"] in [4, 6, 9, 11]:
                    end_day = 30
                elif base_time.year % 4 == 0:
                    if base_time.year % 100 != 0 or base_time.year % 400 == 0:
                        end_day = 29
                    else:
                        end_day = 28
                else:
                    end_day = 28
                start_of_day = base_time.replace(
                    month=time_num["month"], day=end_day, hour=0, minute=0, second=0
                )
                end_of_day = base_time.replace(
                    month=time_num["month"], day=end_day, hour=23, minute=59, second=59
                )
            else:
                start_of_month, end_of_month = self._get_month_range(base_time, time_num["month"])
                return self._format_time_result(start_of_month, end_of_month)
            return self._format_time_result(start_of_day, end_of_day)

        # 只有日
        if "year" not in time_num and "month" not in time_num and "day" in time_num:
            target_date = base_time.replace(day=time_num["day"])
            start_of_day, end_of_day = self._get_day_range(target_date)
            return self._format_time_result(start_of_day, end_of_day)

        # 只有月+日 - 使用基类的天范围函数
        if "year" not in time_num and "month" in time_num and "day" in time_num:
            target_date = base_time.replace(month=time_num["month"], day=time_num["day"])
            start_of_day, end_of_day = self._get_day_range(target_date)
            return self._format_time_result(start_of_day, end_of_day)

        # 年+月+日 - 使用基类的天范围函数
        if "year" in time_num and "month" in time_num and "day" in time_num:
            time_num["year"] = self._normalize_year(time_num["year"])
            target_date = base_time.replace(
                year=time_num["year"], month=time_num["month"], day=time_num["day"]
            )
            start_of_day, end_of_day = self._get_day_range(target_date)
            return self._format_time_result(start_of_day, end_of_day)

        return []

    def _handle_utc_datetime_full(self, base_time, time_num, past_key):  # noqa: C901
        """
        处理UTC年月日时分秒

        Args:
            base_time (datetime): 基准时间
            time_num (dict): 时间数字字典
            past_key (str): 过去时间标识

        Returns:
            list: 时间范围列表
        """
        # 年月日 + 时分秒
        if (
            "year" in time_num
            and "month" in time_num
            and "day" in time_num
            and "hour" in time_num
            and "minute" in time_num
            and "second" in time_num
        ):
            time_num["year"] = self._normalize_year(time_num["year"])
            if time_num["hour"] >= 24:
                time_num["hour"] -= 24
                standtime = base_time.replace(
                    year=time_num["year"],
                    month=time_num["month"],
                    day=time_num["day"],
                    hour=time_num["hour"],
                    minute=time_num["minute"],
                    second=time_num["second"],
                ) + timedelta(days=1)
            else:
                standtime = base_time.replace(
                    year=time_num["year"],
                    month=time_num["month"],
                    day=time_num["day"],
                    hour=time_num["hour"],
                    minute=time_num["minute"],
                    second=time_num["second"],
                )
            return self._format_time_result(standtime)

        # 年月日 + 时分
        if (
            "year" in time_num
            and "month" in time_num
            and "day" in time_num
            and "hour" in time_num
            and "minute" in time_num
            and "second" not in time_num
        ):
            time_num["year"] = self._normalize_year(time_num["year"])
            if time_num["hour"] >= 24:
                time_num["hour"] -= 24
                standtime = base_time.replace(
                    year=time_num["year"],
                    month=time_num["month"],
                    day=time_num["day"],
                    hour=time_num["hour"],
                    minute=time_num["minute"],
                    second=0,
                ) + timedelta(days=1)
            else:
                standtime = base_time.replace(
                    year=time_num["year"],
                    month=time_num["month"],
                    day=time_num["day"],
                    hour=time_num["hour"],
                    minute=time_num["minute"],
                    second=0,
                )
            return self._format_time_result(standtime)

        # 年月日 + 时
        if (
            "year" in time_num
            and "month" in time_num
            and "day" in time_num
            and "hour" in time_num
            and "minute" not in time_num
            and "second" not in time_num
        ):
            time_num["year"] = self._normalize_year(time_num["year"])
            if time_num["hour"] >= 24:
                time_num["hour"] -= 24
                standtime = base_time.replace(
                    year=time_num["year"],
                    month=time_num["month"],
                    day=time_num["day"],
                    hour=time_num["hour"],
                    minute=0,
                    second=0,
                ) + timedelta(days=1)
            else:
                standtime = base_time.replace(
                    year=time_num["year"],
                    month=time_num["month"],
                    day=time_num["day"],
                    hour=time_num["hour"],
                    minute=0,
                    second=0,
                )
            return self._format_time_result(standtime)

        # 处理没有noon - 使用基类的天范围函数
        if "hour" not in time_num and "minute" not in time_num and "second" not in time_num:
            start_of_day, end_of_day = self._get_day_range(base_time)
            return self._format_time_result(start_of_day, end_of_day)
        elif "hour" in time_num and "minute" not in time_num and "second" not in time_num:
            if time_num["hour"] >= 24:
                time_num["hour"] -= 24
                start_of_day = base_time.replace(
                    hour=time_num["hour"], minute=0, second=0
                ) + timedelta(days=1)
            else:
                start_of_day = base_time.replace(hour=time_num["hour"], minute=0, second=0)
            return self._format_time_result(start_of_day)
        elif "hour" in time_num and "minute" in time_num and "second" not in time_num:
            if time_num["hour"] >= 24:
                time_num["hour"] -= 24
                start_of_day = base_time.replace(
                    hour=time_num["hour"], minute=time_num["minute"], second=0
                ) + timedelta(days=1)
            start_of_day = base_time.replace(
                hour=time_num["hour"], minute=time_num["minute"], second=0
            )
            return self._format_time_result(start_of_day)
        else:
            return self._format_time_result(base_time)

    def _handle_year_week(self, token, base_time):
        """
        处理年+第N周的情况（如：21年第一个礼拜）
        """
        week_order = int(token.get("week_order"))
        year = token.get("year")

        if year:
            year_val = self._normalize_year(int(year))
        else:
            year_val = base_time.year

        try:
            start_of_week, end_of_week = self._get_year_nth_week_range(year_val, week_order)
            return self._format_time_result(start_of_week, end_of_week)
        except (ValueError, Exception):
            # 如果该年没有第N周，返回空
            return []

    def _handle_year_month(self, token, base_time):
        """
        处理年+第N个月的情况（如：2025年第九个月）
        """
        month_order = int(token.get("month_order"))
        year = token.get("year")

        if year:
            year_val = self._normalize_year(int(year))
        else:
            year_val = base_time.year

        # 验证月份在1-12范围内
        if month_order < 1 or month_order > 12:
            return []

        try:
            start_of_month, end_of_month = self._get_month_range(
                base_time.replace(year=year_val), month_order
            )
            return self._format_time_result(start_of_month, end_of_month)
        except (ValueError, Exception):
            return []

    def _handle_month_week(self, token, base_time):
        """
        处理月份+第N周/第N个星期X的情况
        """
        week_order = int(token.get("week_order"))
        month = token.get("month")
        year = token.get("year")
        week_day = token.get("week_day")  # 新增：星期几

        if year:
            year_val = self._normalize_year(int(year))
        else:
            year_val = base_time.year

        if month:
            month_val = int(month)
        else:
            month_val = base_time.month

        # 如果有week_day，返回该月第N个星期X的具体一天
        if week_day:
            try:
                target_date = self._get_month_nth_weekday(
                    year_val, month_val, week_order, int(week_day)
                )
                start_of_day, end_of_day = self._get_day_range(target_date)
                return self._format_time_result(start_of_day, end_of_day)
            except (ValueError, Exception):
                # 如果该月没有第N个星期X，返回空
                return []

        # 否则返回该月第N周的时间段
        start_of_week, end_of_week = self._get_month_nth_week_range(year_val, month_val, week_order)

        return self._format_time_result(start_of_week, end_of_week)

    def _validate_compact_date(self, token):
        """
        验证紧凑格式日期的有效性

        Args:
            token (dict): 时间表达式token

        Returns:
            bool: 是否有效
        """
        try:
            year = int(token.get("year", 0))
            month = int(token.get("month", 0))
            day = int(token.get("day", 0))

            # 验证年份范围：1900-2099
            if year < 1900 or year > 2099:
                return False

            # 验证月份范围：01-12
            if month < 1 or month > 12:
                return False

            # 验证日期范围：01-31
            if day < 1 or day > 31:
                return False

            # 进一步验证日期在该月份是否有效（如2月不能有30日）
            import calendar

            max_day = calendar.monthrange(year, month)[1]
            if day > max_day:
                return False

            return True
        except (ValueError, TypeError):
            return False
