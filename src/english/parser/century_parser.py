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

from datetime import datetime
from .base_parser import BaseParser


class CenturyParser(BaseParser):
    """
    Century and decade parser
    Handles century and decade expressions
    """

    def parse(self, token, base_time):
        """
        Parse century or decade expression

        Args:
            token (dict): Token containing century/decade information
            base_time (datetime): Base time reference

        Returns:
            list: Time range in UTC format
        """
        modifier = token.get("modifier", "").strip('"')
        century_num = token.get("century_num", "").strip('"')
        decade = token.get("decade", "").strip('"')

        # Case 1: decade only (e.g., "the 80s")
        if decade and not modifier and not century_num:
            # Determine century based on current year
            # If decade is greater than current decade, assume last century
            # Otherwise assume current century
            current_year = base_time.year
            current_century = current_year // 100
            current_decade = current_year % 100 // 10 * 10
            decade_num = int(decade)

            # If decade > current decade, it likely refers to last century
            if decade_num > current_decade:
                target_century = current_century - 1
            else:
                target_century = current_century

            start_year = target_century * 100 + decade_num
            end_year = start_year + 9

            start_time = datetime(start_year, 1, 1, 0, 0, 0)
            end_time = datetime(end_year, 12, 31, 23, 59, 59)
            return self._format_time_result(start_time, end_time)

        # Case 2: decade + modifier + century (e.g., "seventies of last century")
        if decade and modifier:
            modifier_offset = int(modifier)
            current_century = base_time.year // 100
            target_century = current_century + modifier_offset

            decade_num = int(decade)
            start_year = target_century * 100 + decade_num
            end_year = start_year + 9

            start_time = datetime(start_year, 1, 1, 0, 0, 0)
            end_time = datetime(end_year, 12, 31, 23, 59, 59)
            return self._format_time_result(start_time, end_time)

        # Case 3: decade + century_num (e.g., "nineties of twentieth century")
        if decade and century_num:
            century = int(century_num)
            decade_num = int(decade)

            # 20th century = 1900-1999
            start_year = (century - 1) * 100 + decade_num
            end_year = start_year + 9

            start_time = datetime(start_year, 1, 1, 0, 0, 0)
            end_time = datetime(end_year, 12, 31, 23, 59, 59)
            return self._format_time_result(start_time, end_time)

        # Case 4: modifier + century (e.g., "last century")
        if modifier and not century_num:
            modifier_offset = int(modifier)
            current_century = base_time.year // 100
            target_century = current_century + modifier_offset

            start_year = target_century * 100
            end_year = start_year + 99

            start_time = datetime(start_year, 1, 1, 0, 0, 0)
            end_time = datetime(end_year, 12, 31, 23, 59, 59)
            return self._format_time_result(start_time, end_time)

        # Case 5: century_num only (e.g., "19th century")
        if century_num and not modifier:
            century = int(century_num)

            # 19th century = 1800-1899
            start_year = (century - 1) * 100
            end_year = start_year + 99

            start_time = datetime(start_year, 1, 1, 0, 0, 0)
            end_time = datetime(end_year, 12, 31, 23, 59, 59)
            return self._format_time_result(start_time, end_time)

        return []
