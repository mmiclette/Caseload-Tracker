"""phase 13: audit log

Revision ID: f8e648b8e2ae
Revises: 0419f4486180
Create Date: 2026-08-19 15:06:28.247350

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f8e648b8e2ae'
down_revision: Union[str, None] = '0419f4486180'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'audit_log',
        sa.Column('audit_log_id', sa.Integer(), sa.Identity(always=False), nullable=False),
        sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('actor_provider_id', sa.Integer(), nullable=True),
        sa.Column('actor_label', sa.String(length=255), nullable=True),
        sa.Column(
            'action',
            sa.Enum(
                'STATUS_CHANGED', 'FLAG_SET', 'FLAG_CLEARED', 'SCORE_RECORDED',
                'EPISODE_OPENED', 'EPISODE_CLOSED', 'PATIENT_DEACTIVATED',
                'PATIENT_UPDATED',
                name='audit_action', native_enum=False, length=32,
            ),
            nullable=False,
        ),
        sa.Column('entity_type', sa.String(length=64), nullable=False),
        sa.Column('entity_id', sa.Integer(), nullable=True),
        sa.Column('patient_id', sa.Integer(), nullable=False),
        sa.Column('field', sa.String(length=64), nullable=True),
        sa.Column('old_value', sa.String(length=512), nullable=True),
        sa.Column('new_value', sa.String(length=512), nullable=True),
        sa.Column('context', sa.String(length=512), nullable=True),
        sa.ForeignKeyConstraint(['actor_provider_id'], ['provider.provider_id']),
        sa.ForeignKeyConstraint(['patient_id'], ['patient.patient_id']),
        sa.PrimaryKeyConstraint('audit_log_id'),
    )
    op.create_index(op.f('ix_audit_log_occurred_at'), 'audit_log', ['occurred_at'], unique=False)
    op.create_index(op.f('ix_audit_log_patient_id'), 'audit_log', ['patient_id'], unique=False)
    op.create_index(
        op.f('ix_audit_log_actor_provider_id'), 'audit_log', ['actor_provider_id'], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_audit_log_actor_provider_id'), table_name='audit_log')
    op.drop_index(op.f('ix_audit_log_patient_id'), table_name='audit_log')
    op.drop_index(op.f('ix_audit_log_occurred_at'), table_name='audit_log')
    op.drop_table('audit_log')
