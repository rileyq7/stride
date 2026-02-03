# Scraper Data Schema & AI Integration Guide

## Overview

This document describes the data structures produced by the scrapers and how to best store/query them for:
1. UI display
2. Shoe matching algorithms
3. AI/Chatbot integration (ChatGPT, Claude, etc.)

---

## 1. Raw Scraper Outputs

### Brand Scraper Output (`ProductSpecs`)

```python
@dataclass
class ProductSpecs:
    # Identifiers
    brand: str                    # "Nike", "Hoka", etc.
    name: str                     # "Pegasus 41"
    style_id: str                 # "FD2722-002"
    colorway: str                 # "Black/White"

    # Pricing
    msrp: Decimal                 # 140.00
    current_price: Decimal        # 119.99

    # Physical specs
    weight_oz: Decimal            # 9.8
    weight_g: Decimal             # 278
    stack_height_heel_mm: Decimal # 33
    stack_height_forefoot_mm: Decimal  # 23
    drop_mm: Decimal              # 10

    # Features
    cushion_type: str             # "ZoomX", "DNA Loft", "Fresh Foam"
    cushion_level: str            # "minimal", "moderate", "max"
    has_carbon_plate: bool        # True/False
    has_rocker: bool              # True/False
    terrain: str                  # "road", "trail", "track"
    subcategory: str              # "neutral", "stability", "racing"

    # Media
    primary_image_url: str
    image_urls: List[str]

    # Availability
    width_options: List[str]      # ["D", "2E", "4E"]
    available_sizes: List[str]    # ["8", "8.5", "9", ...]
```

### Review Scraper Output (`RawReview`)

```python
@dataclass
class RawReview:
    # Source tracking
    source: str                   # "doctors_of_running", "running_warehouse"
    source_review_id: str         # Unique ID from source
    source_url: str               # Original URL

    # Content
    reviewer_name: str            # "Matt Klein PT DPT"
    rating: float                 # 4.5 (if available)
    title: str                    # "Great daily trainer"
    body: str                     # Full review text (can be 20k+ chars)
    review_date: str              # "2024-12-15"

    # Review type
    review_type: str              # "user" or "expert"
    expert_credentials: str       # "PT DPT PhD OCS"
    miles_tested: int             # 150

    # Structured scores (some sources)
    form_score: float             # 4/5
    fit_score: float              # 3/5
    function_score: float         # 5/5
    overall_score: float          # 12/15

    # Reviewer context
    reviewer_foot_width: str      # "wide", "narrow", "normal"
    reviewer_arch_type: str       # "high", "flat", "neutral"
    reviewer_size_purchased: str  # "10.5"
    reviewer_typical_size: str    # "10"

    # AI-extracted recommendations
    sizing_recommendation: str    # "true_to_size", "size_up", "size_down"
    width_recommendation: str     # "narrow", "normal", "wide"
```

---

## 2. Recommended PostgreSQL Schema

### Core Tables (Already Exist)

Your existing schema is good. Here's the enhanced version with JSONB for AI-friendly querying:

```sql
-- Enhanced Shoe table with JSONB for flexible data
ALTER TABLE shoes ADD COLUMN IF NOT EXISTS
    ai_summary JSONB DEFAULT '{}';

-- AI-friendly summary structure:
-- {
--   "one_liner": "Max-cushioned neutral trainer for long easy runs",
--   "best_for": ["long runs", "recovery", "high mileage"],
--   "avoid_if": ["speed work", "racing", "narrow feet"],
--   "similar_to": ["Hoka Bondi", "ASICS Nimbus"],
--   "key_features": ["ZoomX foam", "10mm drop", "breathable mesh"],
--   "fit_notes": "Runs true to size, slightly narrow in midfoot",
--   "durability": "300-400 miles typical",
--   "price_value": "good"
-- }
```

### New: Unified Shoe Profile Table (For AI/Matching)

```sql
CREATE TABLE shoe_profiles (
    shoe_id UUID PRIMARY KEY REFERENCES shoes(id) ON DELETE CASCADE,

    -- Normalized numeric specs (for matching algorithms)
    weight_normalized DECIMAL(3,2),      -- 0-1 scale (0=lightest, 1=heaviest)
    cushion_normalized DECIMAL(3,2),     -- 0-1 scale
    stability_normalized DECIMAL(3,2),   -- 0-1 scale
    responsiveness_normalized DECIMAL(3,2), -- 0-1 scale
    flexibility_normalized DECIMAL(3,2), -- 0-1 scale

    -- Fit vector (for matching)
    fit_vector JSONB NOT NULL DEFAULT '{
        "length": 0,
        "width_forefoot": 0,
        "width_midfoot": 0,
        "width_heel": 0,
        "arch_height": 0,
        "volume": 0
    }',
    -- Values: -1 (runs small/narrow), 0 (true), +1 (runs large/wide)

    -- Use case scores (0-1)
    use_case_scores JSONB NOT NULL DEFAULT '{
        "easy_runs": 0.5,
        "long_runs": 0.5,
        "tempo": 0.5,
        "intervals": 0.5,
        "racing": 0.5,
        "walking": 0.5,
        "standing": 0.5
    }',

    -- Terrain scores (0-1)
    terrain_scores JSONB NOT NULL DEFAULT '{
        "road": 1.0,
        "light_trail": 0.0,
        "technical_trail": 0.0,
        "track": 0.0
    }',

    -- AI-generated embeddings for semantic search
    embedding VECTOR(1536),  -- OpenAI ada-002 or similar

    -- Full text search
    search_text TEXT,  -- Concatenated searchable text

    -- Metadata
    confidence_score DECIMAL(3,2),  -- How confident are we in this data
    review_count INT DEFAULT 0,
    last_analyzed_at TIMESTAMP,

    CONSTRAINT valid_scores CHECK (
        weight_normalized BETWEEN 0 AND 1 AND
        cushion_normalized BETWEEN 0 AND 1
    )
);

-- Index for vector similarity search (requires pgvector extension)
CREATE INDEX idx_shoe_profiles_embedding ON shoe_profiles
    USING ivfflat (embedding vector_cosine_ops);

-- GIN index for JSONB queries
CREATE INDEX idx_shoe_profiles_fit ON shoe_profiles USING GIN (fit_vector);
CREATE INDEX idx_shoe_profiles_use_case ON shoe_profiles USING GIN (use_case_scores);
```

### New: Review Summaries Table (AI-Extracted)

```sql
CREATE TABLE review_summaries (
    shoe_id UUID PRIMARY KEY REFERENCES shoes(id) ON DELETE CASCADE,

    -- Aggregated from all reviews
    total_reviews INT DEFAULT 0,
    expert_reviews INT DEFAULT 0,
    user_reviews INT DEFAULT 0,
    average_rating DECIMAL(2,1),

    -- Consensus data (extracted by AI)
    consensus JSONB NOT NULL DEFAULT '{
        "sizing": {
            "verdict": "true_to_size",
            "confidence": 0.85,
            "notes": "Most reviewers agree TTS, some wide-footers size up"
        },
        "width": {
            "forefoot": "normal",
            "midfoot": "slightly_narrow",
            "heel": "normal"
        },
        "comfort": {
            "break_in_miles": 10,
            "all_day_wearable": true
        },
        "durability": {
            "expected_miles_min": 300,
            "expected_miles_max": 500,
            "weak_points": ["outsole wear on lateral edge"]
        }
    }',

    -- Sentiment analysis
    sentiment JSONB NOT NULL DEFAULT '{
        "overall": 0.82,
        "fit": 0.75,
        "comfort": 0.90,
        "durability": 0.70,
        "value": 0.65
    }',

    -- Common themes (for UI display)
    pros JSONB DEFAULT '[]',   -- ["great cushioning", "lightweight", "breathable"]
    cons JSONB DEFAULT '[]',   -- ["durability concerns", "narrow toe box"]

    -- For specific foot types
    recommendations JSONB DEFAULT '{
        "wide_feet": {"suitable": false, "notes": "Consider wide version"},
        "narrow_feet": {"suitable": true, "notes": "Good fit"},
        "high_arches": {"suitable": true, "notes": "Adequate support"},
        "flat_feet": {"suitable": false, "notes": "Needs more stability"},
        "overpronators": {"suitable": false, "notes": "Try stability version"}
    }',

    -- Key quotes from reviews
    notable_quotes JSONB DEFAULT '[]',
    -- [{"quote": "...", "source": "doctors_of_running", "reviewer": "Matt Klein"}]

    updated_at TIMESTAMP DEFAULT NOW()
);
```

---

## 3. AI/Chatbot Integration

### Option A: Direct Database Query (for RAG)

```sql
-- Query to get shoe data for chatbot context
SELECT
    s.name,
    b.name as brand,
    s.msrp_usd,
    ra.weight_oz,
    ra.drop_mm,
    ra.cushion_type,
    ra.cushion_level,
    ra.subcategory,
    sp.fit_vector,
    sp.use_case_scores,
    rs.consensus,
    rs.pros,
    rs.cons,
    rs.recommendations
FROM shoes s
JOIN brands b ON s.brand_id = b.id
LEFT JOIN running_shoe_attributes ra ON s.id = ra.shoe_id
LEFT JOIN shoe_profiles sp ON s.id = sp.shoe_id
LEFT JOIN review_summaries rs ON s.id = rs.shoe_id
WHERE s.is_active = true
  AND s.name ILIKE '%pegasus%';
```

### Option B: Semantic Search (Vector Similarity)

```sql
-- Find shoes similar to a description
SELECT s.name, b.name as brand,
       1 - (sp.embedding <=> $1) as similarity
FROM shoe_profiles sp
JOIN shoes s ON sp.shoe_id = s.id
JOIN brands b ON s.brand_id = b.id
WHERE s.is_active = true
ORDER BY sp.embedding <=> $1  -- $1 is embedding of user query
LIMIT 5;
```

### Option C: Export for Fine-Tuning

```python
def export_for_chatbot():
    """Export shoe data in chatbot-friendly format."""
    return {
        "shoe_id": "uuid",
        "name": "Nike Pegasus 41",
        "brand": "Nike",

        # Structured for easy Q&A
        "facts": {
            "price": "$140",
            "weight": "9.8 oz",
            "drop": "10mm",
            "cushion": "ZoomX foam, max cushion level",
            "category": "Neutral road running shoe",
            "best_for": "Daily training, long runs, easy pace",
        },

        # Natural language summary
        "summary": """
        The Nike Pegasus 41 is a versatile neutral daily trainer with
        ZoomX foam cushioning. At 9.8 oz with a 10mm drop, it's suitable
        for easy to moderate paces. Runs true to size with a slightly
        narrow midfoot. Best for: daily training, long runs. Expected
        durability: 300-400 miles.
        """,

        # For Q&A training
        "qa_pairs": [
            {"q": "Is the Pegasus 41 good for wide feet?",
             "a": "The standard width may feel snug. Consider the wide (2E) version."},
            {"q": "How does it compare to the Pegasus 40?",
             "a": "The 41 has updated ZoomX foam and a slightly wider toe box."},
        ]
    }
```

---

## 4. UI Display Format

### Shoe Card Component Data

```typescript
interface ShoeCardData {
  id: string;
  name: string;
  brand: string;
  primaryImage: string;
  price: {
    msrp: number;
    current: number;
    onSale: boolean;
  };
  specs: {
    weight: string;      // "9.8 oz"
    drop: string;        // "10mm"
    cushion: string;     // "Max"
    category: string;    // "Neutral"
  };
  rating: {
    overall: number;     // 4.5
    reviewCount: number; // 127
  };
  badges: string[];      // ["Best Seller", "Editor's Pick"]
  matchScore?: number;   // 0-100 if from matching
}
```

### Detailed Shoe Page Data

```typescript
interface ShoeDetailData {
  // Basic info
  id: string;
  name: string;
  brand: BrandInfo;
  images: string[];
  price: PriceInfo;

  // Specs
  specs: {
    weight: { value: number; unit: "oz" | "g"; percentile: number };
    stackHeight: { heel: number; forefoot: number };
    drop: number;
    cushionType: string;
    cushionLevel: "minimal" | "moderate" | "max";
    hasCarbonPlate: boolean;
    hasRocker: boolean;
  };

  // Fit profile (from reviews)
  fit: {
    sizing: {
      verdict: "runs_small" | "true_to_size" | "runs_large";
      confidence: number;
      recommendation: string;
    };
    width: {
      forefoot: "narrow" | "normal" | "wide";
      midfoot: "narrow" | "normal" | "wide";
      heel: "narrow" | "normal" | "wide";
    };
    archSupport: "minimal" | "moderate" | "high";
    bestFor: FootType[];
  };

  // Review summary
  reviews: {
    total: number;
    averageRating: number;
    expertCount: number;
    pros: string[];
    cons: string[];
    notableQuotes: Quote[];
  };

  // Use cases
  useCases: {
    type: string;        // "Easy Runs"
    score: number;       // 0-100
    description: string; // "Excellent for recovery and easy pace"
  }[];

  // Similar shoes
  similar: ShoeCardData[];

  // Purchase links
  retailers: RetailerLink[];
}
```

---

## 5. Matching Algorithm Data

### User Profile Input

```typescript
interface UserProfile {
  // Foot measurements
  foot: {
    length: number;          // in cm or US size
    width: "narrow" | "normal" | "wide" | "extra_wide";
    archType: "flat" | "normal" | "high";
    volume: "low" | "normal" | "high";
  };

  // Running profile
  running: {
    weeklyMiles: number;
    primaryTerrain: "road" | "trail" | "mixed";
    paceRange: { min: string; max: string };  // "8:00" - "10:00"
    injuries: string[];      // ["plantar fasciitis", "knee pain"]
  };

  // Preferences
  preferences: {
    cushionLevel: "minimal" | "moderate" | "max";
    dropPreference: "low" | "moderate" | "high";
    stabilityNeed: "none" | "mild" | "moderate" | "max";
    budget: { min: number; max: number };
  };

  // Current/past shoes
  shoeHistory: {
    shoeId: string;
    rating: number;
    notes: string;
  }[];
}
```

### Matching Query

```sql
-- Find best matches for a user profile
WITH user_prefs AS (
    SELECT
        0.7 as target_cushion,      -- User wants max cushion
        0.3 as target_stability,    -- Mild stability
        0.5 as target_weight,       -- Medium weight OK
        'wide' as foot_width,
        150 as budget
)
SELECT
    s.id,
    s.name,
    b.name as brand,
    s.msrp_usd,

    -- Calculate match score
    (
        1 - ABS(sp.cushion_normalized - up.target_cushion) * 0.3 +
        1 - ABS(sp.stability_normalized - up.target_stability) * 0.2 +
        CASE WHEN (sp.fit_vector->>'width_forefoot')::int >= 0 THEN 0.2 ELSE 0 END +
        CASE WHEN s.msrp_usd <= up.budget THEN 0.1 ELSE 0 END +
        COALESCE((rs.recommendations->up.foot_width->>'suitable')::boolean::int * 0.2, 0)
    ) as match_score,

    rs.consensus->'sizing'->>'verdict' as sizing,
    rs.pros,
    rs.cons

FROM shoes s
JOIN brands b ON s.brand_id = b.id
JOIN shoe_profiles sp ON s.id = sp.shoe_id
LEFT JOIN review_summaries rs ON s.id = rs.shoe_id
CROSS JOIN user_prefs up
WHERE s.is_active = true
  AND s.msrp_usd <= up.budget * 1.2  -- Allow 20% over budget
ORDER BY match_score DESC
LIMIT 10;
```

---

## 6. Migration to Add New Tables

```sql
-- Run this migration to add AI-friendly tables

-- Enable pgvector for embeddings (if not already)
CREATE EXTENSION IF NOT EXISTS vector;

-- Create shoe_profiles table
CREATE TABLE IF NOT EXISTS shoe_profiles (
    shoe_id UUID PRIMARY KEY REFERENCES shoes(id) ON DELETE CASCADE,
    weight_normalized DECIMAL(3,2),
    cushion_normalized DECIMAL(3,2),
    stability_normalized DECIMAL(3,2),
    responsiveness_normalized DECIMAL(3,2),
    flexibility_normalized DECIMAL(3,2),
    fit_vector JSONB NOT NULL DEFAULT '{}',
    use_case_scores JSONB NOT NULL DEFAULT '{}',
    terrain_scores JSONB NOT NULL DEFAULT '{}',
    embedding VECTOR(1536),
    search_text TEXT,
    confidence_score DECIMAL(3,2),
    review_count INT DEFAULT 0,
    last_analyzed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Create review_summaries table
CREATE TABLE IF NOT EXISTS review_summaries (
    shoe_id UUID PRIMARY KEY REFERENCES shoes(id) ON DELETE CASCADE,
    total_reviews INT DEFAULT 0,
    expert_reviews INT DEFAULT 0,
    user_reviews INT DEFAULT 0,
    average_rating DECIMAL(2,1),
    consensus JSONB NOT NULL DEFAULT '{}',
    sentiment JSONB NOT NULL DEFAULT '{}',
    pros JSONB DEFAULT '[]',
    cons JSONB DEFAULT '[]',
    recommendations JSONB DEFAULT '{}',
    notable_quotes JSONB DEFAULT '[]',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Add AI summary column to shoes
ALTER TABLE shoes ADD COLUMN IF NOT EXISTS ai_summary JSONB DEFAULT '{}';

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_shoe_profiles_embedding
    ON shoe_profiles USING ivfflat (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_shoe_profiles_fit
    ON shoe_profiles USING GIN (fit_vector);
CREATE INDEX IF NOT EXISTS idx_review_summaries_consensus
    ON review_summaries USING GIN (consensus);
```

---

## 7. Example: Full Data Flow

```
1. SCRAPE
   Brand Site (Nike.com) → ProductSpecs
   Review Site (Doctors of Running) → RawReview[]

2. STORE
   ProductSpecs → shoes + running_shoe_attributes
   RawReview[] → shoe_reviews

3. ANALYZE (AI)
   shoe_reviews → review_summaries (consensus, pros/cons)
   shoes + attributes → shoe_profiles (normalized scores)

4. MATCH
   UserProfile + shoe_profiles → ranked recommendations

5. DISPLAY
   shoes + shoe_profiles + review_summaries → UI components

6. CHATBOT
   User query → embedding → vector search → context
   Context + LLM → natural language response
```
