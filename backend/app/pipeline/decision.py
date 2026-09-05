import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any
from sqlalchemy.orm import Session
import httpx

# Anthropic Imports
from anthropic import (
    Anthropic,
    APIConnectionError as AnthropicAPIConnectionError,
    APITimeoutError as AnthropicAPITimeoutError,
    RateLimitError as AnthropicRateLimitError,
    InternalServerError as AnthropicInternalServerError,
)

# Gemini Imports
import google.generativeai as genai
from google.api_core.exceptions import (
    GoogleAPICallError,
    InternalServerError as GoogleInternalServerError,
    ServiceUnavailable as GoogleServiceUnavailable,
    GatewayTimeout as GoogleGatewayTimeout,
    ResourceExhausted as GoogleResourceExhausted,
)

# Groq Imports
from groq import (
    Groq,
    APIConnectionError as GroqAPIConnectionError,
    APITimeoutError as GroqAPITimeoutError,
    RateLimitError as GroqRateLimitError,
    InternalServerError as GroqInternalServerError,
)

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from backend.app.config import settings
from backend.app.models import Case, Diagnosis, Decision, AuditLogEntry, Action

logger = logging.getLogger(__name__)


def get_mock_decision(db: Session, case: Case, diagnosis: Diagnosis) -> Dict[str, Any]:
    """
    Deterministic rule-based decision matrix for fallback.
    """
    # 1. Check retry count
    retry_count = db.query(Action).filter(
        Action.case_id == case.id,
        Action.action_type == "retry",
        Action.status == "executed"
    ).count()

    # 2. Check if customer opted out
    if case.opted_out:
        if diagnosis.severity == "hard":
            return {
                "action": "escalate_human",
                "channel": "none",
                "delay_minutes": 0,
                "reasoning": "Customer has opted out of communication and case has a hard decline. Escalating to human finance team for offline handling."
            }
        else:
            if retry_count < settings.MAX_RETRY_ATTEMPTS:
                return {
                    "action": "retry",
                    "channel": "none",
                    "delay_minutes": 10,
                    "reasoning": f"Customer opted out of contact, but soft decline is eligible for auto-retry (attempts: {retry_count}/{settings.MAX_RETRY_ATTEMPTS}). Scheduling silent retry."
                }
            else:
                return {
                    "action": "escalate_human",
                    "channel": "none",
                    "delay_minutes": 0,
                    "reasoning": "Customer opted out of contact and retry attempts exhausted. Escalated to human."
                }

    # 3. Hard Decline Logic
    if diagnosis.severity == "hard":
        # Cannot retry, must email to update payment method or escalate
        if diagnosis.root_cause == "stolen_or_lost_card":
            return {
                "action": "escalate_human",
                "channel": "none",
                "delay_minutes": 0,
                "reasoning": "Card reported stolen/lost. Suspicious transaction flagged. Escalating immediately to fraud/support team."
            }
        else:
            return {
                "action": "send_email",
                "channel": "email",
                "delay_minutes": 5,
                "reasoning": f"Hard decline due to {diagnosis.root_cause}. Retrying is blocked. Sending notification to update card/payment details."
            }

    # 4. Soft Decline Logic
    if retry_count >= settings.MAX_RETRY_ATTEMPTS:
        return {
            "action": "escalate_human",
            "channel": "none",
            "delay_minutes": 0,
            "reasoning": f"Soft decline retry limit ({settings.MAX_RETRY_ATTEMPTS}) reached. Escalating to manual recovery."
        }

    if diagnosis.root_cause == "otp_validation_failed":
        # Retrying directly will fail because OTP is dynamic and requires input. Contact customer to finish payment.
        return {
            "action": "send_sms",
            "channel": "sms",
            "delay_minutes": 2,
            "reasoning": "OTP validation failed. Retrying card directly will fail. Sending SMS link for customer to retry manually."
        }
    
    if diagnosis.root_cause == "insufficient_funds":
        # Insufficient funds - retry with a slight delay (e.g. 1 hour or immediate email)
        if retry_count == 0:
            return {
                "action": "retry",
                "channel": "none",
                "delay_minutes": 60,
                "reasoning": "First failure due to insufficient funds. Scheduling a retry in 60 minutes to allow user to add balance."
            }
        else:
            return {
                "action": "send_email",
                "channel": "email",
                "delay_minutes": 5,
                "reasoning": "Subsequent failure due to insufficient funds. Sending warning email to customer to settle invoice."
            }

    # Default soft decline action: retry in 10 minutes
    return {
        "action": "retry",
        "channel": "none",
        "delay_minutes": 10,
        "reasoning": f"Soft decline ({diagnosis.root_cause}). Scheduling auto-retry attempt #{retry_count + 1}."
    }


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((
        AnthropicAPIConnectionError,
        AnthropicAPITimeoutError,
        AnthropicRateLimitError,
        AnthropicInternalServerError,
    ))
)
def _call_claude_decision_with_retry(client: Anthropic, prompt: str, tools: list) -> Any:
    return client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=1000,
        tools=tools,
        tool_choice={"type": "tool", "name": "record_decision"},
        messages=[{"role": "user", "content": prompt}],
        extra_body={"temperature": 0}
    )

@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((
        GoogleInternalServerError,
        GoogleServiceUnavailable,
        GoogleGatewayTimeout
    ))
)
def _call_gemini_decision_with_retry(prompt: str, tool: Any) -> Any:
    # Note: If quota issues persist, gemini-3.1-flash-lite or gemini-3.5-flash-lite are alternatives
    # with typically higher free daily limits, which can be set via the GEMINI_MODEL env var without touching code.
    model = genai.GenerativeModel(
        model_name=settings.GEMINI_MODEL,
        tools=[tool]
    )
    response = model.generate_content(
        prompt,
        tool_config={
            "function_calling_config": {
                "mode": "ANY",
                "allowed_function_names": ["record_decision"]
            }
        },
        generation_config={"temperature": 0.0}
    )
    return response

@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((
        GroqAPIConnectionError,
        GroqAPITimeoutError,
        GroqRateLimitError,
        GroqInternalServerError,
    ))
)
def _call_groq_decision_with_retry(client: Groq, prompt: str, tools: list) -> Any:
    return client.chat.completions.create(
        model=settings.GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        tools=tools,
        tool_choice={"type": "function", "function": {"name": "record_decision"}},
        temperature=0.0
    )

def get_claude_fallback_reason(e: Exception) -> str:
    err_str = str(e).lower()
    if any(kw in err_str for kw in ["quota", "rate", "429", "limit", "exhausted"]):
        return "claude_quota_exceeded"
    return "claude_api_error"

def get_gemini_fallback_reason(e: Exception) -> str:
    err_str = str(e).lower()
    if any(kw in err_str for kw in ["quota", "rate", "429", "limit", "exhausted"]):
        return "gemini_quota_exceeded"
    return "gemini_api_error"

def get_groq_fallback_reason(e: Exception) -> str:
    err_str = str(e).lower()
    if any(kw in err_str for kw in ["quota", "rate", "429", "limit", "exhausted"]):
        return "groq_quota_exceeded"
    return "groq_api_error"

def get_ollama_fallback_reason(e: Exception) -> str:
    err_str = str(e).lower()
    if isinstance(e, httpx.ConnectError) or "connection refused" in err_str or "connecterror" in err_str:
        return "ollama_unreachable"
    if isinstance(e, httpx.TimeoutException) or "timed out" in err_str or "timeout" in err_str:
        return "ollama_timeout"
    if "404" in err_str or "not found" in err_str:
        return "ollama_model_not_found"
    return "ollama_error"

def _call_ollama_decision(prompt: str, tools: list) -> Dict[str, Any]:
    url = f"{settings.OLLAMA_BASE_URL.rstrip('/')}/chat/completions"
    payload = {
        "model": settings.OLLAMA_MODEL,
        "messages": [
            {
                "role": "system",
                "content": "You are the Recovery Decision Agent for 'Retry'. Determine the intervention action. Always call the record_decision function or return valid JSON with keys: action, channel, delay_minutes, reasoning."
            },
            {"role": "user", "content": prompt}
        ],
        "tools": tools,
        "tool_choice": {"type": "function", "function": {"name": "record_decision"}},
        "temperature": 0.0
    }
    with httpx.Client(timeout=httpx.Timeout(connect=5.0, read=45.0, write=10.0, pool=5.0)) as client:
        resp = client.post(url, json=payload)
        resp.raise_for_status()
        res_json = resp.json()

    choice = res_json.get("choices", [{}])[0]
    msg = choice.get("message", {})
    if msg.get("tool_calls"):
        args = msg["tool_calls"][0]["function"]["arguments"]
        return json.loads(args) if isinstance(args, str) else args

    content = msg.get("content", "").strip()
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0].strip()
    elif "```" in content:
        content = content.split("```")[1].split("```")[0].strip()
    return json.loads(content)

def run_ai_decision(db: Session, case_id: str, now: datetime) -> Decision:
    """
    Invokes AI model providers sequentially in a prioritized fallback chain:
    1. Ollama (local, free, primary)
    2. Claude (Anthropic)
    3. Gemini (gemini-2.5-flash)
    4. Groq (llama-3.3-70b-versatile)
    5. Deterministic rules fallback
    """
    case = db.query(Case).filter(Case.id == case_id).first()
    diagnosis = db.query(Diagnosis).filter(Diagnosis.case_id == case_id).order_by(Diagnosis.created_at.desc()).first()
    
    if not case or not diagnosis:
        raise ValueError(f"Case {case_id} or Diagnosis not found in DB.")

    decision_data = None
    final_source = None
    final_payload_source = None
    fallbacks = []

    # Count retries
    retry_count = db.query(Action).filter(
        Action.case_id == case.id,
        Action.action_type == "retry",
        Action.status == "executed"
    ).count()

    prompt = f"""
    You are the Recovery Decision Agent for "Retry". Your job is to choose the optimal next action for a revenue leak case.
    
    Case Context:
    - Leak Type: {case.leak_type}
    - Amount: {case.amount} {case.currency}
    - Customer Reference: {case.customer_reference}
    - Opted Out of Communications: {case.opted_out}
    - Retry Count so far: {retry_count} / {settings.MAX_RETRY_ATTEMPTS}
    
    Diagnosis Context:
    - Root Cause: {diagnosis.root_cause}
    - Severity: {diagnosis.severity}
    - Recovery Probability: {diagnosis.recovery_probability}
    - Diagnosis Reasoning: {diagnosis.reasoning}
    
    Instructions:
    1. Call the `record_decision` tool with the action, channel, scheduling delay, and reasoning.
    2. Actions list: retry, send_email, send_sms, escalate_human, stop.
    3. Channels: email, sms, none.
    4. Hard declines (expired, closed, stolen) must never be auto-retried. If opted_out is false, email them or escalate to human. If opted_out is true, escalate to human or stop (no email/sms allowed!).
    5. Soft declines are eligible for retry. But if the retry cap ({settings.MAX_RETRY_ATTEMPTS}) is reached, you must escalate to human or stop.
    6. For OTP validation failures, direct retry will fail without user input. Contacting them (email/sms) is better.
    7. Delay minutes: Specify delay before action (e.g. 0 for immediate, 60 for 1 hour).
    """

    # 1. OLLAMA (Local, free, primary)
    if settings.OLLAMA_BASE_URL:
        try:
            ollama_tools = [
                {
                    "type": "function",
                    "function": {
                        "name": "record_decision",
                        "description": "Record the decision for recovery action.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "action": {
                                    "type": "string",
                                    "enum": ["retry", "send_email", "send_sms", "escalate_human", "stop"],
                                    "description": "The recovery action to take."
                                },
                                "channel": {
                                    "type": "string",
                                    "enum": ["email", "sms", "none"],
                                    "description": "Communication channel to use."
                                },
                                "delay_minutes": {
                                    "type": "integer",
                                    "minimum": 0,
                                    "description": "Number of minutes to wait before executing this action."
                                },
                                "reasoning": {
                                    "type": "string",
                                    "description": "Reasoning detailing why this action and channel was selected."
                                }
                            },
                            "required": ["action", "channel", "delay_minutes", "reasoning"]
                        }
                    }
                }
            ]
            dec = _call_ollama_decision(prompt, ollama_tools)
            if "action" in dec and "channel" in dec:
                act = str(dec["action"]).lower()
                for valid_act in ["retry", "send_email", "send_sms", "escalate_human", "stop"]:
                    if valid_act in act:
                        dec["action"] = valid_act
                        break
                ch = str(dec["channel"]).lower()
                for valid_ch in ["email", "sms", "none"]:
                    if valid_ch in ch:
                        dec["channel"] = valid_ch
                        break
                try:
                    dec["delay_minutes"] = int(dec.get("delay_minutes", 0))
                except Exception:
                    dec["delay_minutes"] = 0
                if "reasoning" not in dec:
                    dec["reasoning"] = f"Recovery decision by Ollama: {dec['action']} via {dec['channel']}"

                decision_data = dec
                final_source = "ollama_decision"
                final_payload_source = "ollama"
                logger.info("Ollama successfully decided case %s: %s", case_id, decision_data)
            else:
                raise ValueError("Ollama response missing required decision fields")
        except Exception as e:
            reason = get_ollama_fallback_reason(e)
            logger.error("Ollama decision failed for case %s with reason '%s': %s", case_id, reason, e)
            fallbacks.append({
                "provider": "ollama",
                "reason": reason,
                "error": str(e)
            })

    # 2. CLAUDE (Anthropic)
    if decision_data is None and settings.ANTHROPIC_API_KEY and not settings.ANTHROPIC_API_KEY.startswith("dummy"):
        try:
            headers = {
                "Accept-Encoding": "identity"
            }
            if settings.ANTHROPIC_WORKSPACE_ID:
                headers["anthropic-workspace-id"] = settings.ANTHROPIC_WORKSPACE_ID
            client = Anthropic(api_key=settings.ANTHROPIC_API_KEY, default_headers=headers)
            
            anthropic_tools = [
                {
                    "name": "record_decision",
                    "description": "Record the decision for recovery action.",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "action": {
                                "type": "string",
                                "enum": ["retry", "send_email", "send_sms", "escalate_human", "stop"],
                                "description": "The recovery action to take."
                            },
                            "channel": {
                                "type": "string",
                                "enum": ["email", "sms", "none"],
                                "description": "Communication channel to use."
                            },
                            "delay_minutes": {
                                "type": "integer",
                                "minimum": 0,
                                "description": "Number of minutes to wait before executing this action."
                            },
                            "reasoning": {
                                "type": "string",
                                "description": "Reasoning detailing why this action and channel was selected."
                            }
                        },
                        "required": ["action", "channel", "delay_minutes", "reasoning"]
                    }
                }
            ]
            
            message = _call_claude_decision_with_retry(client, prompt, anthropic_tools)
            tool_use = [block for block in message.content if block.type == "tool_use"][0]
            decision_data = tool_use.input
            final_source = "claude_decision"
            final_payload_source = "claude"
            logger.info("Claude successfully decided case %s: %s", case_id, decision_data)
        except Exception as e:
            reason = get_claude_fallback_reason(e)
            logger.error("Claude decision failed for case %s with reason '%s': %s", case_id, reason, e)
            fallbacks.append({
                "provider": "claude",
                "reason": reason,
                "error": str(e)
            })

    # 2. GEMINI (Google)
    if decision_data is None and settings.GEMINI_API_KEY and not settings.GEMINI_API_KEY.startswith("dummy"):
        try:
            genai.configure(api_key=settings.GEMINI_API_KEY)
            gemini_tool = genai.types.FunctionDeclaration(
                name="record_decision",
                description="Record the decision for recovery action.",
                parameters={
                    "type": "OBJECT",
                    "properties": {
                        "action": {
                            "type": "STRING",
                            "enum": ["retry", "send_email", "send_sms", "escalate_human", "stop"],
                            "description": "The recovery action to take."
                        },
                        "channel": {
                            "type": "STRING",
                            "enum": ["email", "sms", "none"],
                            "description": "Communication channel to use."
                        },
                        "delay_minutes": {
                            "type": "INTEGER",
                            "description": "Number of minutes to wait before executing this action."
                        },
                        "reasoning": {
                            "type": "STRING",
                            "description": "Reasoning detailing why this action and channel was selected."
                        }
                    },
                    "required": ["action", "channel", "delay_minutes", "reasoning"]
                }
            )
            response = _call_gemini_decision_with_retry(prompt, gemini_tool)
            function_call = response.candidates[0].content.parts[0].function_call
            decision_data = dict(function_call.args)
            if "delay_minutes" in decision_data:
                decision_data["delay_minutes"] = int(decision_data["delay_minutes"])
            final_source = "gemini_decision"
            final_payload_source = "gemini"
            logger.info("Gemini successfully decided case %s: %s", case_id, decision_data)
        except Exception as e:
            reason = get_gemini_fallback_reason(e)
            logger.error("Gemini decision failed for case %s with reason '%s': %s", case_id, reason, e)
            fallbacks.append({
                "provider": "gemini",
                "reason": reason,
                "error": str(e)
            })

    # 3. GROQ (Llama)
    if decision_data is None and settings.GROQ_API_KEY and not settings.GROQ_API_KEY.startswith("dummy"):
        try:
            groq_client = Groq(api_key=settings.GROQ_API_KEY)
            groq_tools = [
                {
                    "type": "function",
                    "function": {
                        "name": "record_decision",
                        "description": "Record the decision for recovery action.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "action": {
                                    "type": "string",
                                    "enum": ["retry", "send_email", "send_sms", "escalate_human", "stop"],
                                    "description": "The recovery action to take."
                                },
                                "channel": {
                                    "type": "string",
                                    "enum": ["email", "sms", "none"],
                                    "description": "Communication channel to use."
                                },
                                "delay_minutes": {
                                    "type": "integer",
                                    "description": "Number of minutes to wait before executing this action."
                                },
                                "reasoning": {
                                    "type": "string",
                                    "description": "Reasoning detailing why this action and channel was selected."
                                }
                            },
                            "required": ["action", "channel", "delay_minutes", "reasoning"]
                        }
                    }
                }
            ]
            response = _call_groq_decision_with_retry(groq_client, prompt, groq_tools)
            tool_call = response.choices[0].message.tool_calls[0]
            decision_data = json.loads(tool_call.function.arguments)
            if "delay_minutes" in decision_data:
                decision_data["delay_minutes"] = int(decision_data["delay_minutes"])
            final_source = "groq_decision"
            final_payload_source = "groq"
            logger.info("Groq successfully decided case %s: %s", case_id, decision_data)
        except Exception as e:
            reason = get_groq_fallback_reason(e)
            logger.error("Groq decision failed for case %s with reason '%s': %s", case_id, reason, e)
            fallbacks.append({
                "provider": "groq",
                "reason": reason,
                "error": str(e)
            })

    # 4. RULE-BASED FALLBACK
    if decision_data is None:
        decision_data = get_mock_decision(db, case, diagnosis)
        if len(fallbacks) > 0:
            final_source = "rule_engine_fallback"
            final_payload_source = "rule_engine_fallback"
        else:
            final_source = "rule_engine"
            final_payload_source = "rule_fallback"
        logger.info("Fell back to rules for case %s", case_id)

    scheduled_for = now + timedelta(minutes=decision_data.get("delay_minutes", 0))
    
    decision = Decision(
        case_id=case_id,
        action=decision_data["action"],
        channel=decision_data["channel"],
        scheduled_for=scheduled_for,
        reasoning=decision_data["reasoning"]
    )
    db.add(decision)
    db.flush()

    # Log to Audit Table
    audit = AuditLogEntry(
        case_id=case_id,
        step="decision",
        source=final_source,
        payload={
            "decision_id": decision.id,
            "action": decision.action,
            "channel": decision.channel,
            "scheduled_for": decision.scheduled_for.isoformat(),
            "reasoning": decision.reasoning,
            "source": final_payload_source,
            "fallbacks": fallbacks
        }
    )
    db.add(audit)
    db.commit()

    return decision

