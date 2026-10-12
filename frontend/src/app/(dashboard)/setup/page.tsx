"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { apiRequest } from "@/lib/api";
import {
  AlertCircle,
  ArrowLeft,
  ArrowRight,
  BookOpen,
  Calendar,
  CheckCircle,
  Clock,
  DoorOpen,
  FileSpreadsheet,
  GraduationCap,
  HelpCircle,
  Layers,
  Save,
  Send,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Users,
} from "lucide-react";

interface SetupSummary {
  department_id: string;
  department_name: string;
  active_term: {
    id: string;
    name: string;
    start_date: string;
    end_date: string;
  } | null;
  counts: {
    teachers: number;
    subjects: number;
    rooms: number;
    cohort_sections: number;
    requirements: number;
    time_slots: number;
  };
  readiness_checks: Array<{
    step: number;
    name: string;
    passed: boolean;
    message: string;
  }>;
  is_ready_for_generation: boolean;
  saved_draft?: any;
}

const STEPS = [
  { id: 1, title: "Semester Details", desc: "Dates, academic term & working days" },
  { id: 2, title: "Teachers & Subjects", desc: "Teaching requirements & faculty allocation" },
  { id: 3, title: "Classrooms & Labs", desc: "Rooms, capacities & laboratory equipment" },
  { id: 4, title: "Timetable Rules", desc: "Periods, lunch break & workload limits" },
  { id: 5, title: "Review & Generate", desc: "Verify data readiness & launch schedule" },
];

export default function SemesterSetupWizardPage() {
  const { user } = useAuth();
  const router = useRouter();

  const [currentStep, setCurrentStep] = useState(1);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [summary, setSummary] = useState<SetupSummary | null>(null);
  const [statusMessage, setStatusMessage] = useState<{ text: string; type: "success" | "error" | "info" } | null>(null);

  // Form State
  const [academicYear, setAcademicYear] = useState("2026-2027");
  const [termName, setTermName] = useState("Odd Semester 2026");
  const [startDate, setStartDate] = useState("2026-08-01");
  const [endDate, setEndDate] = useState("2026-12-15");
  const [workingDays, setWorkingDays] = useState<number[]>([1, 2, 3, 4, 5]);

  // Rules State
  const [collegeStartTime, setCollegeStartTime] = useState("09:00");
  const [periodDuration, setPeriodDuration] = useState(50);
  const [lunchPeriod, setLunchPeriod] = useState(4);
  const [maxTeacherDaily, setMaxTeacherDaily] = useState(4);
  const [maxCohortDaily, setMaxCohortDaily] = useState(5);
  const [balanceWorkload, setBalanceWorkload] = useState(15);
  const [minimizeGaps, setMinimizeGaps] = useState(10);

  const fetchSummary = async () => {
    try {
      setLoading(true);
      const res: SetupSummary = await apiRequest("/setup/summary/dept_cs");
      setSummary(res);

      if (res.saved_draft) {
        const d = res.saved_draft;
        if (d.semester_details) {
          setAcademicYear(d.semester_details.academic_year || "2026-2027");
          setTermName(d.semester_details.term_name || "Odd Semester 2026");
          setStartDate(d.semester_details.start_date || "2026-08-01");
          setEndDate(d.semester_details.end_date || "2026-12-15");
          setWorkingDays(d.semester_details.working_days || [1, 2, 3, 4, 5]);
        }
        if (d.rules) {
          setCollegeStartTime(d.rules.college_start_time || "09:00");
          setPeriodDuration(d.rules.period_duration_minutes || 50);
          setLunchPeriod(d.rules.lunch_period || 4);
          setMaxTeacherDaily(d.rules.max_daily_sessions_per_teacher || 4);
          setMaxCohortDaily(d.rules.max_daily_sessions_per_cohort || 5);
        }
        if (d.current_step && d.current_step >= 1 && d.current_step <= 5) {
          setCurrentStep(d.current_step);
        }
      } else if (res.active_term) {
        setTermName(res.active_term.name);
        setStartDate(res.active_term.start_date);
        setEndDate(res.active_term.end_date);
      }
    } catch (e: any) {
      console.error(e);
      setStatusMessage({ text: "Failed to load department setup information.", type: "error" });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (user && ["ADMIN", "HOD", "COORDINATOR"].includes(user.role)) {
      fetchSummary();
    }
  }, [user]);

  const handleSaveDraft = async () => {
    try {
      setSaving(true);
      setStatusMessage(null);
      await apiRequest("/setup/draft", {
        method: "POST",
        body: JSON.stringify({
          department_id: "dept_cs",
          current_step: currentStep,
          semester_details: {
            academic_year: academicYear,
            term_name: termName,
            start_date: startDate,
            end_date: endDate,
            department_id: "dept_cs",
            working_days: workingDays,
            daily_periods: 6,
          },
          rules: {
            college_start_time: collegeStartTime,
            period_duration_minutes: periodDuration,
            lunch_period: lunchPeriod,
            max_daily_sessions_per_teacher: maxTeacherDaily,
            max_daily_sessions_per_cohort: maxCohortDaily,
            weight_balanced_daily_workload: balanceWorkload,
            weight_minimize_gaps: minimizeGaps,
          },
        }),
      });
      setStatusMessage({ text: "Progress saved as draft. You can safely return anytime.", type: "success" });
    } catch (e: any) {
      setStatusMessage({ text: e.message || "Could not save draft.", type: "error" });
    } finally {
      setSaving(false);
    }
  };

  const handleCommitAndProceed = async () => {
    try {
      setSaving(true);
      setStatusMessage(null);
      await apiRequest("/setup/commit", {
        method: "POST",
        body: JSON.stringify({
          department_id: "dept_cs",
          current_step: 5,
          semester_details: {
            academic_year: academicYear,
            term_name: termName,
            start_date: startDate,
            end_date: endDate,
            department_id: "dept_cs",
            working_days: workingDays,
            daily_periods: 6,
          },
          rules: {
            college_start_time: collegeStartTime,
            period_duration_minutes: periodDuration,
            lunch_period: lunchPeriod,
            max_daily_sessions_per_teacher: maxTeacherDaily,
            max_daily_sessions_per_cohort: maxCohortDaily,
            weight_balanced_daily_workload: balanceWorkload,
            weight_minimize_gaps: minimizeGaps,
          },
        }),
      });
      setStatusMessage({ text: "Semester rules saved and activated successfully! Redirecting to Timetable Planner...", type: "success" });
      setTimeout(() => {
        router.push("/timetables");
      }, 1500);
    } catch (e: any) {
      setStatusMessage({ text: e.message || "Failed to commit semester configuration.", type: "error" });
    } finally {
      setSaving(false);
    }
  };

  const toggleDay = (day: number) => {
    if (workingDays.includes(day)) {
      if (workingDays.length > 1) {
        setWorkingDays(workingDays.filter((d) => d !== day));
      }
    } else {
      setWorkingDays([...workingDays, day].sort());
    }
  };

  const dayLabels = [
    { id: 1, name: "Monday" },
    { id: 2, name: "Tuesday" },
    { id: 3, name: "Wednesday" },
    { id: 4, name: "Thursday" },
    { id: 5, name: "Friday" },
    { id: 6, name: "Saturday" },
  ];

  if (user && !["ADMIN", "HOD", "COORDINATOR"].includes(user.role)) {
    return (
      <div className="bg-white rounded-xl border border-[#E2E7EE] p-8 text-center max-w-lg mx-auto my-12 shadow-xs">
        <ShieldAlert className="w-12 h-12 text-[#B42332] mx-auto mb-3" />
        <h2 className="text-lg font-bold text-[#17324D]">Access Restricted</h2>
        <p className="text-xs text-[#697586] mt-1.5 leading-relaxed">
          The Semester Setup Wizard is reserved for Department Heads and Administrative Coordinators.
          Your current role ({user.role}) does not have permission to modify institution scheduling configuration.
        </p>
        <div className="mt-5 flex items-center justify-center space-x-3">
          <Link
            href="/timetables"
            className="px-4 py-2 bg-[#1261A0] text-white text-xs font-semibold rounded-lg hover:bg-[#0E4E82] transition-colors"
          >
            Go to Timetable
          </Link>
          <Link
            href="/guide"
            className="px-4 py-2 border border-[#E2E7EE] text-slate-700 text-xs font-semibold rounded-lg hover:bg-slate-50 transition-colors"
          >
            Open Guide
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      {/* Page Header answering: Where am I? What can I do here? What should I do next? */}
      <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2 text-xs text-blue-700 font-semibold tracking-wide uppercase">
            <Sparkles className="w-4 h-4 text-blue-600" />
            <span>Semester Setup Wizard</span>
          </div>
          <h1 className="text-2xl font-bold text-slate-900 mt-1">Configure New Semester</h1>
          <p className="text-sm text-slate-600 mt-1">
            Follow these 5 guided steps to prepare semester dates, faculty workloads, classrooms, and scheduling rules before generating timetables.
          </p>
        </div>

        <div className="flex items-center space-x-3">
          <button
            onClick={handleSaveDraft}
            disabled={saving}
            className="flex items-center space-x-2 px-4 py-2 border border-slate-300 rounded-lg text-sm font-medium text-slate-700 hover:bg-slate-50 transition-colors shadow-xs"
          >
            <Save className="w-4 h-4 text-slate-500" />
            <span>{saving ? "Saving..." : "Save Draft"}</span>
          </button>
          <Link
            href="/import"
            className="flex items-center space-x-2 px-4 py-2 bg-blue-50 border border-blue-200 rounded-lg text-sm font-semibold text-blue-700 hover:bg-blue-100 transition-colors shadow-xs"
          >
            <FileSpreadsheet className="w-4 h-4 text-blue-600" />
            <span>Import via Excel</span>
          </Link>
        </div>
      </div>

      {/* Status banner */}
      {statusMessage && (
        <div
          className={`p-4 rounded-xl border flex items-center justify-between ${
            statusMessage.type === "success"
              ? "bg-emerald-50 border-emerald-200 text-emerald-800"
              : statusMessage.type === "error"
              ? "bg-rose-50 border-rose-200 text-rose-800"
              : "bg-blue-50 border-blue-200 text-blue-800"
          }`}
        >
          <div className="flex items-center space-x-2.5 text-sm font-medium">
            {statusMessage.type === "success" ? (
              <CheckCircle className="w-5 h-5 text-emerald-600 flex-shrink-0" />
            ) : (
              <AlertCircle className="w-5 h-5 text-rose-600 flex-shrink-0" />
            )}
            <span>{statusMessage.text}</span>
          </div>
          <button onClick={() => setStatusMessage(null)} className="text-xs font-semibold underline ml-4">
            Dismiss
          </button>
        </div>
      )}

      {/* Stepper Progress Bar */}
      <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs">
        <div className="grid grid-cols-1 sm:grid-cols-5 gap-3">
          {STEPS.map((s) => {
            const isActive = currentStep === s.id;
            const isCompleted = currentStep > s.id;
            return (
              <button
                key={s.id}
                onClick={() => setCurrentStep(s.id)}
                className={`text-left p-3 rounded-lg border transition-all ${
                  isActive
                    ? "border-blue-600 bg-blue-50/70 shadow-xs"
                    : isCompleted
                    ? "border-emerald-200 bg-emerald-50/50 hover:bg-emerald-100/50"
                    : "border-slate-200 bg-white hover:bg-slate-50"
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <span
                    className={`inline-flex items-center justify-center w-6 h-6 rounded-full text-xs font-bold ${
                      isActive
                        ? "bg-blue-600 text-white"
                        : isCompleted
                        ? "bg-emerald-600 text-white"
                        : "bg-slate-100 text-slate-600"
                    }`}
                  >
                    {isCompleted ? <CheckCircle className="w-3.5 h-3.5" /> : s.id}
                  </span>
                  <span className="text-[11px] font-medium text-slate-500">Step {s.id} of 5</span>
                </div>
                <div className="text-xs font-bold text-slate-900 truncate">{s.title}</div>
                <div className="text-[11px] text-slate-500 truncate">{s.desc}</div>
              </button>
            );
          })}
        </div>
      </div>

      {/* Step Content Container */}
      <div className="bg-white rounded-xl border border-slate-200 p-6 md:p-8 shadow-xs">
        {/* STEP 1: SEMESTER DETAILS */}
        {currentStep === 1 && (
          <div className="space-y-6">
            <div>
              <h2 className="text-lg font-bold text-slate-900">Step 1 — Semester Details</h2>
              <p className="text-sm text-slate-600 mt-0.5">
                Specify academic dates, semester name, and institutional working days.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                  Academic Year
                </label>
                <input
                  type="text"
                  value={academicYear}
                  onChange={(e) => setAcademicYear(e.target.value)}
                  className="w-full px-3.5 py-2.5 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none"
                  placeholder="e.g. 2026-2027"
                />
                <span className="text-xs text-slate-500 mt-1 block">Full institutional academic cycle.</span>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                  Semester Term Name
                </label>
                <input
                  type="text"
                  value={termName}
                  onChange={(e) => setTermName(e.target.value)}
                  className="w-full px-3.5 py-2.5 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none"
                  placeholder="e.g. Odd Semester 2026"
                />
                <span className="text-xs text-slate-500 mt-1 block">Official designation displayed on student schedules.</span>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                  Term Commencement Date
                </label>
                <input
                  type="date"
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                  className="w-full px-3.5 py-2.5 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                  Term Conclusion Date
                </label>
                <input
                  type="date"
                  value={endDate}
                  onChange={(e) => setEndDate(e.target.value)}
                  className="w-full px-3.5 py-2.5 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-2">
                Active Working Days
              </label>
              <div className="grid grid-cols-2 sm:grid-cols-6 gap-2.5">
                {dayLabels.map((d) => {
                  const isSelected = workingDays.includes(d.id);
                  return (
                    <button
                      key={d.id}
                      type="button"
                      onClick={() => toggleDay(d.id)}
                      className={`py-2 px-3 rounded-lg border text-xs font-semibold text-center transition-colors ${
                        isSelected
                          ? "bg-blue-600 border-blue-600 text-white shadow-xs"
                          : "bg-slate-50 border-slate-200 text-slate-600 hover:bg-slate-100"
                      }`}
                    >
                      {d.name}
                    </button>
                  );
                })}
              </div>
              <p className="text-xs text-slate-500 mt-2">
                Timetable sessions will only be scheduled across selected working days.
              </p>
            </div>
          </div>
        )}

        {/* STEP 2: TEACHERS AND SUBJECTS */}
        {currentStep === 2 && (
          <div className="space-y-6">
            <div>
              <h2 className="text-lg font-bold text-slate-900">Step 2 — Teachers and Subjects</h2>
              <p className="text-sm text-slate-600 mt-0.5">
                Review assigned faculty members, courses, and weekly lecture requirements.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="p-4 rounded-xl border border-slate-200 bg-slate-50">
                <div className="flex items-center space-x-2 text-blue-700 mb-1">
                  <Users className="w-4 h-4" />
                  <span className="text-xs font-bold uppercase">Registered Faculty</span>
                </div>
                <div className="text-2xl font-bold text-slate-900">{summary?.counts?.teachers || 0}</div>
                <p className="text-xs text-slate-500 mt-1">Teachers in Computer Science</p>
              </div>

              <div className="p-4 rounded-xl border border-slate-200 bg-slate-50">
                <div className="flex items-center space-x-2 text-indigo-700 mb-1">
                  <BookOpen className="w-4 h-4" />
                  <span className="text-xs font-bold uppercase">Curriculum Subjects</span>
                </div>
                <div className="text-2xl font-bold text-slate-900">{summary?.counts?.subjects || 0}</div>
                <p className="text-xs text-slate-500 mt-1">Theory & laboratory courses</p>
              </div>

              <div className="p-4 rounded-xl border border-slate-200 bg-slate-50">
                <div className="flex items-center space-x-2 text-emerald-700 mb-1">
                  <Calendar className="w-4 h-4" />
                  <span className="text-xs font-bold uppercase">Teaching Requirements</span>
                </div>
                <div className="text-2xl font-bold text-slate-900">{summary?.counts?.requirements || 0}</div>
                <p className="text-xs text-slate-500 mt-1">Mapped subject-section pairs</p>
              </div>
            </div>

            <div className="rounded-xl border border-blue-100 bg-blue-50/50 p-4">
              <div className="flex items-start space-x-3">
                <HelpCircle className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />
                <div className="text-xs text-blue-900 leading-relaxed">
                  <strong>Need to upload new teachers or teaching requirements?</strong>
                  <p className="mt-0.5 text-blue-800">
                    You can import complete faculty rosters and subject requirements directly from your college Excel/CSV spreadsheets without typing everything by hand.
                  </p>
                  <Link
                    href="/import"
                    className="inline-flex items-center space-x-1.5 font-bold text-blue-700 underline mt-2 hover:text-blue-800"
                  >
                    <span>Open Excel Importer</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </Link>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* STEP 3: CLASSROOMS AND LABS */}
        {currentStep === 3 && (
          <div className="space-y-6">
            <div>
              <h2 className="text-lg font-bold text-slate-900">Step 3 — Classrooms and Labs</h2>
              <p className="text-sm text-slate-600 mt-0.5">
                Verify available lecture halls, computer labs, and seating capacities.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="p-5 rounded-xl border border-slate-200 bg-white">
                <div className="flex items-center space-x-2 text-blue-700 mb-2">
                  <DoorOpen className="w-5 h-5" />
                  <span className="text-sm font-bold">Physical Classrooms & Labs</span>
                </div>
                <div className="text-3xl font-bold text-slate-900">{summary?.counts?.rooms || 0}</div>
                <p className="text-xs text-slate-500 mt-1">
                  Active rooms configured with seating capacity and equipment tags.
                </p>
              </div>

              <div className="p-5 rounded-xl border border-slate-200 bg-white">
                <div className="flex items-center space-x-2 text-indigo-700 mb-2">
                  <GraduationCap className="w-5 h-5" />
                  <span className="text-sm font-bold">Student Cohort Sections</span>
                </div>
                <div className="text-3xl font-bold text-slate-900">{summary?.counts?.cohort_sections || 0}</div>
                <p className="text-xs text-slate-500 mt-1">
                  Sections requiring dedicated class seating (e.g. CS-3A, CS-3B).
                </p>
              </div>
            </div>

            <div className="p-4 rounded-xl border border-amber-200 bg-amber-50">
              <div className="flex items-start space-x-3">
                <ShieldCheck className="w-5 h-5 text-amber-700 flex-shrink-0 mt-0.5" />
                <div className="text-xs text-amber-900 leading-relaxed">
                  <strong>Room Capacity & Laboratory Suitability Rules</strong>
                  <p className="mt-1 text-amber-800">
                    The TIMEVERSE scheduler strictly ensures laboratory sessions are assigned to appropriate Computer Labs, and that room seating capacity meets or exceeds section student headcount.
                  </p>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* STEP 4: TIMETABLE RULES */}
        {currentStep === 4 && (
          <div className="space-y-6">
            <div>
              <h2 className="text-lg font-bold text-slate-900">Step 4 — Timetable Rules</h2>
              <p className="text-sm text-slate-600 mt-0.5">
                Configure timing constraints, recess, lunch breaks, and maximum teacher workloads.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                  College Opening Time
                </label>
                <div className="flex items-center space-x-2">
                  <Clock className="w-4 h-4 text-slate-400" />
                  <input
                    type="time"
                    value={collegeStartTime}
                    onChange={(e) => setCollegeStartTime(e.target.value)}
                    className="w-full px-3.5 py-2.5 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                  Period Duration (Minutes)
                </label>
                <select
                  value={periodDuration}
                  onChange={(e) => setPeriodDuration(Number(e.target.value))}
                  className="w-full px-3.5 py-2.5 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none"
                >
                  <option value={45}>45 Minutes</option>
                  <option value={50}>50 Minutes (Standard)</option>
                  <option value={60}>60 Minutes (1 Hour)</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                  Designated Lunch Break Period
                </label>
                <select
                  value={lunchPeriod}
                  onChange={(e) => setLunchPeriod(Number(e.target.value))}
                  className="w-full px-3.5 py-2.5 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none"
                >
                  <option value={3}>Period 3 (11:00 - 11:50)</option>
                  <option value={4}>Period 4 (12:00 - 12:50 - Standard)</option>
                  <option value={5}>Period 5 (13:00 - 13:50)</option>
                </select>
                <span className="text-xs text-slate-500 mt-1 block">No academic lectures will be scheduled during this break.</span>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                  Max Daily Lectures per Teacher
                </label>
                <input
                  type="number"
                  min={1}
                  max={6}
                  value={maxTeacherDaily}
                  onChange={(e) => setMaxTeacherDaily(Number(e.target.value))}
                  className="w-full px-3.5 py-2.5 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none"
                />
                <span className="text-xs text-slate-500 mt-1 block">Prevents teacher burnout and balances workload.</span>
              </div>
            </div>

            <div className="pt-4 border-t border-slate-200">
              <h3 className="text-sm font-bold text-slate-900 mb-3">Optimization Weights</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="p-3.5 rounded-lg border border-slate-200 bg-slate-50">
                  <div className="flex justify-between items-center mb-1">
                    <span className="text-xs font-semibold text-slate-700">Balanced Daily Workload</span>
                    <span className="text-xs font-bold text-blue-700">{balanceWorkload}/20</span>
                  </div>
                  <input
                    type="range"
                    min={5}
                    max={20}
                    value={balanceWorkload}
                    onChange={(e) => setBalanceWorkload(Number(e.target.value))}
                    className="w-full accent-blue-600"
                  />
                  <span className="text-[11px] text-slate-500 block mt-1">Distributes subjects evenly across Monday-Friday.</span>
                </div>

                <div className="p-3.5 rounded-lg border border-slate-200 bg-slate-50">
                  <div className="flex justify-between items-center mb-1">
                    <span className="text-xs font-semibold text-slate-700">Minimize Student Gaps</span>
                    <span className="text-xs font-bold text-blue-700">{minimizeGaps}/20</span>
                  </div>
                  <input
                    type="range"
                    min={5}
                    max={20}
                    value={minimizeGaps}
                    onChange={(e) => setMinimizeGaps(Number(e.target.value))}
                    className="w-full accent-blue-600"
                  />
                  <span className="text-[11px] text-slate-500 block mt-1">Reduces idle waiting periods between classes.</span>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* STEP 5: REVIEW AND CONTINUE */}
        {currentStep === 5 && (
          <div className="space-y-6">
            <div>
              <h2 className="text-lg font-bold text-slate-900">Step 5 — Review and Continue</h2>
              <p className="text-sm text-slate-600 mt-0.5">
                Review the readiness checklist before committing semester rules and generating timetables.
              </p>
            </div>

            <div className="space-y-3">
              {summary?.readiness_checks?.map((check) => (
                <div
                  key={check.step}
                  className={`p-4 rounded-xl border flex items-center justify-between ${
                    check.passed ? "border-emerald-200 bg-emerald-50/50" : "border-amber-200 bg-amber-50/50"
                  }`}
                >
                  <div className="flex items-center space-x-3">
                    {check.passed ? (
                      <CheckCircle className="w-5 h-5 text-emerald-600 flex-shrink-0" />
                    ) : (
                      <AlertCircle className="w-5 h-5 text-amber-600 flex-shrink-0" />
                    )}
                    <div>
                      <div className="text-sm font-bold text-slate-900">{check.name}</div>
                      <div className="text-xs text-slate-600 mt-0.5">{check.message}</div>
                    </div>
                  </div>
                  <span
                    className={`px-2.5 py-1 rounded-full text-xs font-bold ${
                      check.passed ? "bg-emerald-100 text-emerald-800" : "bg-amber-100 text-amber-800"
                    }`}
                  >
                    {check.passed ? "Ready" : "Pending"}
                  </span>
                </div>
              ))}
            </div>

            <div className="p-5 rounded-xl border border-slate-200 bg-slate-50">
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700 mb-2">Configuration Summary</h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs">
                <div>
                  <span className="text-slate-500 block">Semester Term:</span>
                  <span className="font-bold text-slate-900">{termName}</span>
                </div>
                <div>
                  <span className="text-slate-500 block">Duration:</span>
                  <span className="font-bold text-slate-900">{startDate} to {endDate}</span>
                </div>
                <div>
                  <span className="text-slate-500 block">Working Days:</span>
                  <span className="font-bold text-slate-900">{workingDays.length} Days/Week</span>
                </div>
                <div>
                  <span className="text-slate-500 block">Lunch Break:</span>
                  <span className="font-bold text-slate-900">Period {lunchPeriod}</span>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Wizard Navigation Footer */}
        <div className="mt-8 pt-6 border-t border-slate-200 flex items-center justify-between">
          <div>
            {currentStep > 1 ? (
              <button
                type="button"
                onClick={() => setCurrentStep(currentStep - 1)}
                className="flex items-center space-x-2 px-4 py-2 border border-slate-300 rounded-lg text-sm font-medium text-slate-700 hover:bg-slate-50 transition-colors shadow-xs"
              >
                <ArrowLeft className="w-4 h-4" />
                <span>Previous Step</span>
              </button>
            ) : (
              <Link
                href="/dashboard"
                className="flex items-center space-x-2 px-4 py-2 border border-slate-300 rounded-lg text-sm font-medium text-slate-700 hover:bg-slate-50 transition-colors"
              >
                <span>Back to Dashboard</span>
              </Link>
            )}
          </div>

          <div className="flex items-center space-x-3">
            {currentStep < 5 ? (
              <button
                type="button"
                onClick={() => setCurrentStep(currentStep + 1)}
                className="flex items-center space-x-2 px-5 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-semibold transition-colors shadow-xs"
              >
                <span>Next Step</span>
                <ArrowRight className="w-4 h-4" />
              </button>
            ) : (
              <button
                type="button"
                onClick={handleCommitAndProceed}
                disabled={saving}
                className="flex items-center space-x-2 px-6 py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-sm font-semibold transition-colors shadow-xs"
              >
                <Send className="w-4 h-4" />
                <span>{saving ? "Saving..." : "Save & Proceed to Timetable Planner"}</span>
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
