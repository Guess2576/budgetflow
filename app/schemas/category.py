from pydantic import BaseModel, ConfigDict


class CategoryCreate(BaseModel):
    name: str
    parent_category_id: int | None = None


class CategoryUpdate(BaseModel):
    name: str | None = None
    parent_category_id: int | None = None


class CategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    user_id: int | None
    parent_category_id: int | None
