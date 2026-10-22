"""phase 8: encounter and consultation notes

Revision ID: b7fd8c578b81
Revises: b770d6b77369
Create Date: 2026-08-07 11:06:48.544176

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7fd8c578b81'
down_revision: Union[str, None] = 'b770d6b77369'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('contact', sa.Column('notes', sa.Text(), nullable=True))
    op.add_column('consultation', sa.Column('notes', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('consultation', 'notes')
    op.drop_column('contact', 'notes')
