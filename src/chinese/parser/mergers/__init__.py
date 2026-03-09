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
时间表达式合并器模块

该模块包含各种专门的时间表达式合并器，用于处理不同类型的时间表达式合并逻辑。
每个合并器负责特定功能域的时间表达式处理，提高代码的可维护性和可测试性。
"""

from .base_merger import BaseMerger

__all__ = ["BaseMerger"]
