"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { fetchCases, Case } from "@/lib/api";
import { Search, Receipt, ArrowUpDown, Eye, ShieldOff, CheckCircle2 } from "lucide-react";

export default function CasesList() {
  const [cases, setCases] = useState<Case[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filter States
  const [search, setSearch] = useState("");
  const [leakType, setLeakType] = useState("");
  const [status, setStatus] = useState("");

  useEffect(() => {
    async function loadCases() {
      try {
        setLoading(true);
        const data = await fetchCases(leakType || undefined, status || undefined);
        setCases(data);
      } catch (err: any) {
        console.error(err);
        setError("Failed to fetch cases list.");
      } finally {
        setLoading(false);
      }
    }
    loadCases();
  }, [leakType, status]);

  const filteredCases = cases.filter((c) => {
    const matchSearch = c.customer_reference.toLowerCase().includes(search.toLowerCase()) ||
                        (c.customer_email && c.customer_email.toLowerCase().includes(search.toLowerCase()));
    return matchSearch;
  });

  return (
    <div className="flex-1 p-8 bg-[#f8fafc] space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Recovery Cases</h1>
        <p className="text-sm text-slate-500 font-normal">
          View all revenue-at-risk cases, their current status, and recovery interventions.
        </p>
      </div>

      {/* Filters and Controls */}
      <div className="bg-white p-5 border border-slate-100 rounded-xl shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-4">
        {/* Search */}
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
          <input
            type="text"
            placeholder="Search by customer ref or email..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2 border border-slate-200 rounded-lg text-sm bg-slate-50/50 focus:bg-white focus:outline-hidden focus:ring-2 focus:ring-[#3374F0]/20 focus:border-[#3374F0] transition"
          />
        </div>

        {/* Filters Grid */}
        <div className="flex flex-wrap items-center gap-3">
          {/* Leak Type */}
          <select
            value={leakType}
            onChange={(e) => setLeakType(e.target.value)}
            className="px-3.5 py-2 border border-slate-200 rounded-lg text-sm bg-white focus:outline-hidden focus:ring-2 focus:ring-[#3374F0]/20"
          >
            <option value="">All Leak Types</option>
            <option value="payment_failure">Payment Failures</option>
            <option value="receivable_overdue">B2B Promise-to-Pay</option>
          </select>

          {/* Status */}
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            className="px-3.5 py-2 border border-slate-200 rounded-lg text-sm bg-white focus:outline-hidden focus:ring-2 focus:ring-[#3374F0]/20"
          >
            <option value="">All Statuses</option>
            <option value="detected">Detected</option>
            <option value="diagnosing">Diagnosing</option>
            <option value="decided">Decided</option>
            <option value="blocked">Blocked</option>
            <option value="actioned">Actioned</option>
            <option value="recovered">Recovered</option>
            <option value="escalated">Escalated</option>
            <option value="stop">Stopped</option>
          </select>
        </div>
      </div>

      {/* Main Table Card */}
      <div className="bg-white border border-slate-100 rounded-xl shadow-xs overflow-hidden">
        {loading ? (
          <div className="py-20 text-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[#3374F0] mx-auto"></div>
            <p className="text-sm text-slate-400 mt-3">Filtering recovery lists...</p>
          </div>
        ) : error ? (
          <div className="p-8 text-center text-rose-500">{error}</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-50 border-b border-slate-100 text-xs font-semibold text-slate-500 uppercase tracking-wider">
                <tr>
                  <th className="py-4.5 px-6">Customer Reference</th>
                  <th className="py-4.5 px-6">Leak Type</th>
                  <th className="py-4.5 px-6">Amount</th>
                  <th className="py-4.5 px-6">Recovered</th>
                  <th className="py-4.5 px-6">Case Status</th>
                  <th className="py-4.5 px-6">Preference</th>
                  <th className="py-4.5 px-6">Registered Date</th>
                  <th className="py-4.5 px-6 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 font-medium text-slate-700">
                {filteredCases.length > 0 ? (
                  filteredCases.map((c) => {
                    // Status Pills Styling
                    let statusBg = "bg-slate-100 text-slate-600";
                    if (c.status === "recovered") {
                      statusBg = "bg-emerald-50 text-emerald-700 border-emerald-200";
                    } else if (c.status === "escalated" || c.status === "stop") {
                      statusBg = "bg-rose-50 text-rose-700 border-rose-200";
                    } else if (c.status === "blocked") {
                      statusBg = "bg-slate-100 text-slate-700 border-slate-300";
                    } else if (c.status === "detected") {
                      statusBg = "bg-sky-50 text-sky-700 border-sky-200";
                    } else {
                      statusBg = "bg-amber-50 text-amber-700 border-amber-200";
                    }

                    return (
                      <tr key={c.id} className="hover:bg-slate-50/50 transition duration-150">
                        <td className="py-4 px-6">
                          <Link href={`/cases/${c.id}`} className="font-semibold text-slate-900 hover:text-[#3374F0] hover:underline flex items-center gap-2">
                            <Receipt className="h-4 w-4 text-slate-400 shrink-0" />
                            <div className="truncate max-w-[150px]">
                              {c.customer_reference}
                            </div>
                          </Link>
                          <span className="text-[10px] text-slate-400 font-mono block mt-0.5 max-w-[150px] truncate">{c.id}</span>
                        </td>
                        <td className="py-4 px-6 text-xs uppercase tracking-wider text-slate-500">
                          {c.leak_type.replace("_", " ")}
                        </td>
                        <td className="py-4 px-6 font-mono text-slate-900">
                          ₹{c.amount.toLocaleString("en-IN")}
                        </td>
                        <td className="py-4 px-6 font-mono text-emerald-600">
                          {c.recovered_amount > 0 ? `₹${c.recovered_amount.toLocaleString("en-IN")}` : "—"}
                        </td>
                        <td className="py-4 px-6">
                          <span className={`px-2.5 py-0.5 border text-[10px] uppercase font-bold rounded-full tracking-wider ${statusBg}`}>
                            {c.status}
                          </span>
                        </td>
                        <td className="py-4 px-6">
                          {c.opted_out ? (
                            <span className="inline-flex items-center gap-1 px-2.5 py-0.5 border border-rose-200 bg-rose-50 text-rose-700 text-[10px] font-bold rounded-full uppercase tracking-wider">
                              <ShieldOff className="h-3 w-3 shrink-0" />
                              Opted Out
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 px-2.5 py-0.5 border border-emerald-200 bg-emerald-50 text-emerald-700 text-[10px] font-bold rounded-full uppercase tracking-wider">
                              <CheckCircle2 className="h-3 w-3 shrink-0" />
                              Subscribed
                            </span>
                          )}
                        </td>
                        <td className="py-4 px-6 text-xs text-slate-400 font-normal">
                          {new Date(c.created_at).toLocaleDateString("en-IN", {
                            year: "numeric",
                            month: "short",
                            day: "numeric",
                            hour: "2-digit",
                            minute: "2-digit"
                          })}
                        </td>
                        <td className="py-4 px-6 text-right">
                          <Link 
                            href={`/cases/${c.id}`} 
                            className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-slate-50 border border-slate-200 rounded-lg text-xs font-semibold text-slate-700 hover:bg-slate-100 hover:text-slate-950 transition"
                          >
                            <Eye className="h-3.5 w-3.5" />
                            Trace View
                          </Link>
                        </td>
                      </tr>
                    );
                  })
                ) : (
                  <tr>
                    <td colSpan={8} className="py-12 text-center text-slate-400 font-normal">
                      No cases found matching the search filters.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
