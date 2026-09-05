"use client";

import { useEffect, useState, use } from "react";
import Link from "next/link";
import { 
  fetchCaseTrace, 
  createPromiseToPay, 
  optOutCustomer, 
  reactivateCase, 
  CaseTrace, 
  Case, 
  AuditLog 
} from "@/lib/api";
import { 
  ArrowLeft, 
  DollarSign, 
  Calendar, 
  ShieldCheck, 
  ShieldAlert,
  Mail, 
  MessageSquare, 
  Bot, 
  User, 
  Terminal,
  Activity,
  AlertTriangle,
  History,
  CheckCircle,
  Clock,
  Ban
} from "lucide-react";

interface CaseDetailProps {
  params: Promise<{ id: string }>;
}

export default function CaseDetail({ params }: CaseDetailProps) {
  const { id: caseId } = use(params);

  const [trace, setTrace] = useState<CaseTrace | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState(false);

  // Promise Form State
  const [showPromiseForm, setShowPromiseForm] = useState(false);
  const [promiseDate, setPromiseDate] = useState("");
  const [promiseAmount, setPromiseAmount] = useState("");
  const [promiseMessage, setPromiseMessage] = useState("");

  async function loadTrace() {
    try {
      setLoading(true);
      const data = await fetchCaseTrace(caseId);
      setTrace(data);
      setPromiseAmount(data.case.amount.toString());
      setError(null);
    } catch (err: any) {
      console.error(err);
      setError("Failed to fetch audit trace details.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadTrace();
  }, [caseId]);

  // Handle Actions
  async function handleOptOut() {
    if (!confirm("Are you sure you want to opt out this customer? All future emails/SMS for this customer reference will be blocked.")) return;
    try {
      setActionLoading(true);
      await optOutCustomer(caseId);
      await loadTrace();
      alert("Customer successfully opted out.");
    } catch (err: any) {
      alert("Failed to opt out customer.");
    } finally {
      setActionLoading(false);
    }
  }

  async function handleReactivate() {
    try {
      setActionLoading(true);
      await reactivateCase(caseId, false);
      await loadTrace();
      alert("Recovery sequence reactivated.");
    } catch (err: any) {
      if (err.message && err.message.includes("compliance override")) {
        const confirmOverride = window.confirm(
          "WARNING: This case was diagnosed as a Hard Decline (e.g., Expired/Stolen card). Reactivating it will bypass compliance guardrails and log a compliance override audit event. Do you want to proceed?"
        );
        if (confirmOverride) {
          try {
            await reactivateCase(caseId, true);
            await loadTrace();
            alert("Recovery sequence reactivated with compliance override.");
            return;
          } catch (overrideErr: any) {
            alert(overrideErr.message || "Failed to reactivate case with compliance override.");
          }
        }
      } else {
        alert(err.message || "Failed to reactivate recovery sequence.");
      }
    } finally {
      setActionLoading(false);
    }
  }

  async function handlePromiseSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!promiseDate || !promiseAmount) {
      alert("Please fill in all fields");
      return;
    }
    try {
      setActionLoading(true);
      await createPromiseToPay(caseId, promiseDate, parseFloat(promiseAmount));
      setShowPromiseForm(false);
      await loadTrace();
      alert("Promise-to-Pay registered successfully.");
    } catch (err: any) {
      alert("Failed to register Promise-to-Pay.");
    } finally {
      setActionLoading(false);
    }
  }

  if (loading) {
    return (
      <div className="flex-1 flex justify-center items-center min-h-[calc(100vh-4rem)] p-8 bg-[#f8fafc]">
        <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-[#3374F0]"></div>
      </div>
    );
  }

  if (error || !trace) {
    return (
      <div className="flex-1 flex flex-col justify-center items-center min-h-[calc(100vh-4rem)] p-8 bg-[#f8fafc]">
        <div className="p-6 bg-rose-50 border border-rose-100 rounded-xl text-center max-w-sm">
          <AlertTriangle className="h-8 w-8 text-rose-500 mx-auto mb-3" />
          <h3 className="font-semibold text-slate-900 mb-1">Failed to Load Trace</h3>
          <p className="text-sm text-slate-500 mb-4">{error}</p>
          <Link href="/cases" className="text-sm font-semibold text-[#3374F0] hover:underline">
            Back to cases list
          </Link>
        </div>
      </div>
    );
  }

  const { case: caseData, audit_logs: auditLogs } = trace;

  // Group audit logs by step
  const getLogsForStep = (stepName: string) => auditLogs.filter(log => log.step === stepName);

  // Status Styling
  let statusClass = "bg-slate-100 text-slate-700 border-slate-200";
  if (caseData.status === "recovered") statusClass = "bg-emerald-50 text-emerald-700 border-emerald-200";
  else if (caseData.status === "escalated" || caseData.status === "stop") statusClass = "bg-rose-50 text-rose-700 border-rose-200";
  else if (caseData.status === "blocked") statusClass = "bg-slate-100 text-slate-700 border-slate-300";
  else if (caseData.status === "detected") statusClass = "bg-sky-50 text-sky-700 border-sky-200";
  else statusClass = "bg-amber-50 text-amber-700 border-amber-200";

  return (
    <div className="flex-1 p-8 bg-[#f8fafc] space-y-8">
      {/* Top Navigation */}
      <div className="flex items-center justify-between">
        <Link 
          href="/cases" 
          className="inline-flex items-center gap-2 text-sm font-semibold text-slate-500 hover:text-slate-900 transition"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Cases list
        </Link>
        
        {/* Quick Actions Panel */}
        <div className="flex items-center gap-3">
          {/* Opt Out Button */}
          {!caseData.opted_out && (
            <button
              onClick={handleOptOut}
              disabled={actionLoading}
              className="px-3.5 py-2 border border-slate-200 bg-white hover:bg-slate-50 text-slate-700 font-semibold text-xs rounded-lg transition disabled:opacity-50"
            >
              Opt Out Customer
            </button>
          )}

          {/* Promise to Pay Button (B2B receivables only) */}
          {caseData.leak_type === "receivable_overdue" && caseData.status !== "recovered" && (
            <button
              onClick={() => setShowPromiseForm(!showPromiseForm)}
              disabled={actionLoading}
              className="px-3.5 py-2 border border-[#3374F0]/30 bg-blue-50/50 hover:bg-blue-50 text-[#3374F0] font-semibold text-xs rounded-lg transition disabled:opacity-50"
            >
              Log Promise-to-Pay
            </button>
          )}

          {/* Reactivate Button */}
          {caseData.status !== "recovered" && (
            <button
              onClick={handleReactivate}
              disabled={actionLoading}
              className="px-3.5 py-2 bg-[#3374F0] hover:bg-[#2563EB] text-white font-semibold text-xs rounded-lg transition shadow-sm disabled:opacity-50"
            >
              Reactivate Recovery
            </button>
          )}
        </div>
      </div>

      {/* Promise-to-Pay Modal/Form Panel */}
      {showPromiseForm && (
        <form onSubmit={handlePromiseSubmit} className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm max-w-md animate-fade-in">
          <h3 className="font-semibold text-slate-900 text-sm mb-4">Register B2B Promise-to-Pay</h3>
          <div className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-slate-500 mb-1">Promised Date</label>
              <input
                type="datetime-local"
                value={promiseDate}
                onChange={(e) => setPromiseDate(e.target.value)}
                className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm"
                required
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-500 mb-1">Promised Amount (INR)</label>
              <input
                type="number"
                step="0.01"
                value={promiseAmount}
                onChange={(e) => setPromiseAmount(e.target.value)}
                className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm font-mono"
                required
              />
            </div>
            <div className="flex gap-2 justify-end text-xs">
              <button
                type="button"
                onClick={() => setShowPromiseForm(false)}
                className="px-3 py-1.5 border border-slate-200 rounded-lg hover:bg-slate-50"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={actionLoading}
                className="px-3 py-1.5 bg-[#3374F0] text-white rounded-lg hover:bg-[#2563EB] shadow-xs"
              >
                Save Promise
              </button>
            </div>
          </div>
        </form>
      )}

      {/* Case Header Details Grid */}
      <div className="bg-white border border-slate-100 rounded-xl shadow-xs p-6 grid grid-cols-1 md:grid-cols-4 gap-6">
        <div>
          <span className="text-[10px] uppercase font-medium text-slate-400 tracking-wider">Customer Reference</span>
          <h2 className="text-lg font-semibold text-slate-900 mt-1 truncate">{caseData.customer_reference}</h2>
          <p className="text-xs text-slate-400 font-mono mt-0.5 truncate">{caseData.id}</p>
        </div>
        <div>
          <span className="text-[10px] uppercase font-medium text-slate-400 tracking-wider">Leak Type / Amount</span>
          <h2 className="text-lg font-semibold text-slate-900 mt-1 font-mono">
            ₹{caseData.amount.toLocaleString("en-IN")}
          </h2>
          <span className="inline-block text-[10px] uppercase tracking-wider font-medium text-slate-400 mt-0.5">
            {caseData.leak_type.replace("_", " ")}
          </span>
        </div>
        <div>
          <span className="text-[10px] uppercase font-medium text-slate-400 tracking-wider">Communication status</span>
          <div className="mt-1 flex items-center gap-1.5">
            {caseData.opted_out ? (
              <span className="text-xs text-rose-700 bg-rose-50 border border-rose-100 px-2 py-0.5 rounded-full font-medium">
                Communications Blocked (Opted Out)
              </span>
            ) : (
              <span className="text-xs text-emerald-700 bg-emerald-50 border border-emerald-100 px-2 py-0.5 rounded-full font-medium">
                Deliveries Allowed
              </span>
            )}
          </div>
        </div>
        <div>
          <span className="text-[10px] uppercase font-medium text-slate-400 tracking-wider">Current Pipeline State</span>
          <div className="mt-1">
            <span className={`px-3 py-1 border text-xs uppercase font-semibold rounded-full tracking-wider ${statusClass}`}>
              {caseData.status}
            </span>
          </div>
        </div>
      </div>

      {/* PIPELINE TRACE SECTION (Timeline UI) */}
      <div className="space-y-6">
        <h3 className="text-base font-semibold text-slate-900 flex items-center gap-2">
          <Activity className="h-4.5 w-4.5 text-[#3374F0]" />
          Recovery Audit Trail
        </h3>

        {/* 1. Detection Stage */}
        <div className="relative pl-8 border-l-2 border-slate-200 space-y-3 pb-8">
          {/* Icon node */}
          <div className="absolute -left-[11px] top-0 bg-slate-900 text-white p-1 rounded-full border-2 border-white shadow-xs">
            <Terminal className="h-4 w-4" />
          </div>
          <div>
            <div className="flex items-center gap-3">
              <h4 className="text-sm font-semibold text-slate-950">Stage 1: Webhook Signal Detection</h4>
              <span className="px-2 py-0.5 border border-slate-200 bg-slate-100 text-slate-600 text-[9px] font-medium rounded-sm uppercase tracking-wider">Rule</span>
            </div>
            <p className="text-xs text-slate-400 font-medium mt-0.5">
              {caseData.leak_type === "receivable_overdue" 
                ? "Inbound B2B receivable invoice marked overdue and routed by rule engine."
                : "Inbound failed checkout telemetry caught from payment gateway and routed by rule engine."}
            </p>
          </div>
          
          {getLogsForStep("detection").map((log) => (
            <div key={log.id} className="bg-white border border-slate-100 rounded-xl p-4 shadow-2xs space-y-3 max-w-3xl">
              <div className="flex justify-between items-center text-xs text-slate-400 pb-2 border-b border-slate-50">
                <span>Webhook Event ID: {log.payload.event_id}</span>
                <span>{new Date(log.created_at).toLocaleString("en-IN")}</span>
              </div>
              <div className="grid grid-cols-2 gap-4 text-xs">
                <div>
                  <span className="text-slate-400 font-semibold uppercase tracking-wider text-[10px]">Decline Trigger</span>
                  <p className="font-bold text-slate-900 font-mono mt-0.5">{log.payload.event_type}</p>
                </div>
                <div>
                  <span className="text-slate-400 font-semibold uppercase tracking-wider text-[10px]">Payment ID</span>
                  <p className="font-bold text-slate-900 font-mono mt-0.5">{log.payload.payment_id}</p>
                </div>
              </div>
              <details className="text-xs">
                <summary className="cursor-pointer font-semibold text-[#3374F0] hover:underline">View raw Webhook Payload</summary>
                <pre className="bg-slate-950 text-emerald-400 p-4 rounded-lg font-mono overflow-x-auto mt-2 text-[10px] max-h-60">
                  {JSON.stringify(log.payload, null, 2)}
                </pre>
              </details>
            </div>
          ))}
        </div>

        {/* 2. Diagnosis Stage */}
        {(() => {
          const diagLogs = getLogsForStep("diagnosis");
          const isB2B = caseData.leak_type === "receivable_overdue";
          
          const getSourceLabel = (source: string) => {
            if (source === "ollama_diagnosis" || source === "ollama_decision") return "Ollama LLM (Local)";
            if (source === "claude_diagnosis" || source === "claude_decision") return "Claude LLM";
            if (source === "gemini_diagnosis" || source === "gemini_decision") return "Gemini LLM";
            if (source === "groq_diagnosis" || source === "groq_decision") return "Groq LLM";
            if (source === "rule_engine_fallback") return "Rule Engine (Fallback)";
            return "Rule Engine";
          };

          const getProviderBadge = (logSource: string | undefined) => {
            if (!logSource) return <span className="px-2 py-0.5 border border-slate-200 bg-slate-100 text-slate-600 text-[9px] font-bold rounded-sm uppercase tracking-wider">Rule</span>;
            if (logSource.startsWith("ollama")) {
              return <span className="px-2 py-0.5 border border-emerald-200 bg-emerald-50 text-emerald-700 text-[9px] font-bold rounded-sm uppercase tracking-wider">Ollama (Local)</span>;
            }
            if (logSource.startsWith("claude")) {
              return <span className="px-2 py-0.5 border border-blue-200 bg-blue-50 text-[#3374F0] text-[9px] font-bold rounded-sm uppercase tracking-wider">Claude</span>;
            }
            if (logSource.startsWith("gemini")) {
              return <span className="px-2 py-0.5 border border-teal-200 bg-teal-50 text-teal-700 text-[9px] font-bold rounded-sm uppercase tracking-wider">Gemini</span>;
            }
            if (logSource.startsWith("groq")) {
              return <span className="px-2 py-0.5 border border-purple-200 bg-purple-50 text-purple-700 text-[9px] font-bold rounded-sm uppercase tracking-wider">Groq</span>;
            }
            if (logSource === "rule_engine_fallback") {
              return <span className="px-2 py-0.5 border border-amber-200 bg-amber-50 text-amber-700 text-[9px] font-bold rounded-sm uppercase tracking-wider">Rule (Fallback)</span>;
            }
            return <span className="px-2 py-0.5 border border-slate-200 bg-slate-100 text-slate-600 text-[9px] font-bold rounded-sm uppercase tracking-wider">Rule</span>;
          };

          return (
            <div className="relative pl-8 border-l-2 border-slate-200 space-y-5 pb-8">
              <div className="absolute -left-[11px] top-0 bg-[#3374F0] text-white p-1 rounded-full border-2 border-white shadow-xs">
                <Bot className="h-4 w-4" />
              </div>
              
              {diagLogs.map((log) => {
                const isHard = log.payload.severity === "hard";
                const isLogAI = log.source !== "rule_engine" && log.source !== "rule_engine_fallback";
                
                const logTitle = isLogAI 
                  ? (isB2B ? "Stage 2: AI Overdue Analysis & Severity Diagnosis" : "Stage 2: AI failure Analysis & Severity Diagnosis")
                  : (isB2B ? "Stage 2: Rule-Based Overdue Diagnosis" : "Stage 2: Rule-Based failure Diagnosis");
                
                const logDesc = isLogAI 
                  ? (isB2B ? "AI model determines B2B account severity and maps payment likelihood." : "AI model determines failure severity and maps root cause.")
                  : (isB2B ? "Deterministic rules analyzed B2B invoice dunning criteria." : "Deterministic rules mapped the failure severity and root cause.");

                return (
                  <div key={log.id} className="space-y-2">
                    <div>
                      <div className="flex items-center gap-3">
                        <h4 className="text-sm font-bold text-slate-950">{logTitle}</h4>
                        {getProviderBadge(log.source)}
                      </div>
                      <p className="text-xs text-slate-400 font-medium mt-0.5">{logDesc}</p>
                    </div>

                    <div className="bg-white border border-slate-100 rounded-xl p-5 shadow-2xs space-y-4 max-w-3xl">
                      <div className="flex justify-between items-center text-xs text-slate-400">
                        <div className="flex items-center gap-1.5 text-[#3374F0] font-semibold">
                          <History className="h-3.5 w-3.5" />
                          Source: {getSourceLabel(log.source)} ({log.source})
                        </div>
                        <span>{new Date(log.created_at).toLocaleString("en-IN")}</span>
                      </div>

                      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 border-y border-slate-50 py-3 text-xs">
                        <div>
                          <span className="text-slate-400 font-semibold uppercase tracking-wider text-[10px]">Root Cause Category</span>
                          <p className="font-bold text-slate-900 capitalize mt-0.5">{log.payload.root_cause.replace(/_/g, " ")}</p>
                        </div>
                        <div>
                          <span className="text-slate-400 font-semibold uppercase tracking-wider text-[10px]">Severity Gating</span>
                          <p className="mt-0.5">
                            <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold border ${
                              isHard ? "bg-rose-50 border-rose-200 text-rose-700" : "bg-emerald-50 border-emerald-200 text-emerald-700"
                            }`}>
                              {log.payload.severity.toUpperCase()} Decline
                            </span>
                          </p>
                        </div>
                        <div>
                          <span className="text-slate-400 font-semibold uppercase tracking-wider text-[10px]">Recovery Likelihood</span>
                          <p className="font-bold text-slate-900 mt-0.5">
                            {(() => {
                              const p = log.payload?.recovery_probability;
                              if (p === undefined || p === null || p === "") return "N/A";
                              const num = typeof p === "number" ? p : parseFloat(String(p).replace("%", ""));
                              if (isNaN(num)) return "N/A";
                              const pct = num <= 1.0 ? num * 100 : num;
                              return `${pct.toFixed(0)}%`;
                            })()}
                          </p>
                        </div>
                      </div>

                      <div className="bg-slate-50 rounded-lg p-4 text-xs border border-slate-100 space-y-2">
                        <span className="text-slate-400 font-bold uppercase tracking-wider text-[9px] block">
                          {isLogAI ? "AI Reasoning Process" : "Diagnosis Trigger Detail"}
                        </span>
                        <p className="text-slate-700 font-normal leading-relaxed">{log.payload.reasoning}</p>
                        
                        {log.payload.fallbacks && log.payload.fallbacks.length > 0 && (
                          <div className="mt-3 pt-2 border-t border-slate-200/60 space-y-1.5">
                            <span className="text-rose-500 font-bold uppercase tracking-wider text-[9px] block">Provider Fallbacks Detected:</span>
                            {log.payload.fallbacks.map((fb: any, fidx: number) => (
                              <div key={fidx} className="text-[10px] text-slate-500 leading-normal">
                                ⚠️ <span className="font-bold capitalize">{fb.provider}</span> failed with <span className="font-semibold text-rose-600">{fb.reason}</span>: <code className="bg-slate-100 px-1 py-0.5 rounded">{fb.error}</code>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
              
              {diagLogs.length === 0 && (
                <div>
                  <div className="flex items-center gap-3">
                    <h4 className="text-sm font-bold text-slate-950">
                      {isB2B ? "Stage 2: Overdue Diagnosis" : "Stage 2: Failure Diagnosis"}
                    </h4>
                  </div>
                  <p className="text-xs text-slate-400 font-medium mt-0.5">Awaiting failure diagnosis.</p>
                </div>
              )}
            </div>
          );
        })()}

        {/* 3. Decision Stage */}
        {(() => {
          const decLogs = getLogsForStep("decision");
          const isB2B = caseData.leak_type === "receivable_overdue";
          
          const getSourceLabel = (source: string) => {
            if (source === "ollama_diagnosis" || source === "ollama_decision") return "Ollama LLM (Local)";
            if (source === "claude_diagnosis" || source === "claude_decision") return "Claude LLM";
            if (source === "gemini_diagnosis" || source === "gemini_decision") return "Gemini LLM";
            if (source === "groq_diagnosis" || source === "groq_decision") return "Groq LLM";
            if (source === "rule_engine_fallback") return "Rule Engine (Fallback)";
            return "Rule Engine";
          };

          const getProviderBadge = (logSource: string | undefined) => {
            if (!logSource) return <span className="px-2 py-0.5 border border-slate-200 bg-slate-100 text-slate-600 text-[9px] font-bold rounded-sm uppercase tracking-wider">Rule</span>;
            if (logSource.startsWith("ollama")) {
              return <span className="px-2 py-0.5 border border-emerald-200 bg-emerald-50 text-emerald-700 text-[9px] font-bold rounded-sm uppercase tracking-wider">Ollama (Local)</span>;
            }
            if (logSource.startsWith("claude")) {
              return <span className="px-2 py-0.5 border border-blue-200 bg-blue-50 text-[#3374F0] text-[9px] font-bold rounded-sm uppercase tracking-wider">Claude</span>;
            }
            if (logSource.startsWith("gemini")) {
              return <span className="px-2 py-0.5 border border-teal-200 bg-teal-50 text-teal-700 text-[9px] font-bold rounded-sm uppercase tracking-wider">Gemini</span>;
            }
            if (logSource.startsWith("groq")) {
              return <span className="px-2 py-0.5 border border-purple-200 bg-purple-50 text-purple-700 text-[9px] font-bold rounded-sm uppercase tracking-wider">Groq</span>;
            }
            if (logSource === "rule_engine_fallback") {
              return <span className="px-2 py-0.5 border border-amber-200 bg-amber-50 text-amber-700 text-[9px] font-bold rounded-sm uppercase tracking-wider">Rule (Fallback)</span>;
            }
            return <span className="px-2 py-0.5 border border-slate-200 bg-slate-100 text-slate-600 text-[9px] font-bold rounded-sm uppercase tracking-wider">Rule</span>;
          };

          return (
            <div className="relative pl-8 border-l-2 border-slate-200 space-y-5 pb-8">
              <div className="absolute -left-[11px] top-0 bg-[#2563EB] text-white p-1 rounded-full border-2 border-white shadow-xs">
                <Bot className="h-4 w-4" />
              </div>
              
              {decLogs.map((log) => {
                const isLogAI = log.source !== "rule_engine" && log.source !== "rule_engine_fallback";
                const logTitle = isLogAI 
                  ? "Stage 3: AI Recovery Intervention Decision" 
                  : "Stage 3: Rule-Based Recovery Decision";
                const logDesc = isLogAI 
                  ? (isB2B ? "AI model maps the B2B customer state to recovery action, channels, and delay timers." : "AI model maps the diagnosis to recovery action, channels, and delay timers.")
                  : (isB2B ? "Deterministic rules resolved the dunning sequence action." : "Deterministic rules resolved the recovery action.");
                
                return (
                  <div key={log.id} className="space-y-2">
                    <div>
                      <div className="flex items-center gap-3">
                        <h4 className="text-sm font-bold text-slate-950">{logTitle}</h4>
                        {getProviderBadge(log.source)}
                      </div>
                      <p className="text-xs text-slate-400 font-medium mt-0.5">{logDesc}</p>
                    </div>

                    <div className="bg-white border border-slate-100 rounded-xl p-5 shadow-2xs space-y-4 max-w-3xl">
                      <div className="flex justify-between items-center text-xs text-slate-400">
                        <div className="flex items-center gap-1.5 text-[#3374F0] font-semibold">
                          <History className="h-3.5 w-3.5" />
                          Source: {getSourceLabel(log.source)} ({log.source})
                        </div>
                        <span>{new Date(log.created_at).toLocaleString("en-IN")}</span>
                      </div>

                      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 border-y border-slate-50 py-3 text-xs">
                        <div>
                          <span className="text-slate-400 font-semibold uppercase tracking-wider text-[10px]">Proposed Action</span>
                          <p className="font-bold text-slate-900 capitalize mt-0.5">{log.payload.action.replace(/_/g, " ")}</p>
                        </div>
                        <div>
                          <span className="text-slate-400 font-semibold uppercase tracking-wider text-[10px]">Intervention Channel</span>
                          <p className="font-bold text-slate-900 flex items-center gap-1 mt-0.5">
                            {log.payload.channel === "email" && <Mail className="h-3.5 w-3.5 text-[#3374F0]" />}
                            {log.payload.channel === "sms" && <MessageSquare className="h-3.5 w-3.5 text-emerald-500" />}
                            <span className="capitalize">{log.payload.channel}</span>
                          </p>
                        </div>
                        <div>
                          <span className="text-slate-400 font-semibold uppercase tracking-wider text-[10px]">Execution Timer</span>
                          <p className="font-bold text-slate-900 mt-0.5 flex items-center gap-1">
                            <Clock className="h-3.5 w-3.5 text-slate-400" />
                            {(() => {
                              if (!log.payload.scheduled_for) return "Immediate";
                              const d = new Date(log.payload.scheduled_for);
                              if (isNaN(d.getTime())) return "Immediate";
                              return d.toLocaleTimeString("en-IN", {
                                hour: "2-digit",
                                minute: "2-digit"
                              });
                            })()}
                          </p>
                        </div>
                      </div>

                      <div className="bg-slate-50 rounded-lg p-4 text-xs border border-slate-100 space-y-2">
                        <span className="text-slate-400 font-bold uppercase tracking-wider text-[9px] block">
                          {isLogAI ? "Proposed Strategy justification" : "Decision Rule trigger detail"}
                        </span>
                        <p className="text-slate-700 font-normal leading-relaxed">{log.payload.reasoning}</p>

                        {log.payload.fallbacks && log.payload.fallbacks.length > 0 && (
                          <div className="mt-3 pt-2 border-t border-slate-200/60 space-y-1.5">
                            <span className="text-rose-500 font-bold uppercase tracking-wider text-[9px] block">Provider Fallbacks Detected:</span>
                            {log.payload.fallbacks.map((fb: any, fidx: number) => (
                              <div key={fidx} className="text-[10px] text-slate-500 leading-normal">
                                ⚠️ <span className="font-bold capitalize">{fb.provider}</span> failed with <span className="font-semibold text-rose-600">{fb.reason}</span>: <code className="bg-slate-100 px-1 py-0.5 rounded">{fb.error}</code>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
              
              {decLogs.length === 0 && (
                <div>
                  <div className="flex items-center gap-3">
                    <h4 className="text-sm font-bold text-slate-950">Stage 3: Recovery Decision</h4>
                  </div>
                  <p className="text-xs text-slate-400 font-medium mt-0.5">Awaiting recovery decision.</p>
                </div>
              )}
            </div>
          );
        })()}

        {/* 4. Guardrails Stage */}
        <div className="relative pl-8 border-l-2 border-slate-200 space-y-3 pb-8">
          <div className="absolute -left-[11px] top-0 bg-teal-600 text-white p-1 rounded-full border-2 border-white shadow-xs">
            <ShieldCheck className="h-4 w-4" />
          </div>
          <div>
            <div className="flex items-center gap-3">
              <h4 className="text-sm font-bold text-slate-950">Stage 4: Compliance Guardrail Gate Checks</h4>
              <span className="px-2 py-0.5 border border-slate-200 bg-slate-100 text-slate-600 text-[9px] font-bold rounded-sm uppercase tracking-wider">Rule</span>
            </div>
            <p className="text-xs text-slate-400 font-medium mt-0.5">
              {caseData.leak_type === "receivable_overdue" 
                ? "Plain Python compliance rules gating B2B dunning touches."
                : "Plain Python compliance rules executing safety validations."}
            </p>
          </div>
          
          {getLogsForStep("guardrail_check").map((log) => (
            <div key={log.id} className="bg-white border border-slate-100 rounded-xl p-5 shadow-2xs space-y-3 max-w-3xl">
              <div className="flex justify-between items-center text-xs text-slate-400 pb-2 border-b border-slate-50">
                <span className="font-semibold flex items-center gap-1 text-teal-600">
                  <ShieldCheck className="h-4 w-4" />
                  Checks Complete
                </span>
                <span>{new Date(log.created_at).toLocaleString("en-IN")}</span>
              </div>

              <div className="space-y-2.5">
                {log.payload.checks && log.payload.checks.map((c: any, index: number) => (
                  <div key={index} className="flex justify-between items-start gap-4 text-xs">
                    <div className="space-y-0.5">
                      <span className="font-bold text-slate-800 font-mono">{c.rule_name}()</span>
                      <p className="text-slate-400 text-[10px] font-normal leading-relaxed">{c.reason}</p>
                    </div>
                    <span>
                      {c.passed ? (
                        <span className="px-2 py-0.5 rounded-full text-[9px] font-bold bg-emerald-50 border border-emerald-200 text-emerald-700 uppercase tracking-wider">
                          Pass
                        </span>
                      ) : (
                        <span className="px-2 py-0.5 rounded-full text-[9px] font-bold bg-rose-50 border border-rose-200 text-rose-700 uppercase tracking-wider">
                          Block
                        </span>
                      )}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>

        {/* 5. Execution Stage */}
        <div className="relative pl-8 border-l-2 border-slate-200 space-y-3 pb-8">
          <div className="absolute -left-[11px] top-0 bg-purple-600 text-white p-1 rounded-full border-2 border-white shadow-xs">
            <Activity className="h-4 w-4" />
          </div>
          <div>
            <div className="flex items-center gap-3">
              <h4 className="text-sm font-bold text-slate-950">Stage 5: Sandbox Action Execution</h4>
              <span className="px-2 py-0.5 border border-slate-200 bg-slate-100 text-slate-600 text-[9px] font-bold rounded-sm uppercase tracking-wider">Rule</span>
            </div>
            <p className="text-xs text-slate-400 font-medium mt-0.5">
              {caseData.leak_type === "receivable_overdue" 
                ? "Dispatch sandbox dunning outreach events (Email, SMS, or human escalation)."
                : "Dispatch sandbox recovery events (Email, SMS, or Payment retry)."}
            </p>
          </div>
          
          {/* We check Action records for this case */}
          {caseData.actions && caseData.actions.map((act: any) => {
            let statusIcon = <Clock className="h-4.5 w-4.5 text-amber-500 animate-pulse" />;
            if (act.status === "executed") statusIcon = <CheckCircle className="h-4.5 w-4.5 text-emerald-500" />;
            if (act.status === "blocked") statusIcon = <Ban className="h-4.5 w-4.5 text-rose-500" />;

            return (
              <div key={act.id} className="bg-white border border-slate-100 rounded-xl p-5 shadow-2xs space-y-3 max-w-3xl">
                <div className="flex justify-between items-center text-xs text-slate-400">
                  <span className="font-semibold flex items-center gap-1.5 text-purple-700">
                    {statusIcon}
                    Action status: {act.status.toUpperCase()}
                  </span>
                  {act.executed_at && <span>{new Date(act.executed_at).toLocaleString("en-IN")}</span>}
                </div>

                <div className="grid grid-cols-2 gap-4 text-xs font-medium border-y border-slate-50 py-2.5">
                  <div>
                    <span className="text-slate-400 font-bold text-[9px] uppercase tracking-wider">Command Dispatched</span>
                    <p className="text-slate-900 mt-0.5 capitalize">{act.action_type.replace(/_/g, " ")}</p>
                  </div>
                  <div>
                    <span className="text-slate-400 font-bold text-[9px] uppercase tracking-wider">Channel Target</span>
                    <p className="text-slate-900 mt-0.5 capitalize">{act.channel}</p>
                  </div>
                </div>

                <div className="bg-slate-900 text-slate-200 font-mono text-[10px] p-4 rounded-lg border border-slate-800">
                  <span className="text-slate-400 font-bold uppercase tracking-wider text-[8px] block mb-1">Sandbox Execution Log</span>
                  {act.outcome}
                </div>
              </div>
            );
          })}
        </div>

        {/* 6. Outcome Stage */}
        <div className="relative pl-8 space-y-3 pb-8">
          <div className="absolute -left-[11px] top-0 bg-emerald-600 text-white p-1 rounded-full border-2 border-white shadow-xs">
            <CheckCircle className="h-4 w-4" />
          </div>
          <div>
            <div className="flex items-center gap-3">
              <h4 className="text-sm font-bold text-slate-950">Stage 6: Outcome Reconciliation</h4>
              <span className="px-2 py-0.5 border border-slate-200 bg-slate-100 text-slate-600 text-[9px] font-bold rounded-sm uppercase tracking-wider">Rule</span>
            </div>
            <p className="text-xs text-slate-400 font-medium mt-0.5">
              {caseData.leak_type === "receivable_overdue" 
                ? "Final B2B invoice collection status or promise outcome reconciled by rule engine."
                : "Final transaction status reconciled by the rule engine."}
            </p>
          </div>
          
          {getLogsForStep("outcome").map((log) => {
            const hasPay = log.payload.captured_amount !== undefined;
            const success = log.payload.status === "success" || log.payload.captured_amount > 0 || log.payload.promise_id !== undefined || caseData.status === "recovered";
            
            return (
              <div key={log.id} className="bg-white border border-slate-100 rounded-xl p-5 shadow-2xs space-y-3 max-w-3xl">
                <div className="flex justify-between items-center text-xs text-slate-400 pb-1.5 border-b border-slate-50">
                  <span className="font-semibold flex items-center gap-1.5 text-emerald-600">
                    <CheckCircle className="h-4 w-4" />
                    Outcome Status
                  </span>
                  <span>{new Date(log.created_at).toLocaleString("en-IN")}</span>
                </div>

                {hasPay ? (
                  <div className="space-y-3 text-xs">
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <span className="text-slate-400 font-bold text-[9px] uppercase tracking-wider">Settled Amount</span>
                        <p className="text-slate-900 font-bold font-mono mt-0.5">₹{log.payload.captured_amount.toLocaleString("en-IN")}</p>
                      </div>
                      <div>
                        <span className="text-slate-400 font-bold text-[9px] uppercase tracking-wider">Recovery Attribution</span>
                        <p className="mt-0.5">
                          {log.payload.recovered_by_agent ? (
                            <span className="text-emerald-700 bg-emerald-50 px-2 py-0.5 border border-emerald-200 rounded-full font-bold text-[10px] uppercase">
                              Agent Recovered
                            </span>
                          ) : (
                            <span className="text-slate-600 bg-slate-100 px-2 py-0.5 border border-slate-200 rounded-full font-bold text-[10px] uppercase">
                              Self-Recovered (Independent)
                            </span>
                          )}
                        </p>
                      </div>
                    </div>
                    {log.payload.is_partial_recovery && (
                      <div className="p-3 bg-amber-50 border border-amber-100 rounded-lg text-amber-800 text-[11px] font-medium leading-relaxed">
                        Notice: This transaction represents a partial payment of the overall amount due (₹{log.payload.case_amount}).
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="text-xs text-slate-700 font-normal leading-relaxed">
                    {log.payload.message || log.payload.reason || "Outcome recorded: Case completed."}
                  </div>
                )}
              </div>
            );
          })}
          
          {getLogsForStep("outcome").length === 0 && (
            <div className="bg-slate-100/50 border border-slate-200 rounded-xl p-4 text-xs text-slate-500 max-w-3xl italic font-normal">
              Awaiting reconciliation. Case remains active in recovery workflow.
            </div>
          )}
        </div>

      </div>
    </div>
  );
}
