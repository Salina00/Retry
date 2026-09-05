const BASE_URL = "http://127.0.0.1:8000/api/v1";

export interface Case {
  id: string;
  leak_type: "payment_failure" | "receivable_overdue";
  status: "detected" | "diagnosing" | "decided" | "blocked" | "actioned" | "recovered" | "escalated" | "stop";
  customer_reference: string;
  customer_email: string | null;
  customer_phone: string | null;
  opted_out: boolean;
  amount: number;
  recovered_amount: number;
  currency: string;
  created_at: string;
  updated_at: string;
  events?: any[];
  diagnoses?: any[];
  decisions?: any[];
  guardrail_checks?: any[];
  actions?: any[];
  promises?: any[];
}

export interface AuditLog {
  id: number;
  case_id: string;
  step: "detection" | "diagnosis" | "decision" | "guardrail_check" | "action" | "outcome";
  source: string;
  payload: any;
  created_at: string;
}

export interface CaseTrace {
  case: Case;
  audit_logs: AuditLog[];
}

export interface DashboardMetrics {
  total_cases: number;
  recovered_amount: number;
  baseline_recovered_amount: number;
  incremental_recovery: number;
  recovery_rate: number;
  guardrail_violations: number;
  guardrail_blocks: number;
  recovery_by_root_cause: Record<string, number>;
  recovery_rate_by_root_cause: Record<string, number>;
  diagnosis_accuracy_severity: number;
  diagnosis_accuracy_root_cause: number;
  evaluation_last_run?: string;
  provider_breakdown?: {
    ollama: number;
    claude: number;
    gemini: number;
    groq: number;
    rules: number;
  };
  is_mock_mode: boolean;
}

export async function fetchMetrics(): Promise<DashboardMetrics> {
  const res = await fetch(`${BASE_URL}/metrics`, { cache: 'no-store' });
  if (!res.ok) throw new Error("Failed to fetch metrics");
  return res.json();
}

export async function runEvaluation(): Promise<{ status: string; message: string }> {
  const res = await fetch(`${BASE_URL}/batch/evaluate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" }
  });
  if (!res.ok) throw new Error("Failed to trigger evaluation");
  return res.json();
}

export async function fetchCases(leakType?: string, status?: string): Promise<Case[]> {
  const url = new URL(`${BASE_URL}/cases`);
  if (leakType) url.searchParams.append("leak_type", leakType);
  if (status) url.searchParams.append("status", status);
  
  const res = await fetch(url.toString(), { cache: 'no-store' });
  if (!res.ok) throw new Error("Failed to fetch cases");
  return res.json();
}

export async function fetchCaseTrace(id: string): Promise<CaseTrace> {
  const res = await fetch(`${BASE_URL}/cases/${id}`, { cache: 'no-store' });
  if (!res.ok) throw new Error("Failed to fetch case trace");
  return res.json();
}

export async function createPromiseToPay(id: string, date: string, amount: number): Promise<any> {
  const res = await fetch(`${BASE_URL}/cases/${id}/promise`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ promised_date: date, promised_amount: amount }),
  });
  if (!res.ok) throw new Error("Failed to create promise to pay");
  return res.json();
}

export async function optOutCustomer(id: string): Promise<any> {
  const res = await fetch(`${BASE_URL}/cases/${id}/optout`, {
    method: "POST",
  });
  if (!res.ok) throw new Error("Failed to opt out customer");
  return res.json();
}

export async function reactivateCase(id: string, override: boolean = false): Promise<any> {
  const res = await fetch(`${BASE_URL}/cases/${id}/reactivate?override=${override}`, {
    method: "POST",
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || "Failed to reactivate case");
  }
  return res.json();
}

export async function seedDatabase(numCases: number): Promise<any> {
  const res = await fetch(`${BASE_URL}/batch/seed`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ num_cases: numCases }),
  });
  if (!res.ok) throw new Error("Failed to seed database");
  return res.json();
}

export async function runSimulationTick(simulatedTime?: string): Promise<any> {
  const res = await fetch(`${BASE_URL}/batch/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ simulated_time: simulatedTime }),
  });
  if (!res.ok) throw new Error("Failed to run simulation tick");
  return res.json();
}
