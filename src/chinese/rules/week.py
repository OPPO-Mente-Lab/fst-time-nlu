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
from .base import TimeBaseRule, WeekBaseRule


class WeekRule(Processor):
    """星期规则处理器，处理星期相关的时间表达式"""

    def __init__(self):
        super().__init__(name="time_weekday")
        self.weekday = WeekBaseRule().build_rules()
        self.time = TimeBaseRule().build_time_rules()
        self.build_tagger()

    def build_tagger(self):
        tagger = self.weekday | self.weekday + self.time
        self.tagger = self.add_tokens(tagger)
