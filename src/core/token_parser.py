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
标记解析器模块

提供标记解析功能，用于解析FST输出的标记化文本。
包含Token类和TokenParser类，支持结构化标记的解析和格式化。
"""

import string
from typing import List, Dict, Any, Optional


# 结束符常量
EOS = "<EOS>"


class Token:
    """
    标记类，表示一个解析后的标记。

    每个标记包含名称、成员属性和可选的顺序信息。
    支持按指定顺序格式化输出。
    """

    def __init__(self, name: str) -> None:
        """
        初始化标记。

        Args:
            name: 标记名称
        """
        self.name = name
        self.order: List[str] = []
        self.members: Dict[str, str] = {}

    def append(self, key: str, value: str) -> None:
        """
        添加键值对到标记中。

        Args:
            key: 键名
            value: 值
        """
        self.order.append(key)
        self.members[key] = value

    def string(self, orders: Optional[Dict[str, List[str]]] = None) -> str:
        """
        将标记格式化为字符串。

        Args:
            orders: 可选的排序字典，指定不同标记类型的属性顺序

        Returns:
            str: 格式化后的标记字符串
        """
        output = self.name + " {"

        # 如果指定了排序且当前标记不在保持顺序模式
        if orders and self.name in orders:
            if (
                "preserve_order" not in self.members.keys()
                or self.members["preserve_order"] != "true"
            ):
                self.order = orders[self.name]

        # 按顺序输出属性
        for key in self.order:
            if key not in self.members:
                continue
            output += f' {key}: "{self.members[key]}"'

        return output + " }"

    def to_dict(self) -> Dict[str, Any]:
        """
        将标记转换为字典。

        Returns:
            Dict[str, Any]: 包含标记信息的字典
        """
        return {"name": self.name, **self.members}


class TokenParser:
    """
    标记解析器，用于解析FST输出的标记化文本。

    支持解析包含标记类型和属性的结构化文本，
    将文本转换为Token对象列表。
    """

    def __init__(self) -> None:
        """初始化解析器。"""
        self.index: int = 0
        self.text: str = ""
        self.char: str = ""
        self.tokens: List[Token] = []

    def load(self, input_text: str) -> None:
        """
        加载要解析的输入文本。

        Args:
            input_text: 要解析的输入文本

        Raises:
            ValueError: 如果输入文本为空
        """
        if not input_text or len(input_text) == 0:
            raise ValueError("输入文本不能为空")

        self.index = 0
        self.text = input_text
        self.char = input_text[0]
        self.tokens = []

    def read(self) -> bool:
        """
        读取下一个字符。

        Returns:
            bool: 如果成功读取返回True，否则返回False
        """
        if self.index < len(self.text) - 1:
            self.index += 1
            self.char = self.text[self.index]
            return True
        self.char = EOS
        return False

    def parse_ws(self) -> bool:
        """
        解析空白字符。

        Returns:
            bool: 如果未到达结束符返回True，否则返回False
        """
        not_eos = self.char != EOS
        while not_eos and self.char == " ":
            not_eos = self.read()
        return not_eos

    def parse_char(self, expected_char: str) -> bool:
        """
        解析指定字符。

        Args:
            expected_char: 期望的字符

        Returns:
            bool: 如果匹配返回True，否则返回False
        """
        if self.char == expected_char:
            self.read()
            return True
        return False

    def parse_chars(self, expected_chars: str) -> bool:
        """
        按顺序解析字符序列。

        Args:
            expected_chars: 期望的字符序列

        Returns:
            bool: 如果完全匹配返回True，否则返回False
        """
        # 修复：按顺序匹配字符序列，而不是匹配任意一个
        for expected_char in expected_chars:
            if not self.parse_char(expected_char):
                return False
        return True

    def parse_key(self) -> str:
        """
        解析键名。

        键名由字母、数字和下划线组成。

        Returns:
            str: 解析出的键名

        Raises:
            ValueError: 如果遇到无效字符或到达结束符
        """
        if self.char == EOS:
            raise ValueError("意外到达文本结束")
        if self.char in string.whitespace:
            raise ValueError(f"键名不能以空白字符开始: '{self.char}'")

        key = ""
        valid_chars = string.ascii_letters + "_" + string.digits

        while self.char in valid_chars:
            key += self.char
            if not self.read():
                break

        if not key:
            raise ValueError(f"无效的键名字符: '{self.char}'")

        return key

    def parse_value(self) -> str:  # noqa: C901
        """
        解析值。

        支持带引号的字符串值和不带引号的数字值。

        Returns:
            str: 解析出的值

        Raises:
            ValueError: 如果遇到无效字符或到达结束符
        """
        if self.char == EOS:
            raise ValueError("意外到达文本结束")

        value = ""

        # 检查是否是数字值（没有引号的情况）
        if self.char in string.digits + "-":
            while self.char in string.digits + "-":
                value += self.char
                if not self.read():
                    break
            return value

        # 处理带引号的值
        if self.char != '"':
            raise ValueError(f"值必须以引号开始: '{self.char}'")

        # 跳过开始引号
        self.read()

        escape = False
        while self.char != '"':
            if self.char == EOS:
                raise ValueError("未闭合的引号")

            if escape:
                escape = False
                value += self.char
            else:
                if self.char == "\\":
                    escape = True
                else:
                    value += self.char

            if not self.read():
                break

        # 消费结束引号
        if self.char == '"':
            self.read()

        # 自动trim前后空格（但保留纯空格值）
        # 如果value全是空格，保留一个空格；否则trim前后空格
        if value and value.strip() == "":
            # 纯空格值：保留一个空格（词级FST中空格是有意义的token）
            value = " "
        else:
            # 普通值：trim前后空格
            value = value.strip()

        return value

    def parse(self, input_text: str) -> List[Token]:
        """
        解析输入文本并返回标记列表。

        Args:
            input_text: 要解析的输入文本

        Returns:
            List[Token]: 解析出的标记列表

        Raises:
            ValueError: 如果解析过程中遇到错误
        """
        try:
            self.load(input_text)

            while self.parse_ws():
                # 解析标记名称
                name = self.parse_key()

                # 解析开始括号
                if not self.parse_chars(" { "):
                    raise ValueError(f"期望 '{{' 但找到: '{self.char}'")

                token = Token(name)

                # 解析属性
                while self.parse_ws():
                    if self.char == "}":
                        self.parse_char("}")
                        break

                    # 解析键
                    key = self.parse_key()

                    # 解析冒号和空格（不包含引号）
                    if not self.parse_chars(": "):
                        raise ValueError(f"期望 ': ' 但找到: '{self.char}'")

                    # 现在当前字符应该是引号 "
                    # 解析值（parse_value会处理引号）
                    value = self.parse_value()

                    # parse_value已经消费了结束引号，不需要再次解析

                    token.append(key, value)

                self.tokens.append(token)

            return self.tokens

        except Exception as e:
            raise ValueError(f"解析错误在位置 {self.index}: {e}")
