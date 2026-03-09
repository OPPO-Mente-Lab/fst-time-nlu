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

from ..word_level_pynini import string_file, pynutil

from ...core.processor import Processor
from ...core.utils import get_abs_path
from .base import HolidayBaseRule

insert = pynutil.insert
delete = pynutil.delete


class HolidayRule(Processor):
    """节假日规则处理器"""

    def __init__(self):
        super().__init__(name="time_holiday")
        self.holiday_base = HolidayBaseRule().build_rules()
        self.build_tagger()

    def build_tagger(self):
        # 加载年份前缀和日期前缀数据
        year_prefix = string_file(get_abs_path("../data/date/year_prefix.tsv"))
        day_prefix = string_file(get_abs_path("../data/date/day_prefix.tsv"))

        # 构建年份偏移和日期前缀规则
        specific_year_dates = insert('offset_year: "') + year_prefix + insert('"')
        day_prefix_dates = insert('day_prefix: "') + day_prefix + insert('"')

        # 添加具体年份支持（如"2027年除夕"）
        # 加载数字映射
        arabic_digit = string_file(get_abs_path("../data/number/arabic_digit.tsv"))
        # 支持4位年份（2027年）和2位年份（27年）
        year_digit = (arabic_digit**4) | (arabic_digit**2)
        specific_year = insert('year: "') + year_digit + delete("年").ques + insert('"')

        # 支持：年份前缀 + 节假日、具体年份 + 节假日、节假日 + 日期前缀
        tagger = (specific_year_dates.ques + self.holiday_base + day_prefix_dates.ques) | (
            specific_year + self.holiday_base + day_prefix_dates.ques
        )
        self.tagger = self.add_tokens(tagger)
