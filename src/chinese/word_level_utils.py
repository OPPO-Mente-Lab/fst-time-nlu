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

# -*- coding: utf-8 -*-
"""中文词级FST构建工具函数。"""

from __future__ import annotations

import os
from typing import List

import pynini

from .global_symbol_table import get_symbol_table
from .word_tokenizer import ChineseWordTokenizer

_SYM = get_symbol_table()


def _tokens_from_text(text: str) -> List[str]:
    return ChineseWordTokenizer.simple_tokenize(text)


def _epsilon_fst() -> pynini.Fst:
    fst = pynini.Fst()
    state = fst.add_state()
    fst.set_start(state)
    fst.set_final(state)
    fst.set_input_symbols(_SYM)
    fst.set_output_symbols(_SYM)
    return fst


def word_accep(text: str, weight: pynini.Weight | None = None) -> pynini.Fst:
    tokens = _tokens_from_text(text)
    if not tokens:
        return _epsilon_fst()

    fst = pynini.Fst()
    fst.set_input_symbols(_SYM)
    fst.set_output_symbols(_SYM)

    states = [fst.add_state() for _ in range(len(tokens) + 1)]
    fst.set_start(states[0])
    fst.set_final(states[-1])

    for idx, token in enumerate(tokens):
        token_id = _SYM.find(token)
        if token_id == -1:
            token_id = _SYM.add_symbol(token)
        arc = pynini.Arc(token_id, token_id, pynini.Weight.one(fst.weight_type()), states[idx + 1])
        fst.add_arc(states[idx], arc)

    if weight is not None:
        fst = pynini.add_weight(fst, weight)
    return fst


def word_cross(input_str: str, output_str: str) -> pynini.Fst:
    in_tokens = _tokens_from_text(input_str)
    out_tokens = _tokens_from_text(output_str)
    max_len = max(len(in_tokens), len(out_tokens))

    fst = pynini.Fst()
    fst.set_input_symbols(_SYM)
    fst.set_output_symbols(_SYM)

    states = [fst.add_state() for _ in range(max_len + 1)]
    fst.set_start(states[0])
    fst.set_final(states[-1])

    for idx in range(max_len):
        in_token = in_tokens[idx] if idx < len(in_tokens) else ""
        out_token = out_tokens[idx] if idx < len(out_tokens) else ""
        in_id = _SYM.find(in_token) if in_token else 0
        if in_id == -1:
            in_id = _SYM.add_symbol(in_token)
        out_id = _SYM.find(out_token) if out_token else 0
        if out_id == -1:
            out_id = _SYM.add_symbol(out_token)
        arc = pynini.Arc(in_id, out_id, pynini.Weight.one(fst.weight_type()), states[idx + 1])
        fst.add_arc(states[idx], arc)

    return fst


def word_delete(text: str) -> pynini.Fst:
    tokens = _tokens_from_text(text)
    if not tokens:
        return _epsilon_fst()

    fst = pynini.Fst()
    fst.set_input_symbols(_SYM)
    fst.set_output_symbols(_SYM)

    states = [fst.add_state() for _ in range(len(tokens) + 1)]
    fst.set_start(states[0])
    fst.set_final(states[-1])

    for idx, token in enumerate(tokens):
        token_id = _SYM.find(token)
        if token_id == -1:
            token_id = _SYM.add_symbol(token)
        arc = pynini.Arc(token_id, 0, pynini.Weight.one(fst.weight_type()), states[idx + 1])
        fst.add_arc(states[idx], arc)

    return fst


def word_insert(text: str) -> pynini.Fst:
    tokens = _tokens_from_text(text)
    if not tokens:
        return _epsilon_fst()

    fst = pynini.Fst()
    fst.set_input_symbols(_SYM)
    fst.set_output_symbols(_SYM)

    states = [fst.add_state() for _ in range(len(tokens) + 1)]
    fst.set_start(states[0])
    fst.set_final(states[-1])

    for idx, token in enumerate(tokens):
        token_id = _SYM.find(token)
        if token_id == -1:
            token_id = _SYM.add_symbol(token)
        arc = pynini.Arc(0, token_id, pynini.Weight.one(fst.weight_type()), states[idx + 1])
        fst.add_arc(states[idx], arc)

    return fst


def word_delete_space() -> pynini.Fst:
    fst = pynini.Fst()
    fst.set_input_symbols(_SYM)
    fst.set_output_symbols(_SYM)
    state = fst.add_state()
    fst.set_start(state)
    fst.set_final(state)
    space_id = _SYM.find(" ")
    if space_id == -1:
        space_id = _SYM.add_symbol(" ")
    arc = pynini.Arc(space_id, 0, pynini.Weight.one(fst.weight_type()), state)
    fst.add_arc(state, arc)
    return fst


def word_delete_extra_space() -> pynini.Fst:
    fst = pynini.Fst()
    fst.set_input_symbols(_SYM)
    fst.set_output_symbols(_SYM)

    s0 = fst.add_state()
    s1 = fst.add_state()
    fst.set_start(s0)
    fst.set_final(s1)

    space_id = _SYM.find(" ")
    if space_id == -1:
        space_id = _SYM.add_symbol(" ")

    fst.add_arc(s0, pynini.Arc(space_id, space_id, pynini.Weight.one(fst.weight_type()), s1))
    fst.add_arc(s1, pynini.Arc(space_id, 0, pynini.Weight.one(fst.weight_type()), s1))
    return fst


def word_string_file(file_path: str) -> pynini.Fst:
    if not os.path.exists(file_path):
        return _epsilon_fst()

    fsts: List[pynini.Fst] = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) == 1:
                inp = parts[0]
                out = parts[0]
            else:
                inp = parts[0]
                out = parts[1]
            try:
                fst = word_cross(inp, out)
                fsts.append(fst)
            except ValueError:
                continue

    if not fsts:
        return _epsilon_fst()

    result = fsts[0]
    for fst in fsts[1:]:
        result = pynini.union(result, fst)
    return result.optimize()
