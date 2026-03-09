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

from ...word_level_pynini import string_file, union, pynutil

from ....core.utils import get_abs_path

delete = pynutil.delete
insert = pynutil.insert


class WeekBaseRule:
    """星期基础规则类"""

    def __init__(self):
        pass

    def build_rules(self):
        """构建星期规则"""
        # 加载TSV文件
        weekday = string_file(get_abs_path("../../data/week/weekday.tsv"))
        week_word = string_file(get_abs_path("../../data/week/week_word.tsv"))
        week_prefix = string_file(get_abs_path("../../data/week/week_prefix.tsv"))

        week_offset_prefix = insert('offset_week: "') + week_prefix + insert('"')
        weekday_tag = insert('week_day: "') + weekday + insert('"')
        # 通用设置
        optional_ge = delete("个").ques

        # 带前缀的周表达式
        prefixed_week_date = week_offset_prefix + optional_ge + delete(week_word) + weekday_tag.ques

        # 组合所有周相关表达式
        week_date = prefixed_week_date | delete(week_word) + weekday_tag
        return week_date
