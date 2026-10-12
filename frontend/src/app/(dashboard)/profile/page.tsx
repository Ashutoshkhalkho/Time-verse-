"use client";

import React from "react";
import { useAuth } from "@/context/AuthContext";
import {
  Check,
  Key,
  Lock,
  LogOut,
  Mail,
  MapPin,
  Shield,
  User,
  Users,
} from "lucide-react";

export default function ProfilePage() {
  const { user, logout } = useAuth();

  if (!user) {
    return (
      <div className="p-8 text-center bg-white rounded-xl border border-[#E2E7EE]">
        <h3 className="text-base font-bold text-[#17324D]">Not Signed In</h3>
        <p className="text-xs text-[#697586] mt-1">Please sign in to view your profile settings.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6 pb-12">
      {/* Header Banner */}
      <div className="bg-white rounded-xl border border-[#E2E7EE] p-5 sm:p-6 shadow-xs flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2">
            <span className="text-xs font-bold uppercase tracking-wider text-[#1261A0] bg-[#EAF3FB] px-2 py-0.5 rounded">
              Account Security & Identity
            </span>
            <span className="text-xs text-[#697586]">• Institutional Profile</span>
          </div>
          <h1 className="text-xl sm:text-2xl font-bold text-[#17324D] mt-1">
            User Profile & Scoped Access Rights
          </h1>
          <p className="text-xs sm:text-sm text-[#697586] mt-0.5">
            Server-enforced multi-tenant credentials, role permissions, and session management.
          </p>
        </div>

        <button
          onClick={() => logout()}
          className="px-3.5 py-2 rounded-lg bg-rose-50 text-rose-700 hover:bg-rose-100 text-xs font-semibold flex items-center transition-colors"
        >
          <LogOut className="w-3.5 h-3.5 mr-1.5" />
          End Session & Sign Out
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* User Card */}
        <div className="bg-white rounded-xl border border-[#E2E7EE] p-5 shadow-xs flex flex-col items-center text-center space-y-3">
          <div className="w-20 h-20 rounded-full bg-[#17324D] text-white flex items-center justify-center font-bold text-2xl shadow-xs">
            {user.full_name?.charAt(0) || "U"}
          </div>
          <div>
            <h2 className="text-base font-bold text-[#17324D]">{user.full_name}</h2>
            <p className="text-xs text-[#697586] mt-0.5">{user.email}</p>
          </div>
          <span className="px-3 py-1 rounded-full text-xs font-bold bg-[#EAF3FB] text-[#1261A0] border border-blue-200">
            ● Role: {user.role}
          </span>
          <div className="pt-3 border-t border-slate-100 w-full text-xs text-left space-y-2">
            <div className="flex justify-between">
              <span className="text-[#697586]">Institution:</span>
              <span className="font-semibold text-slate-900">{user.institution_id || "timewise-main"}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-[#697586]">Account Status:</span>
              <span className="font-semibold text-[#16805D]">Active / Verified</span>
            </div>
          </div>
        </div>

        {/* Scoped Boundaries & Permissions Matrix */}
        <div className="md:col-span-2 space-y-6">
          <div className="bg-white rounded-xl border border-[#E2E7EE] p-5 shadow-xs space-y-4">
            <div className="flex items-center space-x-2 border-b border-slate-100 pb-3">
              <Shield className="w-5 h-5 text-[#1261A0]" />
              <h3 className="font-bold text-sm text-[#17324D]">Resource Scoping Boundaries</h3>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
              <div className="p-3.5 rounded-xl bg-[#F7F9FC] border border-[#E2E7EE]">
                <div className="font-semibold text-slate-700 flex items-center">
                  <MapPin className="w-3.5 h-3.5 mr-1 text-[#1261A0]" /> Scoped Departments
                </div>
                <div className="mt-1 text-slate-900 font-mono text-[11px]">
                  {user.department_ids && user.department_ids.length > 0
                    ? user.department_ids.join(", ")
                    : "Campus-wide (All Departments)"}
                </div>
              </div>

              <div className="p-3.5 rounded-xl bg-[#F7F9FC] border border-[#E2E7EE]">
                <div className="font-semibold text-slate-700 flex items-center">
                  <Users className="w-3.5 h-3.5 mr-1 text-[#1261A0]" /> Scoped Cohort Sections
                </div>
                <div className="mt-1 text-slate-900 font-mono text-[11px]">
                  {user.section_ids && user.section_ids.length > 0
                    ? user.section_ids.join(", ")
                    : "No specific section restriction"}
                </div>
              </div>
            </div>

            {/* Server-Enforced Permissions */}
            <div className="pt-2">
              <h4 className="text-xs font-bold text-slate-700 uppercase tracking-wider mb-2">
                Server-Enforced Privileges
              </h4>
              <div className="flex flex-wrap gap-1.5">
                {user.permissions && user.permissions.length > 0 ? (
                  user.permissions.map((perm) => (
                    <span
                      key={perm}
                      className="px-2.5 py-1 rounded-md text-[10px] font-mono font-medium bg-slate-100 text-slate-700 border border-slate-200"
                    >
                      {perm}
                    </span>
                  ))
                ) : (
                  <span className="text-xs text-slate-400">Standard student privileges applied.</span>
                )}
              </div>
            </div>
          </div>

          {/* Security & Authentication Protocol */}
          <div className="bg-white rounded-xl border border-[#E2E7EE] p-5 shadow-xs space-y-3">
            <div className="flex items-center space-x-2 border-b border-slate-100 pb-3">
              <Lock className="w-5 h-5 text-[#1261A0]" />
              <h3 className="font-bold text-sm text-[#17324D]">Cryptographic Security Ledger</h3>
            </div>
            <p className="text-xs text-[#697586] leading-relaxed">
              Timeverse utilizes Argon2id password derivation, short-lived JWT access tokens with Redis revocation
              auditing, and tamper-evident SHA-256 audit chaining on all administrative and scheduling modifications.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
