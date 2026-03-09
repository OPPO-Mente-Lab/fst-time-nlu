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

import copy
from datetime import datetime

from .parser import (
    WeekParser,
    UTCTimeParser,
    DeltaParser,
    HolidayParser,
    RelativeParser,
    PeriodParser,
    LunarParser,
    BetweenParser,
    RangeParser,
    RecurringParser,
)
from .parser.context_merger import ContextMerger
from ..core.token_parser import TokenParser
from .utils import get_time_word_filter
from ..core.logger import get_logger


class TimeParser:
    """将FST tag结果转换为实际的日期时间值"""

    def __init__(self):
        """
        初始化时间计算器
        """
        self.logger = get_logger(__name__)
        # 初始化所有解析器
        self.parsers = {
            "time_utc": UTCTimeParser(),
            "time_weekday": WeekParser(),
            "time_holiday": HolidayParser(),
            "time_relative": RelativeParser(),
            "time_delta": DeltaParser(),
            "time_period": PeriodParser(),
            "time_lunar": LunarParser(),
            "time_between": BetweenParser(),
            "time_range": RangeParser(),
            "time_recurring": RecurringParser(),
        }
        # 初始化上下文合并器
        self.context_merger = ContextMerger(self.parsers)
        # 初始化时间词过滤器
        self.time_word_filter = get_time_word_filter()

    def _parse_tokens(self, tag_str: str):
        """将 Processor.Tag 输出的字符串解析成 token dict 列表"""
        parser = TokenParser()
        parser.parse(tag_str)

        tokens = []
        for tok in parser.tokens:
            t_dict = {"type": tok.name}
            t_dict.update(tok.members)
            tokens.append(t_dict)
        return tokens

    def merge_time_parser(self, last_time, new_time):
        """合并时间解析器的结果，共享所有offset_*参数"""
        # 处理new_time可能是字典或列表的情况
        if isinstance(new_time, dict):
            return [last_time[0], new_time]
        else:
            return [last_time[0], new_time[-1]]

    def parse_tag_to_datetime(  # noqa: C901
        self, tokens: list, base_time="2025-01-21 08:00:00", original_query: str = None
    ):
        """将token列表转换为日期时间值"""
        base_time = datetime.strptime(base_time, "%Y-%m-%dT%H:%M:%SZ")
        if isinstance(tokens, str):
            tokens = self._parse_tokens(tokens)

        if not tokens:
            return []

        # 深拷贝tokens，避免修改缓存中的数据
        tokens = copy.deepcopy(tokens)

        # 过滤时间词歧义（"X点"的非时间语义）
        if original_query:
            tokens = self._filter_time_word_ambiguity(tokens, original_query)

        results = []  # 所有的返回日期，列表格式
        last_type = None
        token_list = []
        # 仅对区间类token启用合并
        merge_allowed_types = {"time_period", "time_between"}
        i = 0
        while i < len(tokens):
            token = tokens[i]
            token_type = token.get("type")
            parser = self.parsers.get(token_type)  # 寻找对应的编译器

            # 通用上下文合并：对所有token类型都尝试合并
            merged = self.context_merger.try_merge(i, tokens, base_time)
            if merged is not None:
                merged_results, jump = merged
                results.extend(merged_results)
                i += jump
                last_type = merged_results and token_type or last_type
                continue

            if parser:
                if token_type != "char":
                    token_list.append(token)

                # 内置合并逻辑（保持向后兼容）
                merged = self._try_legacy_merge(i, tokens, base_time)
                if merged is not None:
                    merged_results, jump = merged
                    results.extend(merged_results)
                    i += jump
                    last_type = merged_results and token_type or last_type
                    continue

                # 窄域合并：time_delta 后跟（可有一个“的”）的仅含时分秒的 time_utc，且 delta 仅 day/hour 且方向为 1
                if token_type == "time_delta":
                    j = i + 1
                    # 允许一个“的”作为过渡
                    if (
                        j < len(tokens)
                        and tokens[j].get("type") == "char"
                        and tokens[j].get("value") == "的"
                    ):
                        j += 1
                    # 情形A：delta(year) + 第X季度 → 将偏移应用到基准年，再解析季度
                    if (
                        j < len(tokens)
                        and tokens[j].get("type") == "time_period"
                        and "quarter" in tokens[j]
                    ):
                        delta_keys = set([k for k in token.keys() if not k.startswith("_")])
                        delta_only_year = (
                            delta_keys <= {"type", "year", "offset_direction"}
                            and "year" in delta_keys
                        )
                        if delta_only_year:
                            try:
                                delta_parser = self.parsers.get("time_delta")
                                period_parser = self.parsers.get("time_period")
                                # 归一化两位年（delta 年偏移直接使用原逻辑，无需归一）
                                delta_time_num = delta_parser._get_time_num(token)
                                delta_direction = delta_parser._determine_direction(token)
                                adjusted_base_time = delta_parser._apply_offset_time_num(
                                    base_time, delta_time_num, delta_direction
                                )
                                parsed_result = period_parser.parse(tokens[j], adjusted_base_time)
                                if parsed_result is not None:
                                    results.extend(parsed_result)
                                    last_type = "time_period"
                                    i = j + 1
                                    continue
                            except Exception:
                                pass
                    if j < len(tokens) and tokens[j].get("type") == "time_utc":
                        utc_tok = tokens[j]
                        utc_has_only_hms = ("hour" in utc_tok) and (
                            "year" not in utc_tok
                            and "month" not in utc_tok
                            and "day" not in utc_tok
                        )
                        # delta 仅 day 或 hour
                        delta_keys = set([k for k in token.keys() if not k.startswith("_")])
                        delta_only_day = (
                            delta_keys <= {"type", "day", "offset_direction"}
                            and "day" in delta_keys
                        )
                        delta_only_hour = (
                            delta_keys <= {"type", "hour", "offset_direction"}
                            and "hour" in delta_keys
                        )
                        delta_dir_ok = token.get("offset_direction") == "1"
                        if (
                            utc_has_only_hms
                            and delta_dir_ok
                            and (delta_only_day or delta_only_hour)
                        ):
                            try:
                                delta_parser = self.parsers.get("time_delta")
                                utc_parser = self.parsers.get("time_utc")
                                delta_time_num = delta_parser._get_time_num(token)
                                delta_direction = delta_parser._determine_direction(token)
                                adjusted_base_time = delta_parser._apply_offset_time_num(
                                    base_time, delta_time_num, delta_direction
                                )
                                parsed_result = utc_parser.parse(utc_tok, adjusted_base_time)
                                if parsed_result is not None:
                                    results.extend(parsed_result)
                                    last_type = "time_utc"
                                    i = j + 1
                                    continue
                            except Exception:
                                pass

                if last_type == token_type and token_type in merge_allowed_types:
                    # 端点字段继承：针对 time_between 的相邻端点，右端缺失字段从左端补齐
                    if token_type == "time_between":
                        try:
                            # token_list 末尾是当前端点；上一个同类型端点位于倒数第二个
                            if len(token_list) >= 2:
                                prev_token = token_list[-2]
                                # 支持 utc 和 relative 类型之间的继承
                                if token.get("raw_type") in [
                                    "utc",
                                    "relative",
                                ] and prev_token.get(
                                    "raw_type"
                                ) in ["utc", "relative"]:

                                    # 检查右端点是否是相对时间（包含offset_*字段）
                                    is_relative = (
                                        token.get("raw_type") == "relative"
                                        or token.get("offset_year")
                                        or token.get("offset_month")
                                        or token.get("offset_day")
                                        or token.get("offset_week")
                                    )

                                    # 只有当右端点不是相对时间时，才继承绝对时间字段
                                    if not is_relative:
                                        # 补 year / month / day / noon（右端没有且左端提供时）
                                        if "year" not in token and "year" in prev_token:
                                            token["year"] = prev_token["year"]
                                        if "month" not in token and "month" in prev_token:
                                            token["month"] = prev_token["month"]
                                        if "day" not in token and "day" in prev_token:
                                            token["day"] = prev_token["day"]

                                    # noon可以继承（相对时间也可以有noon）
                                    if "noon" not in token and "noon" in prev_token:
                                        token["noon"] = prev_token["noon"]

                                    # 继承偏移量信息（相对时间可以继承偏移量）
                                    if "offset_day" not in token and "offset_day" in prev_token:
                                        token["offset_day"] = prev_token["offset_day"]
                        except Exception:
                            # 继承失败不影响后续解析
                            pass
                    # 当前token偏移量为空时，从第一个token获取偏移量
                    if parser._get_offset_time_num(token) == {}:
                        offset_value = parser._get_offset_time_num(token_list[0])
                        # 将键名添加offset_前缀
                        mapped_offset = {f"offset_{k}": v for k, v in offset_value.items()}
                        token.update(mapped_offset)

                    try:
                        parsed_result = parser.parse(token, base_time)
                        if parsed_result and len(parsed_result) > 0:
                            if results:
                                results[-1] = self.merge_time_parser(
                                    results[-1], parsed_result[0]
                                )  # 进行拼接
                            else:
                                results.extend(parsed_result)
                                self.logger.debug(
                                    f"Warning: Initial token parsed but results was empty, added directly: {token}"
                                )
                        else:
                            self.logger.debug(f"Warning: No valid parsed result for token {token}")
                            # 添加空结果避免后续索引错误###########
                            if not results:
                                results.append([])
                    except Exception as e:
                        self.logger.debug(f"时间提取错误（已跳过）: {e} - Token: {token}")
                        pass
                        # 跳过该token，继续处理其他token
                        pass
                else:
                    # 非区间类token或不同类型，直接追加
                    try:
                        parsed_result = parser.parse(token, base_time)
                        if parsed_result is not None:
                            results.extend(parsed_result)
                        else:
                            # 处理解析结果为None的情况
                            self.logger.debug(f"Warning: Failed to parse token {token}")
                            pass
                    except Exception as e:
                        self.logger.debug(f"时间提取错误（已跳过）: {e} - Token: {token}")
                        pass
                        # 跳过该token，继续处理其他token
                        pass

            elif token_type == "time_lunar":
                #  lunar_parser尚未实现
                pass
            last_type = token_type
            i += 1

        # 后处理：去重相同结果（当多条token解析为同一时间点/区间时保留一次）
        if results:
            # 去重，保持原有返回结构（不做扁平化）
            uniq: list = []
            seen = set()
            for item in results:
                # 处理新的嵌套列表格式 [[...]]
                if isinstance(item, list) and item and isinstance(item[0], list):
                    # 新的周期性时间格式：外层列表包含内层列表
                    # 使用内层列表的第一个元素作为key
                    inner_list = item[0]
                    if inner_list and isinstance(inner_list[0], str):
                        # 内层列表包含时间字符串
                        key = inner_list[0]
                    elif inner_list and isinstance(inner_list[0], list) and len(inner_list[0]) >= 1:
                        # 内层列表包含时间段（两元素列表）
                        key = inner_list[0][0]  # 使用时间段的开始时间
                    else:
                        key = str(item)
                # 处理时间字符串列表
                elif isinstance(item, list) and item and isinstance(item[0], str):
                    # 对于包含时间字符串的列表，使用第一个时间字符串作为key
                    key = item[0]
                elif isinstance(item, list) and item and isinstance(item[0], dict):
                    # 对于包含字典的列表，使用datetime字符串作为key
                    key = item[0].get("datetime", str(item))
                else:
                    key = tuple(item) if isinstance(item, list) else (item,)
                if key not in seen:
                    seen.add(key)
                    uniq.append(item)
            return uniq
        return results

    def _try_legacy_merge(self, i, tokens, base_time):
        """保留的传统合并逻辑，确保向后兼容"""
        # 这里可以添加一些ContextMerger中未覆盖的特殊合并逻辑
        # 目前暂时返回None，让原有逻辑继续处理
        return None

    def _filter_time_word_ambiguity(self, tokens: list, original_query: str) -> list:
        """
        过滤时间词的非时间语义（如"X点"表示要点而非时间）

        Args:
            tokens: token列表
            original_query: 原始查询文本

        Returns:
            过滤后的token列表
        """
        # 查找所有"点"在原始query中的位置
        dian_positions = []
        index = 0
        while True:
            index = original_query.find("点", index)
            if index == -1:
                break
            dian_positions.append(index)
            index += 1

        if not dian_positions:
            return tokens  # 没有"点"，直接返回

        # 过滤tokens
        filtered_tokens = []

        for token in tokens:
            # 只检查time_utc和time_relative类型的token（包含hour字段）
            if token.get("type") not in ("time_utc", "time_relative"):
                filtered_tokens.append(token)
                continue

            hour_value = token.get("hour")
            if hour_value is None:
                filtered_tokens.append(token)
                continue

            # 检查是否应该过滤这个"X点"token
            should_filter = False
            for dian_index in dian_positions:
                if self.time_word_filter.should_filter_dian(original_query, dian_index, hour_value):
                    should_filter = True
                    break

            if not should_filter:
                filtered_tokens.append(token)
            # else: 过滤掉这个token

        return filtered_tokens
