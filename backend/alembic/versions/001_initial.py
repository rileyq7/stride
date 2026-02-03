"""Initial database schema

Revision ID: 001
Revises:
Create Date: 2025-01-30

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Categories
    op.create_table(
        'categories',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('name', sa.String(50), unique=True, nullable=False),
        sa.Column('slug', sa.String(50), unique=True, nullable=False),
        sa.Column('display_order', sa.Integer, default=0),
        sa.Column('is_active', sa.Boolean, default=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime, server_default=sa.text('NOW()')),
    )

    # Brands
    op.create_table(
        'brands',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('name', sa.String(100), unique=True, nullable=False),
        sa.Column('slug', sa.String(100), unique=True, nullable=False),
        sa.Column('logo_url', sa.String(500)),
        sa.Column('website_url', sa.String(500)),
        sa.Column('affiliate_base_url', sa.String(500)),
        sa.Column('created_at', sa.DateTime, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime, server_default=sa.text('NOW()')),
    )

    # Shoes
    op.create_table(
        'shoes',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('brand_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('brands.id'), nullable=False),
        sa.Column('category_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('categories.id'), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('slug', sa.String(200), nullable=False),
        sa.Column('model_year', sa.Integer),
        sa.Column('version', sa.String(20)),
        sa.Column('msrp_usd', sa.Numeric(10, 2)),
        sa.Column('current_price_min', sa.Numeric(10, 2)),
        sa.Column('current_price_max', sa.Numeric(10, 2)),
        sa.Column('available_regions', postgresql.ARRAY(sa.Text)),
        sa.Column('width_options', postgresql.ARRAY(sa.Text)),
        sa.Column('is_discontinued', sa.Boolean, default=False),
        sa.Column('primary_image_url', sa.String(500)),
        sa.Column('image_urls', postgresql.ARRAY(sa.Text)),
        sa.Column('is_active', sa.Boolean, default=True),
        sa.Column('needs_review', sa.Boolean, default=False),
        sa.Column('last_scraped_at', sa.DateTime),
        sa.Column('created_at', sa.DateTime, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime, server_default=sa.text('NOW()')),
        sa.UniqueConstraint('brand_id', 'slug', name='uq_brand_slug'),
    )

    # Running shoe attributes
    op.create_table(
        'running_shoe_attributes',
        sa.Column('shoe_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('shoes.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('terrain', sa.Text, nullable=False),
        sa.Column('subcategory', sa.Text),
        sa.Column('weight_oz', sa.Numeric(4, 1)),
        sa.Column('stack_height_heel_mm', sa.Numeric(4, 1)),
        sa.Column('stack_height_forefoot_mm', sa.Numeric(4, 1)),
        sa.Column('drop_mm', sa.Numeric(4, 1)),
        sa.Column('has_carbon_plate', sa.Boolean, default=False),
        sa.Column('has_rocker', sa.Boolean, default=False),
        sa.Column('cushion_type', sa.Text),
        sa.Column('cushion_level', sa.Text),
        sa.Column('best_for_distances', postgresql.ARRAY(sa.Text)),
        sa.Column('best_for_pace', sa.Text),
        sa.Column('updated_at', sa.DateTime, server_default=sa.text('NOW()')),
    )

    # Basketball shoe attributes
    op.create_table(
        'basketball_shoe_attributes',
        sa.Column('shoe_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('shoes.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('cut', sa.Text, nullable=False),
        sa.Column('court_type', postgresql.ARRAY(sa.Text)),
        sa.Column('weight_oz', sa.Numeric(4, 1)),
        sa.Column('cushion_type', sa.Text),
        sa.Column('cushion_level', sa.Text),
        sa.Column('traction_pattern', sa.Text),
        sa.Column('ankle_support_level', sa.Text),
        sa.Column('lockdown_level', sa.Text),
        sa.Column('best_for_position', postgresql.ARRAY(sa.Text)),
        sa.Column('best_for_playstyle', postgresql.ARRAY(sa.Text)),
        sa.Column('outdoor_durability', sa.Text),
        sa.Column('updated_at', sa.DateTime, server_default=sa.text('NOW()')),
    )

    # Shoe fit profiles
    op.create_table(
        'shoe_fit_profiles',
        sa.Column('shoe_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('shoes.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('size_runs', sa.Text),
        sa.Column('size_offset', sa.Numeric(3, 1)),
        sa.Column('size_confidence', sa.Numeric(3, 2)),
        sa.Column('width_runs', sa.Text),
        sa.Column('toe_box_room', sa.Text),
        sa.Column('heel_fit', sa.Text),
        sa.Column('midfoot_fit', sa.Text),
        sa.Column('arch_support', sa.Text),
        sa.Column('arch_support_level', sa.Text),
        sa.Column('break_in_period', sa.Text),
        sa.Column('break_in_miles', sa.Integer),
        sa.Column('all_day_comfort', sa.Boolean),
        sa.Column('expected_miles_min', sa.Integer),
        sa.Column('expected_miles_max', sa.Integer),
        sa.Column('durability_rating', sa.Text),
        sa.Column('common_wear_points', postgresql.ARRAY(sa.Text)),
        sa.Column('common_complaints', postgresql.ARRAY(sa.Text)),
        sa.Column('works_well_for', postgresql.ARRAY(sa.Text)),
        sa.Column('avoid_if', postgresql.ARRAY(sa.Text)),
        sa.Column('overall_sentiment', sa.Numeric(3, 2)),
        sa.Column('review_count', sa.Integer),
        sa.Column('last_updated', sa.DateTime, server_default=sa.text('NOW()')),
        sa.Column('extraction_model', sa.String(50)),
        sa.Column('needs_review', sa.Boolean, default=True),
    )

    # Shoe reviews
    op.create_table(
        'shoe_reviews',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('shoe_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('shoes.id', ondelete='CASCADE'), nullable=False),
        sa.Column('source', sa.String(100), nullable=False),
        sa.Column('source_url', sa.String(500)),
        sa.Column('source_review_id', sa.String(100)),
        sa.Column('reviewer_name', sa.String(100)),
        sa.Column('rating', sa.Numeric(2, 1)),
        sa.Column('title', sa.String(500)),
        sa.Column('body', sa.Text),
        sa.Column('reviewer_foot_width', sa.Text),
        sa.Column('reviewer_arch_type', sa.Text),
        sa.Column('reviewer_size_purchased', sa.String(20)),
        sa.Column('reviewer_typical_size', sa.String(20)),
        sa.Column('reviewer_miles_tested', sa.Integer),
        sa.Column('review_date', sa.Date),
        sa.Column('scraped_at', sa.DateTime, server_default=sa.text('NOW()')),
        sa.UniqueConstraint('shoe_id', 'source', 'source_review_id', name='uq_review_source'),
    )

    # Shoe affiliate links
    op.create_table(
        'shoe_affiliate_links',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('shoe_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('shoes.id', ondelete='CASCADE'), nullable=False),
        sa.Column('retailer', sa.String(100), nullable=False),
        sa.Column('url', sa.String(1000), nullable=False),
        sa.Column('affiliate_tag', sa.String(100)),
        sa.Column('current_price', sa.Numeric(10, 2)),
        sa.Column('in_stock', sa.Boolean, default=True),
        sa.Column('last_checked', sa.DateTime),
        sa.UniqueConstraint('shoe_id', 'retailer', name='uq_shoe_retailer'),
    )

    # Admin users
    op.create_table(
        'admin_users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('email', sa.String(255), unique=True, nullable=False),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('name', sa.String(100)),
        sa.Column('role', sa.Text, default='reviewer'),
        sa.Column('is_active', sa.Boolean, default=True),
        sa.Column('last_login', sa.DateTime),
        sa.Column('created_at', sa.DateTime, server_default=sa.text('NOW()')),
    )

    # Quiz sessions
    op.create_table(
        'quiz_sessions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('session_token', sa.String(100), unique=True),
        sa.Column('ip_address', sa.String(45)),
        sa.Column('user_agent', sa.Text),
        sa.Column('category_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('categories.id')),
        sa.Column('answers', postgresql.JSONB, nullable=False, server_default='{}'),
        sa.Column('user_foot_profile', postgresql.JSONB),
        sa.Column('user_preferences', postgresql.JSONB),
        sa.Column('region', sa.String(10)),
        sa.Column('previous_shoes', postgresql.JSONB),
        sa.Column('foot_scan_data', postgresql.JSONB),
        sa.Column('started_at', sa.DateTime, server_default=sa.text('NOW()')),
        sa.Column('completed_at', sa.DateTime),
        sa.Column('created_at', sa.DateTime, server_default=sa.text('NOW()')),
    )

    # Recommendations
    op.create_table(
        'recommendations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('quiz_session_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('quiz_sessions.id'), nullable=False),
        sa.Column('recommended_shoes', postgresql.JSONB, nullable=False),
        sa.Column('algorithm_version', sa.String(20)),
        sa.Column('model_weights', postgresql.JSONB),
        sa.Column('review_status', sa.Text, default='pending'),
        sa.Column('reviewed_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('admin_users.id')),
        sa.Column('reviewed_at', sa.DateTime),
        sa.Column('adjusted_shoes', postgresql.JSONB),
        sa.Column('admin_notes', sa.Text),
        sa.Column('user_clicked_shoes', postgresql.ARRAY(sa.Text)),
        sa.Column('user_feedback', postgresql.JSONB),
        sa.Column('feedback_at', sa.DateTime),
        sa.Column('created_at', sa.DateTime, server_default=sa.text('NOW()')),
    )

    # Training examples
    op.create_table(
        'training_examples',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('quiz_answers', postgresql.JSONB, nullable=False),
        sa.Column('category_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('categories.id')),
        sa.Column('ideal_shoes', postgresql.JSONB, nullable=False),
        sa.Column('reasoning', postgresql.JSONB),
        sa.Column('source', sa.Text),
        sa.Column('quality_score', sa.Float),
        sa.Column('created_at', sa.DateTime, server_default=sa.text('NOW()')),
    )

    # Admin audit log
    op.create_table(
        'admin_audit_log',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('admin_user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('admin_users.id')),
        sa.Column('action', sa.Text, nullable=False),
        sa.Column('entity_type', sa.Text),
        sa.Column('entity_id', postgresql.UUID(as_uuid=True)),
        sa.Column('changes', postgresql.JSONB),
        sa.Column('created_at', sa.DateTime, server_default=sa.text('NOW()')),
    )

    # Scrape jobs
    op.create_table(
        'scrape_jobs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('job_type', sa.Text, nullable=False),
        sa.Column('target_id', postgresql.UUID(as_uuid=True)),
        sa.Column('source', sa.String(100)),
        sa.Column('status', sa.Text, default='pending'),
        sa.Column('started_at', sa.DateTime),
        sa.Column('completed_at', sa.DateTime),
        sa.Column('results', postgresql.JSONB),
        sa.Column('error_message', sa.Text),
        sa.Column('triggered_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('admin_users.id')),
        sa.Column('created_at', sa.DateTime, server_default=sa.text('NOW()')),
    )

    # Create indexes
    op.create_index('idx_shoes_category', 'shoes', ['category_id'], postgresql_where=sa.text('is_active = true'))
    op.create_index('idx_shoes_brand', 'shoes', ['brand_id'])
    op.create_index('idx_shoes_needs_review', 'shoes', ['needs_review'], postgresql_where=sa.text('needs_review = true'))
    op.create_index('idx_recommendations_pending', 'recommendations', ['review_status'], postgresql_where=sa.text("review_status = 'pending'"))
    op.create_index('idx_recommendations_quiz', 'recommendations', ['quiz_session_id'])
    op.create_index('idx_reviews_shoe', 'shoe_reviews', ['shoe_id'])
    op.create_index('idx_reviews_source', 'shoe_reviews', ['source'])
    op.create_index('idx_quiz_sessions_completed', 'quiz_sessions', ['completed_at'], postgresql_where=sa.text('completed_at IS NOT NULL'))


def downgrade() -> None:
    # Drop indexes
    op.drop_index('idx_quiz_sessions_completed')
    op.drop_index('idx_reviews_source')
    op.drop_index('idx_reviews_shoe')
    op.drop_index('idx_recommendations_quiz')
    op.drop_index('idx_recommendations_pending')
    op.drop_index('idx_shoes_needs_review')
    op.drop_index('idx_shoes_brand')
    op.drop_index('idx_shoes_category')

    # Drop tables in reverse order
    op.drop_table('scrape_jobs')
    op.drop_table('admin_audit_log')
    op.drop_table('training_examples')
    op.drop_table('recommendations')
    op.drop_table('quiz_sessions')
    op.drop_table('admin_users')
    op.drop_table('shoe_affiliate_links')
    op.drop_table('shoe_reviews')
    op.drop_table('shoe_fit_profiles')
    op.drop_table('basketball_shoe_attributes')
    op.drop_table('running_shoe_attributes')
    op.drop_table('shoes')
    op.drop_table('brands')
    op.drop_table('categories')
