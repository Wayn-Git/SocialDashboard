import enum
from datetime import datetime
from sqlalchemy import (Column, Integer, String, Boolean, DateTime, ForeignKey, 
                        Enum, JSON, Text, Date, BigInteger)
from sqlalchemy.dialects.postgresql import UUID, BYTEA, JSONB
import uuid
from app.database import Base

class PlatformType(str, enum.Enum):
    facebook = "facebook"
    instagram = "instagram"
    linkedin = "linkedin"

class EmployeeRole(str, enum.Enum):
    admin = "admin"
    analyst = "analyst"
    employee = "employee"

class TokenStatus(str, enum.Enum):
    active = "active"
    expired = "expired"
    failed = "failed"
    revoked = "revoked"

class SyncStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    success = "success"
    failed = "failed"
    skipped = "skipped"

class SyncJobType(str, enum.Enum):
    discover_pages = "discover_pages"
    refresh_token = "refresh_token"
    fetch_posts = "fetch_posts"
    fetch_metrics = "fetch_metrics"

class Client(Base):
    __tablename__ = "clients"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(120), nullable=False)
    brand_color = Column(String(7))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow)

class Employee(Base):
    __tablename__ = "employees"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False)
    full_name = Column(String(120), nullable=False)
    role = Column(Enum(EmployeeRole), default=EmployeeRole.employee)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

class EmployeeOAuthToken(Base):
    __tablename__ = "employee_oauth_tokens"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employee_id = Column(UUID(as_uuid=True), ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)
    provider = Column(Enum(PlatformType), nullable=False)
    enc_access_token = Column(BYTEA, nullable=False)
    enc_refresh_token = Column(BYTEA) # LinkedIn only
    enc_data_key = Column(BYTEA, nullable=False)
    token_iv = Column(BYTEA, nullable=False)
    scopes = Column(JSONB) # TEXT[] equivalent
    expires_at = Column(DateTime(timezone=True), nullable=False)
    last_refreshed_at = Column(DateTime(timezone=True))
    refresh_status = Column(Enum(TokenStatus), default=TokenStatus.active)

class SocialPage(Base):
    __tablename__ = "social_pages"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employee_id = Column(UUID(as_uuid=True), ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="SET NULL"))
    platform = Column(Enum(PlatformType), nullable=False)
    platform_page_id = Column(String(128), nullable=False)
    page_name = Column(String(255), nullable=False)
    enc_page_access_token = Column(BYTEA)
    page_token_iv = Column(BYTEA)
    ig_business_account_id = Column(String(128))
    is_active = Column(Boolean, default=True)
    last_synced_at = Column(DateTime(timezone=True))

class Post(Base):
    __tablename__ = "posts"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    page_id = Column(UUID(as_uuid=True), ForeignKey("social_pages.id", ondelete="CASCADE"), nullable=False)
    platform = Column(Enum(PlatformType), nullable=False)
    platform_post_id = Column(String(255), nullable=False)
    caption = Column(Text)
    permalink_url = Column(Text, nullable=False)
    media_thumbnail_key = Column(String(255))
    created_at = Column(DateTime(timezone=True), nullable=False)
    raw_response = Column(JSONB, default={})
    is_deleted = Column(Boolean, default=False)

class PostMetric(Base):
    __tablename__ = "post_metrics"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    post_id = Column(UUID(as_uuid=True), nullable=False)
    snapshot_date = Column(Date, nullable=False)
    likes = Column(Integer, default=0)
    comments = Column(Integer, default=0)
    shares = Column(Integer, default=0)

class SyncJob(Base):
    __tablename__ = "sync_jobs"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employee_id = Column(UUID(as_uuid=True), ForeignKey("employees.id", ondelete="SET NULL"))
    page_id = Column(UUID(as_uuid=True), ForeignKey("social_pages.id", ondelete="SET NULL"))
    job_type = Column(Enum(SyncJobType), nullable=False)
    status = Column(Enum(SyncStatus), default=SyncStatus.pending)
    started_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    finished_at = Column(DateTime(timezone=True))
    error_payload = Column(JSONB)
    retry_count = Column(Integer, default=0)

# Update this class in app/models.py

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    actor_employee_id = Column(UUID(as_uuid=True), ForeignKey("employees.id", ondelete="SET NULL"))
    action = Column(String(64), nullable=False)
    resource_type = Column(String(32), nullable=False)
    resource_id = Column(UUID(as_uuid=True))
    
    # FIX: Use 'meta_data' in Python, but map it to 'metadata' column in DB
    meta_data = Column("metadata", JSONB, default={})
    
    ip_address = Column(String(45))
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)