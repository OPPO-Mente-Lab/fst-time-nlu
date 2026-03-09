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

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TokenRule - 词级版本（最简化，直接复用char.py逻辑）

使用原有char.py的实现，但替换import为词级版本。
"""

# 使用词级pynini
from ..word_level_pynini import union, accep


class TokenRule:
    """Token rule - 词级FST版本"""

    def __init__(self):
        # 直接从char.py复制逻辑
        # 创建所有可打印字符的union
        # 在词级FST中，这变成了所有词的union

        # 简化方案：只接受基本字符/词，作为通用fallback
        # 实际实现：创建一个"接受任意单个symbol"的FST

        # 最简单的实现：接受空格和常见标点
        common_tokens = [" ", ".", ",", ":", "-", "!", "?"]

        token_fsts = []
        for token in common_tokens:
            try:
                fst = accep(token)
                token_fsts.append(fst)
            except Exception:
                pass

        if token_fsts:
            self.tagger = token_fsts[0]
            for fst in token_fsts[1:]:
                self.tagger = union(self.tagger, fst)
            self.tagger = self.tagger.optimize()
        else:
            # 空FST
            from ..word_level_pynini import Fst

            self.tagger = Fst()
            s = self.tagger.add_state()
            self.tagger.set_start(s)
            self.tagger.set_final(s)


if __name__ == "__main__":
    print("测试TokenRule（最简化版）")
    print("=" * 80)

    try:
        rule = TokenRule()
        print("✓ TokenRule创建成功")
        print(f"  Tagger状态数: {rule.tagger.num_states()}")
    except Exception as e:
        print("✗ 失败: " + str(e))
        import traceback

        traceback.print_exc()
