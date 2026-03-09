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

from datetime import datetime, timedelta


def fathers_day(year):
    """
    计算父亲节的日期

    Args:
        year (int): 年份

    Returns:
        list: [月份, 日期]
    """
    # 找到6月1号是星期几（0=周一，6=周日）
    first_june = datetime(year, 6, 1)
    weekday = first_june.weekday()  # Monday is 0 and Sunday is 6

    # 计算偏移量，使得到达第三个星期日
    # 如果6月1号是星期日，则偏移14天；否则偏移 (6 - weekday + 7) % 7 + 14
    offset = (6 - weekday + 7) % 7 + 14
    fathers_day_date = first_june + timedelta(days=offset)
    # 返回月和日组成的元组
    return [int(fathers_day_date.month), int(fathers_day_date.day)]


def mothers_day(year):
    """
    计算母亲节的日期

    Args:
        year (int): 年份

    Returns:
        list: [月份, 日期]
    """
    # 确保year是整数，如果传入的是datetime对象则提取年份
    # 找到5月1号是星期几（0=周一，6=周日）
    first_may = datetime(year, 5, 1)
    weekday = first_may.weekday()  # Monday is 0 and Sunday is 6
    # 计算偏移量，使得到达第2个星期日
    # 如果5月1号是星期日，则偏移7天；否则偏移 (6 - weekday + 7) % 7 + 7
    offset = (6 - weekday + 7) % 7 + 7
    mothers_day_date = first_may + timedelta(days=offset)
    # 返回月和日组成的元组
    return [int(mothers_day_date.month), int(mothers_day_date.day)]


def gives_day(year):
    """
    计算感恩节的日期

    Args:
        year (int): 年份

    Returns:
        list: [月份, 日期]
    """
    # 找到11月1号是星期几（0=周一，6=周日）
    first_dec = datetime(year, 11, 1)
    weekday = first_dec.weekday()  # Monday is 0 and Sunday is 6
    # 计算偏移量，使得到达第4个星期4
    # 如果11月1号是星期4，则偏移7天；否则偏移 (3 - weekday + 7) % 7 + 21
    offset = (3 - weekday + 7) % 7 + 21
    gives_day_date = first_dec + timedelta(days=offset)
    # 返回月和日组成的元组
    return [int(gives_day_date.month), int(gives_day_date.day)]
