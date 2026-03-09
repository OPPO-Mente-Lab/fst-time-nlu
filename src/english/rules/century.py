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

# 使用词级pynini
from ..word_level_pynini import string_file, union, accep
from ..word_level_pynini import pynutil
from ..word_level_pynini import word_delete_space

from ...core.processor import Processor
from ...core.utils import get_abs_path


class CenturyRule(Processor):
    """
    Century and decade rule processor
    Handles expressions like:
    - last century -> 1900-1999
    - this century -> 2000-2099
    - 19th century -> 1800-1899
    - the 80s -> 1980-1989
    - seventies of last century -> 1970-1979
    """

    def __init__(self):
        super().__init__(name="time_century")
        self.build_tagger()

    def build_tagger(self):
        delete = pynutil.delete
        insert = pynutil.insert
        # 使用词级delete_space
        delete_space = word_delete_space()
        # Load modifiers
        century_modifier = string_file(get_abs_path("../data/date/century_modifiers.tsv"))

        # Load decades
        decades = string_file(get_abs_path("../data/date/decades.tsv"))

        # Ordinal numbers for centuries (word form: first through thirty first)
        ordinal_century_words = string_file(get_abs_path("../data/numbers/ordinal_exceptions.tsv"))

        # Numeric ordinals for centuries (1st, 2nd, 3rd, ..., 21st, etc.)
        # Build FST for numeric ordinals: 1-99 with st/nd/rd/th suffix
        # 词级FST：数字是完整token（如"1", "21", "99"），需要创建所有可能的数字token union
        # 创建1-99的数字token union
        numeric_tokens = [accep(str(i)) for i in range(1, 100)]  # 1-99
        numeric_number = union(*numeric_tokens)

        # 词级FST：序数后缀也是完整token（如"st", "nd", "rd", "th"）
        ordinal_suffix = union(accep("st"), accep("nd"), accep("rd"), accep("th"))

        # 匹配"数字+后缀"格式（如"1st", "21st"）
        # 在词级FST中，这些可能是两个token（"1" + "st"）或一个token（"1st"）
        # 为了兼容两种情况，需要匹配两种模式
        numeric_ordinal_with_space = numeric_number + delete_space.ques + delete(ordinal_suffix)
        # 如果分词器将"1st"作为一个token，需要从TSV文件加载或使用cross映射
        # 这里先使用有空格分隔的模式，如果没有匹配到，可能需要扩展
        numeric_ordinal = numeric_ordinal_with_space

        # Combine word and numeric ordinals
        ordinal_century = ordinal_century_words | numeric_ordinal

        # Century word
        century_word = delete("century")

        # Pattern 1: "[modifier] century" (e.g., "last century", "this century")
        pattern1 = (
            insert('modifier:"') + century_modifier + insert('"') + delete_space + century_word
        )

        # Pattern 2: "[ordinal] century" (e.g., "19th century", "twentieth century")
        pattern2 = (
            insert('century_num:"') + ordinal_century + insert('"') + delete_space + century_word
        )

        # Pattern 3: "the [decade]s" (e.g., "the 80s", "the eighties")
        the_optional = delete("the").ques
        pattern3 = the_optional + delete_space.ques + insert('decade:"') + decades + insert('"')

        # Pattern 4: "[decade] of [modifier] century" (e.g., "seventies of last century")
        pattern4 = (
            insert('decade:"')
            + decades
            + insert('"')
            + delete_space
            + delete("of")
            + delete_space
            + insert('modifier:"')
            + century_modifier
            + insert('"')
            + delete_space
            + century_word
        )

        # Pattern 5: "[decade] of [ordinal] century" (e.g., "nineties of twentieth century")
        pattern5 = (
            insert('decade:"')
            + decades
            + insert('"')
            + delete_space
            + delete("of")
            + delete_space
            + insert('century_num:"')
            + ordinal_century
            + insert('"')
            + delete_space
            + century_word
        )

        # Combine patterns - more specific first
        tagger = pattern5 | pattern4 | pattern3 | pattern2 | pattern1

        self.tagger = self.add_tokens(tagger)
