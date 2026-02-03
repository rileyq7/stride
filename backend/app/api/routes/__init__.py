from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.api.routes import quiz, shoes, admin
from app.core.database import get_db
from app.models import Category, Brand

api_router = APIRouter()

api_router.include_router(quiz.router, prefix="/quiz", tags=["quiz"])
api_router.include_router(shoes.router, prefix="/shoes", tags=["shoes"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])


# Top-level category endpoint for easier access
@api_router.get("/categories", tags=["categories"])
async def list_categories(db: AsyncSession = Depends(get_db)):
    """List all active categories."""
    result = await db.execute(
        select(Category).where(Category.is_active == True).order_by(Category.display_order)
    )
    categories = result.scalars().all()
    return [
        {"id": str(c.id), "name": c.name, "slug": c.slug, "is_active": c.is_active}
        for c in categories
    ]


@api_router.get("/brands", tags=["brands"])
async def list_brands(db: AsyncSession = Depends(get_db)):
    """List all brands."""
    result = await db.execute(select(Brand).order_by(Brand.name))
    brands = result.scalars().all()
    return [
        {"id": str(b.id), "name": b.name, "slug": b.slug, "logo_url": b.logo_url}
        for b in brands
    ]
