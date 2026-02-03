import uuid
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from app.core.database import get_db, async_session_maker
from app.core.security import verify_password, get_password_hash, create_access_token, get_current_admin
from app.models import (
    AdminUser, AdminAuditLog, Shoe, Brand, Category,
    Recommendation, QuizSession, ScrapeJob, TrainingExample,
    RunningShoeAttributes, BasketballShoeAttributes, ShoeFitProfile
)
from app.models.catalog import ShoeProduct, ShoeModel, ShoeOffer
from app.schemas.admin import (
    AdminLoginRequest, AdminLoginResponse, AdminUserResponse, AdminUserCreate,
    RecommendationReviewRequest, RecommendationListResponse, RecommendationListItem,
    ShoeCreateRequest, ShoeUpdateRequest, FitProfileUpdateRequest,
    ScrapeJobRequest, ScrapeJobResponse, AnalyticsOverview
)

logger = logging.getLogger(__name__)

router = APIRouter()


# Auth endpoints
@router.post("/login", response_model=AdminLoginResponse)
async def admin_login(
    request: AdminLoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """Admin login endpoint."""
    result = await db.execute(
        select(AdminUser).where(AdminUser.email == request.email)
    )
    user = result.scalar_one_or_none()

    if not user or not verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is disabled",
        )

    # Update last login
    user.last_login = datetime.utcnow()
    await db.commit()

    # Create token
    access_token = create_access_token(data={"sub": str(user.id)})

    return AdminLoginResponse(access_token=access_token)


@router.get("/me", response_model=AdminUserResponse)
async def get_current_user(
    current_user: AdminUser = Depends(get_current_admin),
):
    """Get current admin user info."""
    return current_user


@router.post("/users", response_model=AdminUserResponse)
async def create_admin_user(
    request: AdminUserCreate,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = Depends(get_current_admin),
):
    """Create a new admin user (admin only)."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can create users",
        )

    # Check if email exists
    result = await db.execute(
        select(AdminUser).where(AdminUser.email == request.email)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    user = AdminUser(
        email=request.email,
        password_hash=get_password_hash(request.password),
        name=request.name,
        role=request.role,
    )

    db.add(user)
    await db.commit()
    await db.refresh(user)

    return user


# Recommendation review endpoints
@router.get("/recommendations", response_model=RecommendationListResponse)
async def list_recommendations(
    status_filter: Optional[str] = Query(None, alias="status"),
    category: Optional[str] = None,
    limit: int = Query(default=50, le=100),
    page: int = 1,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = Depends(get_current_admin),
):
    """List recommendations for review."""
    query = select(Recommendation).options(
        selectinload(Recommendation.quiz_session).selectinload(QuizSession.category)
    )

    if status_filter:
        query = query.where(Recommendation.review_status == status_filter)

    if category:
        query = query.join(QuizSession).join(Category).where(Category.slug == category)

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # Get paginated results
    offset = (page - 1) * limit
    query = query.order_by(Recommendation.created_at.desc()).offset(offset).limit(limit)

    result = await db.execute(query)
    recommendations = result.scalars().all()

    items = []
    for rec in recommendations:
        session = rec.quiz_session

        # Enrich recommended_shoes with shoe names
        enriched_shoes = []
        if rec.recommended_shoes and isinstance(rec.recommended_shoes, list):
            for shoe_rec in rec.recommended_shoes:
                shoe_id = shoe_rec.get('shoe_id') if isinstance(shoe_rec, dict) else None
                if shoe_id:
                    # Look up shoe name
                    try:
                        shoe_result = await db.execute(
                            select(Shoe).options(selectinload(Shoe.brand)).where(Shoe.id == shoe_id)
                        )
                        shoe = shoe_result.scalar_one_or_none()
                        shoe_name = f"{shoe.brand.name} {shoe.name}" if shoe else shoe_rec.get('shoe_name', 'Unknown')
                    except Exception:
                        shoe_name = shoe_rec.get('shoe_name', 'Unknown')

                    enriched_shoes.append({
                        'shoe_id': shoe_id,
                        'shoe_name': shoe_name,
                        'rank': shoe_rec.get('rank', 0),
                        'score': shoe_rec.get('score', 0),
                    })

        items.append(RecommendationListItem(
            id=rec.id,
            created_at=rec.created_at,
            quiz_summary={
                "category": session.category.slug if session.category else None,
                **session.answers,
            },
            recommended_shoes=enriched_shoes,
            review_status=rec.review_status,
        ))

    return RecommendationListResponse(
        items=items,
        total=total,
        page=page,
    )


@router.post("/recommendations/{recommendation_id}/review")
async def review_recommendation(
    recommendation_id: uuid.UUID,
    request: RecommendationReviewRequest,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = Depends(get_current_admin),
):
    """Review a recommendation (approve, reject, or adjust)."""
    result = await db.execute(
        select(Recommendation)
        .where(Recommendation.id == recommendation_id)
        .options(selectinload(Recommendation.quiz_session))
    )
    recommendation = result.scalar_one_or_none()

    if not recommendation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recommendation not found",
        )

    recommendation.review_status = request.status
    recommendation.reviewed_by = current_user.id
    recommendation.reviewed_at = datetime.utcnow()
    recommendation.admin_notes = request.notes

    if request.adjusted_shoes:
        recommendation.adjusted_shoes = [
            {"shoe_id": str(s.shoe_id), "rank": s.rank}
            for s in request.adjusted_shoes
        ]

    # Create training example if approved or adjusted
    training_example_created = False
    if request.status in ["approved", "adjusted"]:
        session = recommendation.quiz_session
        ideal_shoes = request.adjusted_shoes if request.adjusted_shoes else recommendation.recommended_shoes

        training_example = TrainingExample(
            quiz_answers=session.answers,
            category_id=session.category_id,
            ideal_shoes=ideal_shoes if isinstance(ideal_shoes, list) else [ideal_shoes],
            source="admin_approval" if request.status == "approved" else "admin_correction",
            quality_score=1.0 if request.status == "approved" else 0.9,
        )
        db.add(training_example)
        training_example_created = True

    # Log action
    audit_log = AdminAuditLog(
        admin_user_id=current_user.id,
        action="review_recommendation",
        entity_type="recommendation",
        entity_id=recommendation_id,
        changes={"status": request.status, "notes": request.notes},
    )
    db.add(audit_log)

    await db.commit()

    return {"success": True, "training_example_created": training_example_created}


# Shoe management endpoints
@router.get("/shoes/{shoe_id}")
async def get_shoe_detail(
    shoe_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = Depends(get_current_admin),
):
    """Get detailed shoe info for editing (uses new ShoeProduct/ShoeModel catalog)."""
    result = await db.execute(
        select(ShoeProduct)
        .where(ShoeProduct.id == shoe_id)
        .options(
            selectinload(ShoeProduct.model).selectinload(ShoeModel.brand),
            selectinload(ShoeProduct.offers),
        )
    )
    product = result.scalar_one_or_none()

    if not product:
        raise HTTPException(status_code=404, detail="Shoe not found")

    model = product.model
    brand = model.brand if model else None

    # Calculate price range from offers
    prices = [float(o.price) for o in product.offers if o.price and o.in_stock]
    current_price_min = min(prices) if prices else None
    current_price_max = max(prices) if prices else None

    # Build response with all data
    data = {
        "id": product.id,
        "model_id": product.model_id,
        "brand_id": brand.id if brand else None,
        "brand": brand.name if brand else "Unknown",
        "brand_slug": brand.slug if brand else None,
        "category": model.terrain.value if model and model.terrain else "road",
        "name": product.name,
        "slug": product.slug,
        "version": product.version,
        "release_year": product.release_year,
        "colorway": product.colorway,
        "msrp_usd": float(product.msrp_usd) if product.msrp_usd else None,
        "current_price_min": current_price_min,
        "current_price_max": current_price_max,
        "width_options": product.width_options,
        "is_discontinued": product.is_discontinued,
        "is_active": product.is_active,
        "needs_review": product.needs_review,
        "primary_image_url": product.primary_image_url,
        "image_urls": product.image_urls,
        "last_scraped_at": product.updated_at,
        # Specs from product
        "weight_oz": float(product.weight_oz) if product.weight_oz else None,
        "drop_mm": float(product.drop_mm) if product.drop_mm else None,
        "stack_height_heel_mm": float(product.stack_height_heel_mm) if product.stack_height_heel_mm else None,
        "stack_height_forefoot_mm": float(product.stack_height_forefoot_mm) if product.stack_height_forefoot_mm else None,
        # Model-level specs
        "model_info": {
            "id": model.id if model else None,
            "name": model.name if model else None,
            "gender": model.gender.value if model and model.gender else None,
            "terrain": model.terrain.value if model and model.terrain else None,
            "support_type": model.support_type.value if model and model.support_type else None,
            "category": model.category.value if model and model.category else None,
            "description": model.description if model else None,
            "key_features": model.key_features if model else None,
            "has_carbon_plate": model.has_carbon_plate if model else False,
            "has_rocker": model.has_rocker if model else False,
            "cushion_type": model.cushion_type if model else None,
            "cushion_level": model.cushion_level if model else None,
        } if model else None,
        # Offers from retailers
        "offers": [
            {
                "id": o.id,
                "merchant": o.merchant,
                "url": o.url,
                "price": float(o.price) if o.price else None,
                "sale_price": float(o.sale_price) if o.sale_price else None,
                "in_stock": o.in_stock,
                "sizes_available": o.sizes_available,
                "last_seen_at": o.last_seen_at,
            }
            for o in product.offers
        ] if product.offers else [],
    }

    return data


@router.get("/shoes")
async def list_admin_shoes(
    category: Optional[str] = None,
    brand: Optional[str] = None,
    needs_review: Optional[bool] = None,
    incomplete: Optional[bool] = None,
    limit: int = Query(default=50, le=100),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = Depends(get_current_admin),
):
    """List shoes for admin management (uses new ShoeProduct/ShoeModel catalog)."""
    query = select(ShoeProduct).options(
        selectinload(ShoeProduct.model).selectinload(ShoeModel.brand),
        selectinload(ShoeProduct.offers),
    )

    if brand:
        query = query.join(ShoeModel).join(Brand).where(Brand.slug == brand)

    if needs_review is not None:
        query = query.where(ShoeProduct.needs_review == needs_review)

    # Filter by terrain (category equivalent in new model)
    if category:
        query = query.join(ShoeModel).where(ShoeModel.terrain == category)

    query = query.order_by(ShoeProduct.created_at.desc()).offset(offset).limit(limit)

    result = await db.execute(query)
    products = result.scalars().all()

    def check_completeness(product: ShoeProduct) -> bool:
        """Check if shoe product has all required specs filled in."""
        if not product.msrp_usd:
            return False
        if not product.weight_oz or not product.drop_mm:
            return False
        return True

    shoe_list = [
        {
            "id": product.id,
            "brand": product.model.brand.name if product.model and product.model.brand else "Unknown",
            "name": product.name,
            "category": product.model.terrain.value if product.model and product.model.terrain else "road",
            "is_active": product.is_active,
            "needs_review": product.needs_review,
            "last_scraped_at": product.updated_at,
            "is_complete": check_completeness(product),
            "weight_oz": float(product.weight_oz) if product.weight_oz else None,
            "drop_mm": float(product.drop_mm) if product.drop_mm else None,
            "msrp_usd": float(product.msrp_usd) if product.msrp_usd else None,
            "image_url": product.primary_image_url,
            "offer_count": len(product.offers) if product.offers else 0,
        }
        for product in products
    ]

    # Filter by incomplete if requested
    if incomplete is True:
        shoe_list = [s for s in shoe_list if not s["is_complete"]]

    return shoe_list


@router.post("/shoes")
async def create_shoe(
    request: ShoeCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = Depends(get_current_admin),
):
    """Create a new shoe."""
    # Verify brand and category exist
    brand_result = await db.execute(select(Brand).where(Brand.id == request.brand_id))
    if not brand_result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Brand not found")

    category_result = await db.execute(select(Category).where(Category.id == request.category_id))
    category = category_result.scalar_one_or_none()
    if not category:
        raise HTTPException(status_code=400, detail="Category not found")

    shoe = Shoe(
        brand_id=request.brand_id,
        category_id=request.category_id,
        name=request.name,
        slug=request.slug,
        model_year=request.model_year,
        version=request.version,
        msrp_usd=request.msrp_usd,
        current_price_min=request.current_price_min,
        current_price_max=request.current_price_max,
        available_regions=request.available_regions,
        width_options=request.width_options,
        is_discontinued=request.is_discontinued,
        primary_image_url=request.primary_image_url,
        image_urls=request.image_urls,
    )

    db.add(shoe)
    await db.flush()

    # Add category-specific attributes
    if category.slug == "running" and request.running_attributes:
        attrs = RunningShoeAttributes(shoe_id=shoe.id, **request.running_attributes)
        db.add(attrs)
    elif category.slug == "basketball" and request.basketball_attributes:
        attrs = BasketballShoeAttributes(shoe_id=shoe.id, **request.basketball_attributes)
        db.add(attrs)

    # Log action
    audit_log = AdminAuditLog(
        admin_user_id=current_user.id,
        action="create_shoe",
        entity_type="shoe",
        entity_id=shoe.id,
        changes={"name": shoe.name},
    )
    db.add(audit_log)

    await db.commit()
    await db.refresh(shoe)

    return {"id": shoe.id, "name": shoe.name}


@router.put("/shoes/{shoe_id}")
async def update_shoe(
    shoe_id: uuid.UUID,
    request: ShoeUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = Depends(get_current_admin),
):
    """Update a shoe."""
    result = await db.execute(
        select(Shoe)
        .where(Shoe.id == shoe_id)
        .options(
            selectinload(Shoe.running_attributes),
            selectinload(Shoe.basketball_attributes),
            selectinload(Shoe.category),
        )
    )
    shoe = result.scalar_one_or_none()

    if not shoe:
        raise HTTPException(status_code=404, detail="Shoe not found")

    # Update basic fields
    update_data = request.model_dump(exclude_unset=True, exclude={"running_attributes", "basketball_attributes"})
    for field, value in update_data.items():
        setattr(shoe, field, value)

    # Update category-specific attributes
    if shoe.category.slug == "running" and request.running_attributes:
        if shoe.running_attributes:
            for field, value in request.running_attributes.items():
                setattr(shoe.running_attributes, field, value)
        else:
            attrs = RunningShoeAttributes(shoe_id=shoe.id, **request.running_attributes)
            db.add(attrs)

    elif shoe.category.slug == "basketball" and request.basketball_attributes:
        if shoe.basketball_attributes:
            for field, value in request.basketball_attributes.items():
                setattr(shoe.basketball_attributes, field, value)
        else:
            attrs = BasketballShoeAttributes(shoe_id=shoe.id, **request.basketball_attributes)
            db.add(attrs)

    # Log action
    audit_log = AdminAuditLog(
        admin_user_id=current_user.id,
        action="update_shoe",
        entity_type="shoe",
        entity_id=shoe_id,
        changes=update_data,
    )
    db.add(audit_log)

    await db.commit()

    return {"success": True}


@router.delete("/shoes/{shoe_id}")
async def delete_shoe(
    shoe_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = Depends(get_current_admin),
):
    """Delete (deactivate) a shoe."""
    result = await db.execute(select(Shoe).where(Shoe.id == shoe_id))
    shoe = result.scalar_one_or_none()

    if not shoe:
        raise HTTPException(status_code=404, detail="Shoe not found")

    shoe.is_active = False

    # Log action
    audit_log = AdminAuditLog(
        admin_user_id=current_user.id,
        action="delete_shoe",
        entity_type="shoe",
        entity_id=shoe_id,
    )
    db.add(audit_log)

    await db.commit()

    return {"success": True}


@router.post("/shoes/{shoe_id}/fit-profile")
async def update_fit_profile(
    shoe_id: uuid.UUID,
    request: FitProfileUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = Depends(get_current_admin),
):
    """Update shoe fit profile (manual override)."""
    result = await db.execute(
        select(Shoe).where(Shoe.id == shoe_id).options(selectinload(Shoe.fit_profile))
    )
    shoe = result.scalar_one_or_none()

    if not shoe:
        raise HTTPException(status_code=404, detail="Shoe not found")

    update_data = request.model_dump(exclude_unset=True)

    if shoe.fit_profile:
        for field, value in update_data.items():
            setattr(shoe.fit_profile, field, value)
        shoe.fit_profile.needs_review = False
    else:
        fit_profile = ShoeFitProfile(shoe_id=shoe_id, needs_review=False, **update_data)
        db.add(fit_profile)

    # Log action
    audit_log = AdminAuditLog(
        admin_user_id=current_user.id,
        action="update_fit_profile",
        entity_type="shoe",
        entity_id=shoe_id,
        changes=update_data,
    )
    db.add(audit_log)

    await db.commit()

    return {"success": True}


# Scraper management
async def run_brand_scrape(job_id: uuid.UUID, brand_id: uuid.UUID):
    """Background task to run brand scraping - discovers ALL shoes from brand websites dynamically."""
    from app.scrapers.brand_scrapers import get_brand_scraper

    async with async_session_maker() as session:
        try:
            # Update job status to running
            job_result = await session.execute(select(ScrapeJob).where(ScrapeJob.id == job_id))
            job = job_result.scalar_one_or_none()
            if job:
                job.status = 'running'
                job.started_at = datetime.utcnow()
                await session.commit()

            # Get brand info
            brand_result = await session.execute(select(Brand).where(Brand.id == brand_id))
            brand = brand_result.scalar_one_or_none()
            if not brand:
                raise Exception(f"Brand not found: {brand_id}")

            # Get running category
            cat_result = await session.execute(select(Category).where(Category.slug == 'running'))
            running_cat = cat_result.scalar_one_or_none()
            if not running_cat:
                raise Exception("Running category not found")

            # Get the appropriate scraper for this brand
            scraper = get_brand_scraper(brand.slug)
            if not scraper:
                raise Exception(f"No scraper available for brand: {brand.name}")

            logger.info(f"Starting dynamic discovery for {brand.name}...")

            # DYNAMIC DISCOVERY: Find ALL products from the brand's website
            try:
                product_urls = await scraper.discover_all_products()
                logger.info(f"Discovered {len(product_urls)} product URLs for {brand.name}")
            except NotImplementedError:
                raise Exception(f"Scraper for {brand.name} does not support dynamic discovery yet")

            if not product_urls:
                raise Exception(f"No products discovered for brand: {brand.name}")

            added = 0
            errors = 0

            # Scrape each discovered product
            for url in product_urls:
                try:
                    logger.info(f"Scraping: {url}")
                    specs = await scraper.scrape_product_specs_async(url)

                    if not specs or not specs.name:
                        logger.warning(f"Could not scrape specs from {url}")
                        errors += 1
                        continue

                    # Create slug
                    slug = specs.name.lower().replace(' ', '-').replace("'", "")

                    # Check if exists
                    existing = await session.execute(
                        select(Shoe).where(Shoe.brand_id == brand.id, Shoe.slug == slug)
                    )
                    if existing.scalar_one_or_none():
                        logger.info(f"{specs.name} already exists, skipping")
                        continue

                    # Create shoe
                    shoe = Shoe(
                        brand_id=brand.id,
                        category_id=running_cat.id,
                        name=specs.name,
                        slug=slug,
                        msrp_usd=specs.msrp,
                        primary_image_url=specs.primary_image_url,
                        image_urls=specs.image_urls,
                        is_active=True,
                        last_scraped_at=datetime.utcnow(),
                    )
                    session.add(shoe)
                    await session.flush()

                    # Create running attributes
                    attrs = RunningShoeAttributes(
                        shoe_id=shoe.id,
                        terrain=specs.terrain or 'road',
                        subcategory=specs.subcategory,
                        weight_oz=specs.weight_oz,
                        stack_height_heel_mm=specs.stack_height_heel_mm,
                        stack_height_forefoot_mm=specs.stack_height_forefoot_mm,
                        drop_mm=specs.drop_mm,
                        cushion_type=specs.cushion_type,
                        cushion_level=specs.cushion_level,
                        has_carbon_plate=specs.has_carbon_plate or False,
                        has_rocker=specs.has_rocker or False,
                    )
                    session.add(attrs)

                    # Create fit profile placeholder
                    fit = ShoeFitProfile(
                        shoe_id=shoe.id,
                        size_runs='true_to_size',
                        needs_review=True,
                    )
                    session.add(fit)

                    logger.info(f"Added {specs.name} - ${specs.msrp or '?'}")
                    added += 1

                except Exception as e:
                    logger.error(f"Error scraping {url}: {e}")
                    errors += 1
                    continue

            await session.commit()

            # Update job status to completed
            job_result = await session.execute(select(ScrapeJob).where(ScrapeJob.id == job_id))
            job = job_result.scalar_one_or_none()
            if job:
                job.status = 'completed'
                job.completed_at = datetime.utcnow()
                job.error_message = f"Discovered {len(product_urls)} URLs, added {added} shoes, {errors} errors"
                await session.commit()

            logger.info(f"Scrape job {job_id} completed. Discovered {len(product_urls)}, added {added} shoes.")

        except Exception as e:
            logger.error(f"Scrape job {job_id} failed: {e}")
            # Update job status to failed
            try:
                job_result = await session.execute(select(ScrapeJob).where(ScrapeJob.id == job_id))
                job = job_result.scalar_one_or_none()
                if job:
                    job.status = 'failed'
                    job.completed_at = datetime.utcnow()
                    job.error_message = str(e)
                    await session.commit()
            except Exception:
                pass


@router.post("/scrape/trigger", response_model=ScrapeJobResponse)
async def trigger_scrape(
    request: ScrapeJobRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = Depends(get_current_admin),
):
    """Trigger a scrape job."""
    job = ScrapeJob(
        job_type=request.job_type,
        target_id=request.target_id,
        source=",".join(request.sources) if request.sources else None,
        triggered_by=current_user.id,
    )

    db.add(job)
    await db.commit()
    await db.refresh(job)

    # Run scraping in background
    if request.job_type == 'brand' and request.target_id:
        target_uuid = request.target_id if isinstance(request.target_id, uuid.UUID) else uuid.UUID(request.target_id)
        background_tasks.add_task(run_brand_scrape, job.id, target_uuid)

    estimated_duration = {
        "single_shoe": 2,
        "brand": 15,
        "category": 30,
        "all_reviews": 60,
    }.get(request.job_type, 5)

    return ScrapeJobResponse(
        job_id=job.id,
        status="running" if request.job_type == 'brand' else job.status,
        estimated_duration_minutes=estimated_duration,
    )


@router.get("/scrape/jobs")
async def list_scrape_jobs(
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(default=50, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = Depends(get_current_admin),
):
    """List scrape jobs."""
    query = select(ScrapeJob)

    if status_filter:
        query = query.where(ScrapeJob.status == status_filter)

    query = query.order_by(ScrapeJob.created_at.desc()).limit(limit)

    result = await db.execute(query)
    jobs = result.scalars().all()

    return [
        {
            "id": job.id,
            "job_type": job.job_type,
            "target_id": job.target_id,
            "status": job.status,
            "started_at": job.started_at,
            "completed_at": job.completed_at,
            "error_message": job.error_message,
            "created_at": job.created_at,
        }
        for job in jobs
    ]


# Analytics
@router.get("/analytics/overview", response_model=AnalyticsOverview)
async def get_analytics_overview(
    period: str = "30d",
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = Depends(get_current_admin),
):
    """Get analytics overview."""
    # Parse period
    days = int(period.replace("d", "")) if "d" in period else 30
    since = datetime.utcnow() - timedelta(days=days)

    # Quizzes completed
    quiz_count_result = await db.execute(
        select(func.count())
        .select_from(QuizSession)
        .where(QuizSession.completed_at >= since)
    )
    quizzes_completed = quiz_count_result.scalar() or 0

    # Quiz started
    quiz_started_result = await db.execute(
        select(func.count())
        .select_from(QuizSession)
        .where(QuizSession.started_at >= since)
    )
    quizzes_started = quiz_started_result.scalar() or 1  # Avoid division by zero

    # Recommendations generated
    rec_count_result = await db.execute(
        select(func.count())
        .select_from(Recommendation)
        .where(Recommendation.created_at >= since)
    )
    recommendations_generated = rec_count_result.scalar() or 0

    # Recommendations with clicks
    clicked_result = await db.execute(
        select(func.count())
        .select_from(Recommendation)
        .where(
            Recommendation.created_at >= since,
            Recommendation.user_clicked_shoes != None,
        )
    )
    clicked_count = clicked_result.scalar() or 0

    # Helpful feedback
    helpful_result = await db.execute(
        select(func.count())
        .select_from(Recommendation)
        .where(
            Recommendation.created_at >= since,
            Recommendation.user_feedback != None,
        )
    )
    feedback_count = helpful_result.scalar() or 0

    click_through_rate = clicked_count / recommendations_generated if recommendations_generated > 0 else 0
    quiz_completion_rate = quizzes_completed / quizzes_started if quizzes_started > 0 else 0

    return AnalyticsOverview(
        quizzes_completed=quizzes_completed,
        recommendations_generated=recommendations_generated,
        click_through_rate=click_through_rate,
        quiz_completion_rate=quiz_completion_rate,
        feedback_summary={
            "total_feedback": feedback_count,
        },
        top_recommended_shoes=[],  # Would need to aggregate from recommended_shoes JSONB
    )


# Brand and Category management
@router.get("/brands")
async def list_brands(
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = Depends(get_current_admin),
):
    """List all brands."""
    result = await db.execute(select(Brand).order_by(Brand.name))
    brands = result.scalars().all()
    return [{"id": b.id, "name": b.name, "slug": b.slug} for b in brands]


@router.post("/brands")
async def create_brand(
    name: str,
    slug: str,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = Depends(get_current_admin),
):
    """Create a new brand."""
    brand = Brand(name=name, slug=slug)
    db.add(brand)
    await db.commit()
    await db.refresh(brand)
    return {"id": brand.id, "name": brand.name}


@router.get("/categories")
async def list_categories(
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = Depends(get_current_admin),
):
    """List all categories."""
    result = await db.execute(select(Category).order_by(Category.display_order))
    categories = result.scalars().all()
    return [{"id": c.id, "name": c.name, "slug": c.slug, "is_active": c.is_active} for c in categories]


@router.get("/catalog/stats")
async def get_catalog_stats(
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = Depends(get_current_admin),
):
    """Get statistics about the new catalog (ShoeProduct/ShoeModel/ShoeOffer)."""
    # Count products
    product_count_result = await db.execute(select(func.count()).select_from(ShoeProduct))
    product_count = product_count_result.scalar() or 0

    # Count models
    model_count_result = await db.execute(select(func.count()).select_from(ShoeModel))
    model_count = model_count_result.scalar() or 0

    # Count offers
    offer_count_result = await db.execute(select(func.count()).select_from(ShoeOffer))
    offer_count = offer_count_result.scalar() or 0

    # Count products needing review
    needs_review_result = await db.execute(
        select(func.count()).select_from(ShoeProduct).where(ShoeProduct.needs_review == True)
    )
    needs_review_count = needs_review_result.scalar() or 0

    # Count products with all specs
    complete_result = await db.execute(
        select(func.count()).select_from(ShoeProduct).where(
            ShoeProduct.msrp_usd != None,
            ShoeProduct.weight_oz != None,
            ShoeProduct.drop_mm != None,
        )
    )
    complete_count = complete_result.scalar() or 0

    # Products by brand
    brand_stats_result = await db.execute(
        select(Brand.name, func.count(ShoeProduct.id))
        .join(ShoeModel, ShoeModel.brand_id == Brand.id)
        .join(ShoeProduct, ShoeProduct.model_id == ShoeModel.id)
        .group_by(Brand.name)
        .order_by(func.count(ShoeProduct.id).desc())
    )
    brand_stats = [{"brand": row[0], "count": row[1]} for row in brand_stats_result.all()]

    return {
        "total_products": product_count,
        "total_models": model_count,
        "total_offers": offer_count,
        "needs_review": needs_review_count,
        "complete_products": complete_count,
        "incomplete_products": product_count - complete_count,
        "by_brand": brand_stats,
    }
