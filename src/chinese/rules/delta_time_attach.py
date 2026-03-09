# Copyright (c) 2025 Ming Yu (yuming@oppo.com), Liangliang Han (hanliangliang@oppo.com)

from ..word_level_pynini import string_file, pynutil

from ...core.processor import Processor
from ...core.utils import get_abs_path
from .base import DateBaseRule, TimeBaseRule


insert = pynutil.insert
delete = pynutil.delete


class DeltaTimeAttachRule(Processor):
    """将“时间增量 + （的） + 具体时间”组合成单个 time_relative token。
    例： 六天后(的)3时1刻 -> {'type': 'time_relative', 'offset_day': '6', 'offset_direction': '1', 'hour': '3', 'minute': '15'}
    """

    def __init__(self):
        super().__init__(name="time_relative")
        self.build_tagger()

    def build_tagger(self):
        # 复用已有的计数与时间规则
        time_cnt = TimeBaseRule().build_time_cnt_rules()
        date_cnt = DateBaseRule().build_date_cnt_rule()
        time_full = TimeBaseRule().build_time_rules()

        # 方向词表
        before_prefix = string_file(get_abs_path("../data/delta/before_prefix.tsv"))
        after_prefix = string_file(get_abs_path("../data/delta/after_prefix.tsv"))

        # 构造方向字段
        before_pre = insert('offset_direction: "') + before_prefix + insert('"')
        after_pre = insert('offset_direction: "') + after_prefix + insert('"')

        # 偏移数量（天/月/年等）
        # date_cnt/time_cnt 已经会产出 'day'/'month' 等字段

        # 模式： [前/后]+(时/日/月/年计数) + （的）? + 具体时间
        sep_de = delete("的").ques

        # 过去方向
        before_time = before_pre + time_cnt + sep_de + time_full
        before_date = before_pre + date_cnt + sep_de + time_full
        # 未来方向
        after_time = after_pre + time_cnt + sep_de + time_full
        after_date = after_pre + date_cnt + sep_de + time_full

        tagger = self.add_tokens(before_time | before_date | after_time | after_date)
        self.tagger = tagger
