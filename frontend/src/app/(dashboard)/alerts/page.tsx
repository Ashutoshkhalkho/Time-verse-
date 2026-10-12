"use client";

import React, { useEffect, useState, useMemo } from "react";
import Link from "next/link";
import { useAuth } from "@/context/AuthContext";
import { apiRequest } from "@/lib/api";
import {
  AlertTriangle,
  Bell,
  CheckCircle,
  Clock,
  Cpu,
  Filter,
  Flame,
  Info,
  Mail,
  RefreshCw,
  Search,
  Send,
  ShieldAlert,
  Smartphone,
  UserCheck,
  Users,
  XCircle,
  ChevronRight,
  Sparkles,
  ArrowRight,
  Layers,
  FileText
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

interface AlertDeliveryAttempt {
  channel: string;
  recipient_id: string;
  status: "DELIVERED" | "FAILED" | "PENDING";
  attempted_at: string;
  error?: string;
}

interface AlertItem {
  id: string;
  user_id: string;
  session_id?: string;
  title: string;
  message: string;
  severity: "INFO" | "WARNING" | "CRITICAL";
  is_read: boolean;
  created_at: string;
  category: "CONFLICT" | "TIMETABLE_CHANGE" | "EMERGENCY" | "ADMINISTRATIVE" | "OFFICIAL_BROADCAST";
  resolution_status: "PENDING" | "UNDER_REVIEW" | "RESOLVED";
  resolved_at?: string;
  resolution_notes?: string;
  channels_sent?: string[];
  delivery_attempts?: AlertDeliveryAttempt[];
  recipients_count?: number;
  metadata?: Record<string, any>;
}

export default function AlertsHubPage() {
  const { user } = useAuth();
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [selectedCategory, setSelectedCategory] = useState<string>("ALL");
  const [selectedStatus, setSelectedStatus] = useState<string>("ALL");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [refreshing, setRefreshing] = useState<boolean>(false);
  const [actionInProgress, setActionInProgress] = useState<string | null>(null);
  const [notificationMsg, setNotificationMsg] = useState<{ text: string; type: "success" | "error" } | null>(null);

  // Resolution modal state
  const [resolvingAlert, setResolvingAlert] = useState<AlertItem | null>(null);
  const [resolutionNotes, setResolutionNotes] = useState<string>("");
  const [submittingResolution, setSubmittingResolution] = useState<boolean>(false);

  // Emergency dispatch modal state (HOD / Admin only)
  const [showDispatchModal, setShowDispatchModal] = useState<boolean>(false);
  const [dispatchCategory, setDispatchCategory] = useState<string>("EMERGENCY");
  const [dispatchTitle, setDispatchTitle] = useState<string>("");
  const [dispatchMessage, setDispatchMessage] = useState<string>("");
  const [dispatchSeverity, setDispatchSeverity] = useState<"INFO" | "WARNING" | "CRITICAL">("CRITICAL");
  const [dispatching, setDispatching] = useState<boolean>(false);

  const isHodOrAdmin = Boolean(user && ["ADMIN", "HOD", "COORDINATOR"].includes(user.role));

  const fetchAlerts = async () => {
    try {
      setRefreshing(true);
      let queryUrl = "/alerts";
      const params = new URLSearchParams();
      if (selectedCategory !== "ALL") {
        params.append("category", selectedCategory);
      }
      if (selectedStatus !== "ALL") {
        params.append("resolution_status", selectedStatus);
      }
      const qs = params.toString();
      if (qs) queryUrl += `?${qs}`;

      const data: any = await apiRequest(queryUrl);
      setAlerts(Array.isArray(data) ? data : []);
    } catch (err: any) {
      console.error("Failed to load alerts:", err);
      setNotificationMsg({ text: err.detail || "Failed to load alerts.", type: "error" });
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchAlerts();
  }, [selectedCategory, selectedStatus]);

  // Handle Mark as Read
  const handleMarkAsRead = async (alertId: string) => {
    try {
      setActionInProgress(alertId);
      await apiRequest(`/alerts/${alertId}/read`, { method: "PATCH" });
      setAlerts((prev) =>
        prev.map((a) => (a.id === alertId ? { ...a, is_read: true } : a))
      );
      setNotificationMsg({ text: "Alert marked as read.", type: "success" });
    } catch (e: any) {
      setNotificationMsg({ text: e.detail || "Failed to mark as read.", type: "error" });
    } finally {
      setActionInProgress(null);
    }
  };

  // Handle Investigation / Under Review
  const handleSetUnderReview = async (alertId: string) => {
    try {
      setActionInProgress(alertId);
      await apiRequest(`/alerts/${alertId}/resolution`, {
        method: "PATCH",
        body: JSON.stringify({
          resolution_status: "UNDER_REVIEW",
          resolution_notes: `Investigation initiated by ${user?.full_name || "Faculty"}`
        })
      });
      setAlerts((prev) =>
        prev.map((a) =>
          a.id === alertId ? { ...a, resolution_status: "UNDER_REVIEW" } : a
        )
      );
      setNotificationMsg({ text: "Alert status updated to Under Review.", type: "success" });
    } catch (e: any) {
      setNotificationMsg({ text: e.detail || "Failed to update alert resolution.", type: "error" });
    } finally {
      setActionInProgress(null);
    }
  };

  // Submit Resolution Modal
  const handleSubmitResolution = async () => {
    if (!resolvingAlert) return;
    try {
      setSubmittingResolution(true);
      await apiRequest(`/alerts/${resolvingAlert.id}/resolution`, {
        method: "PATCH",
        body: JSON.stringify({
          resolution_status: "RESOLVED",
          resolution_notes: resolutionNotes || "Resolved after timetable adjustment"
        })
      });
      setAlerts((prev) =>
        prev.map((a) =>
          a.id === resolvingAlert.id
            ? { ...a, resolution_status: "RESOLVED", resolution_notes: resolutionNotes, resolved_at: new Date().toISOString() }
            : a
        )
      );
      setResolvingAlert(null);
      setResolutionNotes("");
      setNotificationMsg({ text: "Alert successfully marked as Resolved.", type: "success" });
    } catch (e: any) {
      setNotificationMsg({ text: e.detail || "Failed to resolve alert.", type: "error" });
    } finally {
      setSubmittingResolution(false);
    }
  };

  // Handle Channel Delivery Retry
  const handleRetryChannel = async (alertId: string, channel: string) => {
    try {
      setActionInProgress(`${alertId}-${channel}`);
      const res: any = await apiRequest(`/alerts/${alertId}/retry`, {
        method: "POST",
        body: JSON.stringify({ channel })
      });
      setNotificationMsg({
        text: res.message || `Retried ${channel} notification delivery successfully.`,
        type: "success"
      });
      fetchAlerts();
    } catch (e: any) {
      setNotificationMsg({ text: e.detail || "Failed to retry delivery.", type: "error" });
    } finally {
      setActionInProgress(null);
    }
  };

  // Handle Dispatch Emergency / Broadcast
  const handleDispatchEmergency = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!dispatchTitle || !dispatchMessage) return;
    try {
      setDispatching(true);
      const res: any = await apiRequest("/alerts/trigger-workflow-event", {
        method: "POST",
        body: JSON.stringify({
          event_type: "MANUAL_BROADCAST",
          category: dispatchCategory,
          severity: dispatchSeverity,
          message: `${dispatchTitle}: ${dispatchMessage}`,
          metadata: {
            title: dispatchTitle,
            body: dispatchMessage,
            dispatched_by: user?.email,
            institution: "Kristu Jayanti University - Department of Professional Management Studies"
          }
        })
      });
      setNotificationMsg({
        text: `Emergency event dispatched! ${res.recipients_identified_count || 1} recipients notified across channels.`,
        type: "success"
      });
      setShowDispatchModal(false);
      setDispatchTitle("");
      setDispatchMessage("");
      fetchAlerts();
    } catch (e: any) {
      setNotificationMsg({ text: e.detail || "Failed to dispatch broadcast.", type: "error" });
    } finally {
      setDispatching(false);
    }
  };

  // Computed metrics
  const pendingCount = alerts.filter((a) => a.resolution_status === "PENDING").length;
  const underReviewCount = alerts.filter((a) => a.resolution_status === "UNDER_REVIEW").length;
  const resolvedCount = alerts.filter((a) => a.resolution_status === "RESOLVED").length;
  const criticalCount = alerts.filter((a) => a.severity === "CRITICAL").length;

  // Filtered alert list
  const filteredAlerts = useMemo(() => {
    return alerts.filter((a) => {
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const matchesTitle = a.title?.toLowerCase().includes(q);
        const matchesMessage = a.message?.toLowerCase().includes(q);
        const matchesNotes = a.resolution_notes?.toLowerCase().includes(q);
        if (!matchesTitle && !matchesMessage && !matchesNotes) return false;
      }
      return true;
    });
  }, [alerts, searchQuery]);

  return (
    <div className="space-y-6 pb-16">
      {/* Top Academic Banner */}
      <div className="bg-white rounded-xl border border-[#E2E7EE] p-5 sm:p-6 shadow-xs flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2">
            <span className="text-xs font-bold uppercase tracking-wider text-[#1261A0] bg-[#EAF3FB] px-2.5 py-0.5 rounded">
              Kristu Jayanti University • DPMS
            </span>
            <span className="text-xs font-semibold px-2 py-0.5 rounded bg-emerald-100 text-emerald-800">
              Live Alert Engine
            </span>
          </div>
          <h1 className="text-xl sm:text-2xl font-bold text-[#17324D] mt-1">
            Department Alert & Smart Notification Hub
          </h1>
          <p className="text-xs sm:text-sm text-[#697586] mt-0.5">
            5-Stage Event-Driven Lifecycle: Event Occurs → Alert Engine → Identifies Recipients → Sends Notification → Tracks Resolution.
          </p>
        </div>

        <div className="flex items-center gap-2.5 flex-wrap">
          <Button
            onClick={fetchAlerts}
            disabled={refreshing}
            variant="outline"
            size="sm"
            className="text-xs h-8 border-[#E2E7EE]"
          >
            <RefreshCw className={`w-3.5 h-3.5 mr-1.5 ${refreshing ? "animate-spin" : ""}`} />
            Refresh Feed
          </Button>

          {isHodOrAdmin && (
            <Button
              onClick={() => setShowDispatchModal(true)}
              size="sm"
              className="text-xs h-8 bg-rose-600 hover:bg-rose-700 text-white shadow-xs"
            >
              <Flame className="w-3.5 h-3.5 mr-1.5" />
              Dispatch Emergency Alert
            </Button>
          )}

          <Link href="/timetables">
            <Button size="sm" variant="outline" className="text-xs h-8">
              <Layers className="w-3.5 h-3.5 mr-1.5 text-[#1261A0]" />
              Timetable Planner
            </Button>
          </Link>
        </div>
      </div>

      {/* Global Notifications Toast */}
      {notificationMsg && (
        <div
          className={`p-3.5 rounded-lg text-xs font-medium flex items-center justify-between ${
            notificationMsg.type === "success"
              ? "bg-emerald-50 text-emerald-800 border border-emerald-200"
              : "bg-rose-50 text-rose-800 border border-rose-200"
          }`}
        >
          <span>{notificationMsg.text}</span>
          <button
            onClick={() => setNotificationMsg(null)}
            className="text-slate-400 hover:text-slate-600 font-bold ml-3"
          >
            ✕
          </button>
        </div>
      )}

      {/* WORKFLOW LIFECYCLE PROGRESS PIPELINE BANNER */}
      <Card className="border-[#E2E7EE] shadow-xs bg-linear-to-r from-blue-50/50 via-indigo-50/30 to-purple-50/50">
        <CardHeader className="py-3 px-5 border-b border-[#E2E7EE]/60">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <Sparkles className="w-4 h-4 text-[#1261A0]" />
              <CardTitle className="text-xs font-bold uppercase tracking-wider text-[#17324D]">
                Active Notification Lifecycle Architecture
              </CardTitle>
            </div>
            <span className="text-[11px] text-[#697586] font-medium">
              Zero duplicate ripple alerts • Multi-channel verification
            </span>
          </div>
        </CardHeader>
        <CardContent className="p-4 sm:p-5">
          <div className="grid grid-cols-1 md:grid-cols-5 gap-3 items-center">
            {/* Stage 1 */}
            <div className="p-3 rounded-lg bg-white border border-[#E2E7EE] shadow-2xs">
              <div className="flex items-center justify-between text-xs font-semibold text-slate-500 mb-1">
                <span>Stage 1</span>
                <Clock className="w-3.5 h-3.5 text-blue-500" />
              </div>
              <div className="text-xs font-bold text-[#17324D]">Event Occurs</div>
              <p className="text-[10px] text-[#697586] mt-0.5">Clashes, leave, room reassignment or timetable publish</p>
            </div>

            {/* Stage 2 */}
            <div className="p-3 rounded-lg bg-white border border-blue-200 shadow-2xs relative">
              <div className="flex items-center justify-between text-xs font-semibold text-blue-600 mb-1">
                <span>Stage 2</span>
                <Cpu className="w-3.5 h-3.5 text-[#1261A0]" />
              </div>
              <div className="text-xs font-bold text-[#17324D]">Alert Engine</div>
              <p className="text-[10px] text-[#697586] mt-0.5">Deduplication, 4-tier categorisation & severity scoring</p>
            </div>

            {/* Stage 3 */}
            <div className="p-3 rounded-lg bg-white border border-[#E2E7EE] shadow-2xs">
              <div className="flex items-center justify-between text-xs font-semibold text-slate-500 mb-1">
                <span>Stage 3</span>
                <Users className="w-3.5 h-3.5 text-indigo-500" />
              </div>
              <div className="text-xs font-bold text-[#17324D]">Identifies Recipients</div>
              <p className="text-[10px] text-[#697586] mt-0.5">Scopes HOD, affected teachers, students & section CRs</p>
            </div>

            {/* Stage 4 */}
            <div className="p-3 rounded-lg bg-white border border-[#E2E7EE] shadow-2xs">
              <div className="flex items-center justify-between text-xs font-semibold text-slate-500 mb-1">
                <span>Stage 4</span>
                <Send className="w-3.5 h-3.5 text-emerald-500" />
              </div>
              <div className="text-xs font-bold text-[#17324D]">Sends Notification</div>
              <p className="text-[10px] text-[#697586] mt-0.5">In-app, verified SMTP email & push with failure audit</p>
            </div>

            {/* Stage 5 */}
            <div className="p-3 rounded-lg bg-white border border-emerald-200 bg-emerald-50/20 shadow-2xs">
              <div className="flex items-center justify-between text-xs font-semibold text-emerald-700 mb-1">
                <span>Stage 5</span>
                <CheckCircle className="w-3.5 h-3.5 text-emerald-600" />
              </div>
              <div className="text-xs font-bold text-[#17324D]">Tracks Resolution</div>
              <p className="text-[10px] text-[#697586] mt-0.5">Pending ➔ Under Review ➔ Resolved with audit notes</p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* KPI METRIC CARDS */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 sm:gap-4">
        <div className="bg-white p-4 rounded-xl border border-[#E2E7EE] shadow-2xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-[#697586]">Pending Action</span>
            <AlertTriangle className="w-4 h-4 text-amber-500" />
          </div>
          <div className="text-2xl font-bold text-[#17324D] mt-1">{pendingCount}</div>
          <span className="text-[10px] text-amber-700 font-medium">Awaiting coordinator review</span>
        </div>

        <div className="bg-white p-4 rounded-xl border border-[#E2E7EE] shadow-2xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-[#697586]">Under Review</span>
            <Clock className="w-4 h-4 text-blue-500" />
          </div>
          <div className="text-2xl font-bold text-[#17324D] mt-1">{underReviewCount}</div>
          <span className="text-[10px] text-blue-700 font-medium">Active investigation</span>
        </div>

        <div className="bg-white p-4 rounded-xl border border-[#E2E7EE] shadow-2xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-[#697586]">Resolved Alerts</span>
            <CheckCircle className="w-4 h-4 text-emerald-500" />
          </div>
          <div className="text-2xl font-bold text-[#17324D] mt-1">{resolvedCount}</div>
          <span className="text-[10px] text-emerald-700 font-medium">Changes applied & confirmed</span>
        </div>

        <div className="bg-white p-4 rounded-xl border border-[#E2E7EE] shadow-2xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-[#697586]">Critical / Emergency</span>
            <Flame className="w-4 h-4 text-rose-500" />
          </div>
          <div className="text-2xl font-bold text-[#17324D] mt-1">{criticalCount}</div>
          <span className="text-[10px] text-rose-700 font-medium">High priority notices</span>
        </div>
      </div>

      {/* MAIN ALERTS EXPLORER & CONTROLS */}
      <div className="bg-white rounded-xl border border-[#E2E7EE] shadow-xs overflow-hidden">
        {/* Category Filters Bar */}
        <div className="p-4 border-b border-[#E2E7EE] flex flex-wrap items-center justify-between gap-3 bg-[#F7F9FC]">
          <div className="flex items-center gap-1.5 flex-wrap">
            <button
              onClick={() => setSelectedCategory("ALL")}
              className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-colors ${
                selectedCategory === "ALL"
                  ? "bg-[#1261A0] text-white shadow-xs font-bold"
                  : "bg-white text-slate-700 border border-[#E2E7EE] hover:bg-slate-50"
              }`}
            >
              All Alerts ({alerts.length})
            </button>
            <button
              onClick={() => setSelectedCategory("CONFLICT")}
              className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-colors flex items-center ${
                selectedCategory === "CONFLICT"
                  ? "bg-amber-600 text-white shadow-xs font-bold"
                  : "bg-white text-amber-800 border border-amber-200 hover:bg-amber-50"
              }`}
            >
              <AlertTriangle className="w-3.5 h-3.5 mr-1" />
              Category A: Conflicts
            </button>
            <button
              onClick={() => setSelectedCategory("TIMETABLE_CHANGE")}
              className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-colors flex items-center ${
                selectedCategory === "TIMETABLE_CHANGE"
                  ? "bg-blue-600 text-white shadow-xs font-bold"
                  : "bg-white text-blue-800 border border-blue-200 hover:bg-blue-50"
              }`}
            >
              <RefreshCw className="w-3.5 h-3.5 mr-1" />
              Category B: Timetable Changes
            </button>
            <button
              onClick={() => setSelectedCategory("EMERGENCY")}
              className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-colors flex items-center ${
                selectedCategory === "EMERGENCY"
                  ? "bg-rose-600 text-white shadow-xs font-bold"
                  : "bg-white text-rose-800 border border-rose-200 hover:bg-rose-50"
              }`}
            >
              <Flame className="w-3.5 h-3.5 mr-1" />
              Category C: Emergency
            </button>
            <button
              onClick={() => setSelectedCategory("ADMINISTRATIVE")}
              className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-colors flex items-center ${
                selectedCategory === "ADMINISTRATIVE"
                  ? "bg-purple-600 text-white shadow-xs font-bold"
                  : "bg-white text-purple-800 border border-purple-200 hover:bg-purple-50"
              }`}
            >
              <ShieldAlert className="w-3.5 h-3.5 mr-1" />
              Category D: Administrative
            </button>
          </div>

          {/* Search Box */}
          <div className="relative w-full sm:w-64">
            <Search className="w-3.5 h-3.5 absolute left-3 top-2.5 text-slate-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search alerts or classes..."
              className="w-full pl-8 pr-3 py-1.5 text-xs rounded-lg border border-[#E2E7EE] focus:outline-hidden focus:border-[#1261A0] bg-white"
            />
          </div>
        </div>

        {/* Status Sub-filter Bar */}
        <div className="px-4 py-2.5 border-b border-[#E2E7EE] bg-white flex items-center justify-between text-xs">
          <div className="flex items-center space-x-2">
            <span className="font-semibold text-slate-500 uppercase tracking-wider text-[11px]">Resolution Status:</span>
            <div className="inline-flex rounded-lg border border-[#E2E7EE] p-0.5 bg-[#F7F9FC]">
              <button
                onClick={() => setSelectedStatus("ALL")}
                className={`px-2.5 py-1 text-xs font-semibold rounded-md transition-colors ${
                  selectedStatus === "ALL" ? "bg-white text-[#1261A0] shadow-2xs font-bold" : "text-slate-600"
                }`}
              >
                All
              </button>
              <button
                onClick={() => setSelectedStatus("PENDING")}
                className={`px-2.5 py-1 text-xs font-semibold rounded-md transition-colors ${
                  selectedStatus === "PENDING" ? "bg-white text-amber-700 shadow-2xs font-bold" : "text-slate-600"
                }`}
              >
                Pending
              </button>
              <button
                onClick={() => setSelectedStatus("UNDER_REVIEW")}
                className={`px-2.5 py-1 text-xs font-semibold rounded-md transition-colors ${
                  selectedStatus === "UNDER_REVIEW" ? "bg-white text-blue-700 shadow-2xs font-bold" : "text-slate-600"
                }`}
              >
                Under Review
              </button>
              <button
                onClick={() => setSelectedStatus("RESOLVED")}
                className={`px-2.5 py-1 text-xs font-semibold rounded-md transition-colors ${
                  selectedStatus === "RESOLVED" ? "bg-white text-emerald-700 shadow-2xs font-bold" : "text-slate-600"
                }`}
              >
                Resolved
              </button>
            </div>
          </div>

          <span className="text-[11px] text-slate-500">
            Showing <b>{filteredAlerts.length}</b> events
          </span>
        </div>

        {/* ALERTS FEED LIST */}
        <div className="divide-y divide-[#E2E7EE]">
          {loading ? (
            <div className="p-16 text-center">
              <div className="inline-block animate-spin rounded-full h-7 w-7 border-4 border-slate-200 border-t-[#1261A0] mb-2"></div>
              <p className="text-xs font-semibold text-[#697586]">Querying alert lifecycle records...</p>
            </div>
          ) : filteredAlerts.length === 0 ? (
            <div className="p-12 text-center">
              <CheckCircle className="w-10 h-10 text-emerald-500 mx-auto mb-2 opacity-80" />
              <h4 className="text-sm font-bold text-[#17324D]">No Alerts Found</h4>
              <p className="text-xs text-[#697586] mt-1 max-w-sm mx-auto">
                No active conflicts or emergency alerts match the selected filter criteria. All timetables operate under normal parameters.
              </p>
            </div>
          ) : (
            filteredAlerts.map((alert) => {
              const isPending = alert.resolution_status === "PENDING";
              const isUnderReview = alert.resolution_status === "UNDER_REVIEW";
              const isResolved = alert.resolution_status === "RESOLVED";

              return (
                <div
                  key={alert.id}
                  className={`p-4 sm:p-5 transition-colors ${
                    !alert.is_read ? "bg-blue-50/25" : "bg-white"
                  } hover:bg-slate-50/70`}
                >
                  <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
                    {/* Left details */}
                    <div className="space-y-1.5 max-w-3xl">
                      <div className="flex items-center space-x-2 flex-wrap">
                        {/* Category badge */}
                        <span
                          className={`text-[10px] font-bold px-2 py-0.5 rounded tracking-wide ${
                            alert.category === "CONFLICT"
                              ? "bg-amber-100 text-amber-900 border border-amber-300"
                              : alert.category === "TIMETABLE_CHANGE"
                              ? "bg-blue-100 text-blue-900 border border-blue-300"
                              : alert.category === "EMERGENCY"
                              ? "bg-rose-100 text-rose-900 border border-rose-300"
                              : "bg-purple-100 text-purple-900 border border-purple-300"
                          }`}
                        >
                          {alert.category}
                        </span>

                        {/* Severity badge */}
                        <span
                          className={`text-[10px] font-bold px-2 py-0.5 rounded ${
                            alert.severity === "CRITICAL"
                              ? "bg-rose-600 text-white"
                              : alert.severity === "WARNING"
                              ? "bg-amber-500 text-white"
                              : "bg-slate-200 text-slate-700"
                          }`}
                        >
                          {alert.severity}
                        </span>

                        {/* Resolution status badge */}
                        <span
                          className={`text-[10px] font-semibold px-2 py-0.5 rounded inline-flex items-center ${
                            isPending
                              ? "bg-amber-50 text-amber-800 border border-amber-200"
                              : isUnderReview
                              ? "bg-blue-50 text-blue-800 border border-blue-200"
                              : "bg-emerald-50 text-emerald-800 border border-emerald-200"
                          }`}
                        >
                          {isPending && <Clock className="w-3 h-3 mr-1 text-amber-600" />}
                          {isUnderReview && <RefreshCw className="w-3 h-3 mr-1 text-blue-600" />}
                          {isResolved && <CheckCircle className="w-3 h-3 mr-1 text-emerald-600" />}
                          {alert.resolution_status}
                        </span>

                        {!alert.is_read && (
                          <span className="text-[9px] font-bold px-1.5 py-0.2 rounded bg-blue-500 text-white uppercase tracking-wider">
                            New
                          </span>
                        )}

                        <span className="text-[11px] text-[#697586]">
                          {new Date(alert.created_at).toLocaleString()}
                        </span>
                      </div>

                      <h3 className="text-sm font-bold text-[#17324D]">{alert.title}</h3>
                      <p className="text-xs text-slate-600 leading-relaxed">{alert.message}</p>

                      {/* Ripple context & recipients tags */}
                      <div className="flex items-center space-x-3 text-[11px] text-[#697586] pt-1">
                        <span className="flex items-center">
                          <Users className="w-3 h-3 mr-1 text-slate-400" />
                          Audience: <b>{alert.recipients_count || 1} targeted</b>
                        </span>

                        {/* Multi-channel Delivery Status Pill Indicators */}
                        <div className="flex items-center space-x-1.5">
                          <span className="text-[10px] text-slate-400">Channels:</span>
                          <span className="inline-flex items-center text-[10px] bg-slate-100 text-slate-700 px-1.5 py-0.5 rounded border">
                            <Bell className="w-2.5 h-2.5 mr-0.5 text-blue-500" /> In-App
                          </span>

                          {/* Email channel status */}
                          {alert.channels_sent?.includes("email") ? (
                            <span className="inline-flex items-center text-[10px] bg-emerald-50 text-emerald-700 px-1.5 py-0.5 rounded border border-emerald-200">
                              <Mail className="w-2.5 h-2.5 mr-0.5 text-emerald-600" /> Email Verified
                            </span>
                          ) : (
                            <button
                              onClick={() => handleRetryChannel(alert.id, "email")}
                              disabled={actionInProgress === `${alert.id}-email`}
                              className="inline-flex items-center text-[10px] bg-amber-50 text-amber-800 px-1.5 py-0.5 rounded border border-amber-200 hover:bg-amber-100 transition"
                              title="Click to retry email delivery"
                            >
                              <Mail className="w-2.5 h-2.5 mr-0.5 text-amber-600" /> Retry Email
                            </button>
                          )}

                          {/* Push notification */}
                          {alert.channels_sent?.includes("push") && (
                            <span className="inline-flex items-center text-[10px] bg-purple-50 text-purple-700 px-1.5 py-0.5 rounded border border-purple-200">
                              <Smartphone className="w-2.5 h-2.5 mr-0.5 text-purple-600" /> Push
                            </span>
                          )}
                        </div>
                      </div>

                      {/* Resolution audit notes if present */}
                      {alert.resolution_notes && (
                        <div className="mt-2 p-2.5 rounded-lg bg-emerald-50/70 border border-emerald-200 text-xs text-emerald-900 flex items-start space-x-2">
                          <CheckCircle className="w-3.5 h-3.5 text-emerald-600 mt-0.5 shrink-0" />
                          <div>
                            <span className="font-semibold block text-[11px]">Resolution Audit:</span>
                            <span className="text-[11px]">{alert.resolution_notes}</span>
                            {alert.resolved_at && (
                              <span className="text-[10px] text-emerald-700 block mt-0.5">
                                Logged at {new Date(alert.resolved_at).toLocaleString()}
                              </span>
                            )}
                          </div>
                        </div>
                      )}
                    </div>

                    {/* Right actions (Authorised HOD/Coordinator/Faculty Controls) */}
                    <div className="flex sm:flex-col items-center sm:items-end gap-1.5 shrink-0">
                      {!alert.is_read && (
                        <button
                          onClick={() => handleMarkAsRead(alert.id)}
                          disabled={actionInProgress === alert.id}
                          className="px-2.5 py-1 text-xs font-semibold text-blue-700 bg-blue-50 hover:bg-blue-100 border border-blue-200 rounded-md transition"
                        >
                          Mark as Read
                        </button>
                      )}

                      {/* Workflow state buttons */}
                      {isPending && isHodOrAdmin && (
                        <button
                          onClick={() => handleSetUnderReview(alert.id)}
                          disabled={actionInProgress === alert.id}
                          className="px-2.5 py-1 text-xs font-semibold text-amber-800 bg-amber-50 hover:bg-amber-100 border border-amber-300 rounded-md transition flex items-center"
                        >
                          <RefreshCw className="w-3 h-3 mr-1 text-amber-600" />
                          Investigate
                        </button>
                      )}

                      {!isResolved && isHodOrAdmin && (
                        <button
                          onClick={() => {
                            setResolvingAlert(alert);
                            setResolutionNotes("");
                          }}
                          className="px-2.5 py-1 text-xs font-semibold text-white bg-emerald-600 hover:bg-emerald-700 rounded-md transition flex items-center shadow-xs"
                        >
                          <CheckCircle className="w-3 h-3 mr-1" />
                          Resolve Alert
                        </button>
                      )}

                      {alert.category === "CONFLICT" && (
                        <Link href="/conflicts">
                          <button className="px-2.5 py-1 text-xs font-medium text-slate-600 hover:text-[#1261A0] border border-[#E2E7EE] rounded-md transition flex items-center">
                            View Clash <ArrowRight className="w-3 h-3 ml-1" />
                          </button>
                        </Link>
                      )}
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* RESOLUTION AUDIT DIALOG MODAL */}
      {resolvingAlert && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-xs p-4">
          <div className="bg-white rounded-xl max-w-md w-full p-5 sm:p-6 shadow-xl border border-slate-200 space-y-4">
            <div className="flex items-center justify-between pb-2 border-b">
              <div className="flex items-center space-x-2">
                <CheckCircle className="w-5 h-5 text-emerald-600" />
                <h3 className="text-base font-bold text-[#17324D]">Record Alert Resolution</h3>
              </div>
              <button
                onClick={() => setResolvingAlert(null)}
                className="text-slate-400 hover:text-slate-600 font-bold"
              >
                ✕
              </button>
            </div>

            <div className="text-xs text-[#697586]">
              Recording resolution for: <b className="text-slate-800">{resolvingAlert.title}</b>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Resolution & Audit Notes *
              </label>
              <textarea
                value={resolutionNotes}
                onChange={(e) => setResolutionNotes(e.target.value)}
                rows={3}
                placeholder="e.g. Rescheduled session to LH-102 Period 4; substitute faculty assigned; all affected students notified."
                className="w-full text-xs p-2.5 rounded-lg border border-slate-300 focus:outline-hidden focus:border-emerald-600"
              />
            </div>

            <div className="flex items-center justify-end space-x-2 pt-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setResolvingAlert(null)}
                className="text-xs"
              >
                Cancel
              </Button>
              <Button
                size="sm"
                onClick={handleSubmitResolution}
                disabled={submittingResolution}
                className="text-xs bg-emerald-600 hover:bg-emerald-700 text-white"
              >
                {submittingResolution ? "Saving Resolution..." : "Confirm & Mark Resolved"}
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* EMERGENCY DISPATCH DIALOG MODAL (HOD / Admin) */}
      {showDispatchModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-xs p-4">
          <form
            onSubmit={handleDispatchEmergency}
            className="bg-white rounded-xl max-w-lg w-full p-5 sm:p-6 shadow-xl border border-slate-200 space-y-4"
          >
            <div className="flex items-center justify-between pb-2 border-b">
              <div className="flex items-center space-x-2">
                <Flame className="w-5 h-5 text-rose-600" />
                <h3 className="text-base font-bold text-[#17324D]">Dispatch Department Emergency Broadcast</h3>
              </div>
              <button
                type="button"
                onClick={() => setShowDispatchModal(false)}
                className="text-slate-400 hover:text-slate-600 font-bold"
              >
                ✕
              </button>
            </div>

            <div className="space-y-3 text-xs">
              <div>
                <label className="block font-semibold text-slate-700 mb-1">Alert Category</label>
                <select
                  value={dispatchCategory}
                  onChange={(e) => setDispatchCategory(e.target.value)}
                  className="w-full p-2 rounded-lg border border-slate-300 bg-white"
                >
                  <option value="EMERGENCY">Category C: Urgent Emergency / Facility Lockdown</option>
                  <option value="TIMETABLE_CHANGE">Category B: Urgent Timetable Revision</option>
                  <option value="ADMINISTRATIVE">Category D: Administrative Dean Announcement</option>
                </select>
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1">Severity Level</label>
                <div className="flex space-x-3">
                  {(["WARNING", "CRITICAL"] as const).map((sev) => (
                    <label key={sev} className="flex items-center space-x-1.5 cursor-pointer">
                      <input
                        type="radio"
                        checked={dispatchSeverity === sev}
                        onChange={() => setDispatchSeverity(sev)}
                      />
                      <span className={sev === "CRITICAL" ? "text-rose-700 font-bold" : "text-amber-700 font-bold"}>
                        {sev}
                      </span>
                    </label>
                  ))}
                </div>
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1">Subject / Header *</label>
                <input
                  type="text"
                  required
                  value={dispatchTitle}
                  onChange={(e) => setDispatchTitle(e.target.value)}
                  placeholder="e.g. Sudden Faculty Absence - CS-3A Operating Systems Lab"
                  className="w-full p-2 rounded-lg border border-slate-300"
                />
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1">Detailed Notification Message *</label>
                <textarea
                  required
                  rows={3}
                  value={dispatchMessage}
                  onChange={(e) => setDispatchMessage(e.target.value)}
                  placeholder="e.g. Due to unforeseen electrical maintenance in Lab 1, CS-3A Operating Systems is shifted to Lecture Hall 102 Period 5. All students proceed to LH-102."
                  className="w-full p-2.5 rounded-lg border border-slate-300"
                />
              </div>
            </div>

            <div className="flex items-center justify-end space-x-2 pt-2 border-t">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setShowDispatchModal(false)}
                className="text-xs"
              >
                Cancel
              </Button>
              <Button
                type="submit"
                size="sm"
                disabled={dispatching}
                className="text-xs bg-rose-600 hover:bg-rose-700 text-white"
              >
                {dispatching ? "Broadcasting..." : "Dispatch Notification Now"}
              </Button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
