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
import yaml
import os
from datetime import timedelta
from dateutil.relativedelta import relativedelta
from .base_parser import BaseParser
from .holiday_parser import HolidayParser
from .period_parser import PeriodParser


class RecurringParser(BaseParser):
    """
    周期时间解析器

    处理周期性的时间表达式，如：
    - 每个工作日
    - 每周三
    - 每年9月
    - 每天8点
    """

    def __init__(self):
        """初始化周期时间解析器"""
        super().__init__()
        self.holiday_parser = HolidayParser()
        self.period_parser = PeriodParser()
        self._load_config()

    def _load_config(self):
        """加载recurring配置文件"""
        config_path = os.path.join(os.path.dirname(__file__), "../config/recurring_config.yaml")

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
                self.recurring_counts = config.get("recurring_counts", {})
                self.default_count = config.get("default", 30)
                # 加载解析开关，默认False（统一返回空）
                self.enable_parsing = config.get("enable_recurring_parsing", False)
        except Exception:
            # 如果加载失败，使用默认值
            self.recurring_counts = {
                "day": 30,
                "week": 52,
                "month": 36,
                "quarter": 12,
                "year": 10,
                "hour": 24,
                "interval": 30,
            }
            self.default_count = 30
            self.enable_parsing = False

    def parse(self, token, base_time):  # noqa: C901
        """
        解析周期时间表达式

        Args:
            token (dict): 时间表达式token
            base_time (datetime): 基准时间

        Returns:
            list: 周期时间点列表，或空列表（不解析的类型）
        """
        # 如果未启用解析功能，统一返回空列表
        if not self.enable_parsing:
            return []

        recurring_type = token.get("recurring_type")

        # 对于没有具体时间点的周期，返回时间段
        period_types = ["hour", "day", "month", "quarter", "year", "interval"]
        if recurring_type in period_types:
            return self._parse_period_range(token, base_time)

        # 特殊处理：week类型需要检查是否有week_day
        if recurring_type == "week" and not token.get("week_day"):
            return self._parse_period_range(token, base_time)

        # 解析有具体时间点的周期
        if recurring_type == "week_day":
            return self._parse_weekly(token, base_time)
        elif recurring_type == "week" and token.get("week_day"):
            # 处理每周+星期几的情况
            return self._parse_weekly(token, base_time)
        elif recurring_type in ["month_day", "month_time"]:
            return self._parse_monthly(token, base_time)
        elif recurring_type in ["year_month", "year_time"]:
            return self._parse_yearly(token, base_time)
        elif recurring_type == "day_time":
            return self._parse_daily(token, base_time)
        elif recurring_type == "interval_time":
            return self._parse_interval_time(token, base_time)
        elif recurring_type == "year_holiday":
            return self._parse_yearly_holiday(token, base_time)
        elif recurring_type == "year_season":
            return self._parse_yearly_season(token, base_time)

        # 其他类型暂不解析
        return []

    def _parse_weekly(self, token, base_time):  # noqa: C901
        """
        解析每周+星期几
        例如：每周一、每周一早上八点半
        返回：未来配置周数内的所有该星期几
        """
        week_day = token.get("week_day")
        if not week_day:
            return []

        # 处理多个星期值（如"末"表示6,7）
        try:
            weekdays = [int(d) for d in str(week_day).split(",")]
        except (ValueError, TypeError):
            # 如果week_day不是字符串或数字，尝试直接转换
            try:
                weekdays = [int(week_day)]
            except (ValueError, TypeError):
                return []

        # 检查是否有具体时间
        has_time = bool(token.get("hour") or token.get("minute") or token.get("noon"))

        results = []
        # 使用配置的week数量
        repeat_count = self.recurring_counts.get("week", 52)
        end_time = base_time + timedelta(weeks=repeat_count)

        for wd in weekdays:
            # 转换为Python weekday (Monday=0, Sunday=6)
            # 我们的weekday.tsv中：一=1, 二=2, ..., 日=7
            # Python中：Monday=0, Tuesday=1, ..., Sunday=6
            target_weekday = (wd - 1) % 7  # 将1-7映射到0-6

            # 找到第一个匹配的日期
            current = base_time
            days_ahead = (target_weekday - current.weekday()) % 7
            if days_ahead == 0:
                days_ahead = 7  # 如果今天就是目标星期，从下周开始

            current = current + timedelta(days=days_ahead)

            # 生成所有匹配的日期（每周一次），直到10年后
            while current <= end_time:
                if has_time:
                    # 有具体时间：返回时间点
                    hour = int(token.get("hour", 0))
                    minute = int(token.get("minute", 0))

                    # 处理noon（早上/中午/晚上）
                    noon = token.get("noon", "")
                    if noon:
                        # 根据noon设置默认时间
                        if noon in ["早上", "早", "晨"]:
                            hour = 8 if hour == 0 else hour
                        elif noon in ["中午", "午"]:
                            hour = 12 if hour == 0 else hour
                        elif noon in ["下午", "午后"]:
                            hour = 14 if hour == 0 else hour
                        elif noon in ["晚上", "晚", "夜里", "夜间"]:
                            hour = 20 if hour == 0 else hour
                            if hour < 12:
                                hour += 12
                        elif noon in ["深夜", "半夜"]:
                            hour = 23 if hour == 0 else hour

                    time_point = current.replace(hour=hour, minute=minute, second=0, microsecond=0)
                    results.append([time_point.strftime("%Y-%m-%dT%H:%M:%SZ")])
                else:
                    # 无具体时间：返回时间段（整天）
                    start_time = current.replace(hour=0, minute=0, second=0, microsecond=0)
                    end_time_day = current.replace(
                        hour=23, minute=59, second=59, microsecond=999999
                    )
                    results.append(
                        [
                            start_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                            end_time_day.strftime("%Y-%m-%dT%H:%M:%SZ"),
                        ]
                    )

                current += timedelta(weeks=1)

        return results

    def _parse_monthly(self, token, base_time):
        """
        解析每月+日期
        例如：每月三号、每月三号八点
        返回：未来配置月数内的所有该日期
        """
        day = token.get("day")
        if not day:
            return []

        day = int(day)
        hour = int(token.get("hour", 0))
        minute = int(token.get("minute", 0))

        # 处理noon（早上/中午/晚上）
        noon = token.get("noon", "")
        if noon in ["晚上", "晚", "夜里", "夜间"] and hour < 12:
            hour += 12

        # 检查是否有具体时间
        has_time = bool(token.get("hour") or token.get("minute") or token.get("noon"))

        results = []
        # 使用配置的month数量
        repeat_count = self.recurring_counts.get("month", 36)
        end_time = base_time + relativedelta(months=repeat_count)

        # 从当前月份开始
        current = base_time.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        while current <= end_time:
            try:
                # 尝试设置为目标日期
                target = current.replace(day=day)
                if target > base_time:
                    if has_time:
                        # 有具体时间：返回时间点
                        target = target.replace(hour=hour, minute=minute, second=0, microsecond=0)
                        results.append([target.strftime("%Y-%m-%dT%H:%M:%SZ")])
                    else:
                        # 无具体时间：返回时间段（整天）
                        start_time = target.replace(hour=0, minute=0, second=0, microsecond=0)
                        end_time_day = target.replace(
                            hour=23, minute=59, second=59, microsecond=999999
                        )
                        results.append(
                            [
                                start_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                                end_time_day.strftime("%Y-%m-%dT%H:%M:%SZ"),
                            ]
                        )
            except ValueError:
                # 该月没有这一天（如2月30日）
                pass

            # 移到下个月
            current += relativedelta(months=1)

        return [results]  # 外层包裹

    def _parse_yearly(self, token, base_time):
        """
        解析每年+月份
        例如：每年三月、每年三月十五号
        返回：未来配置年数内的所有该月份（或日期）
        """
        month = token.get("month")
        if not month:
            return []

        month = int(month)
        day = token.get("day")
        hour = int(token.get("hour", 0))
        minute = int(token.get("minute", 0))

        # 检查是否有具体日期
        has_day = bool(day)
        if has_day:
            day = int(day)

        # 检查是否有具体时间
        has_time = bool(token.get("hour") or token.get("minute") or token.get("noon"))

        results = []
        # 使用配置的year数量
        repeat_count = self.recurring_counts.get("year", 10)
        end_time = base_time + relativedelta(years=repeat_count)
        # 从当前年份开始
        current_year = base_time.year

        for year in range(current_year, current_year + repeat_count + 1):
            try:
                if has_day:
                    # 有具体日期：返回具体日期
                    target = base_time.replace(
                        year=year,
                        month=month,
                        day=day,
                        hour=hour,
                        minute=minute,
                        second=0,
                        microsecond=0,
                    )
                    if target > base_time and target <= end_time:
                        if has_time:
                            # 有具体时间：返回时间点
                            results.append([target.strftime("%Y-%m-%dT%H:%M:%SZ")])
                        else:
                            # 无具体时间：返回时间段（整天）
                            start_time = target.replace(hour=0, minute=0, second=0, microsecond=0)
                            end_time_day = target.replace(
                                hour=23, minute=59, second=59, microsecond=999999
                            )
                            results.append(
                                [
                                    start_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                                    end_time_day.strftime("%Y-%m-%dT%H:%M:%SZ"),
                                ]
                            )
                else:
                    # 无具体日期：返回整个月份的时间段
                    start_time = base_time.replace(
                        year=year,
                        month=month,
                        day=1,
                        hour=0,
                        minute=0,
                        second=0,
                        microsecond=0,
                    )
                    # 计算该月的最后一天
                    last_day = calendar.monthrange(year, month)[1]
                    end_time_month = base_time.replace(
                        year=year,
                        month=month,
                        day=last_day,
                        hour=23,
                        minute=59,
                        second=59,
                        microsecond=999999,
                    )
                    if start_time > base_time and start_time <= end_time:
                        results.append(
                            [
                                start_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                                end_time_month.strftime("%Y-%m-%dT%H:%M:%SZ"),
                            ]
                        )
            except ValueError:
                # 无效日期（如2月30日）
                pass

        return [results]  # 外层包裹

    def _parse_daily(self, token, base_time):  # noqa: C901
        """
        解析每天+时间
        例如：每天早上八点半、每天早上
        返回：未来配置天数内的所有该时间点或时间段（每天）
        """
        raw_hour = token.get("hour")
        raw_minute = token.get("minute")
        minute = int(raw_minute) if raw_minute is not None else 0
        noon = token.get("noon", "")

        # 是否显式给出小时/分钟
        has_explicit_time = raw_hour is not None or raw_minute is not None
        hour = raw_hour

        # 如果没有hour但有noon，根据noon设置默认时间
        if not hour and noon:
            if noon in ["早上", "早", "晨"]:
                hour = 8
            elif noon in ["中午", "午"]:
                hour = 12
            elif noon in ["下午", "午后"]:
                hour = 14
            elif noon in ["晚上", "晚", "夜里", "夜间"]:
                hour = 20
            elif noon in ["深夜", "半夜"]:
                hour = 23
            else:
                return []  # 不认识的noon类型
            has_explicit_time = False  # 仅凭noon默认时间段
        elif not hour:
            return []  # 既没有hour也没有noon

        hour = int(hour)

        # 处理noon（早上/中午/晚上）
        if noon in ["晚上", "晚", "夜里", "夜间"] and hour < 12:
            hour += 12

        results = []
        # 使用配置的day数量
        repeat_count = self.recurring_counts.get("day", 30)
        end_time = base_time + timedelta(days=repeat_count)

        if has_explicit_time:
            # 显式时间：按照具体时刻生成事件点
            current = base_time.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if current <= base_time:
                current += timedelta(days=1)

            while current <= end_time:
                results.append([current.strftime("%Y-%m-%dT%H:%M:%SZ")])
                current += timedelta(days=1)
        else:
            # 仅凭noon：使用时间段范围
            base_day = base_time.replace(hour=0, minute=0, second=0, microsecond=0)
            start_range, end_range = self._parse_noon(base_day, noon)
            if start_range <= base_time:
                base_day += timedelta(days=1)
                start_range, end_range = self._parse_noon(base_day, noon)

            while start_range <= end_time:
                results.append(
                    [
                        start_range.strftime("%Y-%m-%dT%H:%M:%SZ"),
                        end_range.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    ]
                )
                base_day += timedelta(days=1)
                start_range, end_range = self._parse_noon(base_day, noon)

        return [results]  # 外层包裹

    def _parse_interval_time(self, token, base_time):  # noqa: C901
        """
        解析间隔型周期+时间
        例如：每两天晚上八点、每三天早上八点
        返回：未来配置数量内的所有该间隔时间点
        """
        interval = token.get("interval")
        unit = token.get("unit")
        hour = token.get("hour")
        minute = token.get("minute", 0)

        if not interval or not unit or not hour:
            return []

        try:
            interval = int(interval)
            hour = int(hour)
            minute = int(minute)
        except (ValueError, TypeError):
            return []

        # 处理noon（早上/中午/晚上）
        noon = token.get("noon", "")
        if noon in ["晚上", "晚", "夜里", "夜间"] and hour < 12:
            hour += 12

        results = []
        # 使用配置的interval数量
        repeat_count = self.recurring_counts.get("interval", 30)
        # 根据单位计算结束时间
        if unit == "day":
            end_time = base_time + timedelta(days=interval * repeat_count)
        elif unit == "week":
            end_time = base_time + timedelta(weeks=interval * repeat_count)
        elif unit == "month":
            end_time = base_time + relativedelta(months=interval * repeat_count)
        elif unit == "year":
            end_time = base_time + relativedelta(years=interval * repeat_count)
        else:
            end_time = base_time + timedelta(days=interval * repeat_count)

        # 从base_time的下一个目标时间开始
        current = base_time.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if current <= base_time:
            # 根据单位计算下一个时间点
            if unit == "day":
                current += timedelta(days=interval)
            elif unit == "week":
                current += timedelta(weeks=interval)
            elif unit == "month":
                current += relativedelta(months=interval)
            elif unit == "year":
                current += relativedelta(years=interval)
            else:
                return []

        # 生成所有匹配的时间点
        while current <= end_time:
            results.append([current.strftime("%Y-%m-%dT%H:%M:%SZ")])

            # 根据单位计算下一个时间点
            if unit == "day":
                current += timedelta(days=interval)
            elif unit == "week":
                current += timedelta(weeks=interval)
            elif unit == "month":
                current += relativedelta(months=interval)
            elif unit == "year":
                current += relativedelta(years=interval)
            else:
                break

        return [results]  # 外层包裹

    def _parse_period_range(self, token, base_time):
        """
        解析周期性时间段
        对于没有具体时间点的周期表达，返回为空列表

        Args:
            token: 时间token
            base_time: 基准时间

        Returns:
            list: 时间段 [['start_time', 'end_time']]
        """
        # start_time = base_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        # end_time = "9999-12-31T23:59:59Z"
        # return [[start_time, end_time]]
        return []

    def _parse_yearly_holiday(self, token, base_time):
        """
        解析每年+节日
        例如：每年春节、每年国庆节、每年暑假
        返回：未来配置年数内的所有该节日时间段
        """
        festival = token.get("festival")
        if not festival:
            return []

        results = []
        # 使用配置的year数量
        repeat_count = self.recurring_counts.get("year", 10)
        # 从当前年份开始
        current_year = base_time.year

        for year in range(current_year, current_year + repeat_count + 1):
            # 使用HolidayParser解析该年的节日
            holiday_token = {
                "type": "time_holiday",
                "festival": festival,
                "year": str(year),
            }

            try:
                # 调用holiday_parser获取节日时间段
                holiday_results = self.holiday_parser.parse(holiday_token, base_time)
                if holiday_results:
                    # holiday_results格式可能是 [{'type': 'timestamp', 'datetime': '...'}] 或 [['start', 'end']]
                    for result in holiday_results:
                        if isinstance(result, dict):
                            # 转换为时间段格式
                            datetime_str = result.get("datetime", "")
                            if datetime_str:
                                results.append([datetime_str, datetime_str])
                        elif isinstance(result, list) and len(result) >= 2:
                            # 已经是时间段格式
                            results.append(result)
            except Exception:
                # 如果解析失败，跳过该年
                continue

        return [results]  # 外层包裹

    def _parse_yearly_season(self, token, base_time):
        """
        解析每年+季节
        例如：每年春天、每年秋天
        返回：未来配置年数内的所有该季节时间段
        """
        season = token.get("season")
        if not season:
            return []

        results = []
        # 使用配置的year数量
        repeat_count = self.recurring_counts.get("year", 10)

        # 从当前年份开始
        current_year = base_time.year

        for year in range(current_year, current_year + repeat_count + 1):
            # 使用PeriodParser解析该年的季节
            season_token = {"type": "time_period", "season": season, "year": str(year)}

            try:
                # 调用period_parser获取季节时间段
                season_results = self.period_parser.parse(season_token, base_time)
                if season_results:
                    # season_results格式可能是 [{'type': 'timestamp', 'datetime': '...'}] 或 [['start', 'end']]
                    for result in season_results:
                        if isinstance(result, dict):
                            # 转换为时间段格式
                            datetime_str = result.get("datetime", "")
                            if datetime_str:
                                results.append([datetime_str, datetime_str])
                        elif isinstance(result, list) and len(result) >= 2:
                            # 已经是时间段格式
                            results.append(result)
            except Exception:
                # 如果解析失败，跳过该年
                continue

        return [results]  # 外层包裹
