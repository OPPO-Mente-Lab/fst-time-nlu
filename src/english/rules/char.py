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
from ..word_level_pynini import union, closure, pynutil, Fst, get_symbol_table
from ...core.processor import Processor
import pynini


class TokenRule(Processor):
    """
    Token rule processor for English (词级版本)

    词级FST中，TokenRule作为fallback，将任意未被其他规则匹配的token
    标记为 token { value: "xxx" }
    """

    def __init__(self):
        super().__init__(name="token")
        self.build_tagger()

    def build_tagger(self):
        """
        构建TokenRule：
        - 词级模式：匹配任意token（包括空格）→ 输出 token { value: "xxx" }
        - 字符级模式：匹配任意字符 → 输出 char { value: "x" }
        """
        # 尝试使用词级FST（检查GlobalSymbolTable是否存在）
        try:
            sym = get_symbol_table()
            if sym and sym.num_symbols() > 100:  # 词级符号表应该有很多符号
                # 词级模式
                token_fst = pynini.Fst()
                token_fst.set_input_symbols(sym)
                token_fst.set_output_symbols(sym)

                start = token_fst.add_state()
                final = token_fst.add_state()
                token_fst.set_start(start)
                token_fst.set_final(final)

                # 为所有token添加identity arc（包括空格）
                for i in range(1, sym.num_symbols()):  # 跳过epsilon (0)
                    # identity arc: 输入token -> 输出token
                    arc = pynini.Arc(i, i, pynini.Weight.one(token_fst.weight_type()), final)
                    token_fst.add_arc(start, arc)

                # 包装为 value:"token" （注意：不添加空格，避免TokenParser trim后空格token变成空字符串）
                wrapped_token = pynutil.insert('value:"') + token_fst + pynutil.insert('"')
                wrapped_token.set_input_symbols(sym)
                wrapped_token.set_output_symbols(sym)

                # 添加class wrapper: token { value: "xxx" }
                self.tagger = self.add_tokens(wrapped_token)
                return
        except Exception:
            # 如果词级FST失败，fallback到字符级
            pass

        # 字符级fallback（参考中文CharRule）
        from pynini.lib import pynutil as char_pynutil

        tagger = char_pynutil.insert('value:"') + self.CHAR + char_pynutil.insert('"')
        self.tagger = self.add_tokens(tagger)
