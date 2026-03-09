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

from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

# 移除中文数字转换器导入，改为使用FST映射


class BaseParser(ABC):
    """
    时间解析器基类

    所有时间解析器都应该继承此类，实现统一的接口和公共功能
    """

    # 年份范围限制
    YEAR_MIN = 1900
    YEAR_MAX = 2100

    def __init__(self):
        """初始化解析器"""
        # 公共的时间段词汇列表
        self.noon_time = [
            "午后",
            "下午",
            "傍晚",
            "晚上",
            "当晚",
            "夜间",
            "今晚",
            "明晚",
            "昨晚",
            "半夜",
        ]

    @abstractmethod
    def parse(self, token, base_time):
        """
        解析时间表达式的抽象方法

        Args:
            token (dict): 时间表达式token
            base_time (datetime): 基准时间

        Returns:
            list: 时间范围列表，格式为 [[start_time_str, end_time_str]]
        """
        pass

    def _format_time_result(self, start_time, end_time=None):
        """
        格式化时间结果为标准格式

        Args:
            start_time (datetime): 开始时间
            end_time (datetime, optional): 结束时间，如果为None则只返回开始时间

        Returns:
            list: 格式化的时间结果，如果年份超出1900-2100范围则返回空列表
        """
        # 检查年份范围：1900-2100
        if end_time is None:
            # 单时间点：检查start_time的年份
            if start_time.year < self.YEAR_MIN or start_time.year > self.YEAR_MAX:
                return []
            return [[start_time.strftime("%Y-%m-%dT%H:%M:%SZ")]]
        else:
            # 时间段：检查start_time和end_time的年份
            if (
                start_time.year < self.YEAR_MIN
                or start_time.year > self.YEAR_MAX
                or end_time.year < self.YEAR_MIN
                or end_time.year > self.YEAR_MAX
            ):
                return []
            return [
                [
                    start_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    end_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                ]
            ]

    def _get_day_range(self, base_time):
        """
        获取一天的开始和结束时间

        Args:
            base_time (datetime): 基准时间

        Returns:
            tuple: (start_of_day, end_of_day)
        """
        start_of_day = base_time.replace(hour=0, minute=0, second=0)
        end_of_day = base_time.replace(hour=23, minute=59, second=59)
        return start_of_day, end_of_day

    def _get_week_range(self, base_time):
        """
        获取一周的开始和结束时间（周一到周日）

        Args:
            base_time (datetime): 基准时间

        Returns:
            tuple: (start_of_week, end_of_week)
        """
        # 计算本周一的日期
        days_since_monday = base_time.weekday()  # 0=Monday, 6=Sunday
        start_of_week = base_time - timedelta(days=days_since_monday)
        start_of_week = start_of_week.replace(hour=0, minute=0, second=0)

        # 计算本周日的日期
        end_of_week = start_of_week + timedelta(days=6)
        end_of_week = end_of_week.replace(hour=23, minute=59, second=59)

        return start_of_week, end_of_week

    def _get_month_range(self, base_time, month=None):
        """
        获取一个月的开始和结束时间

        Args:
            base_time (datetime): 基准时间
            month (int, optional): 指定月份，如果为None则使用base_time的月份

        Returns:
            tuple: (start_of_month, end_of_month)
        """
        if month is not None:
            base_time = base_time.replace(month=month)

        # 计算月份的最后一天
        if base_time.month in [1, 3, 5, 7, 8, 10, 12]:
            end_day = 31
        elif base_time.month in [4, 6, 9, 11]:
            end_day = 30
        elif base_time.year % 4 == 0:
            if base_time.year % 100 != 0 or base_time.year % 400 == 0:
                end_day = 29
            else:
                end_day = 28
        else:
            end_day = 28

        start_of_month = base_time.replace(day=1, hour=0, minute=0, second=0)
        end_of_month = base_time.replace(day=end_day, hour=23, minute=59, second=59)
        return start_of_month, end_of_month

    def _get_quarter_range(self, base_time):
        """
        获取当前日期所在季度的开始和结束时间
        Q1: 1-3, Q2: 4-6, Q3: 7-9, Q4: 10-12
        """
        month = base_time.month
        quarter_index = (month - 1) // 3  # 0..3
        start_month = quarter_index * 3 + 1
        end_month = start_month + 2

        # 季度开始
        start_of_quarter = base_time.replace(month=start_month, day=1, hour=0, minute=0, second=0)

        # 季度结束：取该季度最后一个月的最后一天 23:59:59
        _, end_of_month = self._get_month_range(base_time.replace(month=end_month))
        end_of_quarter = end_of_month

        return start_of_quarter, end_of_quarter

    def _get_year_range(self, base_time, year=None):
        """
        获取一年的开始和结束时间

        Args:
            base_time (datetime): 基准时间
            year (int, optional): 指定年份，如果为None则使用base_time的年份

        Returns:
            tuple: (start_of_year, end_of_year)
        """
        if year is not None:
            # 检查年份范围，Python datetime 限制在 1-9999 之间
            if year < 1000 or year > 2099:
                raise ValueError(f"year {year} is out of range (1000-2099)")
            base_time = base_time.replace(year=year)

        start_of_year = base_time.replace(month=1, day=1, hour=0, minute=0, second=0)
        end_of_year = base_time.replace(month=12, day=31, hour=23, minute=59, second=59)
        return start_of_year, end_of_year

    def _handle_noon_time(self, base_time, noon_str, time_num=None):  # noqa: C901
        """
        处理时间段（noon）相关的时间解析

        Args:
            base_time (datetime): 基准时间
            noon_str (str): 时间段字符串
            time_num (dict, optional): 具体时间数字

        Returns:
            list: 时间范围列表
        """
        if noon_str == "现在":
            return self._format_time_result(base_time)
        elif not time_num or (
            "hour" not in time_num and "minute" not in time_num and "second" not in time_num
        ):
            # 只有时间段，没有具体时间
            start_time, end_time = self._parse_noon(base_time, noon_str)
            # 若 noon 定义为同一时刻（如“午夜”），返回单点时间而非区间
            if start_time == end_time:
                return self._format_time_result(start_time)
            return self._format_time_result(start_time, end_time)
        else:
            # 时间段与具体时间结合
            start_time, end_time = self._parse_noon(base_time, noon_str)

            # 处理下午时间
            if noon_str in self.noon_time and time_num.get("hour", 0) <= 12:
                time_num["hour"] += 12
                if time_num["hour"] >= 24:
                    time_num["hour"] -= 24
                    start_time = start_time + timedelta(days=1)
            elif noon_str == "中午" and time_num.get("hour", 0) < 11:
                time_num["hour"] += 12

            # 设置具体时间
            if "hour" in time_num and "minute" not in time_num:
                if time_num["hour"] >= 24:
                    time_num["hour"] -= 24
                    start_time = start_time + timedelta(days=1)
                target_time = start_time.replace(hour=time_num["hour"], minute=0)
                return self._format_time_result(target_time)
            elif "hour" in time_num and "minute" in time_num:
                if time_num["hour"] >= 24:
                    time_num["hour"] -= 24
                    start_time = start_time + timedelta(days=1)
                target_time = start_time.replace(hour=time_num["hour"], minute=time_num["minute"])
                return self._format_time_result(target_time)

        return self._format_time_result(base_time)

    def _normalize_year(self, year):
        """
        标准化年份格式

        Args:
            year (int): 原始年份

        Returns:
            int: 标准化后的年份
        """
        if year < 49:
            normalized_year = year + 2000
        elif year < 100:
            normalized_year = year + 1900
        else:
            normalized_year = year

        # 检查年份范围：1000-2099
        if normalized_year < 1000 or normalized_year > 2099:
            raise ValueError(f"year {normalized_year} is out of range (1000-2099)")

        return normalized_year

    def _get_month_nth_week_range(self, year, month, week_number):
        """
        获取指定月份的第N周的开始和结束时间

        规则：
        - 第一周从月份1号开始到第一个周日结束（可能不足7天）
        - 后续周都是完整的周一到周日（7天）

        Args:
            year (int): 年份
            month (int): 月份
            week_number (int): 第几周（从1开始）

        Returns:
            tuple: (start_of_week, end_of_week)
        """
        # 获取该月1号
        first_day = datetime(year, month, 1, 0, 0, 0)
        first_weekday = first_day.weekday()  # 0=周一, 6=周日

        if week_number == 1:
            # 第一周：从1号到第一个周日
            start = first_day
            # 计算到第一个周日的天数
            if first_weekday == 6:  # 1号就是周日
                days_until_sunday = 0
            else:
                days_until_sunday = 6 - first_weekday
            end = first_day + timedelta(days=days_until_sunday, hours=23, minutes=59, seconds=59)
        else:
            # 计算第一周的结束日（第一个周日）
            if first_weekday == 6:  # 1号就是周日
                days_until_first_sunday = 0
            else:
                days_until_first_sunday = 6 - first_weekday
            first_week_end = first_day + timedelta(days=days_until_first_sunday)

            # 第N周从第一周结束后的周一开始
            # 第2周从第一周后的第1个周一开始，第3周从第2个周一开始...
            start = first_week_end + timedelta(days=1 + (week_number - 2) * 7)
            start = start.replace(hour=0, minute=0, second=0)
            end = start + timedelta(days=6, hours=23, minutes=59, seconds=59)

        return start, end

    # ==================== 时间工具函数 ====================

    def _determine_direction(self, token):
        """
        确定时间偏移方向

        Args:
            token (dict): 时间表达式token

        Returns:
            int: 偏移方向，1为未来，-1为过去
        """
        offset_direction = token.get("offset_direction", "")
        if offset_direction:
            return int(offset_direction)
        else:
            return 1  # 默认未来方向

    def _get_offset_time_num(self, token):
        """
        获取时间偏移数字

        Args:
            token (dict): 时间表达式token

        Returns:
            dict: 时间偏移数字字典
        """
        # “现在”表示绝对当前时刻，忽略一切offset
        if token.get("noon") == "现在":
            return {}
        time_offset_num = {}
        # 提取基本时间字段
        year = token.get("offset_year")
        month = token.get("offset_month")
        week = token.get("offset_week")
        day = token.get("offset_day")
        hour = token.get("offset_hour")
        minute = token.get("offset_minute")
        second = token.get("offset_second")
        quarter = token.get("offset_quarter")

        if year:
            time_offset_num["year"] = int(year)
        if month:
            time_offset_num["month"] = int(month)
        if week:
            time_offset_num["week"] = int(week)
        if day:
            time_offset_num["day"] = int(day)
        if hour:
            time_offset_num["hour"] = int(hour)
        if minute:
            time_offset_num["minute"] = int(minute)
        if second:
            time_offset_num["second"] = int(second)
        if quarter:
            time_offset_num["quarter"] = int(quarter)
        return time_offset_num

    def _apply_offset_time_num(self, base_time, time_offset_num, direction):
        """
        应用时间偏移

        Args:
            base_time (datetime): 基准时间
            time_offset_num (dict): 时间偏移数字字典
            direction (int): 偏移方向

        Returns:
            datetime: 偏移后的时间
        """
        # 提取基本时间字段
        if time_offset_num.get("year"):
            base_time = base_time + relativedelta(years=time_offset_num.get("year", 0) * direction)
        if time_offset_num.get("month"):
            base_time = base_time + relativedelta(
                months=time_offset_num.get("month", 0) * direction
            )
        if time_offset_num.get("week"):
            base_time = base_time + timedelta(weeks=time_offset_num.get("week", 0) * direction)
        if time_offset_num.get("day"):
            base_time = base_time + timedelta(days=time_offset_num.get("day", 0) * direction)
        if time_offset_num.get("hour"):
            base_time = base_time + timedelta(hours=time_offset_num.get("hour", 0) * direction)
        if time_offset_num.get("minute"):
            base_time = base_time + timedelta(minutes=time_offset_num.get("minute", 0) * direction)
        if time_offset_num.get("second"):
            base_time = base_time + timedelta(seconds=time_offset_num.get("second", 0) * direction)

        # 季度偏移处理：直接使用月份偏移，支持跨年
        if time_offset_num.get("quarter"):
            quarter_offset = time_offset_num.get("quarter", 0) * direction
            # 直接计算月份偏移：每个季度 = 3个月
            months_delta = quarter_offset * 3
            base_time = base_time + relativedelta(months=months_delta)

        return base_time

    def _set_time_num(self, base_time, time_num):  # noqa: C901
        """
        设置具体时间

        Args:
            base_time (datetime): 基准时间
            time_num (dict): 时间数字字典

        Returns:
            datetime: 设置后的时间
        """
        # 应用基本时间字段
        if time_num.get("year"):
            base_time = base_time.replace(year=time_num.get("year"))
        try:  # 防止出现basetime为1.30日，而需要输出2.10日，由于先换的month，导致会有2.30日的结果
            if time_num.get("month"):
                base_time = base_time.replace(month=time_num.get("month"))
            if time_num.get("day"):
                base_time = base_time.replace(day=time_num.get("day"))
        except Exception:
            if time_num.get("day"):
                base_time = base_time.replace(day=time_num.get("day"))
            if time_num.get("month"):
                base_time = base_time.replace(month=time_num.get("month"))
        if time_num.get("hour"):
            hour_val = time_num.get("hour")
            # 验证hour值是否合法
            if hour_val == 24:
                # 24时特殊处理：转换为第二天0时
                base_time = base_time.replace(hour=0) + timedelta(days=1)
            elif hour_val > 24:
                # hour值过大，明显是错误识别（如202501），抛出异常让上层捕获
                raise ValueError(f"hour must be in 0..23, got {hour_val}")
            else:
                base_time = base_time.replace(hour=hour_val)
        if time_num.get("minute"):
            base_time = base_time.replace(minute=time_num.get("minute"))
        if time_num.get("second"):
            base_time = base_time.replace(second=time_num.get("second"))
        return base_time

    def _get_time_num(self, token):  # noqa: C901
        """
        获取时间数字

        Args:
            token (dict): 时间表达式token

        Returns:
            dict: 时间数字字典
        """
        time_num = {}
        minute_plus = 0
        # 提取基本时间字段（FST已映射为阿拉伯数字）
        if token.get("year"):
            # 对于time_delta类型，year表示偏移量，不进行年份扩展
            # 对于其他类型，year表示具体年份，需要进行扩展
            if token.get("type") == "time_delta":
                time_num["year"] = int(token.get("year"))
            else:
                time_num["year"] = self._normalize_year(int(token.get("year")))
        if token.get("month"):
            time_num["month"] = int(token.get("month"))
        if token.get("day"):
            time_num["day"] = int(token.get("day"))
        # 周偏移（用于delta）
        if token.get("week"):
            time_num["week"] = int(token.get("week"))
        # 第N周（用于"今年第37周"等）
        if token.get("week_order"):
            time_num["week_order"] = int(token.get("week_order"))
        # 第N个月（用于"今年第三个月"等）
        if token.get("month_order"):
            time_num["month_order"] = int(token.get("month_order"))
        # 解决一个半小时，半小时的问题
        if token.get("hour"):
            if "." in token.get("hour"):
                time_num["hour"] = int(token.get("hour").split(".")[0])
                minute_plus = (float(token.get("hour")) - time_num["hour"]) * 60
            else:
                time_num["hour"] = int(token.get("hour"))

        # 处理分数时间表达（如：两个半小时、两天半）
        if token.get("fractional"):
            fractional_val = float(token.get("fractional"))

            # 处理有value字段的情况（如：两个半小时）
            if token.get("value"):
                base_val = int(token.get("value"))

                # 根据单位类型处理分数
                if "hour" in token or "小时" in str(token):
                    time_num["hour"] = base_val
                    time_num["minute"] = int(fractional_val * 60)
                elif "minute" in token or "分钟" in str(token):
                    time_num["minute"] = base_val
                    time_num["second"] = int(fractional_val * 60)
                elif "day" in token or "天" in str(token):
                    time_num["day"] = base_val
                    time_num["hour"] = int(fractional_val * 24)
                elif "month" in token or "月" in str(token):
                    # X个半月前：先进行月份计算，然后进行天数计算
                    time_num["month"] = base_val
                    time_num["day"] = int(fractional_val * 30)  # 半月 = 15天
                elif "year" in token or "年" in str(token):
                    time_num["year"] = base_val
                    time_num["month"] = int(fractional_val * 12)

            # 处理直接有day/month/year字段的情况（如：两天半、三个月半）
            elif token.get("day"):
                base_val = int(token.get("day"))
                time_num["day"] = base_val
                time_num["hour"] = int(fractional_val * 24)
            elif token.get("month"):
                base_val = int(token.get("month"))
                # X个半月前：先进行月份计算，然后进行天数计算
                time_num["month"] = base_val
                time_num["day"] = int(fractional_val * 30)  # 半月 = 15天
            elif token.get("year"):
                base_val = int(token.get("year"))
                time_num["year"] = base_val
                time_num["month"] = int(fractional_val * 12)
        if token.get("minute") or minute_plus:
            if token.get("minute") is not None:
                minute_val = int(token.get("minute"))
            else:
                minute_val = 0
            time_num["minute"] = int(minute_val) + int(minute_plus)
        if token.get("second"):
            time_num["second"] = int(token.get("second"))
        return time_num

    def _parse_noon(self, base_time, noon_str):
        """
        解析相对时间段

        Args:
            base_time (datetime): 基准时间
            noon_str (str): 时间段字符串

        Returns:
            tuple: (start_time, end_time)
        """
        if not noon_str:
            return base_time, base_time

        # 偏移天数、小时、分钟、秒
        noon_map = {
            "凌晨": (0, 1, 0, 0, 0, 5, 0, 0),
            "黎明": (0, 4, 0, 0, 0, 6, 0, 0),
            "清晨": (0, 5, 0, 0, 0, 6, 0, 0),
            "早晨": (0, 5, 0, 0, 0, 10, 0, 0),
            "早上": (0, 6, 0, 0, 0, 12, 0, 0),
            "上午": (0, 8, 0, 0, 0, 12, 0, 0),
            "中午": (0, 11, 30, 0, 0, 14, 0, 0),
            "午后": (0, 13, 0, 0, 0, 15, 0, 0),
            "下午": (0, 13, 0, 0, 0, 18, 0, 0),
            "傍晚": (0, 17, 0, 0, 0, 19, 0, 0),
            "今早": (0, 6, 0, 0, 0, 12, 0, 0),
            "今晚": (0, 18, 0, 0, 0, 23, 59, 59),
            "晚上": (0, 18, 0, 0, 0, 23, 59, 59),
            "当晚": (0, 18, 0, 0, 0, 23, 59, 59),
            "夜间": (0, 21, 0, 0, 0, 23, 59, 59),
            "深夜": (0, 22, 0, 0, 1, 2, 0, 0),
            "午夜": (0, 0, 0, 0, 0, 0, 0, 0),
            "上半夜": (0, 0, 0, 0, 0, 3, 0, 0),
            "下半夜": (0, 3, 0, 0, 0, 6, 0, 0),
            "后半夜": (0, 2, 0, 0, 0, 4, 0, 0),
            "明早": (1, 6, 0, 0, 1, 12, 0, 0),
            "明晚": (1, 18, 0, 0, 1, 23, 59, 59),
            "昨晚": (-1, 18, 0, 0, -1, 23, 59, 59),
        }

        (
            start_offset_day,
            start_hour,
            start_minute,
            start_second,
            end_offset_day,
            end_hour,
            end_minute,
            end_second,
        ) = noon_map.get(noon_str, (0, 0, 0, 0, 0, 0, 0, 0))
        start_base_time = base_time + timedelta(days=start_offset_day)
        end_base_time = base_time + timedelta(days=end_offset_day)
        start_time = start_base_time.replace(
            hour=start_hour, minute=start_minute, second=start_second
        )
        end_time = end_base_time.replace(hour=end_hour, minute=end_minute, second=end_second)
        return start_time, end_time

    def _get_month_nth_weekday(self, year, month, nth, weekday):
        """
        获取某月的第N个星期X

        Args:
            year: 年份
            month: 月份
            nth: 第几个（1-5）
            weekday: 星期几（1=周一, 7=周日）

        Returns:
            datetime: 目标日期
        """
        from datetime import datetime, timedelta

        # 转换为Python的weekday（0=Monday, 6=Sunday）
        target_weekday = (weekday - 1) % 7

        # 获取该月第一天
        first_day = datetime(year, month, 1)
        first_weekday = first_day.weekday()

        # 计算第一个目标星期几的日期
        days_until_target = (target_weekday - first_weekday) % 7
        first_occurrence = first_day + timedelta(days=days_until_target)

        # 计算第N个目标星期几
        target_date = first_occurrence + timedelta(weeks=nth - 1)

        # 确保仍在当月
        if target_date.month != month:
            raise ValueError(f"该月没有第{nth}个星期{weekday}")

        return target_date

    def _get_year_nth_week_range(self, year, week_number):
        """
        获取某年的第N周

        Args:
            year: 年份
            week_number: 周数（1-53）

        Returns:
            tuple: (start_of_week, end_of_week)
        """
        from datetime import datetime, timedelta

        # 获取该年第一天
        first_day = datetime(year, 1, 1)

        # 找到第一个周一
        days_until_monday = (0 - first_day.weekday()) % 7
        if days_until_monday > 0:
            first_monday = first_day + timedelta(days=days_until_monday)
        else:
            first_monday = first_day

        # 计算第N周的开始（周一）
        start_of_week = first_monday + timedelta(weeks=week_number - 1)
        start_of_week = start_of_week.replace(hour=0, minute=0, second=0)

        # 计算第N周的结束（周日）
        end_of_week = start_of_week + timedelta(days=6)
        end_of_week = end_of_week.replace(hour=23, minute=59, second=59)

        return start_of_week, end_of_week
