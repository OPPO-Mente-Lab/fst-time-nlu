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

from ...word_level_pynini import pynutil

insert = pynutil.insert


class CharBaseRule:
    """字符基础规则类"""

    def __init__(self):
        pass

    def build_rules(self):
        """构建字符规则"""
        char = insert('value: "') + self.CHAR + insert('"')
        return char
