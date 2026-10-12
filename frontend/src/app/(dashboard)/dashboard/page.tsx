"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useAuth } from "@/context/AuthContext";
import { apiRequest } from "@/lib/api";
import {
  AlertCircle,
  AlertTriangle,
  ArrowRight,
  Bell,
  Bot,
  Calendar,
  CheckCircle,
  Clock,
  Cpu,
  FileSpreadsheet,
  Flame,
  HelpCircle,
  Layers,
  MapPin,
  RefreshCw,
  Send,
  ShieldAlert,
  ShieldCheck,
  Sliders,
  Sparkles,
  TrendingUp,
  UserCheck,
  Users,
} from "lucide-react";

export default function DashboardPage() {
  const { user } = useAuth();
  const [summary, setSummary] = useState<any>(null);
  const [todayTimeline, setTodayTimeline] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchDashboardData = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await apiRequest("/portal/dashboard-summary");
      setSummary(res);

      // Fetch today's schedule for section / teacher
      const sec = user?.role === "CR" ? "sec_cs_3a" : "";
      const tl: any = await apiRequest(
        `/timetables/tt_dept_cs_master_v1/day/1${sec ? `?section_id=${sec}` : ""}`
      );
      setTodayTimeline(tl?.timeline || []);
    } catch (err: any) {
      setError(err?.detail || "Failed to load dashboard operational metrics.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (user) {
      fetchDashboardData();
    }
  }, [user]);

  if (!user) {
    return (
      <div className="p-8 text-center bg-white rounded-xl border border-[#E2E7EE]">
        <h3 className="text-base font-bold text-[#17324D]">Authentication Required</h3>
        <p className="text-xs text-[#697586] mt-1">Please sign in to access your role-specific dashboard.</p>
        <Link
          href="/login"
          className="mt-4 inline-block px-4 py-2 bg-[#1261A0] text-white text-xs font-semibold rounded-lg hover:bg-[#0E4E82]"
        >
          Sign In to Portal
        </Link>
      </div>
    );
  }

  const timetableStatus = summary?.timetable_status || {};
  const conflictSummary = summary?.conflict_summary || {};
  const reschedulerSummary = summary?.rescheduler_summary || {};
  const nextClass = summary?.next_class;

  return (
    <div className="space-y-6 pb-12">
      {/* 1. Welcome & Operational Status Hero Banner */}
      <div className="bg-white rounded-xl border border-[#E2E7EE] p-5 sm:p-6 shadow-xs flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2">
            <span className="text-xs font-bold uppercase tracking-wider text-[#1261A0] bg-[#EAF3FB] px-2.5 py-0.5 rounded">
              {user.role === "HOD" ? "HOD Operations Console" : `${user.role} Workspace`}
            </span>
            <span className="text-xs text-[#697586]">• Spring Term 2026</span>
          </div>
          <h1 className="text-xl sm:text-2xl font-bold text-[#17324D] mt-1">
            Welcome back, {user.full_name}
          </h1>
          <p className="text-xs sm:text-sm text-[#697586] mt-0.5">
            {user.role === "HOD" && "Manage department scheduling data, CP-SAT generation, conflict resolution, and schedule publication."}
            {user.role === "TEACHER" && "View your personal teaching schedule, submit availability preferences, and track schedule changes."}
            {user.role === "CR" && "View Section CS-3A timetable, verify period rooms, and report classroom or schedule clashes."}
            {user.role === "ADMIN" && "College-wide timetable overview, room utilization metrics, and cross-department conflict governance."}
          </p>
        </div>

        <div className="flex items-center space-x-2.5 flex-wrap">
          {user.role === "STUDENT" || user.role === "CR" ? (
            <>
              <Link
                href="/guide"
                className="px-3.5 py-2 rounded-lg bg-[#EAF3FB] text-[#1261A0] hover:bg-blue-100 text-xs font-semibold flex items-center transition-colors"
              >
                <HelpCircle className="w-3.5 h-3.5 mr-1.5" />
                Student Guide
              </Link>
              <Link
                href="/timetables"
                className="px-3.5 py-2 rounded-lg bg-[#1261A0] text-white hover:bg-[#0E4E82] text-xs font-semibold flex items-center shadow-xs transition-colors"
              >
                <Calendar className="w-3.5 h-3.5 mr-1.5" />
                View Class Timetable
              </Link>
            </>
          ) : user.role === "TEACHER" ? (
            <>
              <Link
                href="/guide"
                className="px-3.5 py-2 rounded-lg bg-[#EAF3FB] text-[#1261A0] hover:bg-blue-100 text-xs font-semibold flex items-center transition-colors"
              >
                <HelpCircle className="w-3.5 h-3.5 mr-1.5" />
                Faculty Guide
              </Link>
              <Link
                href="/assistant"
                className="px-3.5 py-2 rounded-lg border border-purple-200 bg-purple-50 hover:bg-purple-100 text-purple-700 text-xs font-semibold flex items-center transition-colors"
              >
                <Bot className="w-3.5 h-3.5 mr-1.5 text-purple-600" />
                AI Assistant
              </Link>
              <Link
                href="/timetables"
                className="px-3.5 py-2 rounded-lg bg-[#1261A0] text-white hover:bg-[#0E4E82] text-xs font-semibold flex items-center shadow-xs transition-colors"
              >
                <Calendar className="w-3.5 h-3.5 mr-1.5" />
                My Teaching Schedule
              </Link>
            </>
          ) : (
            <>
              <Link
                href="/guide"
                className="px-3.5 py-2 rounded-lg border border-[#E2E7EE] hover:bg-slate-50 text-slate-700 text-xs font-semibold flex items-center transition-colors"
              >
                <HelpCircle className="w-3.5 h-3.5 mr-1.5 text-[#1261A0]" />
                Staff Guide
              </Link>
              <Link
                href="/setup"
                className="px-3.5 py-2 rounded-lg border border-[#E2E7EE] hover:bg-slate-50 text-slate-700 text-xs font-semibold flex items-center transition-colors"
              >
                <Sliders className="w-3.5 h-3.5 mr-1.5 text-blue-600" />
                Semester Setup
              </Link>
              <Link
                href="/assistant"
                className="px-3.5 py-2 rounded-lg bg-[#EAF3FB] text-[#1261A0] hover:bg-blue-100 text-xs font-semibold flex items-center transition-colors"
              >
                <Bot className="w-3.5 h-3.5 mr-1.5" />
                AI Assistant
              </Link>
              <Link
                href="/timetables"
                className="px-3.5 py-2 rounded-lg bg-[#1261A0] text-white hover:bg-[#0E4E82] text-xs font-semibold flex items-center shadow-xs transition-colors"
              >
                <Calendar className="w-3.5 h-3.5 mr-1.5" />
                Timetable Planner
              </Link>
            </>
          )}
        </div>
      </div>

      {/* Role-Specific Core Primary Modules */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {user.role === "STUDENT" || user.role === "CR" ? (
          <>
            {/* Student Module 1: Class Timetable */}
            <Link
              href="/timetables"
              className="group bg-white rounded-xl border border-slate-200 hover:border-blue-500 hover:shadow-md p-5 transition-all flex flex-col justify-between"
            >
              <div>
                <div className="w-10 h-10 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center mb-3 group-hover:bg-blue-600 group-hover:text-white transition-colors">
                  <Calendar className="w-5 h-5" />
                </div>
                <h3 className="font-bold text-slate-900 text-sm group-hover:text-blue-700 transition-colors">
                  Class Timetable
                </h3>
                <p className="text-xs text-slate-500 mt-1 leading-relaxed">
                  View your section (CS-3A) weekly schedule, lecture halls, and faculty instructors.
                </p>
              </div>
              <div className="mt-4 flex items-center text-xs font-semibold text-blue-600 group-hover:translate-x-1 transition-transform">
                <span>View Full Week &rarr;</span>
              </div>
            </Link>

            {/* Student Module 2: Student Guide */}
            <Link
              href="/guide"
              className="group bg-white rounded-xl border border-slate-200 hover:border-indigo-500 hover:shadow-md p-5 transition-all flex flex-col justify-between"
            >
              <div>
                <div className="w-10 h-10 rounded-lg bg-indigo-50 text-indigo-600 flex items-center justify-center mb-3 group-hover:bg-indigo-600 group-hover:text-white transition-colors">
                  <HelpCircle className="w-5 h-5" />
                </div>
                <h3 className="font-bold text-slate-900 text-sm group-hover:text-indigo-700 transition-colors">
                  Student Guide
                </h3>
                <p className="text-xs text-slate-500 mt-1 leading-relaxed">
                  Learn how to read periods, room locations, download PDFs, and report classroom issues.
                </p>
              </div>
              <div className="mt-4 flex items-center text-xs font-semibold text-indigo-600 group-hover:translate-x-1 transition-transform">
                <span>Open Student Guide &rarr;</span>
              </div>
            </Link>

            {/* Student Module 3: Daily Timeline */}
            <Link
              href="/timetables"
              className="group bg-white rounded-xl border border-slate-200 hover:border-emerald-500 hover:shadow-md p-5 transition-all flex flex-col justify-between"
            >
              <div>
                <div className="w-10 h-10 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center mb-3 group-hover:bg-emerald-600 group-hover:text-white transition-colors">
                  <Clock className="w-5 h-5" />
                </div>
                <h3 className="font-bold text-slate-900 text-sm group-hover:text-emerald-700 transition-colors">
                  Daily Timeline
                </h3>
                <p className="text-xs text-slate-500 mt-1 leading-relaxed">
                  Period-by-period breakdown for today with exact lecture timings and break intervals.
                </p>
              </div>
              <div className="mt-4 flex items-center text-xs font-semibold text-emerald-600 group-hover:translate-x-1 transition-transform">
                <span>Check Daily Agenda &rarr;</span>
              </div>
            </Link>

            {/* Student Module 4: Profile & Enrollment */}
            <Link
              href="/profile"
              className="group bg-white rounded-xl border border-slate-200 hover:border-purple-500 hover:shadow-md p-5 transition-all flex flex-col justify-between"
            >
              <div>
                <div className="w-10 h-10 rounded-lg bg-purple-50 text-purple-600 flex items-center justify-center mb-3 group-hover:bg-purple-600 group-hover:text-white transition-colors">
                  <UserCheck className="w-5 h-5" />
                </div>
                <h3 className="font-bold text-slate-900 text-sm group-hover:text-purple-700 transition-colors">
                  Academic Identity
                </h3>
                <p className="text-xs text-slate-500 mt-1 leading-relaxed">
                  Verify enrolled section, semester, department, and authorized portal permissions.
                </p>
              </div>
              <div className="mt-4 flex items-center text-xs font-semibold text-purple-600 group-hover:translate-x-1 transition-transform">
                <span>View My Profile &rarr;</span>
              </div>
            </Link>
          </>
        ) : user.role === "TEACHER" ? (
          <>
            {/* Faculty Module 1: Teaching Schedule */}
            <Link
              href="/timetables"
              className="group bg-white rounded-xl border border-slate-200 hover:border-blue-500 hover:shadow-md p-5 transition-all flex flex-col justify-between"
            >
              <div>
                <div className="w-10 h-10 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center mb-3 group-hover:bg-blue-600 group-hover:text-white transition-colors">
                  <Calendar className="w-5 h-5" />
                </div>
                <h3 className="font-bold text-slate-900 text-sm group-hover:text-blue-700 transition-colors">
                  Teaching Schedule
                </h3>
                <p className="text-xs text-slate-500 mt-1 leading-relaxed">
                  View department weekly matrix. Toggle &quot;Highlight My Classes&quot; to isolate your lectures.
                </p>
              </div>
              <div className="mt-4 flex items-center text-xs font-semibold text-blue-600 group-hover:translate-x-1 transition-transform">
                <span>Open Timetable Planner &rarr;</span>
              </div>
            </Link>

            {/* Faculty Module 2: AI Assistant */}
            <Link
              href="/assistant"
              className="group bg-white rounded-xl border border-slate-200 hover:border-purple-500 hover:shadow-md p-5 transition-all flex flex-col justify-between"
            >
              <div>
                <div className="w-10 h-10 rounded-lg bg-purple-50 text-purple-600 flex items-center justify-center mb-3 group-hover:bg-purple-600 group-hover:text-white transition-colors">
                  <Bot className="w-5 h-5" />
                </div>
                <h3 className="font-bold text-slate-900 text-sm group-hover:text-purple-700 transition-colors">
                  AI Assistant
                </h3>
                <p className="text-xs text-slate-500 mt-1 leading-relaxed">
                  Ask natural language questions about classroom availability, workloads, or slot swaps.
                </p>
              </div>
              <div className="mt-4 flex items-center text-xs font-semibold text-purple-600 group-hover:translate-x-1 transition-transform">
                <span>Ask AI Assistant &rarr;</span>
              </div>
            </Link>

            {/* Faculty Module 3: Faculty Guide */}
            <Link
              href="/guide"
              className="group bg-white rounded-xl border border-slate-200 hover:border-indigo-500 hover:shadow-md p-5 transition-all flex flex-col justify-between"
            >
              <div>
                <div className="w-10 h-10 rounded-lg bg-indigo-50 text-indigo-600 flex items-center justify-center mb-3 group-hover:bg-indigo-600 group-hover:text-white transition-colors">
                  <HelpCircle className="w-5 h-5" />
                </div>
                <h3 className="font-bold text-slate-900 text-sm group-hover:text-indigo-700 transition-colors">
                  Faculty Guide
                </h3>
                <p className="text-xs text-slate-500 mt-1 leading-relaxed">
                  Procedures for submitting availability, change requests, printouts, and clash safeguards.
                </p>
              </div>
              <div className="mt-4 flex items-center text-xs font-semibold text-indigo-600 group-hover:translate-x-1 transition-transform">
                <span>Open Faculty Guide &rarr;</span>
              </div>
            </Link>

            {/* Faculty Module 4: Conflict Console */}
            <Link
              href="/conflicts"
              className="group bg-white rounded-xl border border-slate-200 hover:border-emerald-500 hover:shadow-md p-5 transition-all flex flex-col justify-between"
            >
              <div>
                <div className="w-10 h-10 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center mb-3 group-hover:bg-emerald-600 group-hover:text-white transition-colors">
                  <ShieldCheck className="w-5 h-5" />
                </div>
                <h3 className="font-bold text-slate-900 text-sm group-hover:text-emerald-700 transition-colors">
                  Conflict Detector
                </h3>
                <p className="text-xs text-slate-500 mt-1 leading-relaxed">
                  Live verification ensuring zero teacher double-booking and room allocation clashes.
                </p>
              </div>
              <div className="mt-4 flex items-center text-xs font-semibold text-emerald-600 group-hover:translate-x-1 transition-transform">
                <span>Check Conflicts &rarr;</span>
              </div>
            </Link>
          </>
        ) : (
          <>
            {/* Admin Module 1: Timetable Planner */}
            <Link
              href="/timetables"
              className="group bg-white rounded-xl border border-slate-200 hover:border-blue-500 hover:shadow-md p-5 transition-all flex flex-col justify-between"
            >
              <div>
                <div className="w-10 h-10 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center mb-3 group-hover:bg-blue-600 group-hover:text-white transition-colors">
                  <Calendar className="w-5 h-5" />
                </div>
                <h3 className="font-bold text-slate-900 text-sm group-hover:text-blue-700 transition-colors">
                  Timetable Planner
                </h3>
                <p className="text-xs text-slate-500 mt-1 leading-relaxed">
                  View, edit, move, lock sessions, and publish weekly schedules with live conflict detection.
                </p>
              </div>
              <div className="mt-4 flex items-center text-xs font-semibold text-blue-600 group-hover:translate-x-1 transition-transform">
                <span>Open Planner &rarr;</span>
              </div>
            </Link>

            {/* Admin Module 2: Semester Setup Wizard */}
            <Link
              href="/setup"
              className="group bg-white rounded-xl border border-slate-200 hover:border-indigo-500 hover:shadow-md p-5 transition-all flex flex-col justify-between"
            >
              <div>
                <div className="w-10 h-10 rounded-lg bg-indigo-50 text-indigo-600 flex items-center justify-center mb-3 group-hover:bg-indigo-600 group-hover:text-white transition-colors">
                  <Sliders className="w-5 h-5" />
                </div>
                <h3 className="font-bold text-slate-900 text-sm group-hover:text-indigo-700 transition-colors">
                  Semester Setup
                </h3>
                <p className="text-xs text-slate-500 mt-1 leading-relaxed">
                  5-step guided wizard for semester dates, teacher workload limits, rooms, and timing rules.
                </p>
              </div>
              <div className="mt-4 flex items-center text-xs font-semibold text-indigo-600 group-hover:translate-x-1 transition-transform">
                <span>Configure Semester &rarr;</span>
              </div>
            </Link>

            {/* Admin Module 3: Excel/CSV Data Import */}
            <Link
              href="/import"
              className="group bg-white rounded-xl border border-slate-200 hover:border-emerald-500 hover:shadow-md p-5 transition-all flex flex-col justify-between"
            >
              <div>
                <div className="w-10 h-10 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center mb-3 group-hover:bg-emerald-600 group-hover:text-white transition-colors">
                  <FileSpreadsheet className="w-5 h-5" />
                </div>
                <h3 className="font-bold text-slate-900 text-sm group-hover:text-emerald-700 transition-colors">
                  Import Data
                </h3>
                <p className="text-xs text-slate-500 mt-1 leading-relaxed">
                  Upload spreadsheets for faculty, courses, rooms, and weekly requirements with zero data loss.
                </p>
              </div>
              <div className="mt-4 flex items-center text-xs font-semibold text-emerald-600 group-hover:translate-x-1 transition-transform">
                <span>Import Excel &rarr;</span>
              </div>
            </Link>

            {/* Admin Module 4: AI Timetable Assistant */}
            <Link
              href="/assistant"
              className="group bg-white rounded-xl border border-slate-200 hover:border-purple-500 hover:shadow-md p-5 transition-all flex flex-col justify-between"
            >
              <div>
                <div className="w-10 h-10 rounded-lg bg-purple-50 text-purple-600 flex items-center justify-center mb-3 group-hover:bg-purple-600 group-hover:text-white transition-colors">
                  <Bot className="w-5 h-5" />
                </div>
                <h3 className="font-bold text-slate-900 text-sm group-hover:text-purple-700 transition-colors">
                  AI Assistant
                </h3>
                <p className="text-xs text-slate-500 mt-1 leading-relaxed">
                  Natural language assistant: ask questions, resolve clashes, mark leave, and suggest alternatives.
                </p>
              </div>
              <div className="mt-4 flex items-center text-xs font-semibold text-purple-600 group-hover:translate-x-1 transition-transform">
                <span>Chat with Assistant &rarr;</span>
              </div>
            </Link>
          </>
        )}
      </div>

      {/* Role-Adapted Guided Roadmap Banner (What should I do next?) */}
      <div className="bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-200 rounded-xl p-5 shadow-xs">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center space-x-2 text-blue-700 text-xs font-bold uppercase tracking-wider">
              <HelpCircle className="w-4 h-4" />
              <span>
                {user.role === "STUDENT" || user.role === "CR"
                  ? "Student Quick Navigation Roadmap"
                  : user.role === "TEACHER"
                  ? "Faculty Teaching Preparation Guide"
                  : "First-Time Semester Preparation Guide"}
              </span>
            </div>
            <h3 className="text-base font-bold text-slate-900 mt-1">
              {user.role === "STUDENT" || user.role === "CR"
                ? "First time on TIMEVERSE? Here is how to navigate your classes:"
                : user.role === "TEACHER"
                ? "Here is what to review for your upcoming academic schedule:"
                : "New to TIMEVERSE? Here is what you should do next:"}
            </h3>
            <div className="grid grid-cols-1 sm:grid-cols-4 gap-3 mt-3 text-xs">
              {user.role === "STUDENT" || user.role === "CR" ? (
                <>
                  <div className="p-2.5 bg-white/80 rounded-lg border border-blue-100">
                    <span className="font-bold text-blue-800 block">1. View Timetable</span>
                    <span className="text-slate-600 text-[11px]">Check Section CS-3A weekly grid</span>
                  </div>
                  <div className="p-2.5 bg-white/80 rounded-lg border border-blue-100">
                    <span className="font-bold text-blue-800 block">2. Verify Rooms</span>
                    <span className="text-slate-600 text-[11px]">Locate lecture hall & lab codes</span>
                  </div>
                  <div className="p-2.5 bg-white/80 rounded-lg border border-blue-100">
                    <span className="font-bold text-blue-800 block">3. Print / Save PDF</span>
                    <span className="text-slate-600 text-[11px]">Save schedule for offline access</span>
                  </div>
                  <div className="p-2.5 bg-white/80 rounded-lg border border-blue-100">
                    <span className="font-bold text-blue-800 block">4. Student Guide</span>
                    <span className="text-slate-600 text-[11px]">Find answers to common FAQs</span>
                  </div>
                </>
              ) : user.role === "TEACHER" ? (
                <>
                  <div className="p-2.5 bg-white/80 rounded-lg border border-blue-100">
                    <span className="font-bold text-blue-800 block">1. Highlight Classes</span>
                    <span className="text-slate-600 text-[11px]">Isolate your personal lectures</span>
                  </div>
                  <div className="p-2.5 bg-white/80 rounded-lg border border-blue-100">
                    <span className="font-bold text-blue-800 block">2. Check Rooms</span>
                    <span className="text-slate-600 text-[11px]">Verify LH-101 and lab allocations</span>
                  </div>
                  <div className="p-2.5 bg-white/80 rounded-lg border border-blue-100">
                    <span className="font-bold text-blue-800 block">3. Change Requests</span>
                    <span className="text-slate-600 text-[11px]">Submit swaps with zero new clash</span>
                  </div>
                  <div className="p-2.5 bg-white/80 rounded-lg border border-blue-100">
                    <span className="font-bold text-blue-800 block">4. Faculty Guide</span>
                    <span className="text-slate-600 text-[11px]">Review rules & print timetable</span>
                  </div>
                </>
              ) : (
                <>
                  <div className="p-2.5 bg-white/80 rounded-lg border border-blue-100">
                    <span className="font-bold text-blue-800 block">1. Semester Setup</span>
                    <span className="text-slate-600 text-[11px]">Define academic year & working days</span>
                  </div>
                  <div className="p-2.5 bg-white/80 rounded-lg border border-blue-100">
                    <span className="font-bold text-blue-800 block">2. Import Data</span>
                    <span className="text-slate-600 text-[11px]">Upload faculty & course spreadsheets</span>
                  </div>
                  <div className="p-2.5 bg-white/80 rounded-lg border border-blue-100">
                    <span className="font-bold text-blue-800 block">3. Generate Timetable</span>
                    <span className="text-slate-600 text-[11px]">Run solver with 0 clash guarantee</span>
                  </div>
                  <div className="p-2.5 bg-white/80 rounded-lg border border-blue-100">
                    <span className="font-bold text-blue-800 block">4. Review & Publish</span>
                    <span className="text-slate-600 text-[11px]">Lock fixed slots and release to college</span>
                  </div>
                </>
              )}
            </div>
          </div>
          {user.role === "STUDENT" || user.role === "CR" ? (
            <Link
              href="/guide"
              className="self-start md:self-center px-4 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-bold transition-colors shadow-xs whitespace-nowrap"
            >
              Open Student Guide &rarr;
            </Link>
          ) : user.role === "TEACHER" ? (
            <Link
              href="/guide"
              className="self-start md:self-center px-4 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-bold transition-colors shadow-xs whitespace-nowrap"
            >
              Open Faculty Guide &rarr;
            </Link>
          ) : (
            <Link
              href="/setup"
              className="self-start md:self-center px-4 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-bold transition-colors shadow-xs whitespace-nowrap"
            >
              Start Guided Setup &rarr;
            </Link>
          )}
        </div>
      </div>

      {/* DUAL CONNECTED WORKFLOW HUBS (Timetable Planner & Alert System Workflows) */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* WORKFLOW AREA 1: Timetable Planner Workflow (Stages 1 - 7) */}
        <div className="bg-white rounded-xl border border-[#E2E7EE] p-5 shadow-xs flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between pb-3 border-b border-[#E2E7EE]">
              <div className="flex items-center space-x-2">
                <div className="w-8 h-8 rounded-lg bg-blue-50 text-[#1261A0] flex items-center justify-center font-bold">
                  <Calendar className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="font-bold text-sm text-[#17324D]">Timetable Planner Workflow</h3>
                  <span className="text-[11px] text-[#697586]">7-Stage Deterministic Generation Pipeline</span>
                </div>
              </div>
              <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-blue-100 text-blue-900 border border-blue-200">
                Workflow 1
              </span>
            </div>

            <div className="mt-4 space-y-2 text-xs">
              {[
                { stage: 1, title: "Input College Data", desc: "Teachers, subjects, cohorts, rooms, slots, requirements", href: "/import" },
                { stage: 2, title: "Set Constraints", desc: "Workload limits, lab types, availability, breaks", href: "/setup" },
                { stage: 3, title: "Generate Timetable", desc: "Google OR-Tools CP-SAT integer optimization", href: "/timetables" },
                { stage: 4, title: "Validate Conflicts", desc: "Hard clash verification (0 double-bookings guarantee)", href: "/conflicts" },
                { stage: 5, title: "Publish Timetable", desc: "HOD approval, lock sessions, release to college", href: "/timetables" },
                { stage: 6, title: "Monitor & Adjust", desc: "Track leaves, room maintenance, emergency reschedule", href: "/rescheduler" },
                { stage: 7, title: "Impact Simulator", desc: "Cascade simulation, trade-off evaluation & apply changes", href: "/simulator" },
              ].map((s) => (
                <div key={s.stage} className="p-2 rounded-lg bg-[#F7F9FC] border border-[#E2E7EE] flex items-center justify-between hover:bg-blue-50/50 transition">
                  <div className="flex items-center space-x-2.5">
                    <span className="w-5 h-5 rounded-full bg-white border text-[10px] font-extrabold text-[#1261A0] flex items-center justify-center shrink-0">
                      {s.stage}
                    </span>
                    <div>
                      <span className="font-bold text-slate-800 text-[11px]">{s.title}</span>
                      <p className="text-[10px] text-slate-500 leading-tight">{s.desc}</p>
                    </div>
                  </div>
                  <Link href={s.href}>
                    <button className="text-[10px] font-semibold text-[#1261A0] hover:underline flex items-center shrink-0">
                      Go &rarr;
                    </button>
                  </Link>
                </div>
              ))}
            </div>
          </div>

          <div className="mt-4 pt-3 border-t border-[#E2E7EE] flex items-center justify-between text-xs">
            <span className="text-[11px] text-slate-500">
              Active Status: <b className="text-emerald-700">Stage 5 Published</b>
            </span>
            <Link href="/timetables">
              <button className="px-3 py-1 bg-[#1261A0] text-white hover:bg-[#0E4E82] text-xs font-semibold rounded-lg shadow-2xs">
                Open Timetable Matrix &rarr;
              </button>
            </Link>
          </div>
        </div>

        {/* WORKFLOW AREA 2: Alert System Workflow (5-Stage Event Engine) */}
        <div className="bg-white rounded-xl border border-[#E2E7EE] p-5 shadow-xs flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between pb-3 border-b border-[#E2E7EE]">
              <div className="flex items-center space-x-2">
                <div className="w-8 h-8 rounded-lg bg-amber-50 text-amber-700 flex items-center justify-center font-bold">
                  <Bell className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="font-bold text-sm text-[#17324D]">Alert Engine & Notification Hub</h3>
                  <span className="text-[11px] text-[#697586]">Event-Driven Notification & Resolution Loop</span>
                </div>
              </div>
              <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-amber-100 text-amber-900 border border-amber-200">
                Workflow 2
              </span>
            </div>

            <div className="mt-4 space-y-2 text-xs">
              {[
                { stage: 1, title: "Event Occurs", desc: "Clash detected, faculty leave, room locked, or timetable published", icon: Clock },
                { stage: 2, title: "Alert Engine", desc: "Deduplication, 4-tier categorisation (A/B/C/D), severity scoring", icon: Cpu },
                { stage: 3, title: "Identifies Recipients", desc: "Targets HOD, affected teachers, students & section CRs", icon: Users },
                { stage: 4, title: "Sends Notification", desc: "Verified delivery across in-app, email SMTP, and push channels", icon: Send },
                { stage: 5, title: "Tracks Resolution", desc: "Pending ➔ Under Review ➔ Resolved with full audit notes", icon: CheckCircle },
              ].map((s) => (
                <div key={s.stage} className="p-2 rounded-lg bg-[#F7F9FC] border border-[#E2E7EE] flex items-center justify-between hover:bg-amber-50/40 transition">
                  <div className="flex items-center space-x-2.5">
                    <span className="w-5 h-5 rounded-full bg-white border text-[10px] font-extrabold text-amber-700 flex items-center justify-center shrink-0">
                      {s.stage}
                    </span>
                    <div>
                      <span className="font-bold text-slate-800 text-[11px]">{s.title}</span>
                      <p className="text-[10px] text-slate-500 leading-tight">{s.desc}</p>
                    </div>
                  </div>
                  <s.icon className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                </div>
              ))}
            </div>

            {/* 4 Alert Categories Pill Summary */}
            <div className="grid grid-cols-2 gap-2 mt-3 pt-3 border-t border-slate-100 text-[11px]">
              <div className="p-2 rounded bg-amber-50/70 border border-amber-200 text-amber-900">
                <span className="font-bold block">A: Conflict Alerts</span>
                <span className="text-[10px] text-amber-800">Hard clashes & overlap warnings</span>
              </div>
              <div className="p-2 rounded bg-blue-50/70 border border-blue-200 text-blue-900">
                <span className="font-bold block">B: Timetable Changes</span>
                <span className="text-[10px] text-blue-800">Ripple notices to students & faculty</span>
              </div>
              <div className="p-2 rounded bg-rose-50/70 border border-rose-200 text-rose-900">
                <span className="font-bold block">C: Emergency Alerts</span>
                <span className="text-[10px] text-rose-800">Faculty absence & room lockdown</span>
              </div>
              <div className="p-2 rounded bg-purple-50/70 border border-purple-200 text-purple-900">
                <span className="font-bold block">D: Administrative</span>
                <span className="text-[10px] text-purple-800">Workload & resource shortage</span>
              </div>
            </div>
          </div>

          <div className="mt-4 pt-3 border-t border-[#E2E7EE] flex items-center justify-between text-xs">
            <span className="text-[11px] text-slate-500">
              Audit Status: <b className="text-emerald-700">Deduplicated & Active</b>
            </span>
            <Link href="/alerts">
              <button className="px-3 py-1 bg-amber-600 hover:bg-amber-700 text-white text-xs font-semibold rounded-lg shadow-2xs">
                View Alert Feed &rarr;
              </button>
            </Link>
          </div>
        </div>
      </div>

      {/* Loading & Error States */}
      {loading && (
        <div className="p-8 text-center bg-white rounded-xl border border-[#E2E7EE]">
          <RefreshCw className="w-6 h-6 text-[#1261A0] animate-spin mx-auto mb-2" />
          <span className="text-xs text-[#697586] font-medium">Loading live scheduling metrics & conflict ledger...</span>
        </div>
      )}

      {error && (
        <div className="p-4 bg-rose-50 border border-rose-200 rounded-xl text-xs text-[#B42332] flex items-center justify-between">
          <div className="flex items-center">
            <AlertCircle className="w-4 h-4 mr-2 flex-shrink-0" />
            <span>{error}</span>
          </div>
          <button onClick={fetchDashboardData} className="font-semibold underline ml-4">
            Retry
          </button>
        </div>
      )}

      {!loading && summary && (
        <>
          {/* 2. Top Metric Cards — Prioritizing the 3 Core Modules */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {/* Timetable Planner Status */}
            <div className="bg-white rounded-xl border border-[#E2E7EE] p-4 shadow-xs">
              <div className="flex items-center justify-between text-[#697586] text-xs font-medium">
                <span>Timetable Status</span>
                <Calendar className="w-4 h-4 text-[#1261A0]" />
              </div>
              <div className="text-2xl font-bold text-[#17324D] mt-2">
                {timetableStatus.status || "PUBLISHED"}
              </div>
              <div className="flex items-center justify-between text-[11px] text-[#1261A0] mt-1 font-semibold">
                <span>v{timetableStatus.version || "1.0"} Active Master</span>
                <span className="text-slate-500 font-normal">{timetableStatus.total_sessions || 24} Sessions</span>
              </div>
            </div>

            {/* Conflict Detector Status */}
            <div className="bg-white rounded-xl border border-[#E2E7EE] p-4 shadow-xs">
              <div className="flex items-center justify-between text-[#697586] text-xs font-medium">
                <span>Conflict Detector</span>
                <ShieldCheck className="w-4 h-4 text-[#16805D]" />
              </div>
              <div className={`text-2xl font-bold mt-2 ${
                conflictSummary.critical_conflicts_count === 0 ? "text-[#16805D]" : "text-[#B42332]"
              }`}>
                {conflictSummary.critical_conflicts_count === 0 ? "0 Clashes" : `${conflictSummary.critical_conflicts_count} Hard Clashes`}
              </div>
              <div className="flex items-center justify-between text-[11px] mt-1">
                <span className={`font-semibold ${
                  conflictSummary.is_conflict_free ? "text-[#16805D]" : "text-[#B42332]"
                }`}>
                  {conflictSummary.is_conflict_free ? "● Constraint Verified" : "● Action Required"}
                </span>
                <Link href="/conflicts" className="text-[#1261A0] hover:underline font-semibold">
                  Inspect &rarr;
                </Link>
              </div>
            </div>

            {/* Smart Rescheduler Status */}
            <div className="bg-white rounded-xl border border-[#E2E7EE] p-4 shadow-xs">
              <div className="flex items-center justify-between text-[#697586] text-xs font-medium">
                <span>Smart Rescheduler</span>
                <RefreshCw className="w-4 h-4 text-[#1261A0]" />
              </div>
              <div className="text-2xl font-bold text-[#17324D] mt-2">
                {reschedulerSummary.preservation_target || ">90% Stable"}
              </div>
              <div className="flex items-center justify-between text-[11px] text-[#697586] mt-1">
                <span>{reschedulerSummary.pending_change_requests_count || 0} Proposals Pending</span>
                <Link href="/rescheduler" className="text-[#1261A0] hover:underline font-semibold">
                  Simulate &rarr;
                </Link>
              </div>
            </div>

            {/* Institutional Resource Capacity */}
            <div className="bg-white rounded-xl border border-[#E2E7EE] p-4 shadow-xs">
              <div className="flex items-center justify-between text-[#697586] text-xs font-medium">
                <span>Room Capacity</span>
                <MapPin className="w-4 h-4 text-[#1261A0]" />
              </div>
              <div className="text-2xl font-bold text-[#17324D] mt-2">
                87.5% Utilized
              </div>
              <div className="text-[11px] text-[#16805D] mt-1 font-semibold">
                ● 4 Rooms Active (LH-101, 102, LAB-1, 2)
              </div>
            </div>
          </div>

          {/* 3. Primary Feature Grids: Master Timetable, Conflicts & Rescheduler */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Left 2 Columns: Next Class Hero & Today's Schedule Timeline */}
            <div className="lg:col-span-2 space-y-6">
              {/* Upcoming Class Hero Card */}
              {nextClass ? (
                <div className="bg-white rounded-xl border border-[#E2E7EE] p-5 shadow-xs">
                  <div className="flex items-center justify-between pb-3 border-b border-slate-100">
                    <span className="text-xs font-bold uppercase tracking-wider text-[#1261A0] bg-[#EAF3FB] px-2.5 py-0.5 rounded">
                      Upcoming Class Schedule
                    </span>
                    <span className="text-xs text-[#697586] font-medium">
                      {nextClass.day_name} • Period {nextClass.period_number} ({nextClass.start_time} - {nextClass.end_time})
                    </span>
                  </div>

                  <div className="mt-4 flex flex-wrap items-center justify-between gap-4">
                    <div>
                      <h3 className="text-lg font-bold text-[#17324D]">
                        {nextClass.subject_code} — {nextClass.subject_name}
                      </h3>
                      <div className="flex flex-wrap items-center gap-3 text-xs text-[#697586] mt-1.5">
                        <span className="flex items-center text-slate-700 font-semibold">
                          <UserCheck className="w-3.5 h-3.5 mr-1 text-[#1261A0]" />
                          {nextClass.teacher_name}
                        </span>
                        <span>•</span>
                        <span className="flex items-center text-slate-700">
                          <MapPin className="w-3.5 h-3.5 mr-1 text-[#1261A0]" />
                          {nextClass.room_name}
                        </span>
                        <span>•</span>
                        <span className="flex items-center text-slate-700">
                          <Users className="w-3.5 h-3.5 mr-1 text-[#1261A0]" />
                          {nextClass.cohort_section_name}
                        </span>
                      </div>
                    </div>

                    <div className="flex items-center space-x-2">
                      <Link
                        href="/timetables"
                        className="px-3 py-1.5 rounded-lg bg-[#1261A0] text-white hover:bg-[#0E4E82] text-xs font-semibold"
                      >
                        Open Planner
                      </Link>
                      <Link
                        href="/rescheduler"
                        className="px-3 py-1.5 rounded-lg border border-[#E2E7EE] hover:bg-slate-50 text-slate-700 text-xs font-semibold"
                      >
                        Reschedule
                      </Link>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="bg-white rounded-xl border border-[#E2E7EE] p-5 shadow-xs flex items-center justify-between">
                  <div>
                    <h3 className="font-bold text-sm text-[#17324D]">No active classes scheduled right now</h3>
                    <p className="text-xs text-[#697586] mt-0.5">All regular class hours for today have concluded.</p>
                  </div>
                  <Link
                    href="/timetables"
                    className="px-3 py-1.5 rounded-lg bg-[#1261A0] text-white text-xs font-semibold hover:bg-[#0E4E82]"
                  >
                    View Full Week
                  </Link>
                </div>
              )}

              {/* Today's Schedule Overview Cards */}
              <div className="bg-white rounded-xl border border-[#E2E7EE] p-5 shadow-xs space-y-4">
                <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                  <div className="flex items-center space-x-2">
                    <Calendar className="w-4 h-4 text-[#1261A0]" />
                    <h3 className="font-bold text-sm text-[#17324D]">Today&apos;s Class Schedule (Monday)</h3>
                  </div>
                  <Link href="/timetables" className="text-xs text-[#1261A0] font-semibold hover:underline">
                    View Weekly Grid &rarr;
                  </Link>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
                  {todayTimeline
                    .filter((t) => !t.is_break && t.session)
                    .slice(0, 4)
                    .map((slot) => (
                      <div
                        key={slot.period_number}
                        className="p-3 rounded-lg border border-[#E2E7EE] bg-[#F7F9FC] hover:border-[#1261A0] transition-colors"
                      >
                        <div className="flex items-center justify-between text-[10px] text-[#697586] font-semibold">
                          <span>Period {slot.period_number}</span>
                          <span>{slot.start_time || "08:30"}</span>
                        </div>
                        <div className="font-bold text-xs text-[#1261A0] mt-1 truncate">
                          {slot.session?.subject_code}
                        </div>
                        <div className="text-[11px] font-medium text-slate-800 truncate">
                          {slot.session?.subject_name}
                        </div>
                        <div className="text-[10px] text-[#697586] mt-1 flex items-center justify-between">
                          <span className="truncate">{slot.session?.room_name}</span>
                          <span className="font-medium text-slate-700">{slot.session?.teacher_name?.split(" ")[1] || "Faculty"}</span>
                        </div>
                      </div>
                    ))}
                </div>
              </div>

              {/* Conflict Detector Status & Diagnostics Panel */}
              <div className="bg-white rounded-xl border border-[#E2E7EE] p-5 shadow-xs space-y-3">
                <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                  <div>
                    <h3 className="font-bold text-sm text-[#17324D]">Conflict Detector Real-Time Monitor</h3>
                    <p className="text-xs text-[#697586]">
                      Validates teacher double-bookings, room clashes, section overlaps, and room capacity.
                    </p>
                  </div>
                  <Link
                    href="/conflicts"
                    className="px-3 py-1.5 rounded-lg bg-[#EAF3FB] text-[#1261A0] text-xs font-semibold hover:bg-blue-100 transition-colors"
                  >
                    Open Conflict Console &rarr;
                  </Link>
                </div>

                {conflictSummary.critical_conflicts_count === 0 ? (
                  <div className="p-4 rounded-lg bg-emerald-50/70 border border-emerald-200 flex items-center justify-between">
                    <div className="flex items-center space-x-3">
                      <CheckCircle className="w-5 h-5 text-[#16805D] flex-shrink-0" />
                      <div>
                        <div className="text-xs font-bold text-emerald-900">
                          100% Conflict-Free Master Schedule
                        </div>
                        <div className="text-[11px] text-emerald-700">
                          Zero faculty double-bookings, zero classroom clashes, zero cohort overlaps.
                        </div>
                      </div>
                    </div>
                    <Link
                      href="/conflicts"
                      className="text-xs font-semibold text-[#16805D] hover:underline whitespace-nowrap ml-4"
                    >
                      Run Full Audit &rarr;
                    </Link>
                  </div>
                ) : (
                  <div className="p-4 rounded-lg bg-rose-50 border border-rose-200 flex items-center justify-between">
                    <div className="flex items-center space-x-3">
                      <AlertTriangle className="w-5 h-5 text-[#B42332] flex-shrink-0" />
                      <div>
                        <div className="text-xs font-bold text-[#B42332]">
                          {conflictSummary.critical_conflicts_count} Hard Constraint Violation(s) Detected!
                        </div>
                        <div className="text-[11px] text-rose-700">
                          Timetable cannot be published until all hard clashes are resolved.
                        </div>
                      </div>
                    </div>
                    <Link
                      href="/conflicts"
                      className="px-3 py-1 rounded bg-[#B42332] text-white text-xs font-semibold hover:bg-rose-800"
                    >
                      Resolve Clashes Now
                    </Link>
                  </div>
                )}
              </div>
            </div>

            {/* Right 1 Column: Smart Rescheduler & Workflow Launcher */}
            <div className="space-y-6">
              {/* Smart Rescheduler Quick Launch Card */}
              <div className="bg-white rounded-xl border border-[#E2E7EE] p-5 shadow-xs space-y-4">
                <div className="border-b border-slate-100 pb-3">
                  <span className="text-xs font-bold uppercase tracking-wider text-[#1261A0] bg-[#EAF3FB] px-2 py-0.5 rounded">
                    Disruption Engine
                  </span>
                  <h3 className="font-bold text-sm text-[#17324D] mt-1.5">Smart Rescheduler</h3>
                  <p className="text-xs text-[#697586] mt-0.5">
                    Automatically isolate affected classes, preserve unaffected sessions, and suggest clash-free alternatives.
                  </p>
                </div>

                <div className="space-y-2.5 text-xs">
                  <div className="p-3 rounded-lg border border-[#E2E7EE] bg-[#F7F9FC]">
                    <div className="font-semibold text-slate-800 flex items-center">
                      <UserCheck className="w-4 h-4 mr-1.5 text-[#1261A0]" />
                      Faculty Absence Handling
                    </div>
                    <div className="text-[11px] text-[#697586] mt-0.5">
                      Suggest substitute faculty or reschedule to open slots without cascade violations.
                    </div>
                  </div>

                  <div className="p-3 rounded-lg border border-[#E2E7EE] bg-[#F7F9FC]">
                    <div className="font-semibold text-slate-800 flex items-center">
                      <MapPin className="w-4 h-4 mr-1.5 text-[#1261A0]" />
                      Room Maintenance / Outage
                    </div>
                    <div className="text-[11px] text-[#697586] mt-0.5">
                      Reallocate to equivalent capacity classrooms (LH-101 / LH-102) seamlessly.
                    </div>
                  </div>

                  <div className="p-3 rounded-lg border border-[#E2E7EE] bg-[#F7F9FC]">
                    <div className="font-semibold text-slate-800 flex items-center">
                      <RefreshCw className="w-4 h-4 mr-1.5 text-[#1261A0]" />
                      Class Session Swaps
                    </div>
                    <div className="text-[11px] text-[#697586] mt-0.5">
                      Verify mutual feasibility between 2 periods and apply with automated revalidation.
                    </div>
                  </div>
                </div>

                <Link
                  href="/rescheduler"
                  className="w-full py-2 px-3 rounded-lg bg-[#1261A0] text-white hover:bg-[#0E4E82] text-xs font-semibold flex items-center justify-center transition-colors shadow-xs"
                >
                  <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
                  Launch Smart Rescheduler &rarr;
                </Link>
              </div>

              {/* Quick Actions Panel */}
              <div className="bg-white rounded-xl border border-[#E2E7EE] p-5 shadow-xs space-y-3">
                <h3 className="font-bold text-sm text-[#17324D] border-b border-slate-100 pb-2">
                  Role Quick Actions
                </h3>

                <div className="space-y-2">
                  <Link
                    href="/timetables"
                    className="flex items-center justify-between p-2.5 rounded-lg border border-[#E2E7EE] hover:bg-[#EAF3FB] hover:border-[#1261A0] text-xs font-semibold text-slate-700 transition-colors"
                  >
                    <div className="flex items-center space-x-2">
                      <Calendar className="w-4 h-4 text-[#1261A0]" />
                      <span>{user.role === "TEACHER" ? "View My Teaching Grid" : "Open Timetable Grid"}</span>
                    </div>
                    <ArrowRight className="w-3.5 h-3.5 text-slate-400" />
                  </Link>

                  <Link
                    href="/conflicts"
                    className="flex items-center justify-between p-2.5 rounded-lg border border-[#E2E7EE] hover:bg-[#EAF3FB] hover:border-[#1261A0] text-xs font-semibold text-slate-700 transition-colors"
                  >
                    <div className="flex items-center space-x-2">
                      <ShieldAlert className="w-4 h-4 text-[#B42332]" />
                      <span>Check Hard Constraints</span>
                    </div>
                    <ArrowRight className="w-3.5 h-3.5 text-slate-400" />
                  </Link>

                  {(user.role === "HOD" || user.role === "ADMIN") && (
                    <Link
                      href="/import"
                      className="flex items-center justify-between p-2.5 rounded-lg border border-[#E2E7EE] hover:bg-[#EAF3FB] hover:border-[#1261A0] text-xs font-semibold text-slate-700 transition-colors"
                    >
                      <div className="flex items-center space-x-2">
                        <Layers className="w-4 h-4 text-[#1261A0]" />
                        <span>Preflight CSV Data Import</span>
                      </div>
                      <ArrowRight className="w-3.5 h-3.5 text-slate-400" />
                    </Link>
                  )}
                </div>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
