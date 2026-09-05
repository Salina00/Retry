import json
import logging
from typing import Dict, Any, Tuple
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
from backend.app.models import Case, Diagnosis, AuditLogEntry


logger = logging.getLogger(__name__)

# Standard Razorpay decline code mapping for mock fallback and prompt context
DECLINE_RULES = {
    "BAD_REQUEST_PAYMENT_INSUFFICIENT_FUNDS": {
        "root_cause": "insufficient_funds",
        "severity": "soft",
        "recovery_probability": 0.80,
        "reasoning": "The transaction was declined due to insufficient funds in the account. This is a soft decline. Retrying or prompting the user to reload their account is appropriate."
    },
    "BAD_REQUEST_PAYMENT_CARD_EXPIRED": {
        "root_cause": "expired_card",
        "severity": "hard",
        "recovery_probability": 0.25,
        "reasoning": "The card used has expired. This is a hard decline. Auto-retries will fail. The customer must be contacted to update their payment method."
    },
    "BAD_REQUEST_PAYMENT_CARD_STOLEN_OR_LOST": {
        "root_cause": "stolen_or_lost_card",
        "severity": "hard",
        "recovery_probability": 0.05,
        "reasoning": "The card has been reported stolen or lost. This is a hard decline. Retrying is blocked due to security guardrails. Escalate for human fraud/support review."
    },
    "BAD_REQUEST_PAYMENT_CARD_CLOSED": {
        "root_cause": "closed_account",
        "severity": "hard",
        "recovery_probability": 0.05,
        "reasoning": "The card account is closed. This is a hard decline. Retrying is blocked. The customer must provide a different payment method."
    },
    "BAD_REQUEST_PAYMENT_BANK_SYSTEM_OUTAGE": {
        "root_cause": "bank_system_outage",
        "severity": "soft",
        "recovery_probability": 0.90,
        "reasoning": "The issuing bank is experiencing a system outage. This is a temporary soft decline. Retrying later is highly likely to succeed."
    },
    "BAD_REQUEST_PAYMENT_TIMED_OUT": {
        "root_cause": "gateway_timeout",
        "severity": "soft",
        "recovery_probability": 0.85,
        "reasoning": "The payment timed out during processing. This is a temporary network or bank communication timeout. Safe to retry."
    },
    "BAD_REQUEST_PAYMENT_OTP_VALIDATION_FAILED": {
        "root_cause": "otp_validation_failed",
        "severity": "soft",
        "recovery_probability": 0.70,
        "reasoning": "The OTP entered by the customer was incorrect or timed out. This is a soft decline. Direct customer outreach (email/sms) is recommended to prompt them to retry."
    },
    "BAD_REQUEST_PAYMENT_DECLINED_BY_BANK": {
        "root_cause": "generic_bank_decline",
        "severity": "soft",
        "recovery_probability": 0.50,
        "reasoning": "The bank declined the transaction without specifying a granular reason. Since it is unspecified, we categorize as soft, but limit retries and offer manual channels."
    }
}

def get_mock_diagnosis(failure_code: str, failure_description: str) -> Dict[str, Any]:
    """Generates a structured mock diagnosis based on known Razorpay failure codes."""
    rule = DECLINE_RULES.get(failure_code)
    if rule:
        return rule
    
    # Default fallback for unknown failure codes
    return {
        "root_cause": "unrecognized_decline",
        "severity": "hard",
        "recovery_probability": 0.0,
        "reasoning": f"Unrecognized Razorpay decline code: {failure_code} ({failure_description}). Flagged for immediate human escalation."
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
def _call_claude_diagnosis_with_retry(client: Anthropic, prompt: str, tools: list) -> Any:
    return client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=1000,
        tools=tools,
        tool_choice={"type": "tool", "name": "record_diagnosis"},
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
def _call_gemini_diagnosis_with_retry(prompt: str, tool: Any) -> Any:
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
                "allowed_function_names": ["record_diagnosis"]
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
def _call_groq_diagnosis_with_retry(client: Groq, prompt: str, tools: list) -> Any:
    return client.chat.completions.create(
        model=settings.GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        tools=tools,
        tool_choice={"type": "function", "function": {"name": "record_diagnosis"}},
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

def _call_ollama_diagnosis(prompt: str, tools: list) -> Dict[str, Any]:
    url = f"{settings.OLLAMA_BASE_URL.rstrip('/')}/chat/completions"
    payload = {
        "model": settings.OLLAMA_MODEL,
        "messages": [
            {
                "role": "system",
                "content": "You are the Revenue Diagnosis Agent for 'Retry'. Diagnose the payment failure. Always call the record_diagnosis function or return valid JSON with keys: root_cause, severity, recovery_probability, reasoning."
            },
            {"role": "user", "content": prompt}
        ],
        "tools": tools,
        "tool_choice": {"type": "function", "function": {"name": "record_diagnosis"}},
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

def run_ai_diagnosis(db: Session, case_id: str, failure_code: str, failure_description: str) -> Diagnosis:
    """
    Invokes AI model providers sequentially in a prioritized fallback chain:
    1. Ollama (local, free, primary)
    2. Claude (Anthropic)
    3. Gemini (gemini-2.5-flash)
    4. Groq (llama-3.3-70b-versatile)
    5. Deterministic rules fallback
    """
    diagnosis_data = None
    final_source = None
    final_payload_source = None
    fallbacks = []

    prompt = f"""
    You are the Revenue Diagnosis Agent for "Retry". Your task is to diagnose a payment failure.
    
    Payment Failure Information:
    - Razorpay Failure Code: {failure_code}
    - Razorpay Description: {failure_description}
    
    Instructions:
    1. Call the `record_diagnosis` tool with the appropriate root cause category, severity classification, recovery probability (0.0 to 1.0), and detailed reasoning.
    2. Distinguish soft declines (temporary, e.g., insufficient funds, network timeouts, bank outages - safe to retry) from hard declines (expired card, stolen card, closed account - must NOT be retried).
    3. Guideline Mappings:
       - If the failure code maps to generic bank decline (e.g. BAD_REQUEST_PAYMENT_DECLINED_BY_BANK), you MUST classify it as 'generic_bank_decline', severity 'soft', and recovery probability 0.50.
       - If the failure code is insufficient funds, classify it as 'insufficient_funds', severity 'soft', and recovery probability 0.80.
       - If the failure code is card expired, classify it as 'expired_card', severity 'hard', and recovery probability 0.0.
       - If the failure code is stolen or lost card, classify it as 'stolen_or_lost_card', severity 'hard', and recovery probability 0.0.
       - If the failure code is card closed, classify it as 'closed_account', severity 'hard', and recovery probability 0.0.
       - If the failure code is bank system outage, classify it as 'bank_system_outage', severity 'soft', and recovery probability 0.85.
       - If the failure code is network or gateway timeout, classify it as 'gateway_timeout', severity 'soft', and recovery probability 0.85.
       - If the failure code is OTP validation failed, classify it as 'otp_validation_failed', severity 'soft', and recovery probability 0.60.
    
    Use the `record_diagnosis` tool to return your structured assessment.
    """

    # 1. OLLAMA (Local, free, primary)
    if settings.OLLAMA_BASE_URL:
        try:
            ollama_tools = [
                {
                    "type": "function",
                    "function": {
                        "name": "record_diagnosis",
                        "description": "Record the diagnosis of the payment failure.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "root_cause": {
                                    "type": "string",
                                    "enum": ["insufficient_funds", "expired_card", "stolen_or_lost_card", "closed_account", "bank_system_outage", "gateway_timeout", "otp_validation_failed", "generic_bank_decline", "unrecognized_decline"],
                                    "description": "The specific categorized root cause. Must be one of: insufficient_funds, expired_card, stolen_or_lost_card, closed_account, bank_system_outage, gateway_timeout, otp_validation_failed, generic_bank_decline, unrecognized_decline."
                                },
                                "severity": {
                                    "type": "string",
                                    "enum": ["soft", "hard"],
                                    "description": "Whether the decline is soft (temporary, retryable) or hard (permanent, non-retryable)."
                                },
                                "recovery_probability": {
                                    "type": "number",
                                    "description": "Probability of recovering this payment (between 0.0 and 1.0)."
                                },
                                "reasoning": {
                                    "type": "string",
                                    "description": "Your detailed reasoning explaining why you arrived at this diagnosis."
                                }
                            },
                            "required": ["root_cause", "severity", "recovery_probability", "reasoning"]
                        }
                    }
                }
            ]
            diag = _call_ollama_diagnosis(prompt, ollama_tools)
            if "severity" in diag and "root_cause" in diag:
                s = str(diag["severity"]).lower()
                if any(kw in s for kw in ["hard", "critical", "high", "blocked"]):
                    diag["severity"] = "hard"
                else:
                    diag["severity"] = "soft"

                rc = str(diag["root_cause"]).lower()
                for valid_rc in ["insufficient_funds", "expired_card", "stolen_or_lost_card", "closed_account", "bank_system_outage", "gateway_timeout", "otp_validation_failed", "generic_bank_decline"]:
                    if valid_rc in rc:
                        diag["root_cause"] = valid_rc
                        break

                try:
                    diag["recovery_probability"] = float(diag.get("recovery_probability", 0.5))
                except Exception:
                    diag["recovery_probability"] = 0.5

                if "reasoning" not in diag:
                    diag["reasoning"] = f"Diagnosed by Ollama: {diag['root_cause']} ({diag['severity']})"

                diagnosis_data = diag
                final_source = "ollama_diagnosis"
                final_payload_source = "ollama"
                logger.info("Ollama successfully diagnosed case %s: %s", case_id, diagnosis_data)
            else:
                raise ValueError("Ollama response missing required diagnosis fields")
        except Exception as e:
            reason = get_ollama_fallback_reason(e)
            logger.error("Ollama diagnosis failed for case %s with reason '%s': %s", case_id, reason, e)
            fallbacks.append({
                "provider": "ollama",
                "reason": reason,
                "error": str(e)
            })

    # 2. CLAUDE (Anthropic)
    if diagnosis_data is None and settings.ANTHROPIC_API_KEY and not settings.ANTHROPIC_API_KEY.startswith("dummy"):
        try:
            headers = {
                "Accept-Encoding": "identity"
            }
            if settings.ANTHROPIC_WORKSPACE_ID:
                headers["anthropic-workspace-id"] = settings.ANTHROPIC_WORKSPACE_ID
            client = Anthropic(api_key=settings.ANTHROPIC_API_KEY, default_headers=headers)
            
            anthropic_tools = [
                {
                    "name": "record_diagnosis",
                    "description": "Record the diagnosis of the payment failure.",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "root_cause": {
                                "type": "string",
                                "description": "The specific categorized root cause. Must be one of: insufficient_funds, expired_card, stolen_or_lost_card, closed_account, bank_system_outage, gateway_timeout, otp_validation_failed, generic_bank_decline, unrecognized_decline."
                            },
                            "severity": {
                                "type": "string",
                                "enum": ["soft", "hard"],
                                "description": "Whether the decline is soft (temporary, retryable) or hard (permanent, non-retryable)."
                            },
                            "recovery_probability": {
                                "type": "number",
                                "description": "Probability of recovering this payment (between 0.0 and 1.0)."
                            },
                            "reasoning": {
                                "type": "string",
                                "description": "Your detailed reasoning explaining why you arrived at this diagnosis."
                            }
                        },
                        "required": ["root_cause", "severity", "recovery_probability", "reasoning"]
                    }
                }
            ]
            
            message = _call_claude_diagnosis_with_retry(client, prompt, anthropic_tools)
            tool_use = [block for block in message.content if block.type == "tool_use"][0]
            diagnosis_data = tool_use.input
            final_source = "claude_diagnosis"
            final_payload_source = "claude"
            logger.info("Claude successfully diagnosed case %s: %s", case_id, diagnosis_data)
        except Exception as e:
            reason = get_claude_fallback_reason(e)
            logger.error("Claude diagnosis failed for case %s with reason '%s': %s", case_id, reason, e)
            fallbacks.append({
                "provider": "claude",
                "reason": reason,
                "error": str(e)
            })

    # 2. GEMINI (Google)
    if diagnosis_data is None and settings.GEMINI_API_KEY and not settings.GEMINI_API_KEY.startswith("dummy"):
        try:
            genai.configure(api_key=settings.GEMINI_API_KEY)
            gemini_tool = genai.types.FunctionDeclaration(
                name="record_diagnosis",
                description="Record the diagnosis of the payment failure.",
                parameters={
                    "type": "OBJECT",
                    "properties": {
                        "root_cause": {
                            "type": "STRING",
                            "description": "The specific categorized root cause. Must be one of: insufficient_funds, expired_card, stolen_or_lost_card, closed_account, bank_system_outage, gateway_timeout, otp_validation_failed, generic_bank_decline, unrecognized_decline."
                        },
                        "severity": {
                            "type": "STRING",
                            "enum": ["soft", "hard"],
                            "description": "Whether the decline is soft (temporary, retryable) or hard (permanent, non-retryable)."
                        },
                        "recovery_probability": {
                            "type": "NUMBER",
                            "description": "Probability of recovering this payment (between 0.0 and 1.0)."
                        },
                        "reasoning": {
                            "type": "STRING",
                            "description": "Your detailed reasoning explaining why you arrived at this diagnosis."
                        }
                    },
                    "required": ["root_cause", "severity", "recovery_probability", "reasoning"]
                }
            )
            response = _call_gemini_diagnosis_with_retry(prompt, gemini_tool)
            function_call = response.candidates[0].content.parts[0].function_call
            diagnosis_data = dict(function_call.args)
            final_source = "gemini_diagnosis"
            final_payload_source = "gemini"
            logger.info("Gemini successfully diagnosed case %s: %s", case_id, diagnosis_data)
        except Exception as e:
            reason = get_gemini_fallback_reason(e)
            logger.error("Gemini diagnosis failed for case %s with reason '%s': %s", case_id, reason, e)
            fallbacks.append({
                "provider": "gemini",
                "reason": reason,
                "error": str(e)
            })

    # 3. GROQ (Llama)
    if diagnosis_data is None and settings.GROQ_API_KEY and not settings.GROQ_API_KEY.startswith("dummy"):
        try:
            groq_client = Groq(api_key=settings.GROQ_API_KEY)
            groq_tools = [
                {
                    "type": "function",
                    "function": {
                        "name": "record_diagnosis",
                        "description": "Record the diagnosis of the payment failure.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "root_cause": {
                                    "type": "string",
                                    "description": "The specific categorized root cause. Must be one of: insufficient_funds, expired_card, stolen_or_lost_card, closed_account, bank_system_outage, gateway_timeout, otp_validation_failed, generic_bank_decline, unrecognized_decline."
                                },
                                "severity": {
                                    "type": "string",
                                    "enum": ["soft", "hard"],
                                    "description": "Whether the decline is soft (temporary, retryable) or hard (permanent, non-retryable)."
                                },
                                "recovery_probability": {
                                    "type": "number",
                                    "description": "Probability of recovering this payment (between 0.0 and 1.0)."
                                },
                                "reasoning": {
                                    "type": "string",
                                    "description": "Your detailed reasoning explaining why you arrived at this diagnosis."
                                }
                            },
                            "required": ["root_cause", "severity", "recovery_probability", "reasoning"]
                        }
                    }
                }
            ]
            response = _call_groq_diagnosis_with_retry(groq_client, prompt, groq_tools)
            tool_call = response.choices[0].message.tool_calls[0]
            diagnosis_data = json.loads(tool_call.function.arguments)
            final_source = "groq_diagnosis"
            final_payload_source = "groq"
            logger.info("Groq successfully diagnosed case %s: %s", case_id, diagnosis_data)
        except Exception as e:
            reason = get_groq_fallback_reason(e)
            logger.error("Groq diagnosis failed for case %s with reason '%s': %s", case_id, reason, e)
            fallbacks.append({
                "provider": "groq",
                "reason": reason,
                "error": str(e)
            })

    # 4. RULE-BASED FALLBACK
    if diagnosis_data is None:
        diagnosis_data = get_mock_diagnosis(failure_code, failure_description)
        if len(fallbacks) > 0:
            final_source = "rule_engine_fallback"
            final_payload_source = "rule_engine_fallback"
        else:
            final_source = "rule_engine"
            final_payload_source = "rule_fallback"
        logger.info("Fell back to rules for case %s", case_id)

    # Save to Database
    diagnosis = Diagnosis(
        case_id=case_id,
        root_cause=diagnosis_data["root_cause"],
        severity=diagnosis_data["severity"],
        recovery_probability=diagnosis_data["recovery_probability"],
        reasoning=diagnosis_data["reasoning"]
    )
    db.add(diagnosis)
    db.flush()  # Generate ID

    # Log to Audit Table
    audit = AuditLogEntry(
        case_id=case_id,
        step="diagnosis",
        source=final_source,
        payload={
            "diagnosis_id": diagnosis.id,
            "root_cause": diagnosis.root_cause,
            "severity": diagnosis.severity,
            "recovery_probability": diagnosis.recovery_probability,
            "reasoning": diagnosis.reasoning,
            "source": final_payload_source,
            "fallbacks": fallbacks
        }
    )
    db.add(audit)
    db.commit()

    return diagnosis

