# Copyright (c) 2025 Ming Yu (yuming@oppo.com), Liangliang Han (hanliangliang@oppo.com)
# Licensed under the Apache License, Version 2.0

from typing import Optional


_DIGIT_MAP = {
    "零": 0,
    "〇": 0,
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "壹": 1,
    "贰": 2,
    "貳": 2,
    "叁": 3,
    "參": 3,
    "肆": 4,
    "伍": 5,
    "陆": 6,
    "陸": 6,
    "柒": 7,
    "捌": 8,
    "玖": 9,
}

_UNIT_MAP = {
    "十": 10,
    "拾": 10,
    "百": 100,
    "佰": 100,
    "千": 1000,
    "仟": 1000,
    "万": 10000,
    "萬": 10000,
    "亿": 100000000,
    "億": 100000000,
}


def convert_chinese_number(text: str) -> Optional[int]:
    """将中文数字转换为整数。

    目标：
    - "七二" -> 72（逐字拼接）
    - "七十二" -> 72（单位解析）
    - 支持 十/百/千/万/亿 与繁体数字
    - 不处理“半”等小数场景（返回None由调用方自行兜底）
    """
    if not text:
        return None

    # 若包含不支持的字符，直接走简单拼接尝试
    if any(ch not in _DIGIT_MAP and ch not in _UNIT_MAP for ch in text):
        return _convert_simple_digits(text)

    # 如果包含单位，用单位算法；否则用简单拼接
    if any(ch in _UNIT_MAP for ch in text):
        val = _convert_with_units(text)
        if val is not None:
            return val
    return _convert_simple_digits(text)


def _convert_simple_digits(text: str) -> Optional[int]:
    # 逐字映射：七二 -> 72, 一二三 -> 123；忽略无法识别的字符
    buf = []
    for ch in text:
        if ch in _DIGIT_MAP:
            buf.append(str(_DIGIT_MAP[ch]))
        elif ch in _UNIT_MAP:
            # 简单模式下遇到单位，直接失败，交由带单位解析
            return None
        else:
            # 非数字字符：终止
            break
    if not buf:
        return None
    try:
        return int("".join(buf))
    except Exception:
        return None


def _convert_with_units(text: str) -> Optional[int]:
    # 分段算法：先按 亿/万 切分到块，再在块内按 千/百/十 乘加
    try:
        total = 0
        for part, unit_base in _split_by_large_units(text):
            part_val = _eval_small_units(part)
            total = total * unit_base + part_val
        return total
    except Exception:
        return None


def _split_by_large_units(text: str):
    # 返回 (段文本, 基数) 列表，从左到右消费：如 "一亿二万三千四百五十六" ->
    # [("一", 100000000), ("二", 10000), ("三千四百五十六", 1)]
    result = []
    cur = text
    for marker, base in [
        ("亿", 100000000),
        ("億", 100000000),
        ("万", 10000),
        ("萬", 10000),
    ]:
        if marker in cur:
            idx = cur.index(marker)
            left = cur[:idx]
            rest = cur[idx + 1 :]
            if left:
                result.append((left, base))
            cur = rest
    # 剩余部分基数为 1
    if cur:
        result.append((cur, 1))
    return result if result else [(text, 1)]


def _eval_small_units(part: str) -> int:
    # 计算不含 万/亿 的片段：按 千/百/十 组合
    val = 0
    tmp = 0
    unit_order = [
        ("千", 1000),
        ("仟", 1000),
        ("百", 100),
        ("佰", 100),
        ("十", 10),
        ("拾", 10),
    ]

    i = 0
    while i < len(part):
        ch = part[i]
        if ch in _DIGIT_MAP:
            tmp = _DIGIT_MAP[ch]
            i += 1
            continue
        matched = False
        for marker, base in unit_order:
            if ch == marker:
                if tmp == 0:
                    tmp = 1
                val += tmp * base
                tmp = 0
                matched = True
                i += 1
                break
        if not matched:
            # 非识别字符，直接尝试结束
            i += 1
    val += tmp
    return val
