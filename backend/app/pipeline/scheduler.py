import logging
from datetime import datetime
from sqlalchemy.orm import Session
from backend.app.models import Case, Action, PromiseToPay, Diagnosis, Decision, AuditLogEntry
from backend.app.pipeline.detection import execute_recovery_action

logger = logging.getLogger(__name__)

def sweep_scheduled_actions(db: Session, now: datetime = None) -> int:
    """
    Finds pending Actions scheduled for now or in the past, and executes them.
    """
    if now is None:
        now = datetime.utcnow()

    # Find pending actions
    # An action is pending if it has status 'pending'
    # We should look up the Decision scheduled_for to make sure we only execute after that time.
    pending_actions = db.query(Action).filter(
        Action.status == "pending"
    ).all()

    executed_count = 0
    for action in pending_actions:
        # Check corresponding decision
        decision = db.query(Decision).filter(
            Decision.case_id == action.case_id
        ).order_by(Decision.created_at.desc()).first()
        
        if decision and decision.scheduled_for <= now:
            logger.info("Scheduler executing action %s for case %s", action.action_type, action.case_id)
            # Delete the temporary pending action placeholder, as execute_recovery_action creates a new Action record
            db.delete(action)
            db.flush()
            
            execute_recovery_action(db, decision.case_id, decision.action, decision.channel, now)
            executed_count += 1
            
    db.commit()
    return executed_count


def check_and_reactivate_promises(db: Session, now: datetime = None) -> int:
    """
    Checks for pending PromiseToPay records that are past their promised_date.
    If no payment has been received, marks the promise as broken and reactivates the recovery sequence.
    """
    if now is None:
        now = datetime.utcnow()

    # Find pending promises in the past
    overdue_promises = db.query(PromiseToPay).filter(
        PromiseToPay.status == "pending",
        PromiseToPay.promised_date < now
    ).all()

    reactivated_count = 0
    for promise in overdue_promises:
        case = db.query(Case).filter(Case.id == promise.case_id).first()
        if not case:
            continue
            
        # Double check if case was recovered in the meantime
        if case.status == "recovered" or case.recovered_amount >= promise.promised_amount:
            promise.status = "kept"
            continue

        # Mark promise as broken
        promise.status = "broken"
        logger.info("Promise to Pay %s expired. Marking as broken.", promise.id)
        
        # Log to Audit Log
        audit_p = AuditLogEntry(source='rule_engine', 
            case_id=case.id,
            step="outcome",
            payload={"promise_id": promise.id, "status": "broken", "reason": "Promised date passed without payment."}
        )
        db.add(audit_p)
        db.flush()
        
        # Reactivate recovery sequence!
        case.status = "diagnosing"
        case.updated_at = now
        db.flush()

        # Diagnosis step
        diag = Diagnosis(
            case_id=case.id,
            root_cause="broken_promise_to_pay",
            severity="soft",
            recovery_probability=0.30,
            reasoning=f"The B2B customer promised to pay {promise.promised_amount} by {promise.promised_date.strftime('%Y-%m-%d %H:%M:%S')}, but no payment was received. Sequence reactivated."
        )
        db.add(diag)
        db.flush()
        
        audit_diag = AuditLogEntry(source='rule_engine', 
            case_id=case.id,
            step="diagnosis",
            payload={
                "diagnosis_id": diag.id,
                "root_cause": diag.root_cause,
                "severity": diag.severity,
                "recovery_probability": diag.recovery_probability,
                "reasoning": diag.reasoning,
                "source": "rule_promise_reactivation"
            }
        )
        db.add(audit_diag)
        db.flush()

        # Decision step
        dec = Decision(
            case_id=case.id,
            action="send_email",
            channel="email",
            scheduled_for=now,
            reasoning="Promise to pay was broken. Escalating outreach via dunning email."
        )
        db.add(dec)
        db.flush()

        audit_dec = AuditLogEntry(source='rule_engine', 
            case_id=case.id,
            step="decision",
            payload={
                "decision_id": dec.id,
                "action": dec.action,
                "channel": dec.channel,
                "scheduled_for": dec.scheduled_for.isoformat(),
                "reasoning": dec.reasoning,
                "source": "rule_promise_reactivation"
            }
        )
        db.add(audit_dec)
        db.commit()

        # Execute action
        execute_recovery_action(db, case.id, dec.action, dec.channel, now)
        reactivated_count += 1

    db.commit()
    return reactivated_count
