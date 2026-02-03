# Shoe Matcher — Technical Specification

**Version:** 1.0
**Last Updated:** January 2025

---

## Table of Contents

1. [Overview](#overview)
2. [System Architecture](#system-architecture)
3. [Tech Stack](#tech-stack)
4. [Database Schema](#database-schema)
5. [API Specification](#api-specification)
6. [Matching Algorithm](#matching-algorithm)
7. [Frontend Specification](#frontend-specification)
8. [Admin Dashboard](#admin-dashboard)
9. [Scraper System](#scraper-system)
10. [RLHF Training Loop](#rlhf-training-loop)
11. [Deployment](#deployment)
12. [Future Considerations](#future-considerations)

---

## Overview

### Product Summary

A shoe recommendation platform that matches users to their ideal running or basketball shoes based on a quiz, foot scan upload, and AI-enriched shoe data aggregated from reviews across the web.

### Core Value Proposition

- Unbiased recommendations (not tied to a single retailer)
- AI-parsed review data for accurate fit profiles
- Expert-level matching logic refined through RLHF

### Monetization

- Affiliate links (5-15% commission per sale)
- Future: Direct retailer partnerships, premium features

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         FRONTEND                                 │
│                    (Next.js + Vercel)                           │
├─────────────────────────────────────────────────────────────────┤
│  Landing Page  │  Quiz Flow  │  Results  │  Admin Dashboard     │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                        API LAYER                                 │
│                   (Python FastAPI)                              │
├─────────────────────────────────────────────────────────────────┤
│  /quiz  │  /recommend  │  /shoes  │  /admin  │  /scrape        │
└────────────────────────────┬────────────────────────────────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
┌──────────────────┐ ┌──────────────┐ ┌──────────────────┐
│    Supabase      │ │   Scraper    │ │   AI Services    │
│   PostgreSQL     │ │   Workers    │ │  (Claude API)    │
│                  │ │              │ │                  │
│ - Shoes          │ │ - Review     │ │ - Review parsing │
│ - Users          │ │   ingestion  │ │ - Fit extraction │
│ - Quizzes        │ │ - Price      │ │ - Matching boost │
│ - Recommendations│ │   tracking   │ │                  │
│ - Training data  │ │              │ │                  │
└──────────────────┘ └──────────────┘ └──────────────────┘
```

---

## Tech Stack

### Frontend
| Technology | Purpose |
|------------|---------|
| Next.js 14 | React framework, App Router |
| TypeScript | Type safety |
| Tailwind CSS | Styling |
| shadcn/ui | Component library |
| Zustand | State management (quiz flow) |
| React Query | API data fetching |

### Backend
| Technology | Purpose |
|------------|---------|
| Python 3.11+ | Primary language |
| FastAPI | API framework |
| Pydantic | Data validation |
| SQLAlchemy | ORM |
| Alembic | Database migrations |
| Celery + Redis | Background job queue (scrapers) |

### Database
| Technology | Purpose |
|------------|---------|
| Supabase PostgreSQL | Primary database |
| Redis | Job queue, caching |

### Infrastructure
| Technology | Purpose |
|------------|---------|
| Vercel | Frontend hosting |
| Railway / Render | Backend hosting |
| Supabase | Database hosting |
| Upstash | Redis hosting (free tier) |

### External Services
| Service | Purpose |
|---------|---------|
| Claude API | Review parsing, fit extraction |
| Anthropic | AI services |

---

## Database Schema

### Core Tables

```sql
-- Categories: running, basketball, etc.
CREATE TABLE categories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(50) NOT NULL UNIQUE,
    slug VARCHAR(50) NOT NULL UNIQUE,
    display_order INT DEFAULT 0,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Brands
CREATE TABLE brands (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL UNIQUE,
    slug VARCHAR(100) NOT NULL UNIQUE,
    logo_url VARCHAR(500),
    website_url VARCHAR(500),
    affiliate_base_url VARCHAR(500),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Shoes (main product table)
CREATE TABLE shoes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    brand_id UUID NOT NULL REFERENCES brands(id),
    category_id UUID NOT NULL REFERENCES categories(id),
    
    -- Basic info
    name VARCHAR(200) NOT NULL,
    slug VARCHAR(200) NOT NULL,
    model_year INT,
    version VARCHAR(20), -- "21", "v3", etc.
    
    -- Pricing
    msrp_usd DECIMAL(10,2),
    current_price_min DECIMAL(10,2),
    current_price_max DECIMAL(10,2),
    
    -- Availability
    available_regions TEXT[], -- ['US', 'EU', 'UK', 'JP']
    width_options TEXT[], -- ['standard', 'wide', 'extra_wide']
    is_discontinued BOOLEAN DEFAULT false,
    
    -- Images
    primary_image_url VARCHAR(500),
    image_urls TEXT[],
    
    -- Status
    is_active BOOLEAN DEFAULT true,
    needs_review BOOLEAN DEFAULT false,
    last_scraped_at TIMESTAMP,
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    UNIQUE(brand_id, slug)
);

-- Running-specific attributes
CREATE TABLE running_shoe_attributes (
    shoe_id UUID PRIMARY KEY REFERENCES shoes(id) ON DELETE CASCADE,
    
    -- Type
    terrain TEXT NOT NULL, -- 'road', 'trail', 'track'
    subcategory TEXT, -- 'neutral', 'stability', 'motion_control', 'racing', 'daily_trainer'
    
    -- Physical specs
    weight_oz DECIMAL(4,1),
    stack_height_heel_mm DECIMAL(4,1),
    stack_height_forefoot_mm DECIMAL(4,1),
    drop_mm DECIMAL(4,1),
    
    -- Features
    has_carbon_plate BOOLEAN DEFAULT false,
    has_rocker BOOLEAN DEFAULT false,
    cushion_type TEXT, -- 'foam', 'gel', 'air', 'hybrid'
    cushion_level TEXT, -- 'minimal', 'moderate', 'max'
    
    -- Best for
    best_for_distances TEXT[], -- ['5k', 'half_marathon', 'marathon', 'ultra']
    best_for_pace TEXT, -- 'easy', 'tempo', 'speed', 'racing'
    
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Basketball-specific attributes
CREATE TABLE basketball_shoe_attributes (
    shoe_id UUID PRIMARY KEY REFERENCES shoes(id) ON DELETE CASCADE,
    
    -- Type
    cut TEXT NOT NULL, -- 'low', 'mid', 'high'
    court_type TEXT[], -- ['indoor', 'outdoor']
    
    -- Physical specs
    weight_oz DECIMAL(4,1),
    
    -- Features
    cushion_type TEXT, -- 'foam', 'air', 'zoom', 'boost', 'hybrid'
    cushion_level TEXT, -- 'court_feel', 'balanced', 'impact_protection'
    traction_pattern TEXT,
    ankle_support_level TEXT, -- 'minimal', 'moderate', 'high'
    lockdown_level TEXT, -- 'loose', 'moderate', 'tight'
    
    -- Best for
    best_for_position TEXT[], -- ['guard', 'wing', 'big']
    best_for_playstyle TEXT[], -- ['speed', 'power', 'all_around']
    outdoor_durability TEXT, -- 'poor', 'moderate', 'excellent'
    
    updated_at TIMESTAMP DEFAULT NOW()
);

-- AI-extracted fit profile from reviews
CREATE TABLE shoe_fit_profiles (
    shoe_id UUID PRIMARY KEY REFERENCES shoes(id) ON DELETE CASCADE,
    
    -- Sizing
    size_runs TEXT, -- 'small', 'true', 'large'
    size_offset DECIMAL(3,1), -- -1.0 to +1.0 (e.g., +0.5 means runs half size large)
    size_confidence DECIMAL(3,2), -- 0.0 to 1.0
    
    -- Width
    width_runs TEXT, -- 'narrow', 'true', 'wide'
    toe_box_room TEXT, -- 'cramped', 'snug', 'roomy', 'spacious'
    heel_fit TEXT, -- 'loose', 'secure', 'tight'
    midfoot_fit TEXT, -- 'loose', 'secure', 'tight'
    
    -- Arch
    arch_support TEXT, -- 'flat', 'neutral', 'high'
    arch_support_level TEXT, -- 'minimal', 'moderate', 'substantial'
    
    -- Comfort
    break_in_period TEXT, -- 'none', 'short', 'moderate', 'long'
    break_in_miles INT,
    all_day_comfort BOOLEAN,
    
    -- Durability
    expected_miles_min INT,
    expected_miles_max INT,
    durability_rating TEXT, -- 'poor', 'average', 'good', 'excellent'
    common_wear_points TEXT[],
    
    -- Issues
    common_complaints TEXT[],
    works_well_for TEXT[], -- 'wide_feet', 'narrow_feet', 'high_arches', etc.
    avoid_if TEXT[], -- 'plantar_fasciitis', 'bunions', etc.
    
    -- Sentiment
    overall_sentiment DECIMAL(3,2), -- 0.0 to 1.0
    review_count INT,
    
    -- Meta
    last_updated TIMESTAMP DEFAULT NOW(),
    extraction_model VARCHAR(50), -- 'claude-3-sonnet', etc.
    needs_review BOOLEAN DEFAULT true
);

-- Raw scraped reviews (for reprocessing)
CREATE TABLE shoe_reviews (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    shoe_id UUID NOT NULL REFERENCES shoes(id) ON DELETE CASCADE,
    
    source VARCHAR(100) NOT NULL, -- 'running_warehouse', 'fleet_feet', etc.
    source_url VARCHAR(500),
    source_review_id VARCHAR(100),
    
    -- Content
    reviewer_name VARCHAR(100),
    rating DECIMAL(2,1),
    title VARCHAR(500),
    body TEXT,
    
    -- Reviewer context
    reviewer_foot_width TEXT,
    reviewer_arch_type TEXT,
    reviewer_size_purchased VARCHAR(20),
    reviewer_typical_size VARCHAR(20),
    reviewer_miles_tested INT,
    
    -- Dates
    review_date DATE,
    scraped_at TIMESTAMP DEFAULT NOW(),
    
    UNIQUE(shoe_id, source, source_review_id)
);

-- Affiliate links per retailer
CREATE TABLE shoe_affiliate_links (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    shoe_id UUID NOT NULL REFERENCES shoes(id) ON DELETE CASCADE,
    
    retailer VARCHAR(100) NOT NULL, -- 'amazon', 'running_warehouse', 'foot_locker'
    url VARCHAR(1000) NOT NULL,
    affiliate_tag VARCHAR(100),
    current_price DECIMAL(10,2),
    in_stock BOOLEAN DEFAULT true,
    last_checked TIMESTAMP,
    
    UNIQUE(shoe_id, retailer)
);
```

### Quiz & Recommendation Tables

```sql
-- Quiz sessions
CREATE TABLE quiz_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Session tracking
    session_token VARCHAR(100) UNIQUE,
    ip_address INET,
    user_agent TEXT,
    
    -- Quiz data
    category_id UUID REFERENCES categories(id),
    answers JSONB NOT NULL, -- full quiz answers
    
    -- User profile extracted from answers
    user_foot_profile JSONB, -- { width, arch, pronation, issues }
    user_preferences JSONB, -- { priorities, budget, experience }
    
    -- Optional
    region VARCHAR(10),
    previous_shoes JSONB, -- [{ shoe_id, liked, notes }]
    foot_scan_data JSONB, -- uploaded scan results
    
    -- Timestamps
    started_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,
    
    created_at TIMESTAMP DEFAULT NOW()
);

-- Recommendations generated
CREATE TABLE recommendations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    quiz_session_id UUID NOT NULL REFERENCES quiz_sessions(id),
    
    -- The recommendations
    recommended_shoes JSONB NOT NULL, -- [{ shoe_id, rank, score, reasoning }]
    
    -- Algorithm metadata
    algorithm_version VARCHAR(20),
    model_weights JSONB, -- weights used at time of recommendation
    
    -- Admin review (RLHF)
    review_status TEXT DEFAULT 'pending', -- 'pending', 'approved', 'rejected', 'adjusted'
    reviewed_by UUID, -- admin user id
    reviewed_at TIMESTAMP,
    adjusted_shoes JSONB, -- if admin made changes
    admin_notes TEXT,
    
    -- User feedback
    user_clicked_shoes TEXT[], -- shoe_ids they clicked
    user_feedback JSONB, -- { helpful: bool, purchased_shoe_id, rating, notes }
    feedback_at TIMESTAMP,
    
    created_at TIMESTAMP DEFAULT NOW()
);

-- Training data for RLHF
CREATE TABLE training_examples (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Input
    quiz_answers JSONB NOT NULL,
    category_id UUID REFERENCES categories(id),
    
    -- Labels
    ideal_shoes JSONB NOT NULL, -- admin-approved shoe ranking
    reasoning JSONB, -- why each shoe was chosen
    
    -- Meta
    source TEXT, -- 'admin_approval', 'admin_correction', 'user_feedback'
    quality_score DECIMAL(3,2), -- confidence in this example
    
    created_at TIMESTAMP DEFAULT NOW()
);
```

### Admin Tables

```sql
-- Admin users
CREATE TABLE admin_users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    name VARCHAR(100),
    role TEXT DEFAULT 'reviewer', -- 'reviewer', 'editor', 'admin'
    is_active BOOLEAN DEFAULT true,
    last_login TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Audit log
CREATE TABLE admin_audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    admin_user_id UUID REFERENCES admin_users(id),
    action TEXT NOT NULL, -- 'approve_recommendation', 'edit_shoe', 'trigger_scrape'
    entity_type TEXT, -- 'shoe', 'recommendation', 'fit_profile'
    entity_id UUID,
    changes JSONB, -- what changed
    created_at TIMESTAMP DEFAULT NOW()
);

-- Scrape jobs
CREATE TABLE scrape_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    job_type TEXT NOT NULL, -- 'single_shoe', 'brand', 'category', 'all_reviews'
    target_id UUID, -- shoe_id, brand_id, or category_id
    source VARCHAR(100),
    
    status TEXT DEFAULT 'pending', -- 'pending', 'running', 'completed', 'failed'
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    
    results JSONB, -- summary of what was scraped
    error_message TEXT,
    
    triggered_by UUID REFERENCES admin_users(id),
    created_at TIMESTAMP DEFAULT NOW()
);
```

### Indexes

```sql
-- Performance indexes
CREATE INDEX idx_shoes_category ON shoes(category_id) WHERE is_active = true;
CREATE INDEX idx_shoes_brand ON shoes(brand_id);
CREATE INDEX idx_shoes_needs_review ON shoes(needs_review) WHERE needs_review = true;

CREATE INDEX idx_recommendations_pending ON recommendations(review_status) 
    WHERE review_status = 'pending';
CREATE INDEX idx_recommendations_quiz ON recommendations(quiz_session_id);

CREATE INDEX idx_reviews_shoe ON shoe_reviews(shoe_id);
CREATE INDEX idx_reviews_source ON shoe_reviews(source);

CREATE INDEX idx_quiz_sessions_completed ON quiz_sessions(completed_at) 
    WHERE completed_at IS NOT NULL;
```

---

## API Specification

### Base URL

```
Production: https://api.shoematcher.com/v1
Development: http://localhost:8000/v1
```

### Authentication

- Public endpoints: No auth required (quiz, recommendations)
- Admin endpoints: JWT Bearer token

```
Authorization: Bearer <jwt_token>
```

### Public Endpoints

#### Start Quiz Session

```
POST /quiz/start

Request:
{
    "category": "running" | "basketball",
    "region": "US" | "EU" | "UK" (optional)
}

Response:
{
    "session_id": "uuid",
    "session_token": "string",
    "questions": [
        {
            "id": "terrain",
            "type": "single_select",
            "question": "What type of running do you primarily do?",
            "options": [
                { "value": "road", "label": "Road running" },
                { "value": "trail", "label": "Trail running" },
                { "value": "track", "label": "Track / Speed work" },
                { "value": "treadmill", "label": "Treadmill" }
            ]
        },
        // ... more questions
    ]
}
```

#### Submit Quiz Answer

```
POST /quiz/{session_id}/answer

Request:
{
    "question_id": "terrain",
    "answer": "road"
}

Response:
{
    "next_question": { ... } | null,
    "progress": 0.42,
    "is_complete": false
}
```

#### Get Recommendations

```
POST /quiz/{session_id}/recommend

Request:
{
    "previous_shoes": [  // optional
        { "shoe_id": "uuid", "liked": true, "notes": "Great cushion" }
    ]
}

Response:
{
    "recommendation_id": "uuid",
    "shoes": [
        {
            "rank": 1,
            "shoe": {
                "id": "uuid",
                "brand": "Brooks",
                "name": "Ghost 15",
                "primary_image_url": "...",
                "msrp_usd": 140.00,
                "current_price_min": 119.99
            },
            "match_score": 0.94,
            "reasoning": "Based on your preference for cushioned road running and neutral gait, the Ghost 15 offers excellent comfort for daily training. Its balanced cushioning works well for your mixed distances.",
            "fit_notes": {
                "sizing": "Runs true to size",
                "width": "Standard width, roomy toe box",
                "highlights": ["Great for neutral runners", "Versatile daily trainer"],
                "considerations": ["May feel heavy for speed work"]
            },
            "affiliate_links": [
                { "retailer": "Running Warehouse", "url": "...", "price": 119.99 },
                { "retailer": "Amazon", "url": "...", "price": 129.99 }
            ]
        },
        // ... 4 more shoes
    ],
    "not_recommended": [  // optional, shows why popular shoes weren't picked
        {
            "shoe": { "brand": "Hoka", "name": "Clifton 9" },
            "reason": "You mentioned preferring a lower stack height and more ground feel"
        }
    ]
}
```

#### Get Single Shoe Details

```
GET /shoes/{shoe_id}

Response:
{
    "id": "uuid",
    "brand": { "id": "uuid", "name": "Brooks", "logo_url": "..." },
    "category": "running",
    "name": "Ghost 15",
    "full_name": "Brooks Ghost 15",
    "model_year": 2023,
    
    "specs": {
        "weight_oz": 10.1,
        "drop_mm": 12,
        "stack_height_heel_mm": 35,
        "stack_height_forefoot_mm": 23,
        "cushion_type": "DNA LOFT",
        "terrain": "road",
        "subcategory": "neutral"
    },
    
    "fit_profile": {
        "size_runs": "true",
        "width_runs": "true",
        "toe_box_room": "roomy",
        "arch_support": "neutral",
        "break_in_period": "none",
        "durability_rating": "good",
        "expected_miles": "400-500",
        "common_complaints": ["Can feel heavy for speed work"],
        "works_well_for": ["neutral runners", "daily training"],
        "overall_sentiment": 0.87,
        "review_count": 342
    },
    
    "pricing": {
        "msrp_usd": 140.00,
        "current_min": 119.99,
        "current_max": 140.00
    },
    
    "affiliate_links": [...],
    "images": [...]
}
```

#### Submit User Feedback

```
POST /recommendations/{recommendation_id}/feedback

Request:
{
    "helpful": true,
    "purchased_shoe_id": "uuid" | null,
    "rating": 5,
    "notes": "Bought the Ghost 15, fits perfectly!"
}

Response:
{
    "success": true
}
```

### Admin Endpoints

#### List Pending Recommendations

```
GET /admin/recommendations?status=pending&limit=50

Response:
{
    "items": [
        {
            "id": "uuid",
            "created_at": "2025-01-15T...",
            "quiz_summary": {
                "category": "running",
                "terrain": "road",
                "distance": "half_marathon",
                "priorities": ["cushion", "durability"],
                "foot_issues": ["overpronation"]
            },
            "recommended_shoes": [
                { "rank": 1, "shoe_id": "uuid", "shoe_name": "Brooks Adrenaline GTS 23", "score": 0.91 },
                // ...
            ],
            "review_status": "pending"
        }
    ],
    "total": 234,
    "page": 1
}
```

#### Review Recommendation

```
POST /admin/recommendations/{id}/review

Request:
{
    "status": "approved" | "rejected" | "adjusted",
    "adjusted_shoes": [  // only if adjusted
        { "shoe_id": "uuid", "rank": 1 },
        { "shoe_id": "uuid", "rank": 2 },
        // ...
    ],
    "notes": "Swapped #2 and #3, Kayano better for severe overpronation"
}

Response:
{
    "success": true,
    "training_example_created": true
}
```

#### CRUD Shoes

```
GET    /admin/shoes?category=running&brand=brooks&needs_review=true
POST   /admin/shoes
GET    /admin/shoes/{id}
PUT    /admin/shoes/{id}
DELETE /admin/shoes/{id}

POST   /admin/shoes/{id}/fit-profile  // manual override of AI-extracted profile
POST   /admin/shoes/{id}/trigger-scrape  // re-scrape reviews
```

#### Scraper Management

```
POST /admin/scrape/trigger

Request:
{
    "job_type": "single_shoe" | "brand" | "category" | "all_reviews",
    "target_id": "uuid",  // shoe_id, brand_id, or category_id
    "sources": ["running_warehouse", "fleet_feet"]  // optional, defaults to all
}

Response:
{
    "job_id": "uuid",
    "status": "pending",
    "estimated_duration_minutes": 5
}

GET /admin/scrape/jobs?status=running
GET /admin/scrape/jobs/{job_id}
```

#### Analytics

```
GET /admin/analytics/overview?period=30d

Response:
{
    "quizzes_completed": 1234,
    "recommendations_generated": 1189,
    "click_through_rate": 0.34,
    "top_recommended_shoes": [
        { "shoe_id": "uuid", "name": "Brooks Ghost 15", "count": 89 }
    ],
    "quiz_completion_rate": 0.78,
    "drop_off_by_question": {
        "terrain": 0.02,
        "distance": 0.05,
        "foot_issues": 0.12
    },
    "feedback_summary": {
        "helpful_rate": 0.82,
        "purchase_rate": 0.12
    }
}
```

---

## Matching Algorithm

### Overview

The matching algorithm scores each shoe against the user's profile and returns the top 5 matches. It uses a weighted scoring system that can be tuned via admin settings and refined through RLHF.

### Scoring Formula

```python
def calculate_match_score(shoe: Shoe, user_profile: UserProfile, weights: Weights) -> float:
    """
    Calculate how well a shoe matches a user's needs.
    Returns a score from 0.0 to 1.0.
    """
    
    scores = {}
    
    # 1. Category match (hard filter)
    if shoe.category != user_profile.category:
        return 0.0
    
    # 2. Terrain/Court match (hard filter for primary, soft for secondary)
    terrain_score = calculate_terrain_match(shoe, user_profile)
    if terrain_score == 0:
        return 0.0
    scores['terrain'] = terrain_score
    
    # 3. Foot profile compatibility
    scores['width'] = calculate_width_match(shoe.fit_profile, user_profile.foot)
    scores['arch'] = calculate_arch_match(shoe, user_profile.foot)
    scores['pronation'] = calculate_pronation_match(shoe, user_profile.foot)
    
    # 4. Issue compatibility (negative scoring for bad matches)
    scores['issues'] = calculate_issue_compatibility(shoe, user_profile.foot_issues)
    
    # 5. Preference alignment
    scores['cushion'] = calculate_cushion_match(shoe, user_profile.preferences)
    scores['priorities'] = calculate_priority_match(shoe, user_profile.priorities)
    
    # 6. Use case fit
    scores['distance'] = calculate_distance_match(shoe, user_profile.distances)  # running
    scores['position'] = calculate_position_match(shoe, user_profile.position)   # basketball
    
    # 7. Budget fit
    scores['budget'] = calculate_budget_match(shoe.current_price_min, user_profile.budget)
    
    # 8. Previous shoe similarity (if provided)
    if user_profile.previous_shoes:
        scores['history'] = calculate_history_match(shoe, user_profile.previous_shoes)
    
    # 9. Overall quality signal
    scores['sentiment'] = shoe.fit_profile.overall_sentiment or 0.5
    
    # Weighted combination
    final_score = sum(
        scores.get(key, 0.5) * weights.get(key, 1.0)
        for key in weights.keys()
    ) / sum(weights.values())
    
    return final_score
```

### Default Weights

```python
DEFAULT_WEIGHTS = {
    # Hard requirements (high weight)
    'terrain': 2.0,
    'pronation': 1.8,
    'issues': 1.8,
    
    # Important preferences
    'width': 1.5,
    'arch': 1.3,
    'priorities': 1.3,
    'cushion': 1.2,
    
    # Secondary factors
    'distance': 1.0,
    'position': 1.0,
    'budget': 1.0,
    'history': 0.8,
    'sentiment': 0.5,
}
```

### Component Scoring Functions

```python
def calculate_width_match(fit_profile: FitProfile, foot: FootProfile) -> float:
    """
    Score width compatibility.
    """
    width_map = {
        ('narrow', 'narrow'): 1.0,
        ('narrow', 'standard'): 0.5,
        ('narrow', 'wide'): 0.1,
        ('true', 'narrow'): 0.7,
        ('true', 'standard'): 1.0,
        ('true', 'wide'): 0.7,
        ('wide', 'narrow'): 0.1,
        ('wide', 'standard'): 0.6,
        ('wide', 'wide'): 1.0,
    }
    
    shoe_width = fit_profile.width_runs or 'true'
    user_width = foot.width or 'standard'
    
    return width_map.get((shoe_width, user_width), 0.5)


def calculate_pronation_match(shoe: Shoe, foot: FootProfile) -> float:
    """
    Match shoe support level to pronation needs.
    """
    if shoe.category != 'running':
        return 1.0  # Not applicable
    
    attrs = shoe.running_attributes
    user_pronation = foot.pronation or 'neutral'
    
    support_map = {
        # (shoe_type, user_pronation): score
        ('neutral', 'neutral'): 1.0,
        ('neutral', 'overpronation'): 0.3,
        ('neutral', 'underpronation'): 0.8,
        ('stability', 'neutral'): 0.7,
        ('stability', 'overpronation'): 1.0,
        ('stability', 'underpronation'): 0.4,
        ('motion_control', 'neutral'): 0.4,
        ('motion_control', 'overpronation'): 0.9,  # severe overpronation
        ('motion_control', 'underpronation'): 0.2,
    }
    
    return support_map.get((attrs.subcategory, user_pronation), 0.5)


def calculate_issue_compatibility(shoe: Shoe, issues: List[str]) -> float:
    """
    Check if shoe works for or should be avoided given foot issues.
    Returns 0.0 if shoe is contraindicated, 1.0 if works well, 0.5 neutral.
    """
    if not issues:
        return 1.0
    
    fit = shoe.fit_profile
    
    score = 1.0
    for issue in issues:
        if issue in (fit.avoid_if or []):
            score *= 0.1  # Strong penalty
        elif issue in (fit.works_well_for or []):
            score *= 1.2  # Bonus (capped at 1.0 later)
    
    return min(score, 1.0)
```

### Generating Reasoning

```python
def generate_reasoning(shoe: Shoe, user_profile: UserProfile, scores: dict) -> str:
    """
    Generate human-readable explanation for why this shoe was recommended.
    """
    reasons = []
    
    # Top positive factors
    if scores.get('pronation', 0) > 0.8 and user_profile.foot.pronation == 'overpronation':
        reasons.append(f"provides the stability support you need for overpronation")
    
    if scores.get('cushion', 0) > 0.8 and 'cushion' in user_profile.priorities:
        reasons.append(f"offers the high cushioning you prioritized")
    
    if scores.get('width', 0) > 0.9:
        reasons.append(f"fits well for {user_profile.foot.width} feet")
    
    # Use case
    if shoe.category == 'running':
        distances = user_profile.distances
        if 'marathon' in distances:
            reasons.append(f"built for long-distance comfort")
    
    # Combine
    if len(reasons) >= 2:
        return f"This shoe {reasons[0]} and {reasons[1]}."
    elif reasons:
        return f"This shoe {reasons[0]}."
    else:
        return "A solid all-around choice for your profile."
```

### RLHF Integration

```python
def update_weights_from_training(training_examples: List[TrainingExample]) -> Weights:
    """
    Adjust weights based on admin corrections.
    
    When an admin adjusts a recommendation, we can infer which factors
    they're prioritizing.
    """
    # Implementation: gradient-free optimization or simple heuristics
    # 
    # Example: if admin consistently ranks stability shoes higher for
    # overpronators than the algorithm does, increase 'pronation' weight
    
    pass  # Detailed implementation TBD based on volume of training data
```

---

## Frontend Specification

### Pages

```
/                       # Landing page
/quiz/running           # Running shoe quiz
/quiz/basketball        # Basketball shoe quiz
/results/{session_id}   # Results page
/shoes/{slug}           # Individual shoe detail page
/compare                # Compare 2-3 shoes side by side (future)

/admin                  # Admin dashboard
/admin/login            # Admin login
/admin/recommendations  # Review queue
/admin/shoes            # Shoe management
/admin/shoes/{id}       # Edit shoe
/admin/scraper          # Scraper management
/admin/analytics        # Analytics dashboard
```

### Component Hierarchy

```
app/
├── layout.tsx                    # Root layout
├── page.tsx                      # Landing page
├── quiz/
│   ├── [category]/
│   │   └── page.tsx              # Quiz flow
│   └── components/
│       ├── QuizContainer.tsx     # Main quiz state machine
│       ├── QuestionCard.tsx      # Single question display
│       ├── ProgressBar.tsx
│       ├── OptionButton.tsx
│       └── PreviousShoesInput.tsx
├── results/
│   ├── [sessionId]/
│   │   └── page.tsx              # Results page
│   └── components/
│       ├── TopMatchCard.tsx      # Featured #1 recommendation
│       ├── RunnerUpCard.tsx      # #2-5 recommendations
│       ├── FitNotes.tsx
│       ├── ReasoningBlock.tsx
│       ├── AffiliateButtons.tsx
│       ├── NotRecommendedSection.tsx
│       └── FeedbackWidget.tsx
├── shoes/
│   ├── [slug]/
│   │   └── page.tsx              # Shoe detail page
│   └── components/
│       ├── ShoeHeader.tsx
│       ├── SpecsTable.tsx
│       ├── FitProfileCard.tsx
│       └── PriceComparison.tsx
└── admin/
    ├── layout.tsx                # Admin layout with sidebar
    ├── page.tsx                  # Dashboard overview
    ├── recommendations/
    │   └── page.tsx              # Review queue
    ├── shoes/
    │   ├── page.tsx              # Shoe list
    │   └── [id]/
    │       └── page.tsx          # Edit shoe
    ├── scraper/
    │   └── page.tsx              # Scraper jobs
    └── components/
        ├── Sidebar.tsx
        ├── RecommendationReviewCard.tsx
        ├── ShoeForm.tsx
        ├── FitProfileForm.tsx
        └── AnalyticsCharts.tsx
```

### Quiz State Machine

```typescript
// Using Zustand for quiz state

interface QuizState {
  sessionId: string | null;
  category: 'running' | 'basketball' | null;
  currentQuestionIndex: number;
  questions: Question[];
  answers: Record<string, any>;
  previousShoes: PreviousShoe[];
  isLoading: boolean;
  isComplete: boolean;
  
  // Actions
  startQuiz: (category: string) => Promise<void>;
  submitAnswer: (questionId: string, answer: any) => Promise<void>;
  goBack: () => void;
  addPreviousShoe: (shoe: PreviousShoe) => void;
  getRecommendations: () => Promise<void>;
}

type QuizStep = 
  | 'category_select'
  | 'questions'
  | 'previous_shoes'  // optional step
  | 'loading_results'
  | 'complete';
```

### Key UI Components

#### Landing Page

```tsx
// Hero section with clear value prop and category selection
<Hero>
  <h1>Find Your Perfect Shoe</h1>
  <p>60-second quiz. 500+ shoes analyzed. Zero bias.</p>
  
  <CategoryCards>
    <CategoryCard 
      icon={<RunningIcon />}
      title="Running Shoes"
      subtitle="Road, trail, track & more"
      href="/quiz/running"
    />
    <CategoryCard
      icon={<BasketballIcon />}
      title="Basketball Shoes"
      subtitle="Indoor, outdoor, all positions"
      href="/quiz/basketball"
    />
  </CategoryCards>
</Hero>

// Trust signals
<TrustBar>
  <Stat number="500+" label="Shoes analyzed" />
  <Stat number="10K+" label="Reviews processed" />
  <Stat number="95%" label="Match satisfaction" />
</TrustBar>
```

#### Results Page

```tsx
<ResultsPage>
  <Header>
    <h1>Your Top Matches</h1>
    <p>Based on your {category} profile</p>
  </Header>
  
  {/* Featured top pick */}
  <TopMatchCard shoe={recommendations[0]} />
  
  {/* Runners up */}
  <RunnersUpGrid>
    {recommendations.slice(1).map(rec => (
      <RunnerUpCard key={rec.shoe.id} recommendation={rec} />
    ))}
  </RunnersUpGrid>
  
  {/* Why not section */}
  {notRecommended.length > 0 && (
    <NotRecommendedSection items={notRecommended} />
  )}
  
  {/* Feedback */}
  <FeedbackWidget recommendationId={recommendationId} />
  
  {/* Retake option */}
  <RetakeButton href={`/quiz/${category}`}>
    Retake Quiz
  </RetakeButton>
</ResultsPage>
```

---

## Admin Dashboard

### Recommendation Review Queue

The core admin workflow for RLHF training.

```tsx
<ReviewQueue>
  <Filters>
    <StatusFilter options={['pending', 'approved', 'rejected', 'adjusted']} />
    <CategoryFilter options={['running', 'basketball']} />
    <DateRange />
  </Filters>
  
  <QueueList>
    {recommendations.map(rec => (
      <ReviewCard key={rec.id}>
        {/* Quiz summary */}
        <QuizSummary>
          <Badge>{rec.category}</Badge>
          <dl>
            <dt>Terrain</dt><dd>{rec.quiz.terrain}</dd>
            <dt>Priorities</dt><dd>{rec.quiz.priorities.join(', ')}</dd>
            <dt>Foot issues</dt><dd>{rec.quiz.foot_issues.join(', ') || 'None'}</dd>
          </dl>
        </QuizSummary>
        
        {/* Recommendations with reorder capability */}
        <RecommendationList 
          shoes={rec.recommended_shoes}
          onReorder={handleReorder}
          onSwap={handleSwap}
        />
        
        {/* Actions */}
        <Actions>
          <Button variant="success" onClick={() => approve(rec.id)}>
            Approve
          </Button>
          <Button variant="warning" onClick={() => openAdjustModal(rec)}>
            Adjust
          </Button>
          <Button variant="danger" onClick={() => reject(rec.id)}>
            Reject
          </Button>
        </Actions>
        
        <NotesInput placeholder="Optional notes..." />
      </ReviewCard>
    ))}
  </QueueList>
</ReviewQueue>
```

### Shoe Management

```tsx
<ShoeEditor shoe={shoe}>
  <Tabs>
    <Tab label="Basic Info">
      <Form>
        <BrandSelect />
        <Input name="name" label="Model Name" />
        <Input name="version" label="Version/Year" />
        <CategorySelect />
        <PriceInputs />
        <ImageUpload />
      </Form>
    </Tab>
    
    <Tab label="Specifications">
      {/* Dynamic based on category */}
      {shoe.category === 'running' ? (
        <RunningSpecsForm />
      ) : (
        <BasketballSpecsForm />
      )}
    </Tab>
    
    <Tab label="Fit Profile">
      <FitProfileForm>
        {/* AI-extracted values with manual override */}
        <FieldWithSource 
          name="size_runs"
          aiValue={shoe.fit_profile.size_runs}
          onOverride={handleOverride}
        />
        {/* ... more fields */}
      </FitProfileForm>
      
      <ReviewsPreview reviews={shoe.reviews.slice(0, 5)} />
      
      <Button onClick={() => triggerScrape(shoe.id)}>
        Re-scrape Reviews
      </Button>
    </Tab>
    
    <Tab label="Affiliate Links">
      <AffiliateLinksEditor links={shoe.affiliate_links} />
    </Tab>
  </Tabs>
</ShoeEditor>
```

---

## Scraper System

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Scraper Orchestrator                     │
│                        (Celery Beat)                         │
└─────────────────────────────┬───────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                       Job Queue (Redis)                      │
└───────────┬─────────────────┬─────────────────┬─────────────┘
            │                 │                 │
            ▼                 ▼                 ▼
    ┌───────────────┐ ┌───────────────┐ ┌───────────────┐
    │    Worker 1   │ │    Worker 2   │ │    Worker 3   │
    │               │ │               │ │               │
    │  - Scrape     │ │  - Scrape     │ │  - AI Parse   │
    │  - Parse HTML │ │  - Parse HTML │ │  - Extract    │
    │  - Store raw  │ │  - Store raw  │ │  - Update DB  │
    └───────────────┘ └───────────────┘ └───────────────┘
```

### Supported Sources

```python
SCRAPER_SOURCES = {
    'running': {
        'running_warehouse': {
            'base_url': 'https://www.runningwarehouse.com',
            'reviews_pattern': '/reviews/{product_id}',
            'selectors': {
                'review_container': '.review-item',
                'rating': '.rating-stars',
                'title': '.review-title',
                'body': '.review-body',
                'reviewer_stats': '.reviewer-info',
            }
        },
        'fleet_feet': {
            'base_url': 'https://www.fleetfeet.com',
            # ...
        },
        'road_runner_sports': {
            # ...
        },
        'doctors_of_running': {
            'type': 'expert_review',
            # ...
        },
        'believe_in_the_run': {
            'type': 'expert_review',
            # ...
        },
    },
    'basketball': {
        'foot_locker': {
            # ...
        },
        'eastbay': {
            # ...
        },
        'weartesters': {
            'type': 'expert_review',
            # ...
        },
    }
}
```

### Scraper Implementation

```python
# scrapers/base.py

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional
import httpx
from bs4 import BeautifulSoup


@dataclass
class RawReview:
    source: str
    source_review_id: str
    source_url: str
    reviewer_name: Optional[str]
    rating: Optional[float]
    title: Optional[str]
    body: str
    review_date: Optional[str]
    reviewer_foot_width: Optional[str]
    reviewer_arch_type: Optional[str]
    reviewer_size_purchased: Optional[str]
    reviewer_typical_size: Optional[str]


class BaseScraper(ABC):
    """Base class for all review scrapers."""
    
    def __init__(self, config: dict):
        self.config = config
        self.client = httpx.Client(
            headers={
                'User-Agent': 'Mozilla/5.0 (compatible; ShoeMatcherBot/1.0)'
            },
            timeout=30.0
        )
    
    @abstractmethod
    def get_product_url(self, shoe: 'Shoe') -> Optional[str]:
        """Find the product page URL for a given shoe."""
        pass
    
    @abstractmethod
    def scrape_reviews(self, product_url: str) -> List[RawReview]:
        """Scrape all reviews from a product page."""
        pass
    
    def scrape_shoe(self, shoe: 'Shoe') -> List[RawReview]:
        """Main entry point: find product and scrape reviews."""
        url = self.get_product_url(shoe)
        if not url:
            return []
        return self.scrape_reviews(url)


# scrapers/running_warehouse.py

class RunningWarehouseScraper(BaseScraper):
    
    def get_product_url(self, shoe: 'Shoe') -> Optional[str]:
        # Search for the shoe
        search_url = f"{self.config['base_url']}/searchresults.html"
        query = f"{shoe.brand.name} {shoe.name}"
        
        response = self.client.get(search_url, params={'searchtext': query})
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find matching product
        results = soup.select('.product-card')
        for result in results:
            title = result.select_one('.product-name').text.lower()
            if shoe.name.lower() in title:
                return result.select_one('a')['href']
        
        return None
    
    def scrape_reviews(self, product_url: str) -> List[RawReview]:
        reviews = []
        page = 1
        
        while True:
            response = self.client.get(f"{product_url}/reviews", params={'page': page})
            soup = BeautifulSoup(response.text, 'html.parser')
            
            review_elements = soup.select(self.config['selectors']['review_container'])
            if not review_elements:
                break
            
            for elem in review_elements:
                review = self._parse_review_element(elem, product_url)
                if review:
                    reviews.append(review)
            
            page += 1
            if page > 50:  # Safety limit
                break
        
        return reviews
    
    def _parse_review_element(self, elem, source_url: str) -> Optional[RawReview]:
        try:
            # Extract reviewer stats if available
            stats = elem.select_one('.reviewer-info')
            
            return RawReview(
                source='running_warehouse',
                source_review_id=elem.get('data-review-id', ''),
                source_url=source_url,
                reviewer_name=self._safe_text(elem, '.reviewer-name'),
                rating=self._parse_rating(elem),
                title=self._safe_text(elem, self.config['selectors']['title']),
                body=self._safe_text(elem, self.config['selectors']['body']),
                review_date=self._safe_text(elem, '.review-date'),
                reviewer_foot_width=self._extract_stat(stats, 'width'),
                reviewer_arch_type=self._extract_stat(stats, 'arch'),
                reviewer_size_purchased=self._extract_stat(stats, 'size'),
                reviewer_typical_size=self._extract_stat(stats, 'usual_size'),
            )
        except Exception as e:
            logger.error(f"Failed to parse review: {e}")
            return None
```

### AI Review Parser

```python
# scrapers/ai_parser.py

from anthropic import Anthropic


class ReviewFitExtractor:
    """Extract structured fit data from raw reviews using Claude."""
    
    EXTRACTION_PROMPT = """
    Analyze these shoe reviews and extract structured fit information.
    
    Reviews:
    {reviews_text}
    
    Extract the following (respond with JSON only):
    {{
        "size_runs": "small" | "true" | "large",
        "size_offset": float (-1.0 to +1.0, e.g., 0.5 means runs half size large),
        "width_runs": "narrow" | "true" | "wide",
        "toe_box_room": "cramped" | "snug" | "roomy" | "spacious",
        "heel_fit": "loose" | "secure" | "tight",
        "arch_support": "flat" | "neutral" | "high",
        "break_in_period": "none" | "short" | "moderate" | "long",
        "break_in_miles": int or null,
        "durability_rating": "poor" | "average" | "good" | "excellent",
        "expected_miles_min": int,
        "expected_miles_max": int,
        "common_complaints": [list of strings],
        "works_well_for": [list: "wide_feet", "narrow_feet", "high_arches", "flat_feet", "plantar_fasciitis", etc.],
        "avoid_if": [list of conditions this shoe is bad for],
        "overall_sentiment": float (0.0 to 1.0)
    }}
    
    Base your analysis on consensus across reviews. If information isn't available, use null.
    """
    
    def __init__(self):
        self.client = Anthropic()
    
    def extract_fit_profile(self, reviews: List[RawReview]) -> dict:
        # Prepare reviews text (limit to avoid context issues)
        reviews_text = "\n\n---\n\n".join([
            f"Rating: {r.rating}/5\n"
            f"Reviewer width: {r.reviewer_foot_width or 'unknown'}\n"
            f"Reviewer arch: {r.reviewer_arch_type or 'unknown'}\n"
            f"Size purchased: {r.reviewer_size_purchased or 'unknown'}\n"
            f"Review: {r.body[:500]}"  # Truncate long reviews
            for r in reviews[:30]  # Limit number of reviews
        ])
        
        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            messages=[{
                "role": "user",
                "content": self.EXTRACTION_PROMPT.format(reviews_text=reviews_text)
            }]
        )
        
        # Parse JSON response
        import json
        result = json.loads(response.content[0].text)
        result['review_count'] = len(reviews)
        result['extraction_model'] = 'claude-sonnet-4-20250514'
        
        return result
```

### Celery Tasks

```python
# tasks/scraper_tasks.py

from celery import Celery
from scrapers import get_scraper_for_source
from scrapers.ai_parser import ReviewFitExtractor


app = Celery('scraper')


@app.task(bind=True, max_retries=3)
def scrape_shoe_reviews(self, shoe_id: str, sources: List[str] = None):
    """Scrape reviews for a single shoe from specified sources."""
    
    shoe = get_shoe(shoe_id)
    sources = sources or get_default_sources(shoe.category)
    
    all_reviews = []
    
    for source in sources:
        try:
            scraper = get_scraper_for_source(source)
            reviews = scraper.scrape_shoe(shoe)
            all_reviews.extend(reviews)
            
            # Store raw reviews
            store_reviews(shoe_id, reviews)
            
        except Exception as e:
            logger.error(f"Scrape failed for {source}: {e}")
            continue
    
    # Trigger AI extraction
    extract_fit_profile.delay(shoe_id)
    
    return {'shoe_id': shoe_id, 'reviews_scraped': len(all_reviews)}


@app.task
def extract_fit_profile(shoe_id: str):
    """Extract fit profile from stored reviews using AI."""
    
    reviews = get_reviews_for_shoe(shoe_id)
    if not reviews:
        return
    
    extractor = ReviewFitExtractor()
    fit_profile = extractor.extract_fit_profile(reviews)
    
    # Store with needs_review flag
    update_fit_profile(shoe_id, fit_profile, needs_review=True)
    
    return {'shoe_id': shoe_id, 'profile_extracted': True}


@app.task
def scrape_category(category_id: str):
    """Scrape all shoes in a category."""
    
    shoes = get_shoes_by_category(category_id)
    
    for shoe in shoes:
        scrape_shoe_reviews.delay(shoe.id)


# Scheduled tasks
@app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    # Re-scrape all shoes weekly
    sender.add_periodic_task(
        crontab(hour=2, minute=0, day_of_week=0),  # Sunday 2am
        scrape_all_shoes.s(),
    )
    
    # Check for new shoe releases daily
    sender.add_periodic_task(
        crontab(hour=3, minute=0),  # Daily 3am
        check_new_releases.s(),
    )
```

---

## RLHF Training Loop

### Data Flow

```
Admin Reviews Recommendation
            │
            ▼
    ┌───────────────┐
    │  Approved?    │──Yes──▶ Store as positive example
    └───────┬───────┘
            │ No
            ▼
    ┌───────────────┐
    │  Adjusted?    │──Yes──▶ Store correction as training data
    └───────┬───────┘
            │ No (Rejected)
            ▼
    Store as negative example (lower weight)


Training Examples Accumulate
            │
            ▼
    ┌───────────────────────────┐
    │  Periodic Weight Update   │
    │  (when N > threshold)     │
    └───────────────┬───────────┘
                    │
                    ▼
    ┌───────────────────────────┐
    │  Evaluate on held-out set │
    │  Update if improved       │
    └───────────────────────────┘
```

### Training Data Structure

```python
@dataclass
class TrainingExample:
    quiz_answers: dict
    category: str
    
    # The "correct" ranking (from admin)
    ideal_ranking: List[str]  # shoe_ids in order
    
    # What the algorithm originally produced
    original_ranking: List[str]
    
    # Quality signals
    source: str  # 'admin_approval', 'admin_correction', 'user_purchase'
    confidence: float  # How confident we are this is correct
    
    # Optional: specific feedback
    feedback: Optional[dict]  # e.g., {"shoe_x_should_beat_shoe_y": true}
```

### Weight Update Algorithm

```python
class WeightOptimizer:
    """
    Simple gradient-free optimization for matching weights.
    
    Approach: Compare algorithm rankings to admin rankings,
    identify which factors are under/over-weighted.
    """
    
    def __init__(self, current_weights: dict):
        self.weights = current_weights.copy()
        self.learning_rate = 0.1
    
    def update_from_examples(self, examples: List[TrainingExample]):
        """
        Update weights based on admin corrections.
        """
        adjustments = defaultdict(list)
        
        for example in examples:
            if example.source == 'admin_correction':
                # Analyze what changed
                original = example.original_ranking
                ideal = example.ideal_ranking
                
                # Find shoes that moved up (admin preferred them more)
                for i, shoe_id in enumerate(ideal):
                    original_rank = original.index(shoe_id) if shoe_id in original else 999
                    rank_delta = original_rank - i  # positive = moved up
                    
                    if rank_delta > 0:
                        # This shoe was under-ranked. Why?
                        shoe = get_shoe(shoe_id)
                        user_profile = example.quiz_answers
                        
                        # Check which factors this shoe scores well on
                        factor_scores = calculate_factor_scores(shoe, user_profile)
                        
                        for factor, score in factor_scores.items():
                            if score > 0.7:  # Shoe is good on this factor
                                # Factor may be under-weighted
                                adjustments[factor].append(rank_delta * 0.1)
        
        # Apply adjustments
        for factor, deltas in adjustments.items():
            avg_delta = sum(deltas) / len(deltas)
            self.weights[factor] += avg_delta * self.learning_rate
            # Clamp to reasonable range
            self.weights[factor] = max(0.1, min(3.0, self.weights[factor]))
        
        return self.weights
    
    def evaluate(self, held_out: List[TrainingExample]) -> float:
        """
        Evaluate current weights on held-out examples.
        Returns NDCG or similar ranking metric.
        """
        scores = []
        
        for example in held_out:
            predicted = generate_ranking(example.quiz_answers, self.weights)
            ideal = example.ideal_ranking
            
            ndcg = calculate_ndcg(predicted, ideal)
            scores.append(ndcg)
        
        return sum(scores) / len(scores)
```

### Admin Training Interface

```tsx
<TrainingDashboard>
  {/* Stats */}
  <StatsCard>
    <Stat label="Training examples" value={stats.total_examples} />
    <Stat label="Approved" value={stats.approved} />
    <Stat label="Corrected" value={stats.corrected} />
    <Stat label="Last weight update" value={stats.last_update} />
  </StatsCard>
  
  {/* Weight visualization */}
  <WeightsChart weights={currentWeights} />
  
  {/* Manual weight tweaks */}
  <WeightEditor>
    {Object.entries(currentWeights).map(([factor, weight]) => (
      <WeightSlider
        key={factor}
        label={factor}
        value={weight}
        min={0.1}
        max={3.0}
        onChange={(v) => updateWeight(factor, v)}
      />
    ))}
    <Button onClick={saveWeights}>Save Weights</Button>
    <Button onClick={resetToDefault}>Reset to Default</Button>
  </WeightEditor>
  
  {/* Trigger retraining */}
  <RetrainSection>
    <p>{pendingExamples} new examples since last training</p>
    <Button 
      onClick={triggerRetrain}
      disabled={pendingExamples < 50}
    >
      Retrain Model
    </Button>
  </RetrainSection>
</TrainingDashboard>
```

---

## Deployment

### Environment Variables

```bash
# .env.example

# Database
DATABASE_URL=postgresql://user:pass@host:5432/shoematcher
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_ANON_KEY=xxx
SUPABASE_SERVICE_KEY=xxx

# Redis
REDIS_URL=redis://localhost:6379

# AI
ANTHROPIC_API_KEY=sk-ant-xxx

# Auth
JWT_SECRET=xxx
ADMIN_EMAIL=admin@shoematcher.com

# Affiliate
AMAZON_AFFILIATE_TAG=shoematcher-20
RUNNING_WAREHOUSE_AFFILIATE_ID=xxx

# Environment
ENVIRONMENT=development  # development, staging, production
```

### Docker Compose (Development)

```yaml
# docker-compose.yml

version: '3.8'

services:
  db:
    image: postgres:15
    environment:
      POSTGRES_DB: shoematcher
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7
    ports:
      - "6379:6379"

  api:
    build: ./backend
    command: uvicorn main:app --reload --host 0.0.0.0 --port 8000
    volumes:
      - ./backend:/app
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://postgres:postgres@db:5432/shoematcher
      - REDIS_URL=redis://redis:6379
    depends_on:
      - db
      - redis

  worker:
    build: ./backend
    command: celery -A tasks worker --loglevel=info
    volumes:
      - ./backend:/app
    environment:
      - DATABASE_URL=postgresql://postgres:postgres@db:5432/shoematcher
      - REDIS_URL=redis://redis:6379
    depends_on:
      - db
      - redis

  frontend:
    build: ./frontend
    command: npm run dev
    volumes:
      - ./frontend:/app
      - /app/node_modules
    ports:
      - "3000:3000"
    environment:
      - NEXT_PUBLIC_API_URL=http://localhost:8000

volumes:
  postgres_data:
```

### Production Deployment

```
Frontend (Vercel)
├── Auto-deploy from main branch
├── Preview deployments for PRs
└── Environment: NEXT_PUBLIC_API_URL

Backend (Railway)
├── FastAPI service
├── Celery worker service
└── Environment variables from Railway dashboard

Database (Supabase)
├── PostgreSQL
├── Row-level security policies
└── Automatic backups

Redis (Upstash)
├── Serverless Redis
└── Free tier sufficient for initial scale
```

---

## Future Considerations

### V2 Features

1. **Foot scan upload**
   - Parse PDF/image scans from Fleet Feet, Road Runner, etc.
   - Extract: length, width, arch height, pressure map
   - Map to internal foot profile format

2. **Chat layer**
   - Post-recommendation questions
   - "Why not Hokas?" / "Compare #1 and #3"
   - RAG over shoe database + reviews

3. **User accounts**
   - Save recommendations
   - Track purchases
   - Build purchase history for better recs

4. **Expand categories**
   - Trail running (more granular)
   - Walking shoes
   - Tennis / Pickleball
   - Soccer cleats
   - Hiking boots

### Scaling Considerations

1. **Database**
   - Supabase handles initial scale well
   - If >100k daily quizzes: consider read replicas
   - Shoe data is relatively static → aggressive caching

2. **Scraping**
   - Respect rate limits
   - Use proxy rotation if needed
   - Consider official APIs where available (some retailers have them)

3. **AI costs**
   - Claude API for review parsing is the main cost
   - Batch processing reduces per-call overhead
   - Cache extracted fit profiles (only re-run on new reviews)

---

## Appendix: Quiz Questions

### Running Shoe Quiz

```typescript
const RUNNING_QUESTIONS: Question[] = [
  {
    id: 'terrain',
    type: 'single_select',
    question: 'What type of surface do you primarily run on?',
    options: [
      { value: 'road', label: 'Road / Pavement', icon: 'road' },
      { value: 'trail', label: 'Trail / Off-road', icon: 'mountain' },
      { value: 'track', label: 'Track', icon: 'track' },
      { value: 'treadmill', label: 'Treadmill', icon: 'treadmill' },
      { value: 'mixed', label: 'Mixed surfaces', icon: 'mixed' },
    ],
  },
  {
    id: 'distance',
    type: 'single_select',
    question: 'What distances do you typically run?',
    options: [
      { value: 'short', label: 'Short runs (under 5K)' },
      { value: 'mid', label: 'Mid distance (5K - Half Marathon)' },
      { value: 'long', label: 'Long distance (Marathon+)' },
      { value: 'mixed', label: 'Mixed / Varies' },
    ],
  },
  {
    id: 'experience',
    type: 'single_select',
    question: 'How would you describe your running experience?',
    options: [
      { value: 'beginner', label: 'New to running (< 1 year)' },
      { value: 'recreational', label: 'Recreational (1-3 years)' },
      { value: 'experienced', label: 'Experienced (3+ years)' },
      { value: 'competitive', label: 'Competitive / Racing' },
    ],
  },
  {
    id: 'foot_issues',
    type: 'multi_select',
    question: 'Do you have any of these foot characteristics or issues?',
    hint: 'Select all that apply',
    options: [
      { value: 'overpronation', label: 'Overpronation (feet roll inward)' },
      { value: 'underpronation', label: 'Underpronation / Supination (feet roll outward)' },
      { value: 'flat_feet', label: 'Flat feet / Low arches' },
      { value: 'high_arches', label: 'High arches' },
      { value: 'wide_feet', label: 'Wide feet' },
      { value: 'narrow_feet', label: 'Narrow feet' },
      { value: 'plantar_fasciitis', label: 'Plantar fasciitis' },
      { value: 'bunions', label: 'Bunions' },
      { value: 'none', label: 'None of these', exclusive: true },
    ],
  },
  {
    id: 'priorities',
    type: 'rank',
    question: 'What matters most to you in a running shoe?',
    hint: 'Drag to rank in order of importance',
    options: [
      { value: 'cushion', label: 'Cushioning & Comfort' },
      { value: 'speed', label: 'Speed & Responsiveness' },
      { value: 'stability', label: 'Stability & Support' },
      { value: 'durability', label: 'Durability' },
      { value: 'price', label: 'Price / Value' },
    ],
    maxRank: 3,
  },
  {
    id: 'budget',
    type: 'single_select',
    question: "What's your budget?",
    options: [
      { value: 'under_100', label: 'Under $100' },
      { value: '100_150', label: '$100 - $150' },
      { value: '150_200', label: '$150 - $200' },
      { value: 'any', label: 'Whatever it takes' },
    ],
  },
  {
    id: 'previous_shoes',
    type: 'shoe_history',
    question: 'Have you worn any running shoes you loved or hated?',
    hint: 'Optional but helps us dial in recommendations',
    optional: true,
  },
];
```

### Basketball Shoe Quiz

```typescript
const BASKETBALL_QUESTIONS: Question[] = [
  {
    id: 'position',
    type: 'single_select',
    question: 'What position do you play / what\'s your play style?',
    options: [
      { value: 'guard', label: 'Guard - Quick cuts, speed, agility' },
      { value: 'wing', label: 'Wing - All-around, versatile' },
      { value: 'big', label: 'Big - Post play, physicality, rebounding' },
    ],
  },
  {
    id: 'court_type',
    type: 'single_select',
    question: 'Where do you play most often?',
    options: [
      { value: 'indoor', label: 'Indoor (gym/hardwood)' },
      { value: 'outdoor', label: 'Outdoor (concrete/asphalt)' },
      { value: 'both', label: 'Both equally' },
    ],
  },
  {
    id: 'priorities',
    type: 'multi_select',
    question: 'What matters most to you?',
    hint: 'Select up to 2',
    maxSelect: 2,
    options: [
      { value: 'traction', label: 'Traction / Grip' },
      { value: 'cushion', label: 'Cushioning / Impact protection' },
      { value: 'court_feel', label: 'Court feel / Responsiveness' },
      { value: 'support', label: 'Ankle support / Lockdown' },
      { value: 'durability', label: 'Durability (especially outdoor)' },
    ],
  },
  {
    id: 'cut_preference',
    type: 'single_select',
    question: 'Do you have a cut preference?',
    options: [
      { value: 'low', label: 'Low - Maximum mobility' },
      { value: 'mid', label: 'Mid - Balance of support and mobility' },
      { value: 'high', label: 'High - Maximum ankle support' },
      { value: 'no_preference', label: 'No preference' },
    ],
  },
  {
    id: 'foot_issues',
    type: 'multi_select',
    question: 'Any foot concerns?',
    hint: 'Select all that apply',
    options: [
      { value: 'wide_feet', label: 'Wide feet' },
      { value: 'narrow_feet', label: 'Narrow feet' },
      { value: 'ankle_history', label: 'History of ankle injuries' },
      { value: 'knee_issues', label: 'Knee issues' },
      { value: 'none', label: 'None', exclusive: true },
    ],
  },
  {
    id: 'budget',
    type: 'single_select',
    question: "What's your budget?",
    options: [
      { value: 'under_100', label: 'Under $100' },
      { value: '100_150', label: '$100 - $150' },
      { value: '150_plus', label: '$150+' },
    ],
  },
  {
    id: 'previous_shoes',
    type: 'shoe_history',
    question: 'Any basketball shoes you\'ve loved or hated?',
    optional: true,
  },
];
```

---

*End of Technical Specification*
