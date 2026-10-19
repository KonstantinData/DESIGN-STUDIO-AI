"""Large conservative upper bounds must be recordable without integer overflow."""
from alembic import op
import sqlalchemy as sa
revision='0004'
down_revision='0003'
branch_labels=None
depends_on=None

def upgrade():
    for table,columns in [('accounts',['budget','spent','reserved']),('tenants',['budget','spent','reserved']),('reservations',['amount'])]:
        for column in columns:op.alter_column(table,column,existing_type=sa.Integer(),type_=sa.BigInteger(),existing_nullable=False)
def downgrade():
    for table,columns in [('accounts',['budget','spent','reserved']),('tenants',['budget','spent','reserved']),('reservations',['amount'])]:
        for column in columns:op.alter_column(table,column,existing_type=sa.BigInteger(),type_=sa.Integer(),existing_nullable=False)
