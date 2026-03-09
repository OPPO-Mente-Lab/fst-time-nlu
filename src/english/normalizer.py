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
import re
from typing import Any, Dict, List

import pynini
from importlib_resources import files
from pynini.lib.pynutil import add_weight

from ..core.processor import Processor
from ..core.logger import get_logger
from .rules import (
    UTCTimeRule,
    TokenRule,
    PeriodRule,
    WeekRule,
    RelativeRule,
    HolidayRule,
    CompositeRelativeRule,
    TimeRangeRule,
    RangeRule,
    FractionRule,
    CenturyRule,
    WhitelistRule,
    TimeDeltaRule,
    QuarterRule,
    RecurringRule,
)
from .word_tokenizer import EnglishWordTokenizer


class Normalizer(Processor):
    """
    English text normalizer for time expressions

    Provides FST-based normalization for English time expressions,
    handling text standardization and entity recognition.
    """

    def __init__(
        self,
        cache_dir=None,
        overwrite_cache=False,
        normalize_contractions=True,
        normalize_case=True,
        remove_puncts=False,
        use_word_level=True,
        include_source=True,
    ):
        """
        Initialize English text normalizer

        Args:
            cache_dir (str, optional): FST cache directory
            overwrite_cache (bool): Whether to rebuild FST cache
            normalize_contractions (bool): Whether to normalize contractions
            normalize_case (bool): Whether to normalize case
            remove_puncts (bool): Whether to remove punctuation
            use_word_level (bool): Whether to use word-level FST processing (default True)
            include_source (bool): Whether to include source field in tags (default True)
        """
        super().__init__(name="en_normalizer")
        self.logger = get_logger(__name__)
        self.include_source = include_source
        self.normalize_contractions = normalize_contractions
        self.normalize_case = normalize_case
        self.remove_puncts = remove_puncts

        # Initialize word-level tokenizer
        if use_word_level:
            try:
                self.word_tokenizer = EnglishWordTokenizer()
                self.logger.info(
                    f"词级FST已启用，SymbolTable大小: {self.word_tokenizer.sym.num_symbols()}"
                )
                self.logger.info("逐步转换规则中，当前已支持：TokenRule")
            except Exception as e:
                self.logger.warning(f"词级FST初始化失败，回退到字符级: {e}")
                self.word_tokenizer = None
        else:
            self.word_tokenizer = None

        # Override time hint pattern for English
        self._time_hint_pattern = re.compile(
            r"(am|pm|a\.m\.|p\.m\.|morning|afternoon|evening|night|noon|midnight|"
            r"today|tomorrow|yesterday|monday|tuesday|wednesday|thursday|friday|saturday|sunday|"
            r"january|february|march|april|may|june|july|august|september|october|november|december|"
            r"jan|feb|mar|apr|jun|jul|aug|sep|oct|nov|dec|"
            r"recently|lately|"
            r"\d{1,2}[.:：]\d{1,2}|\d{1,2}\s*(?:am|pm)|week|month|year|day|hour|minute|second)",
            re.IGNORECASE,
        )

        if cache_dir is None:
            # 使用默认缓存目录：src/english/test/fst
            cache_dir = os.path.join(os.path.dirname(__file__), "test", "fst")
        self.build_fst("en_tn", cache_dir, overwrite_cache)

    def _preprocess_text(self, text: str) -> str:
        """
        Preprocess English text before FST processing

        Args:
            text (str): Input text

        Returns:
            str: Preprocessed text
        """
        if not text:
            return ""

        # Convert to lowercase for consistency
        text = text.lower()

        # Protect BC/AD abbreviations before punctuation normalization
        text = text.replace("b.c.", "bc")
        text = text.replace("a.d.", "ad")

        # Protect date formats before punctuation normalization
        date_pattern = re.compile(r"\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b")
        text = date_pattern.sub(r"\1-\2-\3", text)

        # Handle common contractions and abbreviations
        contractions = {
            "can't": "cannot",
            "won't": "will not",
            "n't": " not",
            "'ll": " will",
            "'re": " are",
            "'ve": " have",
            "'d": " would",
            "'m": " am",
            "o'clock": "oclock",
        }

        for contraction, expansion in contractions.items():
            text = text.replace(contraction, expansion)

        # Normalize punctuation
        text = text.replace(",", " ")
        # Only replace dots that are not part of decimals (i.e., not between digits)
        text = re.sub(r"(?<!\d)\.(?!\d)", " ", text)
        text = text.replace(";", " ")
        # Keep colons for time expressions (e.g., "14:31")
        # text = text.replace(":", " ")  # Commented out - FST handles colons

        # Remove extra whitespace
        text = " ".join(text.split())

        return text

    def tag(self, text: str) -> List[Dict[str, Any]]:
        """
        重写tag方法以调用预处理

        Args:
            text (str): Input text

        Returns:
            List[Dict[str, Any]]: Tagged tokens
        """
        if not text:
            return []

        # 调用预处理
        preprocessed_text = self._preprocess_text(text)

        # 调用父类的tag方法
        return super().tag(preprocessed_text)

    def _tag_single(self, text: str) -> List[Dict[str, Any]]:  # noqa: C901
        """对单段文本执行一次FST解码并解析为token字典列表（词级FST版本）"""
        unknown_chars = []  # 保存未知字符列表
        # 词级处理：如果有word_tokenizer，使用词级FST
        if self.word_tokenizer:
            try:
                # 在process_text之前重置tokenizer状态
                self.word_tokenizer.reset_stats()
                escaped_text = self.word_tokenizer.process_text(text)
                # 获取未知字符列表
                unknown_chars = self.word_tokenizer.get_unknown_chars()

                # 检查符号表兼容性：词级FST必须有符号表，且tagger也必须有相同的符号表
                input_sym = escaped_text.input_symbols()
                tagger_input_sym = self.tagger.input_symbols()

                # 如果escaped_text有符号表（词级FST），但tagger没有（字符级FST），需要回退
                if input_sym and not tagger_input_sym:
                    # tagger是字符级，回退到字符级输入
                    # 使用accep构建字符级FST（pynini.escape返回字符串，不是FST）
                    escaped_text = pynini.accep(text)
                elif input_sym and tagger_input_sym:
                    # 都有符号表：检查符号表是否兼容（使用数量比较，因为SymbolTableView的==可能不准确）
                    # 如果符号表数量相同，认为兼容（都是词级FST）
                    if input_sym.num_symbols() != tagger_input_sym.num_symbols():
                        # 符号表数量不匹配，回退到字符级
                        # 使用accep构建字符级FST（pynini.escape返回字符串，不是FST）
                        escaped_text = pynini.accep(text)
                    # 如果数量相同，认为兼容，继续使用词级FST
                # 如果都没有符号表，说明都是字符级，可以继续

            except Exception as e:
                # 如果词级处理失败，回退到字符级
                import logging

                logger = logging.getLogger(f"fst_time-{self.name}")
                logger.debug(f"词级处理失败，回退到字符级: {e}")
                # 使用accep构建字符级FST（pynini.escape返回字符串，不是FST）
                escaped_text = pynini.accep(text)
        else:
            # 回退到字符级处理
            # 使用accep构建字符级FST（pynini.escape返回字符串，不是FST）
            escaped_text = pynini.accep(text)

        try:
            lattice = escaped_text @ self.tagger

            # 检查lattice是否有效
            if lattice.num_states() == 0:
                # 空lattice，没有匹配
                return []

            from pynini import shortestpath

            shortest = shortestpath(lattice, nshortest=1)

            # 检查shortest是否有效
            if shortest.num_states() == 0:
                # 没有路径
                return []

            input_string = None  # 输入字符串（用于对齐）
            # 词级FST：使用string(token_type=sym)提取输出（Pynini官方方法）
            if self.word_tokenizer and shortest.output_symbols():
                try:
                    # 使用Pynini官方词级FST输出提取方法
                    sym = shortest.output_symbols()
                    tagged_text = shortest.string(token_type=sym)
                    # 提取输入字符串（词级FST）
                    input_sym = shortest.input_symbols()
                    if input_sym:
                        input_string = shortest.string(token_type=input_sym)
                except Exception as e:
                    # 如果string(token_type=sym)失败，记录错误并返回空
                    import logging

                    logger = logging.getLogger(f"fst_time-{self.name}")
                    logger.warning(f"词级FST string(token_type=sym)失败: {e}, 文本: {text[:50]}")
                    return []
            else:
                # 字符级FST：使用string()方法
                try:
                    tagged_text = shortest.string()
                    # 字符级FST：输入就是原始文本
                    input_string = text
                except Exception as e:
                    import logging

                    logger = logging.getLogger(f"fst_time-{self.name}")
                    logger.warning(f"FST string()失败: {e}, 文本: {text[:50]}")
                    return []

            if not tagged_text:
                return []

            tags = self.parse_tags(tagged_text, input_text=text, input_string=input_string,
                                  token_positions=None, is_word_level=bool(self.word_tokenizer),
                                  include_source=self.include_source)
            
            # 处理unknown_char：将__unknown_char__替换为实际字符
            # TokenRule输出格式为token{value:"__unknown_char__"}，需要处理
            if unknown_chars and self.word_tokenizer:
                unknown_char_index = 0
                for tag in tags:
                    # 检查token类型和char类型的unknown_char
                    if tag.get("type") in ("token", "char") and tag.get("value") == "__unknown_char__":
                        if unknown_char_index < len(unknown_chars):
                            tag["value"] = unknown_chars[unknown_char_index]
                            # 如果是token类型，改为char类型（更符合语义）
                            if tag.get("type") == "token":
                                tag["type"] = "char"
                            unknown_char_index += 1
                        else:
                            # 如果未知字符列表已用完，保留占位符（这种情况不应该发生）
                            import logging
                            logger = logging.getLogger(f"fst_time-{self.name}")
                            logger.warning(
                                f"未知字符列表已用完，但仍有__unknown_char__需要替换, 文本: {text[:50]}"
                            )
            
            return tags
        except Exception as e:
            import logging

            logger = logging.getLogger(f"fst_time-{self.name}")
            logger.warning(f"FST匹配失败: {e}, 文本: {text[:50]}")
            # 返回空列表而不是抛出异常
            return []

    def build_tagger(self):
        """Build English FST tagger"""

        # Initialize preprocessor if needed
        # processor = PreProcessor(
        #     normalize_contractions=self.normalize_contractions,
        #     normalize_case=self.normalize_case).processor

        # Build all rule taggers with weights (lower weight = higher priority)
        fraction = add_weight(
            FractionRule().tagger, 0.3
        )  # Very high priority - prevent fraction from being recognized as time
        range_expr = add_weight(
            RangeRule().tagger, 0.31
        )  # VERY HIGH priority - atomic time range patterns to prevent tokenization errors (must be before UTCTimeRule)
        utctime = add_weight(
            UTCTimeRule().tagger, 0.32
        )  # High priority，确保日期格式（如 2-15, 10.31.1974）优先匹配，但低于RangeRule
        whitelist = add_weight(
            WhitelistRule().tagger, 0.4
        )  # High priority - prevent whitelist phrases from being recognized as time
        time_delta = add_weight(
            TimeDeltaRule().tagger, 0.45
        )  # Time delta expressions like "in 10 minutes" - high priority to prevent "2.5" being recognized as date
        recurring = add_weight(
            RecurringRule().tagger, 1.5
        )  # Recurring expressions like "every monday" - moderate priority (requires prefix)
        weekday = add_weight(
            WeekRule().tagger, 0.7
        )  # Week-related expressions (increased priority)
        holiday = add_weight(HolidayRule().tagger, 0.8)  # Holiday expressions (increased priority)
        period = add_weight(
            PeriodRule().tagger, 0.9
        )  # Time periods like morning, lunch (increased priority)
        quarter = add_weight(QuarterRule().tagger, 0.95)  # Quarter expressions like Q1, 3rd quarter
        composite_relative = add_weight(CompositeRelativeRule().tagger, 1.00)  # Composite patterns
        century = add_weight(CenturyRule().tagger, 1.01)  # Century and decade expressions
        time_range = add_weight(
            TimeRangeRule().tagger, 1.04
        )  # Time range adverbs like recently, lately
        relative = add_weight(RelativeRule().tagger, 1.05)  # Relative time like yesterday, today
        token = add_weight(TokenRule().tagger, 100)  # Lowest priority fallback

        # Combine all taggers with priority ordering (token is needed to match non-time words)
        # 注：未知字符的处理已在tokenizer层面完成（过滤掉不在符号表中的字符）
        combined = (
            fraction
            | utctime
            | range_expr
            | whitelist
            | time_delta
            | recurring
            | weekday
            | holiday
            | period
            | quarter
            | composite_relative
            | century
            | time_range
            | relative
            | token
        ).optimize()

        # Apply star repetition for multiple matches - 重复匹配多个token
        # 词级FST：使用closure而不是.star，避免weight问题
        tagger = combined.star

        # Delete the last space and apply final optimizations
        # 词级FST：使用词级DELETE_SPACE，避免字符级和词级FST混合
        if self.word_tokenizer:
            from .word_level_pynini import word_delete_space

            word_delete_space()  # 词级模式下，跳过cdrewrite操作（避免字符级和词级FST混合）
        else:
            tagger = tagger @ self.build_rule(self.DELETE_SPACE, r="[EOS]")

        # Apply rmepsilon to remove epsilon transitions, then optimize
        # Note: We cannot determinize or minimize weighted FSTs with multiple paths
        tagger = tagger.rmepsilon().optimize()

        # 词级FST：确保最终tagger有符号表（union/optimize可能丢失符号表）
        # 强制设置GlobalSymbolTable，确保词级输入FST能正确匹配
        if self.word_tokenizer:
            from .global_symbol_table import get_symbol_table

            sym = get_symbol_table()
            # 强制设置GlobalSymbolTable（不依赖条件判断，因为SymbolTableView比较可能不准确）
            tagger.set_input_symbols(sym)
            tagger.set_output_symbols(sym)

        self.tagger = tagger
