"use client";

import { useState } from "react";
import { seedDatabase, runSimulationTick, runEvaluation } from "@/lib/api";
import { Cpu, RotateCcw, Calendar, Moon, Sun, ArrowRight, Play, Terminal, HelpCircle, BrainCircuit } from "lucide-react";

interface LogEntry {
  timestamp: string;
  type: "info" | "success" | "warn" | "error";
  message: string;
}

export default function SimulationPage() {
  const [numCases, setNumCases] = useState(15);
  const [loading, setLoading] = useState(false);
  const [customTime, setCustomTime] = useState("");
  const [logs, setLogs] = useState<LogEntry[]>([
    {
      timestamp: new Date().toLocaleTimeString(),
      type: "info",
      message: "Simulation Console Initialized. Ready to seed and run recovery cycles."
    }
  ]);

  function appendLog(message: string, type: "info" | "success" | "warn" | "error" = "info") {
    setLogs((prev) => [
      { timestamp: new Date().toLocaleTimeString(), type, message },
      ...prev
    ]);
  }

  async function handleSeed() {
    try {
      setLoading(true);
      appendLog(`Seeding database with ${numCases} mock cases...`, "info");
      const res = await seedDatabase(numCases);
      appendLog(res.message, "success");
    } catch (err: any) {
      appendLog(err.message || "Failed to seed cases", "error");
    } finally {
      setLoading(false);
    }
  }

  async function handleTick(simulatedTime?: string) {
    try {
      setLoading(true);
      const timeStr = simulatedTime || "current server time";
      appendLog(`Triggering simulation sweep tick at ${timeStr}...`, "info");
      const res = await runSimulationTick(simulatedTime);
      appendLog(res.message, "success");
      appendLog(`Sweep output: ${res.actions_executed} actions executed, ${res.promises_reactivated} promises reactivated.`, "info");
    } catch (err: any) {
      appendLog(err.message || "Failed to execute simulation tick", "error");
    } finally {
      setLoading(false);
    }
  }

  async function handleEvaluate() {
    try {
      setLoading(true);
      appendLog("Triggering manual diagnostics evaluation in background...", "info");
      const res = await runEvaluation();
      appendLog(res.message, "success");
      appendLog("The evaluation is running asynchronously in the background. The metrics panel accuracy will update once it completes (takes ~80s).", "info");
    } catch (err: any) {
      appendLog(err.message || "Failed to trigger evaluation", "error");
    } finally {
      setLoading(false);
    }
  }

  // Pre-configured time travel helpers
  function timeTravelAndRun(type: "night" | "morning" | "future_p2p") {
    const target = new Date();
    
    if (type === "night") {
      // Set to 10:00 PM tonight
      target.setHours(22, 0, 0, 0);
      appendLog("Time Travel: Advancing simulated clock to 10:00 PM (Calling Window Closed)", "warn");
    } else if (type === "morning") {
      // Set to 10:00 AM tomorrow
      target.setDate(target.getDate() + 1);
      target.setHours(10, 0, 0, 0);
      appendLog("Time Travel: Advancing simulated clock to 10:00 AM Tomorrow (Calling Window Open)", "success");
    } else if (type === "future_p2p") {
      // Set to 5 days from now
      target.setDate(target.getDate() + 5);
      appendLog("Time Travel: Advancing simulated clock by +5 Days (B2B Promise-to-Pay Expiry)", "warn");
    }

    const isoStr = target.toISOString();
    setCustomTime(isoStr);
    handleTick(isoStr);
  }

  return (
    <div className="flex-1 p-8 bg-[#f8fafc] space-y-8 flex flex-col">
      
      {/* Header */}
      <div className="shrink-0">
        <h1 className="text-2xl font-semibold text-slate-900 flex items-center gap-2">
          <Cpu className="h-6 w-6 text-[#3374F0]" />
          Simulation Control Room
        </h1>
        <p className="text-sm text-slate-500 font-normal">
          Seed payment failure events and simulate time progression to test guardrails and Promise-to-Pay reactivations.
        </p>
      </div>

      <div className="flex-1 grid grid-cols-1 lg:grid-cols-2 gap-8 min-h-0">
        {/* Left Side: Control Panels */}
        <div className="space-y-6 overflow-y-auto pr-2 pb-6">
          
          {/* Seeding Card */}
          <div className="bg-white border border-slate-100 rounded-xl p-5 shadow-2xs space-y-4">
            <h2 className="font-semibold text-slate-900 text-sm">1. Reset and Seed Test Database</h2>
            <p className="text-xs text-slate-400 font-normal">
              Purges all current case records and seeds the database with N fresh randomized failed payment events.
            </p>
            
            <div className="flex items-center gap-3">
              <input
                type="number"
                min="1"
                max="100"
                value={numCases}
                onChange={(e) => setNumCases(parseInt(e.target.value) || 15)}
                className="w-24 px-3 py-2 border border-slate-200 rounded-lg text-sm font-mono focus:outline-hidden focus:ring-2 focus:ring-[#3374F0]/20"
              />
              <button
                onClick={handleSeed}
                disabled={loading}
                className="flex-1 px-4 py-2 bg-slate-900 hover:bg-slate-800 text-white rounded-lg text-xs font-semibold transition disabled:opacity-50"
              >
                Clear & Seed Events
              </button>
            </div>
          </div>

          {/* Time Travel Card */}
          <div className="bg-white border border-slate-100 rounded-xl p-5 shadow-2xs space-y-5">
            <h2 className="font-semibold text-slate-900 text-sm">2. Simulation Time Travel Console</h2>
            <p className="text-xs text-slate-400 font-normal">
              Gates compliance checking and schedules background worker ticks at specific simulated times.
            </p>

            {/* Quick Presets */}
            <div className="grid grid-cols-3 gap-3">
              <button
                onClick={() => timeTravelAndRun("night")}
                disabled={loading}
                className="p-3 border border-slate-100 bg-slate-50 hover:bg-slate-100 text-slate-700 hover:text-slate-900 rounded-xl text-center space-y-1.5 transition disabled:opacity-50"
              >
                <Moon className="h-5 w-5 mx-auto text-slate-400" />
                <span className="block text-[10px] font-bold uppercase tracking-wider">Night (10 PM)</span>
                <span className="block text-[9px] text-slate-400 font-normal leading-tight">Blocks contact guardrails</span>
              </button>
              <button
                onClick={() => timeTravelAndRun("morning")}
                disabled={loading}
                className="p-3 border border-slate-100 bg-slate-50 hover:bg-slate-100 text-slate-700 hover:text-slate-900 rounded-xl text-center space-y-1.5 transition disabled:opacity-50"
              >
                <Sun className="h-5 w-5 mx-auto text-amber-500" />
                <span className="block text-[10px] font-bold uppercase tracking-wider">Morning (10 AM)</span>
                <span className="block text-[9px] text-slate-400 font-normal leading-tight">Releases queued tasks</span>
              </button>
              <button
                onClick={() => timeTravelAndRun("future_p2p")}
                disabled={loading}
                className="p-3 border border-slate-100 bg-slate-50 hover:bg-slate-100 text-slate-700 hover:text-slate-900 rounded-xl text-center space-y-1.5 transition disabled:opacity-50"
              >
                <Calendar className="h-5 w-5 mx-auto text-[#3374F0]" />
                <span className="block text-[10px] font-bold uppercase tracking-wider">+5 Days Future</span>
                <span className="block text-[9px] text-slate-400 font-normal leading-tight">Breaks overdue P2Ps</span>
              </button>
            </div>

            {/* Custom Datetime Input */}
            <div className="border-t border-slate-50 pt-4 space-y-3">
              <label className="block text-xs font-semibold text-slate-500">Custom ISO Timestamp</label>
              <div className="flex gap-2">
                <input
                  type="text"
                  placeholder="YYYY-MM-DDTHH:MM:SS"
                  value={customTime}
                  onChange={(e) => setCustomTime(e.target.value)}
                  className="flex-1 px-3.5 py-2 border border-slate-200 rounded-lg text-xs font-mono focus:outline-hidden focus:ring-2 focus:ring-[#3374F0]/20"
                />
                <button
                  onClick={() => handleTick(customTime || undefined)}
                  disabled={loading}
                  className="px-4 py-2 bg-[#3374F0] hover:bg-[#2563EB] text-white rounded-lg text-xs font-bold transition flex items-center gap-1.5 shadow-sm disabled:opacity-50"
                >
                  <Play className="h-3 w-3" />
                  Execute Tick
                </button>
              </div>
            </div>
          </div>

          {/* Evaluation Card */}
          <div className="bg-white border border-slate-100 rounded-xl p-5 shadow-2xs space-y-4">
            <h2 className="font-semibold text-slate-900 text-sm">3. Diagnostics Accuracy Evaluation</h2>
            <p className="text-xs text-slate-400 font-normal">
              Triggers the offline diagnostics evaluation script against the golden 20-case test set. This executes AI diagnosis with primary and fallback providers and computes classification accuracy.
            </p>
            <button
              onClick={handleEvaluate}
              disabled={loading}
              className="w-full px-4 py-2 bg-[#3374F0] hover:bg-[#2563EB] text-white rounded-lg text-xs font-semibold transition disabled:opacity-50 flex items-center justify-center gap-1.5 shadow-xs"
            >
              <BrainCircuit className="h-4 w-4" />
              Re-run Evaluation
            </button>
          </div>

          {/* Test Guide Help Box */}
          <div className="bg-blue-50/60 border border-blue-100 rounded-xl p-5 space-y-3.5">
            <h3 className="font-semibold text-blue-950 text-xs flex items-center gap-1.5">
              <HelpCircle className="h-4.5 w-4.5 text-[#3374F0]" />
              Edge Case Test Workflows
            </h3>
            <ul className="list-disc pl-4 text-[11px] text-blue-900 space-y-2 leading-relaxed font-normal">
              <li>
                <strong>Calling Window Guardrail</strong>: Seed cases. Click <strong>Night (10 PM)</strong>. Open a case trace detail to see the SMS/Email actions marked as <code>pending</code> and blocked by <code>is_within_calling_window</code>. Click <strong>Morning (10 AM)</strong>. The scheduler sweeps and executes the queued task.
              </li>
              <li>
                <strong>B2B Promise-to-Pay Expiration</strong>: Go to Cases, click an active <i>Receivable Overdue</i> case. Log a Promise-to-pay date for tomorrow. Come back here and click <strong>+5 Days Future</strong>. Check the trace to see the promise transition to <code>broken</code> and reactivate recovery sequences.
              </li>
              <li>
                <strong>Coordinated Outreach Limit</strong>: Send multiple webhook payment failures on the same day for a single customer reference. The system links them to one active Case and does not spam the user.
              </li>
            </ul>
          </div>

        </div>

        {/* Right Side: Log output console */}
        <div className="bg-[#0C1220] border border-slate-800 rounded-xl flex flex-col h-full overflow-hidden shadow-xl">
          {/* Console Header */}
          <div className="px-5 py-3.5 border-b border-slate-800 flex justify-between items-center shrink-0">
            <h3 className="text-slate-300 font-bold text-xs font-mono flex items-center gap-2">
              <Terminal className="h-4 w-4 text-emerald-400" />
              Simulation Logs Console
            </h3>
            <button
              onClick={() => setLogs([])}
              className="text-[10px] font-semibold text-slate-500 hover:text-slate-300 flex items-center gap-1 font-mono transition"
            >
              <RotateCcw className="h-3 w-3" />
              Clear Console
            </button>
          </div>

          {/* Console Log Area */}
          <div className="flex-1 p-5 overflow-y-auto font-mono text-xs space-y-2.5 min-h-0 select-text">
            {logs.length > 0 ? (
              logs.map((log, index) => {
                let colorClass = "text-slate-400";
                if (log.type === "success") colorClass = "text-emerald-400";
                else if (log.type === "warn") colorClass = "text-amber-400";
                else if (log.type === "error") colorClass = "text-rose-400";

                return (
                  <div key={index} className="flex items-start gap-3.5 leading-relaxed font-normal">
                    <span className="text-slate-600 shrink-0 select-none">[{log.timestamp}]</span>
                    <span className={colorClass}>{log.message}</span>
                  </div>
                );
              })
            ) : (
              <p className="text-slate-600 text-center py-10 font-normal italic select-none">Console log cleared.</p>
            )}
          </div>
        </div>

      </div>
    </div>
  );
}
