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
from .date_base import DateBaseRule
from .time_base import TimeBaseRule

delete = pynutil.delete
insert = pynutil.insert


class RelativeBaseRule:
    """相对时间基础规则类，处理如昨天、今天、明天等相对时间表达式"""

    def __init__(self):
        self.time = TimeBaseRule().build_time_rules()
        self.date = DateBaseRule().build_date_rules()
        self.month_date = DateBaseRule().build_month_date_rules()
        self.month = DateBaseRule().build_month_rules()

        # 加载TSV文件
        digit = string_file(get_abs_path("../../data/number/digit.tsv"))
        zero = string_file(get_abs_path("../../data/number/zero.tsv"))
        self.month_digit = string_file(get_abs_path("../../data/date/digit/month_digit.tsv"))
        self.month_cn = string_file(get_abs_path("../../data/date/cn/month_cn.tsv"))
        self.year_prefix = string_file(get_abs_path("../../data/date/year_prefix.tsv"))
        self.month_prefix = string_file(get_abs_path("../../data/date/month_prefix.tsv"))
        self.day_prefix = string_file(get_abs_path("../../data/date/day_prefix.tsv"))

        # 通用设置
        self.day_suffix = delete("日") | delete("号")
        # 定义数字匹配规则，用于匹配天数
        self.day_number = digit | (digit + (digit | zero))

    def build_std_rules(self):
        """构建标准相对时间规则"""
        # 1. 特定年份偏移 (去年/明年等)
        specific_year_dates = insert('offset_year: "') + self.year_prefix + insert('"')

        # 2. 相对月份表达式 (上个月/下个月等)
        month_offset_prefix = insert('offset_month: "') + self.month_prefix + insert('"')
        offset_month_date = (
            month_offset_prefix
            + delete("月")
            + (insert('day: "') + self.day_number + insert('" ') + self.day_suffix).ques
        )

        # 3. 特定时间偏移 (昨天/今天/明天等)
        specific_day_dates = insert('offset_day: "') + self.day_prefix + insert('"')

        # 4. 相对时间——季度（上个、下个）
        quarter_offset_prefix = insert('offset_quarter: "') + self.month_prefix + insert('"')
        offset_quarter_date = quarter_offset_prefix + delete("季度")

        # 可选连接词“的”
        de_opt = delete("的").ques

        # 年偏移专用：点号月日（只在relative链路中使用）
        md_month = (
            insert('month: "')
            + string_file(get_abs_path("../../data/date/digit/month_digit.tsv"))
            + insert('"')
        )
        md_day = (
            insert('day: "')
            + string_file(get_abs_path("../../data/date/digit/day_digit.tsv"))
            + insert('"')
        )
        month_day_digit_dot = md_month + delete(".") + md_day + self.day_suffix.ques

        # 相对链专用：点号时分（不带“分”字），仅用于“天偏移 + 时间”场景
        hm_hour = (
            insert('hour: "')
            + string_file(get_abs_path("../../data/time/digit/hour_digit.tsv"))
            + insert('"')
        )
        hm_minute = (
            insert('minute: "')
            + string_file(get_abs_path("../../data/time/digit/minute_digit.tsv"))
            + insert('"')
        )
        hm_dot_nf = hm_hour + delete(".") + hm_minute

        # 5. 相对周表达式
        # 5.1 通用周偏移前缀（上周/下周/这周/本周等）
        week_offset_prefix = (
            insert('offset_week: "')
            + string_file(get_abs_path("../../data/week/week_prefix.tsv"))
            + delete("周")
            + insert('"')
        )

        # 5.2 特殊处理：次周（单独定义，不与week_prefix.tsv冲突）
        ci_week = insert('offset_week: "1"') + delete("次周")

        # 合并所有相对时间规则
        relative_date = (
            specific_day_dates + de_opt + (hm_dot_nf | self.time)  # 明天的 + 8.30 或 时间
            | specific_day_dates  # 明天
            | offset_month_date + self.date + self.time
            | offset_month_date + self.date
            | offset_month_date  # 下个月
            | ci_week  # 次周（优先级高）
            | week_offset_prefix  # 其他周偏移（优先级低）
            | offset_quarter_date  # 上个、下个季度
            | specific_year_dates + month_day_digit_dot  # 明年8.30 → 年月日
            | specific_year_dates + self.date + self.time  # 明年,月，日 + 时间
            | specific_year_dates + self.month_date  # 明年,月，日
            | specific_year_dates + self.month  # 明年,月
            | specific_year_dates  # 明年
        )
        return relative_date

    def build_month_rules(self):
        """构建相对月份规则"""
        # 定义月份数字匹配规则
        month_number = (
            insert('month: "') + (self.month_digit | self.month_cn) + delete("月") + insert('"')
        )

        # 1. 相对月份表达式 (上个月/下个月等)
        offset_month = insert('offset_month: "') + self.month_prefix + delete("月") + insert('"')

        # 2. 特定年份偏移 (去年/明年等)
        offset_year = insert('offset_year: "') + self.year_prefix + insert('"')
        offset_year_month = offset_year + month_number

        # 合并相对月份规则
        relative_month = offset_month | offset_year_month
        return relative_month
