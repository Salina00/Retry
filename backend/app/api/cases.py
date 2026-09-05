from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from backend.app.db import get_db
from backend.app.models import Case, AuditLogEntry, PromiseToPay, Diagnosis, Decision
from backend.app.schemas import CaseSchema, CaseTraceResponse, PromiseToPayCreate, PromiseToPaySchema
from backend.app.pipeline.detection import execute_recovery_action

router = APIRouter(prefix="/cases", tags=["Cases"])

@router.get("", response_model=List[CaseSchema])
def get_cases(
    leak_type: Optional[str] = Query(None, description="Filter by leak type (payment_failure | receivable_overdue)"),
    status: Optional[str] = Query(None, description="Filter by status (detected | diagnosing | decided | blocked | actioned | recovered | escalated)"),
    db: Session = Depends(get_db)
):
    query = db.query(Case)
    if leak_type:
        query = query.filter(Case.leak_type == leak_type)
    if status:
        query = query.filter(Case.status == status)
    
    # Order by newest cases first
    return query.order_by(Case.created_at.desc()).all()


@router.get("/{case_id}", response_model=CaseTraceResponse)
def get_case_trace(case_id: str, db: Session = Depends(get_db)):
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    # Fetch audit logs in chronological order
    audit_logs = db.query(AuditLogEntry).filter(
        AuditLogEntry.case_id == case_id
    ).order_by(AuditLogEntry.created_at.asc()).all()

    return {
        "case": case,
        "audit_logs": audit_logs
    }


@router.post("/{case_id}/promise", response_model=PromiseToPaySchema)
def create_promise_to_pay(
    case_id: str,
    promise_in: PromiseToPayCreate,
    db: Session = Depends(get_db)
):
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    # Add Promise to Pay
    p2p = PromiseToPay(
        case_id=case_id,
        promised_date=promise_in.promised_date,
        promised_amount=promise_in.promised_amount,
        status="pending",
        created_at=datetime.utcnow()
    )
    db.add(p2p)
    
    # Audit log
    audit = AuditLogEntry(source='rule_engine', 
        case_id=case_id,
        step="outcome",
        payload={
            "message": "B2B Promise-to-Pay registered.",
            "promised_date": promise_in.promised_date.isoformat(),
            "promised_amount": promise_in.promised_amount
        }
    )
    db.add(audit)
    
    # Keep case status actioned/decided
    case.status = "actioned"
    db.commit()
    db.refresh(p2p)
    return p2p


@router.post("/{case_id}/optout")
def opt_out_customer(case_id: str, db: Session = Depends(get_db)):
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    case.opted_out = True
    db.commit()
    
    # Log to audit
    audit = AuditLogEntry(source='rule_engine', 
        case_id=case_id,
        step="outcome",
        payload={"message": "Customer has opted out of communication."}
    )
    db.add(audit)
    db.commit()
    
    return {"message": "Customer communication preference set to opted-out."}


@router.post("/{case_id}/reactivate")
def reactivate_case(case_id: str, override: bool = False, db: Session = Depends(get_db)):
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    # Check if the latest real failure diagnosis was a hard decline
    latest_real_diag = db.query(Diagnosis).filter(
        Diagnosis.case_id == case_id,
        Diagnosis.root_cause != "manual_reactivation"
    ).order_by(Diagnosis.created_at.desc()).first()
    
    is_hard_decline = latest_real_diag and latest_real_diag.severity == "hard"
    
    if is_hard_decline and not override:
        raise HTTPException(
            status_code=400,
            detail="Cannot reactivate hard decline case without explicit compliance override."
        )

    # Reset status
    case.status = "diagnosing"
    case.updated_at = datetime.utcnow()
    db.flush()
    
    # Log compliance override event if applicable
    has_compliance_override = is_hard_decline and override
    if has_compliance_override:
        audit_compliance = AuditLogEntry(
            source='rule_engine',
            case_id=case_id,
            step="guardrail_check",
            payload={
                "event": "compliance_override",
                "reason": "User manually bypassed hard-decline guardrail during reactivation.",
                "user": "finance_user",
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        db.add(audit_compliance)
        db.flush()

    # Generate manual reactivation diagnosis preserving original severity
    diag = Diagnosis(
        case_id=case_id,
        root_cause="manual_reactivation",
        severity="hard" if is_hard_decline else "soft",
        recovery_probability=0.0 if is_hard_decline else 0.50,
        reasoning="Recovery sequence manually reactivated by finance user." + (" (Explicit compliance override applied for hard decline)" if has_compliance_override else "")
    )
    db.add(diag)
    db.flush()
    
    diag_payload = {
        "diagnosis_id": diag.id,
        "root_cause": diag.root_cause,
        "severity": diag.severity,
        "recovery_probability": diag.recovery_probability,
        "reasoning": diag.reasoning,
        "source": "user_action"
    }
    if has_compliance_override:
        diag_payload["compliance_override"] = True

    audit_d = AuditLogEntry(
        source='rule_engine', 
        case_id=case_id,
        step="diagnosis",
        payload=diag_payload
    )
    db.add(audit_d)

    # Determine default action based on leak type
    if case.leak_type == "receivable_overdue":
        default_action = "send_email"
        default_channel = "email"
        decision_reasoning = "Manual reactivation decision: Escalating overdue invoice recovery via dunning email."
    else:
        default_action = "retry"
        default_channel = "none"
        decision_reasoning = "Manual reactivation decision: Initiating direct payment retry."

    # Decision
    dec = Decision(
        case_id=case_id,
        action=default_action,
        channel=default_channel,
        scheduled_for=datetime.utcnow(),
        reasoning=decision_reasoning
    )
    db.add(dec)
    db.flush()
    
    audit_dec = AuditLogEntry(
        source='rule_engine', 
        case_id=case_id,
        step="decision",
        payload={
            "decision_id": dec.id,
            "action": dec.action,
            "channel": dec.channel,
            "scheduled_for": dec.scheduled_for.isoformat(),
            "reasoning": dec.reasoning,
            "source": "user_action"
        }
    )
    db.add(audit_dec)
    db.commit()

    # Execute
    execute_recovery_action(db, case_id, dec.action, dec.channel, datetime.utcnow())
    return {"message": "Case recovery sequence successfully reactivated."}
