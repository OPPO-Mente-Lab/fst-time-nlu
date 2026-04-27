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

from ..word_level_pynini import union, string_file, cross, pynutil

from ...core.processor import Processor
from ...core.utils import get_abs_path
from .base.number_base import NumberBaseRule


insert = pynutil.insert
delete = pynutil.delete


class UnitRule(Processor):
    """数字/小数 + 单位/量词 识别规则。

    目标：将诸如 2.5元、7.9级、100.0℃、256GB、3.14米 等识别为一个整体 token，
    以便在解析阶段优先于"月日-only"的日期匹配。
    """

    def __init__(self):
        super().__init__(name="unit")
        self.build_tagger()

    def build_tagger(self):
        # 使用NumberBaseRule构建中文数字映射
        number_rule = NumberBaseRule()
        chinese_number = number_rule.build_cn_number()
        digit = string_file(get_abs_path("../data/number/arabic_digit.tsv"))
        dot = "."
        # 小数：支持阿拉伯、中文、混合（中文整数+阿拉伯小数、阿拉伯整数+中文小数）
        dot_cn = cross("点", ".") | cross("點", ".") | dot
        decimal_arabic = union("+", "-").ques + digit.plus + dot + digit.plus
        decimal_arabic_cn_dot = union("+", "-").ques + digit.plus + dot_cn + digit.plus
        decimal_cn = union("+", "-").ques + chinese_number + dot_cn + chinese_number
        decimal_mixed_cn_int = union("+", "-").ques + chinese_number + dot_cn + digit.plus
        decimal_mixed_ar_int = union("+", "-").ques + digit.plus + dot_cn + chinese_number
        integer = union("+", "-").ques + digit.plus
        number = (
            decimal_arabic
            | decimal_arabic_cn_dot
            | decimal_cn
            | decimal_mixed_cn_int
            | decimal_mixed_ar_int
            | integer
            | chinese_number
        )

        # 单位/量词词表
        unit_fst = string_file(get_abs_path("../data/measure/unit.tsv"))

        # 允许数字与单位之间有0或1个空格
        sep = self.DELETE_ZERO_OR_ONE_SPACE

        # 基础规则：数字 + 单位
        basic_rule = (
            insert('value: "')
            + number
            + insert('"')
            + sep
            + insert('unit: "')
            + unit_fst
            + insert('"')
        )

        # 范围规则：数字-数字 + 单位（如：1-12人、9-11座）
        # 支持"-"左右有空格（如：1 - 12人）
        space = delete(" ").star
        range_rule = (
            insert('value: "')
            + digit.plus
            + insert('"')
            + space
            + delete("-")
            + space  # 允许"-"左右有空格
            + insert('value2: "')
            + digit.plus
            + insert('"')
            + sep
            + insert('unit: "')
            + unit_fst
            + insert('"')
        )

        # 特殊规则：数字 + 半 + 单位（如：两个半、两天半）
        number_half_unit = (
            insert('value: "')
            + chinese_number
            + insert('"')
            + delete("半")
            + sep
            + insert('unit: "')
            + unit_fst
            + insert('"')
            + insert('fractional: "0.5"')
        )

        # 特殊规则：数字 + 半（如：两个半，后面可能跟其他词）
        number_half = (
            insert('value: "')
            + chinese_number
            + insert('"')
            + delete("半")
            + insert('fractional: "0.5"')
        )

        tagger = range_rule | basic_rule | number_half_unit | number_half

        self.tagger = self.add_tokens(tagger)
