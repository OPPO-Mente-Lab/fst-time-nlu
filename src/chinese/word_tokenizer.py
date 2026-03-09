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

# -*- coding: utf-8 -*-
"""中文词级分词器。

策略：
- 中文字符维持单字粒度；
- 数字、英文及其它非中文片段复用英文词级逻辑，组成词级 token；
- 长数字使用占位符以避免符号表膨胀。
"""

from __future__ import annotations

import unicodedata
from typing import List, Optional

import pynini

from .global_symbol_table import get_symbol_table


class ChineseWordTokenizer:
    def __init__(self, long_number_threshold: int = 6):
        self.sym = get_symbol_table()
        self.long_number_threshold = long_number_threshold
        self.long_number_token = "__long_number__"
        if self.sym.find(self.long_number_token) == -1:
            self.sym.add_symbol(self.long_number_token)

        # 特殊token：用于标记不在SymbolTable中的字符
        self.unknown_char_token = "__unknown_char__"
        if self.sym.find(self.unknown_char_token) == -1:
            self.sym.add_symbol(self.unknown_char_token)

        # 维护未知字符列表（按出现顺序，用于输出时恢复）
        self.unknown_chars = []

        # 维护token到原始文本位置的映射（用于提取原始文本片段）
        # 格式：{token_index: (start_pos, end_pos, original_text)}
        self.token_positions = []

        self.stats = {
            "total_tokens": 0,
            "unknown_tokens": 0,
            "long_number_tokens": 0,
        }

    # ------------------------------------------------------------------
    # tokenization
    # ------------------------------------------------------------------
    @staticmethod
    def _is_chinese_char(ch: str) -> bool:
        code = ord(ch)
        return 0x4E00 <= code <= 0x9FFF or 0x3400 <= code <= 0x4DBF or 0x20000 <= code <= 0x2A6DF

    @staticmethod
    def _is_english_letter(ch: str) -> bool:
        return ("A" <= ch <= "Z") or ("a" <= ch <= "z")

    @staticmethod
    def _is_cn_number_char(ch: str) -> bool:
        """判断是否为阿拉伯数字或常见中文数字字符"""
        return ch.isdigit() or ch in {
            "零",
            "〇",
            "○",
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
            "百",
            "千",
        }

    @classmethod
    def _should_skip_space(cls, prev_ch: str, next_ch: str) -> bool:
        # 只跳过“数字-单位”和“单位-数字”之间的空格
        if prev_ch == "" or next_ch == "":
            return False
        num_prev = cls._is_cn_number_char(prev_ch)
        num_next = cls._is_cn_number_char(next_ch)
        unit_prev = prev_ch in {"年", "月", "日", "号"}
        unit_next = next_ch in {"年", "月", "日", "号"}
        return (num_prev and unit_next) or (unit_prev and num_next)

    @classmethod
    def simple_tokenize(cls, text: str) -> List[str]:  # noqa: C901
        tokens: List[str] = []
        i = 0
        length = len(text)
        while i < length:
            ch = text[i]
            if ch.isspace():
                prev_ch = text[i - 1] if i > 0 else ""
                # 找到下一个非空格字符
                j = i + 1
                while j < length and text[j].isspace():
                    j += 1
                next_ch = text[j] if j < length else ""
                if cls._should_skip_space(prev_ch, next_ch):
                    # 跳过所有连续空格
                    i = j
                    continue
                tokens.append(" ")
                i += 1
                continue
            if cls._is_chinese_char(ch):
                tokens.append(ch)
                i += 1
                continue
            if ch.isdigit():
                j = i + 1
                while j < length and text[j].isdigit():
                    j += 1
                if j < length and text[j] == "." and (j + 1) < length and text[j + 1].isdigit():
                    k = j + 1
                    while k < length and text[k].isdigit():
                        k += 1
                    tokens.append(text[i:k])
                    i = k
                    continue
                # 非小数：逐位作为独立token，便于与现有数值FST匹配
                while i < j:
                    tokens.append(text[i])
                    i += 1
                continue
            if cls._is_english_letter(ch):
                j = i + 1
                while j < length:
                    cj = text[j]
                    if cls._is_english_letter(cj) or cj.isdigit() or cj in {"'", "-", "_"}:
                        j += 1
                    else:
                        break
                tokens.append(text[i:j].lower())
                i = j
                continue
            # 其它字符（标点、符号等）直接作为独立token
            tokens.append(ch)
            i += 1
        return tokens

    def tokenize(self, text: str) -> List[str]:
        tokens: List[str] = []
        # 清空未知字符列表（每次tokenize时重新开始）
        self.unknown_chars = []
        # 清空token位置映射
        self.token_positions = []

        original_text = text.strip()
        current_pos = 0  # 当前在原始文本中的位置

        for token in self.simple_tokenize(original_text):
            if token == "":
                continue
            if token == " ":
                # 查找空格在原始文本中的位置
                space_pos = original_text.find(" ", current_pos)
                if space_pos != -1:
                    self.token_positions.append((space_pos, space_pos + 1, " "))
                    current_pos = space_pos + 1
                tokens.append(" ")
                continue

            # 查找token在原始文本中的位置
            token_start = original_text.find(token, current_pos)
            if token_start == -1:
                # 如果找不到，尝试不区分大小写查找（用于英文单词）
                token_lower = token.lower()
                token_start = original_text.lower().find(token_lower, current_pos)

            normalized = token
            if self._looks_like_number(token):
                digits_only = token.replace(".", "")
                if len(digits_only) >= self.long_number_threshold:
                    if token_start != -1:
                        token_end = token_start + len(token)
                        self.token_positions.append((token_start, token_end, token))
                        current_pos = token_end
                    tokens.append(self.long_number_token)
                    self.stats["long_number_tokens"] += 1
                    self.stats["total_tokens"] += 1
                    continue
            if self.sym.find(normalized) == -1:
                self.stats["unknown_tokens"] += 1
                # 尝试拆分为字符，看是否有部分字符在符号表中
                fallback_tokens = []
                char_pos = token_start if token_start != -1 else current_pos
                for ch in normalized:
                    if self.sym.find(ch) != -1:
                        # 字符在符号表中，直接添加
                        if char_pos < len(original_text):
                            self.token_positions.append((char_pos, char_pos + 1, ch))
                            char_pos += 1
                        fallback_tokens.append(ch)
                        self.stats["total_tokens"] += 1
                    else:
                        # 字符不在符号表中，使用unknown_char_token占位符
                        # 记录原始字符，以便后续恢复
                        if char_pos < len(original_text):
                            self.token_positions.append((char_pos, char_pos + 1, ch))
                            char_pos += 1
                        self.unknown_chars.append(ch)
                        fallback_tokens.append(self.unknown_char_token)
                        self.stats["total_tokens"] += 1
                if fallback_tokens:
                    tokens.extend(fallback_tokens)
                if token_start != -1:
                    current_pos = token_start + len(token)
                continue

            if token_start != -1:
                token_end = token_start + len(token)
                self.token_positions.append((token_start, token_end, token))
                current_pos = token_end
            tokens.append(normalized)
            self.stats["total_tokens"] += 1
        return tokens

    def _looks_like_number(self, token: str) -> bool:
        if token.isdigit():
            return True
        if token.count(".") == 1:
            left, right = token.split(".", 1)
            return left.isdigit() and right.isdigit()
        return False

    def _ensure_symbol(self, token: str) -> None:
        # 禁用自动扩展全局符号表，仅统计未知token
        return

    # ------------------------------------------------------------------
    def build_input_fst(self, tokens: List[str]) -> pynini.Fst:
        fst = pynini.Fst()
        fst.set_input_symbols(self.sym)
        fst.set_output_symbols(self.sym)
        states = [fst.add_state() for _ in range(len(tokens) + 1)]
        fst.set_start(states[0])
        fst.set_final(states[-1])

        for idx, token in enumerate(tokens):
            token_id = self.sym.find(token)
            if token_id == -1:
                # 未在SymbolTable中，这不应该发生（应该在tokenize()阶段处理）
                # 但为了健壮性，我们记录警告并跳过这个token
                import logging

                logger = logging.getLogger("fst_time")
                logger.warning(
                    f"Token '{token}' not in SymbolTable, skipping. Should be handled in tokenize()"
                )
                continue
            arc = pynini.Arc(
                token_id,
                token_id,
                pynini.Weight.one(fst.weight_type()),
                states[idx + 1],
            )
            fst.add_arc(states[idx], arc)
        return fst

    def process_text(self, text: str) -> pynini.Fst:
        tokens = self.tokenize(text)
        return self.build_input_fst(tokens)

    def get_stats(self) -> dict:
        return dict(self.stats)

    def reset_stats(self) -> None:
        for key in self.stats:
            self.stats[key] = 0
        self.unknown_chars = []  # 重置未知字符列表
        self.token_positions = []  # 重置token位置映射

    def get_unknown_chars(self) -> List[str]:
        """获取未知字符列表（按出现顺序）"""
        return list(self.unknown_chars)

    def get_token_positions(self) -> List[tuple]:
        """获取token位置映射列表（按token顺序）

        Returns:
            List[tuple]: [(start_pos, end_pos, original_text), ...]
        """
        return list(self.token_positions)
