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
FST Time NLU - 基于有限状态转换器的时间自然语言理解库

这个库提供了中文时间表达式的识别、归一化和解析功能。
主要包含以下核心组件：

Classes:
    FstTimeExtractor: 主要的时间提取器类

Usage:
    from fst_time_nlu import FstTimeExtractor

    extractor = FstTimeExtractor()
    results = extractor.extract("明天下午三点")
"""

# 主要导出类
from .chinese.fst_time_extractor import FstTimeExtractor

# 版本信息
__version__ = "1.0.0"
__author__ = "Ming Yu (yuming@oppo.com)"

# 主要API
__all__ = [
    "FstTimeExtractor",
]
