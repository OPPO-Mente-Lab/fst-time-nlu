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
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from .base_parser import BaseParser

# 移除中文数字转换器导入，改为使用FST映射


class RangeParser(BaseParser):
    """
    时间范围解析器

    处理时间范围相关的时间表达式，如：
    - 两天以来
    - 三年间
    - 五日内
    - 最近一周
    """

    def __init__(self):
        """初始化时间范围解析器"""
        super().__init__()

    def parse(self, token, base_time):
        """
        解析时间范围表达式

        Args:
            token (dict): 时间表达式token
            base_time (datetime): 基准时间

        Returns:
            list: 时间范围列表，格式为 [[start_time_str, end_time_str]]
        """
        # 检查是否是"几"字范围表达式
        ji_range_type = token.get("ji_range_type")
        if ji_range_type:
            unit = token.get("unit", "day")
            return self._handle_ji_range(base_time, ji_range_type, unit)

        # 获取value：FST已映射为阿拉伯数字
        raw_value = token.get("value", "1")
        value = int(raw_value)

        unit = token.get("unit", "day")
        range_type = token.get("range_type", "ago")

        # 处理分数时间
        fractional = token.get("fractional")
        if fractional:
            fractional_val = float(fractional)
            # 将分数时间转换为更精确的时间计算
            if unit == "day":
                # 一天半 = 1.5天 = 36小时
                value = value + fractional_val
            elif unit == "month":
                # X个半月：先进行月份计算，然后进行天数计算
                # 保持月份和天数分别计算，不转换为天数
                value = value + fractional_val  # 2.5个月
            elif unit == "year":
                # 一年半 = 1.5年 = 18个月
                value = value + fractional_val
            elif unit == "hour":
                # 一小时半 = 1.5小时 = 90分钟
                value = value + fractional_val
            elif unit == "minute":
                # 一分钟半 = 1.5分钟 = 90秒
                value = value + fractional_val

        # 根据范围类型和时间单位计算时间范围
        if range_type in ["ago", "within", "between", "during"]:
            # 过去时间范围：从过去某个时间点到现在的范围
            return self._handle_ago_range(token, base_time, value, unit)
        elif range_type == "future":
            # 未来时间范围：从现在到未来某个时间点的范围
            return self._handle_future_range(base_time, value, unit)
        else:
            return []

    def _handle_ago_range(self, token, base_time, value, unit):
        """
        处理时间范围（从过去某个时间点到现在的范围）
        适用于：以来、以内、间、期间等所有范围限定词

        Args:
            base_time (datetime): 基准时间
            value (int): 时间数值
            unit (str): 时间单位

        Returns:
            list: 时间范围列表
        """
        # 计算起始时间（过去某个时间点）
        # 注意：仅对带明确前缀的表达式做“口径化”处理：
        #
        # 1) “最近/近 + X +（天/周/月/年）”：结束时间取当天23:59:59（更符合检索口径）
        # 2) “过去 + X +（天/周/月/年）”：结束时间取当前时刻；起始按“含今天的自然日窗口”对齐到00:00:00
        #
        # 其他（如“X天以来/以内/期间/间”）保持原有精确减法逻辑，避免影响既有规则。
        # - 起始：base_time - X单位 + 1天，对齐到00:00:00
        # - 结束：base_time（当前时刻）
        src = token.get("source", "") if isinstance(token, dict) else ""

        # 1) 最近/近 前缀（source通常为“最/近”单字）
        if src in {"最", "近"} and unit in {"day", "week", "month", "year"}:
            start_time = self._subtract_time(base_time, value, unit)
            start_of_day, _ = self._get_day_range(start_time)
            _, end_of_day = self._get_day_range(base_time)
            return self._format_time_result(start_of_day, end_of_day)

        # 2) 过去 前缀（source通常为"过"单字，或原文以"过去"开头）
        if (src == "过" or src.startswith("过去")) and unit in {"day", "week", "month", "year"}:
            # "过去N天"语义：含今天的N个自然日窗口
            # 例如：过去7天 = 今天+过去6天，起始为(base_time - 6天).日初
            # 转换为天数计算
            if unit == "day":
                days = value
            elif unit == "week":
                days = value * 7
            elif unit == "month":
                days = value * 30
            elif unit == "year":
                days = value * 365
            
            # 减去(N-1)天，然后对齐到日初
            start_time = base_time - timedelta(days=days - 1)
            start_of_day, _ = self._get_day_range(start_time)
            return self._format_time_result(start_of_day, base_time)

        start_time = self._subtract_time(base_time, value, unit)
        end_time = base_time
        return self._format_time_result(start_time, end_time)

    def _handle_future_range(self, base_time, value, unit):
        """
        处理未来时间范围（从现在到未来某个时间点的范围）
        适用于：未来两年内、未来三个月等

        Args:
            base_time (datetime): 基准时间
            value (int): 时间数值
            unit (str): 时间单位

        Returns:
            list: 时间范围列表
        """
        # 起始时间就是当前时间
        start_time = base_time
        # 计算结束时间（未来某个时间点）
        end_time = self._add_time(base_time, value, unit)

        return self._format_time_result(start_time, end_time)

    def _add_time(self, base_time, value, unit):
        """
        给基准时间添加指定时间

        Args:
            base_time (datetime): 基准时间
            value (float): 时间数值
            unit (str): 时间单位

        Returns:
            datetime: 添加时间后的时间
        """
        if unit == "year":
            return base_time + relativedelta(
                years=int(value), months=int((value - int(value)) * 12)
            )
        elif unit == "month":
            return base_time + relativedelta(months=int(value), days=int((value - int(value)) * 30))
        elif unit == "week":
            return base_time + timedelta(weeks=value)
        elif unit == "day":
            return base_time + timedelta(days=value)
        elif unit == "hour":
            return base_time + timedelta(hours=value)
        elif unit == "minute":
            return base_time + timedelta(minutes=value)
        elif unit == "second":
            return base_time + timedelta(seconds=value)
        else:
            return base_time

    def _subtract_time(self, base_time, value, unit):
        """
        从基准时间减去指定时间

        Args:
            base_time (datetime): 基准时间
            value (float): 时间数值
            unit (str): 时间单位

        Returns:
            datetime: 减去时间后的时间
        """
        if unit == "year":
            return base_time - relativedelta(
                years=int(value), months=int((value - int(value)) * 12)
            )
        elif unit == "month":
            return base_time - relativedelta(months=int(value), days=int((value - int(value)) * 30))
        elif unit == "week":
            return base_time - timedelta(weeks=value)
        elif unit == "day":
            return base_time - timedelta(days=value)
        elif unit == "hour":
            return base_time - timedelta(hours=value)
        elif unit == "minute":
            return base_time - timedelta(minutes=value)
        elif unit == "second":
            return base_time - timedelta(seconds=value)
        else:
            return base_time

    def _handle_ji_range(self, base_time, ji_range_type, unit):
        """
        处理"几"字范围表达式

        Args:
            base_time (datetime): 基准时间
            ji_range_type (str): 范围类型（bidirectional/past_only）
            unit (str): 时间单位（day/week/month/year）

        Returns:
            list: 时间范围列表
        """
        # 根据单位确定固定数值
        unit_values = {"day": 7, "week": 3, "month": 3, "year": 3}
        value = unit_values.get(unit, 7)

        if unit == "day":
            return self._handle_ji_day(base_time, ji_range_type, value)
        elif unit == "week":
            return self._handle_ji_week(base_time, value)
        elif unit == "month":
            return self._handle_ji_month(base_time, value)
        elif unit == "year":
            return self._handle_ji_year(base_time, value)
        else:
            return []

    def _handle_ji_day(self, base_time, ji_range_type, value):
        """
        处理"几天"表达式

        Args:
            base_time (datetime): 基准时间
            ji_range_type (str): bidirectional（包括未来）或 past_only（仅过去）
            value (int): 天数（默认7）

        Returns:
            list: 时间范围列表
        """
        if ji_range_type == "bidirectional":
            # 最近几天：过去7天（含今天）+ 未来7天
            # past：base_time - (value-1) 天，对齐到00:00:00
            # future：base_time + value 天，对齐到23:59:59
            start_time = base_time - timedelta(days=value - 1)
            end_time = base_time + timedelta(days=value)
            start_of_day, _ = self._get_day_range(start_time)
            _, end_of_day = self._get_day_range(end_time)
            return self._format_time_result(start_of_day, end_of_day)
        else:
            # 过去几天/这几天/近几天：过去7天（含今天）到当前时刻
            start_time = base_time - timedelta(days=value - 1)
            start_of_day, _ = self._get_day_range(start_time)
            return self._format_time_result(start_of_day, base_time)

    def _handle_ji_week(self, base_time, value):
        """
        处理"几周"表达式

        Args:
            base_time (datetime): 基准时间
            value (int): 周数（默认3）

        Returns:
            list: 时间范围列表
        """
        # 三周前的周一到本周的周日
        # 计算本周的周一和周日
        current_weekday = base_time.weekday()  # 0=周一, 6=周日
        current_monday = base_time - timedelta(days=current_weekday)
        current_sunday = current_monday + timedelta(days=6)

        # 计算三周前的周一
        start_monday = current_monday - timedelta(weeks=value)

        # 获取起始和结束的完整日期范围
        start_of_day, _ = self._get_day_range(start_monday)
        _, end_of_day = self._get_day_range(current_sunday)

        return self._format_time_result(start_of_day, end_of_day)

    def _handle_ji_month(self, base_time, value):
        """
        处理"几（个）月"表达式

        Args:
            base_time (datetime): 基准时间
            value (int): 月数（默认3）

        Returns:
            list: 时间范围列表
        """
        # 三月前的1号到本月的最后一天
        # 计算三月前的1号
        start_month_date = base_time - relativedelta(months=value)
        start_time = start_month_date.replace(day=1)

        # 计算本月的最后一天
        last_day = calendar.monthrange(base_time.year, base_time.month)[1]
        end_time = base_time.replace(day=last_day)

        # 获取起始和结束的完整日期范围
        start_of_day, _ = self._get_day_range(start_time)
        _, end_of_day = self._get_day_range(end_time)

        return self._format_time_result(start_of_day, end_of_day)

    def _handle_ji_year(self, base_time, value):
        """
        处理"几年"表达式

        Args:
            base_time (datetime): 基准时间
            value (int): 年数（默认3）

        Returns:
            list: 时间范围列表
        """
        # 三年前的1月1日到今年的12月31日
        start_year = base_time.year - value
        start_time = base_time.replace(year=start_year, month=1, day=1)
        end_time = base_time.replace(month=12, day=31)

        # 获取起始和结束的完整日期范围
        start_of_day, _ = self._get_day_range(start_time)
        _, end_of_day = self._get_day_range(end_time)

        return self._format_time_result(start_of_day, end_of_day)
