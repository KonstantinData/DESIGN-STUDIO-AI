from alembic import context
from app.db import Base, engine_for
config=context.config
target_metadata=Base.metadata
with engine_for().connect() as connection:
    context.configure(connection=connection,target_metadata=target_metadata)
    with context.begin_transaction(): context.run_migrations()
