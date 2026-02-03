import uuid
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.core.database import get_db
from app.models import Shoe, Category, Brand
from app.schemas.shoe import ShoeResponse, ShoeDetailResponse, BrandInfo, FitProfileResponse, AffiliateLink

router = APIRouter()


@router.get("/categories")
async def list_categories(
    db: AsyncSession = Depends(get_db),
):
    """List all active categories."""
    result = await db.execute(
        select(Category).where(Category.is_active == True).order_by(Category.display_order)
    )
    categories = result.scalars().all()
    return [
        {
            "id": c.id,
            "name": c.name,
            "slug": c.slug,
            "is_active": c.is_active,
        }
        for c in categories
    ]


@router.get("/brands")
async def list_brands(
    db: AsyncSession = Depends(get_db),
):
    """List all brands."""
    result = await db.execute(select(Brand).order_by(Brand.name))
    brands = result.scalars().all()
    return [
        {
            "id": b.id,
            "name": b.name,
            "slug": b.slug,
            "logo_url": b.logo_url,
        }
        for b in brands
    ]


@router.get("", response_model=list[ShoeResponse])
async def list_shoes(
    category: str | None = None,
    brand: str | None = None,
    limit: int = Query(default=50, le=100),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """List all active shoes with optional filters."""
    query = select(Shoe).where(Shoe.is_active == True)

    if category:
        query = query.join(Category).where(Category.slug == category)

    if brand:
        query = query.join(Brand).where(Brand.slug == brand)

    query = query.options(
        selectinload(Shoe.brand),
        selectinload(Shoe.category),
    ).offset(offset).limit(limit)

    result = await db.execute(query)
    shoes = result.scalars().all()

    return [
        ShoeResponse(
            id=shoe.id,
            brand=BrandInfo(
                id=shoe.brand.id,
                name=shoe.brand.name,
                logo_url=shoe.brand.logo_url,
            ),
            category=shoe.category.slug,
            name=shoe.name,
            slug=shoe.slug,
            model_year=shoe.model_year,
            msrp_usd=shoe.msrp_usd,
            current_price_min=shoe.current_price_min,
            current_price_max=shoe.current_price_max,
            primary_image_url=shoe.primary_image_url,
            is_active=shoe.is_active,
        )
        for shoe in shoes
    ]


@router.get("/{shoe_id}", response_model=ShoeDetailResponse)
async def get_shoe(
    shoe_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get detailed information about a specific shoe."""
    result = await db.execute(
        select(Shoe)
        .where(Shoe.id == shoe_id)
        .options(
            selectinload(Shoe.brand),
            selectinload(Shoe.category),
            selectinload(Shoe.fit_profile),
            selectinload(Shoe.affiliate_links),
            selectinload(Shoe.running_attributes),
            selectinload(Shoe.basketball_attributes),
        )
    )
    shoe = result.scalar_one_or_none()

    if not shoe:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shoe not found",
        )

    # Build specs based on category
    specs = None
    if shoe.category.slug == "running" and shoe.running_attributes:
        attrs = shoe.running_attributes
        specs = {
            "terrain": attrs.terrain,
            "subcategory": attrs.subcategory,
            "weight_oz": float(attrs.weight_oz) if attrs.weight_oz else None,
            "stack_height_heel_mm": float(attrs.stack_height_heel_mm) if attrs.stack_height_heel_mm else None,
            "stack_height_forefoot_mm": float(attrs.stack_height_forefoot_mm) if attrs.stack_height_forefoot_mm else None,
            "drop_mm": float(attrs.drop_mm) if attrs.drop_mm else None,
            "has_carbon_plate": attrs.has_carbon_plate,
            "has_rocker": attrs.has_rocker,
            "cushion_type": attrs.cushion_type,
            "cushion_level": attrs.cushion_level,
            "best_for_distances": attrs.best_for_distances,
            "best_for_pace": attrs.best_for_pace,
        }
    elif shoe.category.slug == "basketball" and shoe.basketball_attributes:
        attrs = shoe.basketball_attributes
        specs = {
            "cut": attrs.cut,
            "court_type": attrs.court_type,
            "weight_oz": float(attrs.weight_oz) if attrs.weight_oz else None,
            "cushion_type": attrs.cushion_type,
            "cushion_level": attrs.cushion_level,
            "traction_pattern": attrs.traction_pattern,
            "ankle_support_level": attrs.ankle_support_level,
            "lockdown_level": attrs.lockdown_level,
            "best_for_position": attrs.best_for_position,
            "best_for_playstyle": attrs.best_for_playstyle,
            "outdoor_durability": attrs.outdoor_durability,
        }

    # Build fit profile
    fit_profile = None
    if shoe.fit_profile:
        fp = shoe.fit_profile
        fit_profile = FitProfileResponse(
            size_runs=fp.size_runs,
            size_offset=fp.size_offset,
            width_runs=fp.width_runs,
            toe_box_room=fp.toe_box_room,
            heel_fit=fp.heel_fit,
            arch_support=fp.arch_support,
            break_in_period=fp.break_in_period,
            durability_rating=fp.durability_rating,
            expected_miles_min=fp.expected_miles_min,
            expected_miles_max=fp.expected_miles_max,
            common_complaints=fp.common_complaints,
            works_well_for=fp.works_well_for,
            overall_sentiment=fp.overall_sentiment,
            review_count=fp.review_count,
        )

    # Build affiliate links
    affiliate_links = [
        AffiliateLink(
            retailer=link.retailer,
            url=link.url,
            price=link.current_price,
            in_stock=link.in_stock,
        )
        for link in shoe.affiliate_links
    ]

    return ShoeDetailResponse(
        id=shoe.id,
        brand=BrandInfo(
            id=shoe.brand.id,
            name=shoe.brand.name,
            logo_url=shoe.brand.logo_url,
        ),
        category=shoe.category.slug,
        name=shoe.name,
        full_name=f"{shoe.brand.name} {shoe.name}",
        slug=shoe.slug,
        model_year=shoe.model_year,
        version=shoe.version,
        specs=specs,
        fit_profile=fit_profile,
        pricing={
            "msrp_usd": float(shoe.msrp_usd) if shoe.msrp_usd else None,
            "current_min": float(shoe.current_price_min) if shoe.current_price_min else None,
            "current_max": float(shoe.current_price_max) if shoe.current_price_max else None,
        },
        affiliate_links=affiliate_links,
        images=shoe.image_urls or [],
    )


@router.get("/by-slug/{brand_slug}/{shoe_slug}", response_model=ShoeDetailResponse)
async def get_shoe_by_slug(
    brand_slug: str,
    shoe_slug: str,
    db: AsyncSession = Depends(get_db),
):
    """Get shoe by brand and shoe slug."""
    result = await db.execute(
        select(Shoe)
        .join(Brand)
        .where(Brand.slug == brand_slug, Shoe.slug == shoe_slug)
        .options(
            selectinload(Shoe.brand),
            selectinload(Shoe.category),
            selectinload(Shoe.fit_profile),
            selectinload(Shoe.affiliate_links),
            selectinload(Shoe.running_attributes),
            selectinload(Shoe.basketball_attributes),
        )
    )
    shoe = result.scalar_one_or_none()

    if not shoe:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shoe not found",
        )

    # Reuse the same logic from get_shoe
    return await get_shoe(shoe.id, db)
