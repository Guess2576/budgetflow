from fastapi import APIRouter, HTTPException, status
from sqlalchemy import or_, select

from app.api.deps import CurrentUser, DbSession
from app.api.ownership import get_accessible_category
from app.models.category import Category
from app.schemas.category import CategoryCreate, CategoryRead, CategoryUpdate

router = APIRouter(prefix="/categories", tags=["categories"])


async def _get_owned_category(category_id: int, user: CurrentUser, db: DbSession) -> Category:
    category = await db.get(Category, category_id)
    if category is None or category.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    return category


async def _validate_parent(
    parent_category_id: int | None, user: CurrentUser, db: DbSession
) -> None:
    if parent_category_id is None:
        return

    parent = await db.get(Category, parent_category_id)
    if parent is None or (parent.user_id is not None and parent.user_id != user.id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid parent category"
        )


@router.get("", response_model=list[CategoryRead])
async def list_categories(user: CurrentUser, db: DbSession) -> list[Category]:
    result = await db.scalars(
        select(Category).where(or_(Category.user_id == user.id, Category.user_id.is_(None)))
    )
    return list(result.all())


@router.post("", response_model=CategoryRead, status_code=status.HTTP_201_CREATED)
async def create_category(payload: CategoryCreate, user: CurrentUser, db: DbSession) -> Category:
    await _validate_parent(payload.parent_category_id, user, db)

    category = Category(user_id=user.id, **payload.model_dump())
    db.add(category)
    await db.commit()
    await db.refresh(category)
    return category


@router.get("/{category_id}", response_model=CategoryRead)
async def get_category(category_id: int, user: CurrentUser, db: DbSession) -> Category:
    return await get_accessible_category(category_id, user, db)


@router.patch("/{category_id}", response_model=CategoryRead)
async def update_category(
    category_id: int, payload: CategoryUpdate, user: CurrentUser, db: DbSession
) -> Category:
    category = await _get_owned_category(category_id, user, db)

    data = payload.model_dump(exclude_unset=True)
    if "parent_category_id" in data:
        if data["parent_category_id"] == category.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A category cannot be its own parent",
            )
        await _validate_parent(data["parent_category_id"], user, db)

    for field, value in data.items():
        setattr(category, field, value)

    await db.commit()
    await db.refresh(category)
    return category


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(category_id: int, user: CurrentUser, db: DbSession) -> None:
    category = await _get_owned_category(category_id, user, db)
    await db.delete(category)
    await db.commit()
