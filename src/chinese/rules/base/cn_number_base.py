# Copyright (c)  2025  OPPO Corporation.   (authors: Ming Yu, Liangliang Han)
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

from ...word_level_pynini import union


def cn_digit_union():
    """返回中文数字字符集合的可复用接受器（不做数值映射）。"""
    return union(
        "零",
        "〇",
        "一",
        "二",
        "两",
        "三",
        "四",
        "五",
        "六",
        "七",
        "八",
        "九",
        "十",
        "拾",
        "百",
        "佰",
        "千",
        "仟",
        "万",
        "萬",
        "亿",
        "億",
        "壹",
        "贰",
        "貳",
        "叁",
        "參",
        "肆",
        "伍",
        "陆",
        "陸",
        "柒",
        "捌",
        "玖",
    )
