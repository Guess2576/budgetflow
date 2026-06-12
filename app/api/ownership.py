from fastapi import HTTPException, status

from app.api.deps import CurrentUser, DbSession
from app.models.account import Account
from app.models.category import Category


async def get_owned_account(account_id: int, user: CurrentUser, db: DbSession) -> Account:
    account = await db.get(Account, account_id)
    if account is None or account.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    return account


async def get_accessible_category(category_id: int, user: CurrentUser, db: DbSession) -> Category:
    category = await db.get(Category, category_id)
    if category is None or (category.user_id is not None and category.user_id != user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    return category
