"""phase 9: consultation duration minutes

Revision ID: 22f258f006c5
Revises: b7fd8c578b81
Create Date: 2026-08-07 12:03:21.683646

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '22f258f006c5'
down_revision: Union[str, None] = 'b7fd8c578b81'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ContactType gained CARE_TEAM_COLLABORATION in the same phase — no
    # schema change needed for it, since enums are stored as plain VARCHAR
    # (native_enum=False) with no CHECK constraint tied to the value list.
    op.add_column('consultation', sa.Column('duration_minutes', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('consultation', 'duration_minutes')
