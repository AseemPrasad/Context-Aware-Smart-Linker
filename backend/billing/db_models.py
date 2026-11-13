"""SQLAlchemy Relational Ledger Models for Enterprise B2B SaaS.

Provides double-entry auditability, tenant billing records, and permanent
credit transaction tracking to complement real-time Redis rate limits.
"""

from __future__ import annotations

import time
from typing import Optional

try:
    from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, Text, create_engine
    from sqlalchemy.orm import declarative_base, sessionmaker
    Base = declarative_base()
except ImportError:
    Base = object
    Column = Integer = String = Float = Boolean = DateTime = Text = None


if Base is not object:
    class TenantAccount(Base):
        __tablename__ = "tenant_accounts"

        tenant_id = Column(String(128), primary_key=True, index=True)
        plan = Column(String(32), default="starter", nullable=False)
        seats_allocated = Column(Integer, default=5)
        seats_active = Column(Integer, default=1)
        monthly_credits_quota = Column(Integer, default=500)
        credits_used = Column(Integer, default=0)
        stripe_customer_id = Column(String(128), nullable=True)
        stripe_subscription_id = Column(String(128), nullable=True)
        is_active = Column(Boolean, default=True)
        updated_at = Column(Float, default=time.time)

    class CreditAuditLedger(Base):
        __tablename__ = "credit_audit_ledger"

        id = Column(Integer, primary_key=True, autoincrement=True)
        tenant_id = Column(String(128), index=True, nullable=False)
        delta = Column(Integer, nullable=False)  # e.g. -1 for RAG, +5000 for Stripe upgrade
        balance_after = Column(Integer, nullable=False)
        reason = Column(String(128), nullable=False)  # "rag_query", "stripe_subscription", "admin_grant"
        reference_id = Column(String(256), nullable=True)  # request_id or stripe_event_id
        timestamp = Column(Float, default=time.time, index=True)

