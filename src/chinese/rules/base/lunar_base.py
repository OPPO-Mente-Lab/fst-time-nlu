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

from ...word_level_pynini import string_file, pynutil

from ....core.utils import get_abs_path

delete = pynutil.delete
insert = pynutil.insert


class LunarBaseRule:
    """农历基础规则类"""

    def __init__(self):
        digit = string_file(get_abs_path("../../data/number/digit.tsv"))
        zero = string_file(get_abs_path("../../data/number/zero.tsv"))

        # 年份格式
        yyyy = (digit + (digit | zero) ** 3) | (
            digit + zero + digit + zero
        )  # 二零零八年 | 二零二零
        yyy = digit + (digit | zero) ** 2  # 公元一六八年
        yy = (digit | zero) ** 2  # 零八年奥运会

        # 构建农历规则
        self.year = (
            insert('lunar_year: "')
            + (yyyy | yyy | yy)
            + delete("年").ques
            + delete("的").ques
            + insert('",')
        )
        self.month = (
            insert('lunar_month: "')
            + string_file(get_abs_path("../../data/lunar/lunar_month.tsv"))
            + insert('",')
        )
        self.month_digit = (
            insert('lunar_month: "')
            + string_file(get_abs_path("../../data/lunar/lunar_month_digit.tsv"))
            + insert('",')
        )
        self.day = (
            insert('lunar_day: "')
            + string_file(get_abs_path("../../data/lunar/lunar_day.tsv"))
            + insert('",')
        )
        self.day_digit = (
            insert('lunar_day: "')
            + string_file(get_abs_path("../../data/lunar/lunar_day_digit.tsv"))
            + insert('",')
        )
        self.month_prefix = (
            insert('lunar_month_prefix: "')
            + string_file(get_abs_path("../../data/date/month_prefix.tsv"))
            + insert('",')
        )
        self.year_prefix = (
            insert('lunar_year_prefix: "')
            + string_file(get_abs_path("../../data/date/year_prefix.tsv"))
            + insert('",')
        )
        self.jieqi = (
            insert('lunar_jieqi: "')
            + string_file(get_abs_path("../../data/lunar/jieqi.tsv"))
            + insert('",')
        )
        self.day_pre = (
            insert('day_pre: "')
            + string_file(get_abs_path("../../data/date/day_prefix.tsv"))
            + insert('",')
        )

    def build_jieqi_rules(self):
        """构建二十四节气规则"""
        # 立秋、小寒 -- 仅有节气名
        jieqi_only = self.jieqi + self.day_pre.ques
        # 2024年冬至、20年小寒、今年立秋 -- 年+节气
        year_jieqi = (self.year | self.year_prefix) + self.jieqi + self.day_pre.ques
        lunar_jieqi = jieqi_only | year_jieqi
        return lunar_jieqi

    def build_monthday_rules(self):
        """构建农历月日规则"""
        # 本月初一
        lunar_monthday_pre = ((self.month_prefix + delete("月")) | self.month) + self.day
        # (2025年|去年)七月初九 （日期只能是初一到初十）
        lunar_monthday_digit = (
            (self.year | self.year_prefix).ques + (self.month_digit | self.month) + self.day
        )
        # 正月初8 这种农历月份+阿拉伯数字日期的组合
        lunar_monthday_arabic = (self.year | self.year_prefix).ques + self.month + self.day_digit
        # 正月初8 这种农历月份+初+阿拉伯数字日期的组合
        lunar_monthday_chu_arabic = (
            (self.year | self.year_prefix).ques + self.month + delete("初") + self.day_digit
        )
        lunar_monthday = (
            lunar_monthday_pre
            | lunar_monthday_digit
            | lunar_monthday_arabic
            | lunar_monthday_chu_arabic
        )
        return lunar_monthday

    def build_date_rules(self):
        """构建农历日期规则"""
        # (2020年|前年)腊月初一|十二 （日期从初一到三十，但是月份只能是农历月表达)
        lunar_date = (self.year.ques | self.year_prefix) + self.month + (self.day | self.day_digit)
        # 农历|阴历 (2020年)1月(15号|初五)
        lunar_date_digit = (
            (delete("农历") | delete("阴历"))
            + delete("的").ques
            + self.year.ques
            + (self.month_digit | self.month)
            + ((self.day_digit + (delete("日") | delete("号")).ques) | self.day).ques
        )
        # (2020年/去年（的）农历|阴历1月(15号|初五 )
        date_lunar_digit = (
            (self.year.ques | self.year_prefix).ques
            + (delete("农历") | delete("阴历"))
            + delete("的").ques
            + (self.month_digit | self.month)
            + ((self.day_digit + (delete("日") | delete("号")).ques) | self.day).ques
        )

        # 合并农历日期规则
        lunar_date_std = lunar_date | lunar_date_digit | date_lunar_digit | self.day
        return lunar_date_std

    def build_month_rules(self):
        """构建农历月份规则"""
        # (2020年|去年)正月
        lunar_month = (self.year | self.year_prefix).ques + self.month
        # 农历|阴历 (2025年)1月/三月
        lunar_month_digit = (
            (delete("农历") | delete("阴历"))
            + delete("的").ques
            + (self.year | self.year_prefix).ques
            + self.month_digit
        )
        # 去年（2025年） 农历|阴历 8月
        month_lunar_digit = (
            (self.year | self.year_prefix).ques
            + (delete("农历") | delete("阴历"))
            + delete("的").ques
            + self.month_digit
        )
        lunar_month_std = lunar_month | lunar_month_digit | month_lunar_digit
        return lunar_month_std
