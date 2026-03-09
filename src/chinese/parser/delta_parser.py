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


class DeltaParser(BaseParser):
    """
    时间增量解析器

    处理时间增量相关的时间表达式，如：
    - 十年后、2个月后、5天后
    - 时间偏移和增量计算
    """

    def __init__(self):
        """初始化时间增量解析器"""
        super().__init__()

    def parse(self, token, base_time):
        """
        解析时间增量表达式

        Args:
            token (dict): 时间表达式token
            base_time (datetime): 基准时间

        Returns:
            list: 时间范围列表，格式为 [[start_time_str, end_time_str]]
        """
        direction = self._determine_direction(token)
        time_num = self._get_time_num(token)

        # 根据是否有offset_direction来决定处理方式
        if "offset_direction" in token:
            # 使用偏移方式处理（如：十年后）
            base_time = self._apply_offset_time_num(base_time, time_num, direction)
        else:
            # 使用设置方式处理（如：设置为具体时间）
            base_time = self._set_time_num(base_time, time_num)

        # 根据时间单位进行处理
        return self._handle_time_units(base_time, time_num)

    def _handle_time_units(self, base_time, time_num):
        """
        根据时间单位处理不同的时间增量

        Args:
            base_time (datetime): 基准时间
            time_num (dict): 时间数字字典

        Returns:
            list: 时间范围列表
        """
        # 年增量处理（如：十年后）
        if "year" in time_num:
            return self._handle_year_delta(base_time)

        # 月增量处理（如：2个月后）
        if "month" in time_num:
            return self._handle_month_delta(base_time)

        # 周增量处理（如：4个星期后）→ 返回单点（当天00:00:00）
        if "week" in time_num:
            return self._handle_week_delta(base_time)

        # 日增量处理（如：5天后）
        if "day" in time_num:
            return self._handle_day_delta(base_time)

        # 处理时分秒
        return self._handle_time_delta(base_time, time_num)

    def _handle_year_delta(self, base_time):
        """
        处理年增量

        Args:
            base_time (datetime): 基准时间

        Returns:
            list: 全天时间段列表（00:00:00 到 23:59:59）
        """
        # 返回全天时间段
        start_of_day, end_of_day = self._get_day_range(base_time)
        return self._format_time_result(start_of_day, end_of_day)

    def _handle_month_delta(self, base_time):
        """
        处理月增量

        Args:
            base_time (datetime): 基准时间

        Returns:
            list: 全天时间段列表（00:00:00 到 23:59:59）
        """
        # 返回全天时间段
        start_of_day, end_of_day = self._get_day_range(base_time)
        return self._format_time_result(start_of_day, end_of_day)

    def _handle_day_delta(self, base_time):
        """
        处理日增量

        Args:
            base_time (datetime): 基准时间

        Returns:
            list: 全天时间段列表（00:00:00 到 23:59:59）
        """
        # 返回全天时间段
        start_of_day, end_of_day = self._get_day_range(base_time)
        return self._format_time_result(start_of_day, end_of_day)

    def _handle_time_delta(self, base_time, time_num):
        """
        处理时分秒增量

        Args:
            base_time (datetime): 基准时间
            time_num (dict): 时间数字字典

        Returns:
            list: 时间范围列表
        """
        # 没有时分秒，返回全天
        if "hour" not in time_num and "minute" not in time_num and "second" not in time_num:
            start_of_day, end_of_day = self._get_day_range(base_time)
            return self._format_time_result(start_of_day, end_of_day)

        # 只有分钟，没有小时和秒
        elif "hour" not in time_num and "minute" in time_num and "second" not in time_num:
            # 保持原有的秒数，不重置为0
            return self._format_time_result(base_time)

        # 有小时和分钟，没有秒
        elif "hour" in time_num and "minute" in time_num and "second" not in time_num:
            # 保持原有的秒数，不重置为0
            return self._format_time_result(base_time)

        # 其他情况，返回当前时间
        else:
            return self._format_time_result(base_time)

    def _handle_week_delta(self, base_time):
        """
        处理周增量，返回全天时间段（00:00:00 到 23:59:59）
        """
        # 返回全天时间段
        start_of_day, end_of_day = self._get_day_range(base_time)
        return self._format_time_result(start_of_day, end_of_day)

    def _get_month_days(self, month, year):
        """
        获取指定月份的天数

        Args:
            month (int): 月份
            year (int): 年份

        Returns:
            int: 该月的天数
        """
        if month in [1, 3, 5, 7, 8, 10, 12]:
            return 31
        elif month in [4, 6, 9, 11]:
            return 30
        elif month == 2:
            # 判断闰年
            if year % 4 == 0:
                if year % 100 != 0 or year % 400 == 0:
                    return 29
                else:
                    return 28
            else:
                return 28
        else:
            return 30
