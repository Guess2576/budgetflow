from fastapi import APIRouter, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.api.ownership import get_owned_account
from app.models.account import Account
from app.schemas.account import AccountCreate, AccountRead, AccountUpdate

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.get("", response_model=list[AccountRead])
async def list_accounts(user: CurrentUser, db: DbSession) -> list[Account]:
    result = await db.scalars(select(Account).where(Account.user_id == user.id))
    return list(result.all())


@router.post("", response_model=AccountRead, status_code=status.HTTP_201_CREATED)
async def create_account(payload: AccountCreate, user: CurrentUser, db: DbSession) -> Account:
    account = Account(user_id=user.id, **payload.model_dump())
    db.add(account)
    await db.commit()
    await db.refresh(account)
    return account


@router.get("/{account_id}", response_model=AccountRead)
async def get_account(account_id: int, user: CurrentUser, db: DbSession) -> Account:
    return await get_owned_account(account_id, user, db)


@router.patch("/{account_id}", response_model=AccountRead)
async def update_account(
    account_id: int, payload: AccountUpdate, user: CurrentUser, db: DbSession
) -> Account:
    account = await get_owned_account(account_id, user, db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(account, field, value)
    await db.commit()
    await db.refresh(account)
    return account


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(account_id: int, user: CurrentUser, db: DbSession) -> None:
    account = await get_owned_account(account_id, user, db)
    await db.delete(account)
    await db.commit()
