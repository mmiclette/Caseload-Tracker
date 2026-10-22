"""phase 6: profile entry entity

Revision ID: 4ef24f22d749
Revises: 5eebe8f0a50f
Create Date: 2026-08-07 10:15:04.513141

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4ef24f22d749'
down_revision: Union[str, None] = '5eebe8f0a50f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('profile_entry',
    sa.Column('profile_entry_id', sa.Integer(), sa.Identity(always=False), nullable=False),
    sa.Column('patient_id', sa.Integer(), nullable=False),
    sa.Column('section', sa.Enum('BEHAVIORAL_HEALTH', 'CURRENT_MEDICATIONS', 'MEDICAL_PROFILE', 'SAFETY_AND_RISK', 'SUBSTANCE_USE', 'SOCIAL_ENVIRONMENTAL', name='profile_section', native_enum=False, length=32), nullable=False),
    sa.Column('sub_field', sa.String(length=128), nullable=False),
    sa.Column('value', sa.String(length=2048), nullable=False),
    sa.Column('context', sa.String(length=2048), nullable=True),
    sa.Column('recorded_date', sa.Date(), nullable=False),
    sa.Column('recorded_by', sa.String(length=255), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['patient_id'], ['patient.patient_id'], ),
    sa.PrimaryKeyConstraint('profile_entry_id')
    )
    op.create_index(op.f('ix_profile_entry_patient_id'), 'profile_entry', ['patient_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_profile_entry_patient_id'), table_name='profile_entry')
    op.drop_table('profile_entry')
