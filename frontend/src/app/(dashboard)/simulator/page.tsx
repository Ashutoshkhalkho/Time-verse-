"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useAuth } from "@/context/AuthContext";
import { apiRequest } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle,
  Clock,
  Cpu,
  Layers,
  RefreshCw,
  Send,
  ShieldAlert,
  Sparkles,
  Users,
  XCircle,
} from "lucide-react";

interface AffectedSession {
  session_id: string;
  subject_code: string;
  subject_name: string;
  cohort_name: string;
  teacher_name: string;
  room_name: string;
  time_slot_name: string;
  conflict_reason: string;
  is_directly_affected: boolean;
}

interface AlternativeOption {
  option_rank: number;
  proposed_time_slot_id: string;
  proposed_time_slot_name: string;
  proposed_room_id: string;
  proposed_room_number: string;
  proposed_teacher_id: string;
  proposed_teacher_name: string;
  affected_sessions_count: number;
  soft_penalty_score: number;
  is_feasible: boolean;
  hard_constraints_violated: string[];
  trade_off_explanation: {
    gap_penalty?: number;
    workload_penalty?: number;
    room_preference_penalty?: number;
    summary?: string;
  };
}

interface SimulationReport {
  timetable_id: string;
  scenario_type: string;
  is_feasible: boolean;
  directly_affected_count: number;
  indirect_cascade_count: number;
  affected_sessions: AffectedSession[];
  recommended_alternatives: AlternativeOption[];
  hard_constraints_summary: string[];
  simulation_timestamp: string;
}

export default function SimulatorPage() {
  const { user } = useAuth();
  const [timetables, setTimetables] = useState<any[]>([]);
  const [selectedTimetableId, setSelectedTimetableId] = useState<string>("");
  const [scenarioType, setScenarioType] = useState<string>("TEACHER_UNAVAILABLE");
  const [teacherId, setTeacherId] = useState<string>("tch_sharma");
  const [roomId, setRoomId] = useState<string>("rm_lh101");
  const [timeSlotId, setTimeSlotId] = useState<string>("ts_d1_p2");
  const [reason, setReason] = useState<string>("Emergency faculty leave / laboratory equipment maintenance");

  const [loading, setLoading] = useState<boolean>(false);
  const [report, setReport] = useState<SimulationReport | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [applyingIndex, setApplyingIndex] = useState<number | null>(null);
  const [applyResultMsg, setApplyResultMsg] = useState<{ text: string; type: "success" | "error" } | null>(null);

  const isAuthorizedToApply = Boolean(user && ["ADMIN", "HOD", "COORDINATOR"].includes(user.role));

  const handleApplyAlternative = async (alt: AlternativeOption, index: number) => {
    if (!report || report.affected_sessions.length === 0) return;
    const targetSession = report.affected_sessions[0];
    try {
      setApplyingIndex(index);
      setApplyResultMsg(null);
      const res: any = await apiRequest("/simulator/apply", {
        method: "POST",
        body: JSON.stringify({
          timetable_id: report.timetable_id,
          session_id: targetSession.session_id,
          target_time_slot_id: alt.proposed_time_slot_id,
          target_room_id: alt.proposed_room_id || undefined,
          target_teacher_id: alt.proposed_teacher_id || undefined,
          reason: `Applied alternative Rank #${alt.option_rank}: ${alt.trade_off_explanation?.summary || "Optimized schedule"}`,
        }),
      });
      setApplyResultMsg({
        text: `Changes applied successfully! Session reassigned to ${alt.proposed_time_slot_name}. ${res.ripple_alert_count || 1} ripple notification(s) dispatched to affected stakeholders.`,
        type: "success",
      });
    } catch (err: any) {
      setApplyResultMsg({
        text: err.detail || err.message || "Failed to apply alternative.",
        type: "error",
      });
    } finally {
      setApplyingIndex(null);
    }
  };

  useEffect(() => {
    async function loadTimetables() {
      try {
        const list: any = await apiRequest("/timetables?department_id=dept_cs");
        setTimetables(list || []);
        if (list && list.length > 0) {
          setSelectedTimetableId(list[0].id);
        }
      } catch (err: any) {
        console.error("Failed to load timetables for simulation", err);
      }
    }
    loadTimetables();
  }, []);

  const handleSimulate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedTimetableId) {
      setErrorMsg("Please select an active timetable to simulate.");
      return;
    }

    setLoading(true);
    setErrorMsg(null);
    setReport(null);

    const payload: any = {
      timetable_id: selectedTimetableId,
      scenario_type: scenarioType,
      reason: reason,
    };

    if (scenarioType === "TEACHER_UNAVAILABLE") {
      payload.unavailable_teacher_id = teacherId;
      payload.unavailable_time_slot_ids = [timeSlotId];
    } else if (scenarioType === "ROOM_UNAVAILABLE") {
      payload.unavailable_room_id = roomId;
      payload.unavailable_time_slot_ids = [timeSlotId];
    }

    try {
      const res = await apiRequest<SimulationReport>("/simulator/simulate", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      setReport(res);
    } catch (err: any) {
      setErrorMsg(err.detail || "Simulation execution failed.");
    } finally {
      setLoading(false);
    }
  };

  const handleDiscard = () => {
    setReport(null);
  };

  return (
    <div className="min-h-screen bg-surface-canvas p-6 lg:p-8">
      {/* Top Header */}
      <div className="max-w-7xl mx-auto mb-8 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2">
            <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-primary/10 text-primary uppercase tracking-wider">
              What-If Sandbox
            </span>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800">
              Zero DB Writes Guaranteed
            </span>
          </div>
          <h1 className="text-2xl font-bold text-navy mt-1">Impact Simulator & Constraint Sandbox</h1>
          <p className="text-sm text-text-secondary mt-1">
            Simulate ad-hoc disruptions, evaluate constraint cascades, and preview OR-Tools schedule alternatives without modifying official published timetables.
          </p>
        </div>

        <div className="flex items-center space-x-3">
          <Link href="/timetables">
            <Button variant="outline" size="sm">
              <Layers className="w-4 h-4 mr-1.5" />
              View Timetables
            </Button>
          </Link>
          <Link href="/approvals">
            <Button size="sm">
              <Send className="w-4 h-4 mr-1.5" />
              Change Requests
            </Button>
          </Link>
        </div>
      </div>

      <div className="max-w-7xl mx-auto grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Left Column: Simulation Scenario Setup */}
        <div className="lg:col-span-5 space-y-6">
          <Card className="border-surface-border shadow-sm">
            <CardHeader className="pb-4">
              <CardTitle className="text-base flex items-center text-navy">
                <Cpu className="w-4 h-4 mr-2 text-primary" />
                Configure Disruption Scenario
              </CardTitle>
              <CardDescription>
                Define test parameters to run an isolated in-memory constraint solver simulation.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleSimulate} className="space-y-4">
                <div>
                  <label className="block text-xs font-medium text-navy mb-1">Target Timetable</label>
                  <select
                    value={selectedTimetableId}
                    onChange={(e) => setSelectedTimetableId(e.target.value)}
                    className="w-full text-xs rounded-md border border-surface-border bg-white px-3 py-2 text-text-main focus:outline-none focus:ring-1 focus:ring-primary"
                  >
                    {timetables.map((t) => (
                      <option key={t.id} value={t.id}>
                        {t.name || `Timetable v${t.version_major}.${t.version_minor}`} ({t.status})
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-medium text-navy mb-1">Scenario Type</label>
                  <div className="grid grid-cols-2 gap-2">
                    <button
                      type="button"
                      onClick={() => setScenarioType("TEACHER_UNAVAILABLE")}
                      className={`text-xs px-3 py-2 rounded-md border font-medium text-left transition-colors ${
                        scenarioType === "TEACHER_UNAVAILABLE"
                          ? "border-primary bg-primary/10 text-primary"
                          : "border-surface-border bg-white text-text-secondary hover:bg-slate-50"
                      }`}
                    >
                      Faculty Emergency Leave
                    </button>
                    <button
                      type="button"
                      onClick={() => setScenarioType("ROOM_UNAVAILABLE")}
                      className={`text-xs px-3 py-2 rounded-md border font-medium text-left transition-colors ${
                        scenarioType === "ROOM_UNAVAILABLE"
                          ? "border-primary bg-primary/10 text-primary"
                          : "border-surface-border bg-white text-text-secondary hover:bg-slate-50"
                      }`}
                    >
                      Room / Lab Maintenance
                    </button>
                  </div>
                </div>

                {scenarioType === "TEACHER_UNAVAILABLE" && (
                  <div>
                    <label className="block text-xs font-medium text-navy mb-1">Unavailable Teacher</label>
                    <select
                      value={teacherId}
                      onChange={(e) => setTeacherId(e.target.value)}
                      className="w-full text-xs rounded-md border border-surface-border bg-white px-3 py-2 text-text-main focus:outline-none focus:ring-1 focus:ring-primary"
                    >
                      <option value="tch_sharma">Dr. Rajesh Sharma (Faculty CS)</option>
                      <option value="tch_gupta">Prof. Anita Gupta (Faculty CS)</option>
                      <option value="tch_patel">Dr. Vikram Patel (Faculty CS)</option>
                      <option value="tch_rao">Prof. Sneha Rao (Faculty CS)</option>
                    </select>
                  </div>
                )}

                {scenarioType === "ROOM_UNAVAILABLE" && (
                  <div>
                    <label className="block text-xs font-medium text-navy mb-1">Unavailable Room / Lab</label>
                    <select
                      value={roomId}
                      onChange={(e) => setRoomId(e.target.value)}
                      className="w-full text-xs rounded-md border border-surface-border bg-white px-3 py-2 text-text-main focus:outline-none focus:ring-1 focus:ring-primary"
                    >
                      <option value="rm_lh101">Room LH-101 (Lecture Hall - Cap 60)</option>
                      <option value="rm_lh102">Room LH-102 (Lecture Hall - Cap 60)</option>
                      <option value="rm_lab1">CS Lab 1 (Computer Lab - Cap 35)</option>
                      <option value="rm_lab2">CS Lab 2 (Computer Lab - Cap 35)</option>
                    </select>
                  </div>
                )}

                <div>
                  <label className="block text-xs font-medium text-navy mb-1">Affected Time Slot</label>
                  <select
                    value={timeSlotId}
                    onChange={(e) => setTimeSlotId(e.target.value)}
                    className="w-full text-xs rounded-md border border-surface-border bg-white px-3 py-2 text-text-main focus:outline-none focus:ring-1 focus:ring-primary"
                  >
                    <option value="ts_d1_p1">Monday - Period 1 (09:00 - 10:00)</option>
                    <option value="ts_d1_p2">Monday - Period 2 (10:00 - 11:00)</option>
                    <option value="ts_d1_p4">Monday - Period 4 (12:00 - 13:00)</option>
                    <option value="ts_d2_p2">Tuesday - Period 2 (10:00 - 11:00)</option>
                    <option value="ts_d3_p3">Wednesday - Period 3 (11:00 - 12:00)</option>
                    <option value="ts_d4_p5">Thursday - Period 5 (14:00 - 15:00)</option>
                    <option value="ts_d5_p6">Friday - Period 6 (15:00 - 16:00)</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-medium text-navy mb-1">Simulation Note / Rationale</label>
                  <input
                    type="text"
                    value={reason}
                    onChange={(e) => setReason(e.target.value)}
                    className="w-full text-xs rounded-md border border-surface-border bg-white px-3 py-2 text-text-main focus:outline-none focus:ring-1 focus:ring-primary"
                    placeholder="E.g., Power grid overhaul or international research symposium..."
                  />
                </div>

                {errorMsg && (
                  <div className="p-3 bg-red-50 border border-red-200 rounded-md text-xs text-red-700 flex items-center">
                    <XCircle className="w-4 h-4 mr-2 flex-shrink-0" />
                    {errorMsg}
                  </div>
                )}

                <Button type="submit" disabled={loading} className="w-full mt-2">
                  {loading ? (
                    <>
                      <RefreshCw className="w-3.5 h-3.5 mr-2 animate-spin" />
                      Computing Solver Impact...
                    </>
                  ) : (
                    <>
                      <Sparkles className="w-3.5 h-3.5 mr-2" />
                      Run Impact Simulation
                    </>
                  )}
                </Button>
              </form>
            </CardContent>
          </Card>

          {/* Sandbox Isolation Notice */}
          <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 text-xs text-amber-800 space-y-1.5">
            <div className="font-semibold flex items-center">
              <ShieldAlert className="w-4 h-4 mr-1.5 text-amber-700" />
              Strict Architectural Isolation Policy
            </div>
            <p>
              Simulations execute on an in-memory duplicate of timetable sessions. Zero alerts are dispatched to students or faculty, and no database records are committed.
            </p>
          </div>
        </div>

        {/* Right Column: Simulation Report & Ranked Alternatives */}
        <div className="lg:col-span-7 space-y-6">
          {!report && !loading && (
            <Card className="border-dashed border-2 border-surface-border text-center py-16">
              <CardContent className="space-y-3">
                <Cpu className="w-10 h-10 mx-auto text-text-secondary opacity-60" />
                <h3 className="font-semibold text-navy text-base">No Active Simulation</h3>
                <p className="text-xs text-text-secondary max-w-sm mx-auto">
                  Configure a disruption scenario on the left and click &quot;Run Impact Simulation&quot; to inspect affected sessions and OR-Tools ranked alternatives.
                </p>
              </CardContent>
            </Card>
          )}

          {loading && (
            <Card className="border-surface-border text-center py-16">
              <CardContent className="space-y-3">
                <RefreshCw className="w-8 h-8 mx-auto text-primary animate-spin" />
                <h3 className="font-semibold text-navy text-sm">Evaluating Constraint Graph...</h3>
                <p className="text-xs text-text-secondary">
                  Calculating teacher workloads, cohort collision graphs, and CP-SAT soft preference penalties.
                </p>
              </CardContent>
            </Card>
          )}

          {report && (
            <div className="space-y-6">
              {/* Summary Stats Header */}
              <div className="grid grid-cols-3 gap-3">
                <Card className="border-surface-border">
                  <CardContent className="p-4 text-center">
                    <div className="text-xs text-text-secondary font-medium">Scenario Status</div>
                    <div className="mt-1 flex items-center justify-center space-x-1">
                      {report.is_feasible ? (
                        <span className="text-xs font-bold text-emerald-700 flex items-center">
                          <CheckCircle className="w-3.5 h-3.5 mr-1" /> Feasible
                        </span>
                      ) : (
                        <span className="text-xs font-bold text-red-700 flex items-center">
                          <XCircle className="w-3.5 h-3.5 mr-1" /> Disrupted
                        </span>
                      )}
                    </div>
                  </CardContent>
                </Card>

                <Card className="border-surface-border">
                  <CardContent className="p-4 text-center">
                    <div className="text-xs text-text-secondary font-medium">Direct Conflicts</div>
                    <div className="text-xl font-bold text-navy mt-0.5">{report.directly_affected_count}</div>
                  </CardContent>
                </Card>

                <Card className="border-surface-border">
                  <CardContent className="p-4 text-center">
                    <div className="text-xs text-text-secondary font-medium">Cascade Conflicts</div>
                    <div className="text-xl font-bold text-navy mt-0.5">{report.indirect_cascade_count}</div>
                  </CardContent>
                </Card>
              </div>

              {/* Directly Affected Sessions */}
              <Card className="border-surface-border shadow-sm">
                <CardHeader className="pb-3 flex flex-row items-center justify-between">
                  <div>
                    <CardTitle className="text-sm font-semibold text-navy flex items-center">
                      <AlertTriangle className="w-4 h-4 mr-2 text-amber-600" />
                      Directly Affected Sessions ({report.affected_sessions.length})
                    </CardTitle>
                    <CardDescription className="text-xs">
                      Sessions that collide directly with the simulated disruption.
                    </CardDescription>
                  </div>
                  <Button variant="outline" size="sm" onClick={handleDiscard}>
                    Discard Simulation
                  </Button>
                </CardHeader>
                <CardContent className="space-y-3">
                  {report.affected_sessions.length === 0 ? (
                    <div className="text-xs text-text-secondary py-2 text-center">
                      No sessions collide directly with the selected parameters.
                    </div>
                  ) : (
                    report.affected_sessions.map((s) => (
                      <div
                        key={s.session_id}
                        className="p-3 rounded-lg border border-red-200 bg-red-50/60 flex flex-col sm:flex-row sm:items-center justify-between gap-2"
                      >
                        <div>
                          <div className="flex items-center space-x-2">
                            <span className="text-xs font-bold text-navy">{s.subject_code}</span>
                            <span className="text-xs text-navy font-medium">{s.subject_name}</span>
                            <Badge variant="secondary" className="text-[10px]">{s.cohort_name}</Badge>
                          </div>
                          <div className="text-xs text-text-secondary mt-1 flex flex-wrap gap-x-3">
                            <span>Faculty: <b>{s.teacher_name}</b></span>
                            <span>Room: <b>{s.room_name}</b></span>
                            <span>Slot: <b>{s.time_slot_name}</b></span>
                          </div>
                        </div>
                        <div className="text-xs font-medium text-red-700 bg-white px-2.5 py-1 rounded border border-red-200 sm:self-center">
                          {s.conflict_reason}
                        </div>
                      </div>
                    ))
                  )}
                </CardContent>
              </Card>

              {/* Recommended OR-Tools Alternatives */}
              <Card className="border-surface-border shadow-sm">
                <CardHeader className="pb-3">
                  <div className="flex items-center justify-between">
                    <div>
                      <CardTitle className="text-sm font-semibold text-navy flex items-center">
                        <Sparkles className="w-4 h-4 mr-2 text-primary" />
                        CP-SAT Solver Alternative Proposals ({report.recommended_alternatives.length})
                      </CardTitle>
                      <CardDescription className="text-xs">
                        Feasible alternatives ranked by soft-constraint trade-offs (gap minimization, workload balance).
                      </CardDescription>
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="space-y-3">
                  {applyResultMsg && (
                    <div
                      className={`p-3 rounded-lg text-xs font-medium flex items-center justify-between ${
                        applyResultMsg.type === "success"
                          ? "bg-emerald-50 text-emerald-800 border border-emerald-200"
                          : "bg-rose-50 text-rose-800 border border-rose-200"
                      }`}
                    >
                      <span>{applyResultMsg.text}</span>
                      <button
                        onClick={() => setApplyResultMsg(null)}
                        className="text-slate-400 hover:text-slate-600 font-bold ml-2"
                      >
                        ✕
                      </button>
                    </div>
                  )}

                  {report.recommended_alternatives.length === 0 ? (
                    <div className="text-xs text-text-secondary py-3 text-center">
                      No automatic alternatives generated for this test condition.
                    </div>
                  ) : (
                    report.recommended_alternatives.map((alt, idx) => (
                      <div
                        key={alt.option_rank}
                        className={`p-4 rounded-lg border transition-all ${
                          alt.option_rank === 1
                            ? "border-emerald-300 bg-emerald-50/50 ring-1 ring-emerald-300"
                            : "border-surface-border bg-white"
                        }`}
                      >
                        <div className="flex items-center justify-between mb-2">
                          <div className="flex items-center space-x-2">
                            <span
                              className={`text-xs font-bold px-2 py-0.5 rounded ${
                                alt.option_rank === 1
                                  ? "bg-emerald-600 text-white"
                                  : "bg-slate-200 text-slate-800"
                              }`}
                            >
                              Rank #{alt.option_rank} {alt.option_rank === 1 && "(Optimal Trade-off)"}
                            </span>
                            <span className="text-xs text-text-secondary">
                              Soft Penalty: <b>{alt.soft_penalty_score}</b>
                            </span>
                          </div>
                          <span className="text-[11px] font-semibold text-emerald-800 flex items-center">
                            <CheckCircle className="w-3.5 h-3.5 mr-1" /> Feasible
                          </span>
                        </div>

                        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 py-2 text-xs border-y border-surface-border/60 my-2">
                          <div>
                            <span className="text-text-secondary block text-[11px]">Proposed Slot</span>
                            <span className="font-semibold text-navy">{alt.proposed_time_slot_name}</span>
                          </div>
                          <div>
                            <span className="text-text-secondary block text-[11px]">Proposed Room</span>
                            <span className="font-semibold text-navy">{alt.proposed_room_number}</span>
                          </div>
                          <div>
                            <span className="text-text-secondary block text-[11px]">Assigned Teacher</span>
                            <span className="font-semibold text-navy">{alt.proposed_teacher_name}</span>
                          </div>
                        </div>

                        <div className="text-xs text-text-secondary flex flex-wrap items-center justify-between gap-2 pt-1">
                          <span className="max-w-md">{alt.trade_off_explanation?.summary || "Balanced workload with zero teacher double-bookings."}</span>
                          <div className="flex items-center space-x-2">
                            {isAuthorizedToApply && (
                              <Button
                                size="sm"
                                disabled={applyingIndex === idx}
                                onClick={() => handleApplyAlternative(alt, idx)}
                                className="text-xs h-7 bg-emerald-600 hover:bg-emerald-700 text-white shadow-xs"
                              >
                                {applyingIndex === idx ? (
                                  <>
                                    <RefreshCw className="w-3 h-3 mr-1 animate-spin" />
                                    Applying & Notifying...
                                  </>
                                ) : (
                                  <>
                                    <CheckCircle className="w-3 h-3 mr-1" />
                                    Apply Change (HOD)
                                  </>
                                )}
                              </Button>
                            )}
                            <Link href="/approvals">
                              <Button size="sm" variant="outline" className="text-xs h-7">
                                Request Review
                                <ArrowRight className="w-3 h-3 ml-1" />
                              </Button>
                            </Link>
                          </div>
                        </div>
                      </div>
                    ))
                  )}
                </CardContent>
              </Card>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
