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

from ..word_level_pynini import string_file, union, cross, pynutil

from ...core.processor import Processor
from ...core.utils import get_abs_path
from .base import DateBaseRule, LunarBaseRule, PeriodBaseRule, RelativeBaseRule
from .base.number_base import NumberBaseRule

insert = pynutil.insert
delete = pynutil.delete


class PeriodRule(Processor):
    """时间段规则处理器"""

    def __init__(self):
        super().__init__(name="time_period")
        self.month = DateBaseRule().build_month_rules()
        self.year = DateBaseRule().build_year_rules()
        self.relative_month = RelativeBaseRule().build_month_rules()
        self.relative_std = RelativeBaseRule().build_std_rules()
        self.lunar_month = LunarBaseRule().build_month_rules()
        self.period_decade = PeriodBaseRule().build_decade_rules()
        self.period_century = PeriodBaseRule().build_century_rules()
        self.build_tagger()

    def build_tagger(self):
        # 使用NumberBaseRule构建中文数字映射
        number_rule = NumberBaseRule()
        chinese = number_rule.build_cn_number()
        arabic = string_file(get_abs_path("../data/number/arabic_digit.tsv")).plus
        number = arabic | chinese

        # 加载时间段相关数据文件
        period_prefix = (
            insert('offset_direction: "')
            + string_file(get_abs_path("../data/period/period_prefix.tsv"))
            + insert('"')
        )
        # 改为仅写入原文 value，不做FST数值映射
        period_num = insert('offset: "') + number + insert('"')
        period_type = (
            insert('unit: "')
            + string_file(get_abs_path("../data/period/period_unit.tsv"))
            + insert('"')
        )
        period_month = (
            insert('month_period: "')
            + string_file(get_abs_path("../data/period/period_month.tsv"))
            + insert('"')
        )
        period_year = (
            insert('year_period: "')
            + string_file(get_abs_path("../data/period/period_year.tsv"))
            + insert('"')
        )
        # 增加最近、近期这类无数字的情况
        period_word = (
            insert('period_word: "')
            + string_file(get_abs_path("../data/period/period_word.tsv"))
            + insert('"')
        )

        # 季度相关规则
        # 加载季度数字映射（一、二、三、四 -> 1, 2, 3, 4）
        quarter_num_mapped = string_file(get_abs_path("../data/period/quarter_num.tsv"))

        # 1. "第X季度"、"第X个季度"（带"第"）
        quarter_ordinal = (
            delete("第")
            + insert('quarter: "')
            + quarter_num_mapped
            + insert('"')
            + delete("个").ques
            + delete("季度")
        )

        # 2. "X季度"（不带"第"）- 一季度、二季度、1季度、2季度
        quarter_direct = insert('quarter: "') + quarter_num_mapped + insert('"') + delete("季度")

        # 3. "首季度"（第一季度的别称）
        quarter_first = delete("首") + insert('quarter: "1"') + delete("季度")

        # 4. "Q1季度"、"Q2季度"等
        quarter_q_style = (
            delete(union("Q", "q"))
            + insert('quarter: "')
            + union("1", "2", "3", "4")
            + insert('"')
            + delete("季度").ques  # "季度"可选
        )

        # 合并所有季度规则
        quarter_all = quarter_ordinal | quarter_direct | quarter_first | quarter_q_style

        # 季节相关规则
        # 加载季节数据文件
        season_data = string_file(get_abs_path("../data/period/season.tsv"))

        # 1. 完整季节词：春季、夏季、秋季、冬季、春天、夏天、秋天、冬天
        season_full = insert('season: "') + season_data + insert('"')

        # 2. 年份+季节单字：今年春、明年夏、2021年秋
        # 需要确保只有跟在年份后才识别单字，不包括周偏移
        season_single = union("春", "夏", "秋", "冬")
        year_season_single = (
            (self.year | self.relative_month)  # 只包含年份和月份偏移，不包含周偏移
            + insert('season: "')
            + season_single
            + insert('"')
        )

        # 3. 半年相关规则
        # 3a. 完整的半年词（上半年、下半年）已通过period_year.tsv识别为year_period
        # 3b. 年份+半年：21年上半年、明年下半年 → 由合并器处理
        # year_half_year规则已移除，以降低FST时延（"上"和"下"是高频字符）

        # 4. 伊始相关规则
        # 4a. 单独的伊始：不识别（避免过度识别）
        # 4b. 年份+伊始：通过合并器处理

        # 标准时间段表达式
        period_std = period_prefix + period_num + period_type

        # 带分数的时间段表达式（如：这两年半、三个月半）
        # 形式一：数字 + 单位 + 半（原有顺序）
        period_fractional = (
            period_prefix + period_num + period_type + delete("半") + insert('fractional: "0.5"')
        )

        # 形式二：数字 + （个） + 半 + 单位（如：三个半月、两年半）
        # 注意此处“半”在单位之前，需要在插入 unit 之前删除“半”并产出 fractional
        unit_fst = string_file(get_abs_path("../data/period/period_unit.tsv"))
        period_num_ge_half = (
            period_prefix
            + period_num
            + delete("个").ques
            + delete("半")
            + insert('fractional: "0.5"')
            + insert('unit: "')
            + unit_fst
            + insert('"')
        )

        # 形式三：无数字，仅“半 + 单位”（如：最近半个月、过去半年）
        period_half_only = (
            period_prefix
            + insert('offset: "0"')
            + delete("半")
            + insert('fractional: "0.5"')
            + insert('unit: "')
            + unit_fst
            + insert('"')
        )

        # 兼容旧写法：数字 + 个 + 单位 + 半（如：三个 月 半）
        period_fractional_ge = (
            period_prefix
            + period_num
            + delete("个")
            + period_type
            + delete("半")
            + insert('fractional: "0.5"')
        )

        # 构建各种时间段规则
        # 相对月份上、中、下旬
        period_relative_month_std = self.relative_month + period_month
        # 阳历上、中、下旬
        period_utc_month_std = self.month + period_month
        # 农历上、中、下旬
        period_lunar_month_std = self.lunar_month + period_month
        # 年底、年初
        period_relative_year_std = (self.relative_std | self.year) + period_year
        # 单独的年底、年初（没有前缀）
        period_year_alone = period_year

        # 年代、世纪、年代+世纪（在PeriodBaseRule中同样改为接受原文数词）
        period_century_decade = (
            self.period_decade | self.period_century | self.period_century + self.period_decade
        )

        # 合并所有时间段规则
        # 优先匹配“数字+(个)?半+单位”和“半+单位”，以覆盖自然表达
        tagger = self.add_tokens(
            period_num_ge_half
            | period_half_only
            | period_fractional_ge
            | period_fractional
            | period_std
            | period_relative_month_std
            | period_utc_month_std
            | period_lunar_month_std
            | period_word
            | period_century_decade
            | period_relative_year_std
            | period_year_alone
            | quarter_all
            | season_full
            | year_season_single
        )
        self.tagger = tagger
