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

"""
中文时间处理核心模块

提供基于FST（有限状态转换器）的中文时间表达式识别、归一化和解析功能。
该模块包含文本处理器、标记解析器和工具函数。

主要组件:
- Processor: FST基础文本处理类，用于标记和标准化
- TokenParser: 标记解析器，用于解析FST输出
- 工具函数: 路径处理等辅助功能

作者: Ming Yu (yuming@oppo.com)
许可证: Apache License 2.0
"""

from .processor import Processor
from .token_parser import TokenParser, Token
from .utils import get_abs_path
from .logger import get_logger, setup_logging, auto_setup

__version__ = "1.0.0"
__author__ = "Ming Yu"
__email__ = "yuming@oppo.com"

__all__ = [
    "Processor",
    "TokenParser",
    "Token",
    "get_abs_path",
    "get_logger",
    "setup_logging",
    "auto_setup",
]
