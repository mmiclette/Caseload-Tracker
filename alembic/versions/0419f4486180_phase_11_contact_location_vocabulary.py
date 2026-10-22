"""phase 11: contact location vocabulary

Revision ID: 0419f4486180
Revises: 88578d48ce3f
Create Date: 2026-08-07 13:38:36.426343

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0419f4486180'
down_revision: Union[str, None] = '88578d48ce3f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ContactLocation's provisional Phase 2 values became confirmed ones on
    # 2026-08-07 (Matt): in_person -> in_clinic, video -> virtual, phone
    # unchanged. The column is a plain VARCHAR (native_enum=False), so only
    # the stored data needs rewriting, not the column type — a portable
    # UPDATE ... WHERE, no Postgres-only enum ALTER.
    #
    # NOTE the uppercase literals: SQLAlchemy's Enum stores a PEP-435
    # enum's NAME, not its value, so this column holds 'IN_PERSON' /
    # 'VIDEO', not 'in_person' / 'video'. Matching the lowercase values
    # here would silently rewrite nothing and leave rows the new enum
    # can't load. Every other enum column in this schema is stored the
    # same way (verified: contact_type holds 'FOLLOW_UP', etc.).
    contact = sa.table("contact", sa.column("location", sa.String))
    op.execute(contact.update().where(contact.c.location == "IN_PERSON").values(location="IN_CLINIC"))
    op.execute(contact.update().where(contact.c.location == "VIDEO").values(location="VIRTUAL"))


def downgrade() -> None:
    contact = sa.table("contact", sa.column("location", sa.String))
    op.execute(contact.update().where(contact.c.location == "IN_CLINIC").values(location="IN_PERSON"))
    op.execute(contact.update().where(contact.c.location == "VIRTUAL").values(location="VIDEO"))
