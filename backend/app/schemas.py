from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List, Dict, Any
from datetime import datetime

# ----------------- Database Schemas -----------------

class EventBase(BaseModel):
    event_type: str
    payload: Dict[str, Any]

class EventSchema(EventBase):
    id: str
    case_id: str
    created_at: datetime

    class Config:
        from_attributes = True


class DiagnosisBase(BaseModel):
    root_cause: str = Field(..., description="Categorized cause of payment failure")
    severity: str = Field(..., description="Severity level: soft or hard")
    recovery_probability: float = Field(..., description="Likelihood of recovery between 0.0 and 1.0", ge=0.0, le=1.0)
    reasoning: str = Field(..., description="Detailed explanation of the diagnosis")

class DiagnosisSchema(DiagnosisBase):
    id: str
    case_id: str
    created_at: datetime

    class Config:
        from_attributes = True


class DecisionBase(BaseModel):
    action: str = Field(..., description="Intervention action: retry | send_email | send_sms | escalate_human | stop")
    channel: str = Field(..., description="Communication channel: email | sms | none")
    scheduled_for: datetime = Field(..., description="Scheduled timestamp for execution")
    reasoning: str = Field(..., description="Explanation of why this action was decided")

class DecisionSchema(DecisionBase):
    id: str
    case_id: str
    created_at: datetime

    class Config:
        from_attributes = True


class GuardrailCheckBase(BaseModel):
    rule_name: str
    passed: bool
    reason: str

class GuardrailCheckSchema(GuardrailCheckBase):
    id: str
    case_id: str
    created_at: datetime

    class Config:
        from_attributes = True


class ActionBase(BaseModel):
    action_type: str
    channel: str
    payload: Optional[Dict[str, Any]] = None
    status: str
    executed_at: Optional[datetime] = None
    outcome: Optional[str] = None

class ActionSchema(ActionBase):
    id: str
    case_id: str
    created_at: datetime

    class Config:
        from_attributes = True


class AuditLogEntryBase(BaseModel):
    step: str
    source: str
    payload: Dict[str, Any]

class AuditLogEntrySchema(AuditLogEntryBase):
    id: int
    case_id: str
    created_at: datetime

    class Config:
        from_attributes = True


class PromiseToPayBase(BaseModel):
    promised_date: datetime
    promised_amount: float
    status: str = "pending"  # pending | kept | broken

class PromiseToPaySchema(PromiseToPayBase):
    id: str
    case_id: str
    created_at: datetime

    class Config:
        from_attributes = True


class CaseBase(BaseModel):
    leak_type: str
    status: str
    customer_reference: str
    customer_email: Optional[str] = None
    customer_phone: Optional[str] = None
    opted_out: bool = False
    amount: float
    recovered_amount: float = 0.0
    currency: str = "INR"

class CaseSchema(CaseBase):
    id: str
    created_at: datetime
    updated_at: datetime
    
    events: List[EventSchema] = []
    diagnoses: List[DiagnosisSchema] = []
    decisions: List[DecisionSchema] = []
    guardrail_checks: List[GuardrailCheckSchema] = []
    actions: List[ActionSchema] = []
    promises: List[PromiseToPaySchema] = []

    class Config:
        from_attributes = True

# ----------------- API Endpoints Schemas -----------------

class CreateCaseRequest(BaseModel):
    leak_type: str
    customer_reference: str
    customer_email: Optional[str] = None
    customer_phone: Optional[str] = None
    opted_out: bool = False
    amount: float
    currency: str = "INR"
    failure_code: Optional[str] = None
    failure_description: Optional[str] = None

class PromiseToPayCreate(BaseModel):
    promised_date: datetime
    promised_amount: float

class CaseTraceResponse(BaseModel):
    case: CaseSchema
    audit_logs: List[AuditLogEntrySchema]

class SimulationRunRequest(BaseModel):
    num_cases: int = Field(10, ge=1, le=50)

class MetricsResponse(BaseModel):
    total_cases: int
    recovered_amount: float
    baseline_recovered_amount: float
    incremental_recovery: float
    recovery_rate: float
    guardrail_violations: int
    recovery_by_root_cause: Dict[str, float]
    recovery_rate_by_root_cause: Dict[str, float]
