"""add product_id to reviews and summaries

Revision ID: ab64ae437648
Revises: 003_add_catalog_tables
Create Date: 2026-02-03 12:46:55.547035

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ab64ae437648'
down_revision: Union[str, None] = '003_add_catalog_tables'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add product_id column to shoe_reviews
    op.add_column('shoe_reviews', sa.Column('product_id', sa.Uuid(), nullable=True))
    op.create_foreign_key(
        'fk_shoe_reviews_product_id',
        'shoe_reviews', 'shoe_products',
        ['product_id'], ['id'],
        ondelete='SET NULL'
    )

    # Add product_id column to review_summaries
    op.add_column('review_summaries', sa.Column('product_id', sa.Uuid(), nullable=True))
    op.create_index('ix_review_summaries_product_id', 'review_summaries', ['product_id'], unique=False)
    op.create_foreign_key(
        'fk_review_summaries_product_id',
        'review_summaries', 'shoe_products',
        ['product_id'], ['id'],
        ondelete='SET NULL'
    )


def downgrade() -> None:
    # Remove from review_summaries
    op.drop_constraint('fk_review_summaries_product_id', 'review_summaries', type_='foreignkey')
    op.drop_index('ix_review_summaries_product_id', table_name='review_summaries')
    op.drop_column('review_summaries', 'product_id')

    # Remove from shoe_reviews
    op.drop_constraint('fk_shoe_reviews_product_id', 'shoe_reviews', type_='foreignkey')
    op.drop_column('shoe_reviews', 'product_id')
