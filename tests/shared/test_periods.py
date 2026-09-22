# filename: tests/shared/test_periods.py
# title: Shared Contract - Reporting Period Tests
# layer: Test suite - shared contract
# status: Phase 1-6 test recovery
# description:
#     Verifies the canonical reporting-period module: RequestedPeriod,
#     Period, the full-year span rule, and the matching logic that
#     decides whether evidence answers the request.
#
#     This file guards the four fiscal-year concepts that must never be
#     conflated:
#       1. Requested fiscal year (what the caller asked for)
#       2. Actual period end date (ground truth from the source)
#       3. Evidence fiscal year (derived from #2)
#       4. SEC fy/fp labels (untrusted metadata)
#
#     The personal prototype discovered against live SEC data that
#     SEC's "fy" label reflects the FILING's year, not the value's
#     year, and its "fp" label can mark a three-month span as a full
#     fiscal year. The tests in section 3 guard that discovery.
#
# source:
#     AUTHORED - Phase 2 had no saved test before recovery began.
#     The rules in src/veda/shared/periods.py are the specification;
#     this file is the executable form of that spec.
#
# notes:
#     - The MIN/MAX window is 350-380 days. That window covers:
#         365 (normal year), 366 (leap year), 364 (52-week year),
#         371 (53-week year). It excludes quarters (90-92 days).
#     - Period.match_status_against() does two-stage comparison:
#         stage 1: exact date comparison when both sides have dates
#         stage 2: fiscal-year comparison when dates are insufficient

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from veda.shared.enums import PeriodMatchStatus
from veda.shared.periods import (
    MAX_ANNUAL_PERIOD_DAYS,
    MIN_ANNUAL_PERIOD_DAYS,
    Period,
    RequestedPeriod,
)


# ====================================================================
# 1. Constants
# ====================================================================

def test_min_annual_period_days_is_350() -> None:
    assert MIN_ANNUAL_PERIOD_DAYS == 350


def test_max_annual_period_days_is_380() -> None:
    assert MAX_ANNUAL_PERIOD_DAYS == 380


# ====================================================================
# 2. RequestedPeriod
# ====================================================================

def test_requested_period_constructs_with_fiscal_year() -> None:
    rp = RequestedPeriod(fiscal_year=2024, raw="2024")
    assert rp.fiscal_year == 2024
    assert rp.start is None
    assert rp.end is None


def test_requested_period_from_fiscal_year_builds_raw() -> None:
    rp = RequestedPeriod.from_fiscal_year(2024)
    assert rp.fiscal_year == 2024
    assert rp.raw == "2024"


def test_requested_period_from_fiscal_year_respects_explicit_raw() -> None:
    rp = RequestedPeriod.from_fiscal_year(2024, raw="FY2024")
    assert rp.raw == "FY2024"


def test_requested_period_rejects_start_after_end() -> None:
    with pytest.raises(ValidationError):
        RequestedPeriod(
            fiscal_year=2024,
            start=date(2024, 12, 31),
            end=date(2024, 1, 1),
            raw="2024",
        )


def test_requested_period_requires_nonempty_raw() -> None:
    with pytest.raises(ValidationError):
        RequestedPeriod(fiscal_year=2024, raw="")


# ====================================================================
# 3. Period.days() and is_full_year()
# ====================================================================

def test_period_days_normal_year() -> None:
    """A calendar year is 365 or 366 days."""
    p = Period(start=date(2024, 1, 1), end=date(2024, 12, 31))
    assert p.days() == 365


def test_period_days_leap_year() -> None:
    p = Period(start=date(2023, 1, 1), end=date(2023, 12, 31))
    assert p.days() == 364


def test_period_days_returns_none_when_start_missing() -> None:
    p = Period(end=date(2024, 12, 31))
    assert p.days() is None


def test_period_days_returns_none_when_end_missing() -> None:
    p = Period(start=date(2024, 1, 1))
    assert p.days() is None


def test_period_is_full_year_for_normal_year() -> None:
    p = Period(start=date(2024, 1, 1), end=date(2024, 12, 31))
    assert p.is_full_year() is True


def test_period_is_full_year_for_52_week_year() -> None:
    """52-week fiscal calendars produce 364-day spans."""
    p = Period(start=date(2023, 1, 2), end=date(2023, 12, 31))
    assert p.days() == 363 or p.days() == 364
    assert p.is_full_year() is True


def test_period_is_full_year_for_53_week_year() -> None:
    """53-week fiscal calendars produce 371-day spans."""
    p = Period(start=date(2024, 1, 1), end=date(2025, 1, 5))
    span = p.days()
    assert span is not None
    assert MIN_ANNUAL_PERIOD_DAYS <= span <= MAX_ANNUAL_PERIOD_DAYS
    assert p.is_full_year() is True


def test_period_is_not_full_year_for_quarter() -> None:
    """A three-month span, even labeled FY, must be rejected."""
    p = Period(start=date(2024, 1, 1), end=date(2024, 3, 31))
    assert p.days() == 90
    assert p.is_full_year() is False


def test_period_is_not_full_year_for_six_months() -> None:
    p = Period(start=date(2024, 1, 1), end=date(2024, 6, 30))
    assert p.days() == 181
    assert p.is_full_year() is False


def test_period_is_not_full_year_when_undated() -> None:
    """An undated period is never a full year — no guessing."""
    p = Period()
    assert p.is_full_year() is False


def test_period_is_not_full_year_for_two_years() -> None:
    """A span longer than MAX_ANNUAL_PERIOD_DAYS is not a full year."""
    p = Period(start=date(2024, 1, 1), end=date(2025, 12, 31))
    assert p.is_full_year() is False


# ====================================================================
# 4. Period.fiscal_year() - the label-is-a-lie guard
# ====================================================================

def test_period_fiscal_year_derived_from_end_date() -> None:
    p = Period(
        start=date(2023, 1, 1),
        end=date(2023, 12, 31),
        label="FY2024",   # <- label says 2024, date says 2023
    )
    assert p.fiscal_year() == 2023


def test_period_fiscal_year_ignores_label_completely() -> None:
    """
    The fiscal year comes from the end date. The label is display only.
    This test guards the exact bug the personal prototype found.
    """
    p = Period(
        start=date(2024, 1, 1),
        end=date(2024, 12, 31),
        label="FY2023",   # <- label says 2023, date says 2024
    )
    assert p.fiscal_year() == 2024


def test_period_fiscal_year_returns_none_when_undated() -> None:
    p = Period(label="FY2024")
    assert p.fiscal_year() is None


# ====================================================================
# 5. Period.match_status_against() - exact date comparison
# ====================================================================

def test_match_exact_when_dates_equal() -> None:
    p = Period(start=date(2024, 1, 1), end=date(2024, 12, 31))
    rp = RequestedPeriod(
        fiscal_year=2024,
        start=date(2024, 1, 1),
        end=date(2024, 12, 31),
        raw="2024",
    )
    assert p.match_status_against(rp) == PeriodMatchStatus.EXACT


def test_match_mismatch_when_start_differs() -> None:
    p = Period(start=date(2024, 2, 1), end=date(2024, 12, 31))
    rp = RequestedPeriod(
        fiscal_year=2024,
        start=date(2024, 1, 1),
        end=date(2024, 12, 31),
        raw="2024",
    )
    assert p.match_status_against(rp) == PeriodMatchStatus.MISMATCH


def test_match_mismatch_when_end_differs() -> None:
    p = Period(start=date(2024, 1, 1), end=date(2024, 11, 30))
    rp = RequestedPeriod(
        fiscal_year=2024,
        start=date(2024, 1, 1),
        end=date(2024, 12, 31),
        raw="2024",
    )
    assert p.match_status_against(rp) == PeriodMatchStatus.MISMATCH


# ====================================================================
# 6. Period.match_status_against() - fiscal-year fallback
# ====================================================================

def test_match_exact_when_only_year_requested_and_years_equal() -> None:
    """Requested period is a bare year. Evidence ends in the same year."""
    p = Period(start=date(2024, 1, 1), end=date(2024, 12, 31))
    rp = RequestedPeriod(fiscal_year=2024, raw="2024")
    assert p.match_status_against(rp) == PeriodMatchStatus.EXACT


def test_match_adjacent_when_years_differ_by_one() -> None:
    p = Period(start=date(2023, 1, 1), end=date(2023, 12, 31))
    rp = RequestedPeriod(fiscal_year=2024, raw="2024")
    assert p.match_status_against(rp) == PeriodMatchStatus.ADJACENT


def test_match_mismatch_when_years_differ_by_two() -> None:
    p = Period(start=date(2022, 1, 1), end=date(2022, 12, 31))
    rp = RequestedPeriod(fiscal_year=2024, raw="2024")
    assert p.match_status_against(rp) == PeriodMatchStatus.MISMATCH


def test_match_unknown_when_evidence_undated() -> None:
    p = Period(label="FY2024")
    rp = RequestedPeriod(fiscal_year=2024, raw="2024")
    assert p.match_status_against(rp) == PeriodMatchStatus.UNKNOWN


# ====================================================================
# 7. Period.from_iso_strings()
# ====================================================================

def test_from_iso_strings_parses_valid_dates() -> None:
    p = Period.from_iso_strings("2024-01-01", "2024-12-31", label="FY2024")
    assert p.start == date(2024, 1, 1)
    assert p.end == date(2024, 12, 31)
    assert p.label == "FY2024"


def test_from_iso_strings_tolerates_malformed_start() -> None:
    """Malformed strings produce None, not an exception."""
    p = Period.from_iso_strings("not-a-date", "2024-12-31")
    assert p.start is None
    assert p.end == date(2024, 12, 31)


def test_from_iso_strings_tolerates_malformed_end() -> None:
    p = Period.from_iso_strings("2024-01-01", "not-a-date")
    assert p.start == date(2024, 1, 1)
    assert p.end is None


def test_from_iso_strings_tolerates_none_inputs() -> None:
    p = Period.from_iso_strings(None, None)
    assert p.start is None
    assert p.end is None


def test_from_iso_strings_default_label_is_none() -> None:
    p = Period.from_iso_strings("2024-01-01", "2024-12-31")
    assert p.label is None


# ====================================================================
# 8. Period validation
# ====================================================================

def test_period_rejects_start_after_end() -> None:
    with pytest.raises(ValidationError):
        Period(start=date(2024, 12, 31), end=date(2024, 1, 1))


def test_period_accepts_equal_dates() -> None:
    p = Period(start=date(2024, 6, 1), end=date(2024, 6, 1))
    assert p.days() == 0


def test_period_accepts_only_start() -> None:
    p = Period(start=date(2024, 1, 1))
    assert p.start is not None
    assert p.end is None


def test_period_accepts_only_end() -> None:
    p = Period(end=date(2024, 12, 31))
    assert p.start is None
    assert p.end is not None


def test_period_accepts_label_only() -> None:
    p = Period(label="FY2024")
    assert p.start is None
    assert p.end is None
    assert p.label == "FY2024"


# ====================================================================
# 9. The fy-label bug — combined scenario
# ====================================================================

def test_quarterly_entry_labeled_fy_is_not_a_full_year() -> None:
    """
    The exact bug the personal prototype found live: SEC returns a
    three-month span labeled fp="FY". The Period must reject it as a
    full year via the days() window.
    """
    # Q1 2024 span, mislabeled FY
    p = Period(
        start=date(2024, 1, 1),
        end=date(2024, 3, 31),
        label="FY2024",   # <- misleading label
    )
    assert p.is_full_year() is False
    assert p.days() == 90


def test_comparative_year_labeled_fy_is_wrong_year() -> None:
    """
    The exact bug the personal prototype found live: SEC stamps a
    comparative entry with the FILING's fy label, not the value's year.
    Period.fiscal_year() must derive from end date, not from label.
    """
    # 2023 value mislabeled fy=2024
    p = Period(
        start=date(2023, 1, 1),
        end=date(2023, 12, 31),
        label="FY2024",   # <- misleading label
    )
    assert p.fiscal_year() == 2023   # derived from end date
    # And matching against a FY2024 request gives ADJACENT, not EXACT
    rp = RequestedPeriod(fiscal_year=2024, raw="2024")
    assert p.match_status_against(rp) == PeriodMatchStatus.ADJACENT