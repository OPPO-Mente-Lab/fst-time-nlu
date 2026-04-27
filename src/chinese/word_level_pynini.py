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
"""中文词级Pynini包装。"""

from __future__ import annotations

import pynini as _original_pynini
from pynini.lib import pynutil as _original_pynutil

from .global_symbol_table import get_symbol_table
from .word_level_utils import (
    word_accep,
    word_cross,
    word_delete,
    word_insert,
    word_delete_space,
    word_delete_extra_space,
    word_string_file,
)

__all__ = [
    "string_file",
    "accep",
    "cross",
    "pynutil",
    "get_symbol_table",
    "word_string_file",
    "word_accep",
    "word_cross",
    "word_delete",
    "word_insert",
    "word_delete_space",
    "word_delete_extra_space",
    "union",
    "compose",
    "closure",
    "concat",
    "difference",
    "invert",
    "optimize",
    "cdrewrite",
    "string_map",
    "Fst",
    "Arc",
    "Weight",
    "SymbolTable",
]


def string_file(filename: str, **_kwargs) -> _original_pynini.Fst:
    return word_string_file(filename)


def accep(text: str, weight=None, **_kwargs) -> _original_pynini.Fst:
    return word_accep(text, weight)


def cross(input_str, output_str, **_kwargs) -> _original_pynini.Fst:
    if isinstance(input_str, (_original_pynini.Fst,)) or isinstance(
        output_str, (_original_pynini.Fst,)
    ):
        return _original_pynini.cross(input_str, output_str, **_kwargs)
    return word_cross(input_str, output_str)


class WordLevelPynutil:
    @staticmethod
    def delete(text, **_kwargs):
        if isinstance(text, (_original_pynini.Fst,)):
            return _original_pynutil.delete(text, **_kwargs)
        return word_delete(text)

    @staticmethod
    def insert(text, **_kwargs):
        return word_insert(text)

    @staticmethod
    def add_weight(fst, weight):
        return _original_pynutil.add_weight(fst, weight)

    def __getattr__(self, name: str):
        return getattr(_original_pynutil, name)


pynutil = WordLevelPynutil()


def union(*args):
    converted = []
    for arg in args:
        if isinstance(arg, str):
            converted.append(accep(arg))
        else:
            converted.append(arg)
    return _original_pynini.union(*converted)


compose = _original_pynini.compose
closure = _original_pynini.closure
concat = _original_pynini.concat
difference = _original_pynini.difference
invert = _original_pynini.invert
optimize = _original_pynini.optimize
string_map = _original_pynini.string_map
cdrewrite = _original_pynini.cdrewrite
Fst = _original_pynini.Fst
Arc = _original_pynini.Arc
Weight = _original_pynini.Weight
SymbolTable = _original_pynini.SymbolTable
