"""
SQLAlchemy Models - Database schema for DataSift SaaS platform
"""

from sqlalchemy import Column, String, Integer, Float, DateTime, Boolean, Text, Index, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import func
import uuid

Base = declarative_base()


class Plan(Base):
    __tablename__ = "plans"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(Text)

    price_monthly = Column(Float, default=0)
    price_yearly = Column(Float, default=0)

    request_limit = Column(Integer, nullable=False, default=1000)
    max_file_size_mb = Column(Integer, default=10)

    advanced_ml = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    email = Column(String, unique=True, nullable=False, index=True)
    name = Column(String)

    hashed_password = Column(String, nullable=False)

    api_key = Column(String, unique=True, index=True)

    plan_id = Column(String, ForeignKey("plans.id"), default="free")

    subscription_status = Column(String, default="active")

    subscription_start_date = Column(DateTime(timezone=True))
    subscription_end_date = Column(DateTime(timezone=True))

    monthly_requests = Column(Integer, default=0)
    request_limit = Column(Integer, default=1000)
    total_requests = Column(Integer, default=0)

    last_login_at = Column(DateTime(timezone=True))

    email_verified = Column(Boolean, default=False)
    two_factor_enabled = Column(Boolean, default=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_users_plan_status", "plan_id", "subscription_status"),
        Index("ix_users_created_at", "created_at"),
    )


class Payment(Base):
    __tablename__ = "payments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    plan_id = Column(String, ForeignKey("plans.id"), nullable=False)

    amount = Column(Float, nullable=False)
    currency = Column(String, default="USD")

    status = Column(String, default="pending")

    paypal_order_id = Column(String, unique=True, index=True)
    paypal_payer_id = Column(String)
    paypal_capture_id = Column(String)

    billing_cycle = Column(String, default="monthly")

    payment_metadata = Column("payment_metadata", JSONB, default=dict)

    failure_reason = Column(Text)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    completed_at = Column(DateTime(timezone=True))
    refunded_at = Column(DateTime(timezone=True))

    __table_args__ = (
        Index("ix_payments_status_created", "status", "created_at"),
        Index("ix_payments_user_created", "user_id", "created_at"),
    )


class AnalysisReport(Base):
    __tablename__ = "analysis_reports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    dataset_name = Column(Text)
    dataset_hash = Column(Text, index=True)

    dataset_size_bytes = Column(Integer)

    row_count = Column(Integer)
    column_count = Column(Integer)

    analysis_type = Column(String, default="full")

    summary = Column(JSONB, default=dict)
    patterns = Column(JSONB, default=list)
    recommendations = Column(JSONB, default=list)
    quality_scores = Column(JSONB, default=dict)

    processing_time_ms = Column(Integer)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_reports_user_created", "user_id", "created_at"),
        Index("ix_reports_dataset_hash", "dataset_hash"),
    )


class ApiKeyLog(Base):
    __tablename__ = "api_key_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    api_key_prefix = Column(String)

    action = Column(String)

    ip_address = Column(String)

    user_agent = Column(Text)

    created_at = Column(DateTime(timezone=True), server_default=func.now())


class UsageLog(Base):
    __tablename__ = "usage_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    endpoint = Column(Text)

    method = Column(String)

    status_code = Column(Integer)

    response_time_ms = Column(Integer)

    request_size_bytes = Column(Integer)
    response_size_bytes = Column(Integer)

    ip_address = Column(String)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_usage_user_created", "user_id", "created_at"),
        Index("ix_usage_endpoint_created", "endpoint", "created_at"),
    )
