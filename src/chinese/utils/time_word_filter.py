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
时间词歧义过滤工具

支持过滤"X点"等时间词的非时间语义，包括：
1. 列举要点类：再说两点、还有三点
2. "一点"副词类：快一点、简单一点
3. "一点"否定类：一点也不、一点都不
"""

import os
import re
from typing import Set, Optional
from ...core.logger import get_logger


class TimeWordFilter:
    """时间词歧义过滤器（统一框架）"""

    def __init__(self, config_path: str = None):
        """
        初始化过滤器

        Args:
            config_path: 配置文件路径，默认使用内置配置
        """
        self.logger = get_logger(__name__)
        if config_path is None:
            config_path = os.path.join(
                os.path.dirname(__file__), "../data/filter/time_word_filter.txt"
            )

        # 通用"X点"过滤规则
        self.enumeration_prefixes: Set[str] = set()

        # "一点"专属过滤规则
        self.yidian_prefixes: Set[str] = set()
        self.yidian_suffixes: Set[str] = set()

        self._load_config(config_path)

    def _load_config(self, config_path: str):
        """加载配置文件"""
        if not os.path.exists(config_path):
            self.logger.warning(f"时间词过滤配置文件不存在: {config_path}")
            return

        current_section = None

        with open(config_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()

                # 跳过空行和注释
                if not line or line.startswith("#"):
                    continue

                # 检查分节标记
                if line == "[ENUMERATION_PREFIX]":
                    current_section = "ENUMERATION_PREFIX"
                    continue
                elif line == "[YIDIAN_PREFIX]":
                    current_section = "YIDIAN_PREFIX"
                    continue
                elif line == "[YIDIAN_SUFFIX]":
                    current_section = "YIDIAN_SUFFIX"
                    continue

                # 添加到相应的集合
                if current_section == "ENUMERATION_PREFIX":
                    self.enumeration_prefixes.add(line)
                elif current_section == "YIDIAN_PREFIX":
                    self.yidian_prefixes.add(line)
                elif current_section == "YIDIAN_SUFFIX":
                    self.yidian_suffixes.add(line)

    def should_filter_dian(  # noqa: C901
        self, query: str, dian_index: int, hour_value: str
    ) -> bool:
        """
        判断query中指定位置的"X点"是否应该被过滤

        Args:
            query: 原始查询文本
            dian_index: "点"字在query中的索引
            hour_value: 小时值（"1"、"2"、"3"等）

        Returns:
            bool: True表示应该过滤（非时间语义），False表示保留（时间语义）
        """
        # 规则1：检查列举要点类前缀（适用所有"X点"）
        # 例如："再说两点"、"还有三点"
        for prefix in self.enumeration_prefixes:
            # 找到"数字+点"的起始位置
            # 需要找到数字的位置（可能是中文数字或阿拉伯数字）
            num_start = self._find_number_start(query, dian_index)
            if num_start is None:
                continue

            prefix_start = num_start - len(prefix)
            if prefix_start >= 0:
                if query[prefix_start:num_start] == prefix:
                    return True  # 匹配到列举前缀，应该过滤

        # 规则2：针对"一点"的特殊检查
        if hour_value == "1":
            # 2a. 检查副词前缀（仅"一点"）
            # 例如："快一点"、"简单一点"
            yidian_start = dian_index - 1  # "一"的位置
            for prefix in self.yidian_prefixes:
                prefix_start = yidian_start - len(prefix)
                if prefix_start >= 0:
                    if query[prefix_start:yidian_start] == prefix:
                        return True  # 匹配到副词前缀，应该过滤

            # 2b. 检查否定后缀（仅"一点"）
            # 例如："一点也不"、"一点都不"
            yidian_end = dian_index + 1  # "点"之后
            for suffix in self.yidian_suffixes:
                suffix_end = yidian_end + len(suffix)
                if suffix_end <= len(query):
                    if query[yidian_end:suffix_end] == suffix:
                        return True  # 匹配到否定后缀，应该过滤

        return False  # 没有匹配到任何过滤规则，保留时间语义

    def _find_number_start(self, query: str, dian_index: int) -> Optional[int]:
        """
        找到"点"字前面的数字起始位置

        Args:
            query: 原始查询文本
            dian_index: "点"字的索引

        Returns:
            数字的起始索引，如果找不到返回None
        """
        # 中文数字（包括常用的数字表示）
        cn_digits = "零一二三四五六七八九十两"  # 添加"两"
        # 阿拉伯数字
        ar_digits = "0123456789"

        # 从"点"字往前找，找到数字的起始位置
        i = dian_index - 1
        num_end = -1

        # 跳过可能的空格
        while i >= 0 and query[i] == " ":
            i -= 1

        # 先找到数字的结束位置（紧邻"点"的位置）
        if i >= 0 and (query[i] in cn_digits or query[i] in ar_digits):
            num_end = i
        else:
            return None

        # 继续往前找数字的起始位置
        num_start = num_end
        i = num_end - 1
        while i >= 0:
            if query[i] in cn_digits or query[i] in ar_digits:
                num_start = i
                i -= 1
            else:
                break

        return num_start

    def get_stats(self) -> dict:
        """获取过滤器统计信息"""
        return {
            "enumeration_prefix_count": len(self.enumeration_prefixes),
            "yidian_prefix_count": len(self.yidian_prefixes),
            "yidian_suffix_count": len(self.yidian_suffixes),
            "total_patterns": (
                len(self.enumeration_prefixes)
                + len(self.yidian_prefixes)
                + len(self.yidian_suffixes)
            ),
        }


# 全局单例
_filter_instance = None


def get_time_word_filter() -> TimeWordFilter:
    """获取时间词过滤器单例"""
    global _filter_instance
    if _filter_instance is None:
        _filter_instance = TimeWordFilter()
    return _filter_instance
