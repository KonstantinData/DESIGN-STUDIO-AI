"""Durable pseudonymous abuse-limit counters."""
from alembic import op
import sqlalchemy as sa
revision='0003'
down_revision='0002'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('admission_buckets',sa.Column('id',sa.String(),primary_key=True),sa.Column('count',sa.Integer(),nullable=False),sa.Column('expires_at',sa.DateTime(timezone=True),nullable=False))
    op.create_index('ix_admission_buckets_expires_at','admission_buckets',['expires_at'])
def downgrade():
    op.drop_table('admission_buckets')
