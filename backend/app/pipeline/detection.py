import hmac
import hashlib
import json
import logging
import uuid
from datetime import datetime, timedelta
import random
from sqlalchemy.orm import Session
from backend.app.config import settings
from backend.app.models import Case, Event, AuditLogEntry, Action, PromiseToPay, Diagnosis, Decision, GuardrailCheck
from backend.app.pipeline.diagnosis import run_ai_diagnosis, DECLINE_RULES
from backend.app.pipeline.decision import run_ai_decision
from backend.app.pipeline.guardrails import run_all_guardrails

logger = logging.getLogger(__name__)

def verify_razorpay_signature(body: bytes, signature: str, secret: str) -> bool:
    """
    Verifies the signature of the webhook payload using the Razorpay secret.
    """
    if not signature or not secret:
        return False
    expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def process_webhook_payload(db: Session, payload: dict, now: datetime = None) -> Case:
    """
    Processes Razorpay webhook events (payment.failed, payment.captured) and transitions the case pipeline.
    """
    if now is None:
        now = datetime.utcnow()

    event_type = payload.get("event")
    event_id = payload.get("id", str(uuid.uuid4()))
    entity_data = payload.get("payload", {})
    
    if not event_type or not entity_data:
        raise ValueError("Invalid webhook payload format")

    if event_type == "payment.failed":
        payment_entity = entity_data.get("payment", {}).get("entity", {})
        payment_id = payment_entity.get("id")
        amount = float(payment_entity.get("amount", 0)) / 100.0  # Razorpay amount is in paise
        currency = payment_entity.get("currency", "INR")
        
        # Get failure reasons
        error_code = payment_entity.get("error_code", "UNKNOWN_ERROR")
        error_desc = payment_entity.get("error_description", "Unknown payment failure occurred")
        
        # Retrieve customer reference
        customer_email = payment_entity.get("email")
        customer_phone = payment_entity.get("contact")
        customer_ref = payment_entity.get("customer_id") or customer_email or customer_phone or "unknown_customer"
        
        # Check if customer has opted out from metadata
        metadata = payment_entity.get("notes", {})
        opted_out = str(metadata.get("opted_out", "false")).lower() == "true"
        
        # 1. Edge Case: Coordinated Outreach
        # Look for an active case (detected/diagnosing/decided/blocked/actioned) for this customer in last 24h
        time_limit = now - timedelta(hours=24)
        active_case = db.query(Case).filter(
            Case.customer_reference == customer_ref,
            Case.leak_type == "payment_failure",
            Case.status.in_(["detected", "diagnosing", "decided", "blocked", "actioned"]),
            Case.created_at >= time_limit
        ).order_by(Case.created_at.desc()).first()
        
        if active_case:
            logger.info("Found active case %s for customer %s in last 24h. Linking event.", active_case.id, customer_ref)
            case = active_case
            # Link event
            event = Event(case_id=case.id, event_type=event_type, payload=payload, created_at=now)
            db.add(event)
            db.flush()
            
            # Log detection to AuditLogEntry
            audit = AuditLogEntry(
                case_id=case.id,
                step="detection",
                payload={"event_id": event_id, "event_type": event_type, "payment_id": payment_id, "linked_to_existing": True}
            )
            db.add(audit)
            db.commit()
            
            # We don't trigger a new pipeline run automatically if one is already scheduled or completed,
            # but we record the duplicate event. Let's return the case.
            return case

        # 2. Create a new case
        case = Case(
            leak_type="payment_failure",
            status="detected",
            customer_reference=customer_ref,
            customer_email=customer_email,
            customer_phone=customer_phone,
            opted_out=opted_out,
            amount=amount,
            currency=currency,
            created_at=now,
            updated_at=now
        )
        db.add(case)
        db.flush() # get ID
        
        event = Event(case_id=case.id, event_type=event_type, payload=payload, created_at=now)
        db.add(event)
        
        audit = AuditLogEntry(
            case_id=case.id,
            step="detection",
            payload={"event_id": event_id, "event_type": event_type, "payment_id": payment_id, "new_case_created": True}
        )
        db.add(audit)
        db.commit()

        # Run pipeline stages for the new case:
        run_full_recovery_pipeline(db, case.id, error_code, error_desc, now)
        return case

    elif event_type == "payment.captured":
        payment_entity = entity_data.get("payment", {}).get("entity", {})
        captured_amount = float(payment_entity.get("amount", 0)) / 100.0
        customer_email = payment_entity.get("email")
        customer_phone = payment_entity.get("contact")
        customer_ref = payment_entity.get("customer_id") or customer_email or customer_phone or "unknown_customer"
        
        # Look for an active case for this customer
        active_case = db.query(Case).filter(
            Case.customer_reference == customer_ref,
            Case.status.in_(["detected", "diagnosing", "decided", "blocked", "actioned"])
        ).order_by(Case.created_at.desc()).first()
        
        if active_case:
            case = active_case
            event = Event(case_id=case.id, event_type=event_type, payload=payload, created_at=now)
            db.add(event)
            db.flush()

            # Record recovered amount
            case.recovered_amount = captured_amount
            
            # Check if recovery was caused by agent action
            # Agent action is any executed communication outreach before now
            agent_actions = db.query(Action).filter(
                Action.case_id == case.id,
                Action.status == "executed",
                Action.action_type.in_(["send_email", "send_sms"])
            ).count()
            
            recovered_by_agent = agent_actions > 0
            
            # Determine success status (full or partial)
            # A partial payment is tracked distinctly from a full recovery
            is_partial = captured_amount < case.amount
            
            case.status = "recovered"
            case.updated_at = now
            
            # Log outcome to AuditLogEntry
            audit = AuditLogEntry(
                case_id=case.id,
                step="outcome",
                payload={
                    "event_id": event_id,
                    "event_type": event_type,
                    "captured_amount": captured_amount,
                    "case_amount": case.amount,
                    "is_partial_recovery": is_partial,
                    "recovered_by_agent": recovered_by_agent,
                    "executed_actions_count": agent_actions
                }
            )
            db.add(audit)
            
            # Resolve PromiseToPay if exists
            p2p = db.query(PromiseToPay).filter(
                PromiseToPay.case_id == case.id,
                PromiseToPay.status == "pending"
            ).first()
            if p2p:
                p2p.status = "kept" if not is_partial else "pending"  # If partial, keep P2P pending or update logic
                logger.info("PromiseToPay updated to kept for case %s", case.id)
                
            db.commit()
            return case
            
        else:
            logger.info("Received payment.captured for customer %s, but no active recovery case exists.", customer_ref)
            return None
            
    return None


def run_full_recovery_pipeline(db: Session, case_id: str, error_code: str, error_desc: str, now: datetime) -> None:
    """
    Synchronously triggers Diagnosis and Decision. Guardrails and Execution are triggered next if immediate, 
    otherwise scheduled for later.
    """
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        return

    # 1. Diagnosis
    case.status = "diagnosing"
    db.commit()
    diagnosis = run_ai_diagnosis(db, case.id, error_code, error_desc)

    # 2. Decision
    case.status = "decided"
    db.commit()
    decision = run_ai_decision(db, case.id, now)

    # 3. Process the Decision (Guardrails & Execution)
    # If decision execution time is <= now, run it immediately. Otherwise, schedule it.
    if decision.scheduled_for <= now:
        execute_recovery_action(db, case.id, decision.action, decision.channel, now)
    else:
        # Create a pending action to be picked up by the scheduler
        action = Action(
            case_id=case.id,
            action_type=decision.action,
            channel=decision.channel,
            status="pending",
            executed_at=None,
            outcome="Scheduled for later execution"
        )
        db.add(action)
        db.commit()
        logger.info("Action %s scheduled for case %s at %s", decision.action, case.id, decision.scheduled_for)


def execute_recovery_action(db: Session, case_id: str, action_type: str, channel: str, now: datetime) -> Action:
    """
    Gates an action behind Guardrails. If passed, executes. If blocked, logs and marks blocked.
    """
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise ValueError(f"Case {case_id} not found")

    # Log guardrail start
    audit_g = AuditLogEntry(
        case_id=case_id,
        step="guardrail_check",
        payload={"action_type": action_type, "channel": channel, "check_time": now.isoformat()}
    )
    db.add(audit_g)
    db.flush()

    # 1. Run Guardrails
    all_passed, checks = run_all_guardrails(db, case_id, action_type, now)
    
    # Save GuardrailCheck records
    for check in checks:
        gc = GuardrailCheck(
            case_id=case_id,
            rule_name=check["rule_name"],
            passed=check["passed"],
            reason=check["reason"]
        )
        db.add(gc)
        
    # Append checks detailed results to the audit log entry payload
    audit_g.payload = {
        **audit_g.payload,
        "all_passed": all_passed,
        "checks": checks
    }

    action = Action(
        case_id=case_id,
        action_type=action_type,
        channel=channel,
        created_at=now
    )

    if not all_passed:
        # Blocked by guardrails
        case.status = "blocked"
        action.status = "blocked"
        action.executed_at = now
        action.outcome = "Blocked by guardrails: " + ", ".join([c["reason"] for c in checks if not c["passed"]])
        
        db.add(action)
        db.commit()
        
        # Log outcome
        audit_out = AuditLogEntry(
            case_id=case_id,
            step="outcome",
            payload={"action_type": action_type, "status": "blocked", "reason": action.outcome}
        )
        db.add(audit_out)
        db.commit()
        
        logger.warning("Action %s for case %s blocked by guardrails.", action_type, case_id)
        return action

    # 2. Execution (Simulated Sandbox)
    action.status = "executed"
    action.executed_at = now
    
    # Check if case was already recovered independently before execution
    if case.status == "recovered":
        if action_type == "retry":
            action.outcome = "Retry attempted; payment had already independently succeeded"
        else:
            action.outcome = "Outreach skipped; payment had already independently succeeded"
            
        db.add(action)
        db.commit()
        
        audit_out = AuditLogEntry(
            case_id=case_id,
            step="outcome",
            payload={"action_type": action_type, "status": "no_action_needed", "reason": "Payment already resolved independently"}
        )
        db.add(audit_out)
        db.commit()
        return action
    
    # Simulate based on type
    if action_type == "retry":
        # Simulate payment retry. Let's make it have a 40% success rate on soft retries.
        retry_success = random.random() < 0.40
        if retry_success:
            action.outcome = "Payment retry successful. Payment ID: pay_" + str(uuid.uuid4())[:8]
            case.status = "recovered"
            case.recovered_amount = case.amount
            
            # Log outcome audit
            audit_out = AuditLogEntry(
                case_id=case_id,
                step="outcome",
                payload={"action_type": "retry", "status": "success", "recovered_amount": case.amount, "recovered_by_agent": True}
            )
            db.add(audit_out)
            
            # Keep P2P marked kept
            p2p = db.query(PromiseToPay).filter(PromiseToPay.case_id == case.id, PromiseToPay.status == "pending").first()
            if p2p:
                p2p.status = "kept"
        else:
            action.outcome = "Payment retry failed: BAD_REQUEST_PAYMENT_DECLINED_BY_BANK"
            case.status = "actioned"  # stays active
            audit_out = AuditLogEntry(
                case_id=case_id,
                step="outcome",
                payload={"action_type": "retry", "status": "failed", "error": "BAD_REQUEST_PAYMENT_DECLINED_BY_BANK"}
            )
            db.add(audit_out)
            
    elif action_type == "send_email":
        action.outcome = f"Email sent via Resend Sandbox to {case.customer_email or 'customer@business.com'} with payment link."
        case.status = "actioned"
        audit_out = AuditLogEntry(
            case_id=case_id,
            step="outcome",
            payload={"action_type": "send_email", "status": "sent", "channel": "email"}
        )
        db.add(audit_out)
        
    elif action_type == "send_sms":
        action.outcome = f"SMS sent via Twilio Sandbox to {case.customer_phone or '+919999999999'} with quick-pay link."
        case.status = "actioned"
        audit_out = AuditLogEntry(
            case_id=case_id,
            step="outcome",
            payload={"action_type": "send_sms", "status": "sent", "channel": "sms"}
        )
        db.add(audit_out)
        
    elif action_type == "escalate_human":
        action.outcome = "Ticket escalated to human finance desk. Assigned to operations queue."
        case.status = "escalated"
        audit_out = AuditLogEntry(
            case_id=case_id,
            step="outcome",
            payload={"action_type": "escalate_human", "status": "escalated"}
        )
        db.add(audit_out)
        
    elif action_type == "stop":
        action.outcome = "Recovery sequence stopped. Case marked dead."
        case.status = "stop"  # We can map status to escalate/stop
        audit_out = AuditLogEntry(
            case_id=case_id,
            step="outcome",
            payload={"action_type": "stop", "status": "stopped"}
        )
        db.add(audit_out)

    db.add(action)
    db.commit()
    logger.info("Executed action %s for case %s. Outcome: %s", action_type, case_id, action.outcome)
    return action


# ----------------- Seeder Helper -----------------

DEMO_CUSTOMERS = [
    {"ref": "cust_9812", "email": "alex.green@gmail.com", "phone": "+919876543210"},
    {"ref": "cust_3490", "email": "priya.sharma@yahoo.co.in", "phone": "+918888888888"},
    {"ref": "cust_5124", "email": "sam.altman@openai.com", "phone": "+14155552671"},
    {"ref": "cust_0918", "email": "michael.jordan@bulls.com", "phone": "+13125559823"},
    {"ref": "cust_7721", "email": "sarah.connor@cyberdyne.net", "phone": "+12135558482"},
    {"ref": "cust_3311", "email": "bruce.wayne@waynecorp.com", "phone": "+19085552399"},
    {"ref": "cust_5599", "email": "elon.musk@x.com", "phone": "+15125554242"},
    {"ref": "cust_8213", "email": "taylor.swift@republic.com", "phone": "+16155551989"},
    {"ref": "cust_0092", "email": "rahul.dravid@bcci.tv", "phone": "+917777777777"},
    {"ref": "cust_6234", "email": "tony.stark@starkindustries.com", "phone": "+12125553000"}
]

def seed_demo_cases(db: Session, num_cases: int) -> list[Case]:
    """
    Seeds the database with various cases processing them through the pipeline.
    """
    # Clear old data to avoid cluttering in test mode
    db.query(GuardrailCheck).delete()
    db.query(Action).delete()
    db.query(Decision).delete()
    db.query(Diagnosis).delete()
    db.query(AuditLogEntry).delete()
    db.query(PromiseToPay).delete()
    db.query(Event).delete()
    db.query(Case).delete()
    db.commit()

    created_cases = []
    now = datetime.utcnow()

    # Generate a variety of cases
    for i in range(num_cases):
        cust = random.choice(DEMO_CUSTOMERS)
        
        # Ensure distinct references to avoid instant 24h collision unless we explicitly test for it
        customer_ref = f"{cust['ref']}_{i}"
        
        # Random failures
        failure_code = random.choice(list(DECLINE_RULES.keys()))
        failure_desc = f"Failed transaction retry simulation due to {failure_code.replace('_', ' ').lower()}."
        amount = round(random.uniform(10.0, 5000.0), 2)
        
        # Some customers opted out
        opted_out = random.random() < 0.15 # 15% opt-out
        
        # Create a mock webhook payload
        payload = {
            "event": "payment.failed",
            "id": f"evt_{str(uuid.uuid4())[:18]}",
            "payload": {
                "payment": {
                    "entity": {
                        "id": f"pay_{str(uuid.uuid4())[:18]}",
                        "amount": int(amount * 100),
                        "currency": "INR",
                        "email": cust["email"],
                        "contact": cust["phone"],
                        "customer_id": customer_ref,
                        "error_code": failure_code,
                        "error_description": failure_desc,
                        "notes": {
                            "opted_out": "true" if opted_out else "false"
                        }
                    }
                }
            }
        }
        
        # Make timestamps spread across last 7 days
        days_ago = random.uniform(0.1, 7.0)
        case_time = now - timedelta(days=days_ago)
        
        # Run detection and pipeline processing
        case = process_webhook_payload(db, payload, now=case_time)
        
        # Let's simulate some cases succeeding later (self-recovered vs agent-recovered)
        if case.status in ["actioned", "decided", "blocked"]:
            success_chance = random.random()
            if success_chance < 0.35: # 35% success
                # Simulate success webhook
                success_payload = {
                    "event": "payment.captured",
                    "id": f"evt_{str(uuid.uuid4())[:18]}",
                    "payload": {
                        "payment": {
                            "entity": {
                                "id": f"pay_{str(uuid.uuid4())[:18]}",
                                "amount": int(amount * 100),
                                "currency": "INR",
                                "email": cust["email"],
                                "contact": cust["phone"],
                                "customer_id": customer_ref
                            }
                        }
                    }
                }
                
                # Successful payment occurs 1 hour to 1 day later
                payment_time = case_time + timedelta(hours=random.uniform(1, 24))
                process_webhook_payload(db, success_payload, now=payment_time)
                
            elif success_chance < 0.45: # 10% partial success
                partial_amount = round(amount * random.choice([0.25, 0.50, 0.75]), 2)
                success_payload = {
                    "event": "payment.captured",
                    "id": f"evt_{str(uuid.uuid4())[:18]}",
                    "payload": {
                        "payment": {
                            "entity": {
                                "id": f"pay_{str(uuid.uuid4())[:18]}",
                                "amount": int(partial_amount * 100),
                                "currency": "INR",
                                "email": cust["email"],
                                "contact": cust["phone"],
                                "customer_id": customer_ref
                            }
                        }
                    }
                }
                payment_time = case_time + timedelta(hours=random.uniform(1, 24))
                process_webhook_payload(db, success_payload, now=payment_time)

        # Seed some B2B Promise to Pay for receivable overdue cases
        if random.random() < 0.25: # 25% of cases get B2B Promise to Pay
            b2b_amount = round(random.uniform(10.0, 5000.0), 2)
            # Create a receivable case
            b2b_case = Case(
                leak_type="receivable_overdue",
                status="detected",
                customer_reference=customer_ref,
                customer_email=cust["email"],
                customer_phone=cust["phone"],
                opted_out=opted_out,
                amount=b2b_amount,
                currency="INR",
                created_at=case_time,
                updated_at=case_time
            )
            db.add(b2b_case)
            db.flush()
            
            # Create Promise-to-Pay
            # 50% broken, 30% pending, 20% kept
            p2p_status = random.choice(["broken", "pending", "kept"])
            # Promised date
            if p2p_status == "broken":
                promised_date = case_time + timedelta(days=2) # Already passed
            elif p2p_status == "pending":
                promised_date = now + timedelta(days=3) # Future
            else:
                promised_date = case_time + timedelta(days=1)
                
            p2p = PromiseToPay(
                case_id=b2b_case.id,
                promised_date=promised_date,
                promised_amount=b2b_amount,
                status=p2p_status,
                created_at=case_time
            )
            db.add(p2p)
            
            # Create Diagnosis and Decision records for B2B cases based on Promise status
            if p2p_status == "kept":
                b2b_case.status = "recovered"
                b2b_case.recovered_amount = b2b_amount
                
                diagnosis = Diagnosis(
                    case_id=b2b_case.id,
                    root_cause="promise_to_pay_kept",
                    severity="soft",
                    recovery_probability=1.0,
                    reasoning="B2B customer successfully kept the Promise-to-Pay. Reconciling transaction."
                )
                db.add(diagnosis)
                db.flush()
                
                audit_diag = AuditLogEntry(source='rule_engine', 
                    case_id=b2b_case.id,
                    step="diagnosis",
                    payload={
                        "diagnosis_id": diagnosis.id,
                        "root_cause": diagnosis.root_cause,
                        "severity": diagnosis.severity,
                        "recovery_probability": diagnosis.recovery_probability,
                        "reasoning": diagnosis.reasoning,
                        "source": "rule_promise_seeder"
                    }
                )
                db.add(audit_diag)
                db.flush()
                
                decision = Decision(
                    case_id=b2b_case.id,
                    action="stop",
                    channel="none",
                    scheduled_for=case_time,
                    reasoning="Receivable settled. Closing recovery case."
                )
                db.add(decision)
                db.flush()
                
                audit_dec = AuditLogEntry(source='rule_engine', 
                    case_id=b2b_case.id,
                    step="decision",
                    payload={
                        "decision_id": decision.id,
                        "action": decision.action,
                        "channel": decision.channel,
                        "scheduled_for": decision.scheduled_for.isoformat(),
                        "reasoning": decision.reasoning,
                        "source": "rule_promise_seeder"
                    }
                )
                db.add(audit_dec)
                db.flush()
                
            elif p2p_status == "pending":
                b2b_case.status = "actioned"
                
                diagnosis = Diagnosis(
                    case_id=b2b_case.id,
                    root_cause="promise_to_pay_pending",
                    severity="soft",
                    recovery_probability=0.70,
                    reasoning="B2B invoice remains open but customer registered a active Promise-to-Pay."
                )
                db.add(diagnosis)
                db.flush()
                
                audit_diag = AuditLogEntry(source='rule_engine', 
                    case_id=b2b_case.id,
                    step="diagnosis",
                    payload={
                        "diagnosis_id": diagnosis.id,
                        "root_cause": diagnosis.root_cause,
                        "severity": diagnosis.severity,
                        "recovery_probability": diagnosis.recovery_probability,
                        "reasoning": diagnosis.reasoning,
                        "source": "rule_promise_seeder"
                    }
                )
                db.add(audit_diag)
                db.flush()
                
                decision = Decision(
                    case_id=b2b_case.id,
                    action="stop",
                    channel="none",
                    scheduled_for=case_time,
                    reasoning="Active Promise-to-Pay exists. Outreach gated."
                )
                db.add(decision)
                db.flush()
                
                audit_dec = AuditLogEntry(source='rule_engine', 
                    case_id=b2b_case.id,
                    step="decision",
                    payload={
                        "decision_id": decision.id,
                        "action": decision.action,
                        "channel": decision.channel,
                        "scheduled_for": decision.scheduled_for.isoformat(),
                        "reasoning": decision.reasoning,
                        "source": "rule_promise_seeder"
                    }
                )
                db.add(audit_dec)
                db.flush()
                
            else: # broken
                # Reactivate recovery sequence!
                b2b_case.status = "diagnosing"
                db.flush()
                # Run AI/Rule Diagnosis & Decision for B2B receivable
                diagnosis = Diagnosis(
                    case_id=b2b_case.id,
                    root_cause="broken_promise_to_pay",
                    severity="soft",
                    recovery_probability=0.30,
                    reasoning="The B2B customer promised to pay by " + promised_date.strftime("%Y-%m-%d") + " but no transaction was received. Sequence reactivated."
                )
                db.add(diagnosis)
                db.flush()
                
                audit_diag = AuditLogEntry(source='rule_engine', 
                    case_id=b2b_case.id,
                    step="diagnosis",
                    payload={
                        "diagnosis_id": diagnosis.id,
                        "root_cause": diagnosis.root_cause,
                        "severity": diagnosis.severity,
                        "recovery_probability": diagnosis.recovery_probability,
                        "reasoning": diagnosis.reasoning,
                        "source": "rule_promise_seeder"
                    }
                )
                db.add(audit_diag)
                db.flush()
                
                decision = Decision(
                    case_id=b2b_case.id,
                    action="send_email",
                    channel="email",
                    scheduled_for=now,
                    reasoning="Promise to pay broken. Re-initiating dunning sequence via email."
                )
                db.add(decision)
                db.flush()
                
                audit_dec = AuditLogEntry(source='rule_engine', 
                    case_id=b2b_case.id,
                    step="decision",
                    payload={
                        "decision_id": decision.id,
                        "action": decision.action,
                        "channel": decision.channel,
                        "scheduled_for": decision.scheduled_for.isoformat(),
                        "reasoning": decision.reasoning,
                        "source": "rule_promise_seeder"
                    }
                )
                db.add(audit_dec)
                db.flush()
                
                # Execute action
                execute_recovery_action(db, b2b_case.id, "send_email", "email", now)
        
        db.commit()
        created_cases.append(case)
        
    db.commit()
    return created_cases
