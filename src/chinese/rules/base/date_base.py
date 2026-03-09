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

from ....core.utils import get_abs_path
from ...word_level_pynini import string_file, accep, union, cross, pynutil
from .number_base import NumberBaseRule

delete = pynutil.delete
insert = pynutil.insert


class DateBaseRule:
    """日期基础规则类"""

    def __init__(self):
        # 使用NumberBaseRule构建中文数字映射
        number_rule = NumberBaseRule()
        chinese_number = number_rule.build_cn_number()

        # 阿拉伯数字
        arabic_digit = string_file(get_abs_path("../../data/number/arabic_digit.tsv"))
        arabic_number = arabic_digit.plus
        digit = arabic_digit | chinese_number  # 接受阿拉伯或中文数字映射

        # 月、日中文数字映射
        # 使用NumberBaseRule构建的基础中文数字映射
        day_cn_base = chinese_number
        # 读取day_cn.tsv文件（包含"廿"等特殊日期数字）
        day_cn_file = string_file(get_abs_path("../../data/date/cn/day_cn.tsv"))
        # 合并基础数字映射和文件中的日期数字映射
        day_cn = day_cn_base | day_cn_file
        month_cn = chinese_number

        day_digit = string_file(get_abs_path("../../data/date/digit/day_digit.tsv"))
        month_digit = string_file(get_abs_path("../../data/date/digit/month_digit.tsv"))

        special_time = string_file(get_abs_path("../../data/date/special_time.tsv"))

        # 年份：阿拉伯四位年；中文四位年（逐位映射）；特殊中文年（如"两千")
        yyyy_arabic = arabic_digit**4
        # 单位中文数字逐位映射，限定恰好四位，避免将“七年”误作年份
        cn_digit_single = (
            cross("零", "0")
            | cross("〇", "0")
            | cross("○", "0")
            | cross("一", "1")
            | cross("二", "2")
            | cross("两", "2")
            | cross("三", "3")
            | cross("四", "4")
            | cross("五", "5")
            | cross("六", "6")
            | cross("七", "7")
            | cross("八", "8")
            | cross("九", "9")
        )
        yyyy_chinese = cn_digit_single + cn_digit_single + cn_digit_single + cn_digit_single
        yyyy_special = string_file(get_abs_path("../../data/date/special_year.tsv"))
        yyyy = yyyy_arabic | yyyy_chinese | yyyy_special
        # 三位年份（恰好3位）+ '年'
        yyy_arabic = string_file(get_abs_path("../../data/number/arabic_digit.tsv")) ** 3
        yyy_chinese = cn_digit_single + cn_digit_single + cn_digit_single
        yyy = yyy_arabic | yyy_chinese
        # 两位年份：两位阿拉伯数字（如17年），两位中文数字（如三三年），或前导零+一位数字（如07/零七年）
        yy = (
            (arabic_digit + arabic_digit)
            | (cn_digit_single + cn_digit_single)
            | (
                (
                    cross("零", "0")
                    | cross("〇", "0")
                    | cross("○", "0")
                    | string_file(get_abs_path("../../data/number/zero.tsv"))
                    | cross("0", "0")
                )
                + (arabic_digit | cn_digit_single)
            )
        )

        self.special_time = insert('special_time: "') + special_time + insert('"')

        self.year_char = delete("年")
        self.month_char = delete("月") | delete("月份")
        self.day_char = delete("日") | delete("号")

        self.noon = string_file(get_abs_path("../../data/time/noon.tsv"))
        # 支持分隔符左右的空格（如：2025 - 01 - 12）
        space = delete(" ").star
        # 年月日/月份/日期 分隔符：支持 / - .
        self.rmsign = space + (delete("/") | delete("-") | delete(".")) + space + insert(" ")
        # 月日分隔符：不允许 '.'，避免与纯小数冲突，且让独立“8.30”不被UTC识别
        self.mdsign = space + (delete("/") | delete("-")) + space + insert(" ")
        self.between = delete("的")

        # 年月日格式时间
        self.year_std = insert('year: "') + (yyyy) + insert('"')
        self.year_std_yyy = insert('year: "') + (yyy) + insert('"') + self.year_char
        # 对应18年、20年：两位年，作为最后备选
        self.year_std_yy = insert('year: "') + yy + insert('"') + self.year_char
        # 聚合顺序：四位年 > 三位年 > 两位年
        self.year_std_all = (self.year_std + self.year_char) | self.year_std_yyy | self.year_std_yy
        self.month_std = insert('month: "') + (month_cn | month_digit) + insert('"')
        self.day_std = insert('day: "') + (day_cn | day_digit) + insert('"')

        # 数字格式时间
        self.month_digit_std = insert('month: "') + month_digit + insert('"')
        self.day_digit_std = insert('day: "') + day_digit + insert('"')

        # 偏移时间格式（年/月/日计数：使用中文数字映射）
        # 偏移计数：接受多位阿拉伯数字或中文数字
        self.year_offset_std = insert('year: "') + (arabic_number | chinese_number) + insert('"')
        self.month_offset_std = insert('month: "') + (arabic_number | chinese_number) + insert('"')
        self.day_offset_std = insert('day: "') + (arabic_number | chinese_number) + insert('"')

        # 反向日格式
        self.anti_day_offset_std = yyyy | yyy | yy | digit

    def build_year_rules(self):
        """构建年份规则"""
        year_only = self.year_std_all + self.between.ques + self.special_time.ques
        return year_only

    def build_month_rules(self):
        """构建月份规则"""
        # 年月格式：二零二五年十月, 二零二五年的十月
        year_month_std = (
            self.year_std_all
            + self.between.ques
            + (self.month_std | self.month_digit_std)
            + self.month_char
            + self.between.ques
            + self.special_time.ques
        )

        # 年+首月 → 年+1月
        year_first_month_std = (
            self.year_std_all
            + self.between.ques
            + insert('month: "1"')
            + delete("首")
            + self.month_char
            + self.between.ques
            + self.special_time.ques
        )

        # 年+末月 → 年+12月
        year_last_month_std = (
            self.year_std_all
            + self.between.ques
            + insert('month: "12"')
            + delete("末")
            + self.month_char
            + self.between.ques
            + self.special_time.ques
        )

        # 数字格式：2026.01 2026/01 2026-01
        year_month_digit = (
            self.year_std
            + self.rmsign
            + self.month_digit_std
            + self.between.ques
            + self.special_time.ques
        )
        year_month_digit_std = year_month_digit

        # 仅月份：1月，一月，一月份
        month_only = (
            (self.month_std | self.month_digit_std)
            + self.month_char
            + self.between.ques
            + self.special_time.ques
        )

        # 首月 → 1月（无年份）
        month_first_only = (
            insert('month: "1"')
            + delete("首")
            + self.month_char
            + self.between.ques
            + self.special_time.ques
        )

        # 末月 → 12月（无年份）
        month_last_only = (
            insert('month: "12"')
            + delete("末")
            + self.month_char
            + self.between.ques
            + self.special_time.ques
        )

        # 合并所有月份规则
        month = (
            year_month_std
            | year_first_month_std
            | year_last_month_std
            | year_month_digit_std
            | month_only
            | month_first_only
            | month_last_only
        )
        return month

    def build_date_rules(self):
        """构建日期规则"""
        # 年月日格式：二零二五年十月一日/2025年10月1日/25年三月4日
        date_std = (
            self.year_std_all
            + self.between.ques
            + (self.month_std | self.month_digit_std)
            + self.month_char
            + (self.day_std | self.day_digit_std)
            + self.day_char.ques
        )

        # 数字格式：2026/01/12、2026/01/12号、2026.01.12、2026-01-12
        date_digit_std = (
            self.year_std
            + self.rmsign
            + self.month_digit_std
            + self.rmsign
            + self.day_digit_std
            + self.day_char.ques
        )

        # 数字变体：年+月.日（整体一次命中） 例如：2019年8.30 / 2019年的8.30 / 2019年08.30
        year_month_dot_day_digit = (
            self.year_std_all
            + self.between.ques
            + self.month_digit_std
            + delete(".")
            + self.day_digit_std
            + self.day_char.ques
        )

        # 月日格式
        month_date = self.build_month_date_rules()

        # 年+月+首日 → 年+月+1日
        year_month_first_day = (
            self.year_std_all
            + self.between.ques
            + (self.month_std | self.month_digit_std)
            + self.month_char
            + self.between.ques
            + insert('day: "1"')
            + delete("首")
            + self.day_char
        )

        # 年+月+末日 → 年+月+最后一日（special_time: lastday）
        year_month_last_day = (
            self.year_std_all
            + self.between.ques
            + (self.month_std | self.month_digit_std)
            + self.month_char
            + self.between.ques
            + insert('special_time: "lastday"')
            + delete("末")
            + self.day_char
        )

        # 月+首日（无年份）
        month_first_day_only = (
            (self.month_std | self.month_digit_std)
            + self.month_char
            + self.between.ques
            + insert('day: "1"')
            + delete("首")
            + self.day_char
        )

        # 月+末日（无年份）
        month_last_day_only = (
            (self.month_std | self.month_digit_std)
            + self.month_char
            + self.between.ques
            + insert('special_time: "lastday"')
            + delete("末")
            + self.day_char
        )

        # 仅日期
        date_only = (self.day_std | self.day_digit_std) + self.day_char

        # 紧凑日期格式规则
        # 重新定义阿拉伯数字和空格用于紧凑格式
        arabic_digit = string_file(get_abs_path("../../data/number/arabic_digit.tsv"))
        space = delete(" ").star

        # 8位纯数字日期格式：20250121
        # 格式：YYYY(4位) + MM(2位) + DD(2位)
        compact_date_8digit = (
            insert('year: "')
            + (arabic_digit + arabic_digit + arabic_digit + arabic_digit)
            + insert('"')
            + insert('month: "')
            + (arabic_digit + arabic_digit)
            + insert('"')
            + insert('day: "')
            + (arabic_digit + arabic_digit)
            + insert('"')
            + insert('compact_format: "YYYYMMDD"')  # 标记为紧凑格式，需要验证
        )

        # 6位年月+分隔符+日期：202501-21
        # 格式：YYYY(4位) + MM(2位) + '-' + DD(2位)
        compact_date_hyphen = (
            insert('year: "')
            + (arabic_digit + arabic_digit + arabic_digit + arabic_digit)
            + insert('"')
            + insert('month: "')
            + (arabic_digit + arabic_digit)
            + insert('"')
            + space
            + delete("-")
            + space
            + insert('day: "')
            + (arabic_digit + arabic_digit)
            + insert('"')
            + insert('compact_format: "YYYYMM-DD"')  # 标记为紧凑格式，需要验证
        )

        # 合并所有日期规则
        date = (
            date_std
            | year_month_dot_day_digit
            | date_digit_std
            | month_date
            | date_only
            | year_month_first_day
            | year_month_last_day
            | month_first_day_only
            | month_last_day_only
            | compact_date_8digit
            | compact_date_hyphen
        )  # 新增紧凑格式规则
        return date

    def build_month_date_rules(self):
        """构建月日规则"""
        # 月日格式：1月12日 (中文格式，逻辑不变)
        month_day_std = (
            (self.month_std | self.month_digit_std)
            + self.month_char
            + (self.day_std | self.day_digit_std)
            + self.day_char.ques
        )

        # 数字格式：12/3、12-3（不含'.'，避免与纯小数冲突）
        month_day_digit = (
            self.month_digit_std + self.mdsign + self.day_digit_std + self.day_char.ques
        )

        # 数字格式（严格点分，且必须带“日/号”尾缀）：9.4日 / 9.4号
        month_day_digit_dot_with_suffix = (
            self.month_digit_std + delete(".") + self.day_digit_std + self.day_char
        )

        month_day_digit_std = month_day_digit

        # 合并月日规则
        month_date = month_day_std | month_day_digit_std | month_day_digit_dot_with_suffix
        return month_date

    def build_date_cnt_rule(self):
        """构建日期计数规则"""
        # 重新定义中文数字映射
        number_rule = NumberBaseRule()
        chinese_number = number_rule.build_cn_number()
        # 本地数字定义（供周/两位等使用）
        arabic_digit = string_file(get_abs_path("../../data/number/arabic_digit.tsv"))
        arabic_number = arabic_digit.plus
        digit = arabic_digit | chinese_number
        zero = string_file(get_abs_path("../../data/number/zero.tsv"))
        yy = (digit | zero) ** 2

        year_char = delete("年")
        month_char = delete("月") | delete("个月")
        week_char = (
            delete("周") | delete("星期") | delete("礼拜") | delete("个星期") | delete("个礼拜")
        )
        day_char = delete("日") | delete("天")
        between = delete("零") | delete("加")

        # 年、月、周、日计数（使用中文数字映射）
        year_cnt = self.year_offset_std + year_char
        month_cnt = self.month_offset_std + month_char
        week_cnt = insert('week: "') + (yy | digit) + insert('"') + week_char
        day_cnt = self.day_offset_std + day_char

        # 分数日期计数（如：三天半、两个月半、2天半、2个月半）- 支持中文数字和阿拉伯数字
        number_or_chinese = chinese_number | arabic_number
        day_half_cnt = (
            insert('day: "')
            + number_or_chinese
            + insert('"')
            + day_char
            + delete("半")
            + insert('fractional: "0.5"')
        )
        month_half_cnt = (
            insert('month: "')
            + number_or_chinese
            + insert('"')
            + month_char
            + delete("半")
            + insert('fractional: "0.5"')
        )
        year_half_cnt = (
            insert('year: "')
            + number_or_chinese
            + insert('"')
            + year_char
            + delete("半")
            + insert('fractional: "0.5"')
        )

        # 数字 + 个 + 半 + 单位（如：两个半月、三个半天、两个半年）
        day_ge_half_cnt = (
            insert('day: "')
            + number_or_chinese
            + insert('"')
            + delete("个")
            + day_char
            + delete("半")
            + insert('fractional: "0.5"')
        )
        month_ge_half_cnt = (
            insert('month: "')
            + number_or_chinese
            + insert('"')
            + delete("个")
            + month_char
            + delete("半")
            + insert('fractional: "0.5"')
        )
        year_ge_half_cnt = (
            insert('year: "')
            + number_or_chinese
            + insert('"')
            + delete("个")
            + year_char
            + delete("半")
            + insert('fractional: "0.5"')
        )

        # 仅“半X”形式（半年/半月/半天）：以0为基值，携带fractional=0.5
        half_year_only = (
            delete("半") + year_char + insert('year: "0"') + insert('fractional: "0.5"')
        )
        half_month_only = (
            delete("半") + month_char + insert('month: "0"') + insert('fractional: "0.5"')
        )
        half_day_only = delete("半") + day_char + insert('day: "0"') + insert('fractional: "0.5"')

        # 年月日组合
        year_month_day_cnt = (
            self.year_offset_std
            + year_char
            + self.month_offset_std
            + month_char
            + between.ques
            + self.day_offset_std
            + day_char
        )
        # 年月组合
        year_month_cnt = (
            self.year_offset_std + year_char + between.ques + self.month_offset_std + month_char
        )
        # 月日组合
        month_day_cnt = (
            self.month_offset_std + month_char + between.ques + self.day_offset_std + day_char
        )

        # 合并所有计数规则（更具体的规则在前，减少重复匹配）
        # 先匹配分数规则，再匹配普通规则
        date_cnt = (
            day_ge_half_cnt
            | month_ge_half_cnt
            | year_ge_half_cnt
            | day_half_cnt
            | month_half_cnt
            | year_half_cnt
            | half_year_only
            | half_month_only
            | half_day_only
            | year_month_day_cnt
            | year_month_cnt
            | month_day_cnt
            | year_cnt
            | month_cnt
            | week_cnt
            | day_cnt
        )
        return date_cnt

    def build_anti_noon_rule(self):
        """构建反向日期计数规则"""
        seq_cnt = accep("第") | accep("每")
        day_char = accep("日") | accep("天")
        every_week = accep("每周几")

        # (第/每)*(天/日)下午/每周几下午
        anti_day = ((seq_cnt + self.anti_day_offset_std + day_char) | every_week) + self.noon
        return anti_day
