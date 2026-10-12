"use client";

import React, { useCallback, useEffect, useState } from "react";
import { useAuth, UserRole } from "@/context/AuthContext";
import { apiRequest } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { UserPlus, Shield, History, CheckCircle2, AlertTriangle, ArrowLeft } from "lucide-react";
import Link from "next/link";

interface UserItem {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  is_active: boolean;
  department_ids: string[];
  section_ids: string[];
  created_at: string;
}

interface AuditLog {
  id: string;
  actor_user_id: string | null;
  action: string;
  resource_type: string;
  resource_id: string;
  reason: string | null;
  created_at: string;
}

export default function AdminUsersPage() {
  const { user, hasPermission } = useAuth();
  const [users, setUsers] = useState<UserItem[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // User creation form state
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [role, setRole] = useState<UserRole>("TEACHER");
  const [deptId, setDeptId] = useState("dept_cs");
  const [secId, setSecId] = useState("sec_cs_3a");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const fetchData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const userList = await apiRequest<UserItem[]>("/users");
      setUsers(userList);

      if (user?.role === "ADMIN") {
        const logs = await apiRequest<AuditLog[]>("/audit/logs");
        setAuditLogs(logs);
      }
    } catch (err: any) {
      setError(err?.detail || "Failed to load user management records.");
    } finally {
      setIsLoading(false);
    }
  }, [user]);

  useEffect(() => {
    if (user) {
      fetchData();
    }
  }, [user, fetchData]);

  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    setIsSubmitting(true);

    try {
      await apiRequest("/users", {
        method: "POST",
        body: JSON.stringify({
          email,
          password,
          full_name: fullName,
          role,
          department_ids: [deptId],
          section_ids: role === "STUDENT" || role === "CR" ? [secId] : [],
        }),
      });

      setSuccess(`User account '${email}' provisioned successfully.`);
      setEmail("");
      setPassword("");
      setFullName("");
      await fetchData();
    } catch (err: any) {
      setError(err?.detail || "User provisioning failed.");
    } finally {
      setIsSubmitting(false);
    }
  };

  if (!user || (!hasPermission("user:create") && user.role !== "ADMIN" && user.role !== "HOD")) {
    return (
      <div className="min-h-screen p-8 flex items-center justify-center">
        <Card className="max-w-md w-full border-status-danger/20 bg-white p-6 text-center space-y-4">
          <AlertTriangle className="w-12 h-12 text-status-danger mx-auto" />
          <h2 className="text-xl font-bold text-navy">Access Forbidden (403)</h2>
          <p className="text-sm text-text-secondary">
            Your role does not possess permissions to administer users or view compliance logs.
          </p>
          <Link href="/">
            <Button variant="outline">Return to Portal</Button>
          </Link>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-surface-canvas p-4 sm:p-8 space-y-8 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <Link href="/" className="inline-flex items-center text-xs font-semibold text-primary hover:underline mb-2">
            <ArrowLeft className="w-3.5 h-3.5 mr-1" /> Back to Dashboard
          </Link>
          <h1 className="text-2xl font-bold text-navy">User Administration & Scoping</h1>
          <p className="text-sm text-text-secondary">
            Provision user accounts, configure role delegations, and inspect security audit events.
          </p>
        </div>
        <Badge variant="default" className="self-start sm:self-auto">
          Role: {user.role}
        </Badge>
      </div>

      {/* Messages */}
      {error && (
        <div className="p-4 rounded-btn bg-[#FCE8E6] border border-status-danger/20 text-status-danger text-sm flex items-center space-x-2">
          <AlertTriangle className="w-5 h-5 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}
      {success && (
        <div className="p-4 rounded-btn bg-[#E6F4EA] border border-status-success/20 text-status-success text-sm flex items-center space-x-2">
          <CheckCircle2 className="w-5 h-5 flex-shrink-0" />
          <span>{success}</span>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* User Provisioning Form (Admin only) */}
        {user.role === "ADMIN" && (
          <Card className="lg:col-span-1 shadow-sm">
            <CardHeader>
              <div className="flex items-center space-x-2">
                <UserPlus className="w-5 h-5 text-primary" />
                <CardTitle className="text-base">Provision New User</CardTitle>
              </div>
              <CardDescription>
                Assign initial roles and departmental authority.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleCreateUser} className="space-y-3">
                <div>
                  <label className="block text-xs font-semibold text-navy mb-1">Full Name</label>
                  <input
                    type="text"
                    required
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    placeholder="e.g. Dr. Ramesh Kumar"
                    className="w-full px-3 py-2 text-sm border rounded-btn border-surface-border"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-navy mb-1">Email Address</label>
                  <input
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="ramesh@timewise.edu"
                    className="w-full px-3 py-2 text-sm border rounded-btn border-surface-border"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-navy mb-1">Initial Password</label>
                  <input
                    type="password"
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="Min 8 characters"
                    className="w-full px-3 py-2 text-sm border rounded-btn border-surface-border"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-navy mb-1">Assigned Role</label>
                  <select
                    value={role}
                    onChange={(e) => setRole(e.target.value as UserRole)}
                    className="w-full px-3 py-2 text-sm border rounded-btn border-surface-border bg-white"
                  >
                    <option value="HOD">Head of Department (HOD)</option>
                    <option value="COORDINATOR">Timetable Coordinator</option>
                    <option value="TEACHER">Faculty / Teacher</option>
                    <option value="CR">Class Representative (CR)</option>
                    <option value="STUDENT">Student</option>
                    <option value="MENTOR">Mentor</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-navy mb-1">Department Jurisdiction</label>
                  <select
                    value={deptId}
                    onChange={(e) => setDeptId(e.target.value)}
                    className="w-full px-3 py-2 text-sm border rounded-btn border-surface-border bg-white"
                  >
                    <option value="dept_cs">Computer Science (dept_cs)</option>
                    <option value="dept_ee">Electronics Engineering (dept_ee)</option>
                  </select>
                </div>

                {(role === "STUDENT" || role === "CR") && (
                  <div>
                    <label className="block text-xs font-semibold text-navy mb-1">Enrolled Section</label>
                    <select
                      value={secId}
                      onChange={(e) => setSecId(e.target.value)}
                      className="w-full px-3 py-2 text-sm border rounded-btn border-surface-border bg-white"
                    >
                      <option value="sec_cs_3a">CS Year 3 Section A (sec_cs_3a)</option>
                      <option value="sec_ee_3a">EE Year 3 Section A (sec_ee_3a)</option>
                    </select>
                  </div>
                )}

                <Button type="submit" variant="primary" disabled={isSubmitting} className="w-full mt-2">
                  {isSubmitting ? "Provisioning..." : "Provision User"}
                </Button>
              </form>
            </CardContent>
          </Card>
        )}

        {/* User Directory Table */}
        <div className={user.role === "ADMIN" ? "lg:col-span-2 space-y-8" : "lg:col-span-3 space-y-8"}>
          <Card className="shadow-sm">
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <div>
                <CardTitle className="text-base">User Directory</CardTitle>
                <CardDescription>Accounts within your authority scope.</CardDescription>
              </div>
              <Badge variant="secondary">{users.length} Users</Badge>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs border-collapse">
                  <thead>
                    <tr className="border-b border-surface-border text-text-secondary bg-surface-canvas/50">
                      <th className="py-2.5 px-3">User</th>
                      <th className="py-2.5 px-3">Role</th>
                      <th className="py-2.5 px-3">Departments</th>
                      <th className="py-2.5 px-3">Sections</th>
                      <th className="py-2.5 px-3">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-surface-border">
                    {users.map((u) => (
                      <tr key={u.id} className="hover:bg-primary-light/30">
                        <td className="py-2.5 px-3">
                          <div className="font-semibold text-navy">{u.full_name}</div>
                          <div className="text-text-secondary text-[11px]">{u.email}</div>
                        </td>
                        <td className="py-2.5 px-3">
                          <Badge variant="default">{u.role}</Badge>
                        </td>
                        <td className="py-2.5 px-3 text-text-secondary">
                          {u.department_ids.join(", ") || "Global"}
                        </td>
                        <td className="py-2.5 px-3 text-text-secondary">
                          {u.section_ids.join(", ") || "—"}
                        </td>
                        <td className="py-2.5 px-3">
                          <Badge variant={u.is_active ? "success" : "danger"}>
                            {u.is_active ? "Active" : "Disabled"}
                          </Badge>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>

          {/* Security Audit Events (Admin only) */}
          {user.role === "ADMIN" && (
            <Card className="shadow-sm">
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <div className="flex items-center space-x-2">
                  <History className="w-5 h-5 text-primary" />
                  <CardTitle className="text-base">Security Audit Ledger</CardTitle>
                </div>
                <Badge variant="secondary">Immutable Compliance Log</Badge>
              </CardHeader>
              <CardContent>
                <div className="overflow-x-auto max-h-72 overflow-y-auto">
                  <table className="w-full text-left text-xs border-collapse">
                    <thead>
                      <tr className="border-b border-surface-border text-text-secondary bg-surface-canvas/50 sticky top-0">
                        <th className="py-2 px-3">Action</th>
                        <th className="py-2 px-3">Resource</th>
                        <th className="py-2 px-3">Reason</th>
                        <th className="py-2 px-3">Timestamp (UTC)</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-surface-border">
                      {auditLogs.map((log) => (
                        <tr key={log.id}>
                          <td className="py-2 px-3 font-semibold text-navy">
                            <Badge variant="secondary">{log.action}</Badge>
                          </td>
                          <td className="py-2 px-3 text-text-secondary">{log.resource_type}:{log.resource_id}</td>
                          <td className="py-2 px-3 text-text-secondary">{log.reason || "—"}</td>
                          <td className="py-2 px-3 text-[11px] text-text-muted">{new Date(log.created_at).toLocaleString()}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
