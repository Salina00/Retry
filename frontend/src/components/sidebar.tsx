"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard, ReceiptText, RefreshCw, ShieldAlert, Cpu } from "lucide-react";

export default function Sidebar() {
  const pathname = usePathname();

  const links = [
    { name: "Dashboard", href: "/", icon: LayoutDashboard },
    { name: "Cases", href: "/cases", icon: ReceiptText },
    { name: "Simulation Control", href: "/batch", icon: Cpu },
  ];

  return (
    <aside className="w-64 bg-[#0B1220] text-slate-300 flex flex-col h-screen border-r border-slate-800 shrink-0">
      {/* Brand Logo */}
      <div className="p-6 border-b border-slate-800 flex items-center gap-3">
        <div className="bg-[#0B66E4] p-2 rounded-lg text-white">
          <RefreshCw className="h-5 w-5 animate-spin-slow" />
        </div>
        <div>
          <h1 className="font-semibold text-lg text-white tracking-wide">Retry</h1>
          <p className="text-xs text-[#0B66E4] font-medium uppercase tracking-wider">AI Recovery Agent</p>
        </div>
      </div>

      {/* Navigation Links */}
      <nav className="flex-1 px-4 py-6 space-y-1.5">
        {links.map((link) => {
          const Icon = link.icon;
          const isActive = pathname === link.href || (link.href !== "/" && pathname.startsWith(link.href));
          
          return (
            <Link
              key={link.name}
              href={link.href}
              className={`flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium transition-all duration-200 ${
                isActive
                  ? "bg-[#0B66E4] text-white shadow-lg shadow-blue-900/20"
                  : "hover:bg-slate-800 hover:text-white"
              }`}
            >
              <Icon className={`h-4.5 w-4.5 ${isActive ? "text-white" : "text-slate-400 group-hover:text-white"}`} />
              {link.name}
            </Link>
          );
        })}
      </nav>

      {/* Footer Info */}
      <div className="p-4 border-t border-slate-800 bg-[#070b14] flex flex-col gap-2">
        <div className="flex items-center gap-2 text-xs text-emerald-400">
          <span className="h-2 w-2 bg-emerald-500 rounded-full animate-pulse"></span>
          <span>Agent Node Online</span>
        </div>
        <div className="flex items-center gap-2 text-xs text-slate-400">
          <ShieldAlert className="h-4.5 w-4.5 text-blue-500" />
          <span>Guardrails Enforced</span>
        </div>
      </div>
    </aside>
  );
}
