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
import zhdate
from lunarcalendar import Converter, Solar, Lunar, DateNotExist, solarterm
from .base_parser import BaseParser


class BetweenParser(BaseParser):
    """
    时间范围解析器

    处理时间范围相关的时间表达式，支持多种时间类型：
    - 相对时间（relative）
    - UTC时间（utc）
    - 农历时间（lunar）
    """

    def __init__(self):
        """初始化时间范围解析器"""
        super().__init__()

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
        解析时间范围表达式

        Args:
            token (dict): 时间表达式token
            base_time (datetime): 基准时间

        Returns:
            list: 时间范围列表，格式为 [[start_time_str, end_time_str]]
        """
        raw_type = token.get("raw_type")

        if raw_type == "relative":
            return self._parse_relative_time(token, base_time)
        elif raw_type == "utc":
            return self._parse_utc_time(token, base_time)
        elif raw_type == "lunar":
            return self._parse_lunar_time(token, base_time)
        else:
            return []

    def _parse_relative_time(self, token, base_time):
        """
        解析相对时间表达式

        Args:
            token (dict): 时间表达式token
            base_time (datetime): 基准时间

        Returns:
            list: 时间范围列表
        """
        # 优先处理：相对年偏移 + 月.日 到 月.日 的整体区间
        if all(k in token for k in ("month", "day", "month2", "day2")):
            return self._handle_month_day_to_month_day_range(token, base_time)

        direction = self._determine_direction(token)
        time_num = self._get_time_num(token)
        time_offset_num = self._get_offset_time_num(token)
        base_time = self._apply_offset_time_num(base_time, time_offset_num, direction)

        # 记录是否存在 hour==24 的场景，基类会进位到次日0时
        hour_is_24 = "hour" in time_num and time_num["hour"] == 24
        if time_num:
            base_time = self._set_time_num(base_time, time_num)
            # 避免重复进位：若原始hour为24，基类已将时间推进至次日0时
            # 直接返回该时间点，避免后续任何再次根据hour计算而进位
            if hour_is_24:
                return self._format_time_result(base_time)

        noon_str = token.get("noon")

        # 使用基类的noon时间处理函数
        if noon_str:
            if "hour" not in time_num and "minute" not in time_num and "second" not in time_num:
                return self._handle_noon_time(base_time, noon_str)
            elif "hour" in time_num and noon_str:
                return self._handle_noon_time_with_hour(base_time, noon_str, time_num)

        # 处理年月日
        return self._handle_relative_datetime(base_time, time_num, time_offset_num)

    def _parse_utc_time(self, token, base_time):  # noqa: C901
        """
        解析UTC时间表达式

        Args:
            token (dict): 时间表达式token
            base_time (datetime): 基准时间

        Returns:
            list: 时间范围列表
        """
        # 首先检查单token的基于单位/整体范围
        if "year2" in token:
            return self._handle_year_range(token, base_time)
        elif "month2" in token:
            return self._handle_month_range(token, base_time)
        elif "day2" in token:
            return self._handle_day_range(token, base_time)
        elif "hour2" in token:
            return self._handle_hour_range(token, base_time)

        # 整体：相对年偏移 + 月.日 到 月.日（在BetweenRule中一次吐出）
        if token.get("raw_type") in ("relative", "utc") and all(
            k in token for k in ("month", "day", "month2", "day2")
        ):
            return self._handle_month_day_to_month_day_range(token, base_time)

        # 若是"现在"，清理所有offset，避免误继承
        if token.get("noon") == "现在":
            for k in [
                "offset_year",
                "offset_month",
                "offset_day",
                "offset_hour",
                "offset_minute",
                "offset_second",
                "offset_quarter",
                "offset_direction",
            ]:
                token.pop(k, None)
        direction = self._determine_direction(token)
        time_num = self._get_time_num(token)
        time_offset_num = self._get_offset_time_num(token)
        base_time = self._apply_offset_time_num(base_time, time_offset_num, direction)

        # 优先处理：year + month + month_end 跨月区间（如：2018年1-9月份）
        month_str = token.get("month")
        month_end_str = token.get("month_end")
        if month_str and month_end_str:
            try:
                start_month = int(month_str)
                end_month = int(month_end_str)
                # 年份：来自token.year，否则使用base_time.year
                year_val = token.get("year")
                if year_val is not None and year_val != "":
                    year_int = int(year_val)
                    year_int = self._normalize_year(year_int)
                else:
                    year_int = base_time.year
                # 起止月份的月初与月末
                start_date = base_time.replace(year=year_int, month=start_month, day=1)
                start_of_month, _ = self._get_month_range(start_date)
                end_date = base_time.replace(year=year_int, month=end_month, day=1)
                _, end_of_month = self._get_month_range(end_date)
                return self._format_time_result(start_of_month, end_of_month)
            except Exception:
                pass

        # 常规设置年月日
        base_time = self._set_time_num(base_time, time_num)

        noon_str = token.get("noon")
        past_key = token.get("past_key", "")
        special_time = token.get("special_time", "")

        # 使用基类的noon时间处理函数
        if noon_str:
            return self._handle_noon_time(base_time, noon_str, time_num)

        # 处理年月日时分秒
        return self._handle_utc_datetime(base_time, time_num, past_key, special_time)

    def _parse_lunar_time(self, token, base_time):
        """
        解析农历时间表达式

        Args:
            token (dict): 时间表达式token
            base_time (datetime): 基准时间

        Returns:
            list: 时间范围列表
        """
        jieqi = token.get("lunar_jieqi", "")

        if jieqi in self.jieqi_list:
            return self._handle_lunar_jieqi(token, base_time)
        else:
            return self._handle_lunar_date(token, base_time)

    def _handle_noon_time_with_hour(self, base_time, noon_str, time_num):
        """
        处理时间段与具体时间结合的情况

        Args:
            base_time (datetime): 基准时间
            noon_str (str): 时间段字符串
            time_num (dict): 时间数字字典

        Returns:
            list: 时间范围列表
        """
        if noon_str in self.noon_time:
            if time_num["hour"] < 12:
                time_num["hour"] += 12
        if "hour" not in time_num and "minute" not in time_num and "second" not in time_num:
            start_time, end_time = self._parse_noon(base_time, noon_str)
            return self._format_time_result(start_time, end_time)
        else:
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

    def _handle_relative_datetime(self, base_time, time_num, time_offset_num):
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

        # 年偏移+月：去年九月 - 使用基类的月范围函数
        if ("year" in time_offset_num and len(time_offset_num) == 1) and (
            "month" in time_num and len(time_num) == 1
        ):
            start_of_month, end_of_month = self._get_month_range(base_time, time_num["month"])
            return self._format_time_result(start_of_month, end_of_month)

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
            if special_time == "lastday":
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
            # 24时的进位已在基类完成，这里不再加1日
            if time_num["hour"] >= 24:
                time_num["hour"] -= 24
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
            # 24时的进位已在基类完成，这里不再加1日
            if time_num["hour"] >= 24:
                time_num["hour"] -= 24
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
            # 24时的进位已在基类完成，这里不再加1日
            if time_num["hour"] >= 24:
                time_num["hour"] -= 24
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
            # 24时的进位已在基类完成，这里不再加1日
            if time_num["hour"] >= 24:
                time_num["hour"] -= 24
            start_of_day = base_time.replace(hour=time_num["hour"], minute=0, second=0)
            return self._format_time_result(start_of_day)
        elif "hour" in time_num and "minute" in time_num and "second" not in time_num:
            # 24时的进位已在基类完成，这里不再加1日
            if time_num["hour"] >= 24:
                time_num["hour"] -= 24
            start_of_day = base_time.replace(
                hour=time_num["hour"], minute=time_num["minute"], second=0
            )
            return self._format_time_result(start_of_day)
        else:
            return self._format_time_result(base_time)

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
            year_tmp = int(lunar_year)
        else:
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

    def _handle_lunar_date(self, token, base_time):
        """
        处理农历日期

        Args:
            token (dict): 时间表达式token
            base_time (datetime): 基准时间

        Returns:
            list: 时间范围列表
        """
        try:
            # 获取当前basetime的农历日期
            tmp = datetime.datetime(base_time.year, base_time.month, base_time.day)
            lunar_tmp = zhdate.ZhDate.from_datetime(tmp)

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

            # 获取年份偏移量或指定年份
            year_offset = int(token.get("lunar_year_prefix", 0))
            lunar_year_str = token.get("lunar_year", "").strip('"')
            if lunar_year_str:
                year_tmp = int(lunar_year_str)
            else:
                year_tmp = lunar_tmp.lunar_year + year_offset

            if lunar_day_tmp:  # 有具体日，返回为一天 - 使用基类的天范围函数
                lunar_date = zhdate.ZhDate(year_tmp, lunar_mon, lunar_day)
                solar_date = lunar_date.to_datetime()
                start_of_day, end_of_day = self._get_day_range(solar_date)
                return self._format_time_result(start_of_day, end_of_day)
            else:  # 无具体日，返回一月 - 使用基类的月范围函数
                lunar_date = zhdate.ZhDate(year_tmp, lunar_mon, 1)
                solar_date = lunar_date.to_datetime()
                start_of_month, end_of_month = self._get_month_range(solar_date)
                return self._format_time_result(start_of_month, end_of_month)

        except ValueError:
            # 处理农历日期不存在的情况（如小月没有30天）
            return []

    def _handle_year_range(self, token, base_time):
        """
        处理年份范围：2024-2025年

        Args:
            token (dict): 时间表达式token
            base_time (datetime): 基准时间

        Returns:
            list: 时间范围列表
        """
        year1 = self._normalize_year(int(token["year"]))
        year2 = self._normalize_year(int(token["year2"]))
        start = base_time.replace(year=year1, month=1, day=1, hour=0, minute=0, second=0)
        end = base_time.replace(year=year2, month=12, day=31, hour=23, minute=59, second=59)
        return self._format_time_result(start, end)

    def _handle_month_range(self, token, base_time):
        """
        处理月份范围：1-3月

        Args:
            token (dict): 时间表达式token
            base_time (datetime): 基准时间

        Returns:
            list: 时间范围列表
        """
        month1 = int(token["month"])
        month2 = int(token["month2"])
        year = base_time.year
        if "year" in token:
            year = self._normalize_year(int(token["year"]))
        start = base_time.replace(year=year, month=month1, day=1, hour=0, minute=0, second=0)
        # 计算month2的最后一天
        import calendar

        last_day = calendar.monthrange(year, month2)[1]
        end = base_time.replace(
            year=year, month=month2, day=last_day, hour=23, minute=59, second=59
        )
        return self._format_time_result(start, end)

    def _handle_day_range(self, token, base_time):
        """
        处理日期范围：1-3日

        Args:
            token (dict): 时间表达式token
            base_time (datetime): 基准时间

        Returns:
            list: 时间范围列表
        """
        day1 = int(token["day"])
        day2 = int(token["day2"])
        year = base_time.year
        month = base_time.month
        if "year" in token:
            year = self._normalize_year(int(token["year"]))
        if "month" in token:
            month = int(token["month"])
        start = base_time.replace(year=year, month=month, day=day1, hour=0, minute=0, second=0)
        end = base_time.replace(year=year, month=month, day=day2, hour=23, minute=59, second=59)
        return self._format_time_result(start, end)

    def _handle_hour_range(self, token, base_time):
        """
        处理小时范围：9-11点

        Args:
            token (dict): 时间表达式token
            base_time (datetime): 基准时间

        Returns:
            list: 时间范围列表
        """
        hour1 = int(token["hour"])
        hour2 = int(token["hour2"])
        noon = token.get("noon", "")
        # 处理noon调整（下午/晚上）
        if noon in ["下午", "晚上", "晚"] and hour1 < 12:
            hour1 += 12
        if noon in ["下午", "晚上", "晚"] and hour2 < 12:
            hour2 += 12
        start = base_time.replace(hour=hour1, minute=0, second=0, microsecond=0)
        end = base_time.replace(hour=hour2, minute=0, second=0, microsecond=0)
        return self._format_time_result(start, end)

    def _handle_month_day_to_month_day_range(self, token, base_time):
        """处理 (offset_year?) + month.day 到 (offset_year2?) + month.day 的整体区间"""
        try:
            # 左边年份
            year1 = base_time.year
            if token.get("offset_year") is not None and token.get("offset_year") != "":
                try:
                    year1 += int(token.get("offset_year"))
                except Exception:
                    pass

            # 右边年份（新增支持offset_year2）
            year2 = base_time.year
            if token.get("offset_year2") is not None and token.get("offset_year2") != "":
                try:
                    year2 += int(token.get("offset_year2"))
                except Exception:
                    pass
            elif token.get("offset_year") is not None:
                # 如果没有offset_year2，右边默认继承左边的年份
                year2 = year1

            m1 = int(token.get("month"))
            d1 = int(token.get("day"))
            m2 = int(token.get("month2"))
            d2 = int(token.get("day2"))
            start = base_time.replace(year=year1, month=m1, day=d1, hour=0, minute=0, second=0)
            end = base_time.replace(year=year2, month=m2, day=d2, hour=23, minute=59, second=59)
            return self._format_time_result(start, end)
        except Exception:
            return []
