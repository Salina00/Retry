import pytest
from datetime import datetime, time
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.app.db import Base
from backend.app.models import Case, Action, Diagnosis
from backend.app.pipeline.guardrails import (
    is_within_calling_window,
    under_retry_cap,
    under_contact_frequency_cap,
    is_hard_decline_retry_blocked,
    is_opted_out
)

# Setup in-memory SQLite database for testing
@pytest.fixture(name="db_session")
def fixture_db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()

# ----------------- 1. Calling Window Guardrail Tests -----------------

def test_is_within_calling_window_pass():
    # 12:00 PM (noon) is inside the 8 AM - 7 PM calling window
    now = datetime(2026, 8, 29, 12, 0, 0)
    
    passed_email, reason_email = is_within_calling_window(now, "send_email")
    assert passed_email is True
    assert "within calling window" in reason_email

    passed_sms, reason_sms = is_within_calling_window(now, "send_sms")
    assert passed_sms is True

def test_is_within_calling_window_block():
    # 10:00 PM (night) is outside the 8 AM - 7 PM calling window
    now_night = datetime(2026, 8, 29, 22, 0, 0)
    passed_email, reason_email = is_within_calling_window(now_night, "send_email")
    assert passed_email is False
    assert "outside calling window" in reason_email

    # 6:00 AM (early morning) is outside the 8 AM - 7 PM calling window
    now_early = datetime(2026, 8, 29, 6, 0, 0)
    passed_sms, reason_sms = is_within_calling_window(now_early, "send_sms")
    assert passed_sms is False
    assert "outside calling window" in reason_sms

def test_is_within_calling_window_bypass():
    # Retries and other non-contact actions should bypass the calling window at night
    now = datetime(2026, 8, 29, 22, 0, 0)
    passed, reason = is_within_calling_window(now, "retry")
    assert passed is True
    assert "bypass" in reason


# ----------------- 2. Retry Cap Guardrail Tests -----------------

def test_under_retry_cap_pass(db_session):
    case_id = "test-case-retry-pass"
    case = Case(id=case_id, leak_type="payment_failure", customer_reference="cust_1", amount=100.0, status="diagnosing")
    db_session.add(case)
    
    # 2 prior executed retries is under default 4 cap
    for i in range(2):
        action = Action(case_id=case_id, action_type="retry", channel="none", status="executed", executed_at=datetime.utcnow())
        db_session.add(action)
    db_session.commit()

    passed, reason = under_retry_cap(db_session, case_id)
    assert passed is True
    assert "under cap" in reason

def test_under_retry_cap_block(db_session):
    case_id = "test-case-retry-block"
    case = Case(id=case_id, leak_type="payment_failure", customer_reference="cust_2", amount=100.0, status="diagnosing")
    db_session.add(case)
    
    # 4 prior executed retries reaches the cap
    for i in range(4):
        action = Action(case_id=case_id, action_type="retry", channel="none", status="executed", executed_at=datetime.utcnow())
        db_session.add(action)
    db_session.commit()

    passed, reason = under_retry_cap(db_session, case_id)
    assert passed is False
    assert "cap of 4 reached" in reason


# ----------------- 3. Contact Frequency Cap Guardrail Tests -----------------

def test_under_contact_frequency_cap_pass(db_session):
    cust_ref = "cust_freq_pass"
    case = Case(id="case-freq-pass", leak_type="payment_failure", customer_reference=cust_ref, amount=100.0)
    db_session.add(case)
    
    # 2 emails today (under the 3 cap)
    now = datetime(2026, 8, 29, 14, 0, 0)
    for i in range(2):
        action = Action(case_id="case-freq-pass", action_type="send_email", channel="email", status="executed", executed_at=now)
        db_session.add(action)
    db_session.commit()

    passed, reason = under_contact_frequency_cap(db_session, cust_ref, now)
    assert passed is True
    assert "under cap of 3" in reason

def test_under_contact_frequency_cap_block(db_session):
    cust_ref = "cust_freq_block"
    case = Case(id="case-freq-block", leak_type="payment_failure", customer_reference=cust_ref, amount=100.0)
    db_session.add(case)
    
    # 3 communications today (2 emails, 1 sms)
    now = datetime(2026, 8, 29, 14, 0, 0)
    action1 = Action(case_id="case-freq-block", action_type="send_email", channel="email", status="executed", executed_at=datetime(2026, 8, 29, 9, 0, 0))
    action2 = Action(case_id="case-freq-block", action_type="send_email", channel="email", status="executed", executed_at=datetime(2026, 8, 29, 10, 0, 0))
    action3 = Action(case_id="case-freq-block", action_type="send_sms", channel="sms", status="executed", executed_at=datetime(2026, 8, 29, 11, 0, 0))
    db_session.add_all([action1, action2, action3])
    db_session.commit()

    passed, reason = under_contact_frequency_cap(db_session, cust_ref, now)
    assert passed is False
    assert "daily contact cap of 3" in reason


# ----------------- 4. Hard Decline Retry Guardrail Tests -----------------

def test_hard_decline_retry_blocked():
    # Hard decline retries must be blocked
    passed, reason = is_hard_decline_retry_blocked(severity="hard", action_type="retry")
    assert passed is False
    assert "Retry blocked for hard decline" in reason

    # Hard declines allowed to receive emails (e.g. asking to update payment details)
    passed_email, reason_email = is_hard_decline_retry_blocked(severity="hard", action_type="send_email")
    assert passed_email is True

    # Soft declines allowed to retry
    passed_soft, reason_soft = is_hard_decline_retry_blocked(severity="soft", action_type="retry")
    assert passed_soft is True


# ----------------- 5. Customer Opt-Out Guardrail Tests -----------------

def test_is_opted_out_pass(db_session):
    cust_ref = "cust_opt_pass"
    case = Case(id="case-opt-pass", leak_type="payment_failure", customer_reference=cust_ref, amount=100.0, opted_out=False)
    db_session.add(case)
    db_session.commit()

    passed, reason = is_opted_out(db_session, cust_ref, "send_email")
    assert passed is True
    assert "not opted out" in reason

def test_is_opted_out_block(db_session):
    cust_ref = "cust_opt_block"
    case = Case(id="case-opt-block", leak_type="payment_failure", customer_reference=cust_ref, amount=100.0, opted_out=True)
    db_session.add(case)
    db_session.commit()

    # Communication is blocked
    passed, reason = is_opted_out(db_session, cust_ref, "send_email")
    assert passed is False
    assert "opted out of communication" in reason

    # Non-communication is allowed
    passed_retry, reason_retry = is_opted_out(db_session, cust_ref, "retry")
    assert passed_retry is True
