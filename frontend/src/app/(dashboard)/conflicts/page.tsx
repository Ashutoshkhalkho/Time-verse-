"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useAuth } from "@/context/AuthContext";
import { apiRequest } from "@/lib/api";
import {
  AlertCircle,
  AlertTriangle,
  ArrowRight,
  CheckCircle,
  CheckCircle2,
  Clock,
  Filter,
  Layers,
  MapPin,
  RefreshCw,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  UserCheck,
  Users,
  Zap,
} from "lucide-react";

interface ConflictItem {
  id: string;
  type: string;
  severity: "CRITICAL" | "WARNING";
  title: string;
  description: string;
  day_number: number;
  day_name: string;
  period_number: number;
  time_slot_id: string;
  affected_classes: Array<{
    session_id: string;
    subject_code: string;
    subject_name: string;
    teacher_id: string;
    teacher_name: string;
    room_id: string;
    room_name: string;
    cohort_section_id: string;
    cohort_name: string;
    slot_description: string;
  }>;
  affected_resource_type: string;
  affected_resource_name: string;
  feasible_resolutions: string[];
}

interface ConflictReport {
  timetable_id: string;
  version_str: string;
  status: string;
  total_sessions: number;
  is_conflict_free: boolean;
  critical_conflicts_count: number;
  warnings_count: number;
  conflicts: ConflictItem[];
  checked_constraints: string[];
}

export default function ConflictDetectorPage() {
  const { user } = useAuth();
  const [report, setReport] = useState<ConflictReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedFilter, setSelectedFilter] = useState<string>("ALL");
  const [actionLoading, setActionLoading] = useState(false);
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  const fetchConflicts = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await apiRequest<ConflictReport>("/conflicts");
      setReport(data);
    } catch (err: any) {
      setError(err?.message || "Failed to load conflict analysis.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchConflicts();
  }, []);

  const handleInjectClash = async () => {
    try {
      setActionLoading(true);
      setActionMessage(null);
      await apiRequest("/conflicts/inject-demo-clash", { method: "POST" });
      setActionMessage("Deliberate faculty clash injected for evaluation!");
      await fetchConflicts();
    } catch (err: any) {
      setError(err?.message || "Failed to inject demo clash.");
    } finally {
      setActionLoading(false);
    }
  };

  const handleRestoreClean = async () => {
    try {
      setActionLoading(true);
      setActionMessage(null);
      await apiRequest("/conflicts/restore-conflict-free", { method: "POST" });
      setActionMessage("Timetable restored to 100% verified clash-free state.");
      await fetchConflicts();
    } catch (err: any) {
      setError(err?.message || "Failed to restore conflict-free state.");
    } finally {
      setActionLoading(false);
    }
  };

  const filteredConflicts = report?.conflicts.filter((c) => {
    if (selectedFilter === "ALL") return true;
    if (selectedFilter === "TEACHER") return c.type === "TEACHER_DOUBLE_BOOKING";
    if (selectedFilter === "ROOM") return c.type === "ROOM_DOUBLE_BOOKING" || c.type === "ROOM_CAPACITY_VIOLATION";
    if (selectedFilter === "COHORT") return c.type === "COHORT_DOUBLE_BOOKING";
    return true;
  }) || [];

  return (
    <div className="space-y-6">
      {/* Top Banner & Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-4 border-b border-[#E2E7EE]">
        <div>
          <div className="flex items-center space-x-2">
            <span className="text-[11px] font-bold uppercase tracking-wider text-[#1261A0] bg-[#EAF3FB] px-2.5 py-0.5 rounded">
              Core Module 3
            </span>
            <span className="text-xs text-[#697586]">Independent Verification Engine</span>
          </div>
          <h1 className="text-xl sm:text-2xl font-bold text-[#17324D] mt-1">Conflict Detector</h1>
          <p className="text-xs sm:text-sm text-[#697586] mt-0.5">
            Real-time constraint satisfaction verification across faculty, facilities, student cohorts, and laboratory types.
          </p>
        </div>

        {/* Live Demo Sandbox Buttons */}
        <div className="flex items-center space-x-2">
          <button
            onClick={handleInjectClash}
            disabled={actionLoading}
            className="px-3 py-1.5 rounded-lg border border-rose-300 bg-rose-50 hover:bg-rose-100 text-rose-700 text-xs font-semibold flex items-center space-x-1.5 transition-colors disabled:opacity-50"
            title="Inject deliberate faculty overlap to observe instant detection"
          >
            <AlertTriangle className="w-3.5 h-3.5" />
            <span>{actionLoading ? "Processing..." : "+ Inject Test Clash (Demo)"}</span>
          </button>

          <button
            onClick={handleRestoreClean}
            disabled={actionLoading}
            className="px-3 py-1.5 rounded-lg border border-emerald-300 bg-emerald-50 hover:bg-emerald-100 text-emerald-800 text-xs font-semibold flex items-center space-x-1.5 transition-colors disabled:opacity-50"
            title="Restore timetable to verified clash-free state"
          >
            <CheckCircle2 className="w-3.5 h-3.5" />
            <span>Restore Conflict-Free</span>
          </button>

          <button
            onClick={fetchConflicts}
            className="p-2 rounded-lg border border-[#E2E7EE] bg-white hover:bg-slate-50 text-slate-600 text-xs"
            title="Refresh conflict status"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {actionMessage && (
        <div className="p-3 rounded-lg bg-blue-50 border border-blue-200 text-xs text-blue-800 font-medium flex items-center justify-between">
          <span>{actionMessage}</span>
          <button onClick={() => setActionMessage(null)} className="text-blue-500 hover:text-blue-700">&times;</button>
        </div>
      )}

      {error && (
        <div className="p-4 rounded-lg bg-rose-50 border border-rose-200 text-xs text-rose-700 font-medium">
          {error}
        </div>
      )}

      {loading ? (
        <div className="bg-white rounded-xl border border-[#E2E7EE] p-12 text-center text-slate-400">
          <RefreshCw className="w-8 h-8 mx-auto animate-spin mb-2 text-[#1261A0]" />
          <p className="text-sm font-semibold">Running multi-constraint conflict analysis...</p>
        </div>
      ) : report ? (
        <>
          {/* MASTER STATUS CARD */}
          {report.is_conflict_free ? (
            <div className="bg-gradient-to-r from-emerald-50 via-white to-emerald-50/30 rounded-xl border-2 border-emerald-300 p-6 shadow-xs">
              <div className="flex items-start justify-between gap-4">
                <div className="flex items-start space-x-3.5">
                  <div className="w-10 h-10 rounded-full bg-emerald-100 flex items-center justify-center flex-shrink-0 text-emerald-600">
                    <ShieldCheck className="w-6 h-6" />
                  </div>
                  <div>
                    <div className="flex items-center space-x-2">
                      <span className="text-xs font-bold uppercase tracking-wider text-emerald-700 bg-emerald-100 px-2 py-0.5 rounded">
                        Verified 100% Conflict-Free
                      </span>
                      <span className="text-xs text-slate-500 font-medium">
                        Master Schedule {report.version_str} ({report.status})
                      </span>
                    </div>
                    <h3 className="text-lg font-bold text-[#17324D] mt-1">
                      Zero Hard Constraint Violations Detected
                    </h3>
                    <p className="text-xs text-[#697586] mt-1 max-w-3xl leading-relaxed">
                      All {report.total_sessions} academic sessions meet institutional requirements. No teacher double-bookings, facility clashes, room capacity deficits, or cohort section overlaps exist.
                    </p>
                  </div>
                </div>

                <Link
                  href="/timetables"
                  className="hidden md:flex items-center space-x-1.5 px-3.5 py-2 rounded-lg bg-[#1261A0] text-white hover:bg-[#0E4E82] text-xs font-semibold flex-shrink-0"
                >
                  <span>Open Full Timetable</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </Link>
              </div>
            </div>
          ) : (
            <div className="bg-gradient-to-r from-rose-50 via-white to-rose-50/40 rounded-xl border-2 border-rose-300 p-6 shadow-xs">
              <div className="flex items-start justify-between gap-4">
                <div className="flex items-start space-x-3.5">
                  <div className="w-10 h-10 rounded-full bg-rose-100 flex items-center justify-center flex-shrink-0 text-rose-600">
                    <ShieldAlert className="w-6 h-6" />
                  </div>
                  <div>
                    <div className="flex items-center space-x-2">
                      <span className="text-xs font-bold uppercase tracking-wider text-rose-700 bg-rose-100 px-2 py-0.5 rounded">
                        Hard Constraint Violations Detected
                      </span>
                      <span className="text-xs text-rose-600 font-bold">
                        {report.critical_conflicts_count} Critical Clash{report.critical_conflicts_count > 1 ? "es" : ""}
                      </span>
                    </div>
                    <h3 className="text-lg font-bold text-[#17324D] mt-1">
                      Timetable Cannot Be Approved or Published
                    </h3>
                    <p className="text-xs text-[#697586] mt-1 max-w-3xl leading-relaxed">
                      Mandatory institutional constraints are violated. Review the clashes below or launch the Smart Rescheduler to automatically resolve overlaps without cascading disruptions.
                    </p>
                  </div>
                </div>

                <Link
                  href="/rescheduler"
                  className="hidden md:flex items-center space-x-1.5 px-4 py-2.5 rounded-lg bg-rose-600 text-white hover:bg-rose-700 text-xs font-semibold flex-shrink-0 shadow-xs"
                >
                  <Zap className="w-3.5 h-3.5" />
                  <span>Launch Smart Rescheduler</span>
                </Link>
              </div>
            </div>
          )}

          {/* METRICS STRIP */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <div className="bg-white rounded-xl border border-[#E2E7EE] p-4 shadow-xs">
              <div className="text-xs text-[#697586]">Critical Clashes</div>
              <div className={`text-2xl font-bold mt-1 ${report.critical_conflicts_count > 0 ? "text-[#B42332]" : "text-[#16805D]"}`}>
                {report.critical_conflicts_count}
              </div>
              <div className="text-[11px] text-slate-400 mt-0.5">Hard blocking failures</div>
            </div>

            <div className="bg-white rounded-xl border border-[#E2E7EE] p-4 shadow-xs">
              <div className="text-xs text-[#697586]">Workload Warnings</div>
              <div className="text-2xl font-bold text-[#17324D] mt-1">{report.warnings_count}</div>
              <div className="text-[11px] text-slate-400 mt-0.5">Soft guideline flags</div>
            </div>

            <div className="bg-white rounded-xl border border-[#E2E7EE] p-4 shadow-xs">
              <div className="text-xs text-[#697586]">Total Class Sessions</div>
              <div className="text-2xl font-bold text-[#1261A0] mt-1">{report.total_sessions}</div>
              <div className="text-[11px] text-slate-400 mt-0.5">Enrolled across cohorts</div>
            </div>

            <div className="bg-white rounded-xl border border-[#E2E7EE] p-4 shadow-xs">
              <div className="text-xs text-[#697586]">Active Compliance Rate</div>
              <div className="text-2xl font-bold text-[#17324D] mt-1">
                {report.total_sessions > 0
                  ? `${Math.round(((report.total_sessions - report.critical_conflicts_count) / report.total_sessions) * 100)}%`
                  : "100%"}
              </div>
              <div className="text-[11px] text-[#16805D] mt-0.5 font-medium">Constraints Verified</div>
            </div>
          </div>

          {/* CONFLICTS LIST */}
          <div className="bg-white rounded-xl border border-[#E2E7EE] p-5 shadow-xs space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 pb-3 border-b border-slate-100">
              <div className="flex items-center space-x-2">
                <ShieldAlert className="w-4 h-4 text-[#1261A0]" />
                <h3 className="font-bold text-sm text-[#17324D]">
                  Identified Conflicts & Diagnostic Breakdown ({filteredConflicts.length})
                </h3>
              </div>

              {/* Category Filter Tabs */}
              <div className="flex items-center space-x-1.5 bg-[#F7F9FC] p-1 rounded-lg border border-[#E2E7EE] text-xs">
                <button
                  onClick={() => setSelectedFilter("ALL")}
                  className={`px-2.5 py-1 rounded font-semibold transition-colors ${
                    selectedFilter === "ALL" ? "bg-white text-[#1261A0] shadow-xs" : "text-slate-600 hover:text-slate-900"
                  }`}
                >
                  All ({report.conflicts.length})
                </button>
                <button
                  onClick={() => setSelectedFilter("TEACHER")}
                  className={`px-2.5 py-1 rounded font-semibold transition-colors ${
                    selectedFilter === "TEACHER" ? "bg-white text-[#1261A0] shadow-xs" : "text-slate-600 hover:text-slate-900"
                  }`}
                >
                  Faculty Clashes
                </button>
                <button
                  onClick={() => setSelectedFilter("ROOM")}
                  className={`px-2.5 py-1 rounded font-semibold transition-colors ${
                    selectedFilter === "ROOM" ? "bg-white text-[#1261A0] shadow-xs" : "text-slate-600 hover:text-slate-900"
                  }`}
                >
                  Room & Capacity
                </button>
                <button
                  onClick={() => setSelectedFilter("COHORT")}
                  className={`px-2.5 py-1 rounded font-semibold transition-colors ${
                    selectedFilter === "COHORT" ? "bg-white text-[#1261A0] shadow-xs" : "text-slate-600 hover:text-slate-900"
                  }`}
                >
                  Cohort Clashes
                </button>
              </div>
            </div>

            {filteredConflicts.length === 0 ? (
              <div className="py-12 text-center">
                <CheckCircle className="w-10 h-10 text-emerald-500 mx-auto mb-2" />
                <h4 className="text-sm font-bold text-[#17324D]">No Conflicts in Selected Category</h4>
                <p className="text-xs text-[#697586] mt-1">
                  The schedule satisfies all constraints in this filter category.
                </p>
              </div>
            ) : (
              <div className="space-y-4">
                {filteredConflicts.map((c) => (
                  <div
                    key={c.id}
                    className="p-4 rounded-xl border border-rose-200 bg-rose-50/20 hover:border-rose-300 transition-colors space-y-3"
                  >
                    <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-2">
                      <div>
                        <div className="flex items-center space-x-2">
                          <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-rose-100 text-[#B42332] uppercase tracking-wider">
                            {c.severity} • {c.type.replace(/_/g, " ")}
                          </span>
                          <span className="text-xs text-slate-500 font-semibold flex items-center">
                            <Clock className="w-3 h-3 mr-1 text-slate-400" />
                            {c.day_name} • Period {c.period_number}
                          </span>
                        </div>
                        <h4 className="text-sm font-bold text-[#17324D] mt-1">{c.title}</h4>
                        <p className="text-xs text-[#697586] mt-0.5 leading-relaxed">{c.description}</p>
                      </div>

                      <Link
                        href="/rescheduler"
                        className="self-start px-3 py-1.5 rounded-lg bg-[#1261A0] hover:bg-[#0E4E82] text-white text-xs font-semibold flex items-center space-x-1 flex-shrink-0"
                      >
                        <Zap className="w-3.5 h-3.5" />
                        <span>Resolve in Rescheduler</span>
                      </Link>
                    </div>

                    {/* Affected Competing Classes Side-by-Side */}
                    <div className="bg-white rounded-lg border border-[#E2E7EE] p-3">
                      <div className="text-[11px] font-bold text-slate-700 uppercase tracking-wider mb-2">
                        Competing Sessions in this Slot ({c.affected_classes.length})
                      </div>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
                        {c.affected_classes.map((cls, idx) => (
                          <div
                            key={cls.session_id || idx}
                            className="p-2.5 rounded-lg border border-slate-100 bg-[#F7F9FC] flex items-start justify-between text-xs"
                          >
                            <div>
                              <div className="font-bold text-[#17324D]">
                                {cls.subject_code} — {cls.subject_name}
                              </div>
                              <div className="text-[11px] text-[#697586] mt-1 space-y-0.5">
                                <div className="flex items-center">
                                  <Users className="w-3 h-3 mr-1 text-[#1261A0]" />
                                  <span>Section: <strong>{cls.cohort_name}</strong></span>
                                </div>
                                <div className="flex items-center">
                                  <UserCheck className="w-3 h-3 mr-1 text-[#1261A0]" />
                                  <span>Instructor: {cls.teacher_name}</span>
                                </div>
                                <div className="flex items-center">
                                  <MapPin className="w-3 h-3 mr-1 text-[#1261A0]" />
                                  <span>Room: {cls.room_name}</span>
                                </div>
                              </div>
                            </div>
                            <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-200 text-slate-700">
                              #{cls.session_id}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* Feasible Resolution Suggestions */}
                    {c.feasible_resolutions && c.feasible_resolutions.length > 0 && (
                      <div className="p-3 rounded-lg bg-emerald-50/70 border border-emerald-200 text-xs text-emerald-900 space-y-1">
                        <div className="font-bold flex items-center space-x-1.5 text-emerald-800">
                          <Sparkles className="w-3.5 h-3.5 text-emerald-600" />
                          <span>Feasible Resolution Recommendations</span>
                        </div>
                        <ul className="list-disc list-inside space-y-1 text-[11px] text-emerald-800/90 pl-1">
                          {c.feasible_resolutions.map((res, rIdx) => (
                            <li key={rIdx}>{res}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* CHECKED CONSTRAINTS CHECKLIST */}
          <div className="bg-white rounded-xl border border-[#E2E7EE] p-5 shadow-xs">
            <h3 className="font-bold text-sm text-[#17324D] mb-3">Institutional Constraint Safety Rules Evaluated</h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
              {[
                { title: "Teacher Double-Booking", desc: "No instructor assigned to overlapping classes simultaneously" },
                { title: "Room & Lab Double-Booking", desc: "No room allocated to multiple sections at the same period" },
                { title: "Student Cohort Overlaps", desc: "Cohort sections attend exactly one subject per period" },
                { title: "Room Capacity Compliance", desc: "Classroom seats strictly exceed cohort enrolled student count" },
                { title: "Lab & Facility Suitability", desc: "Theory classes in lecture halls; practicals in dedicated laboratories" },
                { title: "Break & Institutional Hours", desc: "No teaching sessions scheduled during campus recess/lunch breaks" },
                { title: "Faculty Availability Limits", desc: "Classes respect faculty leave and declared unavailable hours" },
              ].map((rule, idx) => (
                <div key={idx} className="p-3 rounded-lg border border-[#E2E7EE] bg-[#F7F9FC]">
                  <div className="flex items-center space-x-2">
                    <CheckCircle className="w-4 h-4 text-emerald-600 flex-shrink-0" />
                    <span className="text-xs font-bold text-[#17324D]">{rule.title}</span>
                  </div>
                  <p className="text-[11px] text-[#697586] mt-1">{rule.desc}</p>
                </div>
              ))}
            </div>
          </div>
        </>
      ) : null}
    </div>
  );
}
