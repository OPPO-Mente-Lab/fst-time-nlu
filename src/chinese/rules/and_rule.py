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

from ...core.processor import Processor
from ..word_level_pynini import pynutil

delete = pynutil.delete
insert = pynutil.insert


class AndRule(Processor):
    """并列连接词规则：识别“和”作为独立连接token。

    该规则仅产出 `and { value: "和" }`，左右端点由各自规则独立产出与解析。
    """

    def __init__(self):
        super().__init__(name="and")
        self.build_tagger()

    def build_tagger(self):
        # 产出 and { value: "和" } 或 and { value: "、" }
        tagger = (insert('value: "和"') + delete("和")) | (insert('value: "、"') + delete("、"))
        self.tagger = self.add_tokens(tagger)
