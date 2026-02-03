"""Add AI-friendly tables for matching and chatbot

Revision ID: 002_add_ai_tables
Revises: 001_initial
Create Date: 2025-02-02

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

# revision identifiers
revision: str = '002_add_ai_tables'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create shoe_profiles table
    op.create_table(
        'shoe_profiles',
        sa.Column('shoe_id', UUID(as_uuid=True), sa.ForeignKey('shoes.id', ondelete='CASCADE'), primary_key=True),

        # Normalized scores (0-1 scale for matching algorithms)
        sa.Column('weight_normalized', sa.Numeric(3, 2)),
        sa.Column('cushion_normalized', sa.Numeric(3, 2)),
        sa.Column('stability_normalized', sa.Numeric(3, 2)),
        sa.Column('responsiveness_normalized', sa.Numeric(3, 2)),
        sa.Column('flexibility_normalized', sa.Numeric(3, 2)),

        # JSONB fields for flexible querying
        sa.Column('fit_vector', JSONB, nullable=False, server_default='{}'),
        sa.Column('use_case_scores', JSONB, nullable=False, server_default='{}'),
        sa.Column('terrain_scores', JSONB, nullable=False, server_default='{}'),

        # Full text search
        sa.Column('search_text', sa.Text),

        # Metadata
        sa.Column('confidence_score', sa.Numeric(3, 2)),
        sa.Column('review_count', sa.Integer, default=0),
        sa.Column('last_analyzed_at', sa.DateTime),

        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # Create review_summaries table
    op.create_table(
        'review_summaries',
        sa.Column('shoe_id', UUID(as_uuid=True), sa.ForeignKey('shoes.id', ondelete='CASCADE'), primary_key=True),

        # Review counts
        sa.Column('total_reviews', sa.Integer, default=0),
        sa.Column('expert_reviews', sa.Integer, default=0),
        sa.Column('user_reviews', sa.Integer, default=0),
        sa.Column('average_rating', sa.Numeric(2, 1)),

        # AI-extracted consensus data
        sa.Column('consensus', JSONB, nullable=False, server_default='{}'),
        sa.Column('sentiment', JSONB, nullable=False, server_default='{}'),

        # For UI display
        sa.Column('pros', JSONB, server_default='[]'),
        sa.Column('cons', JSONB, server_default='[]'),

        # Foot type recommendations
        sa.Column('recommendations', JSONB, server_default='{}'),

        # Notable quotes from reviews
        sa.Column('notable_quotes', JSONB, server_default='[]'),

        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # Add AI summary column to shoes table
    op.add_column('shoes', sa.Column('ai_summary', JSONB, server_default='{}'))

    # Create indexes for JSONB columns
    op.create_index('idx_shoe_profiles_fit_vector', 'shoe_profiles', ['fit_vector'], postgresql_using='gin')
    op.create_index('idx_shoe_profiles_use_case', 'shoe_profiles', ['use_case_scores'], postgresql_using='gin')
    op.create_index('idx_review_summaries_consensus', 'review_summaries', ['consensus'], postgresql_using='gin')
    op.create_index('idx_review_summaries_recommendations', 'review_summaries', ['recommendations'], postgresql_using='gin')

    # Full text search index
    op.execute("""
        CREATE INDEX idx_shoe_profiles_search
        ON shoe_profiles USING GIN (to_tsvector('english', COALESCE(search_text, '')))
    """)


def downgrade() -> None:
    op.drop_index('idx_shoe_profiles_search')
    op.drop_index('idx_review_summaries_recommendations')
    op.drop_index('idx_review_summaries_consensus')
    op.drop_index('idx_shoe_profiles_use_case')
    op.drop_index('idx_shoe_profiles_fit_vector')
    op.drop_column('shoes', 'ai_summary')
    op.drop_table('review_summaries')
    op.drop_table('shoe_profiles')
