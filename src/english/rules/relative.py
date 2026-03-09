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
from ...core.utils import INPUT_LOWER_CASED
from .base.relative_base import RelativeBaseRule


class RelativeRule(Processor):
    """Relative time rule processor, handles expressions like yesterday, today, tomorrow"""

    def __init__(self, input_case: str = INPUT_LOWER_CASED):
        super().__init__(name="time_relative")
        self.relative = RelativeBaseRule(input_case=input_case).build_std_rules()
        self.build_tagger()

    def build_tagger(self):
        """Build the tagger for relative time expressions"""
        tagger = self.add_tokens(self.relative)
        self.tagger = tagger
