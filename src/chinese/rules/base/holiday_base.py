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

from ...word_level_pynini import string_file, pynutil

from ....core.utils import get_abs_path

insert = pynutil.insert


class HolidayBaseRule:
    """节假日基础规则类"""

    def __init__(self):
        pass

    def build_rules(self):
        """构建节假日规则"""
        statutory_holidays = string_file(get_abs_path("../../data/holiday/statutory_holidays.tsv"))
        calendar_festivals = string_file(get_abs_path("../../data/holiday/calendar_festivals.tsv"))
        lunar_festivals = string_file(get_abs_path("../../data/holiday/lunar_festivals.tsv"))

        holiday = (
            insert('festival: "')
            + (statutory_holidays | calendar_festivals | lunar_festivals)
            + insert('"')
        )
        return holiday
