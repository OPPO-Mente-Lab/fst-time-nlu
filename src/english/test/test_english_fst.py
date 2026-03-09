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
Test script for English FST rules functionality
"""

import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../..")))

from src.english.fst_time_extractor import FstTimeExtractor  # noqa: E402


def test_fst_extraction():
    """Test FST-based time extraction for English"""

    print("Testing English FST Time Expression Extraction")
    print("=" * 60)

    # Create extractor with FST support
    try:
        extractor = FstTimeExtractor(
            cache_dir=os.path.join(os.path.dirname(__file__), "fst"),
            overwrite_cache=True,  # Force rebuild for testing
        )
    except Exception as e:
        print(f"Error creating FST extractor: {e}")
        print("Falling back to simple extraction...")
        extractor = FstTimeExtractor()

    # Test cases for FST extraction
    test_cases = [
        # Relative time
        "tomorrow",
        "yesterday",
        "next Monday",
        "last Friday",
        "in 2 hours",
        "3 days ago",
        # Periods
        "morning",
        "this afternoon",
        "tonight",
        # Holidays
        "Christmas",
        "next Easter",
        # Between expressions
        "from 9 AM to 5 PM",
        "between Monday and Friday",
        # Complex expressions
        "Meet me tomorrow at 3:30 PM",
        "The meeting is next Friday morning",
        "I'll be there in 2 hours",
    ]

    base_time = "2025-01-21T08:00:00Z"
    print(f"Base time: {base_time}")
    print("(Tuesday, January 21, 2025, 8:00 AM UTC)")
    print()

    for expression in test_cases:
        print(f"Expression: '{expression}'")

        try:
            # Test FST extraction
            result, tags = extractor.extract(expression, base_time)

            if tags:
                print(f"  🏷️  FST Tags: {tags}")
            else:
                print("  🏷️  FST Tags: No tags generated")

            if result:
                print(f"  ✅ FST Result: {result[0]}")
                if len(result[0]) == 2:
                    print(f"     Time range: {result[0][0]} to {result[0][1]}")
                else:
                    print(f"     Single time: {result[0][0]}")
            else:
                print("  ❌ FST Result: No time found")

                # Fallback to simple extraction
                simple_result = extractor.extract_simple(expression, base_time)
                if simple_result:
                    print(f"  📝 Simple fallback: {simple_result[0]}")

        except Exception as e:
            print(f"  💥 Error: {e}")

        print()


def test_individual_rules():
    """Test individual FST rules"""

    print("\nTesting Individual FST Rules")
    print("=" * 40)

    try:
        from src.english.rules import (
            RelativeRule,
            PeriodRule,
            WeekRule,
            HolidayRule,
            UTCTimeRule,
            DeltaRule,
        )

        # Test relative rule
        print("Testing RelativeRule...")
        relative_rule = RelativeRule()
        if hasattr(relative_rule, "tagger") and relative_rule.tagger:
            print("  ✅ RelativeRule initialized successfully")
        else:
            print("  ❌ RelativeRule failed to initialize")

        # Test other rules
        rules_to_test = [
            ("PeriodRule", PeriodRule),
            ("WeekRule", WeekRule),
            ("HolidayRule", HolidayRule),
            ("UTCTimeRule", UTCTimeRule),
            ("DeltaRule", DeltaRule),
        ]

        for rule_name, rule_class in rules_to_test:
            try:
                rule = rule_class()
                if hasattr(rule, "tagger") and rule.tagger:
                    print(f"  ✅ {rule_name} initialized successfully")
                else:
                    print(f"  ❌ {rule_name} failed to initialize")
            except Exception as e:
                print(f"  💥 {rule_name} error: {e}")

    except Exception as e:
        print(f"Error importing rules: {e}")


if __name__ == "__main__":
    # Test individual rules first
    test_individual_rules()

    # Then test full FST extraction
    test_fst_extraction()
