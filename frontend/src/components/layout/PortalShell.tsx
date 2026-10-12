"use client";

import React, { useEffect, useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { apiRequest } from "@/lib/api";
import {
  AlertTriangle,
  Bell,
  Bot,
  Calendar,
  Check,
  CheckCircle,
  ChevronDown,
  FileSpreadsheet,
  HelpCircle,
  Layers,
  LayoutDashboard,
  LogOut,
  Menu,
  RefreshCw,
  ShieldCheck,
  Sliders,
  User,
  Users,
  X,
} from "lucide-react";

import { GuidedTour } from "@/components/guide/GuidedTour";

const DEMO_PERSONAS = [
  {
    label: "Head of Dept (CS)",
    email: "hod.cs@timewise.edu",
    role: "HOD",
    desc: "Manage Dept, Generate, Approve & Publish",
  },
  {
    label: "Faculty / Teacher",
    email: "teacher.sharma@timewise.edu",
    role: "TEACHER",
    desc: "Personal Timetable & Availability",
  },
  {
    label: "Class Representative (Ashutosh)",
    email: "cr.cs3a@timewise.edu",
    role: "CR",
    desc: "Ashutosh • Section CS-3A Timetable & Issues",
  },
  {
    label: "Student (Aarav - View Only)",
    email: "student.aarav@timewise.edu",
    role: "STUDENT",
    desc: "Strictly View-Only • Section CS-3A Timetable",
  },
  {
    label: "College Management",
    email: "admin@timewise.edu",
    role: "ADMIN",
    desc: "Cross-Department Summaries & Resource Utilization",
  },
];

export function PortalShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, logout, login, isLoading } = useAuth();

  useEffect(() => {
    if (!isLoading && !user && !pathname.includes("/login")) {
      router.push("/login");
    }
  }, [user, isLoading, pathname, router]);

  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [personaDropdownOpen, setPersonaDropdownOpen] = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState(false);

  // Real-time conflict status indicator
  const [conflictCount, setConflictCount] = useState<number>(0);
  const [isConflictFree, setIsConflictFree] = useState<boolean>(true);
  const [loadingConflicts, setLoadingConflicts] = useState<boolean>(false);

  const fetchConflictStatus = async () => {
    if (!user) return;
    try {
      setLoadingConflicts(true);
      const res: any = await apiRequest("/conflicts");
      setConflictCount(res?.critical_conflicts_count || 0);
      setIsConflictFree(res?.is_conflict_free ?? true);
    } catch {
      // Graceful fallback
    } finally {
      setLoadingConflicts(false);
    }
  };

  useEffect(() => {
    fetchConflictStatus();
    const interval = setInterval(fetchConflictStatus, 15000); // 15s live poll
    return () => clearInterval(interval);
  }, [user]);

  const handleQuickSwitchPersona = async (email: string) => {
    try {
      await login(email, "DemoPass@2026!");
      setPersonaDropdownOpen(false);
      router.refresh();
    } catch (e) {
      console.error("Failed quick persona switch", e);
    }
  };

  // Role-filtered Navigation conforming to strict role boundaries
  const allNavItems = [
    {
      id: "nav-dashboard",
      label: "Dashboard",
      href: "/dashboard",
      icon: LayoutDashboard,
      roles: ["ADMIN", "HOD", "COORDINATOR", "TEACHER", "CR", "STUDENT", "MENTOR"],
    },
    {
      id: "nav-timetables",
      label: "Timetable",
      href: "/timetables",
      icon: Calendar,
      badge: conflictCount > 0 ? `${conflictCount} Clashes` : undefined,
      badgeColor: "rose",
      roles: ["ADMIN", "HOD", "COORDINATOR", "TEACHER", "CR", "STUDENT", "MENTOR"],
    },
    {
      id: "nav-simulator",
      label: "Impact Simulator",
      href: "/simulator",
      icon: Layers,
      roles: ["ADMIN", "HOD", "COORDINATOR"],
    },
    {
      id: "nav-alerts",
      label: "Alerts & Ripple",
      href: "/alerts",
      icon: Bell,
      badge: conflictCount > 0 ? `${conflictCount}` : undefined,
      badgeColor: "rose",
      roles: ["ADMIN", "HOD", "COORDINATOR", "TEACHER", "CR", "STUDENT", "MENTOR"],
    },
    {
      id: "nav-setup",
      label: "Semester Setup",
      href: "/setup",
      icon: Sliders,
      roles: ["ADMIN", "HOD", "COORDINATOR"],
    },
    {
      id: "nav-import",
      label: "Import Data",
      href: "/import",
      icon: FileSpreadsheet,
      roles: ["ADMIN", "HOD", "COORDINATOR"],
    },
    {
      id: "nav-assistant",
      label: "AI Assistant",
      href: "/assistant",
      icon: Bot,
      roles: ["ADMIN", "HOD", "COORDINATOR", "TEACHER"],
    },
    {
      id: "nav-faculty-directory",
      label: "Faculty Directory",
      href: "/faculty-directory",
      icon: Users,
      roles: ["ADMIN", "HOD", "COORDINATOR", "TEACHER", "CR", "STUDENT", "MENTOR"],
    },
    {
      id: "nav-guide",
      label: "Guide",
      href: "/guide",
      icon: HelpCircle,
      roles: ["ADMIN", "HOD", "COORDINATOR", "TEACHER", "CR", "STUDENT", "MENTOR"],
    },
  ];

  const currentRole = user?.role || "GUEST";
  const navItems = allNavItems.filter((item) => item.roles.includes(currentRole));

  const getBreadcrumb = () => {
    if (pathname.includes("/dashboard")) return "TIMEVERSE / Dashboard";
    if (pathname.includes("/timetables")) return "TIMEVERSE / Timetable Planner";
    if (pathname.includes("/simulator")) return "TIMEVERSE / Impact Simulator";
    if (pathname.includes("/alerts")) return "TIMEVERSE / Alert Engine & Notifications";
    if (pathname.includes("/setup")) return "TIMEVERSE / Semester Setup Wizard";
    if (pathname.includes("/import")) return "TIMEVERSE / Excel & CSV Importer";
    if (pathname.includes("/assistant")) return "TIMEVERSE / AI Timetable Assistant";
    if (pathname.includes("/faculty-directory")) return "TIMEVERSE / Faculty Directory (DPMS, KJU)";
    if (pathname.includes("/guide")) return user?.role === "TEACHER" ? "TIMEVERSE / Faculty Guide" : user?.role === "STUDENT" || user?.role === "CR" ? "TIMEVERSE / Student Guide" : "TIMEVERSE / User & Role Guide";
    if (pathname.includes("/profile")) return "TIMEVERSE / User Profile";
    return "TIMEVERSE / Workspace";
  };


  return (
    <div className="min-h-screen bg-[#F7F9FC] text-[#1F2937] flex flex-col">
      {/* Top Academic Portal Navigation Bar */}
      <header className="border-b border-[#E2E7EE] bg-white sticky top-0 z-40 shadow-xs">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between gap-4">
          {/* Left Brand & Breadcrumb */}
          <div className="flex items-center space-x-3">
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="lg:hidden p-2 rounded-lg text-slate-600 hover:bg-slate-100 focus:outline-none"
              aria-label="Toggle navigation menu"
            >
              {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
            </button>

            <Link href="/" className="flex items-center space-x-2.5">
              <div className="w-9 h-9 relative flex-shrink-0">
                <Image
                  src="/logo.png"
                  alt="Timeverse Logo"
                  width={36}
                  height={36}
                  className="object-contain"
                />
              </div>
              <div className="hidden sm:block">
                <span className="text-base font-bold text-[#17324D] tracking-tight">Timeverse</span>
                <span className="block text-[10px] text-[#697586] -mt-0.5 font-medium">Academic Portal</span>
              </div>
            </Link>

            <div className="hidden md:flex items-center text-xs text-[#697586] pl-3 border-l border-slate-200">
              <span className="font-medium text-slate-700">{getBreadcrumb()}</span>
            </div>
          </div>

          {/* Right Header Controls */}
          <div className="flex items-center space-x-2.5">
            {/* Live Conflict Status Pill Indicator */}
            <Link
              id="header-conflict-pill"
              href="/conflicts"
              className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg border text-xs font-semibold transition-all ${
                isConflictFree && conflictCount === 0
                  ? "bg-emerald-50 border-emerald-200 text-[#16805D] hover:bg-emerald-100"
                  : "bg-rose-50 border-rose-300 text-[#B42332] hover:bg-rose-100 animate-pulse"
              }`}
              title="Click to view real-time conflict diagnostics and resolutions"
            >
              {isConflictFree && conflictCount === 0 ? (
                <>
                  <ShieldCheck className="w-3.5 h-3.5 text-[#16805D]" />
                  <span className="hidden sm:inline">Conflict Free</span>
                  <span className="sm:hidden">0 Clashes</span>
                </>
              ) : (
                <>
                  <AlertTriangle className="w-3.5 h-3.5 text-[#B42332]" />
                  <span>
                    {conflictCount} {conflictCount === 1 ? "Clash" : "Clashes"} Detected
                  </span>
                </>
              )}
            </Link>

            {/* Quick Demo Persona Switcher Dropdown */}
            <div className="relative">
              <button
                onClick={() => {
                  setPersonaDropdownOpen(!personaDropdownOpen);
                  setUserMenuOpen(false);
                }}
                className="flex items-center space-x-1.5 px-2.5 py-1.5 rounded-lg border border-[#E2E7EE] bg-white hover:bg-[#EAF3FB] text-xs font-semibold text-[#17324D] transition-colors"
                title="Switch Demo Persona"
              >
                <span className="inline-block w-2 h-2 rounded-full bg-emerald-500"></span>
                <span className="hidden sm:inline">Role:</span>
                <span className="text-[#1261A0] font-bold">{user?.role || "GUEST"}</span>
                <ChevronDown className="w-3.5 h-3.5 text-slate-400" />
              </button>

              {personaDropdownOpen && (
                <div className="absolute right-0 mt-2 w-72 rounded-xl bg-white border border-[#E2E7EE] shadow-lg py-2 z-50">
                  <div className="px-3 py-1.5 border-b border-slate-100 text-[11px] font-bold uppercase tracking-wider text-slate-400">
                    Switch Active Persona (Instant Live Demo)
                  </div>
                  <div className="max-h-72 overflow-y-auto divide-y divide-slate-50">
                    {DEMO_PERSONAS.map((p) => (
                      <button
                        key={p.role}
                        onClick={() => handleQuickSwitchPersona(p.email)}
                        className={`w-full text-left px-3 py-2 text-xs flex items-start space-x-2 hover:bg-[#EAF3FB] transition-colors ${
                          user?.role === p.role ? "bg-blue-50/70 font-semibold text-[#1261A0]" : "text-slate-700"
                        }`}
                      >
                        <div className="flex-1">
                          <div className="flex items-center justify-between">
                            <span className="font-semibold">{p.label}</span>
                            <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-100 font-mono text-slate-600">
                              {p.role}
                            </span>
                          </div>
                          <div className="text-[11px] text-[#697586] truncate">{p.desc}</div>
                        </div>
                        {user?.role === p.role && <Check className="w-4 h-4 text-[#1261A0] flex-shrink-0 mt-0.5" />}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* User Profile Menu */}
            {user ? (
              <div className="relative">
                <button
                  onClick={() => {
                    setUserMenuOpen(!userMenuOpen);
                    setPersonaDropdownOpen(false);
                  }}
                  className="flex items-center space-x-2 pl-2 focus:outline-none"
                >
                  <div className="w-8 h-8 rounded-full bg-[#17324D] text-white flex items-center justify-center font-bold text-xs shadow-xs">
                    {user.full_name?.charAt(0) || "U"}
                  </div>
                  <div className="hidden lg:block text-left text-xs">
                    <div className="font-bold text-[#17324D] leading-tight truncate max-w-[120px]">{user.full_name}</div>
                    <div className="text-[10px] text-[#697586] leading-tight">{user.role}</div>
                  </div>
                  <ChevronDown className="w-3.5 h-3.5 text-slate-400 hidden lg:block" />
                </button>

                {userMenuOpen && (
                  <div className="absolute right-0 mt-2 w-56 rounded-xl bg-white border border-[#E2E7EE] shadow-lg py-2 z-50">
                    <div className="px-3 py-2 border-b border-slate-100">
                      <div className="text-xs font-bold text-[#17324D]">{user.full_name}</div>
                      <div className="text-[11px] text-[#697586] truncate">{user.email}</div>
                    </div>
                    <Link
                      href="/profile"
                      onClick={() => setUserMenuOpen(false)}
                      className="block px-3 py-1.5 text-xs text-slate-700 hover:bg-[#EAF3FB] transition-colors"
                    >
                      Account Identity & Scopes
                    </Link>
                    <Link
                      href="/guide"
                      onClick={() => setUserMenuOpen(false)}
                      className="block px-3 py-1.5 text-xs text-[#1261A0] font-semibold hover:bg-[#EAF3FB] transition-colors"
                    >
                      {user.role === "TEACHER" ? "Faculty Guide" : user.role === "STUDENT" || user.role === "CR" ? "Student Guide" : "Staff Guide"}
                    </Link>
                    {user.role !== "STUDENT" && user.role !== "CR" && (
                      <>
                        <Link
                          href="/conflicts"
                          onClick={() => setUserMenuOpen(false)}
                          className="block px-3 py-1.5 text-xs text-slate-700 hover:bg-[#EAF3FB] transition-colors"
                        >
                          Conflict Detector Console
                        </Link>
                        <Link
                          href="/rescheduler"
                          onClick={() => setUserMenuOpen(false)}
                          className="block px-3 py-1.5 text-xs text-slate-700 hover:bg-[#EAF3FB] transition-colors"
                        >
                          Smart Rescheduler
                        </Link>
                      </>
                    )}
                    <button
                      onClick={() => {
                        setUserMenuOpen(false);
                        logout();
                      }}
                      className="w-full text-left px-3 py-1.5 text-xs text-rose-600 hover:bg-rose-50 transition-colors flex items-center"
                    >
                      <LogOut className="w-3.5 h-3.5 mr-1.5" /> Sign Out
                    </button>
                  </div>
                )}
              </div>
            ) : (
              <Link
                href="/login"
                className="px-3 py-1.5 rounded-lg bg-[#1261A0] text-white text-xs font-semibold hover:bg-[#0E4E82] transition-colors"
              >
                Sign In
              </Link>
            )}
          </div>
        </div>
      </header>

      {/* Primary Layout Body */}
      <div className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6 flex gap-6">
        {/* Desktop Persistent Sidebar */}
        <aside className="hidden lg:block w-64 flex-shrink-0">
          <div className="bg-white rounded-xl border border-[#E2E7EE] p-3 shadow-xs sticky top-24 space-y-1">
            <div className="px-3 py-2 text-[11px] font-bold uppercase tracking-wider text-[#697586]">
              Core Schedulers
            </div>
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = pathname === item.href;
              return (
                <Link
                  key={item.href}
                  id={item.id}
                  href={item.href}
                  className={`flex items-center justify-between px-3 py-2 rounded-lg text-xs font-medium transition-colors ${
                    isActive
                      ? "bg-[#EAF3FB] text-[#1261A0] font-bold"
                      : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
                  }`}
                >
                  <div className="flex items-center space-x-2.5">
                    <Icon className={`w-4 h-4 ${isActive ? "text-[#1261A0]" : "text-slate-400"}`} />
                    <span>{item.label}</span>
                  </div>
                  {item.badge && (
                    <span className="text-[10px] font-bold px-1.5 py-0.2 rounded-full bg-rose-100 text-[#B42332]">
                      {item.badge}
                    </span>
                  )}
                </Link>
              );
            })}

            <div className="pt-4 mt-4 border-t border-slate-100 px-3">
              <div className="p-3 rounded-lg bg-[#F7F9FC] border border-[#E2E7EE]">
                <div className="text-[11px] font-semibold text-[#17324D]">Academic Term</div>
                <div className="text-[10px] text-[#697586]">Spring Term 2026</div>
                <div className="mt-1 flex items-center text-[10px] text-emerald-600 font-semibold">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 mr-1"></span>
                  Active Master v1.0
                </div>
              </div>
            </div>
          </div>
        </aside>

        {/* Mobile Slide-Out Drawer Menu */}
        {mobileMenuOpen && (
          <div className="lg:hidden fixed inset-0 z-50 flex">
            <div className="fixed inset-0 bg-black/40 backdrop-blur-xs" onClick={() => setMobileMenuOpen(false)} />
            <div className="relative w-72 max-w-[80%] bg-white h-full shadow-2xl p-4 flex flex-col justify-between z-10">
              <div className="space-y-4">
                <div className="flex items-center justify-between pb-3 border-b border-slate-100">
                  <div className="flex items-center space-x-2">
                    <div className="w-8 h-8 relative flex-shrink-0">
                      <Image
                        src="/logo.png"
                        alt="Timeverse Logo"
                        width={32}
                        height={32}
                        className="object-contain"
                      />
                    </div>
                    <span className="font-bold text-sm text-[#17324D]">Timeverse Portal</span>
                  </div>
                  <button onClick={() => setMobileMenuOpen(false)} className="p-1 rounded-md text-slate-500 hover:bg-slate-100">
                    <X className="w-5 h-5" />
                  </button>
                </div>

                <div className="space-y-1">
                  {navItems.map((item) => {
                    const Icon = item.icon;
                    const isActive = pathname === item.href;
                    return (
                      <Link
                        key={item.href}
                        id={`mobile-${item.id}`}
                        href={item.href}
                        onClick={() => setMobileMenuOpen(false)}
                        className={`flex items-center justify-between px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                          isActive
                            ? "bg-[#EAF3FB] text-[#1261A0] font-bold"
                            : "text-slate-600 hover:bg-slate-50"
                        }`}
                      >
                        <div className="flex items-center space-x-3">
                          <Icon className="w-4 h-4 text-slate-400" />
                          <span>{item.label}</span>
                        </div>
                        {item.badge && (
                          <span className="text-[10px] font-bold px-1.5 py-0.5 rounded-full bg-rose-100 text-[#B42332]">
                            {item.badge}
                          </span>
                        )}
                      </Link>
                    );
                  })}
                </div>
              </div>

              {user && (
                <div className="pt-4 border-t border-slate-100">
                  <div className="text-xs font-bold text-slate-800">{user.full_name}</div>
                  <div className="text-[11px] text-slate-500">{user.email}</div>
                  <button
                    onClick={() => {
                      setMobileMenuOpen(false);
                      logout();
                    }}
                    className="mt-3 w-full py-2 px-3 rounded-lg bg-rose-50 text-rose-700 text-xs font-semibold flex items-center justify-center"
                  >
                    <LogOut className="w-3.5 h-3.5 mr-1" /> Sign Out
                  </button>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Main Content Pane */}
        <main className="flex-1 min-w-0 overflow-hidden">
          {children}
        </main>
      </div>

      {/* Mobile Sticky Bottom Navigation (<640px) */}
      <nav className="sm:hidden fixed bottom-0 left-0 right-0 bg-white border-t border-[#E2E7EE] px-2 py-2 flex items-center justify-around z-30 shadow-md">
        <Link
          href="/dashboard"
          className={`flex flex-col items-center py-1 px-2 rounded-lg text-[10px] font-semibold ${
            pathname.includes("/dashboard") ? "text-[#1261A0]" : "text-slate-500"
          }`}
        >
          <LayoutDashboard className="w-5 h-5 mb-0.5" />
          Dashboard
        </Link>
        <Link
          href="/timetables"
          className={`flex flex-col items-center py-1 px-2 rounded-lg text-[10px] font-semibold ${
            pathname.includes("/timetables") ? "text-[#1261A0]" : "text-slate-500"
          }`}
        >
          <Calendar className="w-5 h-5 mb-0.5" />
          Planner
        </Link>
        {user?.role === "STUDENT" || user?.role === "CR" ? (
          <Link
            href="/guide"
            className={`flex flex-col items-center py-1 px-2 rounded-lg text-[10px] font-semibold ${
              pathname.includes("/guide") ? "text-[#1261A0]" : "text-slate-500"
            }`}
          >
            <HelpCircle className="w-5 h-5 mb-0.5" />
            Guide
          </Link>
        ) : (
          <>
            <Link
              href="/rescheduler"
              className={`flex flex-col items-center py-1 px-2 rounded-lg text-[10px] font-semibold ${
                pathname.includes("/rescheduler") ? "text-[#1261A0]" : "text-slate-500"
              }`}
            >
              <RefreshCw className="w-5 h-5 mb-0.5" />
              Rescheduler
            </Link>
            <Link
              href="/conflicts"
              className={`flex flex-col items-center py-1 px-2 rounded-lg text-[10px] font-semibold relative ${
                pathname.includes("/conflicts") ? "text-[#1261A0]" : "text-slate-500"
              }`}
            >
              <AlertTriangle className="w-5 h-5 mb-0.5" />
              {conflictCount > 0 && (
                <span className="absolute top-0 right-2 w-2 h-2 rounded-full bg-[#B42332]" />
              )}
              Conflicts
            </Link>
          </>
        )}
        <button
          onClick={() => setMobileMenuOpen(true)}
          className="flex flex-col items-center py-1 px-2 rounded-lg text-[10px] font-semibold text-slate-500"
        >
          <Menu className="w-5 h-5 mb-0.5" />
          More
        </button>
      </nav>

      {/* Global Interactive Role Guided Tour */}
      <GuidedTour />
    </div>
  );
}
