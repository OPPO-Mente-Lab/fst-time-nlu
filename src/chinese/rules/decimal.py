# Copyright (c)  2025  OPPO Corporation.   (authors: Ming Yu, Liangliang Han)
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

from ..word_level_pynini import union, cross, pynutil, string_file

from ...core.processor import Processor
from ...core.utils import get_abs_path
from .base.number_base import NumberBaseRule

insert = pynutil.insert


class DecimalRule(Processor):
    def __init__(self):
        super().__init__(name="decimal")
        self.build_tagger()

    def build_tagger(self):
        sign = union("+", "-").ques
        digit = string_file(get_abs_path("../data/number/arabic_digit.tsv"))
        dot = "."
        # 中文点：统一到 '.'
        dot_cn = cross("点", ".") | cross("點", ".") | dot
        # 中文数字小数：中文整数 + '点/點/.' + 中文小数
        # 整数部分：允许复杂中文数字（如 二十一）
        # 小数部分：放宽为可重复的中文“单数字”（九九九 → 999）
        cn_num_rule = NumberBaseRule()
        cn_number = cn_num_rule.build_cn_number()
        cn_digit_single = (
            cross("零", "0")
            | cross("〇", "0")
            | cross("○", "0")
            | cross("一", "1")
            | cross("二", "2")
            | cross("两", "2")
            | cross("三", "3")
            | cross("四", "4")
            | cross("五", "5")
            | cross("六", "6")
            | cross("七", "7")
            | cross("八", "8")
            | cross("九", "9")
        )
        # 阿拉伯数字小数：至少一位整数 + '.' + 至少一位小数
        decimal_arabic = sign + digit.plus + dot + digit.plus
        # 纯中文小数
        decimal_chinese = sign + cn_number + dot_cn + cn_digit_single.plus
        # 混合小数：中文整数 + 点 + 阿拉伯小数；阿拉伯整数 + 点 + 中文小数
        decimal_mixed_cn_int = sign + cn_number + dot_cn + digit.plus
        decimal_mixed_ar_int = sign + digit.plus + dot_cn + cn_digit_single.plus

        # 不在小数规则里匹配 纯阿拉伯形式（digit '.' digit），交由其他规则（如unit等）处理
        # 恢复纯阿拉伯小数；仍不识别 阿拉伯整数 + 中文点 + 阿拉伯小数（如 24点5）
        decimal = decimal_arabic | decimal_chinese | decimal_mixed_cn_int | decimal_mixed_ar_int
        tagger = insert('value: "') + decimal + insert('"')
        self.tagger = self.add_tokens(tagger)
