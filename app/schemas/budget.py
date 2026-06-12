import datetime as dt

from pydantic import BaseModel, ConfigDict, Field

from app.models.budget import BudgetPeriod


class BudgetCreate(BaseModel):
    category_id: int
    amount_limit: float = Field(gt=0)
    period: BudgetPeriod
    start_date: dt.date


class BudgetUpdate(BaseModel):
    category_id: int | None = None
    amount_limit: float | None = Field(default=None, gt=0)
    period: BudgetPeriod | None = None
    start_date: dt.date | None = None


class BudgetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    category_id: int
    amount_limit: float
    period: BudgetPeriod
    start_date: dt.date
    current_period_start: dt.date
    current_period_end: dt.date
    spent: float
    remaining: float
