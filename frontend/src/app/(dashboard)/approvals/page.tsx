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
  FileText,
  Filter,
  Layers,
  PlusCircle,
  RefreshCw,
  Send,
  Shield,
  ThumbsDown,
  ThumbsUp,
  UserCheck,
  XCircle,
} from "lucide-react";

interface AlternativeDto {
  id: string;
  option_rank: number;
  proposed_time_slot_id: string;
  proposed_time_slot_name: string;
  proposed_room_id: string;
  proposed_room_number: string;
  proposed_teacher_id: string;
  proposed_teacher_name: string;
  affected_sessions_count: number;
  soft_penalty_score: number;
  trade_off_explanation: any;
  is_selected: boolean;
}

interface ChangeRequestDto {
  id: string;
  timetable_id: string;
  target_session_id: string;
  requester_user_id: string;
  requester_name: string;
  request_type: string;
  reason: string;
  status: "SUBMITTED" | "UNDER_REVIEW" | "ALTERNATIVES_PROPOSED" | "APPROVED" | "REJECTED" | "CANCELLED";
  proposed_time_slot_id?: string;
  proposed_room_id?: string;
  proposed_teacher_id?: string;
  reviewer_user_id?: string;
  reviewer_name?: string;
  review_decision_reason?: string;
  reviewed_at?: string;
  created_at: string;
  updated_at: string;
  alternatives: AlternativeDto[];
}

export default function ApprovalsPage() {
  const { user } = useAuth();
  const [requests, setRequests] = useState<ChangeRequestDto[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [statusFilter, setStatusFilter] = useState<string>("ALL");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Submit Modal State
  const [showSubmitModal, setShowSubmitModal] = useState<boolean>(false);
  const [timetables, setTimetables] = useState<any[]>([]);
  const [selectedTimetableId, setSelectedTimetableId] = useState<string>("");
  const [timetableSessions, setTimetableSessions] = useState<any[]>([]);
  const [selectedSessionId, setSelectedSessionId] = useState<string>("");
  const [requestType, setRequestType] = useState<string>("RESCHEDULE_SESSION");
  const [reason, setReason] = useState<string>("");
  const [submitting, setSubmitting] = useState<boolean>(false);

  // Decision Modal State
  const [activeRequest, setActiveRequest] = useState<ChangeRequestDto | null>(null);
  const [decisionModalOpen, setDecisionModalOpen] = useState<boolean>(false);
  const [decisionType, setDecisionType] = useState<"APPROVED" | "REJECTED">("APPROVED");
  const [selectedAltId, setSelectedAltId] = useState<string>("");
  const [decisionReason, setDecisionReason] = useState<string>("");
  const [deciding, setDeciding] = useState<boolean>(false);

  // Reviewing State
  const [reviewingId, setReviewingId] = useState<string | null>(null);

  const isHodOrAdmin = user && ["ADMIN", "HOD"].includes(user.role);
  const isCoordinator = user && ["ADMIN", "COORDINATOR", "HOD"].includes(user.role);

  const fetchRequests = async () => {
    setLoading(true);
    try {
      const url = statusFilter === "ALL" ? "/approvals/requests" : `/approvals/requests?status=${statusFilter}`;
      const data = await apiRequest<ChangeRequestDto[]>(url);
      setRequests(data || []);
    } catch (err: any) {
      setErrorMsg(err.detail || "Failed to load change requests.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRequests();
  }, [statusFilter]);

  // Load Timetables for Submit Modal
  useEffect(() => {
    async function loadMeta() {
      try {
        const list: any = await apiRequest("/timetables?department_id=dept_cs");
        setTimetables(list || []);
        if (list && list.length > 0) {
          setSelectedTimetableId(list[0].id);
        }
      } catch (err: any) {
        console.error("Failed to load timetables for request modal", err);
      }
    }
    loadMeta();
  }, []);

  // When selected timetable changes, load grid sessions for picking
  useEffect(() => {
    async function loadSessions() {
      if (!selectedTimetableId) return;
      try {
        const res: any = await apiRequest(`/timetables/${selectedTimetableId}/grid?section_id=sec_cs_3a`);
        const extracted: any[] = [];
        if (res?.grid) {
          res.grid.forEach((row: any) => {
            row.periods.forEach((p: any) => {
              if (p.session) {
                extracted.push({
                  id: p.session.session_id,
                  label: `${row.day_name} P${p.period_number}: ${p.session.subject_code} - ${p.session.subject_name} (${p.session.teacher_name})`,
                });
              }
            });
          });
        }
        setTimetableSessions(extracted);
        if (extracted.length > 0) {
          setSelectedSessionId(extracted[0].id);
        }
      } catch (err) {
        console.error("Failed to load sessions for picker", err);
      }
    }
    loadSessions();
  }, [selectedTimetableId]);

  const handleSubmitRequest = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedTimetableId || !selectedSessionId || !reason.trim()) {
      setErrorMsg("Please complete all required fields including justification.");
      return;
    }

    setSubmitting(true);
    setErrorMsg(null);
    setSuccessMsg(null);

    try {
      await apiRequest("/approvals/requests", {
        method: "POST",
        body: JSON.stringify({
          timetable_id: selectedTimetableId,
          target_session_id: selectedSessionId,
          request_type: requestType,
          reason: reason,
        }),
      });

      setSuccessMsg("Timetable change request submitted successfully.");
      setShowSubmitModal(false);
      setReason("");
      fetchRequests();
    } catch (err: any) {
      setErrorMsg(err.detail || "Failed to submit request.");
    } finally {
      setSubmitting(false);
    }
  };

  const handleReview = async (requestId: string) => {
    setReviewingId(requestId);
    setErrorMsg(null);
    try {
      await apiRequest(`/approvals/requests/${requestId}/review`, {
        method: "POST",
      });
      setSuccessMsg("OR-Tools CP-SAT alternatives generated for request.");
      fetchRequests();
    } catch (err: any) {
      setErrorMsg(err.detail || "Review generation failed.");
    } finally {
      setReviewingId(null);
    }
  };

  const handleOpenDecision = (req: ChangeRequestDto, type: "APPROVED" | "REJECTED") => {
    setActiveRequest(req);
    setDecisionType(type);
    setDecisionReason("");
    if (req.alternatives && req.alternatives.length > 0) {
      setSelectedAltId(req.alternatives[0].id);
    } else {
      setSelectedAltId("");
    }
    setDecisionModalOpen(true);
  };

  const handleExecuteDecision = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeRequest) return;
    if (!decisionReason.trim()) {
      setErrorMsg("Please provide formal decision comments/rationale.");
      return;
    }

    setDeciding(true);
    setErrorMsg(null);

    try {
      await apiRequest(`/approvals/requests/${activeRequest.id}/decide`, {
        method: "POST",
        body: JSON.stringify({
          decision: decisionType,
          decision_reason: decisionReason,
          selected_alternative_id: decisionType === "APPROVED" ? (selectedAltId || null) : null,
        }),
      });

      setSuccessMsg(
        decisionType === "APPROVED"
          ? "Change request approved! Revalidation succeeded, new version published, and notifications dispatched."
          : "Change request rejected. Official timetable remains untouched."
      );
      setDecisionModalOpen(false);
      fetchRequests();
    } catch (err: any) {
      setErrorMsg(err.detail || "Decision execution failed.");
    } finally {
      setDeciding(false);
    }
  };

  const handleCancelRequest = async (requestId: string) => {
    if (!confirm("Are you sure you want to cancel this change request?")) return;
    try {
      await apiRequest(`/approvals/requests/${requestId}/cancel`, {
        method: "POST",
      });
      setSuccessMsg("Change request cancelled.");
      fetchRequests();
    } catch (err: any) {
      setErrorMsg(err.detail || "Cancellation failed.");
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "SUBMITTED":
        return <Badge variant="secondary" className="bg-blue-100 text-blue-800 border-blue-200">Submitted</Badge>;
      case "UNDER_REVIEW":
        return <Badge variant="secondary" className="bg-amber-100 text-amber-800 border-amber-200">Under Review</Badge>;
      case "ALTERNATIVES_PROPOSED":
        return <Badge variant="secondary" className="bg-purple-100 text-purple-800 border-purple-200">Alternatives Proposed</Badge>;
      case "APPROVED":
        return <Badge variant="default" className="bg-emerald-600 text-white">Approved & Published</Badge>;
      case "REJECTED":
        return <Badge variant="danger">Rejected</Badge>;
      case "CANCELLED":
        return <Badge variant="secondary" className="text-slate-500">Cancelled</Badge>;
      default:
        return <Badge variant="secondary">{status}</Badge>;
    }
  };

  return (
    <div className="min-h-screen bg-surface-canvas p-6 lg:p-8">
      {/* Header */}
      <div className="max-w-7xl mx-auto mb-8 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2">
            <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-primary/10 text-primary uppercase tracking-wider">
              Governance & Workflow
            </span>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-100 text-slate-700">
              FR-08 / FR-09 / FR-10
            </span>
          </div>
          <h1 className="text-2xl font-bold text-navy mt-1">Timetable Change Requests & Approvals</h1>
          <p className="text-sm text-text-secondary mt-1">
            Submit formal reschedule proposals, generate OR-Tools CP-SAT alternatives, review trade-offs, and publish revalidated timetable versions.
          </p>
        </div>

        <div className="flex items-center space-x-3">
          <Link href="/simulator">
            <Button variant="outline" size="sm">
              <Cpu className="w-4 h-4 mr-1.5" />
              What-If Simulator
            </Button>
          </Link>
          <Button size="sm" onClick={() => setShowSubmitModal(true)}>
            <PlusCircle className="w-4 h-4 mr-1.5" />
            Submit Change Request
          </Button>
        </div>
      </div>

      {/* Messages */}
      {errorMsg && (
        <div className="max-w-7xl mx-auto mb-6 p-4 bg-red-50 border border-red-200 rounded-lg text-xs text-red-700 flex items-center justify-between">
          <div className="flex items-center">
            <XCircle className="w-4 h-4 mr-2 flex-shrink-0" />
            {errorMsg}
          </div>
          <button onClick={() => setErrorMsg(null)} className="text-red-500 hover:text-red-700 font-bold">&times;</button>
        </div>
      )}

      {successMsg && (
        <div className="max-w-7xl mx-auto mb-6 p-4 bg-emerald-50 border border-emerald-200 rounded-lg text-xs text-emerald-800 flex items-center justify-between">
          <div className="flex items-center">
            <CheckCircle className="w-4 h-4 mr-2 flex-shrink-0" />
            {successMsg}
          </div>
          <button onClick={() => setSuccessMsg(null)} className="text-emerald-600 hover:text-emerald-800 font-bold">&times;</button>
        </div>
      )}

      <div className="max-w-7xl mx-auto space-y-6">
        {/* Filter Controls */}
        <div className="flex items-center justify-between bg-white p-3 rounded-lg border border-surface-border">
          <div className="flex items-center space-x-2">
            <Filter className="w-4 h-4 text-text-secondary" />
            <span className="text-xs font-semibold text-navy">Filter Status:</span>
            {["ALL", "SUBMITTED", "UNDER_REVIEW", "ALTERNATIVES_PROPOSED", "APPROVED", "REJECTED"].map((st) => (
              <button
                key={st}
                onClick={() => setStatusFilter(st)}
                className={`text-xs px-2.5 py-1 rounded transition-colors ${
                  statusFilter === st
                    ? "bg-primary text-white font-semibold"
                    : "text-text-secondary hover:bg-slate-100"
                }`}
              >
                {st.replace("_", " ")}
              </button>
            ))}
          </div>

          <Button variant="outline" size="sm" onClick={fetchRequests} className="text-xs h-7">
            <RefreshCw className="w-3.5 h-3.5 mr-1" /> Refresh
          </Button>
        </div>

        {/* Requests List */}
        {loading ? (
          <div className="text-center py-16">
            <RefreshCw className="w-8 h-8 mx-auto text-primary animate-spin" />
            <p className="text-xs text-text-secondary mt-2">Loading change requests...</p>
          </div>
        ) : requests.length === 0 ? (
          <Card className="border-dashed border-2 border-surface-border text-center py-16">
            <CardContent className="space-y-3">
              <FileText className="w-10 h-10 mx-auto text-text-secondary opacity-60" />
              <h3 className="font-semibold text-navy text-base">No Change Requests Found</h3>
              <p className="text-xs text-text-secondary max-w-sm mx-auto">
                No change requests match the current filter. Submit a new change request to initiate the approval lifecycle.
              </p>
              <Button size="sm" onClick={() => setShowSubmitModal(true)}>
                Submit New Request
              </Button>
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-4">
            {requests.map((req) => (
              <Card key={req.id} className="border-surface-border shadow-sm overflow-hidden">
                <div className="p-5">
                  <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3 border-b border-surface-border/60 pb-3">
                    <div>
                      <div className="flex items-center space-x-2">
                        <span className="text-xs font-mono font-bold text-text-secondary">REQ-{req.id.substring(0, 8)}</span>
                        {getStatusBadge(req.status)}
                        <span className="text-xs text-text-secondary">
                          Submitted by <b>{req.requester_name}</b> on {new Date(req.created_at).toLocaleDateString()}
                        </span>
                      </div>
                      <h3 className="text-sm font-bold text-navy mt-1">
                        {req.request_type.replace("_", " ")}: {req.reason}
                      </h3>
                    </div>

                    <div className="flex items-center space-x-2">
                      {/* Coordinator Review Action */}
                      {isCoordinator && (req.status === "SUBMITTED" || req.status === "UNDER_REVIEW") && (
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={reviewingId === req.id}
                          onClick={() => handleReview(req.id)}
                          className="text-xs h-8"
                        >
                          {reviewingId === req.id ? (
                            <RefreshCw className="w-3.5 h-3.5 mr-1 animate-spin" />
                          ) : (
                            <Cpu className="w-3.5 h-3.5 mr-1 text-primary" />
                          )}
                          Review & Propose Alternatives
                        </Button>
                      )}

                      {/* HOD / Admin Decision Actions */}
                      {isHodOrAdmin && (req.status === "ALTERNATIVES_PROPOSED" || req.status === "UNDER_REVIEW" || req.status === "SUBMITTED") && (
                        <>
                          <Button
                            size="sm"
                            onClick={() => handleOpenDecision(req, "APPROVED")}
                            className="text-xs h-8 bg-emerald-600 hover:bg-emerald-700 text-white"
                          >
                            <ThumbsUp className="w-3.5 h-3.5 mr-1" />
                            Approve Change
                          </Button>
                          <Button
                            size="sm"
                            variant="danger"
                            onClick={() => handleOpenDecision(req, "REJECTED")}
                            className="text-xs h-8"
                          >
                            <ThumbsDown className="w-3.5 h-3.5 mr-1" />
                            Reject
                          </Button>
                        </>
                      )}

                      {/* Requester Cancel Action */}
                      {user && user.id === req.requester_user_id && ["SUBMITTED", "UNDER_REVIEW"].includes(req.status) && (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handleCancelRequest(req.id)}
                          className="text-xs h-8 text-red-600 hover:bg-red-50"
                        >
                          Cancel
                        </Button>
                      )}
                    </div>
                  </div>

                  {/* Decision summary if reviewed */}
                  {req.reviewed_at && (
                    <div className="mt-3 p-3 bg-slate-50 border border-slate-200 rounded text-xs text-text-secondary flex items-start space-x-2">
                      <UserCheck className="w-4 h-4 text-primary flex-shrink-0 mt-0.5" />
                      <div>
                        <span className="font-semibold text-navy">Decision Record: </span>
                        Reviewed by <b>{req.reviewer_name}</b> on {new Date(req.reviewed_at).toLocaleString()}.
                        <p className="mt-0.5 text-text-main font-medium italic">&quot;{req.review_decision_reason}&quot;</p>
                      </div>
                    </div>
                  )}

                  {/* Alternatives List */}
                  {req.alternatives && req.alternatives.length > 0 && (
                    <div className="mt-4 pt-3 border-t border-surface-border/60">
                      <h4 className="text-xs font-bold text-navy uppercase tracking-wider mb-2 flex items-center">
                        <Cpu className="w-3.5 h-3.5 mr-1 text-primary" />
                        Generated Alternatives ({req.alternatives.length})
                      </h4>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        {req.alternatives.map((alt) => (
                          <div
                            key={alt.id}
                            className={`p-3 rounded-lg border text-xs ${
                              alt.is_selected
                                ? "border-emerald-500 bg-emerald-50 ring-1 ring-emerald-400"
                                : "border-surface-border bg-white"
                            }`}
                          >
                            <div className="flex items-center justify-between font-semibold text-navy mb-1">
                              <span>Option Rank #{alt.option_rank}</span>
                              <span className="text-[11px] text-text-secondary">
                                Penalty: {alt.soft_penalty_score}
                              </span>
                            </div>
                            <div className="text-text-secondary space-y-0.5">
                              <div>Slot: <b>{alt.proposed_time_slot_name}</b></div>
                              <div>Room: <b>{alt.proposed_room_number}</b></div>
                              <div>Teacher: <b>{alt.proposed_teacher_name}</b></div>
                            </div>
                            {alt.trade_off_explanation && (
                              <div className="mt-2 pt-1 border-t border-surface-border/50 text-[11px] text-text-secondary italic">
                                {alt.trade_off_explanation.summary || "Feasible alternative with minimal disruption."}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </Card>
            ))}
          </div>
        )}
      </div>

      {/* Submit Change Request Modal */}
      {showSubmitModal && (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-lg w-full p-6 space-y-4">
            <div className="flex items-center justify-between border-b pb-3">
              <h3 className="font-bold text-base text-navy flex items-center">
                <Send className="w-4 h-4 mr-2 text-primary" />
                Submit Timetable Change Request
              </h3>
              <button
                onClick={() => setShowSubmitModal(false)}
                className="text-text-secondary hover:text-navy font-bold text-lg"
              >
                &times;
              </button>
            </div>

            <form onSubmit={handleSubmitRequest} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-navy mb-1">Select Timetable</label>
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
                <label className="block text-xs font-medium text-navy mb-1">Select Session to Reschedule</label>
                <select
                  value={selectedSessionId}
                  onChange={(e) => setSelectedSessionId(e.target.value)}
                  className="w-full text-xs rounded-md border border-surface-border bg-white px-3 py-2 text-text-main focus:outline-none focus:ring-1 focus:ring-primary"
                >
                  {timetableSessions.length === 0 ? (
                    <option value="">No sessions loaded</option>
                  ) : (
                    timetableSessions.map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.label}
                      </option>
                    ))
                  )}
                </select>
              </div>

              <div>
                <label className="block text-xs font-medium text-navy mb-1">Request Type</label>
                <select
                  value={requestType}
                  onChange={(e) => setRequestType(e.target.value)}
                  className="w-full text-xs rounded-md border border-surface-border bg-white px-3 py-2 text-text-main focus:outline-none focus:ring-1 focus:ring-primary"
                >
                  <option value="RESCHEDULE_SESSION">Reschedule Session Time Slot</option>
                  <option value="SWAP_ROOM">Relocate to Alternative Room</option>
                  <option value="SWAP_TEACHER">Assign Substitute Faculty</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-medium text-navy mb-1">
                  Justification / Rationale (Required)
                </label>
                <textarea
                  rows={3}
                  required
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  className="w-full text-xs rounded-md border border-surface-border bg-white p-3 text-text-main focus:outline-none focus:ring-1 focus:ring-primary"
                  placeholder="Provide clear educational rationale (e.g., Guest lecture conflict, lab maintenance, conference attendance)..."
                />
              </div>

              <div className="flex items-center justify-end space-x-2 pt-2">
                <Button type="button" variant="outline" size="sm" onClick={() => setShowSubmitModal(false)}>
                  Cancel
                </Button>
                <Button type="submit" size="sm" disabled={submitting}>
                  {submitting ? "Submitting..." : "Submit Proposal"}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Decision Modal (Approval or Rejection) */}
      {decisionModalOpen && activeRequest && (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-lg w-full p-6 space-y-4">
            <div className="flex items-center justify-between border-b pb-3">
              <h3 className="font-bold text-base text-navy flex items-center">
                {decisionType === "APPROVED" ? (
                  <>
                    <ThumbsUp className="w-4 h-4 mr-2 text-emerald-600" />
                    Authorize & Publish Change
                  </>
                ) : (
                  <>
                    <ThumbsDown className="w-4 h-4 mr-2 text-red-600" />
                    Reject Change Proposal
                  </>
                )}
              </h3>
              <button
                onClick={() => setDecisionModalOpen(false)}
                className="text-text-secondary hover:text-navy font-bold text-lg"
              >
                &times;
              </button>
            </div>

            <form onSubmit={handleExecuteDecision} className="space-y-4">
              {decisionType === "APPROVED" && activeRequest.alternatives && activeRequest.alternatives.length > 0 && (
                <div>
                  <label className="block text-xs font-medium text-navy mb-1">
                    Select Alternative Option to Commit
                  </label>
                  <select
                    value={selectedAltId}
                    onChange={(e) => setSelectedAltId(e.target.value)}
                    className="w-full text-xs rounded-md border border-surface-border bg-white px-3 py-2 text-text-main focus:outline-none focus:ring-1 focus:ring-primary"
                  >
                    {activeRequest.alternatives.map((alt) => (
                      <option key={alt.id} value={alt.id}>
                        Rank #{alt.option_rank}: {alt.proposed_time_slot_name} in {alt.proposed_room_number} (Penalty: {alt.soft_penalty_score})
                      </option>
                    ))}
                  </select>
                </div>
              )}

              <div>
                <label className="block text-xs font-medium text-navy mb-1">
                  Formal Reviewer Decision Comments (Required)
                </label>
                <textarea
                  rows={3}
                  required
                  value={decisionReason}
                  onChange={(e) => setDecisionReason(e.target.value)}
                  className="w-full text-xs rounded-md border border-surface-border bg-white p-3 text-text-main focus:outline-none focus:ring-1 focus:ring-primary"
                  placeholder="Record justification for audit trail (e.g., Approved following departmental review; verified no conflicting cohorts)..."
                />
              </div>

              {decisionType === "APPROVED" && (
                <div className="p-3 bg-emerald-50 border border-emerald-200 rounded text-[11px] text-emerald-800 space-y-1">
                  <div className="font-semibold flex items-center">
                    <Shield className="w-3.5 h-3.5 mr-1" />
                    Automatic Revalidation & Versioning Sequence
                  </div>
                  <p>
                    1. Revalidates entire timetable with independent constraint validator before write.
                  </p>
                  <p>
                    2. Creates new immutable version, archives old version, and sends targeted privacy-masked notifications.
                  </p>
                </div>
              )}

              <div className="flex items-center justify-end space-x-2 pt-2">
                <Button type="button" variant="outline" size="sm" onClick={() => setDecisionModalOpen(false)}>
                  Cancel
                </Button>
                <Button
                  type="submit"
                  size="sm"
                  disabled={deciding}
                  className={decisionType === "APPROVED" ? "bg-emerald-600 hover:bg-emerald-700 text-white" : "bg-red-600 hover:bg-red-700 text-white"}
                >
                  {deciding ? "Processing..." : decisionType === "APPROVED" ? "Authorize & Publish" : "Reject Proposal"}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
