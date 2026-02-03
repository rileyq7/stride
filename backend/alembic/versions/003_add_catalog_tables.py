"""Add 3-layer catalog tables (models, products, offers)

Revision ID: 003_add_catalog_tables
Revises: 002_add_ai_tables
Create Date: 2026-02-02

This migration adds the new 3-layer catalog data model:
- shoe_models: Conceptual shoe models (e.g., "Pegasus")
- shoe_products: Specific versions/colorways (e.g., "Pegasus 41 Blue")
- shoe_offers: Merchant listings with prices
- discovered_urls: URL discovery tracking
- merchants: Retailer configuration
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY


# revision identifiers, used by Alembic.
revision = '003_add_catalog_tables'
down_revision = '002_add_ai_tables'
branch_labels = None
depends_on = None


def upgrade():
    # Create enum types using raw SQL with IF NOT EXISTS logic
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'gender') THEN
                CREATE TYPE gender AS ENUM ('mens', 'womens', 'unisex', 'kids');
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'terrain') THEN
                CREATE TYPE terrain AS ENUM ('road', 'trail', 'track', 'hybrid');
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'support_type') THEN
                CREATE TYPE support_type AS ENUM ('neutral', 'stability', 'motion_control');
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'shoe_category') THEN
                CREATE TYPE shoe_category AS ENUM ('daily_trainer', 'racing', 'tempo', 'long_run', 'recovery', 'trail', 'track_spike');
            END IF;
        END
        $$;
    """)

    # Create shoe_models table using raw SQL to avoid enum auto-creation
    op.execute("""
        CREATE TABLE shoe_models (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            brand_id UUID NOT NULL REFERENCES brands(id),
            name VARCHAR(200) NOT NULL,
            slug VARCHAR(200) NOT NULL,
            gender gender NOT NULL,
            terrain terrain DEFAULT 'road',
            support_type support_type,
            category shoe_category,
            description TEXT,
            key_features TEXT[],
            typical_weight_oz NUMERIC(4, 1),
            typical_drop_mm NUMERIC(4, 1),
            typical_stack_heel_mm NUMERIC(4, 1),
            typical_stack_forefoot_mm NUMERIC(4, 1),
            has_carbon_plate BOOLEAN DEFAULT FALSE,
            has_rocker BOOLEAN DEFAULT FALSE,
            cushion_type VARCHAR(100),
            cushion_level VARCHAR(50),
            description_embedding NUMERIC[],
            is_active BOOLEAN DEFAULT TRUE,
            first_release_year INTEGER,
            is_discontinued BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW(),
            CONSTRAINT uq_model_brand_slug_gender UNIQUE (brand_id, slug, gender)
        )
    """)
    op.create_index('ix_shoe_models_brand', 'shoe_models', ['brand_id'])
    op.create_index('ix_shoe_models_terrain', 'shoe_models', ['terrain'])

    # Create shoe_model_aliases table
    op.execute("""
        CREATE TABLE shoe_model_aliases (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            model_id UUID NOT NULL REFERENCES shoe_models(id) ON DELETE CASCADE,
            alias VARCHAR(300) NOT NULL,
            alias_normalized VARCHAR(300) NOT NULL,
            source VARCHAR(100),
            CONSTRAINT uq_model_alias UNIQUE (model_id, alias_normalized)
        )
    """)
    op.create_index('ix_model_aliases_normalized', 'shoe_model_aliases', ['alias_normalized'])

    # Create shoe_products table
    op.execute("""
        CREATE TABLE shoe_products (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            model_id UUID NOT NULL REFERENCES shoe_models(id) ON DELETE CASCADE,
            name VARCHAR(300) NOT NULL,
            slug VARCHAR(300) NOT NULL,
            version VARCHAR(20),
            release_year INTEGER,
            colorway VARCHAR(200),
            style_id VARCHAR(100),
            weight_oz NUMERIC(4, 1),
            drop_mm NUMERIC(4, 1),
            stack_height_heel_mm NUMERIC(4, 1),
            stack_height_forefoot_mm NUMERIC(4, 1),
            msrp_usd NUMERIC(10, 2),
            primary_image_url VARCHAR(500),
            image_urls TEXT[],
            width_options TEXT[],
            is_discontinued BOOLEAN DEFAULT FALSE,
            canonical_url VARCHAR(1000),
            discovered_from VARCHAR(500),
            discovered_at TIMESTAMP,
            is_active BOOLEAN DEFAULT TRUE,
            needs_review BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW(),
            CONSTRAINT uq_product_model_slug UNIQUE (model_id, slug)
        )
    """)
    op.create_index('ix_shoe_products_model', 'shoe_products', ['model_id'])
    op.create_index('ix_shoe_products_style_id', 'shoe_products', ['style_id'])

    # Create shoe_offers table
    op.execute("""
        CREATE TABLE shoe_offers (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            product_id UUID NOT NULL REFERENCES shoe_products(id) ON DELETE CASCADE,
            merchant VARCHAR(100) NOT NULL,
            merchant_product_id VARCHAR(200),
            url VARCHAR(1000) NOT NULL,
            affiliate_url VARCHAR(1500),
            price NUMERIC(10, 2),
            sale_price NUMERIC(10, 2),
            currency VARCHAR(3) DEFAULT 'USD',
            in_stock BOOLEAN DEFAULT TRUE,
            sizes_available JSONB,
            stock_level VARCHAR(50),
            first_seen_at TIMESTAMP DEFAULT NOW(),
            last_seen_at TIMESTAMP DEFAULT NOW(),
            price_updated_at TIMESTAMP,
            CONSTRAINT uq_offer_product_merchant_url UNIQUE (product_id, merchant, url)
        )
    """)
    op.create_index('ix_shoe_offers_product', 'shoe_offers', ['product_id'])
    op.create_index('ix_shoe_offers_merchant', 'shoe_offers', ['merchant'])
    op.create_index('ix_shoe_offers_in_stock', 'shoe_offers', ['in_stock'])

    # Create offer_price_history table
    op.execute("""
        CREATE TABLE offer_price_history (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            offer_id UUID NOT NULL REFERENCES shoe_offers(id) ON DELETE CASCADE,
            price NUMERIC(10, 2) NOT NULL,
            sale_price NUMERIC(10, 2),
            in_stock BOOLEAN,
            recorded_at TIMESTAMP DEFAULT NOW()
        )
    """)
    op.create_index('ix_price_history_offer_date', 'offer_price_history', ['offer_id', 'recorded_at'])

    # Create discovered_urls table
    op.execute("""
        CREATE TABLE discovered_urls (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            url VARCHAR(1000) NOT NULL UNIQUE,
            canonical_url VARCHAR(1000) NOT NULL,
            source_type VARCHAR(50) NOT NULL,
            source_url VARCHAR(1000),
            source_brand VARCHAR(100),
            lastmod TIMESTAMP,
            changefreq VARCHAR(20),
            priority NUMERIC(3, 2),
            status VARCHAR(50) DEFAULT 'pending',
            product_id UUID REFERENCES shoe_products(id) ON DELETE SET NULL,
            error_message TEXT,
            is_product BOOLEAN,
            is_running_shoe BOOLEAN,
            classification_reason VARCHAR(200),
            discovered_at TIMESTAMP DEFAULT NOW(),
            processed_at TIMESTAMP
        )
    """)
    op.create_index('ix_discovered_urls_status', 'discovered_urls', ['status'])
    op.create_index('ix_discovered_urls_source_brand', 'discovered_urls', ['source_brand'])
    op.create_index('ix_discovered_urls_canonical', 'discovered_urls', ['canonical_url'])

    # Create merchants table
    op.execute("""
        CREATE TABLE merchants (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            slug VARCHAR(100) NOT NULL UNIQUE,
            name VARCHAR(200) NOT NULL,
            website_url VARCHAR(500),
            affiliate_network VARCHAR(100),
            affiliate_id VARCHAR(200),
            affiliate_url_template VARCHAR(1000),
            scraper_class VARCHAR(200),
            rate_limit_rpm INTEGER DEFAULT 30,
            requires_browser BOOLEAN DEFAULT FALSE,
            is_active BOOLEAN DEFAULT TRUE,
            last_scrape_at TIMESTAMP,
            last_scrape_status VARCHAR(50),
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        )
    """)

    # Seed default merchants
    op.execute("""
        INSERT INTO merchants (slug, name, website_url, rate_limit_rpm, requires_browser) VALUES
        ('running_warehouse', 'Running Warehouse', 'https://www.runningwarehouse.com', 20, false),
        ('road_runner_sports', 'Road Runner Sports', 'https://www.roadrunnersports.com', 20, true),
        ('zappos', 'Zappos', 'https://www.zappos.com', 30, false),
        ('fleet_feet', 'Fleet Feet', 'https://www.fleetfeet.com', 20, true)
        ON CONFLICT (slug) DO NOTHING
    """)


def downgrade():
    op.drop_table('merchants')
    op.drop_table('discovered_urls')
    op.drop_table('offer_price_history')
    op.drop_table('shoe_offers')
    op.drop_table('shoe_products')
    op.drop_table('shoe_model_aliases')
    op.drop_table('shoe_models')

    # Don't drop enums as they might be used elsewhere
