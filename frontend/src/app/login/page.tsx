"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { RefreshCw, ArrowRight, AlertCircle, Sparkles, Lock, Mail } from "lucide-react";
import { loginApi } from "@/lib/auth";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      await loginApi(email, password);
      router.push("/");
    } catch (err: any) {
      setError(err.message || "Invalid credentials. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const handleFillDemo = () => {
    setEmail("demo@razorpay.com");
    setPassword("password123");
    setError(null);
  };

  return (
    <div className="min-h-[calc(100vh-4rem)] flex items-center justify-center p-4 sm:p-6 bg-[#f8fafc]">
      <div className="bg-white border border-slate-200/80 rounded-2xl p-6 sm:p-10 shadow-[0_4px_25px_rgba(0,0,0,0.03)] max-w-md w-full space-y-6">
        {/* Brand Header */}
        <div className="text-center space-y-2">
          <div className="inline-flex items-center gap-2.5">
            <span className="flex items-center justify-center h-9 w-9 rounded-lg bg-[#3374F0] text-white shadow-xs">
              <RefreshCw className="h-4.5 w-4.5" />
            </span>
            <span className="font-bold text-xl tracking-tight text-slate-900">
              Retry
            </span>
          </div>

          <h1 className="text-2xl font-bold text-slate-900 tracking-tight pt-2">
            Welcome to Retry
          </h1>
          <p className="text-xs sm:text-sm text-slate-500 font-normal">
            Log in to manage autonomous revenue recovery workflows.
          </p>
        </div>

        {/* Quick Demo Fill Helper */}
        <div className="bg-blue-50/70 border border-blue-100 rounded-xl p-3.5 text-center">
          <p className="text-xs text-slate-600 mb-2">
            Evaluating the prototype? Use the pre-seeded account:
          </p>
          <button
            type="button"
            onClick={handleFillDemo}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-white border border-blue-200 hover:border-[#3374F0] text-[#3374F0] rounded-lg text-xs font-semibold transition shadow-2xs hover:bg-blue-50/50"
          >
            <Sparkles className="h-3.5 w-3.5 text-[#3374F0]" />
            Auto-fill Demo Account
          </button>
        </div>

        {/* Error Alert */}
        {error && (
          <div className="p-3 bg-rose-50 border border-rose-100 rounded-xl flex items-center gap-2 text-rose-700 text-xs font-medium">
            <AlertCircle className="h-4 w-4 shrink-0 text-rose-500" />
            <span>{error}</span>
          </div>
        )}

        {/* Login Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider">
              Work Email
            </label>
            <div className="relative">
              <span className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400">
                <Mail className="h-4 w-4" />
              </span>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="name@company.com"
                className="w-full pl-9 pr-3 py-2.5 bg-slate-50/50 border border-slate-200 rounded-lg text-sm text-slate-900 focus:bg-white focus:outline-hidden focus:ring-2 focus:ring-[#3374F0]/20 focus:border-[#3374F0] transition"
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <div className="flex justify-between items-center">
              <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider">
                Password
              </label>
            </div>
            <div className="relative">
              <span className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400">
                <Lock className="h-4 w-4" />
              </span>
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full pl-9 pr-3 py-2.5 bg-slate-50/50 border border-slate-200 rounded-lg text-sm text-slate-900 focus:bg-white focus:outline-hidden focus:ring-2 focus:ring-[#3374F0]/20 focus:border-[#3374F0] transition"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 px-4 bg-[#3374F0] hover:bg-[#2563EB] text-white rounded-lg text-sm font-semibold transition-all shadow-xs flex items-center justify-center gap-2 disabled:opacity-50"
          >
            {loading ? (
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
            ) : (
              <>
                Log In to Workspace
                <ArrowRight className="h-4 w-4" />
              </>
            )}
          </button>
        </form>

        {/* Footer Link */}
        <div className="text-center pt-2 border-t border-slate-100">
          <p className="text-xs text-slate-500">
            Don&apos;t have an account?{" "}
            <Link
              href="/signup"
              className="text-[#3374F0] font-semibold hover:underline"
            >
              Sign Up
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
