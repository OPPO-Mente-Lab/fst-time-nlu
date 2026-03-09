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
from .base import LunarBaseRule, TimeBaseRule

delete = pynutil.delete


class LunarRule(Processor):
    """农历时间规则处理器"""

    def __init__(self):
        super().__init__(name="time_lunar")
        lunar_base = LunarBaseRule()
        self.lunar_date = lunar_base.build_date_rules()
        self.lunar_month = lunar_base.build_month_rules()
        self.lunar_monthday = lunar_base.build_monthday_rules()
        self.lunar_jieqi = lunar_base.build_jieqi_rules()
        self.time = TimeBaseRule().build_time_rules()
        self.build_tagger()

    def build_tagger(self):
        # 构建农历时间表达式
        lunar_time = (
            (self.lunar_date + self.time)
            | self.lunar_date
            | self.lunar_month
            | self.lunar_monthday
            | self.lunar_jieqi
        )

        tagger = self.add_tokens(lunar_time)

        # # 支持时间范围表达式
        # to = (delete('-') | delete('~') | delete('到'))
        # self.tagger = tagger + (to + tagger).ques
        self.tagger = tagger
