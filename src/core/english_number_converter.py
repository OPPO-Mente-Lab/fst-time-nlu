# Copyright (c) 2025 Ming Yu (yuming@oppo.com), Liangliang Han (hanliangliang@oppo.com)
# Licensed under the Apache License, Version 2.0

from typing import Optional


def convert_english_number(text: str) -> Optional[int]:
    """
    Convert English number words to integers

    Args:
        text (str): English number text (e.g., "one", "twenty-one", "one hundred")

    Returns:
        Optional[int]: Parsed number or None if parsing fails
    """
    if not text:
        return None

    text = text.lower().strip()

    # Handle direct digits
    if text.isdigit():
        return int(text)

    # Basic number words
    number_words = {
        "zero": 0,
        "one": 1,
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5,
        "six": 6,
        "seven": 7,
        "eight": 8,
        "nine": 9,
        "ten": 10,
        "eleven": 11,
        "twelve": 12,
        "thirteen": 13,
        "fourteen": 14,
        "fifteen": 15,
        "sixteen": 16,
        "seventeen": 17,
        "eighteen": 18,
        "nineteen": 19,
        "twenty": 20,
        "thirty": 30,
        "forty": 40,
        "fifty": 50,
        "sixty": 60,
        "seventy": 70,
        "eighty": 80,
        "ninety": 90,
    }

    # Unit words
    units = {
        "hundred": 100,
        "thousand": 1000,
        "million": 1000000,
        "billion": 1000000000,
    }

    # Handle simple cases
    if text in number_words:
        return number_words[text]

    # Handle compound numbers like "twenty-one"
    if "-" in text:
        parts = text.split("-")
        if len(parts) == 2 and parts[0] in number_words and parts[1] in number_words:
            return number_words[parts[0]] + number_words[parts[1]]

    # Handle more complex numbers with units
    return _parse_complex_number(text, number_words, units)


def _parse_complex_number(text: str, number_words: dict, units: dict) -> Optional[int]:
    """
    Parse complex numbers like "one hundred twenty-three", "two thousand five"

    Args:
        text (str): Number text
        number_words (dict): Basic number word mappings
        units (dict): Unit word mappings

    Returns:
        Optional[int]: Parsed number or None if parsing fails
    """
    words = text.replace("-", " ").split()

    if not words:
        return None

    result = 0
    current = 0

    for word in words:
        if word in number_words:
            current += number_words[word]
        elif word in units:
            if word == "hundred":
                if current == 0:
                    current = 1
                current *= units[word]
            else:  # thousand, million, billion
                if current == 0:
                    current = 1
                result += current * units[word]
                current = 0
        else:
            # Unknown word, fail parsing
            return None

    result += current
    return result if result > 0 else None
