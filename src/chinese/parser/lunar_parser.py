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

import datetime
import zhdate
from lunarcalendar import Converter, Solar, Lunar, DateNotExist, solarterm
from .base_parser import BaseParser
from ...core.logger import get_logger


class LunarParser(BaseParser):
    """
    农历时间解析器

    处理农历相关的时间表达式，包括：
    - 农历日期（如：农历七月初八）
    - 二十四节气（如：立春、清明）
    - 农历月份（如：农历八月）
    """

    def __init__(self):
        """初始化农历解析器"""
        super().__init__()
        self.logger = get_logger(__name__)

        # 二十四节气映射
        self.jieqi_list = {
            "小寒": "XiaoHan",
            "大寒": "DaHan",
            "立春": "LiChun",
            "雨水": "YuShui",
            "惊蛰": "JingZhe",
            "春分": "ChunFen",
            "清明": "QingMing",
            "谷雨": "GuYu",
            "立夏": "LiXia",
            "小满": "XiaoMan",
            "芒种": "MangZhong",
            "夏至": "XiaZhi",
            "小暑": "XiaoShu",
            "大暑": "DaShu",
            "立秋": "LiQiu",
            "处暑": "ChuShu",
            "白露": "BaiLu",
            "秋分": "QiuFen",
            "寒露": "HanLu",
            "霜降": "ShuangJiang",
            "立冬": "LiDong",
            "小雪": "XiaoXue",
            "大雪": "DaXue",
            "冬至": "DongZhi",
        }

    def parse(self, token, base_time):
        """
        解析农历时间表达式

        Args:
            token (dict): 时间表达式token，格式如：{'type': 'time_lunar', 'lunar_month': '1', 'lunar_day': '1'}
            base_time (datetime): 基准时间

        Returns:
            list: 时间范围列表，格式为 [[start_time_str, end_time_str]]
        """
        jieqi = token.get("lunar_jieqi", "")
        month_period = token.get("month_period", "")

        if jieqi in self.jieqi_list:
            return self._handle_lunar_jieqi(token, base_time)
        elif month_period:
            return self._handle_lunar_month_period(token, base_time)
        else:
            return self._handle_lunar_date(token, base_time)

    def _handle_lunar_jieqi(self, token, base_time):
        """
        处理农历节气

        Args:
            token (dict): 时间表达式token
            base_time (datetime): 基准时间

        Returns:
            list: 时间范围列表
        """
        jieqi = token.get("lunar_jieqi", "")
        fun_jieqi = self.jieqi_list[jieqi]
        lunar_year = token.get("lunar_year", "").strip('"')
        year_offset = int(token.get("lunar_year_prefix", 0))
        day_offset = int(token.get("day_pre", 0))

        if lunar_year:
            # 归一化两位年份为四位
            try:
                year_tmp = int(lunar_year)
                year_tmp = self._normalize_year(year_tmp)
            except Exception:
                year_tmp = base_time.year + year_offset
        else:
            # 应用年份偏移
            year_tmp = base_time.year + year_offset

        jieqi_date = getattr(solarterm, fun_jieqi)(year_tmp) + datetime.timedelta(days=day_offset)
        start_time = base_time.replace(
            year=year_tmp,
            month=jieqi_date.month,
            day=jieqi_date.day,
            hour=0,
            minute=0,
            second=0,
        )
        end_time = start_time.replace(hour=23, minute=59, second=59)
        return self._format_time_result(start_time, end_time)

    def _handle_lunar_month_period(self, token, base_time):
        """
        处理农历月份期间（如：十一月初）

        Args:
            token (dict): 时间表达式token
            base_time (datetime): 基准时间

        Returns:
            list: 时间范围列表
        """
        try:
            lunar_month = int(token.get("lunar_month", "1"))
            month_period = token.get("month_period", "")

            # 确定农历年份：使用base_time的年份
            year_tmp = base_time.year

            # 根据月份期间确定日期范围
            if month_period == "earlymonth":
                # 月初：初一到初十
                start_day = 1
                end_day = 10
            elif month_period == "midmonth":
                # 中旬：十一到二十
                start_day = 11
                end_day = 20
            elif month_period == "latemonth":
                # 下旬：二十一到月末
                start_day = 21
                end_day = 30  # 农历月份最多30天
            else:
                # 默认月初
                start_day = 1
                end_day = 10

            # 转换为阳历日期
            start_lunar = zhdate.ZhDate(year_tmp, lunar_month, start_day)
            end_lunar = zhdate.ZhDate(year_tmp, lunar_month, end_day)

            start_solar = start_lunar.to_datetime()
            end_solar = end_lunar.to_datetime()

            start_time = start_solar.replace(hour=0, minute=0, second=0)
            end_time = end_solar.replace(hour=23, minute=59, second=59)

            return self._format_time_result(start_time, end_time)

        except Exception:
            return []

    def _handle_lunar_date(self, token, base_time):  # noqa: C901
        """
        处理农历日期

        Args:
            token (dict): 时间表达式token
            base_time (datetime): 基准时间

        Returns:
            list: 时间范围列表
        """
        try:
            # 获取当前basetime的农历日期，主要是为了获取当前的农历年份
            tmp = datetime.datetime(base_time.year, base_time.month, base_time.day)
            lunar_tmp = zhdate.ZhDate.from_datetime(tmp)  # 从阳历日期转换成农历日期对象

            lunar_mon = token.get("lunar_month", "").strip('"')
            if lunar_mon:
                lunar_mon = int(lunar_mon)
            else:
                lunar_mon = lunar_tmp.lunar_month

            lunar_day_tmp = token.get("lunar_day", "").strip('"')
            if lunar_day_tmp:
                lunar_day = int(lunar_day_tmp)
            else:
                lunar_day = lunar_tmp.lunar_day

            # 转换农历到公历
            year_offset = int(token.get("lunar_year_prefix", 0))
            lunar_year_str = token.get("lunar_year", "").strip('"')
            if lunar_year_str:
                year_tmp = int(lunar_year_str)
            else:
                # 应用年份偏移
                year_tmp = lunar_tmp.lunar_year + year_offset

            if lunar_day_tmp:  # 有具体日，返回为一天，如农历七月初八
                lunar_date = zhdate.ZhDate(year_tmp, lunar_mon, lunar_day)
                solar_date = lunar_date.to_datetime()

                # 检查是否有时间段和具体时间
                noon_str = token.get("noon")
                hour = token.get("hour")

                if noon_str and hour:
                    # 有时间段和具体时间，返回具体时间点
                    time_num = {"hour": int(hour)}
                    return self._handle_noon_time_with_hour(solar_date, noon_str, time_num)
                elif noon_str:
                    # 只有时间段，返回时间段范围
                    start_time, end_time = self._parse_noon(solar_date, noon_str)
                    return self._format_time_result(start_time, end_time)
                else:
                    # 使用基类的天范围函数
                    start_of_day, end_of_day = self._get_day_range(solar_date)
                    return self._format_time_result(start_of_day, end_of_day)
            else:  # 无具体日，返回整个月范围（农历月起止映射到公历）
                # 优先尝试平月；失败则尝试闰月
                leap_flag = False
                try:
                    lunar_date_start = zhdate.ZhDate(year_tmp, lunar_mon, 1)
                except Exception:
                    try:
                        lunar_date_start = zhdate.ZhDate(year_tmp, lunar_mon, 1, leap_month=True)
                        leap_flag = True
                    except Exception as e:
                        self.logger.debug(f"Invalid lunar date for {token}: {e}")
                        return []

                # 计算该农历月的最后一天：优先尝试30，否则29
                try:
                    lunar_date_end = zhdate.ZhDate(year_tmp, lunar_mon, 30, leap_month=leap_flag)
                except Exception:
                    try:
                        lunar_date_end = zhdate.ZhDate(
                            year_tmp, lunar_mon, 29, leap_month=leap_flag
                        )
                    except Exception as e:
                        self.logger.debug(f"Invalid lunar date for {token}: {e}")
                        return []

                try:
                    start_solar = lunar_date_start.to_datetime().replace(hour=0, minute=0, second=0)
                    end_solar = lunar_date_end.to_datetime().replace(hour=23, minute=59, second=59)
                    return self._format_time_result(start_solar, end_solar)
                except Exception as e:
                    self.logger.debug(f"Invalid lunar date for {token}: {e}")
                    return []

        except ValueError as e:
            # 处理农历日期不存在的情况（如小月没有30天）
            self.logger.debug(f"Invalid lunar date for {token}: {e}")
            return []

    def _handle_noon_time_with_hour(self, base_time, noon_str, time_num):
        """
        处理时间段与具体时间结合

        Args:
            base_time (datetime): 基准时间
            noon_str (str): 时间段字符串
            time_num (dict): 时间数字字典

        Returns:
            list: 时间范围列表
        """
        # 时间段与具体时间结合
        start_time, end_time = self._parse_noon(base_time, noon_str)

        # 处理下午时间
        if noon_str in ["下午", "傍晚", "晚上", "晚", "夜间", "深夜"] and time_num["hour"] <= 12:
            time_num["hour"] += 12
            if time_num["hour"] >= 24:
                time_num["hour"] -= 24
                start_time = start_time + datetime.timedelta(days=1)
        if noon_str == "中午" and time_num["hour"] < 11:
            time_num["hour"] += 12

        if "hour" in time_num and "minute" not in time_num:
            if time_num["hour"] >= 24:
                time_num["hour"] -= 24
                start_time = start_time + datetime.timedelta(days=1)
            target_time = start_time.replace(hour=time_num["hour"], minute=0)
            return self._format_time_result(target_time)
        elif "hour" in time_num and "minute" in time_num and "second" in time_num:
            if time_num["hour"] >= 24:
                time_num["hour"] -= 24
                start_time = start_time + datetime.timedelta(days=1)
            target_time = start_time.replace(
                hour=time_num["hour"],
                minute=time_num["minute"],
                second=time_num["second"],
            )
            return self._format_time_result(target_time)
        elif "hour" in time_num and "minute" in time_num:
            if time_num["hour"] >= 24:
                time_num["hour"] -= 24
                start_time = start_time + datetime.timedelta(days=1)
            target_time = start_time.replace(hour=time_num["hour"], minute=time_num["minute"])
            return self._format_time_result(target_time)

        return []
