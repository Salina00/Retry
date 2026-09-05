"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { RefreshCw, Headphones, ArrowRight, Menu, X, User as UserIcon, LogOut } from "lucide-react";
import { useAuth } from "@/lib/auth";

export default function Navbar() {
  const pathname = usePathname();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const { user, isLoggedIn, logout } = useAuth();

  const links = [
    { name: "Dashboard", href: "/" },
    { name: "Cases", href: "/cases" },
    { name: "Simulation Control", href: "/batch" },
  ];

  return (
    <header className="fixed top-0 left-0 right-0 z-50 bg-white/95 backdrop-blur-xs border-b border-slate-200/80 shadow-[0_1px_3px_rgba(0,0,0,0.03)]">
      <div className="w-full px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        {/* Left: Logo & Wordmark + Horizontal Nav Links */}
        <div className="flex items-center gap-8 lg:gap-10">
          {/* Logo and Wordmark */}
          <Link href="/" className="flex items-center gap-2.5 group">
            <div className="bg-[#3374F0] p-1.5 rounded-sm text-white flex items-center justify-center shadow-xs transition-transform group-hover:scale-105">
              <RefreshCw className="h-4.5 w-4.5" />
            </div>
            <span className="font-bold text-lg text-slate-900 tracking-tight">Retry</span>
          </Link>

          {/* Center-left Nav Links */}
          <nav className="hidden md:flex items-center gap-7 lg:gap-8">
            {links.map((link) => {
              const isActive =
                link.href === "/"
                  ? pathname === "/"
                  : pathname === link.href || pathname.startsWith(link.href + "/");

              return (
                <Link
                  key={link.name}
                  href={link.href}
                  className={`text-sm transition-colors ${
                    isActive
                      ? "text-[#3374F0] font-semibold"
                      : "text-slate-600 hover:text-slate-900 font-medium"
                  }`}
                >
                  {link.name}
                </Link>
              );
            })}
          </nav>
        </div>

        {/* Right side: Razorpay-style utility icon + Auth status */}
        <div className="hidden md:flex items-center gap-3.5">
          {/* Support / Help utility icon */}
          <a
            href="http://127.0.0.1:8000/docs"
            target="_blank"
            rel="noopener noreferrer"
            title="Help & API Documentation"
            className="p-1.5 text-slate-500 hover:text-[#3374F0] transition-colors rounded-sm hover:bg-slate-50 mr-1"
          >
            <Headphones className="h-4.5 w-4.5" />
          </a>

          {isLoggedIn && user ? (
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2 px-3 py-1.5 bg-slate-50 rounded-full border border-slate-200/80 text-xs">
                <span className="h-2 w-2 rounded-full bg-emerald-500"></span>
                <span className="font-semibold text-slate-800">{user.name}</span>
                <span className="text-[10px] text-slate-500 bg-white px-2 py-0.5 rounded-full border border-slate-200 capitalize font-medium">
                  {user.role === "compliance_manager" ? "Manager" : "Specialist"}
                </span>
              </div>
              <button
                onClick={() => logout()}
                className="px-3 py-1.5 rounded-sm text-xs font-semibold text-slate-600 hover:text-rose-600 hover:bg-rose-50 transition-colors flex items-center gap-1.5"
              >
                <LogOut className="h-3.5 w-3.5" />
                Logout
              </button>
            </div>
          ) : (
            <>
              {/* Outline Login button */}
              <Link
                href="/login"
                className="px-4 py-1.5 rounded-sm text-sm font-semibold text-[#3374F0] bg-white hover:bg-blue-50/50 border border-[#3374F0] transition-all duration-150"
              >
                Login
              </Link>

              {/* Solid Sign Up button with right arrow */}
              <Link
                href="/signup"
                className="px-4 py-1.5 rounded-sm text-sm font-semibold text-white bg-[#3374F0] hover:bg-[#2563EB] transition-all duration-150 shadow-xs flex items-center gap-1.5"
              >
                Sign Up
                <ArrowRight className="h-3.5 w-3.5" />
              </Link>
            </>
          )}
        </div>

        {/* Mobile menu toggle button */}
        <div className="flex items-center md:hidden gap-2">
          {isLoggedIn ? (
            <button
              onClick={() => logout()}
              className="px-2.5 py-1 rounded-sm text-xs font-semibold text-rose-600 border border-rose-200 bg-rose-50"
            >
              Logout
            </button>
          ) : (
            <Link
              href="/signup"
              className="px-3 py-1.5 rounded-sm text-xs font-semibold text-white bg-[#3374F0] hover:bg-[#2563EB] transition-all shadow-xs flex items-center gap-1"
            >
              Sign Up <ArrowRight className="h-3 w-3" />
            </Link>
          )}
          <button
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className="p-2 rounded-lg text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition-colors"
            aria-label="Toggle menu"
          >
            {mobileMenuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
        </div>
      </div>

      {/* Mobile dropdown menu */}
      {mobileMenuOpen && (
        <div className="md:hidden border-t border-slate-200 bg-white px-4 pt-3 pb-5 space-y-3 shadow-lg">
          <nav className="flex flex-col space-y-1.5">
            {links.map((link) => {
              const isActive =
                link.href === "/"
                  ? pathname === "/"
                  : pathname === link.href || pathname.startsWith(link.href + "/");

              return (
                <Link
                  key={link.name}
                  href={link.href}
                  onClick={() => setMobileMenuOpen(false)}
                  className={`px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                    isActive
                      ? "bg-blue-50 text-[#3374F0] font-semibold"
                      : "text-slate-700 hover:bg-slate-50"
                  }`}
                >
                  {link.name}
                </Link>
              );
            })}
          </nav>

          <div className="pt-2 border-t border-slate-100 flex flex-col gap-2">
            <a
              href="http://127.0.0.1:8000/docs"
              target="_blank"
              rel="noopener noreferrer"
              className="px-3 py-1.5 text-sm font-medium text-slate-600 hover:text-slate-900 flex items-center gap-2"
            >
              <Headphones className="h-4 w-4 text-[#3374F0]" />
              Help & API Docs
            </a>

            {isLoggedIn && user ? (
              <div className="flex items-center justify-between p-2.5 bg-slate-50 rounded-lg text-xs">
                <div>
                  <span className="font-semibold text-slate-800 block">{user.name}</span>
                  <span className="text-[10px] text-slate-500 capitalize">{user.role.replace("_", " ")}</span>
                </div>
                <button
                  onClick={() => {
                    logout();
                    setMobileMenuOpen(false);
                  }}
                  className="text-xs font-semibold text-rose-600 hover:underline"
                >
                  Log out
                </button>
              </div>
            ) : (
              <div className="flex gap-2 pt-1">
                <Link
                  href="/login"
                  onClick={() => setMobileMenuOpen(false)}
                  className="flex-1 text-center px-4 py-2 rounded-sm text-sm font-semibold text-[#3374F0] bg-white border border-[#3374F0]"
                >
                  Login
                </Link>
                <Link
                  href="/signup"
                  onClick={() => setMobileMenuOpen(false)}
                  className="flex-1 text-center px-4 py-2 rounded-sm text-sm font-semibold text-white bg-[#3374F0] flex items-center justify-center gap-1"
                >
                  Sign Up <ArrowRight className="h-3.5 w-3.5" />
                </Link>
              </div>
            )}
          </div>
        </div>
      )}
    </header>
  );
}
