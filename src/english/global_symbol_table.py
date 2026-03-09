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
全局SymbolTable单例

所有英文FST规则共享同一个词级SymbolTable，确保compose操作兼容。
"""

import pynini
import os
import threading
from ..core.logger import get_logger


class GlobalSymbolTable:
    """
    全局SymbolTable单例

    确保整个应用中所有FST规则使用相同的SymbolTable，
    使得词级输入FST和词级规则FST可以正确compose。
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        """初始化SymbolTable"""
        self.logger = get_logger(__name__)
        self.sym = pynini.SymbolTable()
        self.sym.add_symbol("<eps>", 0)

        # 加载词汇表
        self._load_vocabulary()

        # 添加数字和标点
        self._add_special_chars()

        self.logger.info(f"GlobalSymbolTable已初始化: {self.sym.num_symbols()}个符号")

    def _load_vocabulary(self):  # noqa: C901
        """加载词汇表"""
        current_dir = os.path.dirname(__file__)

        # 加载主词汇表
        vocab_file = os.path.join(current_dir, "data", "vocabulary_complete.txt")
        if os.path.exists(vocab_file):
            with open(vocab_file, "r", encoding="utf-8") as f:
                for line in f:
                    word = line.strip()
                    if word and word.isalpha():
                        if self.sym.find(word) == -1:
                            self.sym.add_symbol(word)

        # 加载复合词（带连字符、点等）
        compound_file = os.path.join(current_dir, "data", "compound_words.txt")
        if os.path.exists(compound_file):
            with open(compound_file, "r", encoding="utf-8") as f:
                for line in f:
                    word = line.strip()
                    if word:
                        if self.sym.find(word) == -1:
                            self.sym.add_symbol(word)

        # 加载所有TSV文件中的token（关键！）
        tsv_tokens_file = os.path.join(current_dir, "data", "all_tsv_tokens.txt")
        if os.path.exists(tsv_tokens_file):
            with open(tsv_tokens_file, "r", encoding="utf-8") as f:
                for line in f:
                    token = line.strip()
                    if token:
                        if self.sym.find(token) == -1:
                            self.sym.add_symbol(token)

    def _add_special_chars(self):  # noqa: C901
        """添加数字和标点符号"""
        # 单位数字 0-9
        for i in range(10):
            char = str(i)
            if self.sym.find(char) == -1:
                self.sym.add_symbol(char)

        # 多位数字 00-99（用于日期、时间等）
        for i in range(100):
            num_str = str(i)
            if self.sym.find(num_str) == -1:
                self.sym.add_symbol(num_str)

        # 前导零数字 00-09
        for i in range(10):
            num_str = f"{i:02d}"
            if self.sym.find(num_str) == -1:
                self.sym.add_symbol(num_str)

        # 三位数 100-999（用于保持SymbolTable稳定，避免运行时动态添加）
        for i in range(100, 1000):
            num_str = str(i)
            if self.sym.find(num_str) == -1:
                self.sym.add_symbol(num_str)

        # 年份范围 1900-2100
        for year in range(1900, 2101):
            year_str = str(year)
            if self.sym.find(year_str) == -1:
                self.sym.add_symbol(year_str)

        # 常见标点（包含花括号和全角标点，以及反斜杠等特殊字符）
        punctuations = [
            ":",
            "-",
            "/",
            ".",
            ",",
            "'",
            '"',
            "(",
            ")",
            " ",
            "!",
            "?",
            ";",
            "_",
            "+",
            "=",
            "@",
            "#",
            "$",
            "%",
            "&",
            "*",
            "|",
            "{",
            "}",
            "[",
            "]",
            "\\",
            "<",
            ">",
            "~",
            "`",
            "^",
            "：",
            "、",
            "。",
            "，",
            "；",
            "！",
            "？",
            "（",
            "）",
            "【",
            "】",
            "《",
            "》",
        ]  # 全角标点
        for p in punctuations:
            if self.sym.find(p) == -1:
                self.sym.add_symbol(p)

        # 所有格和缩写形式（重要：用于识别tomorrow's, year's等）
        possessive_and_contractions = [
            "'s",
            "'t",
            "'m",
            "'ve",
            "'d",
            "'ll",
            "'re",
            "'nt",  # 常见缩写
            "n't",  # not的缩写
        ]
        for form in possessive_and_contractions:
            if self.sym.find(form) == -1:
                self.sym.add_symbol(form)

        # 特殊输出格式（用于TSV输出）
        special_outputs = ["A.M.", "P.M.", "a.m.", "p.m."]
        for s in special_outputs:
            if self.sym.find(s) == -1:
                self.sym.add_symbol(s)

        # 单字母（大写，用于缩写如时区 C S T）
        for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            if self.sym.find(letter) == -1:
                self.sym.add_symbol(letter)

        # 单字母（小写，用于字符级回退）
        for letter in "abcdefghijklmnopqrstuvwxyz":
            if self.sym.find(letter) == -1:
                self.sym.add_symbol(letter)

        # 负数（用于offset）
        for i in range(-10, 0):
            num_str = str(i)
            if self.sym.find(num_str) == -1:
                self.sym.add_symbol(num_str)

        # 特殊格式
        special_formats = [
            "5,6",
            "early_morning",
            "late_morning",
            "mid_morning",
            "early_afternoon",
            "late_afternoon",
            "mid_afternoon",
            "early_evening",
            "late_evening",
            "early_night",
            "late_night",
            "'s",
            "'",  # 撇号相关
            "bom",
            "eom",
            "eoy",
            "eod",  # 缩写：Beginning/End of Month/Year/Day
            "BOM",
            "EOM",
            "EOY",
            "EOD",  # 大写版本
            "sec",
            "secs",  # second 缩写
            "__long_number__",  # 长数字占位符
            "__unknown_char__",  # 未知字符占位符（用于标记不在SymbolTable中的字符）
        ]
        for s in special_formats:
            if self.sym.find(s) == -1:
                self.sym.add_symbol(s)

        # FST输出标签（关键！）
        output_tags = [
            "offset_day:",
            "offset_month:",
            "offset_year:",
            "offset_week:",
            "offset_time:",
            "week_day:",
            "week_period:",
            "is_tonight:",
            "type:",
            "time_relative",
            "time_weekday",
            "utc",
            "period",
            "hours:",
            "minutes:",
            "period:",
            "timezone:",
            "year:",
            "month:",
            "day:",
            "hour:",
            "minute:",
            "second:",
            "year_suffix:",
            "value:",
            "token:",
            "recurring_type:",
            "interval:",
            "range:",
            "delta:",
            "holiday:",
            "festival:",
            "offset:",
            "unit:",
            "offset_direction:",
            "range_days:",
            "month_period:",
            "week_order:",
            "month_order:",
            "quarter:",
            "century_num:",
            "decade:",
            "modifier:",
            "day_prefix:",
            "weekday:",
            "modifier_year:",
            "modifier_month:",
            "ordinal_position:",
            "relation:",
            "season:",
            "ordinal:",
            "boundary:",
            "position:",
            "time_modifier:",
            # 时间类型标签
            "time_utc",
            "time_am",
            "time_pm",
            "time_range",
            "time_delta",
            # 规则类名标签（用于add_tokens包装）
            "time_recurring",
            "time_period",
            "time_holiday",
            "time_composite",
            "time_century",
            "time_quarter",
            "time_whitelist",
            "time_fraction",
            "time_composite_relative",  # CompositeRelativeRule的类名
            "token",  # TokenRule的类名
            "month_period",
            "offset_direction",
            "time_modifier",  # 缺失的属性标签
            # 引号
            '"',
            '""',
            # 历史纪年和时区
            "BC",
            "AD",
            "BCE",
            "CE",
            "UTC",
            "GMT",
            "EST",
            "PST",
            "CST",
            "MST",
        ]
        for tag in output_tags:
            if self.sym.find(tag) == -1:
                self.sym.add_symbol(tag)

        # FST输出属性值（从TSV文件中提取的值）
        output_values = [
            # 时间段值
            "morning",
            "afternoon",
            "evening",
            "night",
            "noon",
            "midnight",
            "dawn",
            "dusk",
            "twilight",
            "sunrise",
            "sunset",
            "tonight",
            # 扩展时间段
            "early_morning",
            "late_morning",
            "mid_morning",
            "early_afternoon",
            "late_afternoon",
            "mid_afternoon",
            "early_evening",
            "late_evening",
            "early_night",
            "late_night",
            # 频率词
            "daily",
            "weekly",
            "monthly",
            "yearly",
            "hourly",
            "regularly",
            "frequently",
            "occasionally",
            "sometimes",
            "always",
            "never",
            # 季节
            "spring",
            "summer",
            "autumn",
            "winter",
            "fall",
            # 月份前缀
            "earlymonth",
            "midmonth",
            "latemonth",
            # 时间单位相关词
            "fortnight",
            "fortnights",  # 两周（14天）
            # 连接词（用于时间范围）
            "thru",  # "July 13 thru 15"
            # 其他值
            "season",
            "-1",
            "-2",
            "0",
            "1",
            "2",
        ]
        for val in output_values:
            if self.sym.find(val) == -1:
                self.sym.add_symbol(val)
        for tag in output_tags:
            if self.sym.find(tag) == -1:
                self.sym.add_symbol(tag)

        # FST输出格式token（避免拆分导致空格）
        # 这些token用于word_insert，确保整个字符串作为单个token匹配
        fst_output_tokens = [
            # 属性格式（key:"格式）
            'noon:"',
            'month:"',
            'day:"',
            'year:"',
            'hour:"',
            'minute:"',
            'second:"',
            'offset_day:"',
            'offset_month:"',
            'offset_year:"',
            'offset_week:"',
            'offset_time:"',
            'week_day:"',
            'week_period:"',
            'is_tonight:"',
            'hours:"',
            'minutes:"',
            'period:"',
            'timezone:"',
            'value:"',
            'token:"',
            'recurring_type:"',
            'interval:"',
            'range:"',
            'delta:"',
            'holiday:"',
            'festival:"',
            'offset:"',
            'unit:"',
            'offset_direction:"',
            'range_days:"',
            'month_period:"',
            'week_order:"',
            'month_order:"',
            'quarter:"',
            'century_num:"',
            'decade:"',
            'modifier:"',
            'day_prefix:"',
            'weekday:"',
            'modifier_year:"',
            'modifier_month:"',
            'ordinal_position:"',
            'relation:"',
            'season:"',
            'ordinal:"',
            'boundary:"',
            'position:"',
            'time_modifier:"',
            'year_suffix:"',
            ' year_suffix:"',
            # 范围字段格式（start_/end_前缀）
            'start_hour:"',
            'end_hour:"',
            'start_minute:"',
            'end_minute:"',
            'start_month:"',
            'end_month:"',
            'start_day:"',
            'end_day:"',
            'start_year:"',
            'end_year:"',
            'start_modifier:"',
            'end_modifier:"',
            # 其他字段格式
            'date_month:"',
            'date_day:"',
            'raw_type:"',
            'negative:"',
            'denominator:"',
            'numerator:"',
            'direction:"',
            'week:"',
            # 类名包装格式（class_name{格式）
            "time_period{",
            "time_utc{",
            "time_relative{",
            "time_weekday{",
            # 添加带空格格式的token（用于兼容TokenParser）
            "time_relative {",
            "time_utc {",
            "time_weekday {",
            "time_period {",
            "quarter_rule {",  # QuarterRule的token类型
            "time_holiday{",
            "time_delta{",
            "time_lunar{",
            "time_between{",
            "time_recurring{",
            "time_composite{",
            "time_century{",
            "time_quarter{",
            "time_whitelist{",
            "time_fraction{",
            "time_composite_relative{",
            "time_range_expr{",
            "time_range_expr {",  # RangeRule类名包装格式
            "fraction{",
            "fraction {",
            "time_fraction {",
            "token{",
            # 结束标记（不同格式）
            "}",
            " }",
            " } ",
            # 引号结束标记
            '"',
            ' "',
        ]
        for token in fst_output_tokens:
            if self.sym.find(token) == -1:
                self.sym.add_symbol(token)


# 全局单例实例
_global_sym_table = None


def get_symbol_table() -> pynini.SymbolTable:
    """
    获取全局SymbolTable

    Returns:
        pynini.SymbolTable: 全局词级SymbolTable
    """
    global _global_sym_table
    if _global_sym_table is None:
        _global_sym_table = GlobalSymbolTable()
    return _global_sym_table.sym


# 为了方便，导出一个全局变量
GLOBAL_SYM = None


def initialize_global_symbol_table():
    """
    显式初始化全局SymbolTable

    在应用启动时调用，确保所有规则使用相同的SymbolTable
    """
    global GLOBAL_SYM
    if GLOBAL_SYM is None:
        GLOBAL_SYM = get_symbol_table()
    return GLOBAL_SYM


# 测试代码
if __name__ == "__main__":
    print("=" * 80)
    print("测试GlobalSymbolTable")
    print("=" * 80)
    print()

    # 测试单例
    sym1 = get_symbol_table()
    sym2 = get_symbol_table()

    print(f"sym1 == sym2: {sym1 == sym2} (应该是True)")
    print(f"SymbolTable大小: {sym1.num_symbols()}")
    print()

    # 测试词汇查找
    test_words = ["tomorrow", "monday", "next", "at", "3", ":", "xyz"]
    print("测试词汇查找:")
    for word in test_words:
        id = sym1.find(word)
        status = "✓" if id != -1 else "✗"
        print(f'  {status} "{word}": ID={id}')
