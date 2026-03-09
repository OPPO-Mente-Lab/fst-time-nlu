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

# 使用词级pynini
from ...word_level_pynini import string_file, union, closure, string_map
from ...word_level_pynini import pynutil
from ...word_level_pynini import word_delete_space

from ....core.utils import (
    get_abs_path,
    INPUT_CASED,
    INPUT_LOWER_CASED,
    create_word_boundary,
    NEMO_CHAR,
)

insert = pynutil.insert
delete = pynutil.delete


class WeekBaseRule:
    """Week base rule class for English"""

    def __init__(self, input_case: str = INPUT_LOWER_CASED):
        self.input_case = input_case

    def build_rules(self):
        """Build week rules"""

        # 使用词级delete_space（替代字符级delete_space）
        delete_space = word_delete_space()

        # Load TSV files
        weekday_full = string_file(get_abs_path("../../data/week/weekdays_full.tsv"))
        weekday_abbr = string_file(get_abs_path("../../data/week/weekdays_abbr.tsv"))
        week_periods = string_file(get_abs_path("../../data/week/week_periods.tsv"))

        # Support capitalized input if needed
        if self.input_case == INPUT_CASED:
            weekday_full = weekday_full | self._capitalize_weekdays()
            weekday_abbr = weekday_abbr | self._capitalize_weekday_abbr()

        # Combine full and abbreviated weekdays
        weekday_full_safe = weekday_full  # 完整单词不需要边界检测

        # 为缩写添加词边界检测：使用更严格的方法
        # 只有当缩写后面跟空格或字符串结尾时才匹配
        weekday_abbr_safe = weekday_abbr + union(" ", "")

        # 组合：完整单词 或 （缩写+词边界）
        weekday = weekday_full_safe | weekday_abbr_safe
        weekday_tag = insert('week_day:"') + weekday + insert('"')

        # Week period expressions (weekend, weekday, etc.)
        week_period_tag = insert('week_period:"') + week_periods + insert('"')

        # Build two types of week offset:
        # 1. For standalone "this week" / "next week" / "last week"
        week_offset_with_week = self._build_week_offset_with_week()
        week_offset_with_week_tag = insert('offset_week:"') + week_offset_with_week + insert('"')

        # 2. For "next Monday" / "this weekend" (prefix without "week")
        week_offset_prefix = self._build_week_offset_prefix()
        week_offset_prefix_tag = insert('offset_week:"') + week_offset_prefix + insert('"')

        # Combinations:
        # Priority order matters! More specific patterns first
        # 1. "next Monday" -> offset_week: "1" week_day: "monday"
        # 2. "this weekend" -> offset_week: "0" week_period: "weekend"
        # 3. "next week" -> offset_week: "1"
        # 4. "Monday" -> week_day: "monday"
        # 5. "weekend" -> week_period: "weekend"

        week_with_day = week_offset_prefix_tag + delete_space + weekday_tag
        week_with_period = week_offset_prefix_tag + delete_space + week_period_tag

        # "end of week" patterns
        # e.g., "end of this week", "end of next week", "at the end of last week"
        end_of_week = self._build_end_of_week_pattern()

        # "beginning of week" patterns
        # e.g., "beginning of this week", "beginning of next week", "at the beginning of last week"
        beginning_of_week = self._build_beginning_of_week_pattern()

        # Final graph combining all patterns
        # Put more specific patterns first to avoid partial matches
        week_date = (
            end_of_week  # "end of this/next/last week" - highest priority
            | beginning_of_week  # "beginning of this/next/last week" - second priority
            | week_with_day
            | week_with_period
            | week_offset_with_week_tag  # "this week" / "next week" / "last week"
            | weekday_tag
            | week_period_tag
        )

        return week_date

    def _build_week_offset_with_week(self):
        """Build week offset expressions with 'week' word (this week, next week, last week)"""
        # 使用词级delete_space
        delete_space = word_delete_space()
        # Load week prefix from TSV file
        week_prefix = string_file(get_abs_path("../../data/week/week_prefix.tsv"))

        # Support lowercase input (preprocessing converts to lowercase)
        week_prefix |= string_map(
            [
                ("next", "1"),
                ("last", "-1"),
                ("this", "0"),
                ("all", "0"),
            ]
        )

        # Must include "week" word
        week_word = delete_space + delete("week")

        # Support "the" prefix: "the following week", "the upcoming week", etc.
        optional_the = closure(delete("the") + delete_space, 0, 1)

        week_offset = optional_the + week_prefix + week_word

        return week_offset

    def _build_week_offset_prefix(self):
        """Build week offset prefix only (for use with weekdays: next Monday)"""
        # Load week prefix from TSV file
        week_prefix = string_file(get_abs_path("../../data/week/week_prefix.tsv"))

        # Support lowercase input (preprocessing converts to lowercase)
        week_prefix |= string_map(
            [
                ("next", "1"),
                ("last", "-1"),
                ("this", "0"),
                ("all", "0"),
            ]
        )

        return week_prefix

    def _build_end_of_week_pattern(self):
        """
        Build 'end of week' pattern
        Examples: "end of this week", "end of next week", "at the end of last week"
        Returns: offset_week + week_period: "weekend"
        """
        delete = pynutil.delete
        insert = pynutil.insert
        # 使用词级delete_space
        delete_space = word_delete_space()
        # Load week prefix from TSV file
        week_prefix = string_file(get_abs_path("../../data/week/week_prefix.tsv"))

        # Support capitalized input if needed
        # Support lowercase input (preprocessing converts to lowercase)
        week_prefix |= string_map(
            [
                ("next", "1"),
                ("last", "-1"),
                ("this", "0"),
                ("current", "0"),
                ("coming", "1"),
                ("following", "1"),
                ("previous", "-1"),
                ("past", "-1"),
            ]
        )

        # Optional "at the"
        optional_at_the = closure(delete("at") + delete_space + delete("the") + delete_space, 0, 1)

        # Optional "the"
        optional_the = closure(delete("the") + delete_space, 0, 1)

        # Optional "around" modifier
        optional_around = closure(delete("around") + delete_space, 0, 1)

        # "end of" pattern
        end_of = delete("end") + delete_space + delete("of") + delete_space

        # Build the pattern: [at the] end of [the] [around] {week_prefix} week
        # Output: offset_week: "X" week_period: "weekend"
        end_of_week_pattern = (
            optional_at_the
            + end_of
            + optional_the
            + optional_around
            + insert('offset_week:"')
            + week_prefix
            + insert('"')
            + delete_space
            + delete("week")
            + insert(' week_period:"weekend"')
        )

        return end_of_week_pattern

    def _build_beginning_of_week_pattern(self):
        """
        Build 'beginning of week' pattern
        Examples: "beginning of this week", "beginning of next week", "at the beginning of last week"
        Returns: offset_week + week_period: "weekbeginning"
        """
        delete = pynutil.delete
        insert = pynutil.insert
        # 使用词级delete_space
        delete_space = word_delete_space()
        # Load week prefix from TSV file
        week_prefix = string_file(get_abs_path("../../data/week/week_prefix.tsv"))

        # Support capitalized input if needed
        # Support lowercase input (preprocessing converts to lowercase)
        week_prefix |= string_map(
            [
                ("next", "1"),
                ("last", "-1"),
                ("this", "0"),
                ("current", "0"),
                ("coming", "1"),
                ("following", "1"),
                ("previous", "-1"),
                ("past", "-1"),
            ]
        )

        # Optional "at the"
        optional_at_the = closure(delete("at") + delete_space + delete("the") + delete_space, 0, 1)

        # Optional "the"
        optional_the = closure(delete("the") + delete_space, 0, 1)

        # Optional "around" modifier
        optional_around = closure(delete("around") + delete_space, 0, 1)

        # "beginning of" pattern
        beginning_of = delete("beginning") + delete_space + delete("of") + delete_space

        # Build the pattern: [at the] beginning of [the] [around] {week_prefix} week
        # Output: offset_week: "X" week_period: "weekbeginning"
        beginning_of_week_pattern = (
            optional_at_the
            + beginning_of
            + optional_the
            + optional_around
            + insert('offset_week:"')
            + week_prefix
            + insert('"')
            + delete_space
            + delete("week")
            + insert(' week_period:"weekbeginning"')
        )

        return beginning_of_week_pattern

    def _capitalize_weekdays(self):
        """Support lowercase weekday names"""
        return string_map(
            [
                ("monday", "monday"),
                ("tuesday", "tuesday"),
                ("wednesday", "wednesday"),
                ("thursday", "thursday"),
                ("friday", "friday"),
                ("saturday", "saturday"),
                ("sunday", "sunday"),
            ]
        )

    def _capitalize_weekday_abbr(self):
        """Support lowercase weekday abbreviations"""
        return string_map(
            [
                ("mon", "monday"),
                ("tue", "tuesday"),
                ("tues", "tuesday"),
                ("wed", "wednesday"),
                ("thu", "thursday"),
                ("thur", "thursday"),
                ("thurs", "thursday"),
                ("fri", "friday"),
                ("sat", "saturday"),
                ("sun", "sunday"),
            ]
        )
