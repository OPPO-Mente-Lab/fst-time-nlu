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

from ..word_level_pynini import string_file, union, pynutil

from ...core.processor import Processor
from ...core.utils import get_abs_path
from .base import RelativeBaseRule
from .base.number_base import NumberBaseRule

delete = pynutil.delete
insert = pynutil.insert


class RelativeRule(Processor):
    """相对时间规则处理器，处理如昨天、今天、明天等相对时间表达式"""

    def __init__(self):
        super().__init__(name="time_relative")
        self.relative = RelativeBaseRule().build_std_rules()
        self.build_tagger()

    def build_tagger(self):
        # 构建"年份+第N个星期"规则
        number_rule = NumberBaseRule()
        chinese_number = number_rule.build_cn_number()
        arabic_digit = string_file(get_abs_path("../data/number/arabic_digit.tsv"))
        arabic_number = arabic_digit.plus
        number = arabic_number | chinese_number

        # 加载年份前缀数据（今年、明年等）
        year_prefix = string_file(get_abs_path("../data/date/year_prefix.tsv"))

        # 相对年份+第N个星期：今年第37个星期、明年第10周
        year_nth_week = (
            insert('offset_year: "')
            + year_prefix
            + insert('"')
            + delete("第")
            + insert('week_order: "')
            + number
            + insert('"')
            + delete("个").ques
            + (delete("星期") | delete("周") | delete("礼拜"))
        )

        # 相对年份+第N个月：今年第三个月、明年第九个月
        year_nth_month = (
            insert('offset_year: "')
            + year_prefix
            + insert('"')
            + delete("第")
            + insert('month_order: "')
            + number
            + insert('"')
            + delete("个").ques
            + delete("月")
        )

        # 合并所有相对时间规则（year_nth_week和year_nth_month优先级高）
        relative_all = year_nth_week | year_nth_month | self.relative

        tagger = self.add_tokens(relative_all)

        self.tagger = tagger
