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

from ..word_level_pynini import string_file, union, pynutil, cross

from ...core.processor import Processor
from ...core.utils import get_abs_path
from .base import PeriodBaseRule, RelativeBaseRule
from .base.number_base import NumberBaseRule

insert = pynutil.insert
delete = pynutil.delete


class RangeRule(Processor):
    """时间范围规则处理器，处理如"两天以来"、"两年间"等时间范围表达式"""

    def __init__(self):
        super().__init__(name="time_range")
        self.build_tagger()

    def build_tagger(self):
        # 使用NumberBaseRule构建中文数字映射
        number_rule = NumberBaseRule()
        chinese_number = number_rule.build_cn_number()

        # 数字：阿拉伯数字 或 中文数字映射
        arabic_digit = string_file(get_abs_path("../data/number/arabic_digit.tsv"))
        arabic_number = arabic_digit.plus
        number = arabic_number | chinese_number

        # 时间单位
        time_units = string_file(get_abs_path("../data/period/period_unit.tsv"))

        # 范围限定词
        range_suffix = string_file(get_abs_path("../data/period/range_suffix.tsv"))

        # 允许数字与单位之间有0或1个空格；允许单位后跟“钟”（分/秒钟）
        sep = delete(self.SPACE).ques
        unit_zh_tail = delete("钟").ques

        # "几"字范围表达式：前缀 + 几 + [个]? + 单位
        # 支持：最近几天、过去几周、这几个月、近几年
        ji_prefix = string_file(get_abs_path("../data/range/ji_phrases.tsv"))
        ji_range = (
            insert('ji_range_type: "')
            + ji_prefix
            + insert('"')
            + delete("几")
            + delete("个").ques
            + sep
            + insert('unit: "')
            + time_units
            + insert('"')
            + unit_zh_tail
        )

        # 模糊数量词映射：十几、二十几等
        fuzzy_number_map = string_file(get_abs_path("../data/range/fuzzy_number.tsv"))

        # 模糊数量词+时间单位（无后缀）
        # 支持：这十几天、那二十几天、最近十几天等
        fuzzy_number_range = (
            (delete("最") + delete("近") + delete("的").ques).ques  # 可选："最近"或"最近的"
            + delete("这").ques
            + delete("那").ques
            + insert('value: "')
            + fuzzy_number_map
            + insert('"')
            + delete("个").ques
            + sep
            + insert('unit: "')
            + time_units
            + insert('"')
            + unit_zh_tail
            + insert('range_type: "ago"')
        )

        # 数字+时间单位+范围限定词
        # 支持：两天以来、三年间、五日内等
        # 使用更严格的匹配，确保完整匹配整个模式
        range_pattern = (
            insert('value: "')
            + number
            + insert('"')
            + sep
            + insert('unit: "')
            + time_units
            + insert('"')
            + unit_zh_tail
            + insert('range_type: "')
            + range_suffix
            + insert('"')
        )

        # 分数时间+范围限定词
        # 支持：一天半以来、7天半以来、两年半以来等
        range_fractional_pattern = (
            insert('value: "')
            + number
            + insert('"')
            + sep
            + insert('unit: "')
            + time_units
            + insert('"')
            + unit_zh_tail
            + delete("半")
            + insert('fractional: "0.5"')
            + insert('range_type: "')
            + range_suffix
            + insert('"')
        )
        # 固定短语：近年来 => 近三年（过去三年到现在）
        recent_years_fixed = (
            delete("近年来")
            + insert('value: "3"')
            + insert('unit: "year"')
            + insert('range_type: "ago"')
        )

        # 前缀型：过去/过去的、近/近的 + 数字 + 单位 (+ 可选"里")
        past_prefix = (delete("过去") | delete("近")) + delete("的").ques
        tail_inside = delete("里").ques
        range_past_prefix = (
            past_prefix
            + insert('value: "')
            + number
            + insert('"')
            + sep
            + insert('unit: "')
            + time_units
            + insert('"')
            + unit_zh_tail
            + tail_inside
            + insert('range_type: "ago"')
        )

        # 前缀型：最近的 + 数字 + 单位（优先级高于"近"单独匹配）
        # 支持：最近的七天、最近的三天、最近的十天等
        recent_prefix = delete("最近") + delete("的").ques
        range_recent_prefix = (
            recent_prefix
            + insert('value: "')
            + number
            + insert('"')
            + sep
            + insert('unit: "')
            + time_units
            + insert('"')
            + unit_zh_tail
            + tail_inside
            + insert('range_type: "ago"')
        )

        # 前缀型：未来/未来的 + 数字 + 单位 (+ 可选"里")
        future_prefix = delete("未来") + delete("的").ques
        range_future_prefix = (
            future_prefix
            + insert('value: "')
            + number
            + insert('"')
            + sep
            + insert('unit: "')
            + time_units
            + insert('"')
            + unit_zh_tail
            + tail_inside
            + insert('range_type: "future"')
        )

        # 前缀型（最近）：带分数：数字 + (个)? + 半 + 单位 (+ 可选"里")
        # 支持：最近的一个半月、最近的三个半月等
        recent_prefix_fractional = (
            recent_prefix
            + insert('value: "')
            + number
            + insert('"')
            + sep
            + delete("个").ques
            + sep
            + delete("半")
            + insert('fractional: "0.5"')
            + sep
            + insert('unit: "')
            + time_units
            + insert('"')
            + unit_zh_tail
            + tail_inside
            + insert('range_type: "ago"')
        )

        # 前缀型（过去/近）：带分数：数字 + (个)? + 半 + 单位 (+ 可选"里")
        past_prefix_fractional = (
            past_prefix
            + insert('value: "')
            + number
            + insert('"')
            + sep
            + delete("个").ques
            + sep
            + delete("半")
            + insert('fractional: "0.5"')
            + sep
            + insert('unit: "')
            + time_units
            + insert('"')
            + unit_zh_tail
            + tail_inside
            + insert('range_type: "ago"')
        )

        # 前缀型（最近）：仅 半 + 单位 (+ 可选"里")
        # 支持：最近的半个月、最近的半年等
        recent_prefix_half_only = (
            recent_prefix
            + insert('value: "0"')
            + insert('fractional: "0.5"')
            + sep
            + insert('unit: "')
            + time_units
            + insert('"')
            + unit_zh_tail
            + tail_inside
            + insert('range_type: "ago"')
        )

        # 前缀型（过去/近）：仅 半 + 单位 (+ 可选"里")
        past_prefix_half_only = (
            past_prefix
            + insert('value: "0"')
            + insert('fractional: "0.5"')
            + sep
            + insert('unit: "')
            + time_units
            + insert('"')
            + unit_zh_tail
            + tail_inside
            + insert('range_type: "ago"')
        )

        # 前缀型（未来）：带分数：数字 + (个)? + 半 + 单位 (+ 可选"里")
        future_prefix_fractional = (
            future_prefix
            + insert('value: "')
            + number
            + insert('"')
            + sep
            + delete("个").ques
            + sep
            + delete("半")
            + insert('fractional: "0.5"')
            + sep
            + insert('unit: "')
            + time_units
            + insert('"')
            + unit_zh_tail
            + tail_inside
            + insert('range_type: "future"')
        )

        # 前缀型（未来）：仅 半 + 单位 (+ 可选"里")
        future_prefix_half_only = (
            future_prefix
            + insert('value: "0"')
            + insert('fractional: "0.5"')
            + sep
            + insert('unit: "')
            + time_units
            + insert('"')
            + unit_zh_tail
            + tail_inside
            + insert('range_type: "future"')
        )

        # 默认过去型：数字 + 单位 + 内 (默认指过去)
        # 支持：两年内、三个月内、五日内等
        default_past_range = (
            insert('value: "')
            + number
            + insert('"')
            + sep
            + insert('unit: "')
            + time_units
            + insert('"')
            + unit_zh_tail
            + delete("内")
            + insert('range_type: "ago"')
        )

        # 半 + 单位 + 内 (默认指过去)
        # 支持：半小时内、半天内、半月内等
        half_past_range = (
            delete("半")
            + insert('value: "0"')
            + insert('fractional: "0.5"')
            + sep
            + insert('unit: "')
            + time_units
            + insert('"')
            + unit_zh_tail
            + delete("内")
            + insert('range_type: "ago"')
        )

        # 数字 + 个 + 半 + 单位 + 内 (默认指过去)
        # 支持：一个半小时内、两个半天内、三个半月内等
        number_ge_half_past_range = (
            insert('value: "')
            + number
            + insert('"')
            + sep
            + delete("个")
            + sep
            + delete("半")
            + insert('fractional: "0.5"')
            + sep
            + insert('unit: "')
            + time_units
            + insert('"')
            + unit_zh_tail
            + delete("内")
            + insert('range_type: "ago"')
        )

        # 数字 + 个 + 半 + 单位 + 以内 (默认指过去)
        # 支持：两个半月以内、三个半天以内等
        number_ge_half_within_range = (
            insert('value: "')
            + number
            + insert('"')
            + sep
            + delete("个")
            + sep
            + delete("半")
            + insert('fractional: "0.5"')
            + sep
            + insert('unit: "')
            + time_units
            + insert('"')
            + unit_zh_tail
            + (delete("以内") | delete("之内"))
            + insert('range_type: "ago"')
        )

        # 数字 + 单位 + 半 + 以内 (默认指过去)
        # 支持：十三分半以内、五分钟半以内等
        number_unit_half_within_range = (
            insert('value: "')
            + number
            + insert('"')
            + sep
            + insert('unit: "')
            + time_units
            + insert('"')
            + sep
            + delete("半")
            + insert('fractional: "0.5"')
            + sep
            + (delete("以内") | delete("之内"))
            + insert('range_type: "ago"')
        )

        self.tagger = (
            self.add_tokens(ji_range)  # "几"字表达式优先级最高
            | self.add_tokens(fuzzy_number_range)  # 模糊数量词（十几、二十几）
            | self.add_tokens(range_pattern)
            | self.add_tokens(range_fractional_pattern)
            | self.add_tokens(recent_years_fixed)
            # "最近"相关模式放在前面，确保优先级高于单独的"近"匹配
            | self.add_tokens(range_recent_prefix)
            | self.add_tokens(recent_prefix_fractional)
            | self.add_tokens(recent_prefix_half_only)
            | self.add_tokens(range_past_prefix)
            | self.add_tokens(past_prefix_fractional)
            | self.add_tokens(past_prefix_half_only)
            | self.add_tokens(range_future_prefix)
            | self.add_tokens(future_prefix_fractional)
            | self.add_tokens(future_prefix_half_only)
            | self.add_tokens(default_past_range)
            | self.add_tokens(half_past_range)
            | self.add_tokens(number_ge_half_past_range)
            | self.add_tokens(number_ge_half_within_range)
            | self.add_tokens(number_unit_half_within_range)
        )
