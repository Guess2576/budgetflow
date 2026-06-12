import datetime as dt

from dateutil.relativedelta import relativedelta
from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DbSession
from app.api.ownership import get_accessible_category
from app.models.account import Account
from app.models.budget import Budget, BudgetPeriod
from app.models.transaction import Transaction, TransactionType
from app.schemas.budget import BudgetCreate, BudgetRead, BudgetUpdate

router = APIRouter(prefix="/budgets", tags=["budgets"])

_PERIOD_LENGTHS = {
    BudgetPeriod.WEEKLY: relativedelta(days=7),
    BudgetPeriod.MONTHLY: relativedelta(months=1),
    BudgetPeriod.YEARLY: relativedelta(years=1),
}


def current_period_bounds(
    start_date: dt.date, period: BudgetPeriod, today: dt.date | None = None
) -> tuple[dt.date, dt.date]:
    """Return the (inclusive) start/end dates of the budget period containing `today`."""
    today = today or dt.date.today()
    step = _PERIOD_LENGTHS[period]

    if today < start_date:
        return start_date, start_date + step - dt.timedelta(days=1)

    period_start = start_date
    while period_start + step <= today:
        period_start += step

    return period_start, period_start + step - dt.timedelta(days=1)


async def _get_owned_budget(budget_id: int, user: CurrentUser, db: DbSession) -> Budget:
    budget = await db.get(Budget, budget_id)
    if budget is None or budget.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Budget not found")
    return budget


async def _to_budget_read(budget: Budget, user: CurrentUser, db: DbSession) -> BudgetRead:
    period_start, period_end = current_period_bounds(budget.start_date, budget.period)

    spent = (
        await db.scalar(
            select(func.sum(Transaction.amount))
            .join(Account, Transaction.account_id == Account.id)
            .where(
                Account.user_id == user.id,
                Transaction.category_id == budget.category_id,
                Transaction.type == TransactionType.EXPENSE,
                Transaction.date >= period_start,
                Transaction.date <= period_end,
            )
        )
        or 0
    )

    spent = float(spent)
    amount_limit = float(budget.amount_limit)

    return BudgetRead(
        id=budget.id,
        category_id=budget.category_id,
        amount_limit=amount_limit,
        period=budget.period,
        start_date=budget.start_date,
        current_period_start=period_start,
        current_period_end=period_end,
        spent=spent,
        remaining=amount_limit - spent,
    )


@router.get("", response_model=list[BudgetRead])
async def list_budgets(user: CurrentUser, db: DbSession) -> list[BudgetRead]:
    result = await db.scalars(select(Budget).where(Budget.user_id == user.id))
    return [await _to_budget_read(budget, user, db) for budget in result.all()]


@router.post("", response_model=BudgetRead, status_code=status.HTTP_201_CREATED)
async def create_budget(payload: BudgetCreate, user: CurrentUser, db: DbSession) -> BudgetRead:
    await get_accessible_category(payload.category_id, user, db)

    budget = Budget(user_id=user.id, **payload.model_dump())
    db.add(budget)
    await db.commit()
    await db.refresh(budget)
    return await _to_budget_read(budget, user, db)


@router.get("/{budget_id}", response_model=BudgetRead)
async def get_budget(budget_id: int, user: CurrentUser, db: DbSession) -> BudgetRead:
    budget = await _get_owned_budget(budget_id, user, db)
    return await _to_budget_read(budget, user, db)


@router.patch("/{budget_id}", response_model=BudgetRead)
async def update_budget(
    budget_id: int, payload: BudgetUpdate, user: CurrentUser, db: DbSession
) -> BudgetRead:
    budget = await _get_owned_budget(budget_id, user, db)

    data = payload.model_dump(exclude_unset=True)
    if "category_id" in data:
        await get_accessible_category(data["category_id"], user, db)

    for field, value in data.items():
        setattr(budget, field, value)

    await db.commit()
    await db.refresh(budget)
    return await _to_budget_read(budget, user, db)


@router.delete("/{budget_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_budget(budget_id: int, user: CurrentUser, db: DbSession) -> None:
    budget = await _get_owned_budget(budget_id, user, db)
    await db.delete(budget)
    await db.commit()
