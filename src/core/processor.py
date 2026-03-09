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

"""
FST基础文本处理器模块

提供基于有限状态转换器(FST)的文本处理功能，包括标记化和标准化。
"""

import os
import re
import string
import logging
import time
from typing import List, Dict, Any, Optional, Union

from pynini import (
    cdrewrite,
    cross,
    difference,
    escape,
    Fst,
    shortestpath,
    union,
    invert,
    determinize,
    minimize,
)
from pynini.lib import byte, utf8
from pynini.lib.pynutil import delete, insert
from concurrent.futures import ThreadPoolExecutor


class Processor:
    """
    FST基础文本处理类，用于标记化和标准化。

    该类提供了构建有限状态转换器的基础功能，包括字符集定义、
    规则构建、标记添加和FST缓存管理。

    Attributes:
        name (str): 处理器名称
        tagger (Optional[Fst]): FST标记器
        ALPHA: 字母字符集
        DIGIT: 数字字符集
        PUNCT: 标点符号字符集
        SPACE: 空格字符集
        VCHAR: 有效UTF-8字符集
        VSIGMA: 任意字符序列
    """

    def __init__(self, name: str) -> None:
        """
        初始化处理器。

        Args:
            name: 处理器名称，用于标识和日志记录
        """
        # 字符集定义
        self.ALPHA = byte.ALPHA
        self.DIGIT = byte.DIGIT
        self.PUNCT = byte.PUNCT
        self.SPACE = byte.SPACE | "\u00A0"  # 包含不间断空格
        self.VCHAR = utf8.VALID_UTF8_CHAR
        self.VSIGMA = self.VCHAR.star
        self.LOWER = byte.LOWER
        self.UPPER = byte.UPPER

        # 特殊字符处理
        CHAR = difference(self.VCHAR, union("\\", '"'))
        self.CHAR = CHAR | cross("\\", "\\") | cross('"', '"')
        self.SIGMA = (CHAR | cross("\\\\", "\\") | cross('"', '"')).star
        self.NOT_QUOTE = difference(self.VCHAR, r'"').optimize()
        self.NOT_SPACE = difference(self.VCHAR, self.SPACE).optimize()

        # 空格处理
        self.INSERT_SPACE = insert(" ")
        self.DELETE_SPACE = delete(self.SPACE).star
        self.DELETE_EXTRA_SPACE = cross(self.SPACE.plus, " ")
        self.DELETE_ZERO_OR_ONE_SPACE = delete(self.SPACE.ques)

        # 权重和大小写转换
        self.MIN_NEG_WEIGHT = -0.0001
        self.TO_LOWER = union(
            *[cross(x, y) for x, y in zip(string.ascii_uppercase, string.ascii_lowercase)]
        )
        self.TO_UPPER = invert(self.TO_LOWER)

        self.name = name
        self.tagger: Optional[Fst] = None

        # 性能优化相关属性
        self._compiled_patterns = None  # 预编译的正则表达式
        # 长文本分句+批处理的阈值与模式
        self._batch_split_threshold = 30
        self._split_pattern = re.compile(r"[。！？；，、\n]+")
        self._time_hint_pattern = re.compile(
            r"(今|明|昨|后天|上午|中午|下午|晚上|夜里|凌晨|深夜|周|星期|礼拜|年|月|日|号|季度|学期|节|假|点|时|分|秒|\d{1,2}[.:：]\d{1,2})"
        )
        # 并行批处理最大线程数
        self._max_workers = 10
        # 可选：按需预编译解析正则（默认延迟到首次使用）

        # 阶段2优化：添加缓存机制
        self._tag_cache = {}  # {text_hash: result}
        self._cache_max_size = 10000
        self._cache_hits = 0
        self._cache_misses = 0

        # FST优化超时设置（秒）- 已禁用复杂优化
        # self._fst_optimize_timeout = 300  # 5分钟超时

    def build_rule(self, fst: Fst, left_context: str = "", r: str = "") -> Any:
        """
        构建上下文相关的重写规则。

        Args:
            fst: 输入FST转换器
            left_context: 左上下文（默认为空字符串）
            r: 右上下文（默认为空字符串）

        Returns:
            CDRewriteRule: 上下文相关的重写规则
        """
        rule = cdrewrite(fst, left_context, r, self.VSIGMA)
        return rule

    def add_tokens(self, tagger: Fst) -> Fst:
        """
        为FST输出添加标记包装。

        Args:
            tagger: 输入FST转换器

        Returns:
            FST: 带标记的FST转换器
        """
        # 检查tagger是否有符号表（词级FST）
        tagger_has_sym = tagger.input_symbols() is not None

        if tagger_has_sym:
            # 词级FST：使用词级insert，但需要确保格式兼容TokenParser
            # TokenParser期望格式：time_relative { ... }（标记名和左花括号之间有空格）
            # 同时加载中英文符号表，根据匹配选择对应的pynutil
            tagger_sym = tagger.input_symbols()
            sym_size = tagger_sym.num_symbols() if tagger_sym else 0

            word_pynutil = None
            try:
                # 同时导入中英文pynutil和符号表
                from src.english.word_level_pynini import (
                    pynutil as en_pynutil,
                    get_symbol_table as get_en_sym,
                )
                from src.chinese.word_level_pynini import (
                    pynutil as zh_pynutil,
                    get_symbol_table as get_zh_sym,
                )

                en_sym = get_en_sym()
                zh_sym = get_zh_sym()

                # 根据符号表大小严格匹配
                if en_sym and en_sym.num_symbols() == sym_size:
                    word_pynutil = en_pynutil
                elif zh_sym and zh_sym.num_symbols() == sym_size:
                    word_pynutil = zh_pynutil
            except ImportError:
                pass

            if word_pynutil:
                try:
                    # 修复：使用复合token "time_relative {" 作为单个token，避免string()自动添加空格
                    # 这样输出格式为 "time_relative {" 而不是 "time_relative   {"
                    tagger = (
                        word_pynutil.insert(f"{self.name} {{") + tagger + word_pynutil.insert(" }")
                    )
                except Exception:
                    # FST操作失败，回退到字符级
                    tagger = insert(f"{self.name} {{ ") + tagger + insert(" } ")
            else:
                # 如果导入失败或无法匹配，回退到字符级（兼容性）
                tagger = insert(f"{self.name} {{ ") + tagger + insert(" } ")
        else:
            # 字符级FST：使用字符级insert（保持原有格式，因为字符级FST输出是字符序列）
            tagger = insert(f"{self.name} {{ ") + tagger + insert(" } ")

        # 注意：optimize()可能会将"00"优化为"0"，这对于时间格式是不可接受的
        # 但为了性能，我们仍然需要optimize()
        # 解决方案：在需要保留"00"格式的地方，使用硬编码字符串或string_map
        return tagger.optimize()

    def build_fst(self, prefix: str, cache_dir: str, overwrite_cache: bool = False) -> None:
        """
        构建并缓存FST标记器模型。

        Args:
            prefix: 模型名称前缀
            cache_dir: FST文件缓存目录
            overwrite_cache: 是否覆盖现有缓存
        """
        logger = logging.getLogger(f"fst_time-{self.name}")
        logger.setLevel(logging.INFO)

        # 避免重复添加处理器
        if not logger.handlers:
            handler = logging.StreamHandler()
            fmt = logging.Formatter("%(asctime)s fst_time %(levelname)s %(message)s")
            handler.setFormatter(fmt)
            logger.addHandler(handler)

        os.makedirs(cache_dir, exist_ok=True)
        tagger_name = f"{prefix}_tagger.fst"
        tagger_path = os.path.join(cache_dir, tagger_name)

        if os.path.exists(tagger_path) and not overwrite_cache:
            logger.info(f"发现现有FST: {tagger_path}")
            logger.info(f"跳过 {self.name} 的FST构建...")
            self.tagger = Fst.read(tagger_path)
        else:
            logger.info(f"为 {self.name} 构建FST...")
            self.build_tagger()
            if self.tagger is not None:
                # 回退到简单优化版本，避免卡死问题
                logger.info("执行基本FST优化...")
                self.tagger = self.tagger.optimize()

                self.tagger.write(tagger_path)
                logger.info("完成")
                logger.info(f"FST路径: {tagger_path}")
            else:
                logger.error(f"构建 {self.name} 的FST失败")

    def build_tagger(self) -> None:
        """
        构建标记器。子类需要实现此方法。

        Raises:
            NotImplementedError: 如果子类未实现此方法
        """
        raise NotImplementedError("子类必须实现 build_tagger 方法")

    def tag(self, text: str) -> List[Dict[str, Any]]:
        """
        标记输入文本并返回标记字典列表（阶段2优化：带缓存）。

        Args:
            text: 要标记的输入文本

        Returns:
            List[Dict[str, Any]]: 包含'type'和属性的标记字典列表
        """
        if not text or len(text) == 0:
            return []

        if self.tagger is None:
            raise ValueError(f"标记器 {self.name} 尚未构建，请先调用 build_fst")

        # 阶段2优化：检查缓存
        text_hash = hash(text)
        if text_hash in self._tag_cache:
            self._cache_hits += 1
            return self._tag_cache[text_hash]

        self._cache_misses += 1

        # 执行FST匹配
        result = self._tag_single(text)

        # 存入缓存（简单LRU策略）
        if len(self._tag_cache) >= self._cache_max_size:
            # 删除最老的10%条目
            remove_count = self._cache_max_size // 10
            for key in list(self._tag_cache.keys())[:remove_count]:
                del self._tag_cache[key]

        self._tag_cache[text_hash] = result
        return result

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        获取缓存统计信息（阶段2优化）

        Returns:
            Dict: 包含hits, misses, hit_rate, cache_size的字典
        """
        total = self._cache_hits + self._cache_misses
        hit_rate = self._cache_hits / total if total > 0 else 0
        return {
            "hits": self._cache_hits,
            "misses": self._cache_misses,
            "hit_rate": hit_rate,
            "cache_size": len(self._tag_cache),
        }

    # 已移除复杂的超时优化方法，回退到简单优化

    def _tag_single(self, text: str) -> List[Dict[str, Any]]:
        """对单段文本执行一次FST解码并解析为token字典列表（阶段3优化）"""
        escaped_text = escape(text)
        lattice = escaped_text @ self.tagger
        # 阶段3优化：FST已经确定性化，不需要unique=True
        tagged_text = shortestpath(lattice, nshortest=1).string()
        return self.parse_tags(tagged_text)

    def _tag_batch_parallel(self, segments: List[str]) -> List[Dict[str, Any]]:
        """对多个片段并行解码并汇总结果（最多_max_workers线程，保持输入顺序）"""
        if not segments:
            return []

        # 使用executor.map以保持顺序；每个任务内部做异常兜底
        def worker(seg: str) -> List[Dict[str, Any]]:
            if not seg:
                return []
            try:
                return self._tag_single(seg)
            except Exception:
                return []

        results: List[Dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=self._max_workers) as executor:
            for part in executor.map(worker, segments):
                if part:
                    results.extend(part)
        return results

    def _split_by_punct(self, text: str) -> List[str]:
        """按常见中文标点与换行切分为较小片段，去除空片段"""
        parts = self._split_pattern.split(text)
        return [p.strip() for p in parts if p and p.strip()]

    def _ensure_compiled_patterns(self) -> None:
        """确保用于解析的正则已预编译，避免并发初始化竞态"""
        if self._compiled_patterns is None:
            self._compiled_patterns = {
                "time_token": re.compile(
                    r"(time_(?:utc|weekday|holiday|relative|delta|period|lunar|between))\s*\{(.*?)\}",
                    re.DOTALL,
                ),
                "kv": re.compile(r'(\w+):\s*"?([^"]*)"?'),
            }

    def _fast_parse_tags(self, tagged_text: str) -> List[Dict[str, Any]]:
        """
        优化的标记解析，使用预编译的正则表达式。

        Args:
            tagged_text: 带标记的FST输出字符串

        Returns:
            List[Dict[str, Any]]: 标记字典列表
        """
        # 对长文本的快速剪枝：没有 time_ 直接返回空
        if "time_" not in tagged_text:
            return []

        # 延迟初始化预编译的正则表达式（仅匹配时间相关 token，跳过 char 等无关 token）
        if self._compiled_patterns is None:
            self._compiled_patterns = {
                # 仅捕获 time_* 类别，DOTALL 允许内容跨行；懒惰匹配至最近的右花括号
                "time_token": re.compile(
                    r"(time_(?:utc|weekday|holiday|relative|delta|period|lunar|between))\s*\{(.*?)\}",
                    re.DOTALL,
                ),
                "kv": re.compile(r'(\w+):\s*"?([^"]*)"?'),
            }

        tokens: List[Dict[str, Any]] = []
        for m in self._compiled_patterns["time_token"].finditer(tagged_text):
            token_type = m.group(1)
            content = m.group(2)
            token_data: Dict[str, Any] = {"type": token_type}
            # 使用预编译的正则表达式流式提取键值对
            for kv_m in self._compiled_patterns["kv"].finditer(content):
                key = kv_m.group(1).strip()
                value = kv_m.group(2).strip()
                token_data[key] = value
            tokens.append(token_data)
        return tokens

    @staticmethod
    def parse_tags(
        tagged_text: str,
        input_text: str = None,
        input_string: str = None,
        token_positions: List[tuple] = None,
        is_word_level: bool = False,
        include_source: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        将标记文本解析为结构化标记列表。（向后兼容的静态方法）

        示例:
            输入: 'time_weekday { week_day: "1" }'
            输出: [{'type': 'time_weekday', 'week_day': '1'}]

        Args:
            tagged_text: 带标记的FST输出字符串
            input_text: 原始输入文本（用于提取source字段）
            input_string: FST输入字符串（词级FST的token序列或字符级FST的原始文本）
            token_positions: token位置映射列表（仅词级FST使用）
            is_word_level: 是否使用词级FST
            include_source: 是否在tag中添加source字段（默认True）

        Returns:
            List[Dict[str, Any]]: 标记字典列表
        """
        tokens = []
        # 提取标记类型和内容的正则表达式模式
        pattern = r"(\w+)\s*\{(.*?)\}"
        matches = re.findall(pattern, tagged_text)

        for token_type, content in matches:
            token_data = {"type": token_type}
            # 提取键值对的正则表达式模式
            # 支持两种格式：
            # 1. 有引号：hour: "8" 或 hour : "1 1"
            # 2. 无引号：raw_type: utc 或 raw_type : relative
            kv_pattern = r'(\w+)\s*:\s*(?:"([^"]*)"|(\S+))'
            for match in re.finditer(kv_pattern, content):
                key = match.group(1).strip()
                # group(2) 是有引号的值，group(3) 是无引号的值
                value = match.group(2) if match.group(2) is not None else match.group(3)

                # 对于有引号的数字类字段，移除空格（词级FST输出时token之间会自动加空格）
                # 例如：'1 1' -> '11', '- 2' -> '-2', '1 0' -> '10'
                # 对于无引号的字段（如raw_type），不需要处理空格（本来就没有）
                if match.group(2) is not None:  # 有引号的值
                    value = value.strip().replace(" ", "")
                else:  # 无引号的值
                    value = value.strip()

                token_data[key] = value

            # 为时间相关tag添加source字段
            if token_type.startswith("time_") and input_text and include_source:
                source_text = Processor._extract_source_text(
                    token_type, content, input_text, input_string, token_positions, is_word_level
                )
                if source_text:
                    token_data["source"] = source_text

            tokens.append(token_data)
        return tokens

    @staticmethod
    def _extract_source_text(
        token_type: str,
        content: str,
        input_text: str,
        input_string: str,
        token_positions: List[tuple],
        is_word_level: bool,
    ) -> str:
        """
        提取tag对应的原始文本片段

        Args:
            token_type: tag类型
            content: tag内容
            input_text: 原始输入文本
            input_string: FST输入字符串（token序列，仅词级FST）
            token_positions: token位置映射（仅词级FST）
            is_word_level: 是否使用词级FST

        Returns:
            str: 原始文本片段，如果无法提取则返回None
        """
        if not input_text:
            return None

        # 对于相对时间，使用关键词匹配（中英文通用）
        if token_type == "time_relative":
            # 中文关键词和完整时间词映射
            chinese_time_words = [
                "昨日",
                "明天",
                "今天",
                "前天",
                "后天",
                "去年",
                "明年",
                "上周",
                "下周",
                "上月",
                "下月",
                "昨天",
                "明日",
                "今日",
                "前日",
                "后日",
            ]
            # 英文关键词
            english_keywords = [
                "yesterday",
                "tomorrow",
                "today",
                "last",
                "next",
                "ago",
                "before",
                "after",
            ]

            # 先尝试匹配完整的中文时间词（按长度从长到短排序，优先匹配长词）
            sorted_words = sorted(chinese_time_words, key=len, reverse=True)
            for word in sorted_words:
                idx = input_text.find(word)
                if idx != -1:
                    return word

            # 如果没有完整词，尝试单个关键词（按文本位置顺序匹配）
            chinese_keywords = ["昨", "明", "今", "前", "后", "上", "下", "去", "来"]
            # 找到所有关键词的位置，按位置排序
            keyword_positions = []
            for keyword in chinese_keywords:
                idx = input_text.find(keyword)
                if idx != -1:
                    keyword_positions.append((idx, keyword))

            if keyword_positions:
                # 按位置排序，取第一个（最靠前的）
                keyword_positions.sort(key=lambda x: x[0])
                idx, keyword = keyword_positions[0]
                # 尝试提取完整的时间词
                common_time_words = [
                    "昨日",
                    "明天",
                    "今天",
                    "前天",
                    "后天",
                    "去年",
                    "明年",
                    "上周",
                    "下周",
                    "上月",
                    "下月",
                    "昨天",
                    "明日",
                    "今日",
                    "前日",
                    "后日",
                ]
                for end in range(idx + 1, min(idx + 5, len(input_text))):
                    candidate = input_text[idx:end]
                    if candidate in common_time_words:
                        return candidate
                # 如果找不到完整词，返回2-3个字符
                return input_text[idx : idx + 2] if idx + 2 <= len(input_text) else input_text[idx]

            # 再尝试英文关键词（按位置顺序匹配）
            input_lower = input_text.lower()
            keyword_positions = []
            for keyword in english_keywords:
                idx = input_lower.find(keyword)
                if idx != -1:
                    keyword_positions.append((idx, keyword))

            if keyword_positions:
                # 按位置排序，取第一个
                keyword_positions.sort(key=lambda x: x[0])
                idx, keyword = keyword_positions[0]
                # 提取完整的单词（可能包含所有格）
                end = idx + len(keyword)
                # 检查是否有所有格
                if end < len(input_text) and input_text[end] == "'":
                    end += 2  # 包含"'s"
                return input_text[idx:end] if end <= len(input_text) else input_text[idx:]

        # 对于其他时间类型，使用更通用的方法
        if is_word_level and token_positions:
            # 词级FST：通过token_positions映射
            # 如果tag包含特定字段，尝试匹配对应的token
            if "offset_day" in content or "offset_month" in content or "offset_year" in content:
                # 相对时间：已经在上面处理
                pass
            elif "week_day" in content:
                # 星期：查找"周"、"星期"等关键词
                week_keywords = ["周", "星期", "礼拜"]
                for keyword in week_keywords:
                    if keyword in input_text:
                        idx = input_text.find(keyword)
                        if idx != -1:
                            # 尝试提取完整的星期表达
                            for end in range(idx + 1, min(idx + 5, len(input_text))):
                                candidate = input_text[idx:end]
                                if any(
                                    day in candidate
                                    for day in ["一", "二", "三", "四", "五", "六", "日", "天"]
                                ):
                                    return candidate
                            return (
                                input_text[idx : idx + 3]
                                if idx + 3 <= len(input_text)
                                else input_text[idx]
                            )
            elif "month" in content or "day" in content or "year" in content:
                # 日期：尝试匹配数字+单位（中文格式）
                import re

                date_pattern = re.compile(r"\d+[年月日号]")
                match = date_pattern.search(input_text)
                if match:
                    return match.group(0)
                # 如果没有中文格式，尝试ISO 8601格式（YYYY-MM-DD）
                iso_pattern = re.compile(r"\d{4}-\d{2}-\d{2}")
                match = iso_pattern.search(input_text)
                if match:
                    return match.group(0)
                # 尝试匹配年份（YYYY）
                if "year" in content:
                    year_pattern = re.compile(r"\d{4}")
                    match = year_pattern.search(input_text)
                    if match:
                        return match.group(0)
            elif "hour" in content or "minute" in content or "second" in content:
                # 时间：尝试匹配ISO 8601时间格式（HH:MM:SS或HH:MM）
                import re

                # 先尝试完整的ISO 8601格式（包含T和Z）
                iso_time_pattern = re.compile(r"T\d{2}:\d{2}(:\d{2})?Z?")
                match = iso_time_pattern.search(input_text)
                if match:
                    return match.group(0)
                # 再尝试简单的时间格式（HH:MM或HH:MM:SS）
                time_pattern = re.compile(r"\d{2}:\d{2}(:\d{2})?")
                match = time_pattern.search(input_text)
                if match:
                    return match.group(0)

            # 默认：返回第一个token的原始文本
            if token_positions:
                _, _, first_token = token_positions[0]
                return first_token
        else:
            # 字符级FST：直接在原始文本中查找
            # 对于其他时间类型，使用关键词匹配
            if "week_day" in content:
                week_keywords = ["周", "星期", "礼拜"]
                for keyword in week_keywords:
                    idx = input_text.find(keyword)
                    if idx != -1:
                        for end in range(idx + 1, min(idx + 5, len(input_text))):
                            candidate = input_text[idx:end]
                            if any(
                                day in candidate
                                for day in ["一", "二", "三", "四", "五", "六", "日", "天"]
                            ):
                                return candidate
                        return (
                            input_text[idx : idx + 3]
                            if idx + 3 <= len(input_text)
                            else input_text[idx]
                        )
            elif "month" in content or "day" in content or "year" in content:
                import re

                # 先尝试中文格式
                date_pattern = re.compile(r"\d+[年月日号]")
                match = date_pattern.search(input_text)
                if match:
                    return match.group(0)
                # 再尝试ISO 8601格式
                iso_pattern = re.compile(r"\d{4}-\d{2}-\d{2}")
                match = iso_pattern.search(input_text)
                if match:
                    return match.group(0)
                # 尝试匹配年份
                if "year" in content:
                    year_pattern = re.compile(r"\d{4}")
                    match = year_pattern.search(input_text)
                    if match:
                        return match.group(0)
            elif "hour" in content or "minute" in content or "second" in content:
                # 时间：尝试匹配ISO 8601时间格式
                import re

                # 先尝试完整的ISO 8601格式（包含T和Z）
                iso_time_pattern = re.compile(r"T\d{2}:\d{2}(:\d{2})?Z?")
                match = iso_time_pattern.search(input_text)
                if match:
                    return match.group(0)
                # 再尝试简单的时间格式（HH:MM或HH:MM:SS）
                time_pattern = re.compile(r"\d{2}:\d{2}(:\d{2})?")
                match = time_pattern.search(input_text)
                if match:
                    return match.group(0)

        return None
