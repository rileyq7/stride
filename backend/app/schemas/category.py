from uuid import UUID
from datetime import datetime
from pydantic import BaseModel


class CategoryBase(BaseModel):
    name: str
    slug: str
    display_order: int = 0
    is_active: bool = True


class CategoryCreate(CategoryBase):
    pass


class CategoryResponse(CategoryBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
