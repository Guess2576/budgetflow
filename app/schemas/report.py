import datetime as dt

from pydantic import BaseModel

from app.models.transaction import TransactionType


class SummaryReport(BaseModel):
    start_date: dt.date
    end_date: dt.date
    income: float
    expenses: float
    net: float


class CategoryBreakdownItem(BaseModel):
    category_id: int
    category_name: str
    total: float
    transaction_count: int


class CategoryBreakdownReport(BaseModel):
    start_date: dt.date
    end_date: dt.date
    type: TransactionType
    items: list[CategoryBreakdownItem]


class TrendPoint(BaseModel):
    month: str
    income: float
    expenses: float
    net: float


class TrendsReport(BaseModel):
    points: list[TrendPoint]
