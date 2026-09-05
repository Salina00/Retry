from datetime import datetime, time
from sqlalchemy.orm import Session
from sqlalchemy import func
from backend.app.models import Action, Case, Diagnosis, AuditLogEntry

def is_within_calling_window(now: datetime, action_type: str) -> tuple[bool, str]:
    """
    Outbound contacts (email, sms) are only allowed between 8 AM and 7 PM (inclusive of 8:00, exclusive of 19:00).
    """
    if action_type not in ["send_email", "send_sms"]:
        # Non-contact actions (retries, escalations) are not restricted by calling window
        return True, "Non-contact action bypasses calling window"
    
    current_time = now.time()
    start_time = time(8, 0, 0)
    end_time = time(19, 0, 0)
    
    if start_time <= current_time < end_time:
        return True, f"Time {current_time} is within calling window (8 AM - 7 PM)"
    else:
        return False, f"Time {current_time} is outside calling window (8 AM - 7 PM)"


def under_retry_cap(db: Session, case_id: str, max_retries: int = 4) -> tuple[bool, str]:
    """
    A case cannot have more than `max_retries` payment retry attempts.
    """
    retry_count = db.query(Action).filter(
        Action.case_id == case_id,
        Action.action_type == "retry",
        Action.status == "executed"
    ).count()
    
    if retry_count < max_retries:
        return True, f"Retry count {retry_count} is under cap of {max_retries}"
    else:
        return False, f"Retry attempt cap of {max_retries} reached"


def under_contact_frequency_cap(db: Session, customer_reference: str, now: datetime, max_contacts: int = 3) -> tuple[bool, str]:
    """
    A customer cannot receive more than `max_contacts` communication touches per calendar day.
    """
    start_of_day = datetime(now.year, now.month, now.day, 0, 0, 0)
    end_of_day = datetime(now.year, now.month, now.day, 23, 59, 59)
    
    # Find all cases for this customer reference
    case_ids = [r[0] for r in db.query(Case.id).filter(Case.customer_reference == customer_reference).all()]
    if not case_ids:
        return True, "No prior cases for customer"
    
    # Count executed contact actions for these cases today
    contact_count = db.query(Action).filter(
        Action.case_id.in_(case_ids),
        Action.action_type.in_(["send_email", "send_sms"]),
        Action.status == "executed",
        Action.executed_at >= start_of_day,
        Action.executed_at <= end_of_day
    ).count()
    
    if contact_count < max_contacts:
        return True, f"Contact count {contact_count} today is under cap of {max_contacts}"
    else:
        return False, f"Customer reached daily contact cap of {max_contacts}"


def is_hard_decline_retry_blocked(severity: str, action_type: str) -> tuple[bool, str]:
    """
    Hard declines must never be retried.
    """
    if severity == "hard" and action_type == "retry":
        return False, "Retry blocked for hard decline cases"
    return True, "No hard decline retry conflict"


def is_opted_out(db: Session, customer_reference: str, action_type: str) -> tuple[bool, str]:
    """
    If a customer has opted out, any communication must be blocked.
    """
    if action_type not in ["send_email", "send_sms"]:
        return True, "Non-contact action bypasses opt-out check"
        
    # Check if any case for this customer has opted_out set to True
    opt_out_exists = db.query(Case).filter(
        Case.customer_reference == customer_reference,
        Case.opted_out == True
    ).first()
    
    if opt_out_exists:
        return False, "Customer has opted out of communication"
    return True, "Customer has not opted out"


def run_all_guardrails(
    db: Session,
    case_id: str,
    action_type: str,
    now: datetime,
    max_retries: int = 4,
    max_contacts: int = 3
) -> tuple[bool, list[dict]]:
    """
    Executes all guardrail checks for a given action and case.
    Returns:
        (all_passed: bool, checks_list: list of dicts detailing each check result)
    """
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        return False, [{"rule_name": "CaseExists", "passed": False, "reason": "Case not found"}]
        
    # Find latest real failure diagnosis severity
    diagnosis = db.query(Diagnosis).filter(
        Diagnosis.case_id == case_id,
        Diagnosis.root_cause != "manual_reactivation"
    ).order_by(Diagnosis.created_at.desc()).first()
    severity = diagnosis.severity if diagnosis else "unknown"

    # Check if there is an active compliance override from the latest manual reactivation
    override_log = db.query(AuditLogEntry).filter(
        AuditLogEntry.case_id == case_id,
        AuditLogEntry.step == "diagnosis"
    ).order_by(AuditLogEntry.created_at.desc()).first()
    
    has_override = False
    if override_log and isinstance(override_log.payload, dict):
        if override_log.payload.get("root_cause") == "manual_reactivation" and override_log.payload.get("compliance_override") is True:
            has_override = True

    checks = []
    
    # 1. Calling Window
    passed, reason = is_within_calling_window(now, action_type)
    checks.append({"rule_name": "is_within_calling_window", "passed": passed, "reason": reason})
    
    # 2. Retry Cap
    if action_type == "retry":
        passed, reason = under_retry_cap(db, case_id, max_retries)
        checks.append({"rule_name": "under_retry_cap", "passed": passed, "reason": reason})
        
    # 3. Contact Frequency Cap
    if action_type in ["send_email", "send_sms"]:
        passed, reason = under_contact_frequency_cap(db, case.customer_reference, now, max_contacts)
        checks.append({"rule_name": "under_contact_frequency_cap", "passed": passed, "reason": reason})
        
    # 4. Hard Decline Block
    if has_override:
        passed, reason = True, "Bypassed by explicit compliance override"
    else:
        passed, reason = is_hard_decline_retry_blocked(severity, action_type)
    checks.append({"rule_name": "is_hard_decline_retry_blocked", "passed": passed, "reason": reason})
    
    # 5. Opt-Out
    passed, reason = is_opted_out(db, case.customer_reference, action_type)
    checks.append({"rule_name": "is_opted_out", "passed": passed, "reason": reason})
    
    all_passed = all(c["passed"] for c in checks)
    return all_passed, checks
