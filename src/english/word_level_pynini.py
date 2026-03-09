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
词级Pynini包装器

提供与原生pynini API兼容的词级版本，最小化代码修改。
通过monkey patching或显式导入，实现无缝迁移。

使用方式1：显式导入（推荐）
    from word_level_pynini import string_file, accep, delete, insert, cross

使用方式2：替换pynini模块（自动）
    import word_level_pynini as pynini
"""

import pynini as _original_pynini
from pynini.lib import pynutil as _original_pynutil
from .global_symbol_table import get_symbol_table  # Export for rules
from .word_level_utils import (
    word_accep,
    word_cross,
    word_delete,
    word_insert,
    word_string_file,
    word_delete_space,
    word_delete_extra_space,
)

# Export word_level_utils functions directly
word_string_file = word_string_file
word_accep = word_accep
word_cross = word_cross
word_delete = word_delete
word_insert = word_insert
word_delete_space = word_delete_space
word_delete_extra_space = word_delete_extra_space

# Export get_symbol_table so rules can use it
__all__ = [
    "string_file",
    "accep",
    "cross",
    "pynutil",
    "get_symbol_table",
    # Export word-level functions directly
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


# ============================================================================
# 核心替换函数
# ============================================================================


def string_file(filename, **kwargs):
    """
    词级版本的pynini.string_file

    自动使用全局SymbolTable，与原API兼容。
    """
    # 忽略其他参数（如token_type），因为我们固定使用全局sym
    return word_string_file(filename)


def accep(text, weight=None, **kwargs):
    """智能版本的accep：字符串用词级，FST直接返回"""

    return word_accep(text, weight)


def cross(input_str, output_str, **kwargs):
    """智能版本的cross：字符串用词级，FST用原版"""
    # 检查参数类型
    is_input_fst = isinstance(input_str, (_original_pynini.Fst,))
    is_output_fst = isinstance(output_str, (_original_pynini.Fst,))

    if is_input_fst or is_output_fst:
        # 任一参数是FST，使用原始pynini.cross
        return _original_pynini.cross(input_str, output_str, **kwargs)
    else:
        # 两个都是字符串，使用word_cross
        return word_cross(input_str, output_str)


# ============================================================================
# Pynutil包装
# ============================================================================


class WordLevelPynutil:
    """词级版本的pynutil"""

    @staticmethod
    def delete(text, **kwargs):
        """词级delete，支持字符串和FST"""
        # 如果text是FST，使用原始pynutil.delete
        if isinstance(text, (_original_pynini.Fst,)):
            return _original_pynutil.delete(text, **kwargs)
        # 否则使用词级delete
        return word_delete(text)

    @staticmethod
    def insert(text, **kwargs):
        """词级insert"""
        return word_insert(text)

    @staticmethod
    def add_weight(fst, weight):
        """保持原有功能"""
        return _original_pynutil.add_weight(fst, weight)

    # 保留其他pynutil函数（直接调用原版）
    def __getattr__(self, name):
        return getattr(_original_pynutil, name)


# 创建pynutil实例
pynutil = WordLevelPynutil()


# ============================================================================
# 保持所有其他pynini功能不变
# ============================================================================

# ============================================================================
# 包装union函数以支持词级字符串参数
# ============================================================================


def union(*args):
    """
    智能union：自动处理字符串和FST参数
    - 如果参数是字符串，先转换为词级FST（使用accep）
    - 如果参数是FST，直接使用
    """
    converted_args = []
    for arg in args:
        if isinstance(arg, str):
            # 字符串参数，转换为词级FST
            converted_args.append(accep(arg))
        else:
            # FST或其他类型，直接使用
            converted_args.append(arg)

    # 使用原始union
    return _original_pynini.union(*converted_args)


# 直接暴露其他原pynini功能
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


# ============================================================================
# 测试代码
# ============================================================================

if __name__ == "__main__":  # noqa: C901
    print("=" * 80)
    print("测试词级Pynini包装器")
    print("=" * 80)
    print()

    # 测试string_file
    print("1. 测试string_file:")
    try:
        fst = string_file("/home/oppoer/work/fst-time-nlu/src/english/data/date/months.tsv")
        print(f"   ✓ string_file: {fst.num_states()} states")
    except Exception as e:
        print(f"   ✗ 失败: {e}")

    # 测试accep
    print("\n2. 测试accep:")
    try:
        fst = accep("tomorrow")
        print(f'   ✓ accep("tomorrow"): {fst.num_states()} states')
    except Exception as e:
        print(f"   ✗ 失败: {e}")

    # 测试cross
    print("\n3. 测试cross:")
    try:
        fst = cross("tomorrow", "1")
        print(f'   ✓ cross("tomorrow", "1"): {fst.num_states()} states')
    except Exception as e:
        print(f"   ✗ 失败: {e}")

    # 测试pynutil.delete
    print("\n4. 测试pynutil.delete:")
    try:
        fst = pynutil.delete("the")
        print(f'   ✓ pynutil.delete("the"): {fst.num_states()} states')
    except Exception as e:
        print(f"   ✗ 失败: {e}")

    # 测试pynutil.insert
    print("\n5. 测试pynutil.insert:")
    try:
        fst = pynutil.insert("test")
        print(f'   ✓ pynutil.insert("test"): {fst.num_states()} states')
    except Exception as e:
        print(f"   ✗ 失败: {e}")

    # 测试union等原生功能
    print("\n6. 测试原生pynini功能:")
    try:
        fst1 = accep("hello")
        fst2 = accep("world")
        fst_union = union(fst1, fst2)
        print(f"   ✓ union: {fst_union.num_states()} states")
    except Exception as e:
        print(f"   ✗ 失败: {e}")

    print("\n✓ 所有测试完成")
