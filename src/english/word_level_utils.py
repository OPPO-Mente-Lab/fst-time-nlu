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
词级FST构建工具函数

提供词级版本的pynini常用函数，如string_file、accep、delete、insert等。
"""

import pynini
from typing import Union
from .global_symbol_table import get_symbol_table

sym = get_symbol_table()


def word_accep(text: str, weight: Union[float, pynini.Weight] = None) -> pynini.Fst:  # noqa: C901
    """
    词级版本的pynini.accep（智能拆分版本）

    自动将未知token拆分为已知的字符，但如果词看起来像单词（全字母且长度>1），
    即使不在SymbolTable中也会尝试作为整体匹配（因为分词器可能已将其保留为整体token）
    """

    def smart_tokenize(text):
        """智能分词：自动拆分未知token"""
        tokens = []
        for word in text.split():
            if sym.find(word) != -1:
                tokens.append(word)
            else:
                # 如果词看起来像单词（全字母且长度>1），尝试作为整体
                # 这样可以匹配分词器保留的未知词（如"fortnight"）
                if word.isalpha() and len(word) > 1:
                    # 尝试添加到SymbolTable（如果可能）
                    # 如果添加失败，仍然尝试作为整体token（分词器已保留）
                    tokens.append(word)
                else:
                    # 逐字符拆分
                    for char in word:
                        if sym.find(char) != -1:
                            tokens.append(char)
        return tokens

    # 智能分词
    tokens = smart_tokenize(text.lower())

    if not tokens:
        # 空token，返回epsilon FST
        fst = pynini.Fst()
        s = fst.add_state()
        fst.set_start(s)
        fst.set_final(s)
        fst.set_input_symbols(sym)
        fst.set_output_symbols(sym)
        return fst

    # 构建acceptor FST
    fst = pynini.Fst()
    fst.set_input_symbols(sym)
    fst.set_output_symbols(sym)

    states = [fst.add_state() for _ in range(len(tokens) + 1)]
    fst.set_start(states[0])
    fst.set_final(states[-1])

    for i, token in enumerate(tokens):
        token_id = sym.find(token)
        if token_id == -1:
            # Token不在SymbolTable中，但分词器已保留为整体
            # 尝试动态添加到SymbolTable（如果可能）
            # 如果无法添加，跳过这个token（会导致FST无法匹配，但这是预期的）
            # 实际上，如果分词器保留了它，SymbolTable应该已经包含它
            # 如果仍然找不到，可能是SymbolTable初始化问题
            continue
        arc = pynini.Arc(token_id, token_id, pynini.Weight.one(fst.weight_type()), states[i + 1])
        fst.add_arc(states[i], arc)

    # 应用权重
    if weight is not None:
        from pynini.lib import pynutil

        fst = pynutil.add_weight(fst, weight)

    return fst


def word_cross(input_str: str, output_str: str) -> pynini.Fst:  # noqa: C901
    """
    词级版本的pynini.cross（智能拆分版本）

    自动将未知token拆分为已知的字符或token
    分词方式与EnglishWordTokenizer保持一致，特别是所有格的处理
    """

    def smart_tokenize(text, is_output=False):
        """
        智能分词：与EnglishWordTokenizer保持一致
        特别处理所有格：总是拆分为base_word + possessive
        例如："father's day" -> ['father', "'s", ' ', 'day']

        Args:
            text: 输入文本
            is_output: 如果是True，表示这是输出字符串，优先检查完整字符串是否在SymbolTable中
        """
        tokens = []

        # 对于输出字符串，优先检查完整字符串是否在SymbolTable中
        # 这样可以保留TSV文件中的下划线格式（如"fathers_day"）
        if is_output and sym.find(text) != -1:
            return [text]

        import re

        # 使用与EnglishWordTokenizer相同的正则模式
        pattern = r"[a-z]+(?:'[a-z]+)?(?:[-.][a-z]+(?:'[a-z]+)?)*|[0-9]+|[^\w\s]|\s+"
        matches = re.findall(pattern, text.lower())

        # 后处理：检查匹配结果，如果包含所有格，需要拆分为base_word和"'s"
        processed_matches = []
        for match in matches:
            if match and not match.isspace() and match[0].isalpha() and "'" in match:
                # 包含所有格的单词，拆分为base_word和possessive
                # 例如："father's" -> "father" + "'s"
                parts = match.rsplit("'", 1)
                base_word = parts[0]
                possessive_suffix = parts[1] if len(parts) > 1 else ""

                if base_word:
                    processed_matches.append(base_word)
                if possessive_suffix:
                    # 将"'s"作为一个整体token
                    possessive = "'" + possessive_suffix
                    processed_matches.append(possessive)
            else:
                processed_matches.append(match)

        # 处理每个匹配的token
        for match in processed_matches:
            if not match:
                continue
            if match.isspace():
                # 空格token
                if sym.find(" ") != -1:
                    tokens.append(" ")
                continue
            if sym.find(match) != -1:
                tokens.append(match)
            else:
                # 不在符号表中，逐字符拆分
                for char in match:
                    if sym.find(char) != -1:
                        tokens.append(char)
        return tokens

    # 智能分词
    # 输入：使用EnglishWordTokenizer的分词方式（拆分所有格）
    # 输出：优先使用完整字符串（保留TSV中的格式，如下划线）
    input_tokens = smart_tokenize(input_str.lower(), is_output=False)
    output_tokens = smart_tokenize(output_str, is_output=True)

    if not input_tokens or not output_tokens:
        # 空token，返回epsilon FST
        fst = pynini.Fst()
        s = fst.add_state()
        fst.set_start(s)
        fst.set_final(s)
        return fst

    # 构建cross FST
    fst = pynini.Fst()
    fst.set_input_symbols(sym)
    fst.set_output_symbols(sym)

    # 状态数 = max(input_len, output_len) + 1
    max_len = max(len(input_tokens), len(output_tokens))
    states = [fst.add_state() for _ in range(max_len + 1)]
    fst.set_start(states[0])
    fst.set_final(states[-1])

    # 添加arcs
    for i in range(max_len):
        inp_id = sym.find(input_tokens[i]) if i < len(input_tokens) else 0  # epsilon
        out_id = sym.find(output_tokens[i]) if i < len(output_tokens) else 0  # epsilon

        arc = pynini.Arc(inp_id, out_id, pynini.Weight.one(fst.weight_type()), states[i + 1])
        fst.add_arc(states[i], arc)

    return fst


def word_delete(text: str) -> pynini.Fst:
    """
    词级版本的pynutil.delete

    Args:
        text: 要删除的文本

    Returns:
        词级delete FST
    """

    # 分词
    tokens = text.lower().split()

    if not tokens:
        # 空删除，返回epsilon
        fst = pynini.Fst()
        s = fst.add_state()
        fst.set_start(s)
        fst.set_final(s)
        fst.set_input_symbols(sym)
        fst.set_output_symbols(sym)
        return fst

    # 构建FST：token输入，epsilon输出
    fst = pynini.Fst()
    fst.set_input_symbols(sym)
    fst.set_output_symbols(sym)

    states = [fst.add_state() for _ in range(len(tokens) + 1)]
    fst.set_start(states[0])
    fst.set_final(states[-1])

    for i, token in enumerate(tokens):
        token_id = sym.find(token)
        if token_id == -1:
            raise ValueError(f"Token '{token}' not in SymbolTable")

        # token输入，epsilon输出
        arc = pynini.Arc(token_id, 0, pynini.Weight.one(fst.weight_type()), states[i + 1])
        fst.add_arc(states[i], arc)

    return fst


def word_insert(text: str) -> pynini.Fst:
    """
    词级版本的pynutil.insert

    Args:
        text: 要插入的文本

    Returns:
        词级insert FST
    """

    # 智能分词：使用贪婪匹配策略，优先匹配符号表中的长token
    tokens = []
    i = 0

    while i < len(text):
        # 策略1：贪婪匹配 - 从最长到最短尝试匹配
        matched = False

        # 尝试从当前位置开始的所有可能长度（从长到短）
        for length in range(len(text) - i, 0, -1):
            candidate = text[i : i + length]
            if sym.find(candidate) != -1:
                tokens.append(candidate)
                i += length
                matched = True
                break

        if not matched:
            # 策略2：单字符匹配（如果在符号表中）
            char = text[i]
            if sym.find(char) != -1:
                tokens.append(char)
            # 如果单字符也不在符号表中，跳过（或记录警告）
            i += 1

    if not tokens:
        # 空插入，返回epsilon
        fst = pynini.Fst()
        s = fst.add_state()
        fst.set_start(s)
        fst.set_final(s)
        return fst

    # 构建FST：epsilon输入，token输出
    fst = pynini.Fst()
    fst.set_input_symbols(sym)
    fst.set_output_symbols(sym)

    states = [fst.add_state() for _ in range(len(tokens) + 1)]
    fst.set_start(states[0])
    fst.set_final(states[-1])

    for i, token in enumerate(tokens):
        token_id = sym.find(token)
        # epsilon输入，token输出
        arc = pynini.Arc(0, token_id, pynini.Weight.one(fst.weight_type()), states[i + 1])
        fst.add_arc(states[i], arc)

    return fst


def word_delete_space():
    """
    词级版本的delete_space

    在词级FST中，空格是一个token ' '，需要删除0个或多个空格token

    Returns:
        词级delete_space FST
    """

    # 空格token
    space_token_id = sym.find(" ")
    if space_token_id == -1:
        # 空格不在SymbolTable中，返回epsilon（不删除任何东西）
        fst = pynini.Fst()
        s = fst.add_state()
        fst.set_start(s)
        fst.set_final(s)
        fst.set_input_symbols(sym)
        fst.set_output_symbols(sym)
        return fst

    # 构建FST：匹配0个或多个空格token，输出epsilon
    fst = pynini.Fst()
    fst.set_input_symbols(sym)
    fst.set_output_symbols(sym)

    # 创建状态：开始状态 = 结束状态（允许0个空格）
    s = fst.add_state()
    fst.set_start(s)
    fst.set_final(s)

    # 添加自循环：允许任意多个空格token
    arc = pynini.Arc(space_token_id, 0, pynini.Weight.one(fst.weight_type()), s)
    fst.add_arc(s, arc)

    return fst


def word_delete_extra_space():
    """
    词级版本的delete_extra_space

    在词级FST中，将1个或多个空格token压缩为1个空格token输出

    Returns:
        词级delete_extra_space FST
    """

    # 空格token
    space_token_id = sym.find(" ")
    if space_token_id == -1:
        # 空格不在SymbolTable中，返回epsilon
        fst = pynini.Fst()
        s = fst.add_state()
        fst.set_start(s)
        fst.set_final(s)
        fst.set_input_symbols(sym)
        fst.set_output_symbols(sym)
        return fst

    # 构建FST：1个或多个空格token -> 1个空格token
    fst = pynini.Fst()
    fst.set_input_symbols(sym)
    fst.set_output_symbols(sym)

    # 状态0: 起始状态
    s0 = fst.add_state()
    fst.set_start(s0)

    # 状态1: 已匹配至少1个空格，输出1个空格
    s1 = fst.add_state()
    fst.set_final(s1)

    # 从s0到s1: 第一个空格，输出空格
    arc1 = pynini.Arc(space_token_id, space_token_id, pynini.Weight.one(fst.weight_type()), s1)
    fst.add_arc(s0, arc1)

    # 从s1自循环: 更多空格，输出epsilon（删除）
    arc2 = pynini.Arc(space_token_id, 0, pynini.Weight.one(fst.weight_type()), s1)
    fst.add_arc(s1, arc2)

    return fst.optimize()


def word_string_file(file_path: str) -> pynini.Fst:
    """
    词级版本的pynini.string_file

    读取TSV文件并构建词级FST

    Args:
        file_path: TSV文件路径

    Returns:
        词级FST
    """

    # 读取TSV文件
    mappings = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            parts = line.split("\t")
            if len(parts) >= 2:
                input_str = parts[0].lower()
                output_str = parts[1]
                mappings.append((input_str, output_str))

    if not mappings:
        # 空文件，返回空FST
        fst = pynini.Fst()
        s = fst.add_state()
        fst.set_start(s)
        fst.set_final(s)
        return fst

    # 构建union of all mappings
    fsts = []
    for input_str, output_str in mappings:
        try:
            fst = word_cross(input_str, output_str)
            fsts.append(fst)
        except ValueError as e:
            # 跳过无法处理的映射（如token不在SymbolTable中）
            print(f"⚠️  跳过映射: {input_str} -> {output_str} ({e})")
            continue

    if not fsts:
        # 所有映射都失败，返回空FST
        fst = pynini.Fst()
        s = fst.add_state()
        fst.set_start(s)
        fst.set_final(s)
        return fst

    # Union所有FSTs
    result = fsts[0]
    for fst in fsts[1:]:
        result = pynini.union(result, fst)

    return result.optimize()


# 测试代码
if __name__ == "__main__":
    print("=" * 80)
    print("测试词级FST工具函数")
    print("=" * 80)
    print()

    # 测试word_delete_space
    print("1. 测试word_delete_space:")
    try:
        fst = word_delete_space()
        print(f"   ✓ word_delete_space: {fst.num_states()} states")
        print(f"   输入符号表: {fst.input_symbols() is not None}")
    except Exception as e:
        print(f"   ✗ 失败: {e}")
        import traceback

        traceback.print_exc()
