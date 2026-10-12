"use client";

import React, { useEffect, useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { useAuth } from "@/context/AuthContext";
import { apiRequest } from "@/lib/api";
import {
  AlertCircle,
  AlertTriangle,
  Bot,
  Calendar,
  CheckCircle,
  ChevronLeft,
  ChevronRight,
  Clock,
  Cpu,
  Edit2,
  GitCompare,
  History,
  Layers,
  Lock,
  MapPin,
  Plus,
  Printer,
  RefreshCw,
  RotateCcw,
  Send,
  ShieldAlert,
  Sparkles,
  Trash2,
  Unlock,
  Upload,
  UserCheck,
  Users,
  X,
  XCircle,
} from "lucide-react";

interface SessionData {
  session_id: string;
  subject_id?: string;
  subject_code: string;
  subject_name: string;
  subject_type: string;
  teacher_id?: string;
  teacher_name: string;
  room_id?: string;
  room_name: string;
  room_type: string;
  section_id?: string;
  section_name: string;
  time_slot_id?: string;
  status: string;
  is_locked?: boolean;
}

interface PeriodHeader {
  period: number;
  is_break: boolean;
  label: string;
}

interface DayRow {
  day_number: number;
  day_name: string;
  periods: Array<{
    period_number: number;
    is_break: boolean;
    session: SessionData | null;
  }>;
}

interface TimetableGridResponse {
  timetable_id: string;
  department_id: string;
  status: string;
  version: string;
  periods_header: PeriodHeader[];
  grid: DayRow[];
  total_sessions: number;
}

interface TimetableMeta {
  id: string;
  department_id: string;
  academic_term_id: string;
  status: string;
  version_major: number;
  version_minor: number;
  lock_version: number;
  name?: string;
  notes?: string;
  created_at: string;
}

interface FormOptions {
  subjects: Array<{ id: string; code: string; name: string; type: string }>;
  teachers: Array<{ id: string; name: string; employee_code: string }>;
  rooms: Array<{ id: string; number: string; capacity: number; type: string }>;
  cohorts: Array<{ id: string; name: string; section_name: string }>;
  time_slots: Array<{
    id: string;
    day_of_week: number;
    period_number: number;
    is_break: boolean;
    start_time: string;
    end_time: string;
  }>;
}

interface DayTimelineItem {
  period_number: number;
  is_break: boolean;
  start_time: string;
  end_time: string;
  session: SessionData | null;
}

const DAYS_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];

export default function TimetableDashboard() {
  const { user } = useAuth();
  const [selectedSection, setSelectedSection] = useState<string>("sec_cs_3a");
  const [gridData, setGridData] = useState<TimetableGridResponse | null>(null);
  const [activeTimetableId, setActiveTimetableId] = useState<string>("");
  const [availableVersions, setAvailableVersions] = useState<TimetableMeta[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [generating, setGenerating] = useState<boolean>(false);
  const [message, setMessage] = useState<{ text: string; type: "success" | "error" | "info" } | null>(null);

  // View state: 'matrix' (University 3-Subrow: Course, Faculty, Room), 'weekly' (Card Grid), or 'daily' (Timeline)
  const [viewMode, setViewMode] = useState<"matrix" | "weekly" | "daily">("matrix");
  const [selectedDayNumber, setSelectedDayNumber] = useState<number>(1);
  const [dayTimeline, setDayTimeline] = useState<DayTimelineItem[]>([]);
  const [dayLoading, setDayLoading] = useState<boolean>(false);
  const [filterMyClasses, setFilterMyClasses] = useState<boolean>(false);
  const [publishing, setPublishing] = useState<boolean>(false);

  // Form options for Add/Edit
  const [formOptions, setFormOptions] = useState<FormOptions | null>(null);

  // Add / Edit Session Modal State
  const [showSessionModal, setShowSessionModal] = useState<boolean>(false);
  const [editingSessionId, setEditingSessionId] = useState<string | null>(null);
  const [sessionSubjectId, setSessionSubjectId] = useState<string>("");
  const [sessionTeacherId, setSessionTeacherId] = useState<string>("");
  const [sessionRoomId, setSessionRoomId] = useState<string>("");
  const [sessionSectionId, setSessionSectionId] = useState<string>("sec_cs_3a");
  const [sessionTimeSlotId, setSessionTimeSlotId] = useState<string>("");
  const [sessionSubmitting, setSessionSubmitting] = useState<boolean>(false);
  const [conflictErrors, setConflictErrors] = useState<string[]>([]);
  const [conflictWarnings, setConflictWarnings] = useState<string[]>([]);
  const [checkingConflict, setCheckingConflict] = useState<boolean>(false);

  // Delete Session Confirmation Modal State
  const [sessionToDelete, setSessionToDelete] = useState<{ id: string; label: string } | null>(null);
  const [deletingSession, setDeletingSession] = useState<boolean>(false);

  // Generation Modal State
  const [showGenModal, setShowGenModal] = useState<boolean>(false);
  const [timeLimit, setTimeLimit] = useState<number>(15);
  const [weightPref, setWeightPref] = useState<number>(10);
  const [weightBalance, setWeightBalance] = useState<number>(15);
  const [weightGaps, setWeightGaps] = useState<number>(10);

  // Rollback Modal State
  const [showRollbackModal, setShowRollbackModal] = useState<boolean>(false);
  const [targetRollbackId, setTargetRollbackId] = useState<string>("");
  const [rollbackReason, setRollbackReason] = useState<string>("");
  const [rollingBack, setRollingBack] = useState<boolean>(false);

  // Edit Mode toggle (enabled by default for authorized HOD/Coordinator)
  const [editMode, setEditMode] = useState<boolean>(true);

  // Timetables can strictly only be edited by HOD, Coordinator, and Admin.
  // Teachers, Class Representatives (CR), and Students have read-only access to published timetables.
  const canManageTimetable = Boolean(user && ["ADMIN", "HOD", "COORDINATOR"].includes(user.role));
  const isFacultyOrAdmin = canManageTimetable && editMode;
  const isHodOrAdmin = Boolean(user && ["ADMIN", "HOD"].includes(user.role));
  const isStudent = user?.role === "STUDENT";
  const isCr = user?.role === "CR";

  const fetchVersions = async () => {
    try {
      const list: TimetableMeta[] = await apiRequest("/timetables?department_id=dept_cs");
      setAvailableVersions(list || []);
      if (list && list.length > 0 && !activeTimetableId) {
        setActiveTimetableId(list[0].id);
      }
    } catch (err) {
      console.error("Failed to load timetable versions", err);
    }
  };

  useEffect(() => {
    fetchVersions();
  }, []);

  const fetchTimetableGrid = async (ttId: string, secId: string) => {
    if (!ttId) return;
    setLoading(true);
    try {
      const data = await apiRequest<TimetableGridResponse>(
        `/timetables/${ttId}/grid?section_id=${secId}`
      );
      setGridData(data);
    } catch (err: any) {
      console.error(err);
      setMessage({ text: err.detail || "Failed to load timetable grid.", type: "error" });
    } finally {
      setLoading(false);
    }
  };

  const fetchDayTimeline = async (ttId: string, dayNum: number, secId: string) => {
    if (!ttId) return;
    setDayLoading(true);
    try {
      const res: any = await apiRequest(
        `/timetables/${ttId}/day/${dayNum}?section_id=${secId}`
      );
      setDayTimeline(res?.timeline || []);
    } catch (err: any) {
      console.error("Failed to load day schedule", err);
    } finally {
      setDayLoading(false);
    }
  };

  const fetchOptions = async (ttId: string) => {
    if (!ttId) return;
    try {
      const opts = await apiRequest<FormOptions>(`/timetables/${ttId}/options`);
      setFormOptions(opts);
      if (opts.subjects.length > 0 && !sessionSubjectId) {
        setSessionSubjectId(opts.subjects[0].id);
      }
      if (opts.teachers.length > 0 && !sessionTeacherId) {
        setSessionTeacherId(opts.teachers[0].id);
      }
      if (opts.rooms.length > 0 && !sessionRoomId) {
        setSessionRoomId(opts.rooms[0].id);
      }
      const validSlots = opts.time_slots.filter((s) => !s.is_break);
      if (validSlots.length > 0 && !sessionTimeSlotId) {
        setSessionTimeSlotId(validSlots[0].id);
      }
    } catch (err) {
      console.error("Failed to load schedule options", err);
    }
  };

  useEffect(() => {
    if (activeTimetableId) {
      fetchTimetableGrid(activeTimetableId, selectedSection);
      if (viewMode === "daily") {
        fetchDayTimeline(activeTimetableId, selectedDayNumber, selectedSection);
      }
      fetchOptions(activeTimetableId);
    }
  }, [activeTimetableId, selectedSection]);

  useEffect(() => {
    if (activeTimetableId && viewMode === "daily") {
      fetchDayTimeline(activeTimetableId, selectedDayNumber, selectedSection);
    }
  }, [selectedDayNumber, viewMode]);

  // Real-time conflict checking when modal values change
  useEffect(() => {
    const runConflictCheck = async () => {
      if (
        !showSessionModal ||
        !activeTimetableId ||
        !sessionTimeSlotId ||
        !sessionTeacherId ||
        !sessionRoomId ||
        !sessionSectionId
      ) {
        return;
      }

      setCheckingConflict(true);
      try {
        const payload: any = {
          timetable_id: activeTimetableId,
          time_slot_id: sessionTimeSlotId,
          teacher_id: sessionTeacherId,
          room_id: sessionRoomId,
          cohort_section_id: sessionSectionId,
          session_id: editingSessionId || undefined,
        };
        const res: any = await apiRequest("/timetables/sessions/check-conflict", {
          method: "POST",
          body: JSON.stringify(payload),
        });
        setConflictErrors(res.conflicts || []);
        setConflictWarnings(res.warnings || []);
      } catch {
        // ignore preflight network issues
      } finally {
        setCheckingConflict(false);
      }
    };

    const debounceTimer = setTimeout(runConflictCheck, 300);
    return () => clearTimeout(debounceTimer);
  }, [
    showSessionModal,
    sessionTimeSlotId,
    sessionTeacherId,
    sessionRoomId,
    sessionSectionId,
    editingSessionId,
    activeTimetableId,
  ]);

  const handleOpenAddSession = async (preselectedSlotId?: string) => {
    if (!canManageTimetable) {
      setMessage({
        text: "Permission denied: Timetables can only be edited by Faculty and HOD. Class Representatives have read-only access.",
        type: "error",
      });
      return;
    }
    setEditingSessionId(null);
    setConflictErrors([]);
    setConflictWarnings([]);
    let opts = formOptions;
    if (!opts && activeTimetableId) {
      try {
        opts = await apiRequest<FormOptions>(`/timetables/${activeTimetableId}/options`);
        setFormOptions(opts);
      } catch (err) {
        console.error("Failed to load options", err);
      }
    }
    if (preselectedSlotId) {
      setSessionTimeSlotId(preselectedSlotId);
    } else if (opts) {
      const validSlots = opts.time_slots.filter((s) => !s.is_break);
      if (validSlots.length > 0) setSessionTimeSlotId(validSlots[0].id);
    }
    if (opts) {
      if (opts.subjects.length > 0) setSessionSubjectId(opts.subjects[0].id);
      if (opts.teachers.length > 0) setSessionTeacherId(opts.teachers[0].id);
      if (opts.rooms.length > 0) setSessionRoomId(opts.rooms[0].id);
    }
    setSessionSectionId(selectedSection);
    setShowSessionModal(true);
  };

  const handleOpenEditSession = async (sess: SessionData, timeSlotId?: string) => {
    if (!canManageTimetable) {
      setMessage({
        text: "Permission denied: Timetables can only be edited by Faculty and HOD. Class Representatives have read-only access.",
        type: "error",
      });
      return;
    }
    setEditingSessionId(sess.session_id);
    setConflictErrors([]);
    setConflictWarnings([]);
    let opts = formOptions;
    if (!opts && activeTimetableId) {
      try {
        opts = await apiRequest<FormOptions>(`/timetables/${activeTimetableId}/options`);
        setFormOptions(opts);
      } catch (err) {
        console.error("Failed to load options", err);
      }
    }
    if (opts) {
      if (sess.subject_id) {
        setSessionSubjectId(sess.subject_id);
      } else {
        const matchedSub = opts.subjects.find((s) => s.code === sess.subject_code || s.name === sess.subject_name);
        if (matchedSub) setSessionSubjectId(matchedSub.id);
      }
      if (sess.teacher_id) setSessionTeacherId(sess.teacher_id);
      if (sess.room_id) setSessionRoomId(sess.room_id);
      if (sess.section_id) setSessionSectionId(sess.section_id);
      else setSessionSectionId(selectedSection);
    }
    const resolvedSlotId = timeSlotId || sess.time_slot_id;
    if (resolvedSlotId) setSessionTimeSlotId(resolvedSlotId);
    setShowSessionModal(true);
  };

  const handleSaveSession = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canManageTimetable) {
      setMessage({
        text: "Permission denied: Timetables can only be edited by Faculty and HOD. Class Representatives have read-only access.",
        type: "error",
      });
      return;
    }
    if (conflictErrors.length > 0) return;

    setSessionSubmitting(true);
    setMessage(null);
    try {
      if (editingSessionId) {
        // Update session
        await apiRequest(`/timetables/${activeTimetableId}/sessions/${editingSessionId}`, {
          method: "PUT",
          body: JSON.stringify({
            subject_id: sessionSubjectId,
            teacher_id: sessionTeacherId,
            room_id: sessionRoomId,
            cohort_section_id: sessionSectionId,
            time_slot_id: sessionTimeSlotId,
          }),
        });
        setMessage({ text: "Schedule entry updated successfully.", type: "success" });
      } else {
        // Create session
        await apiRequest(`/timetables/${activeTimetableId}/sessions`, {
          method: "POST",
          body: JSON.stringify({
            subject_id: sessionSubjectId,
            teacher_id: sessionTeacherId,
            room_id: sessionRoomId,
            cohort_section_id: sessionSectionId,
            time_slot_id: sessionTimeSlotId,
          }),
        });
        setMessage({ text: "Schedule entry created and saved successfully.", type: "success" });
      }

      setShowSessionModal(false);
      await fetchTimetableGrid(activeTimetableId, selectedSection);
      if (viewMode === "daily") {
        await fetchDayTimeline(activeTimetableId, selectedDayNumber, selectedSection);
      }
    } catch (err: any) {
      setMessage({ text: err.detail || "Failed to save schedule session.", type: "error" });
    } finally {
      setSessionSubmitting(false);
    }
  };

  const handleDeleteSessionConfirm = async () => {
    if (!canManageTimetable) {
      setMessage({
        text: "Permission denied: Timetables can only be edited by Faculty and HOD. Class Representatives have read-only access.",
        type: "error",
      });
      return;
    }
    if (!sessionToDelete || !activeTimetableId) return;
    setDeletingSession(true);
    setMessage(null);
    try {
      await apiRequest(`/timetables/${activeTimetableId}/sessions/${sessionToDelete.id}`, {
        method: "DELETE",
      });
      setMessage({ text: "Schedule entry deleted successfully.", type: "success" });
      setSessionToDelete(null);
      await fetchTimetableGrid(activeTimetableId, selectedSection);
      if (viewMode === "daily") {
        await fetchDayTimeline(activeTimetableId, selectedDayNumber, selectedSection);
      }
    } catch (err: any) {
      setMessage({ text: err.detail || "Failed to delete schedule entry.", type: "error" });
    } finally {
      setDeletingSession(false);
    }
  };

  const handleGenerate = async (e: React.FormEvent) => {
    e.preventDefault();
    setGenerating(true);
    setMessage(null);
    try {
      const result: any = await apiRequest("/timetables/generate", {
        method: "POST",
        body: JSON.stringify({
          department_id: "dept_cs",
          academic_term_id: "term_2026_odd",
          time_limit_seconds: timeLimit,
          weight_preferred_times: weightPref,
          weight_balanced_daily_workload: weightBalance,
          weight_minimize_gaps: weightGaps,
          notes: "Generated via Portal UI",
        }),
      });

      if (result.is_valid && result.timetable_id) {
        setActiveTimetableId(result.timetable_id);
        setShowGenModal(false);
        setMessage({
          text: `Timetable successfully generated with ${result.total_sessions_scheduled} sessions (${result.solver_status} in ${result.wall_time_seconds.toFixed(2)}s). Verified by Independent Validator!`,
          type: "success",
        });
        await fetchVersions();
        await fetchTimetableGrid(result.timetable_id, selectedSection);
      } else {
        setMessage({
          text: `Solver reported ${result.solver_status}: ${result.diagnostics?.join(" ") || result.hard_violations?.join(" ")}`,
          type: "error",
        });
      }
    } catch (err: any) {
      setMessage({ text: err.detail || "Failed to generate timetable.", type: "error" });
    } finally {
      setGenerating(false);
    }
  };

  const handlePropose = async () => {
    if (!activeTimetableId) return;
    setMessage(null);
    try {
      const res: any = await apiRequest(`/timetables/${activeTimetableId}/propose`, {
        method: "POST",
      });
      setMessage({ text: res.message, type: "success" });
      await fetchVersions();
    } catch (err: any) {
      setMessage({ text: err.detail || "Failed to propose draft.", type: "error" });
    }
  };

  const handlePublish = async () => {
    if (!activeTimetableId) return;
    setPublishing(true);
    setMessage(null);
    try {
      const res: any = await apiRequest(`/timetables/${activeTimetableId}/publish`, {
        method: "POST",
      });
      setMessage({
        text: res.message || "Timetable verified conflict-free and published successfully!",
        type: "success",
      });
      await fetchVersions();
    } catch (err: any) {
      setMessage({
        text: err.detail || "Publication blocked: unresolvable hard constraints detected.",
        type: "error",
      });
    } finally {
      setPublishing(false);
    }
  };

  const handleRollback = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!targetRollbackId || !rollbackReason) return;
    setRollingBack(true);
    setMessage(null);
    try {
      const res: any = await apiRequest(`/timetables/${activeTimetableId}/rollback`, {
        method: "POST",
        body: JSON.stringify({
          target_version_id: targetRollbackId,
          reason: rollbackReason,
        }),
      });
      setShowRollbackModal(false);
      setMessage({ text: res.message, type: "success" });
      await fetchVersions();
      if (res.id) {
        setActiveTimetableId(res.id);
      }
    } catch (err: any) {
      setMessage({ text: err.detail || "Rollback failed.", type: "error" });
    } finally {
      setRollingBack(false);
    }
  };

  const handleExport = (format: "csv" | "xlsx") => {
    if (!activeTimetableId) return;
    const token = localStorage.getItem("token") || "";
    fetch(
      `http://localhost:8000/api/v1/timetables/${activeTimetableId}/export?export_format=${format}&section_id=${selectedSection}`,
      {
        headers: { Authorization: `Bearer ${token}` },
      }
    )
      .then((res) => res.blob())
      .then((blob) => {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `timetable_${selectedSection}.${format}`;
        document.body.appendChild(a);
        a.click();
        a.remove();
      })
      .catch(() => setMessage({ text: "Export failed.", type: "error" }));
  };

  const handleToggleLock = async (sessionId: string, currentLockedState: boolean) => {
    if (!canManageTimetable) {
      setMessage({
        text: "Permission denied: Timetables can only be locked or unlocked by Faculty and HOD.",
        type: "error",
      });
      return;
    }
    if (!activeTimetableId) return;
    try {
      const res: any = await apiRequest(`/timetables/${activeTimetableId}/sessions/${sessionId}/lock`, {
        method: "PATCH",
        body: JSON.stringify({ is_locked: !currentLockedState }),
      });
      setMessage({
        text: res.message || `Session ${!currentLockedState ? "locked" : "unlocked"}.`,
        type: "success",
      });
      fetchTimetableGrid(activeTimetableId, selectedSection);
    } catch (e: any) {
      setMessage({ text: e.message || "Failed to update session lock.", type: "error" });
    }
  };

  const currentMeta = availableVersions.find((v) => v.id === activeTimetableId);

  return (
    <div className="space-y-6 pb-12">
      {/* Top Header Banner */}
      <div className="bg-white rounded-xl border border-[#E2E7EE] p-5 sm:p-6 shadow-xs flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2">
            <span className="text-xs font-bold uppercase tracking-wider text-[#1261A0] bg-[#EAF3FB] px-2 py-0.5 rounded">
              Academic Timetable Planner
            </span>
            {currentMeta && (
              <span
                className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold ${
                  currentMeta.status === "PUBLISHED"
                    ? "bg-emerald-100 text-emerald-800"
                    : currentMeta.status === "PROPOSED"
                    ? "bg-purple-100 text-purple-800"
                    : currentMeta.status === "ARCHIVED"
                    ? "bg-slate-100 text-slate-700"
                    : "bg-blue-100 text-blue-800"
                }`}
              >
                ● {currentMeta.status} (v{currentMeta.version_major}.{currentMeta.version_minor})
              </span>
            )}
          </div>
          <h1 className="text-xl sm:text-2xl font-bold text-[#17324D] mt-1">
            Department Schedule Matrix & Daily Planner
          </h1>
          <p className="text-xs sm:text-sm text-[#697586] mt-0.5">
            Verified clash-free timetables with multi-day navigation, slot management, and conflict safeguards.
          </p>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          {/* View Mode Toggle: Matrix vs Weekly vs Daily */}
          <div className="inline-flex rounded-lg border border-[#E2E7EE] p-0.5 bg-[#F7F9FC]">
            <button
              onClick={() => setViewMode("matrix")}
              className={`px-3 py-1.5 text-xs font-semibold rounded-md transition-colors ${
                viewMode === "matrix"
                  ? "bg-white text-[#1261A0] shadow-xs font-bold"
                  : "text-slate-600 hover:text-slate-900"
              }`}
            >
              University Matrix (3-Subrow)
            </button>
            <button
              onClick={() => setViewMode("weekly")}
              className={`px-3 py-1.5 text-xs font-semibold rounded-md transition-colors ${
                viewMode === "weekly"
                  ? "bg-white text-[#1261A0] shadow-xs font-bold"
                  : "text-slate-600 hover:text-slate-900"
              }`}
            >
              Card Grid
            </button>
            <button
              onClick={() => setViewMode("daily")}
              className={`px-3 py-1.5 text-xs font-semibold rounded-md transition-colors ${
                viewMode === "daily"
                  ? "bg-white text-[#1261A0] shadow-xs font-bold"
                  : "text-slate-600 hover:text-slate-900"
              }`}
            >
              Daily Timeline
            </button>
          </div>

          {/* Edit Mode Toggle for Faculty/HOD or Read-Only Indicator for CR/Students */}
          {canManageTimetable ? (
            <button
              onClick={() => setEditMode(!editMode)}
              className={`px-3 py-1.5 text-xs font-semibold rounded-lg flex items-center transition-colors border shadow-xs ${
                editMode
                  ? "bg-amber-50 text-amber-900 border-amber-300 font-bold hover:bg-amber-100"
                  : "bg-white text-slate-700 border-[#E2E7EE] hover:bg-slate-50"
              }`}
              title="Toggle Edit Mode to add, modify, or delete timetable sessions"
            >
              <Edit2 className="w-3.5 h-3.5 mr-1.5 text-amber-600" />
              <span>{editMode ? "Edit Mode: ON" : "Edit Mode: OFF"}</span>
            </button>
          ) : (
            <div
              className="px-3 py-1.5 text-xs font-semibold rounded-lg flex items-center bg-slate-100 text-slate-600 border border-slate-200 shadow-2xs"
              title={
                user?.role === "CR"
                  ? "Class Representatives have read-only access. Timetables can only be modified by Faculty and HOD."
                  : "Read-only timetable view"
              }
            >
              <Lock className="w-3.5 h-3.5 mr-1.5 text-slate-500" />
              <span>Read-Only View ({user?.role === "CR" ? "CR" : user?.role || "Student"})</span>
            </div>
          )}

          {/* Add Session Button */}
          {isFacultyOrAdmin && (
            <button
              onClick={() => handleOpenAddSession()}
              className="px-3.5 py-1.5 bg-[#1261A0] text-white hover:bg-[#0E4E82] text-xs font-semibold rounded-lg flex items-center shadow-xs transition-colors"
            >
              <Plus className="w-3.5 h-3.5 mr-1" />
              Add Class Entry
            </button>
          )}

          {isFacultyOrAdmin && (
            <button
              onClick={() => setShowGenModal(true)}
              className="px-3 py-1.5 border border-[#E2E7EE] bg-white text-slate-700 hover:bg-[#EAF3FB] hover:text-[#1261A0] text-xs font-semibold rounded-lg flex items-center transition-colors"
            >
              <Sparkles className="w-3.5 h-3.5 mr-1 text-[#1261A0]" />
              CP-SAT Generator
            </button>
          )}

          <Link
            href="/assistant"
            className="px-3 py-1.5 border border-purple-200 bg-purple-50 text-purple-700 hover:bg-purple-100 text-xs font-semibold rounded-lg flex items-center transition-colors"
          >
            <Bot className="w-3.5 h-3.5 mr-1 text-purple-600" />
            AI Assistant
          </Link>

          <Link
            href="/rescheduler"
            className="px-3 py-1.5 border border-[#E2E7EE] bg-white text-slate-700 hover:bg-[#EAF3FB] hover:text-[#1261A0] text-xs font-semibold rounded-lg flex items-center transition-colors"
          >
            <RefreshCw className="w-3.5 h-3.5 mr-1 text-[#1261A0]" />
            Smart Rescheduler
          </Link>

          <Link
            href="/conflicts"
            className="px-3 py-1.5 border border-[#E2E7EE] bg-white text-slate-700 hover:bg-rose-50 hover:text-rose-700 text-xs font-semibold rounded-lg flex items-center transition-colors"
          >
            <ShieldAlert className="w-3.5 h-3.5 mr-1 text-[#B42332]" />
            Conflict Detector
          </Link>
        </div>
      </div>

      {/* Global Alerts & Toast Messages */}
      {message && (
        <div
          className={`p-4 rounded-xl text-xs border flex items-center justify-between ${
            message.type === "success"
              ? "bg-emerald-50 text-emerald-900 border-emerald-200"
              : message.type === "error"
              ? "bg-rose-50 text-rose-900 border-rose-200"
              : "bg-blue-50 text-blue-900 border-blue-200"
          }`}
        >
          <div className="flex items-center space-x-2">
            {message.type === "success" ? (
              <CheckCircle className="w-4 h-4 text-emerald-600 flex-shrink-0" />
            ) : (
              <AlertCircle className="w-4 h-4 text-rose-600 flex-shrink-0" />
            )}
            <span>{message.text}</span>
          </div>
          <button onClick={() => setMessage(null)} className="font-bold px-2 py-0.5 hover:underline">
            ✕
          </button>
        </div>
      )}

      {/* Control Toolbar: Versions, Cohort Filter, Actions */}
      <div className="bg-white rounded-xl border border-[#E2E7EE] p-4 shadow-xs flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-4 flex-wrap">
          {/* Version Picker */}
          <div className="flex items-center space-x-2">
            <History className="w-4 h-4 text-[#697586]" />
            <label className="text-xs font-semibold text-[#697586] uppercase tracking-wider">
              Version:
            </label>
            <select
              value={activeTimetableId}
              onChange={(e) => setActiveTimetableId(e.target.value)}
              className="text-xs rounded-lg border border-[#E2E7EE] bg-[#F7F9FC] px-2.5 py-1.5 font-semibold text-[#17324D] focus:outline-none focus:ring-1 focus:ring-[#1261A0]"
            >
              {availableVersions.map((v) => (
                <option key={v.id} value={v.id}>
                  v{v.version_major}.{v.version_minor} — {v.status} ({new Date(v.created_at).toLocaleDateString()})
                </option>
              ))}
            </select>
          </div>

          {/* Section Filter */}
          <div className="flex items-center space-x-2">
            <label className="text-xs font-semibold text-[#697586] uppercase tracking-wider">
              Cohort:
            </label>
            {isStudent || isCr ? (
              <span className="px-2.5 py-1 text-xs font-bold rounded-lg bg-slate-100 text-[#1261A0] border border-slate-200 flex items-center shadow-2xs">
                <Lock className="w-3 h-3 mr-1 text-slate-500" /> CS-3A (Assigned Section)
              </span>
            ) : (
              <div className="inline-flex rounded-lg border border-[#E2E7EE] p-0.5 bg-[#F7F9FC]">
                <button
                  onClick={() => setSelectedSection("sec_cs_3a")}
                  className={`px-2.5 py-1 text-xs font-semibold rounded-md transition-colors ${
                    selectedSection === "sec_cs_3a"
                      ? "bg-white text-[#1261A0] shadow-xs font-bold"
                      : "text-slate-600 hover:text-slate-900"
                  }`}
                >
                  CS-3A
                </button>
                <button
                  onClick={() => setSelectedSection("sec_cs_3b")}
                  className={`px-2.5 py-1 text-xs font-semibold rounded-md transition-colors ${
                    selectedSection === "sec_cs_3b"
                      ? "bg-white text-[#1261A0] shadow-xs font-bold"
                      : "text-slate-600 hover:text-slate-900"
                  }`}
                >
                  CS-3B
                </button>
              </div>
            )}
          </div>
          {/* Personal Teacher Filter Toggle */}
          {user?.role === "TEACHER" && (
            <button
              onClick={() => setFilterMyClasses(!filterMyClasses)}
              className={`px-2.5 py-1 text-xs font-semibold rounded-md border transition-colors ${
                filterMyClasses
                  ? "bg-[#1261A0] text-white border-[#1261A0]"
                  : "bg-white text-slate-700 border-[#E2E7EE] hover:bg-slate-50"
              }`}
            >
              {filterMyClasses ? "✓ My Classes Highlighted" : "Highlight My Classes"}
            </button>
          )}
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          {/* HOD / Admin Approve & Publish Button */}
          {isHodOrAdmin && (
            <button
              onClick={handlePublish}
              disabled={publishing}
              className="px-3 py-1.5 text-xs font-semibold bg-[#16805D] hover:bg-emerald-700 text-white rounded-lg shadow-xs transition flex items-center disabled:opacity-50"
            >
              <CheckCircle className="w-3.5 h-3.5 mr-1" />
              {publishing ? "Validating & Publishing..." : "Approve & Publish"}
            </button>
          )}

          {/* Propose Draft Button */}
          {isFacultyOrAdmin && currentMeta?.status === "DRAFT" && (
            <button
              onClick={handlePropose}
              className="px-3 py-1.5 text-xs font-semibold bg-purple-600 hover:bg-purple-700 text-white rounded-lg shadow-xs transition"
            >
              Propose Draft
            </button>
          )}

          {/* Rollback Action for HOD/Admin */}
          {isHodOrAdmin && (
            <button
              onClick={() => {
                const prior = availableVersions.filter((v) => v.id !== activeTimetableId);
                if (prior.length > 0) setTargetRollbackId(prior[0].id);
                setShowRollbackModal(true);
              }}
              className="px-3 py-1.5 text-xs font-semibold border border-amber-300 bg-amber-50 text-amber-800 rounded-lg hover:bg-amber-100 transition flex items-center"
            >
              <RotateCcw className="w-3.5 h-3.5 mr-1" />
              Safe Rollback
            </button>
          )}

          <button
            onClick={() => handleExport("csv")}
            className="px-3 py-1.5 text-xs font-semibold border border-[#E2E7EE] rounded-lg hover:bg-slate-50 text-slate-700 transition"
          >
            Export CSV
          </button>
          <button
            onClick={() => handleExport("xlsx")}
            className="px-3 py-1.5 text-xs font-semibold border border-emerald-300 bg-emerald-50 text-emerald-800 rounded-lg hover:bg-emerald-100 transition"
          >
            Excel (.xlsx)
          </button>
          <button
            onClick={() => window.print()}
            className="px-3 py-1.5 text-xs font-semibold border border-slate-300 bg-white rounded-lg hover:bg-slate-50 text-slate-700 transition flex items-center shadow-xs"
          >
            <Printer className="w-3.5 h-3.5 mr-1 text-slate-500" />
            Print / PDF
          </button>
        </div>
      </div>

      {/* VIEW 0: UNIVERSITY 3-SUBROW MATRIX (COURSE / FACULTY / ROOM) */}
      {viewMode === "matrix" && (
        <div className="bg-white rounded-xl border border-[#E2E7EE] shadow-sm overflow-hidden print:border-none print:shadow-none space-y-0">
          {/* Kristu Jayanti University Institutional Header */}
          <div className="bg-[#17324D] text-white p-5 border-b-4 border-amber-400 print:bg-white print:text-black print:border-b-2 print:border-black">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div>
                <div className="flex items-center space-x-2">
                  <span className="text-[10px] font-extrabold tracking-widest uppercase bg-amber-400 text-slate-900 px-2 py-0.5 rounded">
                    Kristu Jayanti University
                  </span>
                  <span className="text-xs text-amber-200 font-semibold tracking-wider">
                    Autonomous • Bengaluru
                  </span>
                </div>
                <h2 className="text-lg sm:text-xl font-black tracking-tight mt-1">
                  Department of Professional Management Studies
                </h2>
                <div className="text-xs text-slate-300 font-medium mt-0.5">
                  Class Timetable • Academic Year 2026 • Odd Semester (III) • Section {selectedSection === "sec_cs_3a" ? "CS-3A" : "CS-3B"}
                </div>
              </div>

              <div className="text-left sm:text-right text-xs text-slate-300 space-y-1">
                <div><span className="text-slate-400 font-medium">Status:</span> <b className="text-emerald-400 font-bold">{currentMeta?.status || "PUBLISHED"}</b></div>
                <div><span className="text-slate-400 font-medium">Layout:</span> <b>3-Subrow Matrix (Course, Faculty, Room)</b></div>
                <div><span className="text-slate-400 font-medium">Integrity:</span> <b className="text-blue-300">Hard Constraint Clash-Free</b></div>
              </div>
            </div>
          </div>

          {/* 3-Subrow Grid Table */}
          {loading ? (
            <div className="p-16 text-center">
              <div className="inline-block animate-spin rounded-full h-8 w-8 border-4 border-slate-200 border-t-[#1261A0] mb-3"></div>
              <p className="text-sm font-semibold text-[#697586]">Generating institutional 3-subrow schedule matrix...</p>
            </div>
          ) : gridData ? (
            <div className="overflow-x-auto p-4">
              <table className="w-full text-left border-collapse border border-slate-300 text-xs min-w-[900px]">
                <thead>
                  <tr className="bg-[#F7F9FC] border-b-2 border-slate-300 text-[#17324D] font-bold text-center">
                    <th className="p-3 w-28 border border-slate-300 bg-slate-100">Day</th>
                    <th className="p-3 w-20 border border-slate-300 bg-slate-100 text-[11px] uppercase tracking-wider">Field</th>
                    {gridData.periods_header.map((ph) => (
                      <th
                        key={ph.period}
                        className={`p-3 border border-slate-300 text-center ${
                          ph.is_break ? "bg-amber-100/80 text-amber-900 w-28" : "bg-[#F7F9FC]"
                        }`}
                      >
                        <div className="font-extrabold">{ph.label}</div>
                        <div className="text-[10px] text-slate-500 font-normal">
                          {ph.is_break ? "Recess" : `Period ${ph.period}`}
                        </div>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-300">
                  {gridData.grid.map((dayRow, dayIdx) => (
                    <React.Fragment key={dayRow.day_number}>
                      {/* SUBROW 1: COURSE */}
                      <tr className={dayIdx % 2 === 0 ? "bg-white" : "bg-slate-50/40"}>
                        {/* Day Spans all 3 Subrows */}
                        <td
                          rowSpan={3}
                          className="p-3 font-extrabold text-sm text-[#17324D] border border-slate-300 bg-slate-100/90 text-center align-middle"
                        >
                          <div>{dayRow.day_name}</div>
                          <button
                            onClick={() => {
                              setSelectedDayNumber(dayRow.day_number);
                              setViewMode("daily");
                            }}
                            className="text-[10px] text-[#1261A0] hover:underline font-normal mt-1 block mx-auto print:hidden"
                          >
                            Day View &rarr;
                          </button>
                        </td>

                        {/* Field Label: Course */}
                        <td className="p-2.5 font-bold text-[11px] uppercase tracking-wider text-blue-900 bg-blue-50/70 border border-slate-300 text-center align-middle">
                          Course
                        </td>

                        {/* Period Columns for Course */}
                        {dayRow.periods.map((p) => {
                          const sess = p.session;
                          if (p.is_break) {
                            return (
                              <td
                                key={p.period_number}
                                rowSpan={3}
                                className="p-2 border border-slate-300 bg-amber-50 text-center align-middle font-bold text-amber-900 text-xs tracking-wider"
                              >
                                <div className="uppercase py-2 font-extrabold">
                                  LUNCH BREAK
                                </div>
                              </td>
                            );
                          }
                          const isMyClass = sess && user?.full_name && sess.teacher_name?.toLowerCase().includes(user.full_name.toLowerCase().split(" ")[1] || "");
                          return (
                            <td
                              key={p.period_number}
                              className={`p-2.5 border border-slate-300 text-center align-middle ${
                                filterMyClasses && isMyClass ? "bg-blue-100/60 ring-1 ring-blue-500 font-bold" : ""
                              }`}
                            >
                              {sess ? (
                                <div>
                                  <span className="font-bold text-[#1261A0] block text-xs">
                                    {sess.subject_code}
                                  </span>
                                  <span className="text-[11px] text-[#17324D] font-medium line-clamp-1">
                                    {sess.subject_name}
                                  </span>
                                  {sess.is_locked && (
                                    <span className="inline-flex items-center text-[9px] font-bold text-amber-700 bg-amber-100 px-1 rounded mt-0.5">
                                      <Lock className="w-2.5 h-2.5 mr-0.5" /> Locked
                                    </span>
                                  )}
                                </div>
                              ) : (
                                <span className="text-slate-300 font-medium">—</span>
                              )}
                            </td>
                          );
                        })}
                      </tr>

                      {/* SUBROW 2: FACULTY */}
                      <tr className={dayIdx % 2 === 0 ? "bg-white" : "bg-slate-50/40"}>
                        <td className="p-2.5 font-bold text-[11px] uppercase tracking-wider text-emerald-900 bg-emerald-50/70 border border-slate-300 text-center align-middle">
                          Faculty
                        </td>
                        {dayRow.periods.map((p) => {
                          if (p.is_break) return null; // Already spanned by rowSpan=3 from Subrow 1
                          const sess = p.session;
                          return (
                            <td
                              key={p.period_number}
                              className="p-2.5 border border-slate-300 text-center align-middle text-xs text-slate-800 font-medium"
                            >
                              {sess ? (
                                <div className="flex items-center justify-center space-x-1">
                                  <UserCheck className="w-3 h-3 text-emerald-600 shrink-0" />
                                  <span className="truncate">{sess.teacher_name}</span>
                                </div>
                              ) : (
                                <span className="text-slate-300 font-medium">—</span>
                              )}
                            </td>
                          );
                        })}
                      </tr>

                      {/* SUBROW 3: ROOM */}
                      <tr className={dayIdx % 2 === 0 ? "bg-white" : "bg-slate-50/40"}>
                        <td className="p-2.5 font-bold text-[11px] uppercase tracking-wider text-purple-900 bg-purple-50/70 border border-slate-300 text-center align-middle">
                          Room
                        </td>
                        {dayRow.periods.map((p) => {
                          if (p.is_break) return null; // Already spanned by rowSpan=3 from Subrow 1
                          const sess = p.session;
                          return (
                            <td
                              key={p.period_number}
                              className="p-2.5 border border-slate-300 text-center align-middle text-xs text-slate-700"
                            >
                              {sess ? (
                                <div className="flex items-center justify-center space-x-1">
                                  <MapPin className="w-3 h-3 text-purple-600 shrink-0" />
                                  <span className="font-semibold text-[#17324D]">{sess.room_name}</span>
                                  <span className="text-[10px] text-slate-400">({sess.room_type || "LH"})</span>
                                </div>
                              ) : (
                                <span className="text-slate-300 font-medium">—</span>
                              )}
                            </td>
                          );
                        })}
                      </tr>
                    </React.Fragment>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="p-12 text-center">
              <Calendar className="w-8 h-8 text-[#697586] mx-auto mb-2" />
              <h4 className="text-sm font-bold text-[#17324D]">No Timetable Sessions Found</h4>
            </div>
          )}
        </div>
      )}

      {/* VIEW 1: WEEKLY 2D MATRIX GRID */}
      {viewMode === "weekly" && (
        <>
          {loading ? (
            <div className="bg-white rounded-xl border border-[#E2E7EE] p-16 text-center shadow-xs">
              <div className="inline-block animate-spin rounded-full h-8 w-8 border-4 border-slate-200 border-t-[#1261A0] mb-3"></div>
              <p className="text-sm font-semibold text-[#697586]">Loading weekly schedule matrix...</p>
            </div>
          ) : gridData ? (
            <div className="bg-white rounded-xl border border-[#E2E7EE] shadow-xs overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse min-w-[850px]">
                  <thead>
                    <tr className="bg-[#F7F9FC] border-b border-[#E2E7EE] text-xs font-bold text-[#17324D]">
                      <th className="py-3 px-4 w-32 border-r border-[#E2E7EE]">Day / Period</th>
                      {gridData.periods_header.map((ph) => (
                        <th
                          key={ph.period}
                          className={`py-3 px-3 text-center border-r border-[#E2E7EE] last:border-r-0 ${
                            ph.is_break ? "bg-amber-50/60 text-amber-900 w-28" : ""
                          }`}
                        >
                          <div>{ph.label}</div>
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#E2E7EE] text-xs">
                    {gridData.grid.map((dayRow) => (
                      <tr key={dayRow.day_number} className="hover:bg-slate-50/50">
                        <td className="py-4 px-4 font-bold text-[#17324D] border-r border-[#E2E7EE] bg-[#F7F9FC]">
                          <div className="flex items-center justify-between">
                            <span>{dayRow.day_name}</span>
                            <button
                              onClick={() => {
                                setSelectedDayNumber(dayRow.day_number);
                                setViewMode("daily");
                              }}
                              className="text-[10px] text-[#1261A0] hover:underline font-normal"
                              title="Switch to detailed Day View"
                            >
                              Day &rarr;
                            </button>
                          </div>
                        </td>
                        {dayRow.periods.map((p) => {
                          const sess = p.session;
                          if (p.is_break) {
                            return (
                              <td
                                key={p.period_number}
                                className="py-4 px-2 text-center border-r border-[#E2E7EE] bg-amber-50/30 text-amber-800 font-medium"
                              >
                                Recess Interval
                              </td>
                            );
                          }
                          const isMyClass = sess && user?.full_name && sess.teacher_name?.toLowerCase().includes(user.full_name.toLowerCase().split(" ")[1] || "");
                          const cardClasses = filterMyClasses
                            ? isMyClass
                              ? "bg-blue-50/95 border-[#1261A0] ring-2 ring-[#1261A0]/40 shadow-sm"
                              : "opacity-35 bg-slate-50 border-slate-200"
                            : "bg-white hover:border-[#1261A0]";

                          return (
                            <td
                              key={p.period_number}
                              className="py-2.5 px-2.5 border-r border-[#E2E7EE] last:border-r-0 align-top relative group"
                            >
                              {sess ? (
                                <div className={`h-full p-2.5 rounded-lg border transition-colors flex flex-col justify-between shadow-xs ${cardClasses}`}>
                                  <div>
                                    <div className="flex items-center justify-between gap-1 mb-1">
                                      <div className="flex items-center space-x-1">
                                        <span className="font-bold text-[#1261A0]">
                                          {sess.subject_code}
                                        </span>
                                        {isMyClass && (
                                          <span className="text-[8px] font-bold px-1 py-0.2 rounded bg-blue-200 text-blue-900">
                                            MINE
                                          </span>
                                        )}
                                      </div>
                                      <div className="flex items-center space-x-1">
                                        <span
                                          className={`text-[9px] px-1 py-0.2 rounded font-semibold ${
                                            sess.subject_type === "LAB"
                                              ? "bg-purple-100 text-purple-800"
                                              : "bg-blue-100 text-blue-800"
                                          }`}
                                        >
                                          {sess.subject_type}
                                        </span>
                                        {sess.is_locked && (
                                          <span className="inline-flex items-center space-x-0.5 text-[8px] font-bold px-1.5 py-0.5 rounded bg-amber-100 text-amber-900 border border-amber-300">
                                            <Lock className="w-2.5 h-2.5 mr-0.5" />
                                            <span>LOCKED</span>
                                          </span>
                                        )}
                                      </div>
                                    </div>
                                    <div className="text-[11px] font-semibold text-[#17324D] line-clamp-1">
                                      {sess.subject_name}
                                    </div>
                                    <div className="text-[10px] text-[#697586] mt-1 flex items-center">
                                      <UserCheck className="w-3 h-3 mr-1 text-[#1261A0]" />
                                      <span className="truncate">{sess.teacher_name}</span>
                                    </div>
                                    <div className="text-[10px] text-[#697586] flex items-center mt-0.5">
                                      <MapPin className="w-3 h-3 mr-1 text-slate-400" />
                                      <span className="truncate">{sess.room_name}</span>
                                    </div>
                                  </div>

                                  {/* Authorized Actions */}
                                  {isFacultyOrAdmin && (
                                    <div className="mt-2 pt-1 border-t border-slate-100 flex items-center justify-between">
                                      <span className="text-[9px] font-bold text-slate-400">
                                        P{p.period_number}
                                      </span>
                                      <div className="flex items-center space-x-1">
                                        <button
                                          onClick={() => handleToggleLock(sess.session_id, !!sess.is_locked)}
                                          className={`p-1 rounded transition-colors ${
                                            sess.is_locked
                                              ? "text-amber-700 bg-amber-50 hover:bg-amber-100"
                                              : "text-slate-400 hover:text-slate-700 hover:bg-slate-100"
                                          }`}
                                          title={sess.is_locked ? "Click to unlock session" : "Click to lock session"}
                                        >
                                          {sess.is_locked ? (
                                            <Lock className="w-3 h-3 text-amber-600" />
                                          ) : (
                                            <Unlock className="w-3 h-3 text-slate-400" />
                                          )}
                                        </button>
                                        <button
                                          onClick={() =>
                                            handleOpenEditSession(
                                              sess,
                                              `ts_d${dayRow.day_number}_p${p.period_number}`
                                            )
                                          }
                                          className="p-1 text-slate-500 hover:text-white hover:bg-[#1261A0] rounded transition-colors"
                                          title="Edit this class session"
                                        >
                                          <Edit2 className="w-3 h-3" />
                                        </button>
                                        <button
                                          onClick={() =>
                                            setSessionToDelete({
                                              id: sess.session_id,
                                              label: `${sess.subject_code} — ${sess.subject_name} (${dayRow.day_name} P${p.period_number})`,
                                            })
                                          }
                                          className="p-1 text-slate-500 hover:text-white hover:bg-rose-600 rounded transition-colors"
                                          title="Delete this class session"
                                        >
                                          <Trash2 className="w-3 h-3" />
                                        </button>
                                      </div>
                                    </div>
                                  )}
                                </div>
                              ) : (
                                <div className="h-full min-h-[92px] rounded-lg border border-dashed border-slate-200 bg-slate-50/50 p-2 flex flex-col items-center justify-center text-slate-400 hover:border-[#1261A0]/40 transition-colors">
                                  <span className="text-[10px] font-medium text-slate-400">Free Period</span>
                                  {isFacultyOrAdmin && (
                                    <button
                                      onClick={() =>
                                        handleOpenAddSession(
                                          `ts_d${dayRow.day_number}_p${p.period_number}`
                                        )
                                      }
                                      className="mt-1.5 px-2.5 py-1 text-[11px] font-semibold text-[#1261A0] bg-[#EAF3FB] hover:bg-[#1261A0] hover:text-white rounded-md flex items-center transition border border-blue-200 shadow-2xs"
                                      title="Add a class entry to this time slot"
                                    >
                                      <Plus className="w-3 h-3 mr-0.5" /> Add Class
                                    </button>
                                  )}
                                </div>
                              )}
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ) : (
            <div className="bg-white rounded-xl border border-[#E2E7EE] p-12 text-center">
              <Calendar className="w-8 h-8 text-[#697586] mx-auto mb-2" />
              <h4 className="text-sm font-bold text-[#17324D]">No Timetable Sessions Found</h4>
              <p className="text-xs text-[#697586] mt-1">
                Select another version or click &ldquo;+ Add Class Entry&rdquo; to create a schedule entry.
              </p>
            </div>
          )}
        </>
      )}

      {/* VIEW 2: DAILY TIMELINE VIEW WITH DAY NAVIGATION */}
      {viewMode === "daily" && (
        <div className="space-y-4">
          {/* Day Navigation Bar */}
          <div className="bg-white rounded-xl border border-[#E2E7EE] p-3 shadow-xs flex items-center justify-between gap-2">
            <button
              onClick={() => setSelectedDayNumber((prev) => Math.max(1, prev - 1))}
              disabled={selectedDayNumber <= 1}
              className="p-2 rounded-lg border border-[#E2E7EE] hover:bg-slate-50 text-slate-600 disabled:opacity-30 disabled:pointer-events-none"
              title="Previous Day"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>

            <div className="flex items-center space-x-1 sm:space-x-2 overflow-x-auto">
              {[1, 2, 3, 4, 5, 6].map((dayNum) => (
                <button
                  key={dayNum}
                  onClick={() => setSelectedDayNumber(dayNum)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors ${
                    selectedDayNumber === dayNum
                      ? "bg-[#1261A0] text-white shadow-xs"
                      : "bg-[#F7F9FC] text-slate-600 hover:bg-[#EAF3FB] hover:text-[#1261A0]"
                  }`}
                >
                  {DAYS_NAMES[dayNum - 1]}
                </button>
              ))}
            </div>

            <button
              onClick={() => setSelectedDayNumber((prev) => Math.min(6, prev + 1))}
              disabled={selectedDayNumber >= 6}
              className="p-2 rounded-lg border border-[#E2E7EE] hover:bg-slate-50 text-slate-600 disabled:opacity-30 disabled:pointer-events-none"
              title="Next Day"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>

          {/* Daily Schedule Timeline Cards */}
          {dayLoading ? (
            <div className="bg-white rounded-xl border border-[#E2E7EE] p-16 text-center">
              <div className="inline-block animate-spin rounded-full h-8 w-8 border-4 border-slate-200 border-t-[#1261A0] mb-3"></div>
              <p className="text-sm font-semibold text-[#697586]">
                Loading {DAYS_NAMES[selectedDayNumber - 1]} schedule...
              </p>
            </div>
          ) : dayTimeline.length > 0 ? (
            <div className="space-y-3">
              {dayTimeline.map((item) => {
                const sess = item.session;
                if (item.is_break) {
                  return (
                    <div
                      key={item.period_number}
                      className="p-3.5 bg-amber-50/70 border border-amber-200 rounded-xl flex items-center justify-between text-xs text-amber-900"
                    >
                      <div className="flex items-center space-x-3">
                        <span className="font-bold bg-amber-100 text-amber-800 px-2 py-0.5 rounded text-[11px]">
                          PERIOD {item.period_number}
                        </span>
                        <span className="text-amber-800 font-semibold">
                          {item.start_time || "11:45"} - {item.end_time || "12:45"}
                        </span>
                        <span>•</span>
                        <span className="font-medium">Scheduled Recess / Lunch Break</span>
                      </div>
                      <span className="text-[11px] text-amber-700 font-medium">Campus Dining Open</span>
                    </div>
                  );
                }

                if (sess) {
                  return (
                    <div
                      key={item.period_number}
                      className="bg-white rounded-xl border border-[#E2E7EE] p-4 shadow-xs hover:border-[#1261A0] transition-colors flex flex-wrap items-center justify-between gap-4"
                    >
                      <div className="flex items-start space-x-4">
                        <div className="text-center min-w-[70px] border-r border-[#E2E7EE] pr-4">
                          <span className="text-[10px] font-bold uppercase text-[#697586] block">
                            Period {item.period_number}
                          </span>
                          <span className="text-xs font-bold text-[#17324D] mt-0.5 block">
                            {item.start_time || "08:30"}
                          </span>
                          <span className="text-[10px] text-[#697586] block">
                            {item.end_time || "09:30"}
                          </span>
                        </div>

                        <div>
                          <div className="flex items-center space-x-2">
                            <span className="text-xs font-bold text-[#1261A0] bg-[#EAF3FB] px-2 py-0.5 rounded">
                              {sess.subject_code}
                            </span>
                            <span
                              className={`text-[10px] px-1.5 py-0.5 rounded font-semibold ${
                                sess.subject_type === "LAB"
                                  ? "bg-purple-100 text-purple-800"
                                  : "bg-blue-100 text-blue-800"
                              }`}
                            >
                              {sess.subject_type}
                            </span>
                            <span className="text-xs text-slate-400">•</span>
                            <span className="text-xs font-semibold text-slate-700">
                              Section {sess.section_name || selectedSection}
                            </span>
                          </div>

                          <h3 className="text-base font-bold text-[#17324D] mt-1">
                            {sess.subject_name}
                          </h3>

                          <div className="mt-2 flex items-center space-x-4 text-xs text-[#697586]">
                            <span className="flex items-center">
                              <UserCheck className="w-3.5 h-3.5 mr-1 text-[#1261A0]" />
                              {sess.teacher_name}
                            </span>
                            <span>•</span>
                            <span className="flex items-center">
                              <MapPin className="w-3.5 h-3.5 mr-1 text-[#1261A0]" />
                              {sess.room_name}
                            </span>
                          </div>
                        </div>
                      </div>

                      {/* Authorized Actions */}
                      {isFacultyOrAdmin && (
                        <div className="flex items-center space-x-2">
                          <button
                            onClick={() =>
                              handleOpenEditSession(
                                sess,
                                `ts_d${selectedDayNumber}_p${item.period_number}`
                              )
                            }
                            className="px-3 py-1.5 text-xs font-semibold border border-[#E2E7EE] text-slate-700 hover:bg-[#EAF3FB] hover:text-[#1261A0] rounded-lg transition"
                          >
                            Edit Entry
                          </button>
                          <button
                            onClick={() =>
                              setSessionToDelete({
                                id: sess.session_id,
                                label: `${sess.subject_code} (Period ${item.period_number})`,
                              })
                            }
                            className="px-3 py-1.5 text-xs font-semibold border border-rose-200 text-rose-700 hover:bg-rose-50 rounded-lg transition"
                          >
                            Delete
                          </button>
                        </div>
                      )}
                    </div>
                  );
                }

                // Free Slot
                return (
                  <div
                    key={item.period_number}
                    className="p-4 bg-white rounded-xl border border-dashed border-[#E2E7EE] flex items-center justify-between text-xs text-slate-500"
                  >
                    <div className="flex items-center space-x-4">
                      <div className="text-center min-w-[70px] border-r border-[#E2E7EE] pr-4">
                        <span className="text-[10px] font-bold uppercase text-[#697586] block">
                          Period {item.period_number}
                        </span>
                        <span className="text-xs font-bold text-[#17324D] mt-0.5 block">
                          {item.start_time || "08:30"}
                        </span>
                        <span className="text-[10px] text-[#697586] block">
                          {item.end_time || "09:30"}
                        </span>
                      </div>
                      <div>
                        <span className="font-semibold text-slate-600 block">Open Free Period</span>
                        <span className="text-[11px] text-[#697586]">
                          No academic lectures or laboratories scheduled in this slot.
                        </span>
                      </div>
                    </div>

                    {isFacultyOrAdmin && (
                      <button
                        onClick={() =>
                          handleOpenAddSession(`ts_d${selectedDayNumber}_p${item.period_number}`)
                        }
                        className="px-3 py-1.5 bg-[#EAF3FB] text-[#1261A0] hover:bg-blue-100 text-xs font-semibold rounded-lg flex items-center transition"
                      >
                        <Plus className="w-3.5 h-3.5 mr-1" />
                        Schedule Class
                      </button>
                    )}
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="bg-white rounded-xl border border-[#E2E7EE] p-12 text-center">
              <Calendar className="w-8 h-8 text-[#697586] mx-auto mb-2" />
              <h4 className="text-sm font-bold text-[#17324D]">No Schedule for This Day</h4>
            </div>
          )}
        </div>
      )}

      {/* ========================================================= */}
      {/* ADD / EDIT SCHEDULE ENTRY MODAL WITH CONFLICT SAFEGUARD   */}
      {/* ========================================================= */}
      {showSessionModal && formOptions && (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-lg w-full p-6">
            <div className="flex items-center justify-between pb-3 border-b border-[#E2E7EE]">
              <div>
                <h3 className="font-bold text-base text-[#17324D]">
                  {editingSessionId ? "Edit Schedule Entry" : "Create Schedule Entry"}
                </h3>
                <p className="text-xs text-[#697586]">
                  {editingSessionId
                    ? "Modify classroom, faculty, or time slot with conflict re-validation."
                    : "Add an academic class with real-time room, instructor, and cohort clash check."}
                </p>
              </div>
              <button
                onClick={() => setShowSessionModal(false)}
                className="text-slate-400 hover:text-slate-600 p-1 rounded"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Conflict & Preflight Warning Banners */}
            {conflictErrors.length > 0 && (
              <div className="mt-4 p-3 bg-rose-50 border border-rose-200 rounded-lg text-xs text-rose-800 space-y-1">
                <div className="font-bold flex items-center text-rose-900">
                  <AlertCircle className="w-4 h-4 mr-1.5 flex-shrink-0" />
                  Scheduling Conflict Detected:
                </div>
                {conflictErrors.map((err, idx) => (
                  <div key={idx} className="pl-5 text-[11px] leading-tight">
                    • {err}
                  </div>
                ))}
              </div>
            )}

            {conflictWarnings.length > 0 && (
              <div className="mt-3 p-3 bg-amber-50 border border-amber-200 rounded-lg text-xs text-amber-800 space-y-1">
                <div className="font-bold flex items-center text-amber-900">
                  <AlertTriangle className="w-4 h-4 mr-1.5 flex-shrink-0" />
                  Capacity Warning:
                </div>
                {conflictWarnings.map((warn, idx) => (
                  <div key={idx} className="pl-5 text-[11px] leading-tight">
                    • {warn}
                  </div>
                ))}
              </div>
            )}

            <form onSubmit={handleSaveSession} className="mt-4 space-y-4">
              {/* Subject */}
              <div>
                <label className="text-xs font-semibold text-slate-700 block mb-1">
                  Subject Course:
                </label>
                <select
                  required
                  value={sessionSubjectId}
                  onChange={(e) => setSessionSubjectId(e.target.value)}
                  className="w-full text-xs rounded-lg border border-[#E2E7EE] bg-white p-2.5 text-[#17324D] focus:ring-1 focus:ring-[#1261A0]"
                >
                  {formOptions.subjects.map((sub) => (
                    <option key={sub.id} value={sub.id}>
                      {sub.code} — {sub.name} ({sub.type})
                    </option>
                  ))}
                </select>
              </div>

              {/* Faculty Teacher */}
              <div>
                <label className="text-xs font-semibold text-slate-700 block mb-1">
                  Faculty Instructor:
                </label>
                <select
                  required
                  value={sessionTeacherId}
                  onChange={(e) => setSessionTeacherId(e.target.value)}
                  className="w-full text-xs rounded-lg border border-[#E2E7EE] bg-white p-2.5 text-[#17324D] focus:ring-1 focus:ring-[#1261A0]"
                >
                  {formOptions.teachers.map((tch) => (
                    <option key={tch.id} value={tch.id}>
                      {tch.name} ({tch.employee_code})
                    </option>
                  ))}
                </select>
              </div>

              {/* Room & Seating */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-semibold text-slate-700 block mb-1">
                    Room / Lab:
                  </label>
                  <select
                    required
                    value={sessionRoomId}
                    onChange={(e) => setSessionRoomId(e.target.value)}
                    className="w-full text-xs rounded-lg border border-[#E2E7EE] bg-white p-2.5 text-[#17324D] focus:ring-1 focus:ring-[#1261A0]"
                  >
                    {formOptions.rooms.map((rm) => (
                      <option key={rm.id} value={rm.id}>
                        {rm.number} (Cap {rm.capacity})
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="text-xs font-semibold text-slate-700 block mb-1">
                    Cohort Section:
                  </label>
                  <select
                    required
                    value={sessionSectionId}
                    onChange={(e) => setSessionSectionId(e.target.value)}
                    className="w-full text-xs rounded-lg border border-[#E2E7EE] bg-white p-2.5 text-[#17324D] focus:ring-1 focus:ring-[#1261A0]"
                  >
                    {formOptions.cohorts.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Day & Period Time Slot */}
              <div>
                <label className="text-xs font-semibold text-slate-700 block mb-1">
                  Day & Time Slot:
                </label>
                <select
                  required
                  value={sessionTimeSlotId}
                  onChange={(e) => setSessionTimeSlotId(e.target.value)}
                  className="w-full text-xs rounded-lg border border-[#E2E7EE] bg-white p-2.5 text-[#17324D] focus:ring-1 focus:ring-[#1261A0]"
                >
                  {formOptions.time_slots
                    .filter((sl) => !sl.is_break)
                    .map((sl) => (
                      <option key={sl.id} value={sl.id}>
                        {DAYS_NAMES[sl.day_of_week - 1]} • Period {sl.period_number} (
                        {sl.start_time || "08:30"} - {sl.end_time || "09:30"})
                      </option>
                    ))}
                </select>
              </div>

              <div className="flex items-center justify-between pt-3 border-t border-[#E2E7EE]">
                {editingSessionId ? (
                  <button
                    type="button"
                    onClick={() => {
                      const matchedSub = formOptions.subjects.find((s) => s.id === sessionSubjectId);
                      setSessionToDelete({
                        id: editingSessionId,
                        label: `${matchedSub?.code || "Session"} (${sessionSectionId})`,
                      });
                      setShowSessionModal(false);
                    }}
                    className="px-3.5 py-2 bg-rose-50 hover:bg-rose-100 text-rose-700 text-xs font-semibold rounded-lg flex items-center transition border border-rose-200"
                    title="Delete this session from timetable"
                  >
                    <Trash2 className="w-3.5 h-3.5 mr-1 text-rose-600" />
                    Delete Session
                  </button>
                ) : (
                  <div />
                )}
                <div className="flex items-center space-x-2">
                  <button
                    type="button"
                    onClick={() => setShowSessionModal(false)}
                    className="px-4 py-2 border border-[#E2E7EE] text-xs font-semibold rounded-lg text-slate-600 hover:bg-slate-50"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={sessionSubmitting || conflictErrors.length > 0}
                    className="px-4 py-2 bg-[#1261A0] hover:bg-[#0E4E82] text-white text-xs font-semibold rounded-lg transition disabled:opacity-50"
                  >
                    {sessionSubmitting
                      ? "Validating & Saving..."
                      : editingSessionId
                      ? "Update Schedule Entry"
                      : "Add Schedule Entry"}
                  </button>
                </div>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ========================================================= */}
      {/* DELETE CONFIRMATION MODAL                                 */}
      {/* ========================================================= */}
      {sessionToDelete && (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-md w-full p-6">
            <h3 className="font-bold text-base text-[#17324D] mb-1">Confirm Session Removal</h3>
            <p className="text-xs text-[#697586] mb-4">
              Are you sure you want to remove <b>{sessionToDelete.label}</b> from the timetable?
              This period will become an open free slot.
            </p>

            <div className="flex items-center justify-end space-x-2">
              <button
                type="button"
                onClick={() => setSessionToDelete(null)}
                className="px-4 py-2 border border-[#E2E7EE] text-xs font-semibold rounded-lg text-slate-600 hover:bg-slate-50"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={deletingSession}
                onClick={handleDeleteSessionConfirm}
                className="px-4 py-2 bg-[#B42332] hover:bg-rose-700 text-white text-xs font-semibold rounded-lg transition disabled:opacity-50"
              >
                {deletingSession ? "Removing..." : "Delete Entry"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ========================================================= */}
      {/* ROLLBACK MODAL                                            */}
      {/* ========================================================= */}
      {showRollbackModal && (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-md w-full p-6">
            <h3 className="font-bold text-base text-[#17324D] mb-1 flex items-center">
              <RotateCcw className="w-4 h-4 mr-2 text-amber-600" />
              Safe Rollback to Prior Version
            </h3>
            <p className="text-xs text-slate-500 mb-4">
              Restores an audited prior timetable version non-destructively.
            </p>

            <form onSubmit={handleRollback} className="space-y-4">
              <div>
                <label className="text-xs font-semibold text-slate-700 block mb-1">
                  Target Prior Version:
                </label>
                <select
                  value={targetRollbackId}
                  onChange={(e) => setTargetRollbackId(e.target.value)}
                  className="w-full text-xs rounded-lg border border-[#E2E7EE] bg-white p-2.5 text-[#17324D]"
                >
                  {availableVersions
                    .filter((v) => v.id !== activeTimetableId)
                    .map((v) => (
                      <option key={v.id} value={v.id}>
                        v{v.version_major}.{v.version_minor} ({v.status}) — {new Date(v.created_at).toLocaleDateString()}
                      </option>
                    ))}
                </select>
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-700 block mb-1">
                  Mandatory Audit Reason:
                </label>
                <textarea
                  rows={3}
                  required
                  value={rollbackReason}
                  onChange={(e) => setRollbackReason(e.target.value)}
                  className="w-full text-xs rounded-lg border border-[#E2E7EE] bg-white p-3 text-slate-800"
                  placeholder="Record formal reason for restoration..."
                />
              </div>

              <div className="flex items-center justify-end space-x-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowRollbackModal(false)}
                  className="px-4 py-2 border border-[#E2E7EE] text-xs font-semibold rounded-lg text-slate-600 hover:bg-slate-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={rollingBack}
                  className="px-4 py-2 bg-amber-600 hover:bg-amber-700 text-white text-xs font-semibold rounded-lg transition"
                >
                  {rollingBack ? "Restoring..." : "Restore Prior Version"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ========================================================= */}
      {/* GENERATE VIA OR-TOOLS CP-SAT MODAL                        */}
      {/* ========================================================= */}
      {showGenModal && (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-lg w-full p-6">
            <h3 className="font-bold text-base text-[#17324D] mb-1 flex items-center">
              <Sparkles className="w-4 h-4 mr-2 text-[#1261A0]" />
              Generate Timetable via Google OR-Tools CP-SAT
            </h3>
            <p className="text-xs text-slate-500 mb-4">
              Solves college scheduling under strict hard constraints and soft trade-off weights.
            </p>

            <form onSubmit={handleGenerate} className="space-y-4">
              <div>
                <label className="text-xs font-semibold text-slate-700 block mb-1">
                  Department & Academic Term:
                </label>
                <div className="p-2.5 bg-slate-50 rounded-lg border border-slate-200 text-xs font-medium text-slate-600">
                  Computer Science Department (dept_cs) — Academic Term 2026 Odd
                </div>
              </div>

              <div>
                <div className="flex justify-between items-center mb-1">
                  <label className="text-xs font-semibold text-slate-700">
                    Max Solver Wall-Time Limit:
                  </label>
                  <span className="text-xs font-bold text-[#1261A0]">{timeLimit}s</span>
                </div>
                <input
                  type="range"
                  min="5"
                  max="60"
                  step="5"
                  value={timeLimit}
                  onChange={(e) => setTimeLimit(Number(e.target.value))}
                  className="w-full accent-[#1261A0]"
                />
              </div>

              <div className="border-t pt-3">
                <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider block mb-2">
                  Configurable Soft Preference Weights
                </span>

                <div className="space-y-3">
                  <div>
                    <div className="flex justify-between items-center text-xs mb-1">
                      <span className="text-slate-600">Faculty Preferred Time Slots:</span>
                      <span className="font-bold text-[#1261A0]">{weightPref}</span>
                    </div>
                    <input
                      type="range"
                      min="0"
                      max="30"
                      value={weightPref}
                      onChange={(e) => setWeightPref(Number(e.target.value))}
                      className="w-full accent-[#1261A0]"
                    />
                  </div>

                  <div>
                    <div className="flex justify-between items-center text-xs mb-1">
                      <span className="text-slate-600">Balanced Daily Workload:</span>
                      <span className="font-bold text-[#1261A0]">{weightBalance}</span>
                    </div>
                    <input
                      type="range"
                      min="0"
                      max="30"
                      value={weightBalance}
                      onChange={(e) => setWeightBalance(Number(e.target.value))}
                      className="w-full accent-[#1261A0]"
                    />
                  </div>

                  <div>
                    <div className="flex justify-between items-center text-xs mb-1">
                      <span className="text-slate-600">Minimizing Idle Gaps:</span>
                      <span className="font-bold text-[#1261A0]">{weightGaps}</span>
                    </div>
                    <input
                      type="range"
                      min="0"
                      max="30"
                      value={weightGaps}
                      onChange={(e) => setWeightGaps(Number(e.target.value))}
                      className="w-full accent-[#1261A0]"
                    />
                  </div>
                </div>
              </div>

              <div className="border-t pt-4 flex items-center justify-end gap-3">
                <button
                  type="button"
                  onClick={() => setShowGenModal(false)}
                  className="px-4 py-2 border border-slate-200 text-xs font-semibold rounded-lg text-slate-600 hover:bg-slate-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={generating}
                  className="px-4 py-2 bg-[#1261A0] text-white text-xs font-semibold rounded-lg hover:bg-[#0e4d80] transition disabled:opacity-50"
                >
                  {generating ? "Solving with OR-Tools..." : "Start Solver & Validate"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
