"use client";

import React, { useEffect, useState } from "react";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Shield, AlertCircle, ArrowRight, CheckCircle2 } from "lucide-react";

const DEMO_USERS = [
  {
    label: "Head of Dept (CS)",
    email: "hod.cs@timewise.edu",
    role: "HOD",
    desc: "Manage schedules, conflict audits, CP-SAT generation & approvals",
  },
  {
    label: "Faculty / Teacher",
    email: "teacher.sharma@timewise.edu",
    role: "TEACHER",
    desc: "Personal teaching schedule & reschedule proposals",
  },
  {
    label: "Class Representative (Ashutosh)",
    email: "cr.cs3a@timewise.edu",
    role: "CR",
    desc: "Ashutosh • Section CS-3A class schedule & clash reporting",
  },
  {
    label: "College Management",
    email: "admin@timewise.edu",
    role: "ADMIN",
    desc: "Cross-department timetable summaries & room utilization",
  },
];

const DEFAULT_DEMO_PASSWORD = "DemoPass@2026!";

export default function LoginPage() {
  const router = useRouter();
  const { user, login } = useAuth();
  const [email, setEmail] = useState("hod.cs@timewise.edu");
  const [password, setPassword] = useState(DEFAULT_DEMO_PASSWORD);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // If already logged in, redirect directly to dashboard
  useEffect(() => {
    if (user) {
      router.push("/dashboard");
    }
  }, [user, router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      await login(email, password);
      router.push("/dashboard");
    } catch (err: any) {
      setError(err?.detail || "Invalid email or password. Please verify credentials.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSelectDemoUser = (demoEmail: string) => {
    setEmail(demoEmail);
    setPassword(DEFAULT_DEMO_PASSWORD);
    setError(null);
  };

  const handleQuickLoginAs = async (demoEmail: string) => {
    setEmail(demoEmail);
    setPassword(DEFAULT_DEMO_PASSWORD);
    setError(null);
    setIsSubmitting(true);
    try {
      await login(demoEmail, DEFAULT_DEMO_PASSWORD);
      router.push("/dashboard");
    } catch (err: any) {
      setError(err?.detail || "Authentication failed.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#F7F9FC] flex flex-col justify-center py-12 px-4 sm:px-6 lg:px-8">
      <div className="sm:mx-auto sm:w-full sm:max-w-md text-center space-y-2">
        <div className="mx-auto w-20 h-20 relative flex items-center justify-center mb-1">
          <Image
            src="/logo.png"
            alt="Timeverse Logo"
            width={80}
            height={80}
            priority
            className="object-contain"
          />
        </div>
        <h1 className="text-2xl sm:text-3xl font-bold text-[#17324D] tracking-tight">Timeverse Portal</h1>
        <p className="text-xs sm:text-sm text-[#697586]">
          Timetable Planner • Smart Rescheduler • Conflict Detector
        </p>
      </div>

      <div className="mt-6 sm:mx-auto sm:w-full sm:max-w-md">
        <Card className="shadow-sm border-[#E2E7EE] bg-white rounded-xl">
          <CardHeader className="pb-3 border-b border-slate-100">
            <CardTitle className="text-base text-[#17324D]">Sign In to Your Workspace</CardTitle>
            <CardDescription className="text-xs text-[#697586]">
              Enter institutional credentials or pick a role below for instant demo login.
            </CardDescription>
          </CardHeader>
          <CardContent className="pt-4">
            {error && (
              <div className="mb-4 p-3 rounded-lg bg-rose-50 border border-rose-200 flex items-start space-x-2 text-[#B42332] text-xs">
                <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
                <span>{error}</span>
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-3.5">
              <div>
                <label className="block text-[11px] font-bold text-[#17324D] uppercase tracking-wider mb-1">
                  Institutional Email
                </label>
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="name@timewise.edu"
                  className="w-full px-3 py-2 rounded-lg border border-[#E2E7EE] bg-white text-slate-800 text-xs focus:outline-none focus:ring-2 focus:ring-[#1261A0] focus:border-transparent transition-all"
                />
              </div>

              <div>
                <label className="block text-[11px] font-bold text-[#17324D] uppercase tracking-wider mb-1">
                  Password
                </label>
                <input
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••••••"
                  className="w-full px-3 py-2 rounded-lg border border-[#E2E7EE] bg-white text-slate-800 text-xs focus:outline-none focus:ring-2 focus:ring-[#1261A0] focus:border-transparent transition-all"
                />
              </div>

              <button
                type="submit"
                disabled={isSubmitting}
                className="w-full mt-2 py-2.5 px-4 rounded-lg bg-[#1261A0] hover:bg-[#0E4E82] text-white text-xs font-semibold shadow-xs transition-colors flex items-center justify-center disabled:opacity-50"
              >
                {isSubmitting ? "Authenticating..." : "Sign In to Dashboard &rarr;"}
              </button>
            </form>

            {/* Quick-Select Demo Personas for One-Click Instant Login */}
            <div className="mt-6 pt-4 border-t border-slate-100">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-bold text-[#17324D] flex items-center">
                  <Shield className="w-3.5 h-3.5 mr-1 text-[#1261A0]" /> One-Click Role Access
                </span>
                <span className="text-[10px] text-slate-400 font-medium">Click to Sign In</span>
              </div>
              <div className="space-y-2">
                {DEMO_USERS.map((demo) => (
                  <button
                    key={demo.email}
                    type="button"
                    onClick={() => handleQuickLoginAs(demo.email)}
                    disabled={isSubmitting}
                    className="w-full text-left p-2.5 rounded-lg border border-[#E2E7EE] hover:border-[#1261A0] hover:bg-[#EAF3FB] flex items-center justify-between text-xs transition-colors group"
                  >
                    <div>
                      <div className="flex items-center space-x-1.5">
                        <span className="font-bold text-[#17324D] group-hover:text-[#1261A0]">{demo.label}</span>
                        <span className="text-[9px] font-mono px-1.5 py-0.2 rounded bg-slate-100 text-slate-600">
                          {demo.role}
                        </span>
                      </div>
                      <div className="text-[11px] text-[#697586] mt-0.5">{demo.desc}</div>
                    </div>
                    <ArrowRight className="w-3.5 h-3.5 text-slate-400 group-hover:text-[#1261A0] transition-colors" />
                  </button>
                ))}
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
