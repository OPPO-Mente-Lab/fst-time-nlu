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
from ..word_level_pynini import string_file, union, accep, cross, word_cross
from ..word_level_pynini import pynutil
from ..word_level_pynini import word_delete_space

from ...core.processor import Processor
from ...core.utils import get_abs_path, INPUT_LOWER_CASED
from .base.time_base import TimeBaseRule


class TimeDeltaRule(Processor):
    """Time delta rule processor, handles expressions like 'in 10 minutes', '5 hours later'"""

    def __init__(self, input_case: str = INPUT_LOWER_CASED):
        super().__init__(name="time_delta")
        self.input_case = input_case
        self.time = TimeBaseRule(input_case=input_case)
        self.build_tagger()

    def build_tagger(self):
        """Build the tagger for time delta expressions"""
        delete = pynutil.delete
        insert = pynutil.insert
        delete_space = word_delete_space()

        # Load delta patterns

        # Get time duration rules from TimeBaseRule (already includes optional "more" support)
        time_cnt_rules = self.time.build_time_cnt_rules()

        # Build delta direction patterns
        # Pattern 1: "in X minutes/hours/seconds"
        in_pattern = (
            insert('direction:"')
            + insert("future")
            + insert('"')
            + delete_space
            + delete("in")
            + delete_space
            + time_cnt_rules
        )

        # Pattern 2: "X minutes/hours/seconds later"
        later_pattern = (
            time_cnt_rules
            + delete_space
            + delete("later")
            + delete_space
            + insert('direction:"')
            + insert("future")
            + insert('"')
        )

        # Pattern 3: "X minutes/hours/seconds from now"
        from_now_pattern = (
            time_cnt_rules
            + delete_space
            + delete("from")
            + delete_space
            + delete("now")
            + delete_space
            + insert('direction:"')
            + insert("future")
            + insert('"')
        )

        # Pattern 4: "X minutes/hours/seconds after"
        after_pattern = (
            time_cnt_rules
            + delete_space
            + delete("after")
            + delete_space
            + insert('direction:"')
            + insert("future")
            + insert('"')
        )

        # Pattern 5: "X minutes/hours/seconds/years/months ago"
        ago_pattern = (
            time_cnt_rules
            + delete_space
            + delete("ago")
            + delete_space
            + insert('direction:"')
            + insert("past")
            + insert('"')
        )

        # Pattern 6: "X days/weeks/months/years hence" (future direction)
        hence_pattern = (
            time_cnt_rules
            + delete_space
            + delete("hence")
            + delete_space
            + insert('direction:"')
            + insert("future")
            + insert('"')
        )

        # Pattern 7: "X days/weeks/months/years back" (past direction)
        back_pattern = (
            time_cnt_rules
            + delete_space
            + delete("back")
            + delete_space
            + insert('direction:"')
            + insert("past")
            + insert('"')
        )

        # Special patterns for common expressions
        # "half an hour" -> 30 minutes
        # 词级FST：使用delete删除输入词，避免字段名重复
        half_hour = (
            insert('direction:"')
            + insert("future")
            + insert('"')
            + delete_space
            + insert('minute:"')
            + insert("30")
            + insert('"')
            + delete_space
            + delete("half")
            + delete_space
            + delete("an")
            + delete_space
            + delete("hour")
        )

        # "an hour and a half" -> 1 hour 30 minutes
        # 词级FST：使用delete删除输入词，避免字段名重复
        hour_and_half = (
            insert('direction:"')
            + insert("future")
            + insert('"')
            + delete_space
            + insert('hour:"')
            + insert("1")
            + insert('"')
            + delete_space
            + insert('minute:"')
            + insert("30")
            + insert('"')
            + delete_space
            + delete("an")
            + delete_space
            + delete("hour")
            + delete_space
            + delete("and")
            + delete_space
            + delete("a")
            + delete_space
            + delete("half")
        )

        # "a year", "a month", "a day", "a week", "an hour", "a minute", "a sec" patterns
        # 词级FST：使用delete删除输入词，避免字段名重复
        a_unit_pattern = (
            insert('direction:"')
            + insert("future")
            + insert('"')
            + delete_space
            + (
                (
                    delete("a")
                    + delete_space
                    + delete("year")
                    + delete_space
                    + insert('year:"')
                    + insert("1")
                    + insert('"')
                )
                | (
                    delete("a")
                    + delete_space
                    + delete("month")
                    + delete_space
                    + insert('month:"')
                    + insert("1")
                    + insert('"')
                )
                | (
                    delete("a")
                    + delete_space
                    + delete("day")
                    + delete_space
                    + insert('day:"')
                    + insert("1")
                    + insert('"')
                )
                | (
                    delete("a")
                    + delete_space
                    + delete("week")
                    + delete_space
                    + insert('week:"')
                    + insert("1")
                    + insert('"')
                )
                | (
                    delete("an")
                    + delete_space
                    + delete("hour")
                    + delete_space
                    + insert('hour:"')
                    + insert("1")
                    + insert('"')
                )
                | (
                    delete("a")
                    + delete_space
                    + delete("minute")
                    + delete_space
                    + insert('minute:"')
                    + insert("1")
                    + insert('"')
                )
                | (
                    delete("a")
                    + delete_space
                    + delete("sec")
                    + delete_space
                    + insert('second:"')
                    + insert("1")
                    + insert('"')
                )
            )
        )

        # Special patterns for "a unit ago" (past direction)
        # 词级FST：使用delete删除输入词，避免字段名重复
        a_unit_ago_pattern = (
            insert('direction:"')
            + insert("past")
            + insert('"')
            + delete_space
            + (
                (
                    delete("a")
                    + delete_space
                    + delete("year")
                    + delete_space
                    + insert('year:"')
                    + insert("1")
                    + insert('"')
                )
                | (
                    delete("a")
                    + delete_space
                    + delete("month")
                    + delete_space
                    + insert('month:"')
                    + insert("1")
                    + insert('"')
                )
                | (
                    delete("a")
                    + delete_space
                    + delete("day")
                    + delete_space
                    + insert('day:"')
                    + insert("1")
                    + insert('"')
                )
                | (
                    delete("a")
                    + delete_space
                    + delete("week")
                    + delete_space
                    + insert('week:"')
                    + insert("1")
                    + insert('"')
                )
                | (
                    delete("an")
                    + delete_space
                    + delete("hour")
                    + delete_space
                    + insert('hour:"')
                    + insert("1")
                    + insert('"')
                )
                | (
                    delete("a")
                    + delete_space
                    + delete("minute")
                    + delete_space
                    + insert('minute:"')
                    + insert("1")
                    + insert('"')
                )
                | (
                    delete("a")
                    + delete_space
                    + delete("sec")
                    + delete_space
                    + insert('second:"')
                    + insert("1")
                    + insert('"')
                )
            )
            + delete_space
            + delete("ago")
        )

        # Special patterns for "a unit hence" (future direction)
        # 词级FST：使用delete删除输入词，避免字段名重复
        a_unit_hence_pattern = (
            insert('direction:"')
            + insert("future")
            + insert('"')
            + delete_space
            + (
                (
                    delete("a")
                    + delete_space
                    + delete("year")
                    + delete_space
                    + insert('year:"')
                    + insert("1")
                    + insert('"')
                )
                | (
                    delete("a")
                    + delete_space
                    + delete("month")
                    + delete_space
                    + insert('month:"')
                    + insert("1")
                    + insert('"')
                )
                | (
                    delete("a")
                    + delete_space
                    + delete("day")
                    + delete_space
                    + insert('day:"')
                    + insert("1")
                    + insert('"')
                )
                | (
                    delete("a")
                    + delete_space
                    + delete("week")
                    + delete_space
                    + insert('week:"')
                    + insert("1")
                    + insert('"')
                )
                | (
                    delete("an")
                    + delete_space
                    + delete("hour")
                    + delete_space
                    + insert('hour:"')
                    + insert("1")
                    + insert('"')
                )
                | (
                    delete("a")
                    + delete_space
                    + delete("minute")
                    + delete_space
                    + insert('minute:"')
                    + insert("1")
                    + insert('"')
                )
                | (
                    delete("a")
                    + delete_space
                    + delete("sec")
                    + delete_space
                    + insert('second:"')
                    + insert("1")
                    + insert('"')
                )
            )
            + delete_space
            + delete("hence")
        )

        # Fortnight patterns (14 days = 2 weeks)
        # 词级FST：使用delete删除输入词，避免字段名重复
        fortnight_pattern = (
            insert('direction:"')
            + insert("future")
            + insert('"')
            + delete_space
            + delete("a")
            + delete_space
            + delete("fortnight")
            + delete_space
            + insert('day:"')
            + insert("14")
            + insert('"')
            + delete_space
            + delete("hence").ques
        )

        fortnight_ago_pattern = (
            insert('direction:"')
            + insert("past")
            + insert('"')
            + delete_space
            + delete("a")
            + delete_space
            + delete("fortnight")
            + delete_space
            + insert('day:"')
            + insert("14")
            + insert('"')
            + delete_space
            + delete("ago")
        )

        # Quantifier patterns: "in a couple of minutes", "in a few hours", etc.
        # Define specific patterns for each quantifier + unit combination
        # 词级FST：使用accep匹配词级token
        quantifier_pattern = (
            insert('direction:"')
            + insert("future")
            + insert('"')
            + delete_space
            + delete("in")
            + delete_space
            + (
                # "a couple of minutes" -> minute: "2"
                (
                    delete("a")
                    + delete_space
                    + delete("couple")
                    + delete_space
                    + delete("of").ques
                    + delete_space
                    + delete("minutes")
                    + delete_space
                    + insert('minute:"')
                    + insert("2")
                    + insert('"')
                )  # "a couple of hours" -> hour: "2"  # noqa: W504, E261
                | (
                    delete("a")
                    + delete_space
                    + delete("couple")
                    + delete_space
                    + delete("of").ques
                    + delete_space
                    + delete("hours")
                    + delete_space
                    + insert('hour:"')
                    + insert("2")
                    + insert('"')
                )  # "a couple of seconds" -> second: "2"  # noqa: W504, E261
                | (
                    delete("a")
                    + delete_space
                    + delete("couple")
                    + delete_space
                    + delete("of").ques
                    + delete_space
                    + delete("seconds")
                    + delete_space
                    + insert('second:"')
                    + insert("2")
                    + insert('"')
                )  # "a couple of days" -> day: "2"  # noqa: W504, E261
                | (
                    delete("a")
                    + delete_space
                    + delete("couple")
                    + delete_space
                    + delete("of").ques
                    + delete_space
                    + delete("days")
                    + delete_space
                    + insert('day:"')
                    + insert("2")
                    + insert('"')
                )  # "a couple of weeks" -> week: "2"  # noqa: W504, E261
                | (
                    delete("a")
                    + delete_space
                    + delete("couple")
                    + delete_space
                    + delete("of").ques
                    + delete_space
                    + delete("weeks")
                    + delete_space
                    + insert('week:"')
                    + insert("2")
                    + insert('"')
                )  # "a couple of months" -> month: "2"  # noqa: W504, E261
                | (
                    delete("a")
                    + delete_space
                    + delete("couple")
                    + delete_space
                    + delete("of").ques
                    + delete_space
                    + delete("months")
                    + delete_space
                    + insert('month:"')
                    + insert("2")
                    + insert('"')
                )  # "a couple of years" -> year: "2"  # noqa: W504, E261
                | (
                    delete("a")
                    + delete_space
                    + delete("couple")
                    + delete_space
                    + delete("of").ques
                    + delete_space
                    + delete("years")
                    + delete_space
                    + insert('year:"')
                    + insert("2")
                    + insert('"')
                )  # "a pair of minutes" -> minute: "2"  # noqa: W504, E261
                | (
                    delete("a")
                    + delete_space
                    + delete("pair")
                    + delete_space
                    + delete("of").ques
                    + delete_space
                    + delete("minutes")
                    + delete_space
                    + insert('minute:"')
                    + insert("2")
                    + insert('"')
                )  # "a pair of hours" -> hour: "2"  # noqa: W504, E261
                | (
                    delete("a")
                    + delete_space
                    + delete("pair")
                    + delete_space
                    + delete("of").ques
                    + delete_space
                    + delete("hours")
                    + delete_space
                    + insert('hour:"')
                    + insert("2")
                    + insert('"')
                )  # "a few minutes" -> minute: "3"  # noqa: W504, E261
                | (
                    delete("a")
                    + delete_space
                    + delete("few")
                    + delete_space
                    + delete("of").ques
                    + delete_space
                    + delete("minutes")
                    + delete_space
                    + insert('minute:"')
                    + insert("3")
                    + insert('"')
                )  # "a few hours" -> hour: "3"  # noqa: W504, E261
                | (
                    delete("a")
                    + delete_space
                    + delete("few")
                    + delete_space
                    + delete("of").ques
                    + delete_space
                    + delete("hours")
                    + delete_space
                    + insert('hour:"')
                    + insert("3")
                    + insert('"')
                )  # "a few seconds" -> second: "3"  # noqa: W504, E261
                | (
                    delete("a")
                    + delete_space
                    + delete("few")
                    + delete_space
                    + delete("of").ques
                    + delete_space
                    + delete("seconds")
                    + delete_space
                    + insert('second:"')
                    + insert("3")
                    + insert('"')
                )  # "a few days" -> day: "3"  # noqa: W504, E261
                | (
                    delete("a")
                    + delete_space
                    + delete("few")
                    + delete_space
                    + delete("of").ques
                    + delete_space
                    + delete("days")
                    + delete_space
                    + insert('day:"')
                    + insert("3")
                    + insert('"')
                )  # "a few weeks" -> week: "3"  # noqa: W504, E261
                | (
                    delete("a")
                    + delete_space
                    + delete("few")
                    + delete_space
                    + delete("of").ques
                    + delete_space
                    + delete("weeks")
                    + delete_space
                    + insert('week:"')
                    + insert("3")
                    + insert('"')
                )  # "a few months" -> month: "3"  # noqa: W504, E261
                | (
                    delete("a")
                    + delete_space
                    + delete("few")
                    + delete_space
                    + delete("of").ques
                    + delete_space
                    + delete("months")
                    + delete_space
                    + insert('month:"')
                    + insert("3")
                    + insert('"')
                )  # "a few years" -> year: "3"  # noqa: W504, E261
                | (
                    delete("a")
                    + delete_space
                    + delete("few")
                    + delete_space
                    + delete("of").ques
                    + delete_space
                    + delete("years")
                    + delete_space
                    + insert('year:"')
                    + insert("3")
                    + insert('"')
                )  # "few minutes" -> minute: "3"  # noqa: W504, E261
                | (
                    delete("few")
                    + delete_space
                    + delete("minutes")
                    + delete_space
                    + insert('minute:"')
                    + insert("3")
                    + insert('"')
                )  # "few hours" -> hour: "3"  # noqa: W504, E261
                | (
                    delete("few")
                    + delete_space
                    + delete("hours")
                    + delete_space
                    + insert('hour:"')
                    + insert("3")
                    + insert('"')
                )  # "few seconds" -> second: "3"  # noqa: W504, E261
                | (
                    delete("few")
                    + delete_space
                    + delete("seconds")
                    + delete_space
                    + insert('second:"')
                    + insert("3")
                    + insert('"')
                )  # "few days" -> day: "3"  # noqa: W504, E261
                | (
                    delete("few")
                    + delete_space
                    + delete("days")
                    + delete_space
                    + insert('day:"')
                    + insert("3")
                    + insert('"')
                )  # "few weeks" -> week: "3"  # noqa: W504, E261
                | (
                    delete("few")
                    + delete_space
                    + delete("weeks")
                    + delete_space
                    + insert('week:"')
                    + insert("3")
                    + insert('"')
                )  # "few months" -> month: "3"  # noqa: W504, E261
                | (
                    delete("few")
                    + delete_space
                    + delete("months")
                    + delete_space
                    + insert('month:"')
                    + insert("3")
                    + insert('"')
                )  # "few years" -> year: "3"  # noqa: W504, E261
                | (
                    delete("few")
                    + delete_space
                    + delete("years")
                    + delete_space
                    + insert('year:"')
                    + insert("3")
                    + insert('"')
                )
            )
        )

        # Compound time expressions like "2 hours and 18 minutes later"
        # Pattern: time_cnt + "and" + time_cnt + suffix
        compound_time_pattern = (
            time_cnt_rules
            + delete_space
            + delete("and")
            + delete_space
            + time_cnt_rules
            + delete_space
            + delete("later")
            + delete_space
            + insert('direction:"')
            + insert("future")
            + insert('"')
        )

        # Special pattern 1: "in a quarter of an hour" -> 15 minutes
        # 词级FST：使用accep匹配词级token
        in_quarter_hour = (
            insert('direction:"')
            + insert("future")
            + insert('"')
            + delete_space
            + delete("in")
            + delete_space
            + insert('minute:"')
            + insert("15")
            + insert('"')
            + delete_space
            + delete("a")
            + delete_space
            + delete("quarter")
            + delete_space
            + delete("of")
            + delete_space
            + delete("an")
            + delete_space
            + delete("hour")
        )

        # Special pattern 2: "in three-quarters of an hour" -> 45 minutes
        # 词级FST：使用accep匹配词级token
        in_three_quarters_hour = (
            insert('direction:"')
            + insert("future")
            + insert('"')
            + delete_space
            + delete("in")
            + delete_space
            + insert('minute:"')
            + insert("45")
            + insert('"')
            + delete_space
            + (
                (
                    delete("three")
                    + delete_space
                    + delete("quarters")
                    + delete_space
                    + delete("of")
                    + delete_space
                    + delete("an")
                    + delete_space
                    + delete("hour")
                )
                | (
                    delete("three")
                    + delete_space
                    + delete("-")
                    + delete_space
                    + delete("quarters")
                    + delete_space
                    + delete("of")
                    + delete_space
                    + delete("an")
                    + delete_space
                    + delete("hour")
                )
            )
        )

        # Special pattern 3: "a quarter of an hour later" -> 15 minutes
        # 词级FST：使用accep匹配词级token
        quarter_hour_later = (
            insert('minute:"')
            + insert("15")
            + insert('"')
            + delete_space
            + delete("a")
            + delete_space
            + delete("quarter")
            + delete_space
            + delete("of")
            + delete_space
            + delete("an")
            + delete_space
            + delete("hour")
            + delete_space
            + delete("later")
            + delete_space
            + insert('direction:"')
            + insert("future")
            + insert('"')
        )

        # Special pattern 4: "three-quarters of an hour later" -> 45 minutes
        # 词级FST：使用accep匹配词级token
        three_quarters_hour_later = (
            insert('minute:"')
            + insert("45")
            + insert('"')
            + delete_space
            + (
                (
                    delete("three")
                    + delete_space
                    + delete("quarters")
                    + delete_space
                    + delete("of")
                    + delete_space
                    + delete("an")
                    + delete_space
                    + delete("hour")
                )
                | (
                    delete("three")
                    + delete_space
                    + delete("-")
                    + delete_space
                    + delete("quarters")
                    + delete_space
                    + delete("of")
                    + delete_space
                    + delete("an")
                    + delete_space
                    + delete("hour")
                )
            )
            + delete_space
            + delete("later")
            + delete_space
            + insert('direction:"')
            + insert("future")
            + insert('"')
        )

        # Special pattern 5: "in X and a half hours" -> X.5 hours
        # e.g., "in 2 and a half hours" -> hour: "2" minute: "30"
        # 词级FST：使用accep匹配词级token
        in_and_half_hours = (
            insert('direction:"')
            + insert("future")
            + insert('"')
            + delete_space
            + delete("in")
            + delete_space
            + insert('hour:"')
            + self.time.hour
            + insert('"')
            + delete_space
            + delete("and")
            + delete_space
            + (
                (delete("a") + delete_space + delete("half"))
                | (delete("an") + delete_space + delete("half"))
            )
            + delete_space
            + (delete("hour") | delete("hours"))
            + delete_space
            + insert('minute:"')
            + insert("30")
            + insert('"')
        )

        # Combine all patterns (special patterns first for higher priority)
        combined_tagger = (
            in_quarter_hour
            | in_three_quarters_hour
            | quarter_hour_later
            | three_quarters_hour_later
            | in_and_half_hours
            | fortnight_ago_pattern
            | fortnight_pattern
            | a_unit_ago_pattern
            | a_unit_hence_pattern
            | quantifier_pattern
            | in_pattern
            | later_pattern
            | from_now_pattern
            | after_pattern
            | ago_pattern
            | hence_pattern
            | back_pattern
            | half_hour
            | hour_and_half
            | a_unit_pattern
            | compound_time_pattern
        )

        self.tagger = self.add_tokens(combined_tagger)
