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
from ...word_level_pynini import string_file, union, pynutil
from .number_base import NumberBaseRule

delete = pynutil.delete
insert = pynutil.insert


class TimeBaseRule:
    """时间基础规则类"""

    def __init__(self):
        # 使用NumberBaseRule构建中文数字映射
        number_rule = NumberBaseRule()
        chinese_number = number_rule.build_cn_number()

        hour_digit = string_file(get_abs_path("../../data/time/digit/hour_digit.tsv"))
        minute_digit = string_file(get_abs_path("../../data/time/digit/minute_digit.tsv"))
        second_digit = string_file(get_abs_path("../../data/time/digit/second_digit.tsv"))

        noon = string_file(get_abs_path("../../data/time/noon.tsv"))

        # 时间分隔符（移除'-'，避免与日期分隔符冲突）
        self.colon = delete(":") | delete("：")
        self.hour_past_char = delete("过") | delete("零")  # 二点过三分，2点过3分，2点零3分

        # 时间单位字符
        self.hour_char = delete("点") | delete("时")
        self.minute_char = delete("分") | delete("分钟")
        self.second_char = delete("秒") | delete("秒钟")

        # 时间计数单位
        self.hour_cnt_char = delete("小时") | delete("钟头") | delete("个小时") | delete("个钟头")
        self.minute_cnt_char = delete("分钟") | delete("分") | delete("钟")
        self.second_cnt_char = delete("秒") | delete("秒钟")

        # 时间格式规则（使用中文数字映射）
        self.noon_std = insert('noon: "') + noon + insert('"')
        # 支持更大的数字范围：中文数字 + 小时digit + 阿拉伯数字
        arabic_digit = string_file(get_abs_path("../../data/number/arabic_digit.tsv"))
        arabic_number = arabic_digit.plus
        self.hour_std = (
            insert('hour: "') + (chinese_number | hour_digit | arabic_number) + insert('"')
        )
        self.minute_std = (
            insert('minute: "') + (chinese_number | minute_digit | arabic_number) + insert('"')
        )
        self.second_std = (
            insert('second: "') + (chinese_number | second_digit | arabic_number) + insert('"')
        )

        # 数字格式时间
        self.hour_digit_std = insert('hour: "') + hour_digit + insert('"')
        self.minute_digit_std = insert('minute: "') + minute_digit + insert('"')
        self.second_digit_std = insert('second: "') + second_digit + insert('"')

    def build_time_rules(self):
        """构建时间规则"""
        # 格式【时分秒】：下午一点三十分五十秒/下午一点三十分五十/下午1点30分50秒/下午1点30分50
        time_std = (
            self.noon_std.ques
            + self.hour_std
            + self.hour_char
            + self.minute_std
            + self.minute_char
            + self.second_std
            + self.second_char.ques
        )

        # 新增：点半（自动补 30 分）
        time_hour_half = (
            self.noon_std.ques
            + self.hour_std
            + self.hour_char
            + delete("半")
            + insert('minute: "30"')
        )

        # 新增：一刻钟表达（如：两点一刻）
        time_hour_quarter = (
            self.noon_std.ques
            + self.hour_std
            + self.hour_char
            + (
                delete("一") + delete("刻") + insert('minute: "15"')
                | delete("二") + delete("刻") + insert('minute: "30"')
                | delete("三") + delete("刻") + insert('minute: "45"')
                | delete("1") + delete("刻") + insert('minute: "15"')
                | delete("2") + delete("刻") + insert('minute: "30"')
                | delete("3") + delete("刻") + insert('minute: "45"')
            )
        )

        # 格式 上午8:30:30/上午8-30-30
        time_digit_std = (
            self.noon_std.ques
            + self.hour_digit_std
            + self.colon
            + self.minute_digit_std
            + self.colon
            + self.second_digit_std
            + delete(" ").ques
        )

        # 可选时尾缀（整/正/钟等），需在后续多个模式中复用
        hour_tail = (
            delete("整")
            | delete("正")
            | delete("钟")
            | delete("點")
            | delete("點鐘")
            | delete("点钟")
        )

        # 格式【时分】：区分是否带“分”
        # 1) 带“分”→保持原有宽松策略（中文/阿拉伯分钟均可）
        time_hour_minute_with_fen = (
            self.noon_std.ques
            + self.hour_std
            + self.hour_char
            + hour_tail.ques
            + self.minute_std
            + self.minute_char
        )

        # 2) 不带“分”→分钟限定为0-59
        # - 阿拉伯分钟：使用digit词表
        # - 中文分钟：限定为“零一..零九 / 十 / 十一..十九 / 二十..五十九”
        ones_cn_to_num = (
            (delete("一") + insert("1"))
            | (delete("二") + insert("2"))
            | (delete("三") + insert("3"))
            | (delete("四") + insert("4"))
            | (delete("五") + insert("5"))
            | (delete("六") + insert("6"))
            | (delete("七") + insert("7"))
            | (delete("八") + insert("8"))
            | (delete("九") + insert("9"))
        )
        tens_head_cn_to_num = (
            (delete("二") + insert("2"))
            | (delete("三") + insert("3"))
            | (delete("四") + insert("4"))
            | (delete("五") + insert("5"))
        )
        # 中文分钟数值（不带“分”）
        minute_cn_num = (
            (delete("零") + ones_cn_to_num)  # 零一..零九 → 1..9
            | (delete("十") + insert("10"))  # 十 → 10
            | (insert("1") + delete("十") + ones_cn_to_num)  # 十一..十九 → 11..19
            | (tens_head_cn_to_num + delete("十") + insert("0"))  # 十位 → 20/30/40/50
            | (tens_head_cn_to_num + delete("十") + ones_cn_to_num)  # 21..59
        )
        minute_cn_no_fen_std = insert('minute: "') + minute_cn_num + insert('"')

        time_hour_minute_no_fen = (
            self.noon_std.ques
            + self.hour_std
            + self.hour_char
            + hour_tail.ques
            + (self.minute_digit_std | minute_cn_no_fen_std)
        )

        time_hour_minute_normal = time_hour_minute_with_fen | time_hour_minute_no_fen

        # 带“过”的用法：也区分是否带“分”
        time_hour_minute_past_with_fen = (
            self.noon_std.ques
            + self.hour_std
            + self.hour_char
            + hour_tail.ques
            + self.hour_past_char
            + self.minute_std
            + self.minute_char
            + insert("past_key: past")
        )

        time_hour_minute_past_no_fen = (
            self.noon_std.ques
            + self.hour_std
            + self.hour_char
            + hour_tail.ques
            + self.hour_past_char
            + (self.minute_digit_std | minute_cn_no_fen_std)
            + insert("past_key: past")
        )

        # 格式 上午8:30
        time_digit_hour_minute = (
            self.noon_std.ques + self.hour_digit_std + self.colon + self.minute_digit_std
        )

        # 格式 15.30分（用点号代替冒号，但必须有"分"字）
        time_digit_hour_minute_dot = (
            self.noon_std.ques
            + self.hour_digit_std
            + delete(".")
            + self.minute_digit_std
            + self.minute_char
        )

        # 格式 【时】：上午八点/上午8时/上午十一点整/晚上十一点钟
        # 在“点/时”后允许可选的“整/正/钟”等词尾
        time_hour_std = (
            self.noon_std.ques + self.hour_std + self.hour_char + hour_tail.ques + delete(" ").ques
        )

        # 合并所有时间规则
        time = (
            time_std
            | time_hour_half
            | time_hour_quarter
            | time_digit_std
            | time_hour_minute_normal
            | (time_hour_minute_past_with_fen | time_hour_minute_past_no_fen)
            | time_digit_hour_minute
            | time_digit_hour_minute_dot
            | time_hour_std
            | self.noon_std
        )
        return time

    def build_time_cnt_rules(self):
        """构建时间计数规则"""
        # 重新定义中文数字映射
        number_rule = NumberBaseRule()
        chinese_number = number_rule.build_cn_number()

        # 格式 【时】
        hour_cnt = self.hour_std + self.hour_cnt_char
        # 格式 【分】
        minute_cnt = self.minute_std + self.minute_cnt_char
        # 格式 【秒】
        second_cnt = self.second_std + self.second_cnt_char
        # 格式 【时 + 分】
        hour_minute_cnt = hour_cnt + minute_cnt
        # 格式 【分 + 秒】
        minute_second_cnt = minute_cnt + second_cnt

        # 新增：半小时 -> +30 分钟；半分钟 -> +30 秒
        half_hour_cnt = insert('minute: "30"') + (delete("半") + self.hour_cnt_char)
        # 修改：半钟 -> +30 秒，但只匹配单独的"半钟"，不匹配"X分半钟"
        # 使用更精确的规则，只匹配单独的"半钟"
        half_minute_cnt = insert('second: "30"') + (delete("半") + delete("钟"))

        # 新增：一刻钟计数 -> +15 分钟
        quarter_minute_cnt = insert('minute: "15"') + (
            delete("一") + delete("刻") + self.minute_cnt_char
        )

        # 新增：数字+半+单位（如：两个半小时、三天半）
        number_half_unit = (
            insert('value: "')
            + chinese_number
            + insert('"')
            + delete("半")
            + insert('fractional: "0.5"')
            + (
                self.hour_cnt_char
                | self.minute_cnt_char
                | self.second_cnt_char
                | (delete("天") + insert('day: "1"'))
                | (delete("日") + insert('day: "1"'))
                | (delete("月") + insert('month: "1"'))
                | (delete("年") + insert('year: "1"'))
            )
        )

        # 新增：数字+半+个+单位（如：两个半月、三个半天）
        number_half_ge_unit_extended = (
            insert('value: "')
            + chinese_number
            + insert('"')
            + delete("半")
            + insert('fractional: "0.5"')
            + delete("个")
            + (
                self.hour_cnt_char
                | self.minute_cnt_char
                | self.second_cnt_char
                | (delete("天") + insert('day: "1"'))
                | (delete("日") + insert('day: "1"'))
                | (delete("月") + insert('month: "1"'))
                | (delete("年") + insert('year: "1"'))
            )
        )

        # 新增：数字+半+个+单位（如：两个半小时）
        number_half_ge_unit = (
            insert('value: "')
            + chinese_number
            + insert('"')
            + delete("半")
            + insert('fractional: "0.5"')
            + delete("个")
            + (self.hour_cnt_char | self.minute_cnt_char | self.second_cnt_char)
        )

        # 合并时间计数规则
        time_cnt = (
            hour_cnt
            | minute_cnt
            | second_cnt
            | hour_minute_cnt
            | minute_second_cnt
            | half_hour_cnt
            | half_minute_cnt
            | quarter_minute_cnt
            | number_half_unit
            | number_half_ge_unit_extended
            | number_half_ge_unit
        )
        return time_cnt
