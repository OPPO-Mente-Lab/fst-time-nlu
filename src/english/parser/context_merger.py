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
from dateutil.relativedelta import relativedelta
from ...core.logger import get_logger
from .mergers.range_merger import RangeMerger
from .mergers.holiday_merger import HolidayMerger
from .mergers.time_expression_merger import TimeExpressionMerger
from .mergers.modifier_merger import ModifierMerger
from .mergers.duration_merger import DurationMerger
from .mergers.utc_merger import UTCMerger
from .mergers.period_merger import PeriodMerger
from .mergers.delta_merger import DeltaMerger
from .mergers.rules.priority_0_rules import Priority0Rules
from .mergers.rules.priority_1_rules import Priority1Rules
from .mergers.rules.priority_2_rules import Priority2Rules
from .mergers.rules.priority_3_rules import Priority3Rules
from .mergers.rules.priority_4_rules import Priority4Rules
from .mergers.context.of_injection_merger import OfInjectionMerger
from .time_utils import (
    get_month_range,
    month_name_to_number,
    extract_day_value,
    is_digit_sequence,
    skip_empty_tokens,
    skip_the_token,
    extract_day_value_from_tokens,
)


class ContextMerger:
    """Context merger for English time expressions, handling complex time merging logic"""

    def __init__(self, parsers):
        """
        Initialize context merger

        Args:
            parsers (dict): Dictionary containing various time parsers
        """
        self.parsers = parsers
        self.logger = get_logger(__name__)

        # Initialize mergers (order matters due to dependencies)
        # Step 1: Initialize independent mergers
        self.range_merger = RangeMerger(parsers)
        self.holiday_merger = HolidayMerger(parsers)
        self.modifier_merger = ModifierMerger(parsers)
        self.duration_merger = DurationMerger(parsers)

        # Step 2: Initialize TimeExpressionMerger (needs context_merger, but we'll set it later)
        self.time_expression_merger = TimeExpressionMerger(parsers, context_merger=None)
        self.time_expression_merger.context_merger = self

        # Step 3: Initialize UTCMerger and PeriodMerger (need time_expression_merger)
        self.utc_merger = UTCMerger(parsers, time_expression_merger=self.time_expression_merger)
        self.period_merger = PeriodMerger(
            parsers, time_expression_merger=self.time_expression_merger
        )

        # Step 4: Initialize DeltaMerger (needs utc_merger)
        self.delta_merger = DeltaMerger(parsers, utc_merger=self.utc_merger)

        # Step 5: Initialize context sub-mergers
        self.of_injection_merger = OfInjectionMerger(parsers, self)

        # Step 6: Initialize rule processors
        self.rule_processors = [
            Priority0Rules(self),
            Priority1Rules(self),
            Priority2Rules(self),
            Priority3Rules(self),
            Priority4Rules(self),
        ]

    def try_merge(self, i, tokens, base_time):  # noqa: C901
        """
        Try to merge time expressions in tokens

        Args:
            i (int): Current token index
            tokens (list): List of tokens
            base_time (datetime): Base time reference

        Returns:
            tuple: (merged_results_list, jump_count) or None
        """
        n = len(tokens)
        if i >= n:
            return None

        # Try each rule processor in priority order
        for rule_processor in self.rule_processors:
            result = rule_processor.try_merge(i, tokens, base_time)
            if result is not None:
                return result

        return None

    def _try_merge_of_injection(self, i, tokens, base_time):  # noqa: C901
        """Try to merge patterns of the form: X + 'of' + Y, by injecting Y's temporal
        context (year/month/week/quarter) into X.

        This method delegates to OfInjectionMerger.
        """
        return self.of_injection_merger.try_merge(i, tokens, base_time)

    def _check_false_time_recognition(self, i, tokens):  # noqa: C901
        """Delegate to UTCMerger"""
        return self.utc_merger.check_false_time_recognition(i, tokens)

    def _merge_utc_with_relative(self, utc_token, relative_token, base_time):
        """Delegate to UTCMerger"""
        return self.utc_merger.merge_utc_with_relative(utc_token, relative_token, base_time)

    def _merge_relative_with_utc(self, relative_token, utc_token, base_time):
        """Delegate to UTCMerger"""
        return self.utc_merger.merge_relative_with_utc(relative_token, utc_token, base_time)

    def _merge_weekday_with_utc(self, weekday_token, utc_token, base_time):
        """Delegate to UTCMerger"""
        return self.utc_merger.merge_weekday_with_utc(weekday_token, utc_token, base_time)

    def _adjust_utc_with_period_token(self, utc_token, period_token, base_time):
        """Delegate to UTCMerger"""
        return self.utc_merger.adjust_utc_with_period_token(utc_token, period_token, base_time)

    def _merge_modifier_with_holiday(self, modifier_token, holiday_token, base_time):
        """Delegate to HolidayMerger"""
        return self.holiday_merger.merge_modifier_with_holiday(
            modifier_token, holiday_token, base_time
        )

    def _merge_holiday_with_year(self, holiday_token, year_token, base_time):
        """Delegate to HolidayMerger"""
        return self.holiday_merger.merge_holiday_with_year(holiday_token, year_token, base_time)

    def _merge_holiday_with_time(self, holiday_token, time_token, base_time):
        """Delegate to HolidayMerger"""
        return self.holiday_merger.merge_holiday_with_time(holiday_token, time_token, base_time)

    def _merge_period_with_holiday(self, period_token, holiday_token, base_time):
        """Delegate to HolidayMerger"""
        return self.holiday_merger.merge_period_with_holiday(period_token, holiday_token, base_time)

    def _merge_holiday_with_year_modifier(self, holiday_token, year_modifier_token, base_time):
        """Delegate to HolidayMerger"""
        return self.holiday_merger.merge_holiday_with_year_modifier(
            holiday_token, year_modifier_token, base_time
        )

    def _merge_delta_with_holiday(self, delta_token, holiday_token, base_time):
        """Delegate to HolidayMerger"""
        return self.holiday_merger.merge_delta_with_holiday(delta_token, holiday_token, base_time)

    def _merge_modifier_with_weekday(self, modifier_token, weekday_token, base_time):
        """Delegate to merger"""
        return self.modifier_merger.merge_modifier_with_weekday(
            modifier_token, weekday_token, base_time
        )

    def _handle_week_after_next(self, base_time):
        """Delegate to merger"""
        return self.modifier_merger.handle_week_after_next(base_time)

    def _handle_named_month_after_next(self, month_name, base_time):
        """Delegate to merger"""
        return self.modifier_merger.handle_named_month_after_next(month_name, base_time)

    def _merge_holiday_with_year_range(self, holiday_token, range_token, base_time):
        """Delegate to HolidayMerger"""
        return self.holiday_merger.merge_holiday_with_year_range(
            holiday_token, range_token, base_time
        )

    def _merge_holiday_with_time_delta(self, holiday_token, delta_token, base_time):
        """Delegate to HolidayMerger"""
        return self.holiday_merger.merge_holiday_with_time_delta(
            holiday_token, delta_token, base_time
        )

    def _merge_weekday_period_with_month(self, weekday_token, month_token, base_time):
        """Delegate to PeriodMerger"""
        return self.period_merger.merge_weekday_period_with_month(
            weekday_token, month_token, base_time
        )

    def _merge_time_with_period(self, time_token, period_token, base_time):  # noqa: C901
        """Delegate to merger"""
        return self.time_expression_merger.merge_time_with_period(
            time_token, period_token, base_time
        )

    def _merge_past_time(self, minute_token, target_time_token, base_time):
        """Delegate to merger"""
        return self.time_expression_merger.merge_past_time(
            minute_token, target_time_token, base_time
        )

    def _merge_to_time(self, minute_token, target_time_token, base_time):
        """Delegate to merger"""
        return self.time_expression_merger.merge_to_time(minute_token, target_time_token, base_time)

    def _merge_fraction_past_period(self, fraction_token, period_token, base_time):
        """Delegate to merger"""
        return self.time_expression_merger.merge_fraction_past_period(
            fraction_token, period_token, base_time
        )

    def _merge_fraction_to_period(self, fraction_token, period_token, base_time):  # noqa: C901
        """Delegate to merger"""
        return self.time_expression_merger.merge_fraction_to_period(
            fraction_token, period_token, base_time
        )

    def _merge_number_minutes_past_period(self, num1_token, num2_token, period_token, base_time):
        """Delegate to TimeExpressionMerger"""
        return self.time_expression_merger.merge_number_minutes_past_period(
            num1_token, num2_token, period_token, base_time
        )

    def _merge_number_minutes_past_period_single(self, minutes, period_token, base_time):
        """Delegate to TimeExpressionMerger"""
        return self.time_expression_merger.merge_number_minutes_past_period_single(
            minutes, period_token, base_time
        )

    def _try_merge_time_with_year_modifier(self, i, tokens, base_time):  # noqa: C901
        """Delegate to merger"""
        return self.modifier_merger.try_merge_time_with_year_modifier(i, tokens, base_time)

    def _try_merge_from_to_range(self, i, tokens, base_time):  # noqa: C901
        """Delegate to RangeMerger"""
        return self.range_merger.try_merge(i, tokens, base_time)

    def _try_merge_to_range(self, i, tokens, base_time):  # noqa: C901
        """Delegate to RangeMerger"""
        return self.range_merger.try_merge(i, tokens, base_time)

    def _try_merge_prefix_range(self, i, tokens, base_time):  # noqa: C901
        """Delegate to RangeMerger"""
        return self.range_merger.try_merge(i, tokens, base_time)

    def _merge_time_range(  # noqa: C901
        self,
        start_token,
        end_token,
        modifier_token,
        base_time,
        prefix_modifier=False,
        start_modifier_token=None,
        end_modifier_token=None,
    ):
        """Delegate to RangeUtils"""
        return self.range_merger.range_utils.merge_time_range(
            start_token,
            end_token,
            modifier_token,
            base_time,
            prefix_modifier,
            start_modifier_token,
            end_modifier_token,
        )

    def _apply_modifier_to_base_time(self, modifier_token, base_time):  # noqa: C901
        """Delegate to merger"""
        return self.modifier_merger.apply_modifier_to_base_time(modifier_token, base_time)

    def _parse_time_token(self, token, base_time):
        """Delegate to UTCMerger"""
        return self.utc_merger.parse_time_token(token, base_time)

    def _merge_utc_date_components(self, i, tokens, base_time):  # noqa: C901
        """Delegate to UTCMerger"""
        return self.utc_merger.merge_utc_date_components(i, tokens, base_time)

    def _check_on_holiday_context(self, i, tokens):
        """Delegate to HolidayMerger"""
        return self.holiday_merger.check_on_holiday_context(i, tokens)

    def _handle_on_holiday_single_day(self, i, tokens, base_time):
        """Delegate to HolidayMerger"""
        return self.holiday_merger.handle_on_holiday_single_day(i, tokens, base_time)

    def _handle_weekday_after_next_multiple(self, weekday_token, after_next_count, base_time):
        """Delegate to ModifierMerger"""
        return self.modifier_merger.handle_weekday_after_next_multiple(
            weekday_token, after_next_count, base_time
        )

    def _merge_utc_with_delta(self, utc_token, delta_token, base_time):  # noqa: C901
        """Delegate to merger"""
        return self.utc_merger.merge_utc_with_delta(utc_token, delta_token, base_time)

    def _get_month_range(self, base_time, month=None):
        """Delegate to time_utils"""
        return get_month_range(base_time, month=None)

    def _month_name_to_number(self, month_name):
        """Delegate to time_utils"""
        return month_name_to_number(month_name)

    def _try_merge_between_and_range(self, i, tokens, base_time):  # noqa: C901
        """Delegate to RangeMerger"""
        return self.range_merger.try_merge(i, tokens, base_time)

    def _try_merge_day_to_day_month(self, i, tokens, base_time):
        """Delegate to RangeMerger"""
        return self.range_merger.try_merge(i, tokens, base_time)

    def _try_merge_from_day_to_day_month(self, i, tokens, base_time):  # noqa: C901
        """Delegate to RangeMerger"""
        return self.range_merger.try_merge(i, tokens, base_time)

    def _try_merge_month_day_to_day(self, i, tokens, base_time):  # noqa: C901
        """Delegate to RangeMerger"""
        return self.range_merger.try_merge(i, tokens, base_time)

    def _try_merge_day_to_day_month_direct(self, i, tokens, base_time):  # noqa: C901
        """Delegate to RangeMerger"""
        return self.range_merger.try_merge(i, tokens, base_time)

    def _try_merge_compact_date_range(self, i, tokens, base_time):
        """Delegate to RangeMerger"""
        return self.range_merger.try_merge(i, tokens, base_time)

    def _try_merge_from_compact_date_range(self, i, tokens, base_time):
        """Delegate to RangeMerger"""
        return self.range_merger.try_merge(i, tokens, base_time)

    def _try_merge_month_compact_date_range(self, i, tokens, base_time):  # noqa: C901
        """Delegate to RangeMerger"""
        return self.range_merger.try_merge(i, tokens, base_time)

    def _extract_day_from_incorrect_parsing(self, token):
        """Delegate to RangeUtils"""
        return self.range_merger.range_utils.extract_day_from_incorrect_parsing(token)

    def _check_on_weekday_suffix(self, time_b_idx, tokens):
        """Delegate to RangeUtils"""
        return self.range_merger.range_utils.check_on_weekday_suffix(self, time_b_idx, tokens)

    def _merge_time_range_with_weekday(
        self, start_token, end_token, weekday_token, modifier_token, base_time
    ):
        """Delegate to RangeUtils"""
        return self.range_merger.range_utils.merge_time_range_with_weekday(
            start_token, end_token, weekday_token, modifier_token, base_time
        )

    def _try_merge_weekday_time_range(self, i, tokens, base_time):
        """Delegate to RangeMerger"""
        return self.range_merger.try_merge_weekday_time_range(i, tokens, base_time)

    def _is_from_day_to_day_of_month_pattern(self, i, tokens):  # noqa: C901
        """Delegate to RangeUtils"""
        return self.range_merger.range_utils.is_from_day_to_day_of_month_pattern(self, i, tokens)

    def _skip_empty_tokens(self, tokens, start_idx):
        """Delegate to time_utils"""
        return skip_empty_tokens(tokens, start_idx)

    def _skip_the_token(self, tokens, start_idx):
        """Delegate to time_utils"""
        return skip_the_token(tokens, start_idx)

    def _is_digit_sequence(self, tokens, start_idx):
        """Delegate to time_utils"""
        return is_digit_sequence(tokens, start_idx)

    def _extract_day_value_from_tokens(self, tokens, start_idx):  # noqa: C901
        """Delegate to time_utils"""
        return extract_day_value_from_tokens(tokens, start_idx)

    def _extract_day_value(self, token):
        """Delegate to time_utils"""
        return extract_day_value(token)

    def _merge_utc_with_weekday(self, utc_token, weekday_token, base_time):
        """Delegate to merger"""
        return self.utc_merger.merge_utc_with_weekday(utc_token, weekday_token, base_time)

    def _try_merge_delta_from_time(self, i, tokens, base_time):  # noqa: C901
        """Delegate to merger"""
        return self.delta_merger.try_merge_delta_from_time(i, tokens, base_time)

    def _try_merge_weekday_from_now(self, i, tokens, base_time):  # noqa: C901
        """Delegate to merger"""
        return self.delta_merger.try_merge_weekday_from_now(i, tokens, base_time)

    def _parse_number_unit_delta(self, i, tokens):  # noqa: C901
        """Delegate to merger"""
        return self.delta_merger.parse_number_unit_delta(i, tokens)

    def _inherit_period_marker(self, start_token, end_token):
        """Delegate to RangeUtils"""
        return self.range_merger.range_utils.inherit_period_marker(self, start_token, end_token)

    def _check_short_time_range_pattern(self, i, tokens):  # noqa: C901
        """Delegate to merger"""
        return self.time_expression_merger.check_short_time_range_pattern(i, tokens)

    def _try_merge_short_time_range(self, i, tokens, base_time):  # noqa: C901
        """Delegate to merger"""
        return self.time_expression_merger.try_merge_short_time_range(i, tokens, base_time)

    def _check_weekday_prefix(self, i, tokens):
        """Delegate to RangeUtils"""
        return self.range_merger.range_utils.check_weekday_prefix(self, i, tokens)

    def _merge_ordinal_weekday_month(self, i, tokens, base_time):  # noqa: C901
        """Delegate to merger"""
        return self.modifier_merger.merge_ordinal_weekday_month(i, tokens, base_time)

    def _merge_at_number(self, i, tokens, base_time):  # noqa: C901
        """Delegate to merger"""
        return self.time_expression_merger.merge_at_number(i, tokens, base_time)

    def _try_merge_period_of_year(self, i, tokens, base_time):  # noqa: C901
        """Delegate to merger"""
        return self.period_merger.try_merge_period_of_year(i, tokens, base_time)

    def _try_merge_time_for_relative(self, i, tokens, base_time):  # noqa: C901
        """Delegate to merger"""
        return self.delta_merger.try_merge_time_for_relative(i, tokens, base_time)

    def _merge_by_future_time(self, i, tokens, base_time):  # noqa: C901
        """Delegate to merger"""
        return self.delta_merger.merge_by_future_time(i, tokens, base_time)

    def _parse_duration(self, start_idx, tokens):  # noqa: C901
        """Delegate to merger"""
        return self.duration_merger.parse_duration(start_idx, tokens)

    def _parse_time_expression(self, time_tokens, base_time):  # noqa: C901
        """Delegate to merger"""
        return self.duration_merger.parse_time_expression(time_tokens, base_time)

    def _merge_for_duration_from_time(self, i, tokens, base_time):  # noqa: C901
        """Delegate to merger"""
        return self.duration_merger.merge_for_duration_from_time(i, tokens, base_time)

    def _merge_from_time_for_duration(self, i, tokens, base_time):  # noqa: C901
        """Delegate to merger"""
        return self.duration_merger.merge_from_time_for_duration(i, tokens, base_time)

    def _merge_time_for_duration(self, i, tokens, base_time):  # noqa: C901
        """Delegate to merger"""
        return self.duration_merger.merge_time_for_duration(i, tokens, base_time)

    def _merge_duration_from_time(self, i, tokens, base_time):  # noqa: C901
        """Delegate to merger"""
        return self.duration_merger.merge_duration_from_time(i, tokens, base_time)

    def _merge_period_with_date(self, period_token, date_token, base_time):  # noqa: C901
        """Delegate to merger"""
        return self.period_merger.merge_period_with_date(period_token, date_token, base_time)

    def _apply_period_to_date(self, period, target_date):
        """Delegate to merger"""
        return self.time_expression_merger.apply_period_to_date(period, target_date)

    def _apply_period_modifier(self, period, modifier):  # noqa: C901
        """Delegate to merger"""
        return self.period_merger.apply_period_modifier(period, modifier)
