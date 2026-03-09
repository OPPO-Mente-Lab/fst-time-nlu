# Copyright (c) 2021, NVIDIA CORPORATION.  All rights reserved.
# Copyright (c) 2024, WENET COMMUNITY.  Xingchen Song (sxc19@tsinghua.org.cn).
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

"""
工具函数模块

提供各种辅助功能，包括路径处理、文件操作等。
"""

import os
import inspect
from typing import Union
import inflect
import pynini
import string
from pynini.lib import byte, pynutil, utf8

_inflect = inflect.engine()
INPUT_CASED = "cased"
INPUT_LOWER_CASED = "lower_cased"
NEMO_SPACE = " "
NEMO_WHITE_SPACE = pynini.union(" ", "\t", "\n", "\r", "\u00a0").optimize()
NEMO_CHAR = utf8.VALID_UTF8_CHAR
NEMO_SIGMA = pynini.closure(NEMO_CHAR)
NEMO_DIGIT = byte.DIGIT
NEMO_LOWER = pynini.union(*string.ascii_lowercase).optimize()
NEMO_UPPER = pynini.union(*string.ascii_uppercase).optimize()
NEMO_ALPHA = pynini.union(NEMO_LOWER, NEMO_UPPER).optimize()
NEMO_ALNUM = pynini.union(NEMO_DIGIT, NEMO_ALPHA).optimize()
TO_LOWER = pynini.union(
    *[pynini.cross(x, y) for x, y in zip(string.ascii_uppercase, string.ascii_lowercase)]
).optimize()
NEMO_NON_BREAKING_SPACE = "\u00a0"
MINUS = pynini.union("minus", "Minus").optimize()

delete_space = pynutil.delete(pynini.closure(NEMO_WHITE_SPACE))
delete_zero_or_one_space = pynutil.delete(pynini.closure(NEMO_WHITE_SPACE, 0, 1))
insert_space = pynutil.insert(" ")
delete_extra_space = pynini.cross(pynini.closure(NEMO_WHITE_SPACE, 1), " ")


def capitalized_input_graph(
    graph: "pynini.FstLike",
    original_graph_weight: float = None,
    capitalized_graph_weight: float = None,
) -> "pynini.FstLike":
    """
    Allow graph input to be capitalized, e.g. for ITN)

    Args:
        graph: FstGraph
        original_graph_weight: weight to add to the original `graph`
        capitalized_graph_weight: weight to add to the capitalized graph
    """
    capitalized_graph = pynini.compose(TO_LOWER + NEMO_SIGMA, graph).optimize()

    if original_graph_weight is not None:
        graph = pynutil.add_weight(graph, weight=original_graph_weight)

    if capitalized_graph_weight is not None:
        capitalized_graph = pynutil.add_weight(capitalized_graph, weight=capitalized_graph_weight)

    graph |= capitalized_graph
    return graph


def num_to_word(x: Union[str, int]):
    """
    converts integer to spoken representation

    Args
        x: integer

    Returns: spoken representation
    """
    if isinstance(x, int):
        x = str(x)
        x = _inflect.number_to_words(str(x)).replace("-", " ").replace(",", "")
    return x


def create_word_boundary():
    """
    创建词边界FST
    匹配非字母字符或字符串结尾

    Returns:
        pynini.Fst: 词边界FST
    """
    # 使用更简单的方法：匹配空格或字符串结尾
    space = pynini.accep(" ")
    string_end = pynini.accep("")

    # 词边界 = 空格 或 字符串结尾
    word_boundary = space | string_end

    return word_boundary.optimize()


def get_abs_path(rel_path: str) -> str:
    """
    基于调用文件的位置获取绝对路径。

    Args:
        rel_path: 相对于调用文件的路径

    Returns:
        str: 绝对路径

    Raises:
        ValueError: 如果无法获取调用者信息
        FileNotFoundError: 如果相对路径不存在

    Example:
        >>> # 在 /path/to/module.py 中调用
        >>> abs_path = get_abs_path("data/config.json")
        >>> # 返回: /path/to/data/config.json
    """
    try:
        # 获取调用者的文件路径
        caller_frame = inspect.currentframe().f_back
        if caller_frame is None:
            raise ValueError("无法获取调用者信息")

        caller_file = caller_frame.f_globals["__file__"]
        caller_dir = os.path.dirname(os.path.abspath(caller_file))
        abs_path = os.path.join(caller_dir, rel_path)

        return abs_path

    except (KeyError, AttributeError) as e:
        raise ValueError(f"无法获取调用者文件信息: {e}")


def ensure_dir_exists(dir_path: str) -> None:
    """
    确保目录存在，如果不存在则创建。

    Args:
        dir_path: 目录路径

    Raises:
        OSError: 如果无法创建目录
    """
    os.makedirs(dir_path, exist_ok=True)


def is_valid_path(path: str) -> bool:
    """
    检查路径是否有效。

    Args:
        path: 要检查的路径

    Returns:
        bool: 如果路径有效返回True，否则返回False
    """
    try:
        # 尝试规范化路径
        os.path.normpath(path)
        return True
    except (TypeError, ValueError):
        return False


def get_file_extension(file_path: str) -> str:
    """
    获取文件扩展名。

    Args:
        file_path: 文件路径

    Returns:
        str: 文件扩展名（包含点号），如果没有扩展名则返回空字符串
    """
    _, ext = os.path.splitext(file_path)
    return ext


def safe_filename(filename: str) -> str:
    """
    生成安全的文件名，移除或替换不安全的字符。

    Args:
        filename: 原始文件名

    Returns:
        str: 安全的文件名
    """
    # 定义不安全的字符
    unsafe_chars = '<>:"/\\|?*'

    # 替换不安全的字符
    safe_name = filename
    for char in unsafe_chars:
        safe_name = safe_name.replace(char, "_")

    # 移除前后空格和点号
    safe_name = safe_name.strip(" .")

    # 确保文件名不为空
    if not safe_name:
        safe_name = "unnamed"

    return safe_name


def convert_space(fst) -> "pynini.FstLike":
    """
    Converts space to nonbreaking space.
    Used only in tagger grammars for transducing token values within quotes, e.g. name: "hello kitty"
    This is making transducer significantly slower, so only use when there could be potential spaces within quotes, otherwise leave it.

    Args:
        fst: input fst

    Returns output fst where breaking spaces are converted to non breaking spaces
    """
    return fst @ pynini.cdrewrite(
        pynini.cross(NEMO_SPACE, NEMO_NON_BREAKING_SPACE), "", "", NEMO_SIGMA
    )


class GraphFst:
    """
    Base class for all grammar fsts.

    Args:
        name: name of grammar class
        kind: either 'classify' or 'verbalize'
        deterministic: if True will provide a single transduction option,
            for False multiple transduction are generated (used for audio-based normalization)
    """

    def __init__(self, name: str, kind: str, deterministic: bool = True):
        self.name = name
        self.kind = kind
        self._fst = None
        self.deterministic = deterministic

    def far_exist(self) -> bool:
        """
        Returns true if FAR can be loaded
        """
        return self.far_path.exists()

    @property
    def fst(self) -> "pynini.FstLike":
        return self._fst

    @fst.setter
    def fst(self, fst):
        self._fst = fst

    def add_tokens(self, fst) -> "pynini.FstLike":
        """
        Wraps class name around to given fst

        Args:
            fst: input fst

        Returns:
            Fst: fst
        """
        return pynutil.insert(f"{self.name} {{ ") + fst + pynutil.insert(" }")

    def delete_tokens(self, fst) -> "pynini.FstLike":
        """
        Deletes class name wrap around output of given fst

        Args:
            fst: input fst

        Returns:
            Fst: fst
        """
        res = (
            pynutil.delete(f"{self.name}")
            + delete_space
            + pynutil.delete("{")
            + delete_space
            + fst
            + delete_space
            + pynutil.delete("}")
        )
        return res @ pynini.cdrewrite(pynini.cross("\u00a0", " "), "", "", NEMO_SIGMA)
