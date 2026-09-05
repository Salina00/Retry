import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, Boolean, DateTime, Integer, ForeignKey, JSON
from sqlalchemy.orm import relationship
from backend.app.db import Base

def generate_uuid():
    return str(uuid.uuid4())

class Case(Base):
    __tablename__ = "cases"

    id = Column(String, primary_key=True, default=generate_uuid)
    leak_type = Column(String, nullable=False)  # payment_failure | receivable_overdue
    status = Column(String, nullable=False, default="detected")  # detected, diagnosing, decided, blocked, actioned, recovered, escalated
    customer_reference = Column(String, nullable=False, index=True)
    customer_email = Column(String, nullable=True)
    customer_phone = Column(String, nullable=True)
    opted_out = Column(Boolean, default=False)
    amount = Column(Float, nullable=False)
    recovered_amount = Column(Float, default=0.0)
    currency = Column(String, nullable=False, default="INR")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    events = relationship("Event", back_populates="case", cascade="all, delete-orphan")
    diagnoses = relationship("Diagnosis", back_populates="case", cascade="all, delete-orphan")
    decisions = relationship("Decision", back_populates="case", cascade="all, delete-orphan")
    guardrail_checks = relationship("GuardrailCheck", back_populates="case", cascade="all, delete-orphan")
    actions = relationship("Action", back_populates="case", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLogEntry", back_populates="case", cascade="all, delete-orphan")
    promises = relationship("PromiseToPay", back_populates="case", cascade="all, delete-orphan")


class Event(Base):
    __tablename__ = "events"

    id = Column(String, primary_key=True, default=generate_uuid)
    case_id = Column(String, ForeignKey("cases.id", ondelete="CASCADE"), nullable=False)
    event_type = Column(String, nullable=False)
    payload = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    case = relationship("Case", back_populates="events")


class Diagnosis(Base):
    __tablename__ = "diagnoses"

    id = Column(String, primary_key=True, default=generate_uuid)
    case_id = Column(String, ForeignKey("cases.id", ondelete="CASCADE"), nullable=False)
    root_cause = Column(String, nullable=False)
    severity = Column(String, nullable=False)  # soft | hard | unknown
    recovery_probability = Column(Float, nullable=False)
    reasoning = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    case = relationship("Case", back_populates="diagnoses")


class Decision(Base):
    __tablename__ = "decisions"

    id = Column(String, primary_key=True, default=generate_uuid)
    case_id = Column(String, ForeignKey("cases.id", ondelete="CASCADE"), nullable=False)
    action = Column(String, nullable=False)  # retry | send_email | send_sms | escalate_human | stop
    channel = Column(String, nullable=False)  # email | sms | none
    scheduled_for = Column(DateTime, nullable=False)
    reasoning = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    case = relationship("Case", back_populates="decisions")


class GuardrailCheck(Base):
    __tablename__ = "guardrail_checks"

    id = Column(String, primary_key=True, default=generate_uuid)
    case_id = Column(String, ForeignKey("cases.id", ondelete="CASCADE"), nullable=False)
    rule_name = Column(String, nullable=False)
    passed = Column(Boolean, nullable=False)
    reason = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    case = relationship("Case", back_populates="guardrail_checks")


class Action(Base):
    __tablename__ = "actions"

    id = Column(String, primary_key=True, default=generate_uuid)
    case_id = Column(String, ForeignKey("cases.id", ondelete="CASCADE"), nullable=False)
    action_type = Column(String, nullable=False)  # retry | send_email | send_sms | escalate_human | stop
    channel = Column(String, nullable=False)  # email | sms | none
    payload = Column(JSON, nullable=True)
    status = Column(String, nullable=False, default="pending")  # executed | blocked | pending
    executed_at = Column(DateTime, nullable=True)
    outcome = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    case = relationship("Case", back_populates="actions")


class AuditLogEntry(Base):
    __tablename__ = "audit_log_entries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    case_id = Column(String, ForeignKey("cases.id", ondelete="CASCADE"), nullable=False)
    step = Column(String, nullable=False)  # detection | diagnosis | decision | guardrail_check | action | outcome
    source = Column(String, nullable=False, default="rule_engine")  # claude_diagnosis | claude_decision | rule_engine
    payload = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    case = relationship("Case", back_populates="audit_logs")


class PromiseToPay(Base):
    __tablename__ = "promises_to_pay"

    id = Column(String, primary_key=True, default=generate_uuid)
    case_id = Column(String, ForeignKey("cases.id", ondelete="CASCADE"), nullable=False)
    promised_date = Column(DateTime, nullable=False)
    promised_amount = Column(Float, nullable=False)
    status = Column(String, nullable=False, default="pending")  # pending | kept | broken
    created_at = Column(DateTime, default=datetime.utcnow)

    case = relationship("Case", back_populates="promises")


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, default="recovery_specialist")  # recovery_specialist | compliance_manager | admin
    created_at = Column(DateTime, default=datetime.utcnow)

    sessions = relationship("SessionToken", back_populates="user", cascade="all, delete-orphan")


class SessionToken(Base):
    __tablename__ = "session_tokens"

    token = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="sessions")

