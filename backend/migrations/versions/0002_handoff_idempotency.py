"""Support upgrading early local onboarding schema (no public deployment)."""
from alembic import op
import sqlalchemy as sa
revision='0002'
down_revision='0001'
branch_labels=None
depends_on=None

def upgrade():
    # Columns already included in frozen initial for fresh installs; additive compatibility.
    conn=op.get_bind()
    columns={c['name'] for c in sa.inspect(conn).get_columns('handoffs')}
    if 'idempotency_key' not in columns:
        op.add_column('handoffs',sa.Column('idempotency_key',sa.String(),nullable=True))
        op.add_column('handoffs',sa.Column('request_hash',sa.String(),nullable=True))
        op.execute("UPDATE handoffs SET idempotency_key=id, request_hash=id")
        op.alter_column('handoffs','idempotency_key',nullable=False)
        op.alter_column('handoffs','request_hash',nullable=False)
        op.create_unique_constraint('uq_handoff_session_idempotency','handoffs',['session_id','idempotency_key'])
def downgrade(): pass
