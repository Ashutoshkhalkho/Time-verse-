"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useAuth } from "@/context/AuthContext";
import {
  BookOpen,
  Bot,
  Calendar,
  CheckCircle,
  ChevronDown,
  ChevronUp,
  Clock,
  Compass,
  FileSpreadsheet,
  FileText,
  HelpCircle,
  Info,
  MapPin,
  Printer,
  RefreshCw,
  Search,
  Send,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  User,
  Users,
} from "lucide-react";
import { apiRequest } from "@/lib/api";

export default function GuidePage() {
  const { user } = useAuth();
  const [searchQuery, setSearchQuery] = useState("");
  const [openFaqIndex, setOpenFaqIndex] = useState<number | null>(null);

  // For Admin / HOD, allow toggling between Faculty and Student view to inspect both
  const [adminActiveTab, setAdminActiveTab] = useState<"FACULTY" | "STUDENT">("FACULTY");

  const isTeacher = user?.role === "TEACHER";
  const isStudentOrCr = user?.role === "STUDENT" || user?.role === "CR";
  const isStaffOrAdmin = user && ["ADMIN", "HOD", "COORDINATOR"].includes(user.role);

  // Active guide mode
  const activeMode: "FACULTY" | "STUDENT" = isTeacher
    ? "FACULTY"
    : isStudentOrCr
    ? "STUDENT"
    : adminActiveTab;

  const handleStartTour = () => {
    window.dispatchEvent(new CustomEvent("start-timeverse-tour"));
  };

  const toggleFaq = (index: number) => {
    setOpenFaqIndex(openFaqIndex === index ? null : index);
  };

  // AI Guide Assistant State
  const [aiQuestion, setAiQuestion] = useState("");
  const [aiAnswer, setAiAnswer] = useState<string | null>(null);
  const [aiLoading, setAiLoading] = useState(false);
  const [aiError, setAiError] = useState<string | null>(null);

  const handleAskAi = async (customPrompt?: string) => {
    const queryText = (customPrompt || aiQuestion).trim();
    if (!queryText) return;

    if (customPrompt) {
      setAiQuestion(customPrompt);
    }

    setAiLoading(true);
    setAiError(null);
    try {
      const res: any = await apiRequest("/assistant/guide-query", {
        method: "POST",
        body: JSON.stringify({
          question: queryText,
          guide_role: activeMode,
        }),
      });
      setAiAnswer(res.answer);
    } catch (err: any) {
      setAiError(err.detail || "Unable to retrieve AI response. Please try again.");
    } finally {
      setAiLoading(false);
    }
  };

  // ----------------------------------------------------
  // FACULTY GUIDE CONTENT DATA
  // ----------------------------------------------------
  const facultySections = [
    {
      id: "my-timetable",
      title: "1. My Timetable & Teaching Schedule",
      icon: Calendar,
      summary:
        "Learn how to view your weekly lecture distribution, assigned sections, classrooms, and timing slots.",
      steps: [
        {
          title: "Navigate to Timetable Planner",
          detail: "Open Timetable from the sidebar or top navigation (/timetables).",
        },
        {
          title: "Isolate Your Personal Schedule",
          detail:
            "Click the 'Highlight My Classes' toggle on the top toolbar. Your assigned lecture and lab slots will be highlighted with a distinctive blue border.",
        },
        {
          title: "Inspect Details per Slot",
          detail:
            "Each slot displays the Course Code (e.g., CS301), Course Name (Data Structures), Cohort Section (CS-3A or CS-3B), and Room (e.g., LH-101 or Lab-2).",
        },
        {
          title: "Toggle Weekly Grid vs. Daily Timeline",
          detail:
            "Switch to 'Daily Timeline' to view your day period-by-period with exact start and end times (e.g., Period 1: 08:30 - 09:20).",
        },
      ],
      tip: "College Teaching Example: If Dr. Rajesh Sharma teaches CS301 to Section CS-3A on Monday Period 1 in LH-101, activating 'Highlight My Classes' immediately pinpoints that lecture.",
      actionLabel: "Open My Timetable",
      actionHref: "/timetables",
    },
    {
      id: "my-availability",
      title: "2. Faculty Availability & Workload Rules",
      icon: Clock,
      summary:
        "Understand weekly teaching caps, preferred times, and how leave or unavailable slots are handled.",
      steps: [
        {
          title: "Workload Guidelines",
          detail:
            "TIMEVERSE automatically enforces institutional limits: a maximum of 4 teaching periods per day and balanced weekly distribution to prevent faculty fatigue.",
        },
        {
          title: "Submitting Preferred Time Slots",
          detail:
            "To register preferred teaching windows (e.g., morning sessions) or recurring unavailable blocks, coordinate with your HOD or use the AI Assistant prompt (e.g., 'Keep Dr. Sharma free on Wednesday mornings').",
        },
        {
          title: "Pre-Solver Constraint Safeguard",
          detail:
            "Individual teacher constraints are verified by the CP-SAT solver before the master timetable is generated. Once locked, the solver will never schedule lectures during marked unavailable slots.",
        },
      ],
      tip: "Note: Direct modification of core workload parameters is reserved for Department Coordinators and HOD to prevent departmental scheduling deadlock.",
      actionLabel: "Ask AI Assistant About Availability",
      actionHref: "/assistant",
    },
    {
      id: "change-requests",
      title: "3. Timetable Change Requests & Slot Swaps",
      icon: RefreshCw,
      summary:
        "How to request a lecture rescheduling, provide an academic justification, and track the approval status.",
      steps: [
        {
          title: "Initiate Reschedule or Swap",
          detail:
            "When an urgent academic duty, conference, or emergency necessitates moving a lecture, navigate to the Smart Rescheduler (/rescheduler) or Approvals (/approvals).",
        },
        {
          title: "Provide Justification & Details",
          detail:
            "Select your active session, specify the reason (e.g., 'Faculty conference attending on Friday'), and suggest the target day/period.",
        },
        {
          title: "Automated Ripple-Effect Analysis",
          detail:
            "The system checks room availability and student cohort schedules so that your change does not create any secondary teacher or room clash.",
        },
        {
          title: "Status Tracking",
          detail:
            "Track your request in the Approvals registry. Statuses progress through SUBMITTED → UNDER_REVIEW → APPROVED or REJECTED. Approved changes automatically bump the official timetable version.",
        },
      ],
      tip: "Approved changes notify all enrolled students and automatically update their section timetables with zero manual re-entry.",
      actionLabel: "View Change Requests & Approvals",
      actionHref: "/approvals",
    },
    {
      id: "conflict-info",
      title: "4. Conflict Safeguards & Clash Notifications",
      icon: ShieldAlert,
      summary:
        "Understand teacher double-booking, room capacity mismatches, and live clash alerts in TIMEVERSE.",
      steps: [
        {
          title: "Live Conflict Detector Indicator",
          detail:
            "Observe the pill in the header navigation: a green 'Conflict Free' badge indicates 100% clash-free schedules, while a pulsing red badge indicates active clashes.",
        },
        {
          title: "Teacher Clashes",
          detail:
            "Occur if an instructor is scheduled for two simultaneous classes across different sections. TIMEVERSE hard constraints strictly forbid simultaneous teacher assignments.",
        },
        {
          title: "Room Conflicts",
          detail:
            "Occur if two classes are assigned to the same room or if a practical laboratory class is assigned to a standard lecture hall.",
        },
        {
          title: "Viewing Diagnostics",
          detail:
            "Click the top Conflict indicator to access the Conflict Detector Console (/conflicts) to see affected periods and suggested resolutions.",
        },
      ],
      tip: "All timetables published by the HOD undergo rigorous automated validation by Google OR-Tools CP-SAT before release.",
      actionLabel: "Inspect Conflict Center",
      actionHref: "/conflicts",
    },
    {
      id: "timetable-updates",
      title: "5. Identifying Approved & Published Versions",
      icon: CheckCircle,
      summary:
        "How to verify that you are looking at the active, officially approved academic schedule.",
      steps: [
        {
          title: "Check the Version Badge",
          detail:
            "Look at the top toolbar in Timetable Planner. An official schedule displays '● PUBLISHED' in green next to the version number (e.g., v1.0).",
        },
        {
          title: "Understanding Statuses",
          detail:
            "DRAFT (internal editing in progress), PROPOSED (submitted to HOD for review), PUBLISHED (active official timetable), and ARCHIVED (superseded past versions).",
        },
        {
          title: "Automatic Version Bumps",
          detail:
            "When the HOD approves a change request or publishes updates, a new version (e.g., v1.1) is released, preserving past versions for audit compliance.",
        },
      ],
      tip: "Faculty members should always teach according to the latest PUBLISHED version shown in TIMEVERSE.",
      actionLabel: "Check Active Timetable Version",
      actionHref: "/timetables",
    },
    {
      id: "download-print",
      title: "6. Downloading & Printing Schedules",
      icon: Printer,
      summary:
        "Generate clean, formatted copies of your timetable for your noticeboard, faculty cabin, or binder.",
      steps: [
        {
          title: "Browser Print & PDF Export",
          detail:
            "In Timetable Planner (/timetables), click the 'Print / PDF' button. The print view strips out menus and generates a clean academic grid suitable for printing or saving as PDF.",
        },
        {
          title: "Excel (.xlsx) Export",
          detail:
            "Click 'Excel (.xlsx)' to download a spreadsheet with all periods, rooms, and instructor names.",
        },
        {
          title: "CSV Format",
          detail:
            "Click 'Export CSV' for lightweight spreadsheet importing into calendar tools or personal backups.",
        },
      ],
      tip: "Print out a clean copy at the start of each semester to pin on your faculty cabin door.",
      actionLabel: "Go to Print / Export in Timetable",
      actionHref: "/timetables",
    },
  ];

  const facultyFaqs = [
    {
      q: "Can I swap a lecture slot directly with a colleague?",
      a: "Direct informal swaps without system logging can create untracked room and student conflicts. Please submit a Change Request via the Approvals console (/approvals) or contact your Department Coordinator so the solver can confirm that both sections remain clash-free.",
    },
    {
      q: "Why can't I see the 'Add Class Entry' or 'CP-SAT Generator' button?",
      a: "Adding new sessions or running CP-SAT batch generation requires Department Coordinator or HOD administrative permissions. Faculty members have read and change-request permissions for published schedules.",
    },
    {
      q: "What should I do if a student section cannot fit into my assigned classroom?",
      a: "Check the classroom capacity in the slot card. If enrollment exceeds room capacity, notify your HOD or use the AI Assistant to identify available larger lecture halls (e.g., LH-101 or Audi-1).",
    },
    {
      q: "How often does the timetable refresh?",
      a: "TIMEVERSE checks conflict and published timetable states live every 15 seconds. If an HOD publishes a revised timetable, your portal will reflect the updated schedule immediately.",
    },
  ];

  // ----------------------------------------------------
  // STUDENT GUIDE CONTENT DATA
  // ----------------------------------------------------
  const studentSections = [
    {
      id: "student-timetable",
      title: "1. View My Class Timetable",
      icon: Calendar,
      summary:
        "Find the complete weekly schedule for your assigned cohort section (e.g., CS-3A).",
      steps: [
        {
          title: "Open the Timetable Planner",
          detail:
            "Click 'Timetable' in the left navigation sidebar or open /timetables directly from your student portal.",
        },
        {
          title: "Locate Your Assigned Section",
          detail:
            "Your assigned section (e.g., CS-3A) is automatically selected. You can switch between CS-3A and CS-3B tabs to verify your cohort's lecture agenda.",
        },
        {
          title: "Understand the Weekly Grid",
          detail:
            "Days run from Monday to Saturday down the left column. Periods 1 through 6 run horizontally across the top with start and end times clearly labeled.",
        },
      ],
      tip: "Student Security Scope: Students only have access to published academic schedules and section views. You are never shown faculty private records or administrative settings.",
      actionLabel: "View CS-3A Class Timetable",
      actionHref: "/timetables",
    },
    {
      id: "understand-schedule",
      title: "2. Understanding Your Schedule Cards",
      icon: Info,
      summary:
        "Learn how to read course codes, faculty names, room numbers, and scheduled recess periods.",
      steps: [
        {
          title: "Subject Code & Name",
          detail:
            "Each box shows the course code (e.g., CS301) and subject title (e.g., Data Structures & Algorithms).",
        },
        {
          title: "Assigned Faculty Member",
          detail:
            "Below the course title, you will see your instructor's name (e.g., Prof. Vikram Sharma or Dr. Sneha Rao).",
        },
        {
          title: "Lecture Hall & Room Location",
          detail:
            "Identified by building and room code (e.g., 'Main Block LH-101' for lectures, or 'CS Block Lab-2' for programming practicals).",
        },
        {
          title: "Recess & Lunch Break",
          detail:
            "Period 4 (12:00 - 13:00) is reserved as Lunch Break across all cohorts. No classes are scheduled during this time.",
        },
      ],
      tip: "Tip: Before heading to your next lecture, check your Student Dashboard (/dashboard) for your 'Next Upcoming Class' summary card.",
      actionLabel: "Open Student Dashboard",
      actionHref: "/dashboard",
    },
    {
      id: "check-updates",
      title: "3. Checking for Timetable Updates",
      icon: CheckCircle,
      summary:
        "How to know when your timetable has been updated and verify that you are looking at the latest version.",
      steps: [
        {
          title: "Look for the Green 'PUBLISHED' Status",
          detail:
            "Always verify that the top banner shows '● PUBLISHED'. Draft or proposed schedules are withheld until officially authorized by the Head of Department.",
        },
        {
          title: "Version Identification",
          detail:
            "The active master is marked with version tags (e.g., v1.0, v1.1). When an approved change occurs, the version number automatically increments.",
        },
        {
          title: "Conflict Free Guarantee",
          detail:
            "Every published student timetable is verified so that your section has zero double-booked periods or missing faculty.",
        },
      ],
      tip: "If a teacher is on approved leave, your Class Representative (CR) or department will announce the rescheduled period in TIMEVERSE.",
      actionLabel: "Check Timetable Version",
      actionHref: "/timetables",
    },
    {
      id: "download-print-student",
      title: "4. Downloading & Printing Your Timetable",
      icon: Printer,
      summary:
        "Save your timetable on your smartphone, laptop, or print a copy to stick on your study desk.",
      steps: [
        {
          title: "Print or Save as PDF",
          detail:
            "On the Timetable page (/timetables), click the 'Print / PDF' button. Your browser's print dialog will open where you can select 'Save as PDF' or send to a printer.",
        },
        {
          title: "Download Spreadsheet",
          detail:
            "Click 'Excel (.xlsx)' or 'Export CSV' to download a clean file you can open in Excel or Google Sheets.",
        },
      ],
      tip: "We recommend saving a PDF copy on your mobile phone at the start of every semester for quick offline access.",
      actionLabel: "Go to Timetable to Print",
      actionHref: "/timetables",
    },
    {
      id: "report-issues",
      title: "5. How to Report a Timetable Issue",
      icon: ShieldAlert,
      summary:
        "Found a locked room, conflicting lab timing, or discrepancy? Here is how issues are reported and fixed.",
      steps: [
        {
          title: "Notify Your Class Representative (CR)",
          detail:
            "Students in Section CS-3A can report any schedule discrepancies directly to their Class Representative (Ashutosh Khalkho • cr.cs3a@timewise.edu).",
        },
        {
          title: "CR Issue Submission",
          detail:
            "Class Representatives have authorized access to submit issue tickets directly to the Department Coordinator and HOD for prompt resolution.",
        },
        {
          title: "Faculty Mentor Channel",
          detail:
            "You can also mention scheduling difficulties during your regular Faculty Mentor advisory sessions.",
        },
      ],
      tip: "Please do not create unofficial timetable sheets on social media—always rely on the live published version inside TIMEVERSE.",
      actionLabel: "View CS-3A Schedule",
      actionHref: "/timetables",
    },
  ];

  const studentFaqs = [
    {
      q: "Why can't I see other department timetables (like Mechanical or Electrical)?",
      a: "To ensure academic privacy and prevent confusion, students are strictly scoped to their enrolled department and cohort section (CS-3A). You can only view schedules authorized for your cohort.",
    },
    {
      q: "What does Period 4 mean?",
      a: "Period 4 is the universal lunch break across the department (12:00 PM to 1:00 PM). It is designated as a break period and no academic classes are assigned.",
    },
    {
      q: "A lecture hall is locked or another batch is already inside. What should we do?",
      a: "Verify the room code on your TIMEVERSE schedule. If the correct room is occupied, notify your Class Representative (CR) immediately. The CR will alert the Department Coordinator to re-allocate an alternate hall.",
    },
    {
      q: "Can students edit or reschedule classes in TIMEVERSE?",
      a: "No. Student accounts have read-only access to published timetables to maintain academic integrity. Rescheduling can only be submitted by faculty and approved by the HOD.",
    },
  ];

  // ----------------------------------------------------
  // FILTERING LOGIC FOR SEARCH BAR
  // ----------------------------------------------------
  const activeSections = activeMode === "FACULTY" ? facultySections : studentSections;
  const activeFaqs = activeMode === "FACULTY" ? facultyFaqs : studentFaqs;

  const filteredSections = activeSections.filter(
    (sec) =>
      sec.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      sec.summary.toLowerCase().includes(searchQuery.toLowerCase()) ||
      sec.steps.some(
        (st) =>
          st.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
          st.detail.toLowerCase().includes(searchQuery.toLowerCase())
      )
  );

  const filteredFaqs = activeFaqs.filter(
    (faq) =>
      faq.q.toLowerCase().includes(searchQuery.toLowerCase()) ||
      faq.a.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="space-y-6 pb-16">
      {/* 1. Header Banner */}
      <div className="bg-white rounded-xl border border-[#E2E7EE] p-5 sm:p-6 shadow-xs flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2">
            <span className="text-xs font-bold uppercase tracking-wider text-[#1261A0] bg-[#EAF3FB] px-2.5 py-0.5 rounded">
              TIMEVERSE Help Center
            </span>
            <span className="text-xs text-[#697586]">
              • {activeMode === "FACULTY" ? "Faculty Documentation" : "Student & Class Rep Guide"}
            </span>
          </div>
          <h1 className="text-xl sm:text-2xl font-bold text-[#17324D] mt-1">
            {activeMode === "FACULTY"
              ? "Faculty Member Timetable Guide"
              : "Student Timetable & Schedule Guide"}
          </h1>
          <p className="text-xs sm:text-sm text-[#697586] mt-0.5 max-w-2xl">
            {activeMode === "FACULTY"
              ? "Comprehensive instructions for college faculty on reading schedules, managing availability, submitting change requests, and conflict safeguards."
              : "Simple, step-by-step instructions for students to find their class schedule, identify lecture halls, check updates, and report issues."}
          </p>
        </div>

        <div className="flex items-center gap-2.5 flex-wrap">
          {/* Admin Role Toggle: Only for HOD/Admin/Coordinator */}
          {isStaffOrAdmin && (
            <div className="inline-flex rounded-lg border border-[#E2E7EE] p-0.5 bg-[#F7F9FC]">
              <button
                onClick={() => setAdminActiveTab("FACULTY")}
                className={`px-3 py-1.5 text-xs font-semibold rounded-md transition-colors ${
                  adminActiveTab === "FACULTY"
                    ? "bg-white text-[#1261A0] shadow-xs font-bold"
                    : "text-slate-600 hover:text-slate-900"
                }`}
              >
                Faculty View
              </button>
              <button
                onClick={() => setAdminActiveTab("STUDENT")}
                className={`px-3 py-1.5 text-xs font-semibold rounded-md transition-colors ${
                  adminActiveTab === "STUDENT"
                    ? "bg-white text-[#1261A0] shadow-xs font-bold"
                    : "text-slate-600 hover:text-slate-900"
                }`}
              >
                Student View
              </button>
            </div>
          )}

          {/* Interactive Guided Tour Trigger */}
          <button
            onClick={handleStartTour}
            className="px-3.5 py-2 rounded-lg bg-[#1261A0] hover:bg-[#0E4E82] text-white text-xs font-bold flex items-center shadow-xs transition-colors"
            title="Start Interactive Guided Tour"
          >
            <Compass className="w-4 h-4 mr-1.5" />
            Start Guided Tour
          </button>
        </div>
      </div>

      {/* 2. Search Bar & Topic Filter */}
      <div className="bg-white rounded-xl border border-[#E2E7EE] p-4 shadow-xs">
        <div className="relative">
          <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder={
              activeMode === "FACULTY"
                ? "Search faculty topics (e.g., 'highlight classes', 'availability', 'change request', 'clash')..."
                : "Search student topics (e.g., 'CS-3A', 'lecture hall', 'lunch break', 'print schedule')..."
            }
            className="w-full pl-10 pr-4 py-2.5 text-xs sm:text-sm bg-[#F7F9FC] border border-[#E2E7EE] rounded-lg text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-1 focus:ring-[#1261A0] focus:bg-white transition-all"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery("")}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-xs font-semibold text-slate-400 hover:text-slate-600"
            >
              Clear
            </button>
          )}
        </div>
        {searchQuery && (
          <div className="mt-2 text-xs text-[#697586]">
            Showing results matching &ldquo;<span className="font-semibold text-slate-800">{searchQuery}</span>&rdquo; ({filteredSections.length} topics, {filteredFaqs.length} FAQs)
          </div>
        )}
      </div>

      {/* 3. Guide Topic Cards (Step-by-Step Instructions) */}
      <div className="space-y-5">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-bold uppercase tracking-wider text-[#17324D] flex items-center space-x-2">
            <BookOpen className="w-4 h-4 text-[#1261A0]" />
            <span>Step-by-Step Guide Topics</span>
          </h2>
          <span className="text-xs text-[#697586]">{filteredSections.length} Modules Available</span>
        </div>

        {filteredSections.length === 0 ? (
          <div className="bg-white rounded-xl border border-[#E2E7EE] p-8 text-center">
            <Info className="w-8 h-8 text-slate-400 mx-auto mb-2" />
            <h3 className="text-sm font-bold text-slate-800">No help topics match your search</h3>
            <p className="text-xs text-slate-500 mt-1">Try searching for &quot;timetable&quot;, &quot;print&quot;, or &quot;schedule&quot;.</p>
            <button
              onClick={() => setSearchQuery("")}
              className="mt-3 px-3 py-1.5 text-xs font-semibold bg-[#EAF3FB] text-[#1261A0] rounded-lg hover:bg-blue-100"
            >
              Reset Search Filter
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {filteredSections.map((sec) => {
              const Icon = sec.icon;
              return (
                <div
                  key={sec.id}
                  className="bg-white rounded-xl border border-[#E2E7EE] hover:border-[#1261A0] p-5 shadow-xs transition-all flex flex-col justify-between"
                >
                  <div className="space-y-3">
                    <div className="flex items-center space-x-3">
                      <div className="w-9 h-9 rounded-lg bg-[#EAF3FB] text-[#1261A0] flex items-center justify-center flex-shrink-0">
                        <Icon className="w-5 h-5" />
                      </div>
                      <h3 className="font-bold text-sm sm:text-base text-[#17324D]">
                        {sec.title}
                      </h3>
                    </div>

                    <p className="text-xs text-[#697586] leading-relaxed">
                      {sec.summary}
                    </p>

                    {/* Step by Step List */}
                    <div className="space-y-2 pt-1 border-t border-slate-100">
                      {sec.steps.map((st, i) => (
                        <div key={i} className="flex items-start space-x-2 text-xs">
                          <span className="inline-flex items-center justify-center w-4 h-4 rounded-full bg-slate-100 text-slate-700 text-[10px] font-bold flex-shrink-0 mt-0.5">
                            {i + 1}
                          </span>
                          <div>
                            <span className="font-semibold text-slate-800">{st.title}: </span>
                            <span className="text-slate-600">{st.detail}</span>
                          </div>
                        </div>
                      ))}
                    </div>

                    {/* Pro Tip Callout */}
                    {sec.tip && (
                      <div className="p-2.5 rounded-lg bg-[#F7F9FC] border border-blue-100 text-[11px] text-[#1261A0] flex items-start space-x-2 mt-2">
                        <Info className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" />
                        <span>{sec.tip}</span>
                      </div>
                    )}
                  </div>

                  {/* Direct Link Action */}
                  <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between">
                    <Link
                      href={sec.actionHref}
                      className="inline-flex items-center text-xs font-bold text-[#1261A0] hover:text-[#0E4E82] transition-colors"
                    >
                      <span>{sec.actionLabel}</span>
                      <span className="ml-1">&rarr;</span>
                    </Link>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* 4. Interactive AI Timetable Assistant for Guide */}
      <div className="bg-white rounded-xl border border-blue-200 p-5 sm:p-6 shadow-xs space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 pb-3">
          <div className="flex items-center space-x-2.5">
            <div className="w-8 h-8 rounded-lg bg-purple-50 text-purple-600 flex items-center justify-center">
              <Bot className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-sm sm:text-base font-bold text-[#17324D] flex items-center space-x-2">
                <span>Ask TIMEVERSE AI Guide</span>
              </h2>
              <p className="text-[11px] text-[#697586]">
                Instant timetable answers powered by Google Gemini (gemini-2.5-flash) &amp; database ground truth
              </p>
            </div>
          </div>
          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 mr-1.5"></span>
            Gemini 2.5 Flash Active
          </span>
        </div>

        {/* Suggested Quick Question Chips */}
        <div className="space-y-1.5">
          <div className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
            Quick Questions ({activeMode === "FACULTY" ? "Faculty" : "Student"}):
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            {(activeMode === "FACULTY"
              ? [
                  "How do I isolate my assigned lectures on the weekly grid?",
                  "How do I submit a change request for Friday?",
                  "What workload limit is enforced for teachers?",
                ]
              : [
                  "Where are our CS-3A computer practicals held?",
                  "When is our college lunch break scheduled?",
                  "What should we do if our classroom is locked?",
                ]
            ).map((promptText, i) => (
              <button
                key={i}
                onClick={() => handleAskAi(promptText)}
                disabled={aiLoading}
                className="text-xs px-3 py-1.5 rounded-lg bg-[#F7F9FC] border border-[#E2E7EE] text-slate-700 hover:border-[#1261A0] hover:text-[#1261A0] transition-colors text-left"
              >
                &ldquo;{promptText}&rdquo;
              </button>
            ))}
          </div>
        </div>

        {/* Input Field & Submit Button */}
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleAskAi();
          }}
          className="flex items-center gap-2"
        >
          <input
            type="text"
            value={aiQuestion}
            onChange={(e) => setAiQuestion(e.target.value)}
            placeholder={
              activeMode === "FACULTY"
                ? "Ask anything about teaching loads, slot swaps, clash detection, or printing..."
                : "Ask about your CS-3A lecture halls, lab locations, lunch breaks, or reporting issues..."
            }
            className="flex-1 px-3.5 py-2.5 text-xs sm:text-sm bg-[#F7F9FC] border border-[#E2E7EE] rounded-lg text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-1 focus:ring-[#1261A0] focus:bg-white"
          />
          <button
            type="submit"
            disabled={aiLoading || !aiQuestion.trim()}
            className="px-4 py-2.5 bg-[#1261A0] hover:bg-[#0E4E82] disabled:opacity-50 text-white rounded-lg text-xs font-bold flex items-center shadow-xs transition-colors whitespace-nowrap"
          >
            {aiLoading ? (
              <>
                <RefreshCw className="w-3.5 h-3.5 mr-1.5 animate-spin" />
                Thinking...
              </>
            ) : (
              <>
                <Send className="w-3.5 h-3.5 mr-1.5" />
                Ask AI
              </>
            )}
          </button>
        </form>

        {/* AI Answer Display Card */}
        {aiAnswer && (
          <div className="p-4 rounded-xl bg-[#F7F9FC] border border-blue-100 space-y-2">
            <div className="flex items-center justify-between text-xs font-bold text-[#1261A0]">
              <span className="flex items-center space-x-1.5">
                <Sparkles className="w-3.5 h-3.5 text-purple-600" />
                <span>AI Timetable Guide Answer:</span>
              </span>
              <button
                onClick={() => setAiAnswer(null)}
                className="text-[11px] font-semibold text-slate-400 hover:text-slate-600"
              >
                Dismiss
              </button>
            </div>
            <div className="text-xs sm:text-sm text-slate-800 leading-relaxed whitespace-pre-wrap font-sans">
              {aiAnswer}
            </div>
          </div>
        )}

        {aiError && (
          <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 text-xs text-rose-700 flex items-center justify-between">
            <span>{aiError}</span>
            <button onClick={() => setAiError(null)} className="font-bold underline ml-2">
              ✕
            </button>
          </div>
        )}
      </div>

      {/* 5. Frequently Asked Questions (Expandable Accordion) */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-bold uppercase tracking-wider text-[#17324D] flex items-center space-x-2">
            <HelpCircle className="w-4 h-4 text-[#1261A0]" />
            <span>Frequently Asked Questions ({activeMode === "FACULTY" ? "Faculty" : "Students"})</span>
          </h2>
          <span className="text-xs text-[#697586]">{filteredFaqs.length} Answers</span>
        </div>

        {filteredFaqs.length === 0 ? (
          <div className="bg-white rounded-xl border border-[#E2E7EE] p-6 text-center text-xs text-slate-500">
            No FAQs matching this query.
          </div>
        ) : (
          <div className="space-y-2.5">
            {filteredFaqs.map((faq, idx) => {
              const isOpen = openFaqIndex === idx;
              return (
                <div
                  key={idx}
                  className="bg-white rounded-xl border border-[#E2E7EE] overflow-hidden shadow-xs transition-colors"
                >
                  <button
                    onClick={() => toggleFaq(idx)}
                    className="w-full text-left px-4 py-3.5 flex items-center justify-between hover:bg-slate-50 transition-colors"
                    aria-expanded={isOpen}
                  >
                    <span className="font-semibold text-xs sm:text-sm text-[#17324D] pr-4">
                      {faq.q}
                    </span>
                    {isOpen ? (
                      <ChevronUp className="w-4 h-4 text-[#1261A0] flex-shrink-0" />
                    ) : (
                      <ChevronDown className="w-4 h-4 text-slate-400 flex-shrink-0" />
                    )}
                  </button>

                  {isOpen && (
                    <div className="px-4 pb-4 pt-1 text-xs text-slate-600 border-t border-slate-50 leading-relaxed bg-[#F7F9FC]">
                      {faq.a}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* 5. What Should I Do Next? (Actionable Steps Card) */}
      <div className="bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-200 rounded-xl p-5 shadow-xs">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center space-x-2 text-[#1261A0] text-xs font-bold uppercase tracking-wider">
              <Sparkles className="w-4 h-4" />
              <span>Next Steps & Quick Actions</span>
            </div>
            <h3 className="text-base font-bold text-slate-900 mt-1">
              Ready to view or export your academic schedule?
            </h3>
            <p className="text-xs text-slate-600 mt-0.5">
              {activeMode === "FACULTY"
                ? "Open Timetable Planner to verify your weekly lecture load, highlight your periods, or export a printable PDF."
                : "Open your Section CS-3A timetable to check tomorrow's classes or print your schedule for your binder."}
            </p>
          </div>

          <div className="flex items-center space-x-2 flex-wrap">
            <button
              onClick={handleStartTour}
              className="px-3.5 py-2 rounded-lg border border-blue-300 bg-white hover:bg-blue-50 text-[#1261A0] text-xs font-bold transition-colors"
            >
              Launch Tour
            </button>
            <Link
              href="/timetables"
              className="px-4 py-2 rounded-lg bg-[#1261A0] hover:bg-[#0E4E82] text-white text-xs font-bold transition-colors shadow-xs"
            >
              Open Timetable Planner &rarr;
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
