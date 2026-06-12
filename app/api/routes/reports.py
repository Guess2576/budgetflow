import datetime as dt

from dateutil.relativedelta import relativedelta
from fastapi import APIRouter
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DbSession
from app.models.account import Account
from app.models.category import Category
from app.models.transaction import Transaction, TransactionType
from app.schemas.report import (
    CategoryBreakdownItem,
    CategoryBreakdownReport,
    SummaryReport,
    TrendPoint,
    TrendsReport,
)

router = APIRouter(prefix="/reports", tags=["reports"])


def _current_month_bounds() -> tuple[dt.date, dt.date]:
    today = dt.date.today()
    start = today.replace(day=1)
    end = start + relativedelta(months=1) - dt.timedelta(days=1)
    return start, end


async def _sum_amount(
    db: DbSession, user: CurrentUser, type_: TransactionType, start: dt.date, end: dt.date
) -> float:
    total = await db.scalar(
        select(func.sum(Transaction.amount))
        .join(Account, Transaction.account_id == Account.id)
        .where(
            Account.user_id == user.id,
            Transaction.type == type_,
            Transaction.date >= start,
            Transaction.date <= end,
        )
    )
    return float(total or 0)


@router.get("/summary", response_model=SummaryReport)
async def summary(
    user: CurrentUser,
    db: DbSession,
    start_date: dt.date | None = None,
    end_date: dt.date | None = None,
) -> SummaryReport:
    if start_date is None or end_date is None:
        default_start, default_end = _current_month_bounds()
        start_date = start_date or default_start
        end_date = end_date or default_end

    income = await _sum_amount(db, user, TransactionType.INCOME, start_date, end_date)
    expenses = await _sum_amount(db, user, TransactionType.EXPENSE, start_date, end_date)

    return SummaryReport(
        start_date=start_date,
        end_date=end_date,
        income=income,
        expenses=expenses,
        net=income - expenses,
    )


@router.get("/by-category", response_model=CategoryBreakdownReport)
async def by_category(
    user: CurrentUser,
    db: DbSession,
    start_date: dt.date | None = None,
    end_date: dt.date | None = None,
    type: TransactionType = TransactionType.EXPENSE,
) -> CategoryBreakdownReport:
    if start_date is None or end_date is None:
        default_start, default_end = _current_month_bounds()
        start_date = start_date or default_start
        end_date = end_date or default_end

    rows = await db.execute(
        select(
            Category.id,
            Category.name,
            func.sum(Transaction.amount),
            func.count(Transaction.id),
        )
        .join(Transaction, Transaction.category_id == Category.id)
        .join(Account, Transaction.account_id == Account.id)
        .where(
            Account.user_id == user.id,
            Transaction.type == type,
            Transaction.date >= start_date,
            Transaction.date <= end_date,
        )
        .group_by(Category.id, Category.name)
        .order_by(func.sum(Transaction.amount).desc())
    )

    items = [
        CategoryBreakdownItem(
            category_id=category_id,
            category_name=category_name,
            total=float(total),
            transaction_count=count,
        )
        for category_id, category_name, total, count in rows
    ]

    return CategoryBreakdownReport(start_date=start_date, end_date=end_date, type=type, items=items)


@router.get("/trends", response_model=TrendsReport)
async def trends(user: CurrentUser, db: DbSession, months: int = 6) -> TrendsReport:
    months = min(max(months, 1), 24)
    today = dt.date.today()
    range_start = today.replace(day=1) - relativedelta(months=months - 1)

    rows = await db.execute(
        select(Transaction.date, Transaction.type, Transaction.amount)
        .join(Account, Transaction.account_id == Account.id)
        .where(Account.user_id == user.id, Transaction.date >= range_start)
    )

    buckets: dict[str, dict[str, float]] = {}
    for i in range(months):
        key = (range_start + relativedelta(months=i)).strftime("%Y-%m")
        buckets[key] = {"income": 0.0, "expenses": 0.0}

    for tx_date, tx_type, amount in rows:
        key = tx_date.strftime("%Y-%m")
        if key not in buckets:
            continue
        if tx_type == TransactionType.INCOME:
            buckets[key]["income"] += float(amount)
        else:
            buckets[key]["expenses"] += float(amount)

    points = [
        TrendPoint(
            month=month,
            income=v["income"],
            expenses=v["expenses"],
            net=v["income"] - v["expenses"],
        )
        for month, v in sorted(buckets.items())
    ]

    return TrendsReport(points=points)
