"""phase 5: medication entity

Revision ID: 5eebe8f0a50f
Revises: d57c571e7d09
Create Date: 2026-08-07 09:18:49.308146

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5eebe8f0a50f'
down_revision: Union[str, None] = 'd57c571e7d09'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('medication',
    sa.Column('medication_id', sa.Integer(), sa.Identity(always=False), nullable=False),
    sa.Column('patient_id', sa.Integer(), nullable=False),
    sa.Column('medication_key', sa.String(length=128), nullable=True),
    sa.Column('medication_name', sa.String(length=255), nullable=False),
    sa.Column('dose', sa.String(length=128), nullable=True),
    sa.Column('frequency', sa.String(length=128), nullable=True),
    sa.Column('is_current', sa.Boolean(), nullable=False),
    sa.Column('stop_reason', sa.String(length=1024), nullable=True),
    sa.Column('recorded_by', sa.String(length=255), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['patient_id'], ['patient.patient_id'], ),
    sa.PrimaryKeyConstraint('medication_id')
    )
    op.create_index(op.f('ix_medication_patient_id'), 'medication', ['patient_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_medication_patient_id'), table_name='medication')
    op.drop_table('medication')
