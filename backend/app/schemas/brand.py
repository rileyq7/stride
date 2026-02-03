from uuid import UUID
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class BrandBase(BaseModel):
    name: str
    slug: str
    logo_url: Optional[str] = None
    website_url: Optional[str] = None
    affiliate_base_url: Optional[str] = None


class BrandCreate(BrandBase):
    pass


class BrandResponse(BrandBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
