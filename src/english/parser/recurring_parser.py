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

from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from typing import List, Union
import yaml
import os

from .base_parser import BaseParser


class RecurringParser(BaseParser):
    """Parser for recurring time expressions in English"""

    def __init__(self):
        super().__init__()
        self.month_names = {
            "january": 1,
            "february": 2,
            "march": 3,
            "april": 4,
            "may": 5,
            "june": 6,
            "july": 7,
            "august": 8,
            "september": 9,
            "october": 10,
            "november": 11,
            "december": 12,
        }

        self.weekday_names = {
            "monday": 0,
            "tuesday": 1,
            "wednesday": 2,
            "thursday": 3,
            "friday": 4,
            "saturday": 5,
            "sunday": 6,
        }

        # 加载配置文件
        self._load_config()

    def _load_config(self):
        """加载recurring配置文件"""
        config_path = os.path.join(os.path.dirname(__file__), "../config/recurring_config.yaml")

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
                self.recurring_counts = config.get("recurring_counts", {})
                self.default_count = config.get("default", 30)
        except Exception:
            # 如果加载失败，使用默认值
            self.recurring_counts = {
                "day": 30,
                "week": 52,
                "month": 36,
                "quarter": 12,
                "year": 10,
                "hour": 24,
            }
            self.default_count = 30

    def parse(self, token: dict, base_time: datetime) -> List[List[str]]:
        """
        解析recurring token

        Args:
            token: recurring token
            base_time: 基准时间

        Returns:
            List[List[str]]: 时间序列列表
        """
        recurring_type = token.get("recurring_type")

        # 新增：带时间范围的周期类型
        if recurring_type == "day_time_range":
            return self._parse_daily_time_range(token, base_time)

        # 解析有具体时间点的周期
        elif recurring_type == "week_day":
            return self._parse_weekly(token, base_time)
        elif recurring_type in ["month_day", "month_time"]:
            return self._parse_monthly(token, base_time)
        elif recurring_type in ["year_month", "year_time"]:
            return self._parse_yearly(token, base_time)
        elif recurring_type == "day_time":
            return self._parse_daily(token, base_time)
        elif recurring_type == "week" and token.get("week_day"):
            # 处理每周+星期几的情况
            return self._parse_weekly(token, base_time)
        elif recurring_type == "period":
            # 处理周期性时段（如every night, every morning）
            return self._parse_period_recurring(token, base_time)
        else:
            # 对于没有具体时间点的周期，返回时间段（当前时间到9999年底）
            period_types = ["hour", "day", "week", "month", "quarter", "year"]
            if recurring_type in period_types:
                return self._parse_period_range(token, base_time)
            else:
                # 默认返回时间段
                return self._parse_period_range(token, base_time)

    def _parse_period_range(self, token: dict, base_time: datetime) -> List[List[str]]:
        """
        解析周期性时间段
        对于没有具体时间点的周期表达，返回空列表

        Args:
            token: 时间token
            base_time: 基准时间

        Returns:
            list: 空列表 []
        """
        return []

    def _parse_weekly(self, token: dict, base_time: datetime) -> List[List[str]]:
        """
        解析每周+星期几
        例如：every monday, every tuesday
        返回：未来52周内的所有该星期几

        Args:
            token: 时间token
            base_time: 基准时间

        Returns:
            list: 时间点列表或时间段列表
        """
        weekday_name = token.get("week_day", "").lower()
        if not weekday_name:
            return self._parse_period_range(token, base_time)

        weekday_num = self.weekday_names.get(weekday_name)
        if weekday_num is None:
            return self._parse_period_range(token, base_time)

        # 检查是否有具体时间（与中文版本保持一致）
        has_time = bool(token.get("hour") or token.get("minute") or token.get("period"))

        # 从配置获取重复次数
        repeat_count = self.recurring_counts.get("week", 52)

        # 计算未来N周的所有该星期几
        results = []
        current = base_time

        # 找到下一个该星期几
        days_ahead = weekday_num - current.weekday()
        if days_ahead <= 0:  # 如果今天就是该星期几，或者已经过了
            days_ahead += 7

        current = current + timedelta(days=days_ahead)

        # 生成未来N周的所有该星期几
        for _ in range(repeat_count):
            if has_time:
                # 有具体时间：返回时间点
                hour = int(token.get("hour", 0))
                minute = int(token.get("minute", 0))

                # 处理period（morning/afternoon/evening等）
                period = token.get("period", "").lower()
                if period:
                    if period in ["morning", "am"]:
                        hour = 8 if hour == 0 else hour
                    elif period in ["noon", "midday"]:
                        hour = 12 if hour == 0 else hour
                    elif period in ["afternoon", "pm"]:
                        hour = 14 if hour == 0 else hour
                        if hour < 12 and hour != 0:
                            hour += 12
                    elif period in ["evening", "night"]:
                        hour = 20 if hour == 0 else hour
                        if hour < 12:
                            hour += 12

                time_point = current.replace(hour=hour, minute=minute, second=0, microsecond=0)
                results.append([time_point.strftime("%Y-%m-%dT%H:%M:%SZ")])
            else:
                # 无具体时间：返回时间段（整天，与中文版本保持一致）
                start_time = current.replace(hour=0, minute=0, second=0, microsecond=0)
                end_time_day = current.replace(hour=23, minute=59, second=59, microsecond=0)
                results.append(
                    [
                        start_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                        end_time_day.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    ]
                )

            current += timedelta(days=7)

        return results if results else self._parse_period_range(token, base_time)

    def _parse_monthly(self, token: dict, base_time: datetime) -> List[List[str]]:
        """
        解析每月+日期
        例如：every 3rd of the month, every 15th of the month
        返回：未来36个月内的所有该日期

        Args:
            token: 时间token
            base_time: 基准时间

        Returns:
            list: 时间点列表
        """
        day_str = token.get("day", "")
        if not day_str:
            return self._parse_period_range(token, base_time)

        try:
            day = int(day_str)
            if day < 1 or day > 31:
                return self._parse_period_range(token, base_time)
        except ValueError:
            return self._parse_period_range(token, base_time)

        # 从配置获取重复次数
        repeat_count = self.recurring_counts.get("month", 36)

        # 计算未来N个月的所有该日期
        time_points = []
        current = base_time.replace(day=1)  # 从月初开始

        # 生成未来N个月的所有该日期
        for _ in range(repeat_count):
            try:
                # 尝试创建该日期
                target_date = current.replace(day=day)
                if target_date >= base_time:  # 只包含未来或当前日期
                    time_points.append(target_date.strftime("%Y-%m-%dT%H:%M:%SZ"))
            except ValueError:
                # 如果该月没有这一天（如2月30日），跳过
                pass

            # 移动到下个月
            current += relativedelta(months=1)

        return [time_points] if time_points else self._parse_period_range(token, base_time)

    def _parse_yearly(self, token: dict, base_time: datetime) -> List[List[str]]:
        """
        解析每年+月份
        例如：every january, every march
        返回：未来10年内的所有该月份

        Args:
            token: 时间token
            base_time: 基准时间

        Returns:
            list: 时间点列表
        """
        month_name = token.get("month", "").lower()
        if not month_name:
            return self._parse_period_range(token, base_time)

        month_num = self.month_names.get(month_name)
        if month_num is None:
            return self._parse_period_range(token, base_time)

        # 从配置获取重复次数
        repeat_count = self.recurring_counts.get("year", 10)

        # 计算未来N年的所有该月份
        time_points = []
        current = base_time.replace(month=month_num, day=1)

        # 如果当前月份已经过了，从下一年开始
        if current < base_time:
            current = current.replace(year=current.year + 1)

        # 生成未来N年的所有该月份
        for _ in range(repeat_count):
            time_points.append(current.strftime("%Y-%m-%dT%H:%M:%SZ"))
            current = current.replace(year=current.year + 1)

        return [time_points] if time_points else self._parse_period_range(token, base_time)

    def _parse_daily(self, token: dict, base_time: datetime) -> List[List[str]]:
        """
        解析每天+时间
        例如：every day at 8 am, every day at 9:30
        返回：未来30天的所有该时刻

        Args:
            token: 时间token
            base_time: 基准时间

        Returns:
            list: 时间点列表
        """
        # 从token中提取时间信息
        hour_str = token.get("hour", "")
        minute_str = token.get("minute", "0")
        second_str = token.get("second", "0")

        if not hour_str:
            return self._parse_period_range(token, base_time)

        try:
            hour = int(hour_str)
            minute = int(minute_str)
            second = int(second_str)
        except ValueError:
            return self._parse_period_range(token, base_time)

        # 处理AM/PM
        period = token.get("period", "").lower()
        if period == "pm" and hour != 12:
            hour += 12
        elif period == "am" and hour == 12:
            hour = 0

        # 从配置获取重复次数
        repeat_count = self.recurring_counts.get("day", 30)

        # 计算未来N天的所有该时刻
        time_points = []
        current = base_time.replace(hour=hour, minute=minute, second=second, microsecond=0)

        # 如果今天这个时间已经过了，从明天开始
        if current <= base_time:
            current += timedelta(days=1)

        # 生成未来N天的所有该时刻
        for _ in range(repeat_count):
            time_points.append(current.strftime("%Y-%m-%dT%H:%M:%SZ"))
            current += timedelta(days=1)

        return [time_points] if time_points else self._parse_period_range(token, base_time)

    def _parse_daily_time_range(  # noqa: C901
        self, token: dict, base_time: datetime
    ) -> List[List[str]]:
        """
        解析每天+时间范围
        例如：every day from 7:30 to 9:30, every day from ten to eleven
        返回：未来30天的所有该时间段

        Args:
            token: 时间token
            base_time: 基准时间

        Returns:
            list: 时间段列表
        """
        # 英文单词到数字的映射
        word_to_number = {
            "one": 1,
            "two": 2,
            "three": 3,
            "four": 4,
            "five": 5,
            "six": 6,
            "seven": 7,
            "eight": 8,
            "nine": 9,
            "ten": 10,
            "eleven": 11,
            "twelve": 12,
        }

        # 提取时间范围
        start_hour_str = token.get("start_hour", "0")
        start_minute_str = token.get("start_minute", "0")
        end_hour_str = token.get("end_hour", "0")
        end_minute_str = token.get("end_minute", "0")

        # 转换小时（支持数字和英文单词）
        start_hour = word_to_number.get(start_hour_str.lower(), None)
        if start_hour is None:
            try:
                start_hour = int(start_hour_str)
            except ValueError:
                start_hour = 0

        end_hour = word_to_number.get(end_hour_str.lower(), None)
        if end_hour is None:
            try:
                end_hour = int(end_hour_str)
            except ValueError:
                end_hour = 0

        # 转换分钟
        try:
            start_minute = int(start_minute_str)
        except ValueError:
            start_minute = 0

        try:
            end_minute = int(end_minute_str)
        except ValueError:
            end_minute = 0

        period = token.get("period", "").strip('"').lower()

        # 处理AM/PM
        if period in ["pm", "p.m."]:
            if start_hour < 12:
                start_hour += 12
            if end_hour < 12:
                end_hour += 12
        elif period in ["am", "a.m."]:
            if start_hour == 12:
                start_hour = 0
            if end_hour == 12:
                end_hour = 0

        # 从配置获取重复次数
        repeat_count = self.recurring_counts.get("day", 30)

        # 生成未来N天的时间段序列
        time_ranges = []
        for i in range(repeat_count):
            date = base_time + timedelta(days=i)
            start_time = date.replace(hour=start_hour, minute=start_minute, second=0, microsecond=0)
            end_time = date.replace(hour=end_hour, minute=end_minute, second=0, microsecond=0)

            # 如果结束时间早于开始时间（跨日），结束时间加一天
            if end_time <= start_time:
                end_time += timedelta(days=1)

            time_ranges.append(
                [
                    start_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    end_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                ]
            )

        return [time_ranges] if time_ranges else self._parse_period_range(token, base_time)

    def _parse_period_recurring(self, token: dict, base_time: datetime) -> List[List[str]]:
        """
        解析周期性时段
        例如：every night, every morning, every evening
        返回：未来30天的所有该时段

        Args:
            token: 时间token
            base_time: 基准时间

        Returns:
            list: 时间段列表
        """
        period = token.get("period", "").strip('"').lower()

        if not period:
            return self._parse_period_range(token, base_time)

        # 从配置获取重复次数
        repeat_count = self.recurring_counts.get("period", 30)

        # 生成未来N天的所有该时段
        time_ranges = []

        for i in range(repeat_count):
            # 使用base_time加天数来保持时区信息
            target_datetime = base_time.replace(
                hour=0, minute=0, second=0, microsecond=0
            ) + timedelta(days=i)

            # 使用BaseParser的_parse_period方法获取时段
            start_time, end_time = self._parse_period(target_datetime, period)

            # 只包含未来的时段（去除时区比较，直接添加所有时段）
            time_ranges.append(
                [
                    start_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    end_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                ]
            )

        return [time_ranges] if time_ranges else self._parse_period_range(token, base_time)
