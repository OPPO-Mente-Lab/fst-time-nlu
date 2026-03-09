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

from ..word_level_pynini import string_file

from ...core.processor import Processor
from ...core.utils import get_abs_path


class PreProcessor(Processor):
    """预处理器，用于文本预处理"""

    def __init__(self, traditional_to_simple=True, mapping_path: str = None):
        super().__init__(name="preprocessor")

        processor = self.build_rule("")
        if traditional_to_simple:
            # 支持传入精简映射表路径；未提供则回退到默认全量表
            path = mapping_path or "../data/char/traditional_to_simple.tsv"
            traditional_to_simple_rules = string_file(get_abs_path(path))
            processor @= self.build_rule(traditional_to_simple_rules)

        self.processor = processor.optimize()
