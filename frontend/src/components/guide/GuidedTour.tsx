"use client";

import React, { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import {
  Compass,
  ArrowRight,
  ArrowLeft,
  Check,
  X,
  HelpCircle,
  Calendar,
  LayoutDashboard,
  ShieldCheck,
  Bot,
  Sliders,
  FileSpreadsheet,
} from "lucide-react";

export interface TourStep {
  targetId: string;
  title: string;
  description: string;
  icon?: any;
  route?: string;
}

export function GuidedTour() {
  const { user } = useAuth();
  const pathname = usePathname();
  const router = useRouter();

  const [isOpen, setIsOpen] = useState(false);
  const [currentStepIndex, setCurrentStepIndex] = useState(0);

  // Define role-specific tour steps
  const getRoleSteps = (): TourStep[] => {
    if (!user) return [];

    if (user.role === "STUDENT" || user.role === "CR") {
      return [
        {
          targetId: "nav-dashboard",
          title: "Student Dashboard Overview",
          description:
            "Your central dashboard displays today's lecture schedule, upcoming class timings, and active academic term information for Section CS-3A.",
          icon: LayoutDashboard,
          route: "/dashboard",
        },
        {
          targetId: "nav-timetables",
          title: "View Class Timetable",
          description:
            "Navigate your section's weekly timetable grid. Check course codes, assigned faculty, lecture hall room numbers, and scheduled breaks.",
          icon: Calendar,
          route: "/timetables",
        },
        {
          targetId: "header-conflict-pill",
          title: "Verified Timetable Status",
          description:
            "TIMEVERSE automatically verifies that all student classes are conflict-free. When green, your schedule has zero overlapping periods.",
          icon: ShieldCheck,
        },
        {
          targetId: "nav-guide",
          title: "Student Guide & Help Desk",
          description:
            "Need assistance reading your schedule or understanding room numbers? Access step-by-step instructions and FAQs anytime.",
          icon: HelpCircle,
          route: "/guide",
        },
      ];
    }

    if (user.role === "TEACHER") {
      return [
        {
          targetId: "nav-dashboard",
          title: "Faculty Dashboard",
          description:
            "View your upcoming teaching commitments, next scheduled lecture hall, and current department timetable publication status.",
          icon: LayoutDashboard,
          route: "/dashboard",
        },
        {
          targetId: "nav-timetables",
          title: "Teaching Schedule Matrix",
          description:
            "Inspect weekly timetables across all cohorts. Use the 'Highlight My Classes' toggle to isolate your personal teaching commitments.",
          icon: Calendar,
          route: "/timetables",
        },
        {
          targetId: "header-conflict-pill",
          title: "Clash & Conflict Safeguards",
          description:
            "Real-time constraint checking guards against teacher double-booking and room clashes. Click to view detailed clash diagnostics.",
          icon: ShieldCheck,
        },
        {
          targetId: "nav-assistant",
          title: "AI Timetable Assistant",
          description:
            "Use natural language to inquire about room availability, faculty teaching loads, or submit scheduling preferences.",
          icon: Bot,
          route: "/assistant",
        },
        {
          targetId: "nav-guide",
          title: "Faculty Guide & Documentation",
          description:
            "Review formal guidelines for submitting availability, requesting timetable modifications, and exporting printable PDF schedules.",
          icon: HelpCircle,
          route: "/guide",
        },
      ];
    }

    // Default for HOD, ADMIN, COORDINATOR
    return [
      {
        targetId: "nav-dashboard",
        title: "Department Operations Console",
        description:
          "Monitor semester readiness, solver status, scheduled lecture hours, and active master timetable versions.",
        icon: LayoutDashboard,
        route: "/dashboard",
      },
      {
        targetId: "nav-timetables",
        title: "Timetable Planner & Solver",
        description:
          "Create, edit, lock sessions, and run the CP-SAT constraint engine with zero clash guarantees. Approve and publish official drafts.",
        icon: Calendar,
        route: "/timetables",
      },
      {
        targetId: "nav-setup",
        title: "Semester Setup Wizard",
        description:
          "5-step guided wizard to configure academic dates, working days, daily period limits, and teacher workload rules.",
        icon: Sliders,
        route: "/setup",
      },
      {
        targetId: "nav-import",
        title: "Data Importer & Validation",
        description:
          "Preflight validate and commit spreadsheets for faculty, course curriculum, classrooms, and teaching requirements.",
        icon: FileSpreadsheet,
        route: "/import",
      },
      {
        targetId: "nav-assistant",
        title: "AI Timetable Assistant",
        description:
          "AI assistant powered by Google Gemini and CP-SAT to draft timetables, lock sessions, and resolve complex clashes automatically.",
        icon: Bot,
        route: "/assistant",
      },
      {
        targetId: "nav-guide",
        title: "Role-Based Guides",
        description:
          "Explore official guides tailored for faculty and students. Share standard operating procedures with your department.",
        icon: HelpCircle,
        route: "/guide",
      },
    ];
  };

  const steps = getRoleSteps();

  // Listen for custom trigger to start tour (e.g. from Guide page button)
  useEffect(() => {
    const handleStartTour = () => {
      setCurrentStepIndex(0);
      setIsOpen(true);
    };

    window.addEventListener("start-timeverse-tour", handleStartTour);
    return () => window.removeEventListener("start-timeverse-tour", handleStartTour);
  }, []);

  // Handle tour completion persistence
  const getStorageKey = () => {
    return user ? `timeverse_tour_completed_${user.role.toLowerCase()}` : "timeverse_tour_completed_guest";
  };

  const handleFinish = () => {
    try {
      localStorage.setItem(getStorageKey(), "true");
    } catch {
      // Ignore storage errors in private browsing
    }
    setIsOpen(false);
  };

  const handleSkip = () => {
    try {
      localStorage.setItem(getStorageKey(), "true");
    } catch {
      // Ignore storage errors
    }
    setIsOpen(false);
  };

  const currentStep = steps[currentStepIndex];

  // Navigate to corresponding route if step specifies one
  const handleNext = () => {
    if (currentStepIndex < steps.length - 1) {
      const nextIndex = currentStepIndex + 1;
      setCurrentStepIndex(nextIndex);
      const nextStep = steps[nextIndex];
      if (nextStep.route && pathname !== nextStep.route) {
        router.push(nextStep.route);
      }
    } else {
      handleFinish();
    }
  };

  const handleBack = () => {
    if (currentStepIndex > 0) {
      const prevIndex = currentStepIndex - 1;
      setCurrentStepIndex(prevIndex);
      const prevStep = steps[prevIndex];
      if (prevStep.route && pathname !== prevStep.route) {
        router.push(prevStep.route);
      }
    }
  };

  // Keyboard navigation
  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") handleSkip();
      if (e.key === "ArrowRight") handleNext();
      if (e.key === "ArrowLeft") handleBack();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, currentStepIndex]);

  // Spotlight effect: highlight target element
  useEffect(() => {
    if (!isOpen || !currentStep) return;
    const el = document.getElementById(currentStep.targetId);
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "center" });
      el.classList.add("ring-2", "ring-[#1261A0]", "ring-offset-2", "transition-all");
    }
    return () => {
      if (el) {
        el.classList.remove("ring-2", "ring-[#1261A0]", "ring-offset-2");
      }
    };
  }, [isOpen, currentStepIndex, currentStep]);

  if (!isOpen || !currentStep) return null;

  const StepIcon = currentStep.icon || Compass;

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-4 bg-slate-900/40 backdrop-blur-xs transition-opacity animate-in fade-in duration-200">
      <div
        className="w-full max-w-md bg-white rounded-2xl border border-[#E2E7EE] shadow-2xl p-5 sm:p-6 space-y-4 relative"
        role="dialog"
        aria-labelledby="tour-step-title"
        aria-describedby="tour-step-desc"
      >
        {/* Top Header */}
        <div className="flex items-center justify-between pb-3 border-b border-slate-100">
          <div className="flex items-center space-x-2">
            <span className="px-2 py-0.5 rounded-full bg-[#EAF3FB] text-[#1261A0] text-[11px] font-bold uppercase tracking-wider">
              {user?.role === "STUDENT" || user?.role === "CR"
                ? "Student Tour"
                : user?.role === "TEACHER"
                ? "Faculty Tour"
                : "Staff Tour"}
            </span>
            <span className="text-xs text-[#697586] font-medium">
              Step {currentStepIndex + 1} of {steps.length}
            </span>
          </div>
          <button
            onClick={handleSkip}
            className="p-1 text-slate-400 hover:text-slate-600 rounded-lg hover:bg-slate-100 transition-colors"
            title="Skip Tour"
            aria-label="Close Tour"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Step Content */}
        <div className="flex items-start space-x-3.5">
          <div className="w-10 h-10 rounded-xl bg-[#EAF3FB] text-[#1261A0] flex items-center justify-center flex-shrink-0 shadow-xs">
            <StepIcon className="w-5 h-5" />
          </div>
          <div className="space-y-1">
            <h3 id="tour-step-title" className="text-sm sm:text-base font-bold text-[#17324D]">
              {currentStep.title}
            </h3>
            <p id="tour-step-desc" className="text-xs sm:text-sm text-[#697586] leading-relaxed">
              {currentStep.description}
            </p>
          </div>
        </div>

        {/* Progress Dots Indicator */}
        <div className="flex items-center justify-center space-x-1.5 py-1">
          {steps.map((_, idx) => (
            <button
              key={idx}
              onClick={() => setCurrentStepIndex(idx)}
              className={`h-1.5 rounded-full transition-all ${
                idx === currentStepIndex
                  ? "w-6 bg-[#1261A0]"
                  : "w-2 bg-slate-200 hover:bg-slate-300"
              }`}
              title={`Go to step ${idx + 1}`}
              aria-label={`Go to step ${idx + 1}`}
            />
          ))}
        </div>

        {/* Bottom Controls */}
        <div className="flex items-center justify-between pt-2 border-t border-slate-100">
          <button
            onClick={handleSkip}
            className="text-xs font-semibold text-slate-500 hover:text-slate-800 px-2 py-1.5 rounded transition-colors"
          >
            Skip Tour
          </button>

          <div className="flex items-center space-x-2">
            {currentStepIndex > 0 && (
              <button
                onClick={handleBack}
                className="px-3 py-1.5 rounded-lg border border-[#E2E7EE] hover:bg-slate-50 text-slate-700 text-xs font-semibold flex items-center transition-colors"
              >
                <ArrowLeft className="w-3.5 h-3.5 mr-1" />
                Back
              </button>
            )}

            <button
              onClick={handleNext}
              className="px-4 py-1.5 rounded-lg bg-[#1261A0] hover:bg-[#0E4E82] text-white text-xs font-bold flex items-center shadow-xs transition-colors"
            >
              {currentStepIndex === steps.length - 1 ? (
                <>
                  <Check className="w-3.5 h-3.5 mr-1" />
                  Finish Tour
                </>
              ) : (
                <>
                  Next
                  <ArrowRight className="w-3.5 h-3.5 ml-1" />
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
