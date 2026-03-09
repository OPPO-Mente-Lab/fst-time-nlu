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
from .time_base import TimeBaseRule

insert = pynutil.insert


class PeriodBaseRule:
    """时间段基础规则类"""

    def __init__(self):
        self.period_pre = (
            insert('offset_direction: "')
            + string_file(get_abs_path("../../data/period/period_prefix.tsv"))
            + insert('"')
        )
        self.period_suf = (
            insert('month_period: "')
            + string_file(get_abs_path("../../data/period/period_month.tsv"))
            + insert('"')
        )
        self.period_num = (
            insert('century_num: "')
            + string_file(get_abs_path("../../data/period/period_num.tsv"))
            + insert('"')
        )
        self.period_type = (
            insert('unit: "')
            + string_file(get_abs_path("../../data/period/period_special.tsv"))
            + insert('"')
        )
        # 增加年代前缀
        self.period_decade_num = (
            insert('decade_num: "')
            + string_file(get_abs_path("../../data/period/period_decade.tsv"))
            + insert('"')
        )

    def build_decade_rules(self):
        """构建年代规则，如80年代"""
        period_decade = (
            self.period_decade_num + self.period_type + self.period_suf.ques
        )  # 90年代（初）
        return period_decade

    def build_century_rules(self):
        """构建世纪规则，如二十世纪"""
        period_century = (
            (self.period_num | self.period_pre) + self.period_type + self.period_suf.ques
        )  # 本/二十世纪（初）
        return period_century
