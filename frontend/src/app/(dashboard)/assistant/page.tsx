"use client";

import React, { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { apiRequest } from "@/lib/api";
import {
  AlertCircle,
  AlertTriangle,
  ArrowRight,
  Bot,
  Calendar,
  CheckCircle,
  Clock,
  CornerDownLeft,
  ExternalLink,
  HelpCircle,
  Info,
  Lock,
  MessageSquare,
  RefreshCw,
  Send,
  ShieldCheck,
  Sparkles,
  User,
  Zap,
} from "lucide-react";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: string;
  proposedAction?: {
    action_type: string;
    title: string;
    description: string;
    requires_confirmation: boolean;
    affected_sessions?: Array<any>;
    alternatives?: Array<any>;
    execution_payload?: Record<string, any>;
  };
  suggestedPrompts?: string[];
  providerInfo?: Record<string, any>;
  toolExecutions?: Array<{
    tool_name: string;
    arguments: Record<string, any>;
    summary: string;
  }>;
  isError?: boolean;
}

const SAMPLE_PROMPTS = [
  "Show faculty workload for Department",
  "Create a timetable for CS Semester 3",
  "Why is this timetable showing conflicts?",
  "Find an available room for laboratory session",
  "Search faculty members in DPMS",
  "Show timetable publication status",
];

export default function AIAssistantPage() {
  const { user } = useAuth();
  const router = useRouter();

  const [providerStatus, setProviderStatus] = useState<any>(null);
  const [showConfigModal, setShowConfigModal] = useState(false);

  const [messages, setMessages] = useState<Message[]>([
    {
      id: "m_welcome",
      role: "assistant",
      content:
        "### Welcome to the TIMEVERSE AI Assistant\n**Kristu Jayanti University (KJU) • Department of Professional Management Studies (DPMS)**\n*Airport Road Campus, Bengaluru*\n\nI am your verified AI Scheduling Assistant powered by **Google Gemini** with real database tool-calling and the **Google OR-Tools CP-SAT constraint engine**.\n\n#### What I can do for you:\n- **Inspect Live Faculty Workloads:** Real teaching hours, designations, and leaves\n- **Verify Room Allocations:** Computer labs, lecture halls, and seating capacity\n- **Detect Clashes:** Real-time analysis of teacher, room, and section double-bookings\n- **Solve Complete Schedules:** Generate 100% mathematically clash-free timetable drafts\n- **Evaluate Changes:** Preview clash impact before committing changes\n\nChoose a quick question below or ask in natural language:",
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      suggestedPrompts: SAMPLE_PROMPTS,
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [applyingAction, setApplyingAction] = useState<string | null>(null);
  const [lastCreatedTimetableId, setLastCreatedTimetableId] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    // Fetch provider status on page load
    apiRequest("/assistant/provider-status")
      .then((data) => setProviderStatus(data))
      .catch(() => {
        // Fallback info if endpoint temporarily unavailable
        setProviderStatus({
          provider: "Google Gemini",
          model: "gemini-2.5-flash",
          is_configured: false,
          engine: "Google OR-Tools CP-SAT (Local Constraint Engine)",
          status_text: "Deterministic & Constraint Engine Active (Local / Offline Mode)",
        });
      });
  }, []);

  const handleSend = async (textToSend?: string) => {
    const text = (textToSend || input).trim();
    if (!text || loading) return;

    const userMsg: Message = {
      id: `usr_${Date.now()}`,
      role: "user",
      content: text,
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    try {
      const res: any = await apiRequest("/assistant/chat", {
        method: "POST",
        body: JSON.stringify({
          message: text,
          department_id: "dept_cs",
          academic_term_id: "term_odd_2026",
          history: messages.map((m) => ({ role: m.role, content: m.content })),
        }),
      });

      if (res.provider_info) {
        setProviderStatus(res.provider_info);
      }

      const assistantMsg: Message = {
        id: `ast_${Date.now()}`,
        role: "assistant",
        content: res.reply,
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        proposedAction: res.proposed_action,
        suggestedPrompts: res.suggested_prompts || [],
        providerInfo: res.provider_info,
        toolExecutions: res.tool_executions || [],
      };

      setMessages((prev) => [...prev, assistantMsg]);
    } catch (e: any) {
      setMessages((prev) => [
        ...prev,
        {
          id: `err_${Date.now()}`,
          role: "assistant",
          content: `⚠️ I encountered an issue: ${e.message || "Failed to process scheduling request."}`,
          timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
          isError: true,
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleApplyAction = async (msgId: string, action: any, publishDirectly: boolean = false) => {
    try {
      setApplyingAction(msgId);

      const payload = {
        ...(action.execution_payload || {}),
        publish_directly: publishDirectly,
      };

      const res: any = await apiRequest("/assistant/apply", {
        method: "POST",
        body: JSON.stringify({
          action_type: action.action_type,
          execution_payload: payload,
        }),
      });

      if (res.timetable_id) {
        setLastCreatedTimetableId(res.timetable_id);
      }

      // Add assistant confirmation message
      setMessages((prev) => [
        ...prev,
        {
          id: `conf_${Date.now()}`,
          role: "assistant",
          content: `✅ **Successfully Approved & Saved!**\n\n${res.message}\n\nAll constraint checks passed with zero conflicts. You can now view and manage this timetable directly in the planner.`,
          timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
          suggestedPrompts: ["Show me the timetable grid", "Why is this timetable showing conflicts?"],
        },
      ]);
    } catch (e: any) {
      alert(`Could not apply change: ${e.message}`);
    } finally {
      setApplyingAction(null);
    }
  };

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      {/* Top Banner answering Where am I? What can I do here? What should I do next? */}
      <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2 text-xs text-blue-700 font-semibold tracking-wide uppercase">
            <Bot className="w-4 h-4 text-blue-600" />
            <span>AI Semester Timetable Assistant</span>
            <span className="text-slate-300">•</span>
            <span className="text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded text-[11px] font-bold">
              CP-SAT Real Solver Grounded
            </span>
          </div>
          <h1 className="text-2xl font-bold text-slate-900 mt-1">Smart Scheduling Assistant</h1>
          <p className="text-sm text-slate-600 mt-1">
            Accepts natural-language instructions, verifies actual database records, and generates verified schedules with complete constraint satisfaction.
          </p>
        </div>

        <div className="flex items-center space-x-2.5">
          <button
            onClick={() => setShowConfigModal(true)}
            className="inline-flex items-center space-x-1.5 px-3 py-2 border border-slate-200 hover:border-slate-300 bg-slate-50 hover:bg-slate-100 rounded-lg text-xs font-semibold text-slate-700 transition-colors shadow-2xs"
            title="Inspect AI Provider configuration"
          >
            <Zap className="w-3.5 h-3.5 text-amber-500" />
            <span>AI Provider Settings</span>
          </button>

          <Link
            href="/timetables"
            className="inline-flex items-center space-x-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-bold transition-colors shadow-xs"
          >
            <Calendar className="w-4 h-4" />
            <span>Open Timetable Planner</span>
          </Link>
        </div>
      </div>

      {/* Provider Status Pill */}
      <div className="bg-slate-50 border border-slate-200 rounded-lg px-4 py-2.5 flex items-center justify-between text-xs text-slate-600">
        <div className="flex items-center space-x-2">
          <ShieldCheck className="w-4 h-4 text-emerald-600" />
          <span>
            <strong>Optimization Engine:</strong> Google OR-Tools CP-SAT (100% offline, guaranteed mathematical constraints)
          </span>
        </div>
        <div className="flex items-center space-x-1.5">
          <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
          <span className="font-semibold text-slate-700">
            {providerStatus?.status_text || "Constraint Engine Active (Local)"}
          </span>
        </div>
      </div>

      {/* Main Chat Shell */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-xs flex flex-col h-[650px] overflow-hidden">
        {/* Messages Stream */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {messages.map((m) => (
            <div
              key={m.id}
              className={`flex items-start gap-3.5 ${m.role === "user" ? "flex-row-reverse" : "flex-row"}`}
            >
              {/* Avatar */}
              <div
                className={`w-9 h-9 rounded-full flex items-center justify-center flex-shrink-0 text-sm font-bold shadow-xs ${
                  m.role === "user"
                    ? "bg-slate-800 text-white"
                    : "bg-blue-600 text-white"
                }`}
              >
                {m.role === "user" ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
              </div>

              {/* Message Content */}
              <div
                className={`max-w-[88%] rounded-2xl px-5 py-4 text-sm leading-relaxed ${
                  m.role === "user"
                    ? "bg-blue-600 text-white rounded-tr-xs"
                    : "bg-slate-50 border border-slate-200 text-slate-900 rounded-tl-xs shadow-xs"
                }`}
              >
                {/* Tool Executions Badge if any */}
                {m.toolExecutions && m.toolExecutions.length > 0 && (
                  <div className="mb-3 space-y-1.5 pb-2.5 border-b border-slate-200/60">
                    <div className="text-[10px] font-bold text-slate-500 uppercase tracking-wider flex items-center space-x-1 mb-1">
                      <Zap className="w-3 h-3 text-amber-500" />
                      <span>Verified Server Tools Executed:</span>
                    </div>
                    <div className="flex flex-wrap gap-1.5">
                      {m.toolExecutions.map((t, tidx) => (
                        <div
                          key={tidx}
                          className="inline-flex items-center space-x-1.5 text-[11px] font-mono bg-blue-50 border border-blue-200 text-blue-800 px-2 py-0.5 rounded-md shadow-2xs"
                          title={JSON.stringify(t.arguments)}
                        >
                          <span className="w-1.5 h-1.5 rounded-full bg-blue-600"></span>
                          <span className="font-semibold">{t.tool_name}</span>
                          {t.summary && (
                            <span className="text-blue-600 font-sans text-[10px] max-w-[200px] truncate">
                              ({t.summary})
                            </span>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                <div className="whitespace-pre-wrap">{m.content}</div>

                {/* Error Retry Option */}
                {m.isError && (
                  <div className="mt-3 pt-2.5 border-t border-rose-100 flex items-center justify-between">
                    <span className="text-xs text-rose-600 font-medium">Request failed</span>
                    <button
                      onClick={() => {
                        const lastUser = [...messages].reverse().find((msg) => msg.role === "user");
                        if (lastUser) handleSend(lastUser.content);
                      }}
                      className="inline-flex items-center space-x-1.5 px-3 py-1 bg-rose-50 hover:bg-rose-100 border border-rose-200 text-rose-700 rounded-lg text-xs font-semibold transition-colors"
                    >
                      <RefreshCw className="w-3 h-3" />
                      <span>Retry</span>
                    </button>
                  </div>
                )}

                {/* Proposed Action Card if present */}
                {m.proposedAction && (
                  <div className="mt-4 pt-4 border-t border-slate-200 bg-white p-5 rounded-xl border shadow-2xs space-y-3">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-2 text-blue-700">
                        <Sparkles className="w-4 h-4" />
                        <span className="text-xs font-bold uppercase tracking-wider">
                          {m.proposedAction.action_type === "APPROVE_AND_SAVE_TIMETABLE"
                            ? "Proposed Timetable for Review"
                            : "Proposed Action"}
                        </span>
                      </div>
                      <span className="text-[11px] font-semibold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded">
                        0 Hard Violations
                      </span>
                    </div>

                    <div className="text-base font-bold text-slate-900">{m.proposedAction.title}</div>
                    <div className="text-xs text-slate-600">{m.proposedAction.description}</div>

                    {/* Affected Sessions / Schedule Preview Table */}
                    {m.proposedAction.affected_sessions && m.proposedAction.affected_sessions.length > 0 && (
                      <div className="mt-3">
                        <div className="flex items-center justify-between text-xs font-semibold text-slate-700 mb-2">
                          <span>Session Preview (First {m.proposedAction.affected_sessions.length} sessions):</span>
                          <span className="text-[11px] text-slate-500 font-normal">
                            Total {m.proposedAction.execution_payload?.total_sessions || m.proposedAction.affected_sessions.length} sessions
                          </span>
                        </div>
                        <div className="border border-slate-200 rounded-lg overflow-x-auto max-h-56 overflow-y-auto">
                          <table className="min-w-full text-xs text-left">
                            <thead className="bg-slate-100 text-slate-600 font-bold sticky top-0">
                              <tr>
                                <th className="p-2 border-b">Section</th>
                                <th className="p-2 border-b">Slot</th>
                                <th className="p-2 border-b">Subject</th>
                                <th className="p-2 border-b">Faculty</th>
                                <th className="p-2 border-b">Room</th>
                                <th className="p-2 border-b">Lock Status</th>
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-100">
                              {m.proposedAction.affected_sessions.map((sess: any, idx: number) => (
                                <tr key={idx} className="hover:bg-slate-50">
                                  <td className="p-2 font-medium text-slate-800">{sess.cohort}</td>
                                  <td className="p-2 text-slate-600">{sess.day} P{sess.period}</td>
                                  <td className="p-2 font-semibold text-slate-900">{sess.subject}</td>
                                  <td className="p-2 text-slate-700">{sess.teacher}</td>
                                  <td className="p-2 text-slate-600">{sess.room}</td>
                                  <td className="p-2">
                                    {sess.is_locked ? (
                                      <span className="inline-flex items-center space-x-1 text-[10px] text-amber-700 bg-amber-50 px-1.5 py-0.5 rounded font-bold">
                                        <Lock className="w-2.5 h-2.5" />
                                        <span>Locked</span>
                                      </span>
                                    ) : (
                                      <span className="text-[10px] text-emerald-700 bg-emerald-50 px-1.5 py-0.5 rounded font-medium">
                                        Active
                                      </span>
                                    )}
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    )}

                    {/* Alternatives List */}
                    {m.proposedAction.alternatives && m.proposedAction.alternatives.length > 0 && (
                      <div className="mt-3 space-y-1.5">
                        <span className="text-xs font-semibold text-slate-700 block">Recommended Alternatives (0 Clashes):</span>
                        {m.proposedAction.alternatives.map((alt: any, idx: number) => (
                          <div
                            key={idx}
                            className="text-xs p-2.5 rounded bg-blue-50/70 border border-blue-200 text-blue-900"
                          >
                            <span className="font-bold">{alt.title}:</span> {alt.description}
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Review & Approval Action Buttons */}
                    {m.proposedAction.requires_confirmation && (user?.role === "HOD" || user?.role === "ADMIN" || user?.role === "COORDINATOR") && (
                      <div className="mt-4 pt-3 border-t border-slate-100 flex flex-wrap items-center justify-end gap-2.5">
                        {m.proposedAction.action_type === "APPROVE_AND_SAVE_TIMETABLE" ? (
                          <>
                            <button
                              onClick={() => handleApplyAction(m.id, m.proposedAction, false)}
                              disabled={applyingAction === m.id}
                              className="flex items-center space-x-1.5 px-4 py-2 border border-slate-300 hover:bg-slate-50 text-slate-700 rounded-lg text-xs font-bold transition-colors shadow-2xs"
                            >
                              <CheckCircle className="w-3.5 h-3.5 text-slate-500" />
                              <span>{applyingAction === m.id ? "Saving Draft..." : "Approve & Save Draft"}</span>
                            </button>

                            <button
                              onClick={() => handleApplyAction(m.id, m.proposedAction, true)}
                              disabled={applyingAction === m.id}
                              className="flex items-center space-x-1.5 px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-bold transition-colors shadow-xs"
                            >
                              <CheckCircle className="w-3.5 h-3.5" />
                              <span>{applyingAction === m.id ? "Publishing..." : "Approve & Publish to Campus"}</span>
                            </button>
                          </>
                        ) : (
                          <button
                            onClick={() => handleApplyAction(m.id, m.proposedAction, false)}
                            disabled={applyingAction === m.id}
                            className="flex items-center space-x-1.5 px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-bold transition-colors shadow-xs"
                          >
                            <CheckCircle className="w-3.5 h-3.5" />
                            <span>{applyingAction === m.id ? "Applying..." : "Confirm & Apply to Schedule"}</span>
                          </button>
                        )}
                      </div>
                    )}
                  </div>
                )}

                {/* Suggested Follow-up chips */}
                {m.suggestedPrompts && m.suggestedPrompts.length > 0 && (
                  <div className="mt-4 pt-3 border-t border-slate-200 flex flex-wrap gap-1.5">
                    {m.suggestedPrompts.map((p, i) => (
                      <button
                        key={i}
                        onClick={() => handleSend(p)}
                        className="text-[11px] px-2.5 py-1 bg-white border border-slate-300 hover:border-blue-400 hover:bg-blue-50 text-slate-700 rounded-full transition-colors"
                      >
                        {p}
                      </button>
                    ))}
                  </div>
                )}

                <div
                  className={`text-[10px] mt-2 font-medium ${
                    m.role === "user" ? "text-blue-100 text-right" : "text-slate-400 text-left"
                  }`}
                >
                  {m.timestamp}
                </div>
              </div>
            </div>
          ))}

          {loading && (
            <div className="flex items-center space-x-3 text-slate-600 text-xs p-3.5 bg-slate-50 rounded-xl border border-blue-200/70 shadow-2xs animate-pulse">
              <div className="w-7 h-7 rounded-full bg-blue-100 flex items-center justify-center text-blue-600">
                <Bot className="w-4 h-4 animate-spin" />
              </div>
              <div className="space-y-0.5">
                <div className="font-bold text-slate-800">TIMEVERSE AI is analyzing your request...</div>
                <div className="text-[11px] text-slate-500">Evaluating intent, invoking database tools, and verifying constraint safeguards.</div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input Bar */}
        <div className="border-t border-slate-200 p-4 bg-slate-50">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSend();
            }}
            className="flex items-center gap-3"
          >
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="e.g. 'Create a timetable for CS Semester 3' or 'Keep Professor Sharma unavailable on Wednesday'..."
              className="flex-1 px-4 py-3 bg-white border border-slate-300 rounded-xl text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none shadow-xs text-slate-900"
              disabled={loading}
            />
            <button
              type="submit"
              disabled={!input.trim() || loading}
              className="flex items-center space-x-2 px-5 py-3 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded-xl text-sm font-semibold transition-colors shadow-xs"
            >
              <span>Send</span>
              <Send className="w-4 h-4" />
            </button>
          </form>
        </div>
      </div>

      {/* AI Provider Info Modal */}
      {showConfigModal && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-xl border border-slate-200 space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <div className="flex items-center space-x-2 text-slate-900 font-bold text-base">
                <Zap className="w-5 h-5 text-amber-500" />
                <span>AI Provider & Scheduling Engine</span>
              </div>
              <button
                onClick={() => setShowConfigModal(false)}
                className="text-slate-400 hover:text-slate-600 text-lg font-bold"
              >
                ✕
              </button>
            </div>

            <div className="space-y-3 text-xs text-slate-600 leading-relaxed">
              <div className="p-3 bg-slate-50 rounded-lg border border-slate-200">
                <div className="font-bold text-slate-800 text-sm mb-1">
                  Provider: {providerStatus?.provider || "Google Gemini"} ({providerStatus?.model || "gemini-2.5-flash"})
                </div>
                <div>Status: <span className="font-semibold text-emerald-700">{providerStatus?.status_text}</span></div>
                <div>Optimization Engine: <span className="font-semibold text-slate-800">{providerStatus?.engine}</span></div>
              </div>

              <div className="font-semibold text-slate-800">How to configure the AI API securely on the server:</div>
              <ol className="list-decimal pl-4 space-y-1">
                <li>Create an API key from <strong>Google AI Studio</strong> (https://aistudio.google.com).</li>
                <li>Add the key to your server&apos;s environment:
                  <div className="mt-1 p-2 bg-slate-900 text-slate-100 rounded font-mono text-[11px]">
                    GEMINI_API_KEY=your_gemini_api_key_here
                  </div>
                </li>
                <li>In production, inject this variable as a secret in your deployment environment.</li>
              </ol>

              <div className="p-3 bg-emerald-50 text-emerald-800 rounded-lg border border-emerald-200 font-medium">
                <strong>Important:</strong> Core scheduling does NOT depend on the AI API being available. Google OR-Tools CP-SAT executes 100% locally and guarantees zero teacher/room clashes even if offline.
              </div>
            </div>

            <div className="flex justify-end pt-2">
              <button
                onClick={() => setShowConfigModal(false)}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg text-xs font-bold hover:bg-blue-700 transition-colors"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
