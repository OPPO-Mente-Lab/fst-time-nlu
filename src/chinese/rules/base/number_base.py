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

from ...word_level_pynini import accep, cross, union, pynutil

delete = pynutil.delete
insert = pynutil.insert
add_weight = pynutil.add_weight


class NumberBaseRule:
    """构建中文数字→阿拉伯数字的FST（仅用于通用数值，如 七十二 -> 72）。

    参考思路来自 TTS/ITN 的 Cardinal 规则，覆盖 十/百/千/万/亿 等常见组合。
    注意：这里只处理纯中文数字（不包含单位），用于与单位组合的规则（如 小时/天）。
    """

    def build_cn_number(self):
        # 简化版本：只处理1-99的常用中文数字，避免复杂组合

        # 个位（中文一到九）
        one_to_nine = (
            cross("一", "1")
            | cross("二", "2")
            | cross("两", "2")
            | cross("俩", "2")  # 口语化：俩 = 两个
            | cross("三", "3")
            | cross("仨", "3")  # 口语化：仨 = 三个
            | cross("四", "4")
            | cross("五", "5")
            | cross("六", "6")
            | cross("七", "7")
            | cross("八", "8")
            | cross("九", "9")
        )
        zero = cross("零", "0") | cross("〇", "0")

        # 十位：十/十一/十二.../十九
        ten = cross("十", "10")
        teen = cross("十", "1") + one_to_nine  # 十一到十九

        # 几十：二十/三十/四十.../九十
        tens = one_to_nine + delete("十") + one_to_nine  # 二十一/二十二等
        tens_simple = one_to_nine + cross("十", "0")  # 二十/三十等 -> 20/30等

        # 组合：0-9, 10, 11-19, 20-99
        number = zero | one_to_nine | ten | teen | tens | tens_simple

        return number.optimize()
