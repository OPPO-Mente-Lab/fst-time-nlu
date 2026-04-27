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

# -*- coding: utf-8 -*-
"""中文词级SymbolTable单例。

参考英文实现，收集规则与tokenizer需要的全部token，确保所有词级FST共享同一份符号表。"""

from __future__ import annotations

import json
import os
import threading

import pynini
from ..core.logger import get_logger


class GlobalSymbolTable:
    _instance: "GlobalSymbolTable" | None = None
    _lock = threading.Lock()
    _TOKEN_FILE = os.path.join(
        os.path.dirname(__file__),
        "data",
        "generated",
        "zh_symbol_table_tokens.jsonl",
    )

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialize()
        return cls._instance

    # ------------------------------------------------------------------
    # 初始化
    # ------------------------------------------------------------------
    def _initialize(self) -> None:
        self.logger = get_logger(__name__)
        self.sym = pynini.SymbolTable()
        self.sym.add_symbol("<eps>", 0)

        self._input_tokens = self._collect_input_tokens()
        tokens = self._load_tokens_from_file()
        for token in tokens:
            self._add_token(token)

        self._add_output_tokens()

        self.logger.info(f"GlobalSymbolTable(zh)已初始化: {self.sym.num_symbols()}个符号")

    # ------------------------------------------------------------------
    # 从生成的 jsonl 文件读取 token
    # ------------------------------------------------------------------
    def _load_tokens_from_file(self) -> list[str]:
        if not os.path.exists(self._TOKEN_FILE):
            raise FileNotFoundError(
                f"未找到符号表 token 文件: {self._TOKEN_FILE}\n"
                "请先运行 scripts/build_zh_symbol_table.py 生成最新列表。"
            )

        tokens: list[str] = []
        with open(self._TOKEN_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    token = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(token, str):
                    continue
                if token == "<eps>":
                    # `<eps>` 已经手动添加
                    continue
                tokens.append(token)
        return tokens

    # ------------------------------------------------------------------
    # 输出相关token
    # ------------------------------------------------------------------
    def _add_output_tokens(self) -> None:
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
            "period:",
            "hours:",
            "minutes:",
            "timezone:",
            "year:",
            "month:",
            "day:",
            "hour:",
            "minute:",
            "second:",
            "value:",
            "token:",
            "recurring_type:",
            "interval:",
            "range:",
            "delta:",
            "holiday:",
            "festival:",
            "value2:",
            "offset:",
            "unit:",
            "offset_direction:",
            "range_days:",
            "month_period:",
            "week_order:",
            "month_order:",
            "offset_quarter:",
            "quarter:",
            "century_num:",
            "decade:",
            "modifier:",
            "day_prefix:",
            "year_period:",
            "weekday:",
            "modifier_year:",
            "modifier_month:",
            "ordinal_position:",
            "period_word:",
            "relation:",
            "season:",
            "ordinal:",
            "boundary:",
            "position:",
            "time_modifier:",
            "year_suffix:",
            "fraction:",
            "duration:",
            "noon:",
            "past_key:",
            "fractional:",
            "year2:",
            "month2:",
            "day2:",
            "hour2:",
            "offset_year2:",
            "lunar_year:",
            "lunar_month:",
            "lunar_day:",
            "lunar_month_prefix:",
            "lunar_year_prefix:",
            "lunar_jieqi:",
            "day_pre:",
        ]
        for tag in output_tags:
            self._add_token(tag)

        # 添加ISO 8601格式需要的两位数字 (00-59)
        # 这些数字在hour_digit.tsv, minute_digit.tsv, second_digit.tsv,
        # month_digit.tsv, day_digit.tsv中定义，但_simple_tokenize会将它们拆分
        # 所以需要在这里手动添加到符号表中
        for i in range(60):
            two_digit = f"{i:02d}"  # 00, 01, 02, ..., 59
            self._add_token(two_digit)

        fst_output_tokens = [
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
            'offset_quarter:"',
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
            'value2:"',
            'offset:"',
            'unit:"',
            'offset_direction:"',
            'range_days:"',
            'month_period:"',
            'week_order:"',
            'month_order:"',
            'year_period:"',
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
            'decade_num:"',
            'year_suffix:"',
            ' year_suffix:"',
            'fraction:"',
            'duration:"',
            'noon:"',
            'past_key:"',
            'fractional:"',
            'period_word:"',
            'year2:"',
            'month2:"',
            'day2:"',
            'hour2:"',
            'offset_year2:"',
            'lunar_year:"',
            'lunar_month:"',
            'lunar_day:"',
            'lunar_month_prefix:"',
            'lunar_year_prefix:"',
            'lunar_jieqi:"',
            'day_pre:"',
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
            'date_month:"',
            'date_day:"',
            'raw_type:"',
            'negative:"',
            'denominator:"',
            'numerator:"',
            'direction:"',
            'week:"',
            "time_period{",
            "time_utc{",
            "time_relative{",
            "time_weekday{",
            "time_relative {",
            "time_utc {",
            "time_weekday {",
            "time_period {",
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
            "time_range_expr {",
            "fraction{",
            "fraction {",
            "}",
            " }",
            " } ",
            '"',
            ' "',
            'char { value: "none" }',  # 🔧 固定的char标记，避免动态添加符号
        ]
        for token in fst_output_tokens:
            self._add_token(token)

        # 额外添加插入时可能出现但未包含的纯词元
        supplemental_tokens = [
            "special_time",
            "offset_day",
            "offset_month",
            "offset_year",
            "offset_week",
            "offset_time",
            "week_day",
            "week_period",
            "is_tonight",
            "recurring_type",
            "interval",
            "range",
            "delta",
            "holiday",
            "festival",
            "offset",
            "unit",
            "offset_direction",
            "range_days",
            "month_period",
            "week_order",
            "month_order",
            "range_type",
            "interval_time",
            "quarter",
            "century_num",
            "decade",
            "modifier",
            "day_prefix",
            "weekday",
            "modifier_year",
            "modifier_month",
            "ordinal_position",
            "relation",
            "season",
            "ordinal",
            "boundary",
            "position",
            "time_modifier",
            "year_suffix",
            "fraction",
            "duration",
            "noon",
            "past_key",
            "year",
            "month",
            "day",
            "hour",
            "minute",
            "second",
            "week",
            "holiday",
            "value",
            "token",
            "compact_format",
            "yyyymmdd",
            "yyyymm-dd",
            "raw_type",
            "gb",
            "mb",
            "tb",
            "kw",
            "kwh",
            "wh",
            "past",
            "offset_quarter",
            "time_utc",
            "time_relative",
            "time_period",
            "time_weekday",
            "time_delta",
            "time_recurring",
            "time_range_expr",
            "time_composite",
            "time_fraction",
            "time_holiday",
            "time_quarter",
            "time_century",
            "decade_num",
            "fractional",
            "time_between",
            "time_range",
            "lunar_year",
            "lunar_month",
            "lunar_day",
            "lunar_month_prefix",
            "lunar_year_prefix",
            "lunar_jieqi",
            "day_pre",
            "relative",
            "lunar",
            "future",
            "value2",
            "time_lunar",
            "whitelist",
            "day_time",
            "year_time",
            "month_time",
            "year_holiday",
            "year_season",
            "month_day",
            "week_day",
            "year_month",
            "year2",
            "month2",
            "day2",
            "hour2",
            "offset_year2",
            "decimal",
            "year_period",
            "period_word",
            'char{value:"',
            '"}',  # 用于skip_rule的固定token
            "__long_number__",  # 长数字占位符
            "__unknown_char__",  # 未知字符占位符
        ]
        for token in supplemental_tokens:
            self._add_token(token)

    # ------------------------------------------------------------------
    def _add_token(self, token: str) -> None:
        if not token:
            return
        if self.sym.find(token) == -1:
            self.sym.add_symbol(token)

    def get_input_tokens(self) -> set[str]:
        return self._input_tokens

    def _collect_input_tokens(self) -> set[str]:  # noqa: C901
        tokens: set[str] = set()
        data_dir = os.path.join(os.path.dirname(__file__), "data")
        if not os.path.isdir(data_dir):
            return tokens

        for root, _dirs, files in os.walk(data_dir):
            for filename in files:
                if not filename.endswith(".tsv"):
                    continue
                path = os.path.join(root, filename)
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        for line in f:
                            line = line.strip()
                            if not line or line.startswith("#"):
                                continue
                            for field in line.split("\t"):
                                field = field.strip()
                                if not field:
                                    continue
                                for tok in self._simple_tokenize(field):
                                    if tok and not tok.isspace():
                                        tokens.add(tok)
                except UnicodeDecodeError:
                    continue

        tokens.add(" ")
        return tokens

    @staticmethod
    def _simple_tokenize(text: str) -> list[str]:  # noqa: C901
        tokens: list[str] = []
        i = 0
        length = len(text)
        while i < length:
            ch = text[i]
            if ch.isspace():
                tokens.append(" ")
                i += 1
                continue
            code = ord(ch)
            is_chinese = (
                0x4E00 <= code <= 0x9FFF or 0x3400 <= code <= 0x4DBF or 0x20000 <= code <= 0x2A6DF
            )
            if is_chinese:
                tokens.append(ch)
                i += 1
                continue
            if ch.isdigit():
                j = i + 1
                while j < length and text[j].isdigit():
                    j += 1
                if j < length and text[j] == "." and (j + 1) < length and text[j + 1].isdigit():
                    k = j + 1
                    while k < length and text[k].isdigit():
                        k += 1
                    tokens.append(text[i:k])
                    i = k
                    continue
                while i < j:
                    tokens.append(text[i])
                    i += 1
                continue
            if ("A" <= ch <= "Z") or ("a" <= ch <= "z"):
                j = i + 1
                while j < length:
                    cj = text[j]
                    if (
                        ("A" <= cj <= "Z")
                        or ("a" <= cj <= "z")
                        or cj.isdigit()
                        or cj in {"'", "-", "_"}
                    ):
                        j += 1
                    else:
                        break
                tokens.append(text[i:j].lower())
                i = j
                continue
            tokens.append(ch)
            i += 1
        return tokens


_GLOBAL_SYM: pynini.SymbolTable | None = None
_INPUT_TOKENS: set[str] | None = None


def get_symbol_table() -> pynini.SymbolTable:
    global _GLOBAL_SYM
    global _INPUT_TOKENS
    if _GLOBAL_SYM is None:
        gst = GlobalSymbolTable()
        _GLOBAL_SYM = gst.sym
        _INPUT_TOKENS = gst.get_input_tokens()
    return _GLOBAL_SYM


def get_input_tokens() -> set[str]:
    if _INPUT_TOKENS is None:
        get_symbol_table()
    return _INPUT_TOKENS or set()


def initialize_global_symbol_table() -> pynini.SymbolTable:
    return get_symbol_table()
