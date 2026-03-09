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

import pynini

from ..word_level_pynini import string_file, pynutil

from ...core.processor import Processor
from ...core.utils import get_abs_path
from .base import DateBaseRule, TimeBaseRule


class DeltaRule(Processor):
    """基于配置的简化版时间偏移处理器"""

    def __init__(self):
        super().__init__(name="time_delta")
        self.time_cnt = TimeBaseRule().build_time_cnt_rules()
        self.date_cnt = DateBaseRule().build_date_cnt_rule()

        # 构建偏移方向规则
        insert = pynutil.insert

        self.before_prefix_map = string_file(get_abs_path("../data/delta/before_prefix.tsv"))
        self.before_suffix_map = string_file(get_abs_path("../data/delta/before_subfix.tsv"))
        self.after_prefix_map = string_file(get_abs_path("../data/delta/after_prefix.tsv"))
        self.after_suffix_map = string_file(get_abs_path("../data/delta/after_subfix.tsv"))

        self.before_prefix = insert('offset_direction: "') + self.before_prefix_map + insert('"')
        self.before_suffix = insert('offset_direction: "') + self.before_suffix_map + insert('"')
        self.after_prefix = insert('offset_direction: "') + self.after_prefix_map + insert('"')
        self.after_suffix = insert('offset_direction: "') + self.after_suffix_map + insert('"')
        self.build_tagger()

    @staticmethod
    def _is_trivial_fst(fst: pynini.Fst) -> bool:
        """判断FST是否只包含空串（即无有效匹配）。"""
        if fst.start() == pynini.NO_STATE_ID:
            return True
        if fst.num_states() != 1:
            return False
        start_state = fst.start()
        if start_state == pynini.NO_STATE_ID:
            return True
        try:
            next(fst.arcs(start_state))
        except StopIteration:
            return True
        return False

    @staticmethod
    def _has_real_input(fst: pynini.Fst) -> bool:
        """检查FST是否存在至少一个非epsilon的输入标签。"""
        start = fst.start()
        if start == pynini.NO_STATE_ID:
            return False
        visited = set()
        stack = [start]
        while stack:
            state = stack.pop()
            if state in visited:
                continue
            visited.add(state)
            for arc in fst.arcs(state):
                if arc.ilabel != 0:
                    return True
                stack.append(arc.nextstate)
        return False

    def build_tagger(self):
        # 构建时间偏移规则
        components = []

        has_before_prefix = self._has_real_input(self.before_prefix_map)
        has_before_suffix = self._has_real_input(self.before_suffix_map)
        has_after_prefix = self._has_real_input(self.after_prefix_map)
        has_after_suffix = self._has_real_input(self.after_suffix_map)

        if has_before_prefix:
            components.append(self.before_prefix + self.time_cnt)
            components.append(self.before_prefix + self.date_cnt)
        if has_before_suffix:
            components.append(self.time_cnt + self.before_suffix)
            components.append(self.date_cnt + self.before_suffix)
        if has_after_prefix:
            components.append(self.after_prefix + self.time_cnt)
            components.append(self.after_prefix + self.date_cnt)
        if has_after_suffix:
            components.append(self.time_cnt + self.after_suffix)
            components.append(self.date_cnt + self.after_suffix)

        if not components:
            empty = pynini.Fst()
            empty.set_input_symbols(self.time_cnt.input_symbols())
            empty.set_output_symbols(self.time_cnt.output_symbols())
            self.tagger = self.add_tokens(empty)
            return

        tagger = pynini.union(*components).optimize()
        self.tagger = self.add_tokens(tagger)
