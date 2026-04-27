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

from ...core.processor import Processor
from ...core.utils import get_abs_path
from ..word_level_pynini import string_file, union, pynutil
from .base.number_base import NumberBaseRule

insert = pynutil.insert


class VerbDurationRule(Processor):
    """动词触发 + 短数字 + 时间量词（天/周/月/年）识别为时长(time_delta)。"""

    def __init__(self):
        # 使用独立类型，避免被 TimeParser 当作 time_delta 去解析出结果
        super().__init__(name="time_duration")
        self.build_tagger()

    def build_tagger(self):
        triggers = string_file(get_abs_path("../data/period/verb_duration_triggers.tsv"))
        # 使用NumberBaseRule构建中文数字映射
        number_rule = NumberBaseRule()
        chinese_number = number_rule.build_cn_number()

        # 数字：1-2位阿拉伯；或中文数字映射，用于短时长表达
        digit = string_file(get_abs_path("../data/number/arabic_digit.tsv"))
        digit_1_2 = digit | (digit + digit)
        number = digit_1_2 | chinese_number

        unit = string_file(get_abs_path("../data/period/duration_units.tsv"))  # 天/周/月/年

        tagger = (
            insert('trigger: "')
            + triggers
            + insert('"')
            + self.DELETE_ZERO_OR_ONE_SPACE
            + insert('value: "')
            + number
            + insert('"')
            + insert(' unit: "')
            + unit
            + insert('"')
        )

        self.tagger = self.add_tokens(tagger)
