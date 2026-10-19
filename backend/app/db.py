"""PostgreSQL-only persistence; all money amounts are conservative cents."""
import os
from datetime import datetime, timezone
from uuid import uuid4
from functools import lru_cache
from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

def now(): return datetime.now(timezone.utc)
def uid(): return str(uuid4())
class Base(DeclarativeBase): pass
class Tenant(Base):
    __tablename__ = 'tenants'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    host: Mapped[str] = mapped_column(String, unique=True)
    config: Mapped[dict] = mapped_column(JSONB)
    budget: Mapped[int] = mapped_column(BigInteger)
    spent: Mapped[int] = mapped_column(BigInteger, default=0)
    reserved: Mapped[int] = mapped_column(BigInteger, default=0)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
class Account(Base):
    __tablename__='accounts'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    budget: Mapped[int] = mapped_column(BigInteger)
    spent: Mapped[int] = mapped_column(BigInteger,default=0)
    reserved: Mapped[int] = mapped_column(BigInteger,default=0)
class Session(Base):
    __tablename__='sessions'
    id: Mapped[str] = mapped_column(String,primary_key=True,default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey('tenants.id'),index=True)
    token_hash: Mapped[str] = mapped_column(String,unique=True)
    resume_hash: Mapped[str|None] = mapped_column(String,nullable=True,unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),default=now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),index=True)
    changes_used: Mapped[int] = mapped_column(Integer,default=0)
    changes_pending: Mapped[int] = mapped_column(Integer,default=0)
class Studio(Base):
    __tablename__='studios'
    id: Mapped[str] = mapped_column(String,primary_key=True,default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey('tenants.id'),index=True)
    session_id: Mapped[str] = mapped_column(ForeignKey('sessions.id',ondelete='CASCADE'),index=True)
    status: Mapped[str] = mapped_column(String,default='queued')
    prompt: Mapped[str] = mapped_column(Text)
    source_kind: Mapped[str] = mapped_column(String)
    source_media_id: Mapped[str|None] = mapped_column(String,nullable=True)
    brief: Mapped[dict|None] = mapped_column(JSONB,nullable=True)
    selected_revision_id: Mapped[str|None] = mapped_column(String,nullable=True)
    error: Mapped[str|None] = mapped_column(Text,nullable=True)
class Media(Base):
    __tablename__='media'
    id: Mapped[str] = mapped_column(String,primary_key=True,default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey('tenants.id'),index=True)
    session_id: Mapped[str] = mapped_column(ForeignKey('sessions.id',ondelete='CASCADE'),index=True)
    path: Mapped[str] = mapped_column(Text)
    mime: Mapped[str] = mapped_column(String)
class Revision(Base):
    __tablename__='revisions'
    id: Mapped[str] = mapped_column(String,primary_key=True,default=uid)
    studio_id: Mapped[str] = mapped_column(ForeignKey('studios.id',ondelete='CASCADE'),index=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey('tenants.id'),index=True)
    concept: Mapped[str] = mapped_column(String)
    number: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String)
    media_id: Mapped[str] = mapped_column(ForeignKey('media.id',ondelete='CASCADE'))
    curation: Mapped[list] = mapped_column(JSONB)
    profile: Mapped[dict] = mapped_column(JSONB)
    room_version: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),default=now)
class Job(Base):
    __tablename__='jobs'
    __table_args__=(UniqueConstraint('session_id','idempotency_key','operation'),)
    id: Mapped[str] = mapped_column(String,primary_key=True,default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey('tenants.id'),index=True)
    session_id: Mapped[str] = mapped_column(ForeignKey('sessions.id',ondelete='CASCADE'),index=True)
    studio_id: Mapped[str] = mapped_column(ForeignKey('studios.id',ondelete='CASCADE'),index=True)
    operation: Mapped[str] = mapped_column(String)
    idempotency_key: Mapped[str] = mapped_column(String)
    request_hash: Mapped[str] = mapped_column(String)
    payload: Mapped[dict] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String,default='queued',index=True)
    error: Mapped[str|None] = mapped_column(Text,nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),default=now)
    started_at: Mapped[datetime|None] = mapped_column(DateTime(timezone=True),nullable=True)
class Reservation(Base):
    __tablename__='reservations'
    id: Mapped[str] = mapped_column(String,primary_key=True,default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey('tenants.id'))
    job_id: Mapped[str|None] = mapped_column(ForeignKey('jobs.id',ondelete='SET NULL'),nullable=True)
    amount: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String,default='reserved')
    usage: Mapped[dict|None] = mapped_column(JSONB,nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),default=now)
class Handoff(Base):
    __tablename__='handoffs'
    __table_args__=(UniqueConstraint('session_id','idempotency_key'),)
    idempotency_key: Mapped[str] = mapped_column(String)
    request_hash: Mapped[str] = mapped_column(String)
    id: Mapped[str] = mapped_column(String,primary_key=True,default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey('tenants.id'))
    session_id: Mapped[str] = mapped_column(ForeignKey('sessions.id',ondelete='CASCADE'))
    revision_id: Mapped[str] = mapped_column(ForeignKey('revisions.id',ondelete='CASCADE'))
    status: Mapped[str] = mapped_column(String,default='pending')

class AdmissionBucket(Base):
    __tablename__='admission_buckets'
    id: Mapped[str] = mapped_column(String,primary_key=True)
    count: Mapped[int] = mapped_column(Integer)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),index=True)

@lru_cache(maxsize=8)
def engine_for(url=None):
    url=url or os.environ.get('DATABASE_URL','')
    if not url.startswith('postgresql+psycopg://'): raise RuntimeError('DATABASE_URL must use postgresql+psycopg://')
    return create_engine(url,pool_pre_ping=True,pool_size=10,max_overflow=10,hide_parameters=True)
def factory(): return sessionmaker(engine_for(os.environ.get('DATABASE_URL','')),expire_on_commit=False)
