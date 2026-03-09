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

import os
import time

from .normalizer import Normalizer
from .time_parser import TimeParser
from ..core.logger import get_logger


class FstTimeExtractor:
    """整合时间归一化和解析功能的提取器"""

    def __init__(self, cache_dir=None, overwrite_cache=False, include_source=True):
        """
        初始化时间提取器
        
        Args:
            cache_dir: FST缓存目录
            overwrite_cache: 是否覆盖现有缓存
            include_source: 是否在tag中添加source字段（默认True）
        """
        self.logger = get_logger(__name__)
        # 初始化归一化器
        if not cache_dir:
            cache_dir = os.path.dirname(__file__) + "/test/fst"
        self.normalizer = Normalizer(cache_dir=cache_dir, overwrite_cache=overwrite_cache,
                                     include_source=include_source)
        # 初始化时间解析器
        self.time_parser = TimeParser()
        self.normalizer_time = 0
        self.time_parser_time = 0

    def extract(self, query, base_time="2025-01-21T08:00:00Z"):
        """
        提取查询中的时间信息
        :param query: 输入查询文本
        :param base_time: 基准时间，默认为 2025-01-21T08:00:00Z
        :return: 解析后的时间结果列表和查询标签
        """
        query_tag = None  # 初始化query_tag，避免异常时未定义
        try:
            start_time = time.time()
            # 1. 对查询进行归一化处理
            query_tag = self.normalizer.tag(query)
            self.normalizer_time += time.time() - start_time
            if not query_tag:
                return [], query_tag
            self.logger.debug(f"Tag: {query_tag}")
            # 2. 解析归一化结果为时间（传递原始query用于歧义过滤）
            start_time = time.time()
            datetime_results = self.time_parser.parse_tag_to_datetime(
                query_tag, base_time, original_query=query
            )
            self.time_parser_time += time.time() - start_time
            return datetime_results, query_tag
        except Exception as e:
            self.logger.error(f"时间提取错误: {str(e)}")
            self.logger.debug(f"时间提取错误: {str(e)}, 文本内容为：{query}")
            return [], query_tag
