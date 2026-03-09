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

from ..word_level_pynini import difference, string_file, pynutil
from pynini.lib.tagger import Tagger

from ...core.processor import Processor
from ...core.utils import get_abs_path

delete = pynutil.delete


class PostProcessor(Processor):
    """后处理器，用于文本清理和标准化"""

    def __init__(
        self,
        remove_interjections=True,
        remove_puncts=False,
        full_to_half=True,
        tag_oov=False,
    ):
        super().__init__(name="postprocessor")

        # 加载数据文件
        blacklist = string_file(get_abs_path("/data/default/blacklist.tsv"))
        puncts = string_file(get_abs_path("../data/char/punctuations_zh.tsv"))
        full2half = string_file(get_abs_path("../data/char/fullwidth_to_halfwidth.tsv"))
        zh_charset_std = string_file(
            get_abs_path("chinese/data/char/charset_national_standard_2013_8105.tsv")
        )
        zh_charset_ext = string_file(get_abs_path("../data/char/charset_extension.tsv"))

        processor = self.build_rule("")

        # 应用各种处理规则
        if remove_interjections:
            processor @= self.build_rule(delete(blacklist))

        if remove_puncts:
            processor @= self.build_rule(delete(puncts | self.PUNCT))

        if full_to_half:
            processor @= self.build_rule(full2half)

        if tag_oov:
            charset = (
                zh_charset_std
                | zh_charset_ext
                | puncts
                | self.DIGIT
                | self.ALPHA
                | self.PUNCT
                | self.SPACE
            )
            oov = difference(self.VCHAR, charset)
            processor @= Tagger("oov", oov, self.VSIGMA)._tagger

        self.processor = processor.optimize()
