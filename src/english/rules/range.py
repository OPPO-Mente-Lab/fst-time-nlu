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
from ..word_level_pynini import (
    accep,
    union,
    string_file,
    string_map,
    closure,
    word_delete_space,
)
from ..word_level_pynini import pynutil
from ...core.processor import Processor
from ...core.utils import get_abs_path, INPUT_LOWER_CASED


class RangeRule(Processor):
    """
    English time range rule processor

    Handles explicit time range expressions like:
    - "8 to 10 o'clock" (hour range)
    - "8 to 10" (hour range without o'clock)
    - "from 2pm to 5pm" (explicit time range with periods)
    """

    def __init__(self, input_case: str = INPUT_LOWER_CASED):
        super().__init__(name="time_range_expr")
        self.input_case = input_case

        # 导入UTCTimeRule来复用其日期时间识别能力
        from .utctime import UTCTimeRule

        self.utc_time_rule = UTCTimeRule(input_case=input_case)

        # 导入TimeBaseRule来复用hour_numeric和minute_numeric
        from .base.time_base import TimeBaseRule

        self.time_base = TimeBaseRule(input_case=input_case)

        self.build_tagger()

    def build_tagger(self):
        """Build time range FST tagger"""
        delete = pynutil.delete
        insert = pynutil.insert
        delete_space = word_delete_space()  # 使用词级delete_space

        # Load year modifiers
        year_prefix = string_file(get_abs_path("../data/date/year_prefix.tsv"))

        # 统一使用TimeBaseRule的hour_numeric和minute_numeric，确保所有pattern使用相同的定义
        # 这样可以避免重复定义导致的不一致问题，并确保能正确匹配"00"等格式
        hour = self.time_base.hour_numeric
        minute = self.time_base.minute_numeric

        # 参考UTCTimeRule的做法：创建2位数分钟格式（00-59）
        # UTCTimeRule使用minute_two_digit = union(*[accep(f"{i:02d}") for i in range(60)])
        # 这样可以确保"00"格式不被optimize()优化为"0"
        # 对于RangeRule，我们需要确保分钟值以2位数格式输出
        # 注意：使用add_weight确保minute_two_digit有更高优先级（更小的权重值）
        minute_two_digit = union(*[accep(f"{i:02d}") for i in range(60)])  # 00-59，2位数格式

        # minute_with_padding：优先使用2位数格式，确保"00"格式优先匹配
        # 使用add_weight确保minute_two_digit优先于minute
        minute_with_padding = pynutil.add_weight(minute_two_digit, -0.5) | minute

        # English word numbers for hours (用于某些特定pattern，如hour_range_oclock)
        # 保留hour_words定义，用于需要文字数字的pattern
        hour_words = union(
            accep("one"),
            accep("two"),
            accep("three"),
            accep("four"),
            accep("five"),
            accep("six"),
            accep("seven"),
            accep("eight"),
            accep("nine"),
            accep("ten"),
            accep("eleven"),
            accep("twelve"),
        )

        # 对于需要文字数字的pattern，使用hour | hour_words
        # 这样可以同时支持数字和文字格式
        hour_with_words = hour | hour_words

        # Day numbers (1-31) - both regular numbers and ordinals
        day_number = union(*[accep(str(i)) for i in range(1, 32)])

        # Ordinal suffixes
        ordinal_suffix = union(accep("st"), accep("nd"), accep("rd"), accep("th"))

        # Day with optional ordinal suffix (e.g., "23", "23rd", "1st", "2nd", "3rd", "21st")
        day_ordinal = day_number + ordinal_suffix.ques

        # Use ordinal-aware day pattern
        day = day_ordinal

        # Month names (full names and abbreviations)
        month_names = union(
            accep("january"),
            accep("february"),
            accep("march"),
            accep("april"),
            accep("may"),
            accep("june"),
            accep("july"),
            accep("august"),
            accep("september"),
            accep("october"),
            accep("november"),
            accep("december"),
            # Month abbreviations
            accep("jan"),
            accep("feb"),
            accep("mar"),
            accep("apr"),
            accep("may"),
            accep("jun"),
            accep("jul"),
            accep("aug"),
            accep("sep"),
            accep("oct"),
            accep("nov"),
            accep("dec"),
        )

        # Optional space (词级版本)
        optional_space = delete_space.ques

        # 移除year_prefix支持以优化性能，年份修饰词由UTCTimeRule + ContextMerger处理

        # Colon (词级FST：需要处理前后空格token)
        colon = delete_space.ques + delete(accep(":")) + delete_space.ques

        # "to", "till", "until", "thru", "through" connectors
        # 修复：参考UTCTimeRule的实现方式，使用delete(union(accep(...)))
        # 先创建union FST，然后用delete删除
        # 添加 "thru" 支持（"July 13 thru 15"）
        to_words_fst = union(
            accep("to"), accep("till"), accep("until"), accep("thru"), accep("through")
        )
        to_connector = optional_space + delete(to_words_fst) + optional_space

        # Complex "from" connectors (including "later than")
        # "later than"是多词短语，需要拆分为两个词：later + than
        from_words_fst = union(accep("from"))
        # "later than"需要单独处理：later + delete_space + than
        from_connector = (
            optional_space
            + (
                delete(from_words_fst)
                | (delete(accep("later")) + delete_space + delete(accep("than")))
            )
            + optional_space
        )

        # Extended "to" connectors (including "but before")
        # "but before"需要拆分为两个词：but + before

        # Year modifier tags (optional)
        start_modifier_tag = insert('start_modifier:"') + year_prefix + insert('"')
        end_modifier_tag = insert('end_modifier:"') + year_prefix + insert('"')
        optional_start_modifier = (optional_space + start_modifier_tag + optional_space).ques
        optional_end_modifier = (optional_space + end_modifier_tag + optional_space).ques

        # Optional "from" prefix (for backward compatibility)
        optional_from = (optional_space + delete("from") + optional_space).ques

        # AM/PM suffix
        # 注意：分词器可能将 "p.m." 分为 "p.m" 和 "."，所以需要支持 "p.m" 格式
        am_pm = union(
            accep("am"),
            accep("a.m."),
            accep("a m"),
            accep("a.m"),  # 支持 "a.m" 格式
            accep("pm"),
            accep("p.m."),
            accep("p m"),
            accep("p.m"),  # 支持 "p.m" 格式
        )
        optional_am_pm = (optional_space + insert('period:"') + am_pm + insert('"')).ques

        am_variants = union(accep("am"), accep("a.m"), accep("a.m."), accep("a m"))
        pm_variants = union(accep("pm"), accep("p.m"), accep("p.m."), accep("p m"))

        dot_delete = delete(accep(".")) | delete(accep(""))

        am_token = (
            delete(am_variants)
            | (delete(accep("a.m")) + optional_space + dot_delete.ques)
            | (
                delete(accep("a"))
                + optional_space
                + dot_delete
                + optional_space
                + delete(accep("m"))
                + optional_space
                + dot_delete.ques
            )
        )
        pm_token = (
            delete(pm_variants)
            | (delete(accep("p.m")) + optional_space + dot_delete.ques)
            | (
                delete(accep("p"))
                + optional_space
                + dot_delete
                + optional_space
                + delete(accep("m"))
                + optional_space
                + dot_delete.ques
            )
        )

        start_period_required = optional_space + (
            (am_token + insert(' start_period:"am"')) | (pm_token + insert(' start_period:"pm"'))
        )
        start_period_optional = start_period_required | pynutil.add_weight(accep(""), 0.1)

        end_period_required = optional_space + (
            (am_token + insert(' end_period:"am"')) | (pm_token + insert(' end_period:"pm"'))
        )
        end_period_optional = end_period_required | pynutil.add_weight(accep(""), 0.1)

        end_period_with_shared = optional_space + (
            (am_token + insert(' end_period:"am"') + insert(' period:"am"'))
            | (pm_token + insert(' end_period:"pm"') + insert(' period:"pm"'))
        )

        # o'clock variations
        oclock = union(accep("oclock"), accep("o'clock"), accep("o clock"))

        # Pattern 1: "8 to 10 o'clock" or "8 to 10 oclock"
        # This captures hour ranges with o'clock
        # 使用hour_with_words以支持文字数字（如"eight to ten o'clock"）
        hour_range_oclock = (
            insert('start_hour:"')
            + hour_with_words
            + insert('"')
            + to_connector
            + insert('end_hour:"')
            + hour_with_words
            + insert('"')
            + optional_space
            + delete(oclock)
        )

        # Pattern 1b: "8 to 10" (simple hour range without o'clock)
        # 支持英文单词形式："ten to eleven"
        hour_range_simple = (
            insert('start_hour:"')
            + hour_with_words
            + insert('"')
            + insert(' start_minute:"00"')
            + to_connector
            + insert('end_hour:"')
            + hour_with_words
            + insert('"')
            + insert(' end_minute:"00"')
        )

        # Pattern 2a: "from H:MM to H:MM" or "from H:MM to H:MM AM/PM" (with "from" prefix)
        # Higher priority - complete pattern with "from" marker
        # 使用minute_with_padding确保"00"不被optimize()优化为"0"
        # 支持文字小时（如 "from 3:30 to six p.m."）
        # 注意：分词器可能将 "p.m." 分为 "p.m" 和 "."，所以需要支持多token格式
        # 分词结果：['from', ' ', '3', ':', '30', ' ', 'to', ' ', 'six', ' ', 'p.m', '.']
        # 所以需要匹配 "p.m" + "." 的情况
        time_hm_range_with_from = (
            from_connector
            + insert('start_hour:"')
            + hour
            + insert('"')
            + colon
            + insert(' start_minute:"')
            + minute_with_padding
            + insert('"')
            + to_connector
            + insert('end_hour:"')
            + hour_with_words
            + insert('"')
            + (colon + insert(' end_minute:"') + minute_with_padding + insert('"')).ques
            + end_period_optional
        )

        # Pattern 2b: "H:MM to H:MM" or "H:MM to H:MM AM/PM" (without "from" prefix)
        # Lower priority - may conflict with other patterns in star repetition
        # 使用minute_with_padding确保"00"不被optimize()优化为"0"
        time_hm_range = (
            insert('start_hour:"')
            + hour
            + insert('"')
            + colon
            + insert(' start_minute:"')
            + minute_with_padding
            + insert('"')
            + to_connector
            + insert('end_hour:"')
            + hour
            + insert('"')
            + colon
            + insert(' end_minute:"')
            + minute_with_padding
            + insert('"')
            + optional_am_pm
        )

        # Pattern 2c: "H:MM to H PM/AM" (with AM/PM suffix, higher priority)
        # This pattern must come BEFORE graph_m_to_h to prevent "30 to 6 PM" being parsed as "5:30 PM"
        time_hm_to_h_with_period = (
            optional_from
            + insert('start_hour:"')
            + hour
            + insert('"')
            + colon
            + insert(' start_minute:"')
            + minute
            + insert('"')
            + to_connector
            + insert('end_hour:"')
            + hour
            + insert('"')
            + insert(' end_minute:"00"')
            + optional_space
            + insert('period:"')
            + am_pm
            + insert('"')  # Required AM/PM
        )

        # Pattern 3: "H:MM [o'clock] to H [o'clock] AM/PM" (start has minutes, end doesn't)

        # Pattern 4: "H [o'clock] to H:MM [o'clock] AM/PM" (start doesn't have minutes, end has)
        time_h_to_hm = (
            optional_from
            + insert('start_hour:"')
            + hour
            + insert('"')
            + insert(' start_minute:"00"')
            # Optional o'clock after start hour  # noqa: E131
            + (delete_space.ques + delete(oclock)).ques
            + to_connector
            + insert('end_hour:"')
            + hour
            + insert('"')
            + colon
            + insert(' end_minute:"')
            + minute
            + insert('"')
            # Optional o'clock after end hour
            + (delete_space.ques + delete(oclock)).ques
            + optional_am_pm
        )

        # Pattern 4a: "from H [o'clock] to H [o'clock] AM/PM" (explicit from prefix, both hours only)
        # 支持英文单词形式："from ten to eleven"
        time_h_from_to_h = (
            from_connector
            + insert('start_hour:"')
            + hour_with_words
            + insert('"')
            + insert(' start_minute:"00"')
            # Optional o'clock after start hour  # noqa: E131
            + (delete_space.ques + delete(oclock)).ques
            + to_connector
            + insert('end_hour:"')
            + hour_with_words
            + insert('"')
            + insert(' end_minute:"00"')
            # Optional o'clock after end hour
            + (delete_space.ques + delete(oclock)).ques
            + optional_am_pm
        )

        # Pattern 5: "H:MM till H:MM on weekday" (atomic pattern to prevent conflicts)
        # This pattern handles cases where "on weekday" follows the time range
        weekday_names = union(
            accep("monday"),
            accep("tuesday"),
            accep("wednesday"),
            accep("thursday"),
            accep("friday"),
            accep("saturday"),
            accep("sunday"),
        )
        time_hm_till_hm_on_weekday = (
            insert('start_hour:"')
            + hour
            + insert('"')
            + delete(union(accep(":"), accep("h")))  # 支持 ":" 或 "h" 作为分隔符
            + insert(' start_minute:"')
            + minute
            + insert('"')
            + optional_space
            + delete(union(accep("till"), accep("to"), accep("-")))
            + optional_space
            + insert('end_hour:"')
            + hour
            + insert('"')
            + delete(union(accep(":"), accep("h")))  # 支持 ":" 或 "h" 作为分隔符
            + insert(' end_minute:"')
            + minute
            + insert('"')
            + optional_space
            + delete("on")
            + optional_space
            + insert('weekday:"')
            + weekday_names
            + insert('"')
        )

        # Pattern 6: "from H:MM to H:MM AM/PM on weekday" (atomic pattern)
        time_hm_range_with_from_on_weekday = (
            from_connector
            + insert('start_hour:"')
            + hour
            + insert('"')
            + colon
            + insert(' start_minute:"')
            + minute
            + insert('"')
            + to_connector
            + insert('end_hour:"')
            + hour
            + insert('"')
            + colon
            + insert(' end_minute:"')
            + minute
            + insert('"')
            + optional_am_pm
            + optional_space
            + delete("on")
            + optional_space
            + insert('weekday:"')
            + weekday_names
            + insert('"')
        )

        # ==== 通用UTC时间范围模式（最高优先级） ====
        # 复用 UTCTimeRule 的完整时间识别能力
        # 这样可以自动支持所有 ISO 格式及其变体：
        #   - YYYY-MM-DD, YYYY/MM/DD, YYYY.MM.DD
        #   - YYYY-MM-DD HH:MM:SS
        #   - YYYY-MM-DD HH:MM
        #   - 以及所有中间形式

        # 从 DateBaseRule 获取基础组件
        from .base.date_base import DateBaseRule

        date_base = DateBaseRule(input_case=self.input_case)
        year_4digit = date_base.year_numeric
        month_numeric = string_file(get_abs_path("../data/date/month_numeric.tsv"))
        day_numeric = date_base.day_numeric

        # 定义分隔符（与DateBaseRule保持一致，词级版本）
        separator = (
            delete_space + delete("-") + delete_space
            | delete_space + delete("/") + delete_space
            | delete_space + delete(".") + delete_space
            | delete("-")
            | delete("/")
            | delete(".")
        )

        # 时分秒组件：统一使用TimeBaseRule的定义（已在文件开头定义）
        # hour和minute已经在第57-58行定义为self.time_base.hour_numeric和self.time_base.minute_numeric
        # 删除重复定义，直接使用已定义的hour和minute
        # second仍然需要单独定义，因为TimeBaseRule没有second_numeric
        second = union(
            *[accep(str(i).zfill(2)) for i in range(60)] + [accep(str(i)) for i in range(60)]
        )

        # 起始时间：YYYY-MM-DD [HH:MM:SS]
        start_date = (
            insert('start_year:"')
            + year_4digit
            + insert('"')
            + separator
            + insert(' start_month:"')
            + month_numeric
            + insert('"')
            + separator
            + insert(' start_day:"')
            + day_numeric
            + insert('"')
            # 可选的时间部分  # noqa: E131
            + closure(
                delete_space
                + insert(' start_hour:"')
                + hour
                + insert('"')
                + delete(":")  # word_delete handles single char tokens
                + insert(' start_minute:"')
                + minute
                + insert('"')
                + closure(
                    delete(":")  # word_delete handles single char tokens
                    + insert(' start_second:"')
                    + second
                    + insert('"'),
                    0,
                    1,
                ),
                0,
                1,
            )
        )

        # 结束时间：类似结构，使用 "end_" 前缀
        end_date = (
            insert('end_year:"')
            + year_4digit
            + insert('"')
            + separator
            + insert(' end_month:"')
            + month_numeric
            + insert('"')
            + separator
            + insert(' end_day:"')
            + day_numeric
            + insert('"')
            # 可选的时间部分  # noqa: E131
            + closure(
                delete_space
                + insert(' end_hour:"')
                + hour
                + insert('"')
                + delete(":")  # word_delete handles single char tokens
                + insert(' end_minute:"')
                + minute
                + insert('"')
                + closure(
                    delete(":")  # word_delete handles single char tokens
                    + insert(' end_second:"')
                    + second
                    + insert('"'),
                    0,
                    1,
                ),
                0,
                1,
            )
        )

        # Pattern UTC-1: "from UTC_TIME to UTC_TIME"
        utc_range_with_from = from_connector + start_date + to_connector + end_date

        # Pattern UTC-2: "UTC_TIME to UTC_TIME" (without from)
        utc_range_direct = start_date + to_connector + end_date

        # Date range patterns
        # Pattern 7: "month day to day" (e.g., "July 13 to 15")
        date_range_month_day = (
            insert('month:"')
            + month_names
            + insert('"')
            + optional_space
            + insert(' start_day:"')
            + day
            + insert('"')
            + to_connector
            + insert('end_day:"')
            + day
            + insert('"')
        )

        # Pattern 8: "from day to day month" (e.g., "from 13 to 15 July")
        date_range_from_day_month = (
            from_connector
            + insert('start_day:"')
            + day
            + insert('"')
            + to_connector
            + insert('end_day:"')
            + day
            + insert('"')
            + optional_space
            + insert('month:"')
            + month_names
            + insert('"')
        )

        # Pattern 9: "from the day to day month" (e.g., "from the 13 to 15 July")
        date_range_from_the_day = (
            from_connector
            + optional_space
            + delete("the")
            + optional_space
            + insert('start_day:"')
            + day
            + insert('"')
            + to_connector
            + insert('end_day:"')
            + day
            + insert('"')
            + optional_space
            + insert('month:"')
            + month_names
            + insert('"')
        )

        # Pattern 10: "from day to day of month" (e.g., "from 13 to 15 of July")
        date_range_from_day_of_month = (
            from_connector
            + insert('start_day:"')
            + day
            + insert('"')
            + to_connector
            + insert('end_day:"')
            + day
            + insert('"')
            + optional_space
            + delete("of")
            + optional_space
            + insert('month:"')
            + month_names
            + insert('"')
        )

        # Pattern 11: "from day to dayth of month" (e.g., "from 13 to 15th of July")
        # Handle ordinal suffixes like "th", "st", "nd", "rd"
        date_range_from_day_ordinal = (
            from_connector
            + insert('start_day:"')
            + day
            + insert('"')
            + to_connector
            + insert('end_day:"')
            + day
            + insert('"')
            + optional_space
            + delete("of")
            + optional_space
            + insert('month:"')
            + month_names
            + insert('"')
        )

        # Hyphen connector with optional spaces
        hyphen_connector = optional_space + delete(accep("-")) + optional_space

        # Date range patterns with hyphen
        # Pattern 12: "month day-day" (e.g., "July 13-15")
        # 修改字段名以匹配新的解析逻辑
        date_range_month_hyphen = (
            insert('start_month:"')
            + month_names
            + insert('"')
            + optional_space
            + insert('start_day:"')
            + day
            + insert('"')
            + hyphen_connector
            + insert('end_day:"')
            + day
            + insert('"')
        )

        # Pattern 13: "from month day-day" (e.g., "from July 13-15")
        date_range_from_month_hyphen = (
            from_connector
            + insert('month:"')
            + month_names
            + insert('"')
            + optional_space
            + insert('start_day:"')
            + day
            + insert('"')
            + hyphen_connector
            + insert('end_day:"')
            + day
            + insert('"')
        )

        # Pattern 13b: "month day - month day" (e.g., "July 13 - July 15")
        date_range_month_day_hyphen_month_day = (
            insert('start_month:"')
            + month_names
            + insert('"')
            + optional_space
            + insert('start_day:"')
            + day
            + insert('"')
            + hyphen_connector
            + insert('end_month:"')
            + month_names
            + insert('"')
            + optional_space
            + insert('end_day:"')
            + day
            + insert('"')
        )

        # Pattern 13: Universal "month day to month day" with optional modifiers and optional "from"
        # Supports all combinations:
        # - "april 3 to may 1"
        # - "from april 3 to may 1"
        # - "last year april 3 to may 1"
        # - "april 3 last year to may 1"
        # - "april 3 to may 1 this year"
        # - "april 3 last year to may 1 this year"
        # - "from april 3 last year to may 1 this year"
        date_range_universal_month_day_to_month_day = (
            from_connector.ques  # Optional "from"
            + optional_start_modifier  # Optional start modifier before month
            + insert('start_month:"')
            + month_names
            + insert('"')
            + optional_space
            + insert('start_day:"')
            + day
            + insert('"')
            # 添加可选的start_year字段（在day之后）  # noqa: E131
            + closure(
                optional_space + insert('start_year:"') + year_4digit + insert('"'),
                0,
                1,
            )
            + optional_start_modifier  # Optional start modifier after day
            + to_connector
            + optional_end_modifier  # Optional end modifier before month
            + insert('end_month:"')
            + month_names
            + insert('"')
            + optional_space
            + insert('end_day:"')
            + day
            + insert('"')
            # 添加可选的end_year字段（在day之后）  # noqa: E131
            + closure(optional_space + insert('end_year:"') + year_4digit + insert('"'), 0, 1)
            + optional_end_modifier  # Optional end modifier after day
        )

        # 移除年份修饰词支持以优化性能

        # Month numbers (1-12) for single hyphen date
        month_number = union(*[accep(str(i)) for i in range(1, 13)])

        # Pattern 14: "day-day" (e.g., "2-15" as February 15th)
        # This should be interpreted as month-day when standalone
        # Use different field names to avoid conflict with time patterns
        single_hyphen_date = (
            insert('date_month:"')
            + month_number
            + insert('"')
            + hyphen_connector
            + insert('date_day:"')
            + day
            + insert('"')
        )

        # Additional date range patterns
        # Pattern 16: "ordinal to ordinal month" (e.g., "23rd to 26th Oct")
        date_range_ordinal_to_ordinal_month = (
            insert('start_day:"')
            + day
            + insert('"')
            + to_connector
            + insert('end_day:"')
            + day
            + insert('"')
            + optional_space
            + insert('month:"')
            + month_names
            + insert('"')
        )

        # Pattern 16b: "month ordinal - ordinal" (e.g., "August 27th - 29th")
        date_range_month_ordinal_hyphen = (
            insert('month:"')
            + month_names
            + insert('"')
            + optional_space
            + insert('start_day:"')
            + day
            + insert('"')
            + hyphen_connector
            + insert('end_day:"')
            + day
            + insert('"')
        )

        # Pattern 17: "number to number month" (e.g., "12 to 16 september")
        date_range_number_to_number_month = (
            insert('start_day:"')
            + day
            + insert('"')
            + to_connector
            + insert('end_day:"')
            + day
            + insert('"')
            + optional_space
            + insert('month:"')
            + month_names
            + insert('"')
        )

        # ==== 通用连字符时间范围模式（高优先级） ====
        # 核心思路：连字符左右两侧各自是一个完整的时间表达式
        # 左侧：H[:MM[:SS]] [AM/PM]
        # 右侧：H[:MM[:SS]] [AM/PM]

        # 通用时间组件（支持可选的分钟、秒、AM/PM）
        # 起始时间：H[:MM[:SS]] [AM/PM]
        start_time_flexible = (
            insert('start_hour:"')
            + hour
            + insert('"')
            # 可选的分钟  # noqa: E131
            + closure(
                delete(union(accep(":"), accep("h")))  # 支持 ":" 或 "h" 作为分隔符
                + insert(' start_minute:"')
                + minute
                + insert('"')
                # 可选的秒  # noqa: E131
                + closure(
                    delete(union(accep(":"), accep("h")))  # 支持 ":" 或 "h" 作为分隔符
                    + insert(' start_second:"')
                    + minute
                    + insert('"'),  # 复用minute定义（00-59）
                    0,
                    1,
                ),
                0,
                1,
            )
            + start_period_optional
        )

        # 结束时间：H[:MM[:SS]] [AM/PM]
        end_time_flexible = (
            insert('end_hour:"')
            + hour
            + insert('"')
            # 可选的分钟  # noqa: E131
            + closure(
                delete(union(accep(":"), accep("h")))  # 支持 ":" 或 "h" 作为分隔符
                + insert(' end_minute:"')
                + minute
                + insert('"')
                # 可选的秒  # noqa: E131
                + closure(
                    delete(union(accep(":"), accep("h")))  # 支持 ":" 或 "h" 作为分隔符
                    + insert(' end_second:"')
                    + minute
                    + insert('"'),
                    0,
                    1,
                ),
                0,
                1,
            )
            + end_period_optional
        )

        # 通用连字符时间范围模式
        # Pattern: "TIME-TIME" 其中 TIME = H[:MM[:SS]] [AM/PM]
        time_hyphen_range_universal = start_time_flexible + hyphen_connector + end_time_flexible

        # Time range patterns with hyphen
        # Pattern 18: "H-H AM/PM" (e.g., "9-11am", "8am - 1pm")
        # MUST have AM/PM suffix to avoid conflicts with date patterns like "2-15"
        # 支持两种格式：
        # 1. "8am - 1pm" (每个时间都有独立的 AM/PM，输出 start_period 和 end_period)
        # 2. "9-11am" (共享 AM/PM，输出 period)
        # 注意：需要创建两个独立的模式，因为 FST 的 union 和 .ques 可能导致匹配歧义
        # 模式1：起始有 AM/PM，结束也有 AM/PM（输出 start_period 和 end_period）
        time_range_hyphen_with_both_periods = (
            insert('start_hour:"')
            + hour
            + insert('"')
            + insert(' start_minute:"00"')
            + start_period_required
            + hyphen_connector
            + insert('end_hour:"')
            + hour
            + insert('"')
            + insert(' end_minute:"00"')
            + end_period_required
        )

        # 模式2：起始没有 AM/PM，结束共享 AM/PM（输出 end_period，并保留 period 以兼容旧解析）
        time_range_hyphen_with_shared_period = (
            insert('start_hour:"')
            + hour
            + insert('"')
            + insert(' start_minute:"00"')
            + hyphen_connector
            + insert('end_hour:"')
            + hour
            + insert('"')
            + insert(' end_minute:"00"')
            + end_period_with_shared
        )

        # 合并两个模式
        # 注意：将 time_range_hyphen_with_both_periods 放在前面，确保优先匹配
        # 因为当输入中有起始和结束的 AM/PM 时，应该输出 start_period 和 end_period
        time_range_hyphen = (
            time_range_hyphen_with_both_periods | time_range_hyphen_with_shared_period
        )

        # ==== 专门的月-日模式（最高优先级） ====
        # 处理 "2-15" 这种纯数字格式，识别为月份-日期
        # 使用更严格的约束：月份必须是1-12，日期必须是1-31
        # 添加约束：第一个数字必须是1-12（月份），第二个数字必须是1-31（日期）

        # 为了确保优先级，我们使用权重来强制 month_day_pattern 优先匹配
        # 在 Pynini 中，权重越低，优先级越高
        # 设置较高优先级，确保 "2-15" 被识别为日期而不是时间

        # Combine patterns with priority (most specific first)
        # Prioritize atomic weekday patterns, then date ranges, then time ranges
        # Put UTC time ranges at the very beginning for ISO format support
        range_expr = (
            pynutil.add_weight(
                date_range_month_hyphen, -1.0
            )  # **最高优先级**：月份+日期范围 "July 13-15"
            | pynutil.add_weight(
                date_range_month_day_hyphen_month_day, -0.9
            )  # **高优先级**：月份+日期-月份+日期 "July 13 - July 15"
            | pynutil.add_weight(
                date_range_universal_month_day_to_month_day, -0.8
            )  # **高优先级**：通用月份+日期 to 月份+日期（支持修饰词和可选from）
            | utc_range_with_from  # ISO时间范围
            | utc_range_direct
            | pynutil.add_weight(single_hyphen_date, 0.5)  # "2-15" 作为日期（提高优先级）
            | pynutil.add_weight(
                time_hyphen_range_universal, 1.0
            )  # **NEW** 通用连字符时间范围（降低优先级）
            | time_h_from_to_h
            | time_hm_to_h_with_period
            | pynutil.add_weight(
                time_hm_range_with_from_on_weekday, 0.6
            )  # Lower priority to allow recurring rules to match complete expressions first
            | pynutil.add_weight(
                time_hm_till_hm_on_weekday, 0.6
            )  # Lower priority to avoid抢占复合型周期规则
            | pynutil.add_weight(
                time_hm_range_with_from, 0.6
            )  # Lower priority: still match standalone ranges but not ahead of recurring
            | time_hm_range
            | time_h_to_hm  # time_hm_to_h removed temporarily to avoid conflicts with "H:MM to H:MM" patterns  # noqa: W504, E261
            | date_range_ordinal_to_ordinal_month
            | date_range_month_ordinal_hyphen  # Add month ordinal hyphen pattern
            | date_range_number_to_number_month
            | date_range_from_month_hyphen
            | date_range_month_hyphen
            | date_range_from_day_ordinal
            | date_range_from_day_of_month
            | date_range_from_the_day
            | date_range_from_day_month
            | date_range_month_day
            | time_range_hyphen  # 旧的，可以考虑删除（被通用模式覆盖）
            | hour_range_simple  # Move hour_range_simple lower to avoid conflicts with date patterns
            | hour_range_oclock
        )

        # Add class wrapper and optimize - 直接使用词级pynutil.insert
        # 参考UTCTimeRule的实现：不使用self.add_tokens()，因为它可能在某些情况下使用错误的insert
        # 注意：TokenParser期望格式：time_range_expr { ... }（标记名和左花括号之间有空格）
        # 使用"time_range_expr { "格式，与UTCTimeRule保持一致
        tagger = (insert(f"{self.name} {{ ") + range_expr + insert(" }")).optimize()

        # 确保符号表被保留（optimize可能丢失符号表）
        # 强制设置GlobalSymbolTable，确保词级FST兼容性
        from ..global_symbol_table import get_symbol_table

        sym = get_symbol_table()
        tagger.set_input_symbols(sym)
        tagger.set_output_symbols(sym)

        self.tagger = tagger
