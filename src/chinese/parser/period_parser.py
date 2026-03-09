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
import zhdate
from datetime import timedelta
from dateutil.relativedelta import relativedelta

from .base_parser import BaseParser

# 移除中文数字转换器导入，改为使用FST映射


class PeriodParser(BaseParser):
    """
    时间段解析器

    处理时间段相关的时间表达式，包括：
    - 时间单位（年、月、日、小时、分钟、秒、周、年代、世纪）
    - 月份时间段（月初、月中、月末）
    - 年份时间段（年初、年末）
    - 近期、最近等相对时间段
    """

    def __init__(self):
        """初始化时间段解析器"""
        super().__init__()

    def parse(self, token, base_time):  # noqa: C901
        """
        解析时间段表达式

        Args:
            token (dict): 时间表达式token
            base_time (datetime): 基准时间

        Returns:
            list: 时间范围列表，格式为 [[start_time_str, end_time_str]]
        """
        direction = self._determine_direction(token)  # 默认为1

        # offset/period_word/decade_num/century_num/quarter 使用FST映射的阿拉伯数字
        def to_int_safe(raw):
            return int(raw) if raw is not None else 0

        offset = to_int_safe(token.get("offset", 0))
        unit = token.get("unit")
        month_period = token.get("month_period")
        year_period = token.get("year_period")
        period_word = to_int_safe(token.get("period_word", 0))
        decade_num = to_int_safe(token.get("decade_num", 0))
        century_num = to_int_safe(token.get("century_num", 0))
        year_offset = token.get("offset_direction", "")

        # 处理近期、最近这类无数字的情况
        if period_word != 0:
            return self._handle_period_word(base_time, period_word)

        # 处理时间单位
        if unit:
            # 获取fractional信息
            fractional = token.get("fractional")
            return self._handle_time_unit(
                base_time,
                unit,
                offset,
                direction,
                decade_num,
                century_num,
                year_offset,
                month_period,
                fractional,
                token.get("source", ""),
            )

        # 处理月份时间段
        if month_period:
            return self._handle_month_period(token, base_time)

        # 处理年份时间段
        if year_period:
            # 检查是否是半年相关的year_period
            if year_period in ["firsthalf", "secondhalf"]:
                # 转换为half_year处理
                token["half_year"] = year_period
                return self._handle_half_year(token, base_time)
            elif year_period == "beginning":
                # 检查是否有年份信息
                if token.get("year") or token.get("offset_year"):
                    # 有年份信息，转换为yishi处理
                    token["yishi"] = "beginning"
                    return self._handle_yishi(token, base_time)
                else:
                    # 单独的"伊始"不识别，返回空
                    return []
            else:
                return self._handle_year_period(token, base_time)

        # 处理季度序号（第X季度）
        if token.get("quarter"):
            token["quarter"] = to_int_safe(token.get("quarter"))
            return self._handle_quarter_ordinal(token, base_time)

        # 处理季节
        if token.get("season"):
            return self._handle_season(token, base_time)

        # 处理半年
        if token.get("half_year"):
            return self._handle_half_year(token, base_time)

        # 处理伊始
        if token.get("yishi"):
            return self._handle_yishi(token, base_time)

        return []

    def _handle_period_word(self, base_time, period_word):
        """
        处理近期、最近等时间段词汇

        Args:
            base_time (datetime): 基准时间
            period_word (int): 时间段词汇对应的天数

        Returns:
            list: 时间范围列表
        """
        if period_word < 0:
            # 过去时间段：从过去某天的00:00:00到当前时刻
            # 采用“含今天的N个自然日”口径：例如 period_word=-7 表示最近7天
            # base_time=12/17 10:00 → start=12/11 00:00, end=12/17 10:00
            # 等价于 base_time + (period_word + 1) 天后对齐到日初
            start_time = base_time + timedelta(days=period_word + 1)
            start_of_day, _ = self._get_day_range(start_time)
            return self._format_time_result(start_of_day, base_time)
        else:
            # 未来时间段：从现在到未来某个时间点的范围
            # 例如：之后(7) -> 从现在到7天后
            base_start, base_end = self._get_day_range(base_time)
            end_time = base_time + timedelta(days=period_word)
            start_of_day, end_of_day = self._get_day_range(end_time)
            return self._format_time_result(base_start, end_of_day)

    def _handle_time_unit(
        self,
        base_time,
        unit,
        offset,
        direction,
        decade_num,
        century_num,
        year_offset,
        month_period=None,
        fractional=None,
        source="",
    ):
        """
        处理时间单位（年、月、日、小时、分钟、秒、周、年代、世纪）

        Args:
            base_time (datetime): 基准时间
            unit (str): 时间单位
            offset (int): 偏移量
            direction (int): 方向

        Returns:
            list: 时间范围列表
        """
        # “这一年/这一周/这一个月”类：在现网tag中常被识别为 time_period（这 + 1 + 年/周/月）
        # 但需求语义是当前自然周期（本年/本周/本月）。
        if source == "这" and direction == -1 and offset == 1 and unit in {"year", "month", "week"}:
            if unit == "year":
                start_of_year, end_of_year = self._get_year_range(base_time)
                return self._format_time_result(start_of_year, end_of_year)
            if unit == "month":
                start_of_month, end_of_month = self._get_month_range(base_time)
                return self._format_time_result(start_of_month, end_of_month)
            if unit == "week":
                start_of_week, end_of_week = self._get_week_range(base_time)
                return self._format_time_result(start_of_week, end_of_week)

        if unit == "year":
            return self._handle_year_unit(base_time, offset, direction, fractional)
        elif unit == "month":
            return self._handle_month_unit(base_time, offset, direction, fractional)
        elif unit == "day":
            return self._handle_day_unit(base_time, offset, direction, fractional)
        elif unit == "hour":
            return self._handle_hour_unit(base_time, offset, direction)
        elif unit == "minute":
            return self._handle_minute_unit(base_time, offset, direction)
        elif unit == "second":
            return self._handle_second_unit(base_time, offset, direction)
        elif unit == "week":
            return self._handle_week_unit(base_time, offset, direction, fractional)
        elif unit == "decade":
            return self._handle_decade_unit(base_time, decade_num, century_num, year_offset)
        elif unit == "century":
            return self._handle_century_unit(base_time, century_num, year_offset, month_period)

        return []

    def _handle_year_unit(self, base_time, offset, direction, fractional=None):
        """处理年单位"""
        # 处理分数年份（如：两年半 = 2.5年 -> 2年6个月）
        if fractional:
            fractional_val = float(fractional)
            months_total = offset * 12 + int(round(fractional_val * 12))
            start_time = base_time + relativedelta(months=months_total * direction)
        else:
            start_time = base_time + relativedelta(years=offset * direction)

        if direction < 0:
            return self._format_time_result(start_time, base_time)
        else:
            return self._format_time_result(base_time, start_time)

    def _handle_month_unit(self, base_time, offset, direction, fractional=None):
        """处理月单位"""
        # 处理分数月份（如：两月半 = 2.5个月 -> 2个月15天）
        if fractional:
            fractional_val = float(fractional)
            months_part = offset
            days_part = int(round(fractional_val * 30))
            start_time = (
                base_time
                + relativedelta(months=months_part * direction)
                + timedelta(days=days_part * direction)
            )
        else:
            start_time = base_time + relativedelta(months=offset * direction)

        if direction < 0:
            return self._format_time_result(start_time, base_time)
        else:
            return self._format_time_result(base_time, start_time)

    def _handle_day_unit(self, base_time, offset, direction, fractional=None):
        """处理日单位"""
        # 处理分数天数（如：两天半 = 2.5天 -> 2天12小时）
        if fractional:
            fractional_val = float(fractional)
            days_part = offset
            hours_part = int(round(fractional_val * 24))
            start_time = base_time + timedelta(
                days=days_part * direction, hours=hours_part * direction
            )
        else:
            start_time = base_time + timedelta(days=offset * direction)

        if direction < 0:
            return self._format_time_result(start_time, base_time)
        else:
            return self._format_time_result(base_time, start_time)

    def _handle_hour_unit(self, base_time, offset, direction):
        """处理小时单位"""
        start_time = base_time + timedelta(hours=offset * direction)
        if direction < 0:
            return self._format_time_result(start_time, base_time)
        else:
            return self._format_time_result(base_time, start_time)

    def _handle_minute_unit(self, base_time, offset, direction):
        """处理分钟单位"""
        start_time = base_time + timedelta(minutes=offset * direction)
        if direction < 0:
            return self._format_time_result(start_time, base_time)
        else:
            return self._format_time_result(base_time, start_time)

    def _handle_second_unit(self, base_time, offset, direction):
        """处理秒单位"""
        start_time = base_time + timedelta(seconds=offset * direction)
        if direction < 0:
            return self._format_time_result(start_time, base_time)
        else:
            return self._format_time_result(base_time, start_time)

    def _handle_week_unit(self, base_time, offset, direction, fractional=None):
        """处理周单位"""
        # 处理分数周数（如：两周半 = 2.5周 -> 2周3天12小时）
        if fractional:
            fractional_val = float(fractional)
            weeks_part = offset
            days_part = int(fractional_val * 7)
            hours_part = int(round((fractional_val * 7 - days_part) * 24))
            start_time = base_time + timedelta(
                weeks=weeks_part * direction,
                days=days_part * direction,
                hours=hours_part * direction,
            )
        else:
            start_time = base_time + timedelta(days=offset * 7 * direction)

        if direction < 0:
            return self._format_time_result(start_time, base_time)
        else:
            return self._format_time_result(base_time, start_time)

    def _handle_decade_unit(self, base_time, decade_num, century_num, year_offset):
        """处理年代单位"""
        if decade_num <= 20:  # 00-20(00年代：2000-2009)
            if century_num == 0:  # 上个世纪20年代
                if year_offset != "":
                    tmp_year = 2000 + int(year_offset) * 100 + decade_num
                else:
                    tmp_year = 2000 + decade_num  # 20年代（2020-2030）
            else:
                tmp_year = (century_num - 1) * 100 + decade_num  # 19世纪20年代
        else:  # 30-90(60年代：1969-1999)
            if century_num == 0:
                if year_offset != "":
                    tmp_year = 2000 + int(year_offset) * 100 + decade_num
                else:
                    tmp_year = 1900 + decade_num  # 六十年代
            else:
                tmp_year = (century_num - 1) * 100 + decade_num  # 19世纪50年代

        # 使用基类的年范围函数
        start_of_decade, end_of_decade = self._get_year_range(base_time, tmp_year)
        end_of_decade = end_of_decade.replace(year=tmp_year + 9)
        return self._format_time_result(start_of_decade, end_of_decade)

    def _handle_century_unit(self, base_time, century_num, year_offset, month_period=None):
        """处理世纪单位"""
        if century_num != 0:  # 二十世纪
            tmp_year = (century_num - 1) * 100
        else:  # 本世纪、上个世纪
            tmp_year = 2000 + int(year_offset) * 100

        # 检查是否有时间段修饰符
        if month_period == "earlymonth":
            # 世纪初：前10年
            start_year = tmp_year
            end_year = tmp_year + 9
        elif month_period == "midmonth":
            # 世纪中：中间10年
            start_year = tmp_year + 45
            end_year = tmp_year + 54
        elif month_period == "latemonth":
            # 世纪末：后10年
            start_year = tmp_year + 90
            end_year = tmp_year + 99
        else:
            # 整个世纪
            start_year = tmp_year
            end_year = tmp_year + 99

        # 使用基类的年范围函数
        start_of_period, end_of_period = self._get_year_range(base_time, start_year)
        end_of_period = end_of_period.replace(year=end_year)
        return self._format_time_result(start_of_period, end_of_period)

    def _handle_month_period(self, token, base_time):  # noqa: C901
        """
        处理月份时间段（月初、月中、月末）
        """
        month_period = token.get("month_period")
        year = token.get("year")
        month = token.get("month")
        offset_year = token.get("offset_year", 0)
        offset_month = token.get("offset_month", 0)

        # 应用时间偏移
        if token.get("offset_year"):
            base_time = base_time + relativedelta(years=int(offset_year))
        if token.get("offset_month"):
            base_time = base_time + relativedelta(months=int(offset_month))
        if token.get("year"):
            # year 统一走基类规范化（已有范围检查）
            y_val = int(year)
            y_val = self._normalize_year(y_val)
            base_time = base_time.replace(year=y_val)
        if token.get("month"):
            m_val = int(month)
            if m_val is not None:
                base_time = base_time.replace(month=m_val)
        if token.get("lunar_month"):
            lm_val = int(token.get("lunar_month"))
            if lm_val is not None:
                base_time = base_time.replace(month=lm_val)

        # 根据月份时间段类型处理
        if month_period == "earlymonth":
            start_time = base_time.replace(day=1, hour=0, minute=0, second=0)
            end_time = base_time.replace(day=10, hour=23, minute=59, second=59)
        elif month_period == "midmonth":
            start_time = base_time.replace(day=11, hour=0, minute=0, second=0)
            end_time = base_time.replace(day=20, hour=23, minute=59, second=59)
        elif month_period == "latemonth":
            start_time = base_time.replace(day=21, hour=0, minute=0, second=0)
            # 使用基类的月范围函数获取月末
            _, end_of_month = self._get_month_range(base_time)
            end_time = end_of_month
        elif month_period == "earlymidmonth":
            # 中上旬：上旬+中旬 = 1-20日
            start_time = base_time.replace(day=1, hour=0, minute=0, second=0)
            end_time = base_time.replace(day=20, hour=23, minute=59, second=59)
        elif month_period == "midlatemonth":
            # 中下旬：中旬+下旬 = 11日-月末
            start_time = base_time.replace(day=11, hour=0, minute=0, second=0)
            _, end_of_month = self._get_month_range(base_time)
            end_time = end_of_month
        else:
            return []

        # 处理农历月份
        if token.get("lunar_month"):
            # 先转换农历日期，再设置正确的时间
            start_lunar = zhdate.ZhDate(start_time.year, start_time.month, start_time.day)
            end_lunar = zhdate.ZhDate(end_time.year, end_time.month, end_time.day)

            start_solar = start_lunar.to_datetime().replace(hour=0, minute=0, second=0)
            end_solar = end_lunar.to_datetime().replace(hour=23, minute=59, second=59)

            return self._format_time_result(start_solar, end_solar)
        else:
            return self._format_time_result(start_time, end_time)

    def _handle_year_period(self, token, base_time):
        """
        处理年份时间段（年初、年末）

        Args:
            token (dict): 时间表达式token
            base_time (datetime): 基准时间

        Returns:
            list: 时间范围列表
        """
        year_period = token.get("year_period")
        year = token.get("year")
        offset_year = token.get("offset_year", 0)

        # 应用时间偏移
        if token.get("offset_year"):
            base_time = base_time + relativedelta(years=int(offset_year))
        if token.get("year"):
            year_val = int(year)
            year_val = self._normalize_year(year_val)
            base_time = base_time.replace(year=year_val)

        # 根据年份时间段类型处理
        if year_period == "earlyyear":
            # 年初：1月1日到2月底
            start_time = base_time.replace(month=1, day=1, hour=0, minute=0, second=0)
            # 计算2月的最后一天
            last_day_of_feb = calendar.monthrange(base_time.year, 2)[1]
            end_time = base_time.replace(
                month=2, day=last_day_of_feb, hour=23, minute=59, second=59
            )
        elif year_period == "lateyear":
            # 年末：11月1日到12月31日
            start_time = base_time.replace(month=11, day=1, hour=0, minute=0, second=0)
            end_time = base_time.replace(month=12, day=31, hour=23, minute=59, second=59)
        else:
            return []

        return self._format_time_result(start_time, end_time)

    def _handle_quarter_ordinal(self, token, base_time):
        """
        处理“第X季度”
        """
        quarter = int(token.get("quarter"))
        year = token.get("year")
        offset_year = token.get("offset_year", 0)

        # 应用年份（相对或绝对）
        if token.get("offset_year"):
            base_time = base_time + relativedelta(years=int(offset_year))
        if token.get("year"):
            year_val = int(year)
            year_val = self._normalize_year(year_val)
            base_time = base_time.replace(year=year_val)

        # 计算季度的起止月份
        start_month = (quarter - 1) * 3 + 1
        end_month = start_month + 2

        start_time = base_time.replace(month=start_month, day=1, hour=0, minute=0, second=0)
        # 使用基类的月范围函数获取季度末
        _, end_of_month = self._get_month_range(base_time.replace(month=end_month))
        end_time = end_of_month

        return self._format_time_result(start_time, end_time)

    def _calculate_equinox_solstice(self, year):
        """
        计算指定年份的春分、夏至、秋分、冬至日期

        使用简化的天文算法公式
        参考：2000-2099年的近似公式

        Args:
            year: 年份

        Returns:
            dict: {
                'spring_equinox': (month, day),
                'summer_solstice': (month, day),
                'autumn_equinox': (month, day),
                'winter_solstice': (month, day)
            }
        """
        if 2000 <= year <= 2099:
            # 使用简化公式计算（精度约±1天）
            y = year - 2000
            spring_day = 20 + y * 0.24219 - int(y / 4)
            summer_day = 21 + y * 0.24219 - int(y / 4)
            autumn_day = 23 + y * 0.24219 - int(y / 4)
            winter_day = 22 + y * 0.24219 - int(y / 4)
        else:
            # 其他年份使用固定近似值
            spring_day, summer_day = 20, 21
            autumn_day, winter_day = 23, 22

        return {
            "spring_equinox": (3, int(spring_day)),
            "summer_solstice": (6, int(summer_day)),
            "autumn_equinox": (9, int(autumn_day)),
            "winter_solstice": (12, int(winter_day)),
        }

    def _get_season_range(self, year, season):
        """
        根据年份和季节计算精确范围

        Args:
            year: 年份
            season: 季节 ('spring', 'summer', 'autumn', 'winter')

        Returns:
            (start_date, end_date) 元组
        """
        from datetime import datetime

        dates = self._calculate_equinox_solstice(year)

        if season == "spring":
            # 春分到夏至前一天
            start_m, start_d = dates["spring_equinox"]
            end_m, end_d = dates["summer_solstice"]
            end_d -= 1
            start = datetime(year, start_m, start_d, 0, 0, 0)
            end = datetime(year, end_m, end_d, 23, 59, 59)

        elif season == "summer":
            # 夏至到秋分前一天
            start_m, start_d = dates["summer_solstice"]
            end_m, end_d = dates["autumn_equinox"]
            end_d -= 1
            start = datetime(year, start_m, start_d, 0, 0, 0)
            end = datetime(year, end_m, end_d, 23, 59, 59)

        elif season == "autumn":
            # 秋分到冬至前一天
            start_m, start_d = dates["autumn_equinox"]
            end_m, end_d = dates["winter_solstice"]
            end_d -= 1
            start = datetime(year, start_m, start_d, 0, 0, 0)
            end = datetime(year, end_m, end_d, 23, 59, 59)

        elif season == "winter":
            # 冬至到次年春分前一天（跨年）
            start_m, start_d = dates["winter_solstice"]
            next_dates = self._calculate_equinox_solstice(year + 1)
            end_m, end_d = next_dates["spring_equinox"]
            end_d -= 1
            start = datetime(year, start_m, start_d, 0, 0, 0)
            end = datetime(year + 1, end_m, end_d, 23, 59, 59)

        return start, end

    def _handle_season(self, token, base_time):
        """
        处理季节表达式

        Args:
            token: 包含season字段的token
            base_time: 基准时间

        Returns:
            list: 时间范围列表
        """
        season = token.get("season")
        year = token.get("year")
        offset_year = token.get("offset_year", 0)

        # 中文单字季节转换为英文
        season_map = {"春": "spring", "夏": "summer", "秋": "autumn", "冬": "winter"}
        if season in season_map:
            season = season_map[season]

        # 应用年份（相对或绝对）
        if token.get("offset_year"):
            base_time = base_time + relativedelta(years=int(offset_year))
        if token.get("year"):
            year_val = int(year)
            year_val = self._normalize_year(year_val)
            base_time = base_time.replace(year=year_val)

        # 计算季节范围
        start_time, end_time = self._get_season_range(base_time.year, season)

        return self._format_time_result(start_time, end_time)

    def _handle_half_year(self, token, base_time):
        """
        处理半年表达式

        Args:
            token: 包含half_year字段的token
            base_time: 基准时间

        Returns:
            list: 时间范围列表
        """
        half_year = token.get("half_year")
        year = token.get("year")
        offset_year = token.get("offset_year", 0)

        # 应用年份（相对或绝对）
        if token.get("offset_year"):
            base_time = base_time + relativedelta(years=int(offset_year))
        if token.get("year"):
            year_val = int(year)
            year_val = self._normalize_year(year_val)
            base_time = base_time.replace(year=year_val)

        # 计算半年范围
        if half_year in ["firsthalf", "上半年"]:
            # 上半年：1月1日到6月30日
            start_time = base_time.replace(month=1, day=1, hour=0, minute=0, second=0)
            end_time = base_time.replace(month=6, day=30, hour=23, minute=59, second=59)
        elif half_year in ["secondhalf", "下半年"]:
            # 下半年：7月1日到12月31日
            start_time = base_time.replace(month=7, day=1, hour=0, minute=0, second=0)
            end_time = base_time.replace(month=12, day=31, hour=23, minute=59, second=59)
        else:
            return []

        return self._format_time_result(start_time, end_time)

    def _handle_yishi(self, token, base_time):
        """
        处理伊始表达式（年份的第一个月）

        Args:
            token: 包含yishi字段的token
            base_time: 基准时间

        Returns:
            list: 时间范围列表
        """
        year = token.get("year")
        offset_year = token.get("offset_year", 0)

        # 应用年份（相对或绝对）
        if token.get("offset_year"):
            base_time = base_time + relativedelta(years=int(offset_year))
        if token.get("year"):
            year_val = int(year)
            year_val = self._normalize_year(year_val)
            base_time = base_time.replace(year=year_val)

        # 伊始：该年的第一个月（1月1日到1月31日）
        start_time = base_time.replace(month=1, day=1, hour=0, minute=0, second=0)
        end_time = base_time.replace(month=1, day=31, hour=23, minute=59, second=59)

        return self._format_time_result(start_time, end_time)
