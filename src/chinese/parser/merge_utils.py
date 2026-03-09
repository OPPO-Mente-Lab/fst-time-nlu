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
合并工具函数模块
提供通用的token合并辅助函数，减少重复代码
"""

from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime


def adjust_base_for_relative(
    token: Dict[str, Any], base_time: datetime, relative_parser
) -> datetime:
    """
    应用相对时间偏移，返回调整后的基准时间

    Args:
        token: 相对时间token
        base_time: 基准时间
        relative_parser: 相对时间解析器

    Returns:
        调整后的基准时间
    """
    if relative_parser:
        direction = relative_parser._determine_direction(token)
        time_offset_num = relative_parser._get_offset_time_num(token)
        return relative_parser._apply_offset_time_num(base_time, time_offset_num, direction)
    return base_time


def inherit_noon(left_token: Dict[str, Any], right_token: Dict[str, Any]) -> Optional[str]:
    """
    继承noon值：若仅一侧有，则两侧都用同一个

    Args:
        left_token: 左侧token
        right_token: 右侧token

    Returns:
        继承的noon值
    """
    return left_token.get("noon") or right_token.get("noon")


def build_utc_token(
    hour: Optional[str] = None, minute: Optional[str] = None, noon: Optional[str] = None, **kwargs
) -> Dict[str, Any]:
    """
    构造UTC token

    Args:
        hour: 小时
        minute: 分钟
        noon: 时段
        **kwargs: 其他字段

    Returns:
        UTC token字典
    """
    token = {"type": "time_utc"}
    if hour is not None:
        token["hour"] = hour
    if minute is not None:
        token["minute"] = minute
    if noon is not None:
        token["noon"] = noon
    token.update(kwargs)
    return token


def build_range_from_endpoints(
    left_result: List, right_result: List
) -> Tuple[List[List[str]], int]:
    """
    从两个解析结果构造时间区间

    Args:
        left_result: 左端点解析结果
        right_result: 右端点解析结果

    Returns:
        时间区间列表
    """
    if left_result and right_result and left_result[0] and right_result[0]:
        left_start = left_result[0][0]
        right_end = right_result[0][1] if len(right_result[0]) > 1 else right_result[0][0]
        return [[left_start, right_end]]
    return []


def normalize_year(year_val: int) -> int:
    """
    标准化两位数年份（与 BaseParser._normalize_year 保持一致）

    Args:
        year_val: 年份值

    Returns:
        标准化后的年份
    """
    if year_val < 49:
        return 2000 + year_val
    elif year_val < 100:
        return 1900 + year_val
    else:
        return year_val


def reinterpret_hour_as_month(token: Dict[str, Any]) -> Dict[str, Any]:
    """
    将token中的hour字段重新解释为month

    Args:
        token: 包含hour的token

    Returns:
        包含month的新token
    """
    new_token = dict(token)
    if "hour" in new_token:
        new_token["month"] = new_token.pop("hour")
    return new_token


def check_token_pattern(
    tokens: List[Dict[str, Any]],
    start_idx: int,
    pattern: List[Tuple[str, Optional[str]]],
) -> bool:
    """
    检查token序列是否匹配指定模式

    Args:
        tokens: token列表
        start_idx: 起始索引
        pattern: 模式列表，每项为(type, field)元组，field为None表示只检查type

    Returns:
        是否匹配
    """
    n = len(tokens)
    for i, (expected_type, expected_field) in enumerate(pattern):
        idx = start_idx + i
        if idx >= n:
            return False
        token = tokens[idx]
        if token.get("type") != expected_type:
            return False
        if expected_field is not None and expected_field not in token:
            return False
    return True


def safe_parse(parser, token: Dict[str, Any], base_time: datetime) -> List:
    """
    安全地调用解析器，捕获异常并返回空列表

    Args:
        parser: 解析器对象
        token: token字典
        base_time: 基准时间

    Returns:
        解析结果列表，失败返回空列表
    """
    try:
        result = parser.parse(token, base_time)
        return result if result else []
    except Exception:
        return []


def inherit_fields(source: Dict[str, Any], target: Dict[str, Any], fields: List[str]) -> None:
    """
    从源token继承字段到目标token（仅当目标没有该字段时）

    Args:
        source: 源token
        target: 目标token
        fields: 要继承的字段列表
    """
    for field in fields:
        if field in source and field not in target:
            target[field] = source[field]


def check_token_sequence(
    tokens: List[Dict[str, Any]], start_idx: int, pattern: List[Dict[str, Any]]
) -> bool:
    """
    检查从start_idx开始的token序列是否匹配给定的模式。

    Args:
        tokens: token列表
        start_idx: 开始索引
        pattern: 模式列表，每个元素包含type和可选的fields检查

    Returns:
        bool: 是否匹配模式
    """
    if start_idx + len(pattern) > len(tokens):
        return False

    for i, expected in enumerate(pattern):
        token = tokens[start_idx + i]
        if token.get("type") != expected.get("type"):
            return False

        # 检查必需字段
        required_fields = expected.get("fields", [])
        for field in required_fields:
            if field not in token:
                return False

    return True


def safe_parse_with_jump(
    parser: Any, token: Dict[str, Any], base_time: datetime, jump_count: int
) -> Optional[Tuple[List[List[str]], int]]:
    """
    安全地调用解析器，返回结果和跳跃数。

    Args:
        parser: 解析器
        token: token
        base_time: 基准时间
        jump_count: 跳跃的token数量

    Returns:
        (解析结果, 跳跃数) 或 None
    """
    try:
        result = parser.parse(token, base_time) if parser else None
        return (result or [], jump_count) if result else None
    except Exception:
        return None


def normalize_year_in_token(token: Dict[str, Any], year_field: str = "year") -> Optional[int]:
    """
    标准化token中的年份字段。

    Args:
        token: token
        year_field: 年份字段名

    Returns:
        标准化后的年份或None
    """
    if year_field not in token:
        return None

    try:
        year_val = int(token[year_field])
        return normalize_year(year_val)
    except (ValueError, TypeError):
        return None
