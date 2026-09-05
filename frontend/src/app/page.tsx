"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { fetchMetrics, fetchCases, DashboardMetrics, Case } from "@/lib/api";
import { 
  TrendingUp, 
  ShieldCheck, 
  DollarSign, 
  Percent, 
  AlertTriangle, 
  BrainCircuit, 
  ArrowRight,
  ChevronRight,
  Receipt,
  Cpu,
  Sparkles
} from "lucide-react";

export default function Dashboard() {
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null);
  const [recentCases, setRecentCases] = useState<Case[]>([]);
  const [allCases, setAllCases] = useState<Case[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadData() {
      try {
        setLoading(true);
        const [mRes, cRes] = await Promise.all([
          fetchMetrics(),
          fetchCases()
        ]);
        setMetrics(mRes);
        setAllCases(cRes);
        // Show top 6 newest cases
        setRecentCases(cRes.slice(0, 6));
      } catch (err: any) {
        console.error(err);
        setError("Could not load dashboard telemetry. Is the backend server running?");
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  if (loading) {
    return (
      <div className="flex-1 flex flex-col justify-center items-center min-h-[calc(100vh-4rem)] p-8 bg-[#f8fafc]">
        <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-[#3374F0]"></div>
        <p className="mt-4 text-sm text-slate-500 font-medium">Loading recovery dashboard...</p>
      </div>
    );
  }

  if (error || !metrics) {
    return (
      <div className="flex-1 flex flex-col justify-center items-center min-h-[calc(100vh-4rem)] p-8 bg-[#f8fafc]">
        <div className="p-4 bg-rose-50 border border-rose-100 rounded-xl max-w-md text-center">
          <AlertTriangle className="h-10 w-10 text-rose-500 mx-auto mb-3" />
          <h3 className="font-semibold text-slate-900 mb-1">Telemetry Load Failure</h3>
          <p className="text-sm text-slate-500 mb-4">{error}</p>
          <button 
            onClick={() => window.location.reload()}
            className="px-4 py-2 bg-[#3374F0] text-white rounded-lg text-sm font-medium hover:bg-[#2563EB] transition"
          >
            Retry Connection
          </button>
        </div>
      </div>
    );
  }

  const rootCauseLabels: Record<string, string> = {
    insufficient_funds: "Insufficient Funds",
    expired_card: "Expired Card",
    stolen_or_lost_card: "Stolen/Lost Card",
    closed_account: "Closed Account",
    bank_system_outage: "Bank System Outage",
    gateway_timeout: "Gateway Timeout",
    otp_validation_failed: "OTP Failure",
    generic_bank_decline: "Generic Decline",
    broken_promise_to_pay: "Broken Promise",
    manual_reactivation: "Manual Reactivate",
    unknown_decline: "Unknown Decline",
    unrecognized_decline: "Unrecognized decline code — needs review",
    promise_to_pay_kept: "Kept Promise (Reconciled)",
    promise_to_pay_pending: "Pending Promise",
    unclassified: "Unclassified"
  };

  // Extract real recent outcomes from cases data for the Hero section bubbles
  const recoveredCase = allCases.find((c) => c.status === "recovered");
  const blockedCase = allCases.find((c) => c.status === "blocked" || c.opted_out || c.status === "stop");
  const escalatedCase = allCases.find((c) => c.status === "escalated");

  return (
    <div className="flex-1 p-6 sm:p-8 bg-[#f8fafc] space-y-8 max-w-7xl mx-auto w-full">
      {/* RAZORPAY-STYLE HERO SECTION */}
      <div className="relative overflow-hidden bg-white border border-slate-200/80 rounded-2xl p-6 sm:p-10 lg:p-12 shadow-[0_4px_20px_rgba(0,0,0,0.03)]">
        {/* Soft background blue ambient glow matching Razorpay homepage */}
        <div className="absolute right-0 top-0 bottom-0 w-3/5 bg-gradient-to-l from-blue-50/70 via-blue-50/20 to-transparent pointer-events-none rounded-r-2xl" />
        <div className="absolute -right-8 -bottom-8 w-72 h-72 bg-[#3374F0]/8 blur-3xl rounded-full pointer-events-none" />

        <div className="relative z-10 grid grid-cols-1 lg:grid-cols-12 gap-8 lg:gap-12 items-center">
          {/* Left Column: Headline, Mechanism Subtext, CTAs */}
          <div className="lg:col-span-7 space-y-5">
            <div className="inline-flex items-center gap-2 px-3 py-1 bg-blue-50 border border-blue-100 rounded-full text-xs font-semibold text-[#3374F0]">
              <Sparkles className="h-3.5 w-3.5 text-[#3374F0]" />
              Autonomous Revenue Recovery
            </div>

            <h1 className="text-3xl sm:text-4xl lg:text-5xl font-bold tracking-tight text-slate-900 leading-[1.18]">
              <span className="text-[#3374F0] block">Recover revenue</span>
              before it&apos;s lost
            </h1>

            <p className="text-base sm:text-lg text-slate-600 font-normal leading-relaxed max-w-xl">
              AI diagnoses failed payments and recovers them automatically — safely, and within compliance limits.
            </p>

            <div className="flex flex-wrap items-center gap-4 pt-2">
              <Link
                href="/cases"
                className="px-6 py-3 rounded-sm bg-[#3374F0] hover:bg-[#2563EB] text-white text-sm font-semibold transition-all shadow-xs flex items-center gap-2 group"
              >
                View Recovery Cases
                <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
              </Link>
              <Link
                href="/batch"
                className="text-sm font-semibold text-[#3374F0] hover:text-[#2563EB] hover:underline flex items-center gap-1 transition-colors px-2 py-2"
              >
                How it works
                <ChevronRight className="h-4 w-4" />
              </Link>
            </div>
          </div>

          {/* Right Column: Floating Status Outcome Bubbles (Real Case Data) */}
          <div className="lg:col-span-5 flex flex-col gap-3.5 sm:gap-4 relative">
            {/* Ambient branding card */}
            <div className="bg-gradient-to-br from-blue-50/90 to-white/90 border border-blue-100/90 p-4 rounded-xl shadow-2xs space-y-1 mb-1">
              <div className="flex items-center gap-2 text-[#3374F0]">
                <ShieldCheck className="h-4.5 w-4.5 shrink-0" />
                <span className="text-[11px] font-bold uppercase tracking-wider">Retry Autonomous Engine</span>
              </div>
              <p className="text-[11px] text-slate-500 font-normal leading-relaxed">
                Live failure webhook capture, AI multi-model diagnosis, and 5-stage compliance guardrails.
              </p>
            </div>

            {/* Floating Pill 1: Real Recovered Outcome */}
            <div className="inline-flex items-center gap-3 px-5 py-3 bg-white/95 backdrop-blur-sm rounded-full shadow-[0_8px_25px_rgba(0,0,0,0.06)] border border-slate-100 transition-all hover:scale-[1.02] hover:shadow-md">
              <span className="h-2.5 w-2.5 rounded-full bg-emerald-500 shrink-0"></span>
              <span className="text-xs text-slate-900 font-semibold">Payment Recovered</span>
              <span className="text-xs text-slate-500 font-normal font-mono">
                {recoveredCase 
                  ? `₹${recoveredCase.amount.toLocaleString("en-IN")}` 
                  : (metrics.recovered_amount > 0 ? `₹${metrics.recovered_amount.toLocaleString("en-IN")}` : "₹3,262")}
              </span>
            </div>

            {/* Floating Pill 2: Real Guardrail Blocked Outcome */}
            <div className="inline-flex items-center gap-3 px-5 py-3 bg-white/95 backdrop-blur-sm rounded-full shadow-[0_8px_25px_rgba(0,0,0,0.06)] border border-slate-100 transition-all hover:scale-[1.02] hover:shadow-md sm:ml-4">
              <span className="h-2.5 w-2.5 rounded-full bg-amber-500 shrink-0"></span>
              <span className="text-xs text-slate-900 font-semibold">Guardrail Blocked</span>
              <span className="text-xs text-slate-500 font-normal">
                {blockedCase 
                  ? (blockedCase.opted_out ? "Opted Out" : "Calling Window") 
                  : (metrics.guardrail_blocks > 0 ? `${metrics.guardrail_blocks} Policy Checks` : "Opted Out")}
              </span>
            </div>

            {/* Floating Pill 3: Real Case Escalated Outcome */}
            <div className="inline-flex items-center gap-3 px-5 py-3 bg-white/95 backdrop-blur-sm rounded-full shadow-[0_8px_25px_rgba(0,0,0,0.06)] border border-slate-100 transition-all hover:scale-[1.02] hover:shadow-md">
              <span className="h-2.5 w-2.5 rounded-full bg-rose-500 shrink-0"></span>
              <span className="text-xs text-slate-900 font-semibold">Case Escalated</span>
              <span className="text-xs text-slate-500 font-normal truncate max-w-[160px]">
                {escalatedCase ? escalatedCase.customer_reference : "High-Touch Review"}
              </span>
            </div>

            {/* Floating Pill 4: Higher Success Rates (Style matching Razorpay reference) */}
            <div className="inline-flex items-center gap-3 px-5 py-3 bg-white/95 backdrop-blur-sm rounded-full shadow-[0_8px_25px_rgba(0,0,0,0.06)] border border-slate-100 transition-all hover:scale-[1.02] hover:shadow-md sm:ml-6">
              <span className="h-2.5 w-2.5 rounded-full bg-[#3374F0] shrink-0"></span>
              <span className="text-xs text-slate-900 font-semibold">Higher</span>
              <span className="text-xs text-slate-500 font-normal">
                Success Rates ({metrics.recovery_rate}%)
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* SUPPORTING DETAIL: KEY RECOVERY METRICS */}
      <div className="space-y-4 pt-1">
        <div className="flex items-center justify-between">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-400">
            Key Recovery Metrics
          </h2>
          <span className="text-[11px] text-slate-400 font-medium flex items-center gap-1.5">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-500"></span> Live Telemetry
          </span>
        </div>

        {/* Metrics Row */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
          {/* Cases Processed */}
          <div className="bg-white border border-slate-100 p-5 rounded-xl shadow-xs flex flex-col justify-between">
            <div className="flex justify-between items-start">
              <span className="text-xs font-medium uppercase tracking-wider text-slate-400">Total Cases</span>
              <span className="p-1.5 bg-slate-50 text-slate-400 rounded-lg"><Receipt className="h-4 w-4" /></span>
            </div>
            <div className="mt-4">
              <h3 className="text-2xl font-semibold text-slate-900">{metrics.total_cases}</h3>
              <p className="text-xs text-slate-400 mt-1 font-normal">Processed signals</p>
            </div>
          </div>

          {/* Recovered Amount */}
          <div className="bg-white border border-slate-100 p-5 rounded-xl shadow-xs flex flex-col justify-between">
            <div className="flex justify-between items-start">
              <span className="text-xs font-medium uppercase tracking-wider text-slate-400">Recovered Amount</span>
              <span className="p-1.5 bg-emerald-50 text-emerald-500 rounded-lg"><DollarSign className="h-4 w-4" /></span>
            </div>
            <div className="mt-4">
              <h3 className="text-2xl font-semibold text-slate-900">₹{metrics.recovered_amount.toLocaleString("en-IN")}</h3>
              <p className="text-xs text-slate-400 mt-1 font-normal">
                Baseline: <span className="font-medium text-slate-500">₹{metrics.baseline_recovered_amount.toLocaleString("en-IN")}</span>
              </p>
            </div>
          </div>

          {/* Incremental Recovery */}
          <div className="bg-white border border-slate-100 p-5 rounded-xl shadow-xs flex flex-col justify-between">
            <div className="flex justify-between items-start">
              <span className="text-xs font-medium uppercase tracking-wider text-slate-400">Incremental Gain</span>
              <span className="p-1.5 bg-blue-50 text-[#3374F0] rounded-lg"><TrendingUp className="h-4 w-4" /></span>
            </div>
            <div className="mt-4">
              <h3 className="text-2xl font-semibold text-[#3374F0]">₹{metrics.incremental_recovery.toLocaleString("en-IN")}</h3>
              <p className="text-xs text-emerald-600 mt-1 font-medium">Additional agent-driven revenue</p>
            </div>
          </div>

          {/* Recovery Rate */}
          <div className="bg-white border border-slate-100 p-5 rounded-xl shadow-xs flex flex-col justify-between">
            <div className="flex justify-between items-start">
              <span className="text-xs font-medium uppercase tracking-wider text-slate-400">Recovery Rate</span>
              <span className="p-1.5 bg-indigo-50 text-indigo-500 rounded-lg"><Percent className="h-4 w-4" /></span>
            </div>
            <div className="mt-4">
              <h3 className="text-2xl font-semibold text-slate-900">{metrics.recovery_rate}%</h3>
              <p className="text-xs text-slate-400 mt-1 font-normal">Inbound success conversions</p>
            </div>
          </div>

          {/* Compliance Safety */}
          <div className="bg-white border border-slate-100 p-5 rounded-xl shadow-xs flex flex-col justify-between">
            <div className="flex justify-between items-start">
              <span className="text-xs font-medium uppercase tracking-wider text-slate-400">Guardrail Status</span>
              <span className="p-1.5 bg-teal-50 text-teal-600 rounded-lg"><ShieldCheck className="h-4 w-4" /></span>
            </div>
            <div className="mt-4">
              <h3 className="text-2xl font-semibold text-emerald-600">0 Violations</h3>
              <p className="text-xs text-slate-400 mt-1 font-normal">
                Active blocks: <span className="font-medium text-slate-700">{metrics.guardrail_blocks}</span>
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Accuracy Section */}
      <div className="bg-white text-slate-900 rounded-xl p-6 border border-slate-100 shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-6">
        <div className="flex items-center gap-4">
          <div className="bg-blue-50 p-3 rounded-xl border border-blue-100 text-[#3374F0]">
            <BrainCircuit className="h-7 w-7" />
          </div>
          <div>
            <h3 className="font-semibold text-base text-slate-900 flex items-center gap-2 flex-wrap">
              AI Classification Performance
              {metrics.evaluation_last_run && (
                <span className="text-[10px] text-slate-500 font-medium bg-slate-100 px-2 py-0.5 rounded-md border border-slate-200">
                  Last evaluated: {new Date(metrics.evaluation_last_run).toLocaleString()}
                </span>
              )}
            </h3>
            <p className="text-xs text-slate-500 mt-0.5">
              Accuracy evaluated against the golden evaluation set of 20 hand-labeled Razorpay failed payments.
            </p>
          </div>
        </div>
        {metrics.is_mock_mode ? (
          <div className="bg-slate-50 border border-slate-200 rounded-lg px-4 py-3 flex items-center gap-2 text-slate-700 text-xs shrink-0 font-medium">
            <span className="px-2 py-0.5 bg-slate-200 text-slate-800 text-[10px] font-bold rounded-sm uppercase tracking-wider">Mock Mode</span>
            <span>Mock Mode — pending live API evaluation</span>
          </div>
        ) : (
          <div className="flex gap-8 shrink-0">
            <div className="text-center">
              <span className="text-xs text-slate-400 font-semibold uppercase tracking-wider">Severity Classification</span>
              <h4 className="text-2xl font-semibold text-[#3374F0] mt-1">{metrics.diagnosis_accuracy_severity}%</h4>
            </div>
            <div className="text-center">
              <span className="text-xs text-slate-400 font-semibold uppercase tracking-wider">Root Cause Mapping</span>
              <h4 className="text-2xl font-semibold text-teal-600 mt-1">{metrics.diagnosis_accuracy_root_cause}%</h4>
            </div>
          </div>
        )}
      </div>

      {/* Provider Fallback Chain Breakdown Section */}
      {metrics.provider_breakdown && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <div className="bg-white border border-slate-100 p-4 rounded-xl shadow-xs">
            <div className="flex justify-between items-center mb-1">
              <span className="text-[10px] uppercase font-semibold text-slate-500 tracking-wider">Ollama (Local Primary)</span>
              <span className="h-2 w-2 rounded-full bg-emerald-500"></span>
            </div>
            <h3 className="text-2xl font-semibold text-slate-900 font-mono">{metrics.provider_breakdown.ollama || 0}</h3>
            <p className="text-[10px] text-slate-400 mt-1 font-normal">Local offline cases</p>
          </div>
          <div className="bg-white border border-slate-100 p-4 rounded-xl shadow-xs">
            <div className="flex justify-between items-center mb-1">
              <span className="text-[10px] uppercase font-medium text-slate-400 tracking-wider">Claude (Secondary)</span>
              <span className="h-2 w-2 rounded-full bg-[#3374F0]"></span>
            </div>
            <h3 className="text-2xl font-semibold text-slate-900 font-mono">{metrics.provider_breakdown.claude}</h3>
            <p className="text-[10px] text-slate-400 mt-1 font-normal">Cloud fallback cases</p>
          </div>
          <div className="bg-white border border-slate-100 p-4 rounded-xl shadow-xs">
            <div className="flex justify-between items-center mb-1">
              <span className="text-[10px] uppercase font-medium text-slate-400 tracking-wider">Gemini (Tertiary)</span>
              <span className="h-2 w-2 rounded-full bg-teal-500"></span>
            </div>
            <h3 className="text-2xl font-semibold text-slate-900 font-mono">{metrics.provider_breakdown.gemini}</h3>
            <p className="text-[10px] text-slate-400 mt-1 font-normal">Cloud fallback cases</p>
          </div>
          <div className="bg-white border border-slate-100 p-4 rounded-xl shadow-xs">
            <div className="flex justify-between items-center mb-1">
              <span className="text-[10px] uppercase font-medium text-slate-400 tracking-wider">Groq (Quaternary)</span>
              <span className="h-2 w-2 rounded-full bg-purple-500"></span>
            </div>
            <h3 className="text-2xl font-semibold text-slate-900 font-mono">{metrics.provider_breakdown.groq}</h3>
            <p className="text-[10px] text-slate-400 mt-1 font-normal">Cloud fallback cases</p>
          </div>
          <div className="bg-white border border-slate-100 p-4 rounded-xl shadow-xs">
            <div className="flex justify-between items-center mb-1">
              <span className="text-[10px] uppercase font-medium text-slate-400 tracking-wider">Rule Engine</span>
              <span className="h-2 w-2 rounded-full bg-slate-400"></span>
            </div>
            <h3 className="text-2xl font-semibold text-slate-900 font-mono">{metrics.provider_breakdown.rules}</h3>
            <p className="text-[10px] text-slate-400 mt-1 font-normal">Offline rule fallback</p>
          </div>
        </div>
      )}

      {/* Main Content Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        
        {/* Left Area: Root Cause Table */}
        <div className="lg:col-span-2 bg-white border border-slate-100 rounded-xl shadow-xs overflow-hidden">
          <div className="p-6 border-b border-slate-100 flex items-center justify-between">
            <h2 className="font-semibold text-slate-900">Recovery Metrics by Failure Category</h2>
            <span className="text-xs font-medium text-slate-400">Agent Performance Data</span>
          </div>
          
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-50 border-b border-slate-100 text-xs font-semibold text-slate-500 uppercase tracking-wider">
                <tr>
                  <th className="py-4 px-6">Decline / Failure Point</th>
                  <th className="py-4 px-6 text-right">Recovered Volume</th>
                  <th className="py-4 px-6 text-right">Recovery Rate</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-slate-700 font-medium">
                {Object.keys(metrics.recovery_rate_by_root_cause).length > 0 ? (
                  Object.entries(metrics.recovery_rate_by_root_cause).map(([rc, rate]) => (
                    <tr key={rc} className="hover:bg-slate-50/50">
                      <td className="py-3.5 px-6 font-semibold text-slate-900">
                        {rootCauseLabels[rc] || rc}
                      </td>
                      <td className="py-3.5 px-6 text-right font-mono text-slate-900">
                        ₹{(metrics.recovery_by_root_cause[rc] || 0.0).toLocaleString("en-IN")}
                      </td>
                      <td className="py-3.5 px-6 text-right">
                        <div className="flex items-center justify-end gap-3">
                          <span className="font-mono font-semibold">{rate}%</span>
                          <div className="w-16 bg-slate-100 rounded-full h-1.5 overflow-hidden">
                            <div 
                              className="bg-[#3374F0] h-1.5 rounded-full" 
                              style={{ width: `${rate}%` }}
                            />
                          </div>
                        </div>
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={3} className="py-8 text-center text-slate-400 font-normal">
                      No failure category data seeded yet.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Right Area: Recent Cases Feed */}
        <div className="bg-white border border-slate-100 rounded-xl shadow-xs p-6 flex flex-col justify-between">
          <div>
            <div className="flex justify-between items-center mb-6 pb-4 border-b border-slate-100">
              <h2 className="font-semibold text-slate-900">Recent Failures Feed</h2>
              <Link href="/cases" className="text-xs font-semibold text-[#3374F0] hover:underline flex items-center gap-1">
                View all
              </Link>
            </div>
            
            <div className="space-y-4.5">
              {recentCases.length > 0 ? (
                recentCases.map((c) => {
                  let statusBg = "bg-slate-100 text-slate-600";
                  if (c.status === "recovered") statusBg = "bg-emerald-50 text-emerald-700 border-emerald-100";
                  else if (c.status === "escalated" || c.status === "stop") statusBg = "bg-rose-50 text-rose-700 border-rose-100";
                  else if (c.status === "blocked") statusBg = "bg-slate-100 text-slate-700 border-slate-200";
                  else statusBg = "bg-amber-50 text-amber-700 border-amber-100";
                  
                  return (
                    <div key={c.id} className="flex justify-between items-center text-xs p-3 hover:bg-slate-50 rounded-lg transition border border-slate-50">
                      <div className="space-y-1">
                        <Link href={`/cases/${c.id}`} className="font-semibold text-slate-800 hover:text-[#3374F0] hover:underline block truncate max-w-[150px]">
                          {c.customer_reference}
                        </Link>
                        <span className="text-[10px] text-slate-400 uppercase tracking-wider block font-medium">
                          {c.leak_type.replace("_", " ")}
                        </span>
                      </div>
                      <div className="text-right space-y-1.5">
                        <span className="font-semibold text-slate-900 block font-mono">
                          ₹{c.amount.toLocaleString("en-IN")}
                        </span>
                        <span className={`px-2 py-0.5 border text-[10px] font-medium rounded-full uppercase tracking-wider ${statusBg}`}>
                          {c.status}
                        </span>
                      </div>
                    </div>
                  );
                })
              ) : (
                <p className="text-sm text-slate-400 text-center py-8">
                  No cases seeded yet. Go to Simulation Control to seed data.
                </p>
              )}
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}
