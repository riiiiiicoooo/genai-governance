"""
Database Configuration — SQLAlchemy + Redis for persistent storage.

Replaces in-memory state with:
- PostgreSQL (via SQLAlchemy) for transactional logs and audit trails
- Redis for fast aggregate statistics and caching

Connection pooling via QueuePool ensures efficient resource management.
"""

from sqlalchemy import create_engine, Column, String, Integer, Float, DateTime, Boolean, Text, JSON, Date
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
import redis
from datetime import datetime
from typing import Optional
import os

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///./governance.db"  # Default to SQLite for development
)

REDIS_URL = os.getenv(
    "REDIS_URL",
    "redis://localhost:6379"
)

# SQLAlchemy Engine with QueuePool for connection pooling
engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool if "sqlite" not in DATABASE_URL else None,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,  # Test connections before using
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Redis Client
try:
    redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    redis_client.ping()  # Test connection
except Exception as e:
    print(f"Warning: Redis connection failed ({e}). Aggregate stats will use in-memory fallback.")
    redis_client = None

Base = declarative_base()


# ---------------------------------------------------------------------------
# ORM Models
# ---------------------------------------------------------------------------

class InteractionLogORM(Base):
    """ORM model for interaction logs."""
    __tablename__ = "interaction_logs"

    id = Column(String, primary_key=True)
    interaction_id = Column(String, unique=True, index=True)
    timestamp = Column(DateTime, index=True)
    log_level = Column(String)

    # Source
    use_case = Column(String, index=True)
    application_id = Column(String)
    user_id = Column(String)
    session_id = Column(String, nullable=True)

    # Model configuration
    model_id = Column(String, index=True)
    template_id = Column(String)
    prompt_version = Column(String)
    temperature = Column(Float, default=0.0)
    max_tokens = Column(Integer, default=0)

    # Input
    input_text_hash = Column(String)
    input_length = Column(Integer)
    input_contains_pii = Column(Boolean, default=False)
    input_pii_types = Column(JSON, default=list)

    # Output
    output_text_hash = Column(String)
    output_length = Column(Integer)
    output_contains_pii = Column(Boolean, default=False)
    output_pii_types = Column(JSON, default=list)

    # Guardrail results
    guardrail_action = Column(String)
    guardrail_checks = Column(JSON, default=list)

    # Human review
    human_review_required = Column(Boolean, default=False)
    human_reviewer = Column(String, nullable=True)
    human_review_timestamp = Column(DateTime, nullable=True)
    human_review_outcome = Column(String, nullable=True)
    human_review_notes = Column(Text, default="")

    # Final disposition
    final_action = Column(String)
    customer_visible = Column(Boolean, default=False)

    # Performance
    model_latency_ms = Column(Float, default=0.0)
    guardrail_latency_ms = Column(Float, default=0.0)
    total_latency_ms = Column(Float, default=0.0)

    # Integrity
    log_hash = Column(String)


class ComplianceEventORM(Base):
    """ORM model for compliance events."""
    __tablename__ = "compliance_events"

    id = Column(String, primary_key=True)
    event_id = Column(String, unique=True, index=True)
    interaction_id = Column(String, index=True)
    timestamp = Column(DateTime, index=True)
    event_type = Column(String, index=True)
    severity = Column(String, index=True)
    description = Column(Text)
    resolution = Column(Text, nullable=True)
    resolved_by = Column(String, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    escalated_to = Column(String, nullable=True)


class GuardrailReportORM(Base):
    """ORM model for guardrail assessment reports."""
    __tablename__ = "guardrail_reports"

    id = Column(String, primary_key=True)
    interaction_id = Column(String, unique=True, index=True)
    assessed_at = Column(DateTime, index=True)
    action = Column(String)

    # Context
    template_id = Column(String)
    version_id = Column(String)
    model_id = Column(String, index=True)
    input_length = Column(Integer)
    output_length = Column(Integer)

    # Results
    checks = Column(JSON)
    checks_passed = Column(Integer)
    checks_warned = Column(Integer)
    checks_blocked = Column(Integer)

    # Totals
    total_processing_time_ms = Column(Float)
    pii_detected = Column(Boolean)
    hallucination_detected = Column(Boolean)
    bias_detected = Column(Boolean)
    compliance_violation = Column(Boolean)

    # If blocked
    block_reason = Column(Text, nullable=True)
    human_reviewer_assigned = Column(String, nullable=True)
    human_review_completed = Column(Boolean, default=False)
    human_review_outcome = Column(String, nullable=True)


class EvaluationRunORM(Base):
    """ORM model for model evaluation runs."""
    __tablename__ = "evaluation_runs"

    id = Column(String, primary_key=True)
    suite_id = Column(String, index=True)
    model_id = Column(String, index=True)
    prompt_version = Column(String)
    started_at = Column(DateTime)
    completed_at = Column(DateTime, nullable=True)
    status = Column(String)

    # Results
    test_results = Column(JSON, default=list)
    bias_results = Column(JSON, default=list)
    dimension_scores = Column(JSON, default=dict)

    # Summary
    total_cases = Column(Integer)
    passed_cases = Column(Integer)
    failed_cases = Column(Integer)
    pass_rate_pct = Column(Float)

    # Validation outcome
    validation_outcome = Column(String, nullable=True)
    validation_notes = Column(Text, default="")
    conditions = Column(JSON, default=list)

    # Comparison to baseline
    baseline_run_id = Column(String, nullable=True)
    regression_detected = Column(Boolean, default=False)
    regression_details = Column(JSON, default=list)


# ---------------------------------------------------------------------------
# Database Initialization
# ---------------------------------------------------------------------------

def init_db():
    """Create all tables in the database."""
    Base.metadata.create_all(bind=engine)


def get_db() -> Session:
    """Get a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Redis Helpers
# ---------------------------------------------------------------------------

def get_redis_client():
    """Get Redis client or None if unavailable."""
    return redis_client


def redis_set(key: str, value: str, ex: Optional[int] = None):
    """Set a Redis key with optional expiration (seconds)."""
    if redis_client:
        if ex:
            redis_client.setex(key, ex, value)
        else:
            redis_client.set(key, value)


def redis_get(key: str) -> Optional[str]:
    """Get a Redis value."""
    if redis_client:
        return redis_client.get(key)
    return None


def redis_delete(key: str):
    """Delete a Redis key."""
    if redis_client:
        redis_client.delete(key)


def redis_hincrby(key: str, field: str, increment: int = 1):
    """Increment a Redis hash field."""
    if redis_client:
        redis_client.hincrby(key, field, increment)


def redis_hgetall(key: str) -> dict:
    """Get all fields in a Redis hash."""
    if redis_client:
        return redis_client.hgetall(key)
    return {}


def redis_hset(key: str, mapping: dict):
    """Set multiple fields in a Redis hash."""
    if redis_client:
        redis_client.hset(key, mapping=mapping)
