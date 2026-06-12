import io
from datetime import date
from typing import Literal

import pandas as pd
from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DbSession
from app.api.ownership import get_accessible_category, get_owned_account
from app.models.account import Account
from app.models.category import Category
from app.models.transaction import Transaction, TransactionType
from app.schemas.transaction import (
    ImportRowError,
    TransactionCreate,
    TransactionImportResponse,
    TransactionListResponse,
    TransactionRead,
    TransactionUpdate,
)

router = APIRouter(prefix="/transactions", tags=["transactions"])

SortField = Literal["date", "amount", "created_at"]
SortOrder = Literal["asc", "desc"]


async def _get_owned_transaction(
    transaction_id: int, user: CurrentUser, db: DbSession
) -> Transaction:
    transaction = await db.get(Transaction, transaction_id)
    if transaction is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")

    account = await db.get(Account, transaction.account_id)
    if account is None or account.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")

    return transaction


async def _validate_transaction_refs(
    account_id: int, category_id: int | None, user: CurrentUser, db: DbSession
) -> None:
    await get_owned_account(account_id, user, db)
    if category_id is not None:
        await get_accessible_category(category_id, user, db)


@router.get("", response_model=TransactionListResponse)
async def list_transactions(
    user: CurrentUser,
    db: DbSession,
    account_id: int | None = None,
    category_id: int | None = None,
    type: TransactionType | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    sort_by: SortField = "date",
    order: SortOrder = "desc",
    page: int = 1,
    page_size: int = 20,
) -> TransactionListResponse:
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)

    query = select(Transaction).join(Account).where(Account.user_id == user.id)

    if account_id is not None:
        query = query.where(Transaction.account_id == account_id)
    if category_id is not None:
        query = query.where(Transaction.category_id == category_id)
    if type is not None:
        query = query.where(Transaction.type == type)
    if start_date is not None:
        query = query.where(Transaction.date >= start_date)
    if end_date is not None:
        query = query.where(Transaction.date <= end_date)

    total = await db.scalar(select(func.count()).select_from(query.subquery())) or 0

    sort_column = getattr(Transaction, sort_by)
    sort_column = sort_column.desc() if order == "desc" else sort_column.asc()

    query = query.order_by(sort_column).offset((page - 1) * page_size).limit(page_size)
    result = await db.scalars(query)

    return TransactionListResponse(
        items=list(result.all()), total=total, page=page, page_size=page_size
    )


@router.post("", response_model=TransactionRead, status_code=status.HTTP_201_CREATED)
async def create_transaction(
    payload: TransactionCreate, user: CurrentUser, db: DbSession
) -> Transaction:
    await _validate_transaction_refs(payload.account_id, payload.category_id, user, db)

    transaction = Transaction(**payload.model_dump())
    db.add(transaction)
    await db.commit()
    await db.refresh(transaction)
    return transaction


@router.get("/{transaction_id}", response_model=TransactionRead)
async def get_transaction(transaction_id: int, user: CurrentUser, db: DbSession) -> Transaction:
    return await _get_owned_transaction(transaction_id, user, db)


@router.patch("/{transaction_id}", response_model=TransactionRead)
async def update_transaction(
    transaction_id: int, payload: TransactionUpdate, user: CurrentUser, db: DbSession
) -> Transaction:
    transaction = await _get_owned_transaction(transaction_id, user, db)

    data = payload.model_dump(exclude_unset=True)
    await _validate_transaction_refs(
        data.get("account_id", transaction.account_id),
        data.get("category_id", transaction.category_id),
        user,
        db,
    )

    for field, value in data.items():
        setattr(transaction, field, value)

    await db.commit()
    await db.refresh(transaction)
    return transaction


@router.delete("/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_transaction(transaction_id: int, user: CurrentUser, db: DbSession) -> None:
    transaction = await _get_owned_transaction(transaction_id, user, db)
    await db.delete(transaction)
    await db.commit()


@router.post("/import", response_model=TransactionImportResponse)
async def import_transactions(
    user: CurrentUser,
    db: DbSession,
    account_id: int = Form(...),
    file: UploadFile = File(...),  # noqa: B008
) -> TransactionImportResponse:
    await get_owned_account(account_id, user, db)

    raw = await file.read()
    try:
        frame = pd.read_csv(io.BytesIO(raw))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Could not parse CSV: {exc}"
        ) from exc

    frame.columns = [str(col).strip().lower() for col in frame.columns]
    required = {"date", "amount"}
    missing = required - set(frame.columns)
    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"CSV is missing required column(s): {', '.join(sorted(missing))}",
        )

    category_cache: dict[str, Category] = {}
    imported = 0
    skipped: list[ImportRowError] = []

    for idx, row in frame.iterrows():
        row_number = int(idx) + 2  # account for header row + 0-index

        try:
            parsed_date = pd.to_datetime(row["date"]).date()
            amount = float(row["amount"])
        except (ValueError, TypeError) as exc:
            skipped.append(ImportRowError(row=row_number, error=str(exc)))
            continue

        if amount == 0:
            skipped.append(ImportRowError(row=row_number, error="Amount cannot be zero"))
            continue

        has_description = "description" in row and pd.notna(row["description"])
        description = str(row["description"]).strip() if has_description else None

        category_id = None
        if "category" in row and pd.notna(row["category"]):
            category_name = str(row["category"]).strip()
            if category_name:
                category = await _get_or_create_category(category_name, category_cache, user, db)
                category_id = category.id

        transaction = Transaction(
            account_id=account_id,
            category_id=category_id,
            amount=abs(amount),
            type=TransactionType.INCOME if amount > 0 else TransactionType.EXPENSE,
            description=description,
            date=parsed_date,
            is_recurring=False,
        )
        db.add(transaction)
        imported += 1

    await db.commit()
    return TransactionImportResponse(imported=imported, skipped=skipped)


async def _get_or_create_category(
    name: str, cache: dict[str, Category], user: CurrentUser, db: DbSession
) -> Category:
    key = name.lower()
    if key in cache:
        return cache[key]

    category = await db.scalar(
        select(Category).where(
            func.lower(Category.name) == key,
            (Category.user_id == user.id) | (Category.user_id.is_(None)),
        )
    )

    if category is None:
        category = Category(user_id=user.id, name=name)
        db.add(category)
        await db.flush()

    cache[key] = category
    return category
