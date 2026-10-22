"""phase 7: episode primary and secondary diagnosis

Revision ID: b770d6b77369
Revises: 4ef24f22d749
Create Date: 2026-08-07 10:37:55.062873

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b770d6b77369'
down_revision: Union[str, None] = '4ef24f22d749'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    condition_type = sa.Enum(
        'DEPRESSION', 'ANXIETY', 'PTSD', 'ADHD', 'SUBSTANCE_USE',
        name='condition_type', native_enum=False, length=32,
    )
    op.add_column('episode_of_care', sa.Column('primary_diagnosis', condition_type, nullable=True))
    op.add_column('episode_of_care', sa.Column('secondary_diagnosis', condition_type, nullable=True))


def downgrade() -> None:
    op.drop_column('episode_of_care', 'secondary_diagnosis')
    op.drop_column('episode_of_care', 'primary_diagnosis')
