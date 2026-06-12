import datetime as dt

from app.api.routes.budgets import current_period_bounds
from app.models.budget import BudgetPeriod


def test_current_period_bounds_monthly() -> None:
    start = dt.date(2026, 1, 15)
    today = dt.date(2026, 3, 20)

    period_start, period_end = current_period_bounds(start, BudgetPeriod.MONTHLY, today)

    assert period_start == dt.date(2026, 3, 15)
    assert period_end == dt.date(2026, 4, 14)


def test_current_period_bounds_weekly() -> None:
    start = dt.date(2026, 1, 1)
    today = dt.date(2026, 1, 10)

    period_start, period_end = current_period_bounds(start, BudgetPeriod.WEEKLY, today)

    assert period_start == dt.date(2026, 1, 8)
    assert period_end == dt.date(2026, 1, 14)


def test_current_period_bounds_before_start() -> None:
    start = dt.date(2026, 6, 1)
    today = dt.date(2026, 5, 1)

    period_start, period_end = current_period_bounds(start, BudgetPeriod.MONTHLY, today)

    assert period_start == start
    assert period_end == dt.date(2026, 6, 30)
