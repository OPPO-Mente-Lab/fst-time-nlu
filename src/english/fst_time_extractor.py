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
    """Integrated time normalization and parsing extractor for English"""

    def __init__(self, cache_dir=None, overwrite_cache=False, include_source=True):
        """
        Initialize time extractor

        Args:
            cache_dir: FST cache directory
            overwrite_cache: Whether to overwrite existing cache
            include_source: Whether to include source field in tags (default True)
        """
        self.logger = get_logger(__name__)
        # Initialize normalizer
        if not cache_dir:
            cache_dir = os.path.dirname(__file__) + "/test/fst"
        self.normalizer = Normalizer(
            cache_dir=cache_dir, overwrite_cache=overwrite_cache, include_source=include_source
        )
        # Initialize time parser
        self.time_parser = TimeParser()
        self.normalizer_time = 0
        self.time_parser_time = 0

    def extract(self, query, base_time="2025-01-21T08:00:00Z"):
        """
        Extract time information from English query

        Args:
            query (str): Input query text
            base_time (str): Base time reference, default "2025-01-21T08:00:00Z"

        Returns:
            tuple: (datetime_results, query_tag) - parsed time results and query tags
        """
        query_tag = None  # Initialize query_tag to avoid undefined errors
        try:
            start_time = time.time()
            # 1. Normalize the query
            query_tag = self.normalizer.tag(query)
            if query_tag:
                query_tag = self._compact_numeric_tokens(query_tag)
            self.normalizer_time += time.time() - start_time
            if not query_tag:
                return [], query_tag
            self.logger.debug(f"Tag: {query_tag}")

            # 2. Parse normalization results to time
            start_time = time.time()
            datetime_results = self.time_parser.parse_tag_to_datetime(query_tag, base_time)
            self.time_parser_time += time.time() - start_time
            return datetime_results, query_tag
        except Exception as e:
            self.logger.error(f"English time extraction error: {str(e)}")
            self.logger.debug(f"English time extraction error: {str(e)}, text content: {query}")
            return [], query_tag

    @staticmethod
    def _compact_numeric_tokens(query_tag):
        """Remove redundant spaces inside numeric string fields for readability."""
        numeric_fields = {
            "hour",
            "minute",
            "second",
            "start_hour",
            "end_hour",
            "start_minute",
            "end_minute",
            "year",
            "month",
            "week",
            "day",
            "offset_year",
            "offset_month",
            "offset_week",
            "offset_day",
            "time_modifier",
        }

        for token in query_tag:
            if not isinstance(token, dict):
                continue
            for key in numeric_fields:
                if key in token and isinstance(token[key], str):
                    cleaned = token[key].replace(" ", "")
                    token[key] = cleaned
        return query_tag

    def extract_simple(self, query, base_time="2025-01-21T08:00:00Z"):
        """
        Simple extraction without FST tagging (for testing)

        Args:
            query (str): Input query text
            base_time (str): Base time reference

        Returns:
            list: Parsed time results
        """
        try:
            return self.time_parser.parse_single_expression(query, base_time)
        except Exception as e:
            self.logger.error(f"Simple extraction error: {str(e)}")
            return []
