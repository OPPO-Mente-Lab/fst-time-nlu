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

from abc import ABC, abstractmethod
from datetime import datetime


class BaseMerger(ABC):
    """
    时间表达式合并器抽象基类

    定义了所有合并器的公共接口和属性，确保统一的合并逻辑处理方式。
    """

    def __init__(self, parsers):
        """
        初始化合并器

        Args:
            parsers (dict): 解析器字典，包含各种时间解析器
        """
        self.parsers = parsers

        # 中文数字映射
        self.chinese_num_map = {
            "一": 1,
            "二": 2,
            "三": 3,
            "四": 4,
            "五": 5,
            "六": 6,
            "七": 7,
            "八": 8,
            "九": 9,
            "十": 10,
            "十一": 11,
            "十二": 12,
            "十三": 13,
            "十四": 14,
            "十五": 15,
            "十六": 16,
            "十七": 17,
            "十八": 18,
            "十九": 19,
            "二十": 20,
        }

    @abstractmethod
    def try_merge(self, i, tokens, base_time):
        """
        尝试合并tokens中的时间表达式

        Args:
            i (int): 当前token索引
            tokens (list): token列表
            base_time (datetime): 基准时间

        Returns:
            tuple: (合并结果列表, 跳跃的token数量) 或 None
        """
        pass
