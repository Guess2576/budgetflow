from pydantic import BaseModel, ConfigDict

from app.models.account import AccountType


class AccountCreate(BaseModel):
    name: str
    type: AccountType
    balance: float = 0
    currency: str = "USD"


class AccountUpdate(BaseModel):
    name: str | None = None
    type: AccountType | None = None
    balance: float | None = None
    currency: str | None = None


class AccountRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    type: AccountType
    balance: float
    currency: str
