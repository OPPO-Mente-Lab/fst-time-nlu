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

from ...core.processor import Processor
from ...core.utils import get_abs_path
from ..word_level_pynini import string_file, accep, pynutil, union
from .base.date_base import DateBaseRule
from .base.number_base import NumberBaseRule

delete = pynutil.delete
insert = pynutil.insert


class WhitelistRule(Processor):
    """白名单规则处理器，处理预定义的时间表达式"""

    def __init__(self):
        super().__init__(name="whitelist")
        self.build_tagger()

    def build_tagger(self):
        whitelist = string_file(get_abs_path("../data/default/whitelist.tsv"))

        shiyi_num = self._build_shiyi_num()
        yidian_pattern = self._build_yidian_pattern()
        xianzai_pattern = self._build_xianzai_pattern()
        hao_pattern = self._build_hao_pattern()
        num_measure_pattern = self._build_num_measure_pattern()
        decimal_measure_pattern = self._build_decimal_measure_pattern()
        num_range_pattern = self._build_num_range_pattern()
        comparison_hour_pattern = self._build_comparison_hour_pattern()
        three_digit_hao_pattern = self._build_three_digit_hao_pattern()
        am_pm_with_letter_pattern = self._build_am_pm_with_letter_pattern()
        anti_noon = DateBaseRule().build_anti_noon_rule()

        # 对于whitelist，如果第二列是token类型，则使用该类型；否则使用默认的whitelist类型
        # 使用add_tokens来自动处理类型映射
        tagger = (insert('value: "') + (whitelist | shiyi_num | yidian_pattern | xianzai_pattern | hao_pattern | num_measure_pattern | decimal_measure_pattern | num_range_pattern | comparison_hour_pattern | three_digit_hao_pattern | am_pm_with_letter_pattern | anti_noon)) + insert('"')
        self.tagger = self.add_tokens(tagger)

    def _build_shiyi_num(self):
        postfix = accep("十") + accep("一")
        prefix = (
            accep("一")
            | accep("二")
            | accep("三")
            | accep("四")
            | accep("五")
            | accep("六")
            | accep("七")
            | accep("八")
            | accep("九")
            | accep("十")
        )
        shiyi_num = prefix + postfix

        return shiyi_num

    def _build_yidian_pattern(self):
        """构建"X一点"模式的规则
        
        从 yidian_prefix.tsv 文件读取前缀配置，构建"前缀+一点"的规则
        例如：大一点、小一点、多一点、少一点等
        
        Returns:
            构建的FST规则
        """
        # 从文件读取前缀配置
        yidian_prefix = string_file(get_abs_path("../data/default/yidian_prefix.tsv"))
        
        # 构建后缀（固定为"一点"）
        postfix = accep("一点")

        # 组合前缀和后缀：前缀 + "一点"
        yidian_pattern = yidian_prefix + postfix
        
        return yidian_pattern

    def _build_xianzai_pattern(self):
        """构建"现在X"模式的规则
        
        从 xianzai_postfix.tsv 文件读取后缀配置，构建"现在+后缀"的规则
        例如：现在怎么办、现在这么卡、现在马克龙等
        
        Returns:
            构建的FST规则
        """
        # 从文件读取后缀配置
        xianzai_postfix = string_file(get_abs_path("../data/default/xianzai_postfix.tsv"))
        
        # 构建前缀（固定为"现在"）
        prefix = accep("现在")

        # 组合前缀和后缀：现在 + 后缀
        xianzai_pattern = prefix + xianzai_postfix
        
        return xianzai_pattern

    def _build_hao_pattern(self):
        """构建"X号Y"模式的规则
        
        支持中文数字或阿拉伯数字 + "号" + 泛化词
        例如：12号楼、1号公寓、三号房、二十号教室等
        
        Returns:
            构建的FST规则
        """
        # 从文件读取后缀配置（楼、公寓、房等）
        hao_postfix = string_file(get_abs_path("../data/default/hao_postfix.tsv"))
        
        # 构建数字部分：支持阿拉伯数字和中文数字
        arabic_digit = string_file(get_abs_path("../data/number/arabic_digit.tsv"))
        arabic_number = arabic_digit.plus  # 支持多位阿拉伯数字：1, 12, 123等
        
        # 中文数字
        number_rule = NumberBaseRule()
        chinese_number = number_rule.build_cn_number()
        
        # 数字部分：阿拉伯数字或中文数字
        number = arabic_number | chinese_number
        
        # 构建模式：数字 + "号" + 后缀
        hao_pattern = number + accep("号") + hao_postfix
        
        return hao_pattern

    def _build_num_measure_pattern(self):
        """构建"十一+量词"模式的规则
        
        只匹配"十一" + 量词的组合
        例如：十一题、十一个、十一箱等
        
        Returns:
            构建的FST规则
        """
        # 从文件读取量词配置
        measure_word = string_file(get_abs_path("../data/default/measure_word.tsv"))
        
        # 只匹配"十一"
        shiyi = accep("十") + accep("一")
        
        # 构建模式：十一 + 量词
        num_measure_pattern = shiyi + measure_word
        
        return num_measure_pattern

    def _build_decimal_measure_pattern(self):
        """构建"小数+量词"模式的规则
        
        匹配小数（阿拉伯数字.阿拉伯数字）+ 量词
        例如：1.5个、3.2题、10.8箱、0.5米等
        
        Returns:
            构建的FST规则
        """
        # 读取量词配置
        measure_word = string_file(get_abs_path("../data/default/measure_word.tsv"))
        
        # 读取阿拉伯数字和小数点
        arabic_digit = string_file(get_abs_path("../data/number/arabic_digit.tsv"))
        dot = string_file(get_abs_path("../data/number/dot.tsv"))
        
        # 构建小数部分：整数部分（至少一位）+ 小数点 + 小数部分（至少一位）
        integer_part = arabic_digit.plus  # 一位或多位数字
        decimal_part = arabic_digit.plus  # 一位或多位数字
        
        # 小数：整数部分 + 点 + 小数部分
        decimal_number = integer_part + dot + decimal_part
        
        # 构建模式：小数 + 量词
        decimal_measure_pattern = decimal_number + (measure_word | accep('正常'))
        
        return decimal_measure_pattern

    def _build_num_range_pattern(self):
        """构建"数字-数字"范围模式的规则
        
        匹配"数字-数字"的模式，其中至少有一个数字是3位及以上
        例如：100-200、150-80、50-1000、1000-2000等
        
        Returns:
            构建的FST规则
        """
        # 读取阿拉伯数字
        arabic_digit = string_file(get_abs_path("../data/number/arabic_digit.tsv"))
        
        # 任意位数的数字
        any_number = arabic_digit.plus
        
        # 3位及以上的数字（100-999, 1000-9999, ...）
        three_plus_digit = arabic_digit + arabic_digit + arabic_digit + arabic_digit.star
        
        # 分隔符：连字符
        separator = accep("-") | accep("—") | accep("–") | accep(":") | accep("：")
        
        # 构建模式：至少一个数字是3位及以上
        # 情况1：第一个数字≥3位 + 分隔符 + 任意数字
        pattern1 = (three_plus_digit + separator + any_number | any_number + separator + three_plus_digit)
        
        # 情况2：任意数字 + 分隔符 + 第二个数字≥3位
        pattern2 = any_number + separator + three_plus_digit
        
        # 合并两种情况
        num_range_pattern = pattern1 | pattern2
        
        return num_range_pattern

    def _build_comparison_hour_pattern(self):
        """构建"比较词+1-24+时"模式的规则
        
        匹配"大于/小于/等于 + 1-24 + 时"的条件表达式
        例如：大于12时、小于5时、等于18时、不等于24时等
        
        Returns:
            构建的FST规则
        """
        # 比较词
        comparison = (
            accep("大于") | accep("小于") | accep("等于") |
            accep("不等于") | accep("不大于") | accep("不小于") |
            accep("超过") | accep("低于") | accep("高于") |
            accep("多于") | accep("少于") | accep("达到") |
            accep(">") | accep("<") | accep("=") | 
            accep(">=") | accep("<=") | accep("!=") | accep("==")
        )
        
        # 1-24的小时数（包括中文数字和阿拉伯数字）
        # 阿拉伯数字：1-9, 10-19, 20-24
        arabic_digit = string_file(get_abs_path("../data/number/arabic_digit.tsv"))
        hour_1_9 = arabic_digit  # 1-9
        hour_10_24 = (accep("1") | accep("2")) + arabic_digit  # 10-24
        
        # 中文数字：一到二十四
        number_rule = NumberBaseRule()
        chinese_number = number_rule.build_cn_number()
        
        # 小时数（阿拉伯或中文）
        hour_num = hour_1_9 | hour_10_24 | chinese_number
        
        # 构建模式：比较词 + 小时数 + "时"
        comparison_hour_pattern = comparison + hour_num + accep("时")
        
        return comparison_hour_pattern

    def _build_three_digit_hao_pattern(self):
        """构建"31以上数字+号"模式的规则
        
        匹配32及以上的数字后接"号"（避免与日期1-31号冲突）
        例如：32号、50号、100号、1234号等
        
        Returns:
            构建的FST规则
        """
        # 读取阿拉伯数字
        arabic_digit = string_file(get_abs_path("../data/number/arabic_digit.tsv"))
        
        # 32-39: 3[2-9]
        num_32_39 = accep("3") + (accep("2") | accep("3") | accep("4") | accep("5") | accep("6") | accep("7") | accep("8") | accep("9"))
        
        # 40-99: [4-9][0-9]
        num_40_99 = (accep("4") | accep("5") | accep("6") | accep("7") | accep("8") | accep("9")) + arabic_digit
        
        # 100及以上: [1-9][0-9]{2,}
        num_100_plus = arabic_digit + arabic_digit + arabic_digit + arabic_digit.star
        
        # 合并所有情况：32-39, 40-99, 100+
        num_above_31 = num_32_39 | num_40_99 | num_100_plus
        
        # 构建模式：≥32的数字 + "号"
        three_digit_hao_pattern = num_above_31 + accep("号")
        
        return three_digit_hao_pattern

    def _build_am_pm_with_letter_pattern(self):
        """构建"字母+a m/p m"或"a m/p m+字母"模式的规则
        
        当"a m"或"p m"（带空格）的前后有字母时，将其视为白名单
        例如：abc10 a m、10 a m xyz、test p m data等
        
        Returns:
            构建的FST规则
        """
        # 构建英文字母（A-Z, a-z）
        letter = union(*[accep(chr(i)) for i in range(ord('A'), ord('Z')+1)])
        letter = letter | union(*[accep(chr(i)) for i in range(ord('a'), ord('z')+1)])
        
        # 字母序列（至少一个）
        letters = letter.plus
        
        # 任意字符序列（用于中间部分）- 包括数字、字母、空格等
        arabic_digit = string_file(get_abs_path("../data/number/arabic_digit.tsv"))
        any_char = letter | arabic_digit | accep(" ")
        
        # "a m" 或 "p m" (带空格)
        am_space = accep("a") + accep(" ") + accep("m")
        pm_space = accep("p") + accep(" ") + accep("m")
        am_pm_space = am_space | pm_space
        
        # 也支持大写
        AM_space = accep("A") + accep(" ") + accep("M")
        PM_space = accep("P") + accep(" ") + accep("M")
        AM_PM_space = AM_space | PM_space
        
        # 混合大小写
        Am_space = accep("A") + accep(" ") + accep("m")
        Pm_space = accep("P") + accep(" ") + accep("m")
        Am_Pm_space = Am_space | Pm_space
        
        aM_space = accep("a") + accep(" ") + accep("M")
        pM_space = accep("p") + accep(" ") + accep("M")
        aM_pM_space = aM_space | pM_space
        
        all_am_pm = am_pm_space | AM_PM_space | Am_Pm_space | aM_pM_space
        
        # 模式1: 字母 + 任意字符 + "a m/p m"
        # 例如: "abc10 a m"
        pattern1 = letters + any_char.star + all_am_pm
        
        # 模式2: "a m/p m" + 任意字符 + 字母
        # 例如: "a m xyz"
        pattern2 = all_am_pm + any_char.star + letters
        
        # 合并两种模式
        am_pm_with_letter_pattern = pattern1 | pattern2
        
        return am_pm_with_letter_pattern
