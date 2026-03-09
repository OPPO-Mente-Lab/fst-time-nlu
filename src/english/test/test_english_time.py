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
Simple test script for English time parsing functionality
"""

import sys
import os

# Add the project root to the Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.join(current_dir, "../../../..")
sys.path.insert(0, os.path.abspath(project_root))

from src.english.fst_time_extractor import FstTimeExtractor  # noqa: E402


def test_simple_expressions():
    """Test simple time expressions using the parser directly"""

    # Create extractor
    extractor = FstTimeExtractor()

    # Test cases
    test_cases = [
        "tomorrow",
        "yesterday",
        "next Monday",
        "last Friday",
        "this morning",
        "next week",
        "in 2 hours",
        "3 days ago",
        "Christmas",
        "next Christmas",
        "morning",
        "afternoon",
        "tonight",
    ]

    print("Testing English Time Expression Parsing")
    print("=" * 50)

    base_time = "2025-01-21T08:00:00Z"

    for expression in test_cases:
        print(f"\nExpression: '{expression}'")

        # Test simple extraction (without FST)
        try:
            result = extractor.extract_simple(expression, base_time)
            if result:
                print(f"  Result: {result}")
            else:
                print("  Result: No time found")
        except Exception as e:
            print(f"  Error: {e}")


if __name__ == "__main__":
    test_simple_expressions()
