"""phase 10: relapse prevention plan fields

Revision ID: 88578d48ce3f
Revises: 22f258f006c5
Create Date: 2026-08-07 13:29:56.702506

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '88578d48ce3f'
down_revision: Union[str, None] = '22f258f006c5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('contact', sa.Column('other_treatments', sa.Text(), nullable=True))
    op.add_column('contact', sa.Column('personal_warning_signs', sa.Text(), nullable=True))
    op.add_column('contact', sa.Column('stress_reduction_plan', sa.Text(), nullable=True))
    op.add_column('contact', sa.Column('additional_comments', sa.Text(), nullable=True))
    op.add_column(
        'contact',
        sa.Column(
            'medications_confirmation',
            sa.Enum(
                'CONFIRMED_WITH_PATIENT', 'CONFIRMED_IN_MEDICAL_RECORD', 'DEFERRED',
                name='medication_confirmation', native_enum=False, length=32,
            ),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column('contact', 'medications_confirmation')
    op.drop_column('contact', 'additional_comments')
    op.drop_column('contact', 'stress_reduction_plan')
    op.drop_column('contact', 'personal_warning_signs')
    op.drop_column('contact', 'other_treatments')
