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

from ...core.processor import Processor


class CharRule(Processor):
    """占位用的 char 规则。

    词级管道在无法匹配时间表达式时会回退到字符级输出，这里仅保留一个
    轻量规则用于在规则列表中声明 `char` 的存在，避免再次构建庞大的词级
    union。
    """

    def __init__(self):
        super().__init__(name="char")
        self.build_tagger()

    def build_tagger(self):
        # 构建一个 ε 转换，占位表达式
        fst = pynini.Fst()
        state = fst.add_state()
        fst.set_start(state)
        fst.set_final(state)
        self.tagger = fst.optimize()
