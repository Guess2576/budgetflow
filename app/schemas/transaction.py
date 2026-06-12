import datetime as dt

from pydantic import BaseModel, ConfigDict, Field

from app.models.transaction import RecurrenceRule, TransactionType


class TransactionCreate(BaseModel):
    account_id: int
    category_id: int | None = None
    amount: float = Field(gt=0)
    type: TransactionType
    description: str | None = None
    date: dt.date
    is_recurring: bool = False
    recurrence_rule: RecurrenceRule | None = None


class TransactionUpdate(BaseModel):
    account_id: int | None = None
    category_id: int | None = None
    amount: float | None = Field(default=None, gt=0)
    type: TransactionType | None = None
    description: str | None = None
    date: dt.date | None = None
    is_recurring: bool | None = None
    recurrence_rule: RecurrenceRule | None = None


class TransactionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    account_id: int
    category_id: int | None
    amount: float
    type: TransactionType
    description: str | None
    date: dt.date
    is_recurring: bool
    recurrence_rule: RecurrenceRule | None


class TransactionListResponse(BaseModel):
    items: list[TransactionRead]
    total: int
    page: int
    page_size: int


class ImportRowError(BaseModel):
    row: int
    error: str


class TransactionImportResponse(BaseModel):
    imported: int
    skipped: list[ImportRowError]
