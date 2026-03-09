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

import os
import json
import datetime
import zhdate

from .time_utils import fathers_day, mothers_day, gives_day
from .base_parser import BaseParser
from ...core.logger import get_logger


class HolidayParser(BaseParser):
    """
    节假日时间解析器

    处理各种节假日相关的时间表达式，包括：
    - 公历节假日（元旦、情人节等）
    - 农历节假日（春节、中秋等）
    - 法定节假日（国庆、劳动节等）
    """

    def __init__(self):
        """初始化节假日解析器"""
        super().__init__()
        self.logger = get_logger(__name__)

        # 公历节假日配置
        self.calendar_holiday = {
            "元旦": [1, 1],
            "情人节": [2, 14],
            "妇女节": [3, 8],
            "植树节": [3, 12],
            "青年节": [4, 1],
            "愚人节": [4, 1],
            "母亲节": [5, 11],
            "父亲节": [6, 10],
            "儿童节": [6, 1],
            "建党节": [7, 1],
            "建军节": [8, 1],
            "教师节": [9, 10],
            "万圣节": [10, 31],
            "圣诞节": [12, 25],
            "感恩节": [11, 27],
        }

        # 农历节假日配置
        self.holiday_lunar = {
            "中和节": [2, 2],
            "中元节": [7, 15],
            "元宵": [1, 15],
            "重阳": [9, 9],
            "七夕": [7, 7],
            "腊八": [12, 8],
            "除夕": [12, 30],
            "春节": [1, 1],
            "端午": [5, 5],
            "中秋": [8, 15],
        }

        # 法定节假日配置
        self.statutory_holiday = {
            "清明": [
                4,
                4,
            ],  # 清明放这里是因为每年清明节不确定，需要读取json文件中的日期
            "劳动": [5, 1],
            "国庆": [10, 1],
        }

    def parse(self, token, base_time):
        """
        解析节假日相关的时间表达式

        Args:
            token (dict): 时间表达式token
            base_time (datetime): 基准时间

        Returns:
            list: 时间范围列表，格式为 [[start_time_str, end_time_str]]
        """
        festival = token.get("festival", "").strip('"')
        day_prefix = token.get("day_prefix", "")
        day_offset = int(token.get("day_prefix", 0))

        # 保存原始基准时间
        base_time_raw = base_time

        # 处理年份信息
        if token.get("year"):
            year_val = int(token.get("year"))
            year_val = self._normalize_year(year_val)
            base_time = base_time.replace(year=year_val)
            # 对于农历节假日，需要确保年份在支持范围内
            if festival in self.holiday_lunar:
                # 检查年份是否在农历支持范围内（1900-2100）
                if year_val < 1900 or year_val > 2100:
                    self.logger.debug(
                        f"农历日期不支持，超出农历1900年1月1日至2100年12月30日，或日期不存在 - Token: {token}"
                    )
                    return []

        # 计算目标年份和时间偏移
        direction = self._determine_direction(token)
        time_offset_num = self._get_offset_time_num(token)
        base_time = self._apply_offset_time_num(base_time, time_offset_num, direction)

        # 根据节假日类型进行处理
        if festival in self.holiday_lunar:
            return self._handle_lunar_holiday(
                festival,
                base_time,
                base_time_raw,
                time_offset_num,
                direction,
                day_offset,
                token,
            )
        elif festival in self.calendar_holiday:
            return self._handle_calendar_holiday(festival, base_time, day_offset)
        elif festival in self.statutory_holiday:
            return self._handle_statutory_holiday(festival, base_time, day_prefix, day_offset)
        elif festival == "暑假":
            # 暑假：当年7月1日至8月末
            start_time = base_time.replace(month=7, day=1, hour=0, minute=0, second=0)
            _, end_of_aug = self._get_month_range(base_time.replace(month=8, day=1))
            return self._format_time_result(start_time, end_of_aug)
        elif festival == "寒假":
            # 寒假：当年2月1日至2月末
            start_time = base_time.replace(month=2, day=1, hour=0, minute=0, second=0)
            _, end_of_feb = self._get_month_range(base_time.replace(month=2, day=1))
            return self._format_time_result(start_time, end_of_feb)
        else:
            return []

    def _handle_lunar_holiday(  # noqa: C901
        self,
        festival,
        base_time,
        base_time_raw,
        time_offset_num,
        direction,
        day_offset,
        token=None,
    ):
        """
        处理农历节假日

        Args:
            festival (str): 节假日名称
            base_time (datetime): 基准时间（可能已经包含指定年份）
            base_time_raw (datetime): 原始基准时间
            time_offset_num (dict): 时间偏移数字
            direction (int): 偏移方向
            day_offset (int): 天数偏移

        Returns:
            list: 时间范围列表
        """
        try:
            # 获取农历月日
            lunar_month, lunar_day = self.holiday_lunar[festival]

            if festival == "除夕":
                # 除夕是农历年的最后一天（腊月三十或腊月二十九）
                # 计算方法：先计算农历正月初一，然后减去一天
                # 确定目标农历年份
                if token and token.get("year"):
                    # token中指定了公历年份，需要转换为农历年份
                    # 使用该公历年的中间日期来获取农历年份
                    solar_year = base_time.year
                    tmp_date = datetime.datetime(solar_year, 6, 15)
                    lunar_date_now = zhdate.ZhDate.from_datetime(tmp_date)
                    lunar_target_year = lunar_date_now.lunar_year
                else:
                    # 没有指定年份，从基准时间推导农历年份
                    tmp_date = datetime.datetime(
                        base_time_raw.year, base_time_raw.month, base_time_raw.day
                    )
                    lunar_date_now = zhdate.ZhDate.from_datetime(tmp_date)
                    lunar_target_year = lunar_date_now.lunar_year

                # 应用时间偏移
                offset_year_val = (
                    int(token.get("offset_year", 0)) if token.get("offset_year") else 0
                )
                if offset_year_val != 0:
                    # 对于"去年除夕"，offset_year_val=-1
                    # "去年"指的是公历年的偏移
                    # 需要找到偏移后的公历年对应的农历年，然后计算该农历年的除夕
                    if token and token.get("year"):
                        # 如果有指定年份，应用偏移
                        solar_year = base_time.year + offset_year_val
                    else:
                        # 没有指定年份，应用偏移到基准时间
                        solar_year = base_time_raw.year + offset_year_val

                    # 使用该公历年的中间日期（6月15日）来获取农历年份
                    tmp_date = datetime.datetime(solar_year, 6, 15)
                    lunar_date_now = zhdate.ZhDate.from_datetime(tmp_date)
                    lunar_target_year = lunar_date_now.lunar_year
                # 如果没有偏移，lunar_target_year已经在上面计算好了

                # 确保农历年份在支持范围内
                if lunar_target_year < 1900 or lunar_target_year > 2100:
                    raise ValueError(f"农历年份超出支持范围: {lunar_target_year}")

                # 计算该农历年的正月初一，然后减去一天得到除夕
                try:
                    # 计算下一年的正月初一
                    lunar_new_year = zhdate.ZhDate(lunar_target_year + 1, 1, 1)
                    # 减去一天得到除夕
                    lunar_date = lunar_new_year - 1
                except ValueError as e:
                    raise ValueError(f"无法计算农历 {lunar_target_year} 年的除夕: {e}")
            else:
                # 其他农历节假日
                # 确定目标年份
                if token and token.get("year"):
                    target_year = base_time.year
                else:
                    tmp_date = datetime.datetime(
                        base_time_raw.year, base_time_raw.month, base_time_raw.day
                    )
                    lunar_date_now = zhdate.ZhDate.from_datetime(tmp_date)
                    target_year = lunar_date_now.lunar_year

                # 对于有时间偏移的情况
                new_solar_date = self._apply_offset_time_num(
                    base_time_raw.replace(year=target_year), time_offset_num, direction
                )
                lunar_date = zhdate.ZhDate(new_solar_date.year, lunar_month, lunar_day)

            solar_date = lunar_date.to_datetime()

            # 设置公历日期的开始和结束时间 - 使用基类的天范围函数
            target_date = solar_date + datetime.timedelta(days=day_offset)
            start_of_day, end_of_day = self._get_day_range(target_date)
            return self._format_time_result(start_of_day, end_of_day)

        except ValueError as e:
            # 处理农历日期不存在的情况（如小月没有30天）
            self.logger.debug(f"Invalid lunar date for {festival}: {e}")
            return []
        except Exception as e:
            # 处理其他异常情况
            self.logger.debug(f"Error processing lunar holiday {festival}: {e}")
            return []

    def _handle_calendar_holiday(self, festival, base_time, day_offset):
        """
        处理公历节假日

        Args:
            festival (str): 节假日名称
            base_time (datetime): 基准时间
            day_offset (int): 天数偏移

        Returns:
            list: 时间范围列表
        """
        # 获取特殊节假日的日期
        # 暑假：当年7月1日至8月末
        if festival == "暑假":
            start_time = base_time.replace(month=7, day=1, hour=0, minute=0, second=0)
            _, end_of_aug = self._get_month_range(base_time.replace(month=8, day=1))
            target_start = start_time + datetime.timedelta(days=day_offset)
            # day_offset 对整段的处理：仅平移开始日，结束仍为8月末（也可按需同时平移）
            return self._format_time_result(target_start, end_of_aug)
        elif festival == "寒假":
            # 寒假：整个二月份
            start_time = base_time.replace(month=2, day=1, hour=0, minute=0, second=0)
            _, end_of_feb = self._get_month_range(base_time.replace(month=2, day=1))
            target_start = start_time + datetime.timedelta(days=day_offset)
            return self._format_time_result(target_start, end_of_feb)
        elif festival == "父亲节":
            month, day = fathers_day(base_time.year)
        elif festival == "母亲节":
            month, day = mothers_day(base_time.year)
        elif festival == "感恩节":
            month, day = gives_day(base_time.year)
        else:
            month, day = self.calendar_holiday[festival]

        # 使用基类的天范围函数
        target_date = base_time.replace(month=month, day=day) + datetime.timedelta(days=day_offset)
        start_of_day, end_of_day = self._get_day_range(target_date)
        return self._format_time_result(start_of_day, end_of_day)

    def _handle_statutory_holiday(self, festival, base_time, day_prefix, day_offset):
        """
        处理法定节假日

        Args:
            festival (str): 节假日名称
            base_time (datetime): 基准时间
            day_prefix (str): 天数前缀
            day_offset (int): 天数偏移

        Returns:
            list: 时间范围列表
        """
        # 读取节假日配置文件
        json_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "../data/holiday/holidays.json"
        )

        try:
            with open(json_path, "r", encoding="utf-8") as f:
                holidays_data = json.load(f)
        except FileNotFoundError:
            self.logger.warning(f"Holiday data file not found: {json_path}")
            return []

        # 获取对应年份的节假日数据
        year_str = str(base_time.year)
        if year_str in holidays_data:  # 节日时间为近五年
            holiday_info = holidays_data[year_str][festival]
            start_date = holiday_info["start_time"]
            end_date = holiday_info["end_time"]
            start_time = datetime.datetime.strptime(start_date, "%Y-%m-%d").replace(
                hour=0, minute=0, second=0
            )
            end_time = datetime.datetime.strptime(end_date, "%Y-%m-%d").replace(
                hour=23, minute=59, second=59
            )
        else:  # 时间为近五年之外
            holiday_info = holidays_data["normal"][festival]
            start_date = holiday_info["start_time"]
            end_date = holiday_info["end_time"]
            start_time = datetime.datetime.strptime(start_date, "%Y-%m-%d").replace(
                year=base_time.year, hour=0, minute=0, second=0
            )
            end_time = datetime.datetime.strptime(end_date, "%Y-%m-%d").replace(
                year=base_time.year, hour=23, minute=59, second=59
            )

        # 处理有天数前缀（如 国庆那天）
        if day_prefix:
            day_prefix = int(day_prefix)
            date_month, date_day = self.statutory_holiday[festival]
            target_date = base_time.replace(month=date_month, day=date_day) + datetime.timedelta(
                days=day_prefix
            )
            start_of_day, end_of_day = self._get_day_range(target_date)
            return self._format_time_result(start_of_day, end_of_day)

        return self._format_time_result(start_time, end_time)
