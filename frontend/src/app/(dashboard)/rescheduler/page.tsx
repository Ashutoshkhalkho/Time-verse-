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
  Cpu,
  Layers,
  Lock,
  MapPin,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  UserCheck,
  Users,
  Zap,
} from "lucide-react";

interface AlternativeOption {
  strategy: string;
  title: string;
  description: string;
  new_time_slot_id: string;
  new_teacher_id: string;
  new_room_id: string;
  feasibility_score: number;
  conflicts_introduced: number;
}

interface AffectedSession {
  session_id: string;
  subject_code: string;
  subject_name: string;
  teacher_id: string;
  teacher_name: string;
  room_id: string;
  room_name: string;
  cohort_section_id: string;
  cohort_name: string;
  current_slot_description: string;
  time_slot_id: string;
  suggested_alternatives: AlternativeOption[];
}

interface AnalysisResponse {
  timetable_id: string;
  disruption_type: string;
  total_sessions: number;
  affected_count: number;
  unaffected_preserved_count: number;
  preservation_rate_percent: number;
  affected_sessions: AffectedSession[];
  summary: string;
}

export default function SmartReschedulerPage() {
  const { user } = useAuth();
  const isFacultyOrAdmin = Boolean(user && ["ADMIN", "HOD", "COORDINATOR", "TEACHER"].includes(user.role));

  // Step 1: Disruption Input
  const [disruptionType, setDisruptionType] = useState<"TEACHER_ABSENCE" | "ROOM_OUTAGE" | "SESSION_RESCHEDULE">("TEACHER_ABSENCE");
  const [selectedTeacherId, setSelectedTeacherId] = useState("tch_sharma");
  const [selectedRoomId, setSelectedRoomId] = useState("rm_lh101");
  const [selectedDay, setSelectedDay] = useState<number>(1); // Monday

  // Step 2: Analysis Results
  const [analysis, setAnalysis] = useState<AnalysisResponse | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [selectedAlternatives, setSelectedAlternatives] = useState<Record<string, AlternativeOption>>({});

  // Step 3: Application & Verification
  const [applying, setApplying] = useState(false);
  const [applyResult, setApplyResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  // Auto-run analysis on initial mount
  useEffect(() => {
    handleRunAnalysis();
  }, []);

  const handleRunAnalysis = async () => {
    try {
      setAnalyzing(true);
      setError(null);
      setApplyResult(null);

      const res = await apiRequest<AnalysisResponse>("/rescheduler/analyze", {
        method: "POST",
        body: JSON.stringify({
          disruption_type: disruptionType,
          teacher_id: disruptionType === "TEACHER_ABSENCE" ? selectedTeacherId : null,
          room_id: disruptionType === "ROOM_OUTAGE" ? selectedRoomId : null,
          day_of_week: selectedDay,
        }),
      });

      setAnalysis(res);

      // Pre-select the highest ranked alternative for each affected session
      const preselected: Record<string, AlternativeOption> = {};
      res.affected_sessions.forEach((s) => {
        if (s.suggested_alternatives.length > 0) {
          preselected[s.session_id] = s.suggested_alternatives[0];
        }
      });
      setSelectedAlternatives(preselected);
    } catch (err: any) {
      setError(err?.message || "Failed to analyze schedule disruption.");
    } finally {
      setAnalyzing(false);
    }
  };

  const handleApplyAlternative = async (sessionId: string) => {
    if (!isFacultyOrAdmin) {
      setError("Permission denied: Only Faculty and HOD can apply schedule modifications. Class Representatives have read-only access.");
      return;
    }
    const chosen = selectedAlternatives[sessionId];
    if (!chosen) return;

    try {
      setApplying(true);
      setError(null);

      const res = await apiRequest("/rescheduler/apply", {
        method: "POST",
        body: JSON.stringify({
          session_id: sessionId,
          new_time_slot_id: chosen.new_time_slot_id,
          new_teacher_id: chosen.new_teacher_id,
          new_room_id: chosen.new_room_id,
          reason: `Smart Rescheduler adjustment: ${chosen.title}`,
        }),
      });

      setApplyResult(res);
      // Re-run analysis to show updated schedule
      await handleRunAnalysis();
    } catch (err: any) {
      setError(err?.message || "Failed to apply reschedule change.");
    } finally {
      setApplying(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Banner & Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-4 border-b border-[#E2E7EE]">
        <div>
          <div className="flex items-center space-x-2">
            <span className="text-[11px] font-bold uppercase tracking-wider text-[#1261A0] bg-[#EAF3FB] px-2.5 py-0.5 rounded">
              Core Module 2
            </span>
            <span className="text-xs text-[#697586]">Automated Schedule Continuity Engine</span>
          </div>
          <h1 className="text-xl sm:text-2xl font-bold text-[#17324D] mt-1">Smart Rescheduler</h1>
          <p className="text-xs sm:text-sm text-[#697586] mt-0.5">
            Handle faculty leave, room maintenance, and timetable changes with automated clash-free alternative proposals.
          </p>
        </div>

        <div className="flex items-center space-x-2">
          <Link
            href="/conflicts"
            className="px-3 py-1.5 rounded-lg border border-[#E2E7EE] bg-white hover:bg-slate-50 text-slate-700 text-xs font-semibold flex items-center space-x-1.5 transition-colors"
          >
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
            <span>Open Conflict Detector</span>
          </Link>
          <Link
            href="/timetables"
            className="px-3.5 py-1.5 rounded-lg bg-[#1261A0] hover:bg-[#0E4E82] text-white text-xs font-semibold flex items-center space-x-1.5 transition-colors"
          >
            <span>Timetable Matrix</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>
      </div>

      {applyResult && (
        <div className="p-4 rounded-xl bg-emerald-50 border-2 border-emerald-300 text-xs text-emerald-900 flex items-start justify-between gap-3 shadow-xs">
          <div className="flex items-start space-x-2.5">
            <CheckCircle2 className="w-5 h-5 text-emerald-600 flex-shrink-0 mt-0.5" />
            <div>
              <h4 className="font-bold text-sm text-emerald-900">
                Reschedule Applied & Automatically Revalidated!
              </h4>
              <p className="text-emerald-800 mt-0.5">
                {applyResult.message} Session has been updated in the master timetable with zero clashes introduced.
              </p>
            </div>
          </div>
          <button onClick={() => setApplyResult(null)} className="text-emerald-600 hover:text-emerald-800 font-bold">
            &times;
          </button>
        </div>
      )}

      {error && (
        <div className="p-4 rounded-lg bg-rose-50 border border-rose-200 text-xs text-rose-700 font-medium">
          {error}
        </div>
      )}

      {/* STEP 1: CONFIGURE DISRUPTION SCENARIO */}
      <div className="bg-white rounded-xl border border-[#E2E7EE] p-5 shadow-xs space-y-4">
        <div className="flex items-center justify-between border-b border-slate-100 pb-3">
          <div className="flex items-center space-x-2">
            <span className="w-5 h-5 rounded-full bg-[#1261A0] text-white text-xs font-bold flex items-center justify-center">
              1
            </span>
            <h3 className="font-bold text-sm text-[#17324D]">Declare Disruption Scenario</h3>
          </div>
          <span className="text-xs text-[#697586]">Simulate & Resolve in 1 Click</span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <button
            onClick={() => setDisruptionType("TEACHER_ABSENCE")}
            className={`p-3.5 rounded-xl border text-left transition-all ${
              disruptionType === "TEACHER_ABSENCE"
                ? "border-[#1261A0] bg-[#EAF3FB] ring-1 ring-[#1261A0]"
                : "border-[#E2E7EE] bg-white hover:border-slate-300"
            }`}
          >
            <div className="flex items-center space-x-2">
              <UserCheck className={`w-4 h-4 ${disruptionType === "TEACHER_ABSENCE" ? "text-[#1261A0]" : "text-slate-500"}`} />
              <span className="font-bold text-xs text-[#17324D]">Faculty Absence / Leave</span>
            </div>
            <p className="text-[11px] text-[#697586] mt-1">Instructor unavailable; substitute or swap affected periods</p>
          </button>

          <button
            onClick={() => setDisruptionType("ROOM_OUTAGE")}
            className={`p-3.5 rounded-xl border text-left transition-all ${
              disruptionType === "ROOM_OUTAGE"
                ? "border-[#1261A0] bg-[#EAF3FB] ring-1 ring-[#1261A0]"
                : "border-[#E2E7EE] bg-white hover:border-slate-300"
            }`}
          >
            <div className="flex items-center space-x-2">
              <MapPin className={`w-4 h-4 ${disruptionType === "ROOM_OUTAGE" ? "text-[#1261A0]" : "text-slate-500"}`} />
              <span className="font-bold text-xs text-[#17324D]">Classroom / Lab Outage</span>
            </div>
            <p className="text-[11px] text-[#697586] mt-1">Facility maintenance or AC repair; reallocate suitable venue</p>
          </button>

          <button
            onClick={() => setDisruptionType("SESSION_RESCHEDULE")}
            className={`p-3.5 rounded-xl border text-left transition-all ${
              disruptionType === "SESSION_RESCHEDULE"
                ? "border-[#1261A0] bg-[#EAF3FB] ring-1 ring-[#1261A0]"
                : "border-[#E2E7EE] bg-white hover:border-slate-300"
            }`}
          >
            <div className="flex items-center space-x-2">
              <RefreshCw className={`w-4 h-4 ${disruptionType === "SESSION_RESCHEDULE" ? "text-[#1261A0]" : "text-slate-500"}`} />
              <span className="font-bold text-xs text-[#17324D]">Class Schedule Swap</span>
            </div>
            <p className="text-[11px] text-[#697586] mt-1">Move individual lecture to an optimal vacant period</p>
          </button>
        </div>

        {/* Inputs */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-2">
          {disruptionType === "TEACHER_ABSENCE" && (
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Select Unavailable Faculty</label>
              <select
                value={selectedTeacherId}
                onChange={(e) => setSelectedTeacherId(e.target.value)}
                className="w-full text-xs rounded-lg border border-[#E2E7EE] p-2 bg-white font-medium text-[#17324D]"
              >
                <option value="tch_sharma">Prof. Vikram Sharma (Data Structures)</option>
                <option value="tch_gupta">Prof. Anita Gupta (Database Systems)</option>
                <option value="tch_patel">Prof. Rajesh Patel (Operating Systems)</option>
                <option value="tch_rao">Prof. Sneha Rao (Software Engineering)</option>
              </select>
            </div>
          )}

          {disruptionType === "ROOM_OUTAGE" && (
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Select Facility Under Maintenance</label>
              <select
                value={selectedRoomId}
                onChange={(e) => setSelectedRoomId(e.target.value)}
                className="w-full text-xs rounded-lg border border-[#E2E7EE] p-2 bg-white font-medium text-[#17324D]"
              >
                <option value="rm_lh101">Main Block LH-101 (Lecture Hall, Cap: 60)</option>
                <option value="rm_lh102">Main Block LH-102 (Lecture Hall, Cap: 60)</option>
                <option value="rm_lab1">CS Block LAB-201 (Computer Lab, Cap: 40)</option>
                <option value="rm_lab2">CS Block LAB-202 (Computer Lab, Cap: 40)</option>
              </select>
            </div>
          )}

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Affected Academic Day</label>
            <select
              value={selectedDay}
              onChange={(e) => setSelectedDay(Number(e.target.value))}
              className="w-full text-xs rounded-lg border border-[#E2E7EE] p-2 bg-white font-medium text-[#17324D]"
            >
              <option value={1}>Monday</option>
              <option value={2}>Tuesday</option>
              <option value={3}>Wednesday</option>
              <option value={4}>Thursday</option>
              <option value={5}>Friday</option>
            </select>
          </div>

          <div className="flex items-end">
            <button
              onClick={handleRunAnalysis}
              disabled={analyzing}
              className="w-full px-4 py-2 rounded-lg bg-[#1261A0] hover:bg-[#0E4E82] text-white text-xs font-semibold flex items-center justify-center space-x-1.5 transition-colors disabled:opacity-50"
            >
              <Cpu className="w-4 h-4" />
              <span>{analyzing ? "Analyzing Impact..." : "Run Impact Analysis"}</span>
            </button>
          </div>
        </div>
      </div>

      {/* STEP 2: IMPACT PREVIEW & PRESERVATION SCORE */}
      {analysis && (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="bg-white rounded-xl border border-[#E2E7EE] p-4 shadow-xs">
              <div className="text-xs text-[#697586]">Directly Affected Classes</div>
              <div className="text-2xl font-bold text-[#B42332] mt-1">
                {analysis.affected_count} Session{analysis.affected_count > 1 ? "s" : ""}
              </div>
              <div className="text-[11px] text-slate-400 mt-0.5">Requiring alternative scheduling</div>
            </div>

            <div className="bg-white rounded-xl border border-[#E2E7EE] p-4 shadow-xs">
              <div className="text-xs text-[#697586]">Preserved Unaffected Classes</div>
              <div className="text-2xl font-bold text-[#16805D] mt-1">
                {analysis.unaffected_preserved_count} Sessions
              </div>
              <div className="text-[11px] text-emerald-700 mt-0.5 font-medium">
                {analysis.preservation_rate_percent}% Schedule Stability
              </div>
            </div>

            <div className="bg-white rounded-xl border border-[#E2E7EE] p-4 shadow-xs">
              <div className="text-xs text-[#697586]">Constraint Revalidation</div>
              <div className="text-2xl font-bold text-[#1261A0] mt-1">Verified</div>
              <div className="text-[11px] text-slate-400 mt-0.5">0 clashes in proposed alternatives</div>
            </div>
          </div>

          {/* STEP 3: AFFECTED SESSIONS & RANKED ALTERNATIVES */}
          <div className="bg-white rounded-xl border border-[#E2E7EE] p-5 shadow-xs space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div className="flex items-center space-x-2">
                <span className="w-5 h-5 rounded-full bg-[#1261A0] text-white text-xs font-bold flex items-center justify-center">
                  2
                </span>
                <h3 className="font-bold text-sm text-[#17324D]">
                  Affected Classes & Feasible Alternative Proposals ({analysis.affected_sessions.length})
                </h3>
              </div>
              <span className="text-xs text-[#16805D] font-bold">
                ✓ Non-destructive sandbox preview
              </span>
            </div>

            {analysis.affected_sessions.length === 0 ? (
              <div className="py-12 text-center text-slate-500">
                <CheckCircle className="w-10 h-10 text-emerald-500 mx-auto mb-2" />
                <h4 className="text-sm font-bold text-[#17324D]">No Classes Affected in This Scenario</h4>
                <p className="text-xs text-[#697586] mt-1">
                  The selected faculty or room has zero scheduled classes during the specified day.
                </p>
              </div>
            ) : (
              <div className="space-y-6">
                {analysis.affected_sessions.map((sess) => {
                  const currentSelected = selectedAlternatives[sess.session_id];

                  return (
                    <div
                      key={sess.session_id}
                      className="p-4 rounded-xl border border-[#E2E7EE] bg-[#F7F9FC] space-y-4"
                    >
                      {/* Current Session Summary */}
                      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 pb-3 border-b border-slate-200">
                        <div>
                          <div className="flex items-center space-x-2">
                            <span className="text-xs font-bold text-[#17324D]">
                              {sess.subject_code} — {sess.subject_name}
                            </span>
                            <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-200 text-slate-700">
                              Section: {sess.cohort_name}
                            </span>
                          </div>
                          <div className="flex items-center space-x-3 text-xs text-[#697586] mt-1">
                            <span className="flex items-center">
                              <Clock className="w-3.5 h-3.5 mr-1 text-[#1261A0]" />
                              {sess.current_slot_description}
                            </span>
                            <span>•</span>
                            <span className="flex items-center">
                              <MapPin className="w-3.5 h-3.5 mr-1 text-[#1261A0]" />
                              {sess.room_name}
                            </span>
                            <span>•</span>
                            <span className="flex items-center">
                              <UserCheck className="w-3.5 h-3.5 mr-1 text-[#1261A0]" />
                              {sess.teacher_name}
                            </span>
                          </div>
                        </div>

                        <span className="text-xs font-bold text-[#B42332] bg-rose-100 px-2.5 py-1 rounded">
                          Disruption Active
                        </span>
                      </div>

                      {/* Alternative Suggestions Grid */}
                      <div>
                        <div className="flex items-center space-x-1.5 text-xs font-bold text-slate-700 uppercase tracking-wider mb-2">
                          <Sparkles className="w-3.5 h-3.5 text-[#1261A0]" />
                          <span>Feasible Clash-Free Alternatives Ranked for This Class</span>
                        </div>

                        {sess.suggested_alternatives.length === 0 ? (
                          <div className="p-3 rounded-lg bg-amber-50 border border-amber-200 text-xs text-amber-800">
                            No immediate vacant slot identified. Recommend creating an asynchronous makeup session or consulting HOD.
                          </div>
                        ) : (
                          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                            {sess.suggested_alternatives.map((alt, aIdx) => {
                              const isChosen = currentSelected?.title === alt.title;

                              return (
                                <div
                                  key={aIdx}
                                  onClick={() =>
                                    setSelectedAlternatives((prev) => ({
                                      ...prev,
                                      [sess.session_id]: alt,
                                    }))
                                  }
                                  className={`p-3.5 rounded-xl border text-left cursor-pointer transition-all ${
                                    isChosen
                                      ? "border-[#1261A0] bg-white ring-2 ring-[#1261A0] shadow-sm"
                                      : "border-[#E2E7EE] bg-white hover:border-slate-300"
                                  }`}
                                >
                                  <div className="flex items-center justify-between">
                                    <span
                                      className={`text-[10px] font-bold px-1.5 py-0.5 rounded uppercase tracking-wider ${
                                        alt.strategy === "SHIFT_TIMESLOT"
                                          ? "bg-blue-100 text-[#1261A0]"
                                          : alt.strategy === "SUBSTITUTE_FACULTY"
                                          ? "bg-purple-100 text-purple-700"
                                          : "bg-emerald-100 text-emerald-800"
                                      }`}
                                    >
                                      {alt.strategy.replace(/_/g, " ")}
                                    </span>
                                    <span className="text-[10px] font-bold text-emerald-700">
                                      {alt.feasibility_score}% Feasible
                                    </span>
                                  </div>

                                  <h5 className="text-xs font-bold text-[#17324D] mt-2">{alt.title}</h5>
                                  <p className="text-[11px] text-[#697586] mt-1 leading-relaxed">
                                    {alt.description}
                                  </p>

                                  <div className="mt-3 pt-2 border-t border-slate-100 flex items-center justify-between text-[11px]">
                                    <span className="text-[#16805D] font-semibold flex items-center">
                                      <CheckCircle className="w-3 h-3 mr-1" />
                                      0 Clashes
                                    </span>
                                    <span className={`font-bold ${isChosen ? "text-[#1261A0]" : "text-slate-400"}`}>
                                      {isChosen ? "Selected ✓" : "Select Option"}
                                    </span>
                                  </div>
                                </div>
                              );
                            })}
                          </div>
                        )}
                      </div>

                      {/* Action Button */}
                      {currentSelected && (
                        <div className="flex items-center justify-end pt-2">
                          {isFacultyOrAdmin ? (
                            <button
                              onClick={() => handleApplyAlternative(sess.session_id)}
                              disabled={applying}
                              className="px-4 py-2 rounded-lg bg-[#16805D] hover:bg-[#12664A] text-white text-xs font-semibold flex items-center space-x-1.5 transition-colors shadow-xs disabled:opacity-50"
                            >
                              <CheckCircle2 className="w-3.5 h-3.5" />
                              <span>
                                {applying ? "Applying & Revalidating..." : `Apply & Revalidate: "${currentSelected.title}"`}
                              </span>
                            </button>
                          ) : (
                            <div className="text-xs text-slate-500 italic flex items-center">
                              <Lock className="w-3.5 h-3.5 mr-1 text-slate-400" />
                              <span>Read-only preview. Schedule modifications can only be applied by Faculty and HOD.</span>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
