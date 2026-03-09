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
英文词级分词器和SymbolTable管理

将英文文本从字符级转换为词级处理，大幅减少FST token数量。
"""

import pynini
import re
import json
import os
from typing import List, Optional
from .global_symbol_table import get_symbol_table


class EnglishWordTokenizer:
    """
    英文词级分词器

    核心功能：
    1. 维护词汇表（SymbolTable）
    2. 将文本分词为词列表
    3. 构建词级输入FST
    """

    def __init__(self, vocab_file: Optional[str] = None):
        """
        初始化分词器

        Args:
            vocab_file: 词汇表文件路径，默认使用vocabulary_complete.txt（已废弃，使用全局SymbolTable）
        """
        # 使用全局SymbolTable（单例）
        self.sym = get_symbol_table()

        # 从SymbolTable构建词汇表
        self.vocab = set()
        for i in range(self.sym.num_symbols()):
            symbol = self.sym.find(i)
            if symbol and symbol.isalpha():
                self.vocab.add(symbol)

        # 统计信息
        self.stats = {
            "total_words": 0,
            "unknown_words": 0,
            "char_level_fallback": 0,
            "long_number_tokens": 0,
        }
        self.long_number_threshold = 6  # >=6 位的数字视为长数字，避免膨胀
        self.long_number_token = "__long_number__"
        if self.sym.find(self.long_number_token) == -1:
            self.sym.add_symbol(self.long_number_token)
        
        # 特殊token：用于标记不在SymbolTable中的字符
        self.unknown_char_token = "__unknown_char__"
        if self.sym.find(self.unknown_char_token) == -1:
            self.sym.add_symbol(self.unknown_char_token)
        
        # 维护未知字符列表（按出现顺序，用于输出时恢复）
        self.unknown_chars = []

    def _smart_split_unknown_string(self, text: str) -> List[str]:
        """
        智能拆分不在SymbolTable中的字符串
        
        策略：
        1. 尝试找出字符串中哪些部分在SymbolTable中（优先匹配长串）
        2. 对于不在SymbolTable中的字符，作为token保留（但不会添加到SymbolTable）
           - 这些token在FST构建时会被跳过
           - 它们会被TokenRule处理（如果TokenRule支持），输出为 token { value: "xxx" }
        
        例如："next甲乙丙丁morning" -> ['next', '甲', '乙', '丙', '丁', 'morning']
        
        Args:
            text: 输入字符串（不在SymbolTable中）
            
        Returns:
            List[str]: 拆分后的token列表（包含不在SymbolTable中的字符）
        """
        tokens = []
        i = 0
        n = len(text)
        
        while i < n:
            # 尝试从当前位置开始，找到最长的在SymbolTable中的子串
            found = False
            # 从最长到最短尝试匹配
            for length in range(min(n - i, 20), 0, -1):  # 最多尝试20个字符
                substring = text[i:i + length]
                if self.sym.find(substring) != -1:
                    tokens.append(substring)
                    i += length
                    found = True
                    break
            
            if not found:
                # 当前字符不在SymbolTable中，作为token保留（但不添加到SymbolTable）
                # 在FST构建时会被跳过，但会被TokenRule处理
                char = text[i]
                tokens.append(char)
                i += 1
        
        return tokens

    def tokenize(self, text: str) -> List[str]:  # noqa: C901
        """
        将文本分词为词列表

        策略：
        - 带连字符/点的词：尝试作为整体
        - 字母序列：作为整词，如果不在词汇表则拆成字符
        - 连续数字：作为整体
        - 标点：保持单字符
        - 空格：保留（用于词间分隔）

        Args:
            text: 输入文本

        Returns:
            词token列表
        """
        text = text.lower().strip()
        tokens = []
        # 清空未知字符列表（每次tokenize时重新开始）
        self.unknown_chars = []

        # 改进的正则：先匹配所有格形式（word's），再匹配普通单词
        # 匹配顺序：1) 所有格形式（word's） 2) 普通单词 3) 数字 4) 标点 5) 空格
        # 注意：正则表达式需要能匹配包含单引号的单词，然后后处理拆分
        # 修改：将 [a-z]+ 改为 [^\W\d_]+ 以支持 Unicode 字母（包括中文）
        pattern = r"[^\W\d_]+(?:'[^\W\d_]+)?(?:[-.][^\W\d_]+(?:'[^\W\d_]+)?)*|[0-9]+|[^\w\s]|\s+"
        matches = re.findall(pattern, text)

        # 后处理：检查匹配结果，如果包含所有格，需要拆分为base_word和"'s"
        processed_matches = []
        for match in matches:
            if match and not match.isspace() and match[0].isalpha() and "'" in match:
                # 包含所有格的单词，拆分为base_word和possessive
                # 例如："year's" -> "year" + "'s"
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
        matches = processed_matches

        for match in matches:
            if match.isspace():
                # 保留空格作为分隔符
                tokens.append(" ")
            elif match[0].isalpha():
                # 字母序列（可能带所有格、连字符等）
                # 先尝试作为整体查找（包括所有格形式）
                if self.sym.find(match) != -1:
                    tokens.append(match)
                    self.stats["total_words"] += 1
                elif match in self.vocab:
                    tokens.append(match)
                    self.stats["total_words"] += 1
                else:
                    # 不在词汇表，检查是否包含所有格
                    if "'" in match:
                        # 处理所有格：总是拆分为base_word + possessive
                        # 例如："tomorrow's" -> "tomorrow" + "'s"
                        parts = match.rsplit("'", 1)
                        base_word = parts[0]  # "tomorrow's" -> "tomorrow"
                        possessive_suffix = parts[1] if len(parts) > 1 else ""
                        possessive = "'" + possessive_suffix if possessive_suffix else "'s"

                        # 处理base_word：优先作为整体，避免字符级拆分
                        if base_word:
                            if self.sym.find(base_word) != -1:
                                tokens.append(base_word)
                                self.stats["total_words"] += 1
                            elif base_word in self.vocab:
                                tokens.append(base_word)
                                self.stats["total_words"] += 1
                            else:
                                # base_word不在符号表，但不要立即拆分
                                # 先尝试添加到vocab（如果看起来像单词）
                                if base_word.isalpha() and len(base_word) > 1:
                                    # 看起来像单词，尝试直接添加（可能SymbolTable会动态添加）
                                    tokens.append(base_word)
                                    self.stats["total_words"] += 1
                                else:
                                    # 最终回退：字符级
                                    tokens.extend(list(base_word))
                                    self.stats["char_level_fallback"] += len(base_word)

                        # 添加所有格后缀（优先使用标准形式"'s"）
                        if possessive:
                            # 尝试标准形式"'s"
                            standard_possessive = "'s"
                            if self.sym.find(standard_possessive) != -1:
                                tokens.append(standard_possessive)
                            elif self.sym.find(possessive) != -1:
                                tokens.append(possessive)
                            else:
                                # 如果都不在，尝试添加标准形式（可能SymbolTable会处理）
                                tokens.append(standard_possessive)
                                # 记录但不回退到字符级（所有格后缀应该是标准形式）
                    elif "-" in match or "." in match:
                        # 检查是否为"字母+符号+字母"模式
                        letter_symbol_letter_pattern = r'^[a-z]+[-.][a-z]+$'
                        
                        if re.match(letter_symbol_letter_pattern, match):
                            # 字母+符号+字母模式：保持整体不拆分
                            # 尝试作为整体在 SymbolTable 中查找
                            if self.sym.find(match) != -1:
                                tokens.append(match)
                                self.stats["total_words"] += 1
                            else:
                                # 整体不在 SymbolTable 中，拆分成字符级别
                                # 这样可以避免误识别，比如 "CAN-BOM" 不会识别出 "BOM"
                                for char in match:
                                    if self.sym.find(char) != -1:
                                        tokens.append(char)
                                    else:
                                        # 字符不在 SymbolTable 中，也添加（保持完整性）
                                        tokens.append(char)
                                self.stats["unknown_words"] += 1
                                self.stats["char_level_fallback"] += len(match)
                        else:
                            # 非字母+符号+字母模式：保持原有拆分逻辑
                            # 例如：12-30, apple-123 等
                            parts = re.split(r"([-'.])", match)
                            for part in parts:
                                if part and self.sym.find(part) != -1:
                                    tokens.append(part)
                                elif part and part in self.vocab:
                                    tokens.append(part)
                                elif part:
                                    # 最终回退：字符级
                                    tokens.extend(list(part))
                                    self.stats["char_level_fallback"] += len(part)
                    else:
                        # 单纯的未知词
                        # 如果看起来像单词（全字母且长度>1），且不在SymbolTable中
                        # 使用智能拆分：找出在SymbolTable中的部分，保留不在的部分作为特殊token
                        if match.isalpha() and len(match) > 1:
                            # 检查是否在SymbolTable中
                            if self.sym.find(match) != -1:
                                # 在SymbolTable中，作为整体保留
                                tokens.append(match)
                                self.stats["total_words"] += 1
                            else:
                                # 不在SymbolTable中，使用智能拆分
                                split_tokens = self._smart_split_unknown_string(match)
                                for token in split_tokens:
                                    if self.sym.find(token) != -1:
                                        tokens.append(token)
                                        self.stats["total_words"] += 1
                                    else:
                                        # 不在SymbolTable中的字符，使用特殊token标记
                                        # 记录原始字符，以便输出时恢复
                                        self.unknown_chars.append(token)
                                        tokens.append(self.unknown_char_token)
                                        self.stats["unknown_words"] += 1
                                self.stats["char_level_fallback"] += len([t for t in split_tokens if self.sym.find(t) == -1])
                        else:
                            # 单字符或非字母：使用智能拆分
                            split_tokens = self._smart_split_unknown_string(match)
                            for token in split_tokens:
                                if self.sym.find(token) != -1:
                                    tokens.append(token)
                                else:
                                    # 不在SymbolTable中的字符，使用特殊token标记
                                    # 记录原始字符，以便输出时恢复
                                    self.unknown_chars.append(token)
                                    tokens.append(self.unknown_char_token)
                                    self.stats["unknown_words"] += 1
                            self.stats["char_level_fallback"] += len([t for t in split_tokens if self.sym.find(t) == -1])
            elif match[0].isdigit():
                # 检查是否包含序数后缀（st, nd, rd, th）
                # 例如："20th" -> ["20", "th"], "2nd" -> ["2", "nd"]
                ordinal_match = re.match(r"^(\d+)(st|nd|rd|th)$", match, re.IGNORECASE)
                if ordinal_match:
                    number = ordinal_match.group(1)
                    suffix = ordinal_match.group(2).lower()  # 统一小写

                    # 处理数字部分
                    if len(number) >= self.long_number_threshold or self.sym.find(number) == -1:
                        tokens.append(self.long_number_token)
                        self.stats["long_number_tokens"] += 1
                    else:
                        tokens.append(number)

                    # 处理序数后缀（应该已在symbol table中）
                    if self.sym.find(suffix) != -1:
                        tokens.append(suffix)
                    else:
                        # 如果后缀不在symbol table，尝试添加（不应该发生）
                        tokens.append(suffix)
                        self.stats["char_level_fallback"] += len(suffix)
                else:
                    # 普通数字，不包含序数后缀
                    # 连续数字作为整体
                    if len(match) >= self.long_number_threshold or self.sym.find(match) == -1:
                        tokens.append(self.long_number_token)
                        self.stats["long_number_tokens"] += 1
                    else:
                        tokens.append(match)
            else:
                # 标点（包括冒号等）
                # 特殊处理：时间格式中的冒号（如"8:30"）应该在分词时保持
                # 但这里match已经是单个字符（冒号），所以直接处理
                if self.sym.find(match) != -1:
                    tokens.append(match)
                else:
                    # 🔧 对齐中文tokenizer：不在符号表中的字符，尝试拆分为字符
                    # 如果拆分后仍然没有在符号表中的字符，则过滤掉（不添加）
                    fallback_chars = [ch for ch in match if self.sym.find(ch) != -1]
                    if fallback_chars:
                        tokens.extend(fallback_chars)
                        self.stats["char_level_fallback"] += len(fallback_chars)
                    else:
                        # 完全未知的字符，使用特殊token标记
                        # 记录原始字符，以便输出时恢复
                        self.unknown_chars.append(match)
                        tokens.append(self.unknown_char_token)
                        self.stats["unknown_tokens"] = self.stats.get("unknown_tokens", 0) + 1
                        self.stats["unknown_words"] += 1

        return tokens

    def build_input_fst(self, tokens: List[str]) -> pynini.Fst:
        """
        将词token列表转换为词级FST

        Args:
            tokens: 词token列表

        Returns:
            词级FST
        """
        if not tokens:
            # 空输入，返回epsilon
            fst = pynini.Fst()
            s = fst.add_state()
            fst.set_start(s)
            fst.set_final(s)
            fst.set_input_symbols(self.sym)
            fst.set_output_symbols(self.sym)
            return fst

        # 手动构建FST
        fst = pynini.Fst()
        fst.set_input_symbols(self.sym)
        fst.set_output_symbols(self.sym)

        # 创建状态链
        states = [fst.add_state() for _ in range(len(tokens) + 1)]
        fst.set_start(states[0])
        fst.set_final(states[-1])

        # 为每个token添加arc
        # 注意：如果token不在SymbolTable中，应该在tokenize()阶段就拆分为字符
        # 这里只是构建FST，不进行拆分
        for i, token in enumerate(tokens):
            token_id = self.sym.find(token)
            if token_id == -1:
                # 未在SymbolTable中，这不应该发生（应该在tokenize()阶段处理）
                # 但为了健壮性，我们记录警告并跳过这个token
                import logging

                logger = logging.getLogger("fst_time")
                logger.warning(
                    f"Token '{token}' not in SymbolTable, skipping. Should be split into characters in tokenize()"
                )
                continue

            # 添加arc: state[i] -> state[i+1], label=token
            arc = pynini.Arc(
                token_id, token_id, pynini.Weight.one(fst.weight_type()), states[i + 1]
            )
            fst.add_arc(states[i], arc)

        return fst

    def process_text(self, text: str) -> pynini.Fst:
        """
        处理文本：分词 + 构建FST

        Args:
            text: 输入文本

        Returns:
            词级FST
        """
        tokens = self.tokenize(text)
        return self.build_input_fst(tokens)

    def get_stats(self) -> dict:
        """获取统计信息"""
        return self.stats.copy()

    def reset_stats(self):
        """重置统计信息"""
        self.stats = {"total_words": 0, "unknown_words": 0, "char_level_fallback": 0}
        self.unknown_chars = []  # 重置未知字符列表
    
    def get_unknown_chars(self) -> List[str]:
        """获取未知字符列表（按出现顺序）"""
        return list(self.unknown_chars)


# 测试代码
if __name__ == "__main__":
    # 测试分词器
    print("=" * 80)
    print("测试EnglishWordTokenizer")
    print("=" * 80)
    print()

    try:
        tokenizer = EnglishWordTokenizer()

        # 测试用例
        test_cases = [
            "tomorrow",
            "next monday",
            "remind me at 3:30",
            "what is the time",
            "schedule meeting for friday",
        ]

        print("测试分词:")
        print("-" * 80)
        for text in test_cases:
            tokens = tokenizer.tokenize(text)
            char_count = len(text)
            token_count = len(tokens)
            reduction = (char_count - token_count) / char_count * 100

            print(f'文本: "{text}"')
            print(f"  字符数: {char_count}")
            print(f"  Token数: {token_count}")
            print(f"  减少: {reduction:.1f}%")
            print(f"  Tokens: {tokens}")
            print()

        # 测试FST构建
        print("测试FST构建:")
        print("-" * 80)
        text = "next monday"
        tokens = tokenizer.tokenize(text)
        fst = tokenizer.build_input_fst(tokens)

        print(f'文本: "{text}"')
        print(f"Tokens: {tokens}")
        print(f"FST状态数: {fst.num_states()}")
        print(f"期望状态数: {len(tokens) + 1}")
        print(f'匹配: {"✓" if fst.num_states() == len(tokens) + 1 else "✗"}')
        print()

        # 统计信息
        print("统计信息:")
        print("-" * 80)
        stats = tokenizer.get_stats()
        for key, value in stats.items():
            print(f"  {key}: {value}")

    except Exception as e:
        print(f"错误: {e}")
        import traceback

        traceback.print_exc()
