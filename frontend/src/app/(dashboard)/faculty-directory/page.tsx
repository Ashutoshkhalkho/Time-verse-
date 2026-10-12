"use client";

import React, { useEffect, useMemo, useState } from "react";
import { useAuth } from "@/context/AuthContext";
import { apiRequest } from "@/lib/api";
import {
  AlertCircle,
  AlertTriangle,
  Archive,
  ArrowUpDown,
  BookOpen,
  Building2,
  Calendar,
  Check,
  CheckCircle,
  Clock,
  Copy,
  Download,
  Edit,
  Eye,
  FileSpreadsheet,
  Filter,
  GraduationCap,
  HelpCircle,
  Info,
  Layers,
  Mail,
  MapPin,
  Plus,
  RefreshCw,
  Search,
  ShieldAlert,
  ShieldCheck,
  Table as TableIcon,
  Upload,
  User,
  UserCheck,
  Users,
  X,
} from "lucide-react";

interface FacultyMember {
  id: string;
  full_name: string;
  normalized_name: string;
  designation: string | null;
  department: string;
  institution: string;
  faculty_id: string | null;
  official_email: string | null;
  profile_photo: string | null;
  subjects_taught: string[];
  specialisation: string | null;
  office_location: string | null;
  profile_status: "PENDING_VERIFICATION" | "ACTIVE" | "INACTIVE";
  is_verified: boolean;
  source_notes: string | null;
  verification_notes: string | null;
  verified_by_user_id: string | null;
  verified_by_name: string | null;
  verified_at: string | null;
  archived_at: string | null;
  duplicate_flag: boolean;
  duplicate_notes: string | null;
  potential_duplicate_of_id: string | null;
  missing_fields: string[];
  created_at: string;
  updated_at: string;
}

interface CSVPreviewRow {
  row_number: number;
  full_name: string;

  raw_designation: string | null;
  mapped_designation: string | null;
  source_notes: string | null;
  is_valid: boolean;
  validation_errors: string[];
  is_potential_duplicate: boolean;
  potential_duplicate_reason: string | null;
  existing_member_id: string | null;
  existing_member_name: string | null;
  existing_is_verified: boolean;
  unrecognized_columns: Record<string, any>;
}

interface CSVPreviewData {
  total_rows: number;
  valid_rows_count: number;
  invalid_rows_count: number;
  potential_duplicates_count: number;
  detected_headers: string[];
  unrecognized_headers: string[];
  rows: CSVPreviewRow[];
}

export default function FacultyDirectoryPage() {
  const { user } = useAuth();
  const isAdmin = ["ADMIN", "HOD", "COORDINATOR"].includes(user?.role || "");

  // Directory Data State
  const [members, setMembers] = useState<FacultyMember[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Filters and Search
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [selectedDesignation, setSelectedDesignation] = useState<string>("ALL");
  const [selectedStatus, setSelectedStatus] = useState<string>("ALL");
  const [sortBy, setSortBy] = useState<string>("name_asc");
  const [viewMode, setViewMode] = useState<"cards" | "table">("cards");
  const [includeArchived, setIncludeArchived] = useState<boolean>(false);
  const [duplicateFilterOnly, setDuplicateFilterOnly] = useState<boolean>(false);

  // Modals & Drawers
  const [selectedMember, setSelectedMember] = useState<FacultyMember | null>(null);
  const [isDetailOpen, setIsDetailOpen] = useState<boolean>(false);

  const [isAddEditOpen, setIsAddEditOpen] = useState<boolean>(false);
  const [editingMember, setEditingMember] = useState<FacultyMember | null>(null);
  const [formFullName, setFormFullName] = useState<string>("");
  const [formDesignation, setFormDesignation] = useState<string>("");
  const [formFacultyId, setFormFacultyId] = useState<string>("");
  const [formOfficialEmail, setFormOfficialEmail] = useState<string>("");
  const [formSubjectsTaught, setFormSubjectsTaught] = useState<string>("");
  const [formSpecialisation, setFormSpecialisation] = useState<string>("");
  const [formOfficeLocation, setFormOfficeLocation] = useState<string>("");
  const [formProfileStatus, setFormProfileStatus] = useState<"PENDING_VERIFICATION" | "ACTIVE" | "INACTIVE">("PENDING_VERIFICATION");
  const [formSourceNotes, setFormSourceNotes] = useState<string>("");
  const [formError, setFormError] = useState<string | null>(null);
  const [submittingForm, setSubmittingForm] = useState<boolean>(false);

  // Verification Modal
  const [isVerifyOpen, setIsVerifyOpen] = useState<boolean>(false);
  const [memberToVerify, setMemberToVerify] = useState<FacultyMember | null>(null);
  const [verifyDesignation, setVerifyDesignation] = useState<string>("");
  const [verifyNotes, setVerifyNotes] = useState<string>("");
  const [verifyAcknowledged, setVerifyAcknowledged] = useState<boolean>(false);
  const [verifySubmitting, setVerifySubmitting] = useState<boolean>(false);
  const [verifyError, setVerifyError] = useState<string | null>(null);

  // Archiving Modal
  const [isArchiveOpen, setIsArchiveOpen] = useState<boolean>(false);
  const [memberToArchive, setMemberToArchive] = useState<FacultyMember | null>(null);
  const [archiveReason, setArchiveReason] = useState<string>("");
  const [archiveConfirmed, setArchiveConfirmed] = useState<boolean>(false);
  const [archiveSubmitting, setArchiveSubmitting] = useState<boolean>(false);

  // CSV Import Modal
  const [isCSVModalOpen, setIsCSVModalOpen] = useState<boolean>(false);
  const [csvFile, setCsvFile] = useState<File | null>(null);
  const [csvPreviewData, setCsvPreviewData] = useState<CSVPreviewData | null>(null);
  const [csvPreviewLoading, setCsvPreviewLoading] = useState<boolean>(false);
  const [csvCommitLoading, setCsvCommitLoading] = useState<boolean>(false);
  const [csvError, setCsvError] = useState<string | null>(null);
  const [csvCommitConfirmed, setCsvCommitConfirmed] = useState<boolean>(false);
  const [csvOverwriteVerified, setCsvOverwriteVerified] = useState<boolean>(false);
  const [csvResultSummary, setCsvResultSummary] = useState<any | null>(null);

  // Fetch directory records
  const fetchFaculty = async () => {
    try {
      setLoading(true);
      setError(null);
      const params = new URLSearchParams();
      if (searchQuery.trim()) params.append("search", searchQuery.trim());
      if (selectedDesignation !== "ALL") params.append("designation", selectedDesignation);
      if (selectedStatus !== "ALL") params.append("profile_status", selectedStatus);
      if (includeArchived) params.append("include_archived", "true");
      params.append("sort_by", sortBy);

      const res: any = await apiRequest(`/faculty-directory?${params.toString()}`);
      setMembers(Array.isArray(res) ? res : []);
    } catch (err: any) {
      setError(err?.message || "Failed to load faculty directory records.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchFaculty();
  }, [searchQuery, selectedDesignation, selectedStatus, sortBy, includeArchived]);

  // Derived Designations for filter dropdown
  const availableDesignations = useMemo(() => {
    const set = new Set<string>();
    members.forEach((m) => {
      if (m.designation) set.add(m.designation);
    });
    return Array.from(set).sort();
  }, [members]);

  // Filtered members list
  const displayedMembers = useMemo(() => {
    let list = members;
    if (duplicateFilterOnly) {
      list = list.filter((m) => m.duplicate_flag);
    }
    return list;
  }, [members, duplicateFilterOnly]);

  const duplicateCount = useMemo(() => {
    return members.filter((m) => m.duplicate_flag).length;
  }, [members]);

  // Open Add/Edit Modal
  const handleOpenAdd = () => {
    setEditingMember(null);
    setFormFullName("");
    setFormDesignation("");
    setFormFacultyId("");
    setFormOfficialEmail("");
    setFormSubjectsTaught("");
    setFormSpecialisation("");
    setFormOfficeLocation("");
    setFormProfileStatus("PENDING_VERIFICATION");
    setFormSourceNotes("");
    setFormError(null);
    setIsAddEditOpen(true);
  };

  const handleOpenEdit = (m: FacultyMember) => {
    setEditingMember(m);
    setFormFullName(m.full_name);
    setFormDesignation(m.designation || "");
    setFormFacultyId(m.faculty_id || "");
    setFormOfficialEmail(m.official_email || "");
    setFormSubjectsTaught(m.subjects_taught.join(", "));
    setFormSpecialisation(m.specialisation || "");
    setFormOfficeLocation(m.office_location || "");
    setFormProfileStatus(m.profile_status);
    setFormSourceNotes(m.source_notes || "");
    setFormError(null);
    setIsAddEditOpen(true);
  };

  const handleSaveMember = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formFullName.trim()) {
      setFormError("Faculty member full name is required.");
      return;
    }

    try {
      setSubmittingForm(true);
      setFormError(null);
      const subjectsArray = formSubjectsTaught
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);

      const payload: any = {
        full_name: formFullName.trim(),
        designation: formDesignation.trim() || null,
        department: "Department of Professional Management Studies",
        institution: "Kristu Jayanti University",
        faculty_id: formFacultyId.trim() || null,
        official_email: formOfficialEmail.trim() || null,
        subjects_taught: subjectsArray,
        specialisation: formSpecialisation.trim() || null,
        office_location: formOfficeLocation.trim() || null,
        profile_status: formProfileStatus,
        source_notes: formSourceNotes.trim() || null,
      };

      if (editingMember) {
        await apiRequest(`/faculty-directory/${editingMember.id}`, {
          method: "PUT",
          body: JSON.stringify(payload),
        });
        setSuccessMessage(`Updated profile for ${formFullName.trim()}`);
      } else {
        await apiRequest("/faculty-directory", {
          method: "POST",
          body: JSON.stringify(payload),
        });
        setSuccessMessage(`Added faculty record for ${formFullName.trim()}`);
      }

      setIsAddEditOpen(false);
      fetchFaculty();
    } catch (err: any) {
      setFormError(err?.message || "Failed to save faculty record.");
    } finally {
      setSubmittingForm(false);
    }
  };

  // Open Verification Modal
  const handleOpenVerify = (m: FacultyMember) => {
    setMemberToVerify(m);
    setVerifyDesignation(m.designation || "");
    setVerifyNotes("");
    setVerifyAcknowledged(false);
    setVerifyError(null);
    setIsVerifyOpen(true);
  };

  const handleCommitVerify = async () => {
    if (!memberToVerify) return;
    if (!verifyAcknowledged) {
      setVerifyError("You must acknowledge responsibility before certifying verification.");
      return;
    }
    if (!verifyNotes.trim() || verifyNotes.trim().length < 5) {
      setVerifyError("Please provide an administrative note explaining the basis of verification.");
      return;
    }

    try {
      setVerifySubmitting(true);
      setVerifyError(null);
      await apiRequest(`/faculty-directory/${memberToVerify.id}/verify`, {
        method: "POST",
        body: JSON.stringify({
          designation: verifyDesignation.trim() || null,
          verification_notes: verifyNotes.trim(),
          acknowledged_responsibility: true,
          profile_status: "ACTIVE",
        }),
      });

      setSuccessMessage(`Profile for ${memberToVerify.full_name} has been formally verified.`);
      setIsVerifyOpen(false);
      if (selectedMember && selectedMember.id === memberToVerify.id) {
        setIsDetailOpen(false);
      }
      fetchFaculty();
    } catch (err: any) {
      setVerifyError(err?.message || "Verification failed.");
    } finally {
      setVerifySubmitting(false);
    }
  };

  // Open Archive Modal
  const handleOpenArchive = (m: FacultyMember) => {
    setMemberToArchive(m);
    setArchiveReason("");
    setArchiveConfirmed(false);
    setIsArchiveOpen(true);
  };

  const handleCommitArchive = async () => {
    if (!memberToArchive) return;
    if (!archiveConfirmed) return;

    try {
      setArchiveSubmitting(true);
      await apiRequest(`/faculty-directory/${memberToArchive.id}/archive`, {
        method: "POST",
        body: JSON.stringify({
          confirmed: true,
          reason: archiveReason.trim() || "Soft-archived by authorized administrator",
        }),
      });
      setSuccessMessage(`Record for ${memberToArchive.full_name} has been archived.`);
      setIsArchiveOpen(false);
      if (selectedMember?.id === memberToArchive.id) {
        setIsDetailOpen(false);
      }
      fetchFaculty();
    } catch (err: any) {
      setError(err?.message || "Failed to archive record.");
    } finally {
      setArchiveSubmitting(false);
    }
  };

  const handleRestoreRecord = async (m: FacultyMember) => {
    try {
      await apiRequest(`/faculty-directory/${m.id}/restore`, { method: "POST" });
      setSuccessMessage(`Restored profile for ${m.full_name}`);
      fetchFaculty();
    } catch (err: any) {
      setError(err?.message || "Failed to restore record.");
    }
  };

  // CSV Import Workflow
  const handlePreviewCSVFile = async (fileToPreview: File | null) => {
    if (!fileToPreview) return;
    try {
      setCsvPreviewLoading(true);
      setCsvError(null);
      const formData = new FormData();
      formData.append("file", fileToPreview);

      const res: any = await apiRequest("/faculty-directory/preview-csv", {
        method: "POST",
        body: formData,
      });
      setCsvPreviewData(res);
      setCsvCommitConfirmed(false);
    } catch (err: any) {
      setCsvError(err?.message || "Failed to parse and preview CSV file.");
    } finally {
      setCsvPreviewLoading(false);
    }
  };

  const handleLoadBundledCSV = async () => {
    try {
      setCsvPreviewLoading(true);
      setCsvError(null);
      // Fetch bundled CSV content directly
      const csvRes = await fetch("/KJU_DPMS_Faculty_and_Designations.csv").catch(() => null);
      let text = "";
      if (csvRes && csvRes.ok) {
        text = await csvRes.text();
      } else {
        // Fallback default bundled data
        text = `No.,Faculty member,Designation (as found in public sources),Source / verification note
1,Dr. V. G. Jisha,"Head, Department of Professional Management Studies",Official department FDP document (2025) — Confirmed in cited university source
2,Dr. C. H. Raja Kamal,Not verified,KJU research-project records / staff coordinator listing — Designation not confirmed in source reviewed
3,Dr. A. J. Excelce,Associate Professor,Official KJU FDP page / 2025 FDP document — Confirmed in cited university source
4,Dr. Ajai Abraham Thomas,"Coordinator, Department of Professional Management Studies",Official KJU FDP document (2025) — Confirmed in cited university source
5,Dr. Sivaprasad V,Not verified,KJU research-project records / staff coordinator listing — Designation not confirmed in source reviewed
6,Dr. Eshan M. R.,Not verified,KJU research-project records — Designation not confirmed in source reviewed
7,Dr. Roshen Therese Sebastian,Assistant Professor (listed in 2023–24 report),KJU annual report 2023–24 — Historical designation; current status unverified
8,Dr. Jagdeep Singh,Not verified,KJU faculty achievements page — Designation not confirmed in source reviewed
9,Dr. Arunkumar B,Assistant Professor,Official KJU FDP document (2025) — Confirmed in cited university source
10,Mr. Haribaskar R,Assistant Professor (listed in 2023–24 report),KJU annual report 2023–24 — Historical designation; current status unverified
11,Mr. Vipulkumar N. M.,Not verified,KJU research-project records — Designation not confirmed in source reviewed
12,Mr. Leslie Dass P,Not verified,KJU research-project records (listed as Mr. Leslie) — Name/designation needs confirmation
13,Ms. C. Shilpa Rao,Assistant Professor (listed in 2023–24 report),KJU annual report 2023–24 — Historical designation; current status unverified
14,Ms. Rupashree R,Assistant Professor (listed in 2023–24 report),KJU annual report 2023–24 — Historical designation; current status unverified
15,Ms. Ponny Thomas,Not verified,KJU research-project records — Designation not confirmed in source reviewed
16,Dr. Manju M. Kaimal,Not verified,KJU faculty achievements page lists Ms. Manju M Kaimal — Name/title discrepancy; verify with department
17,Dr. Subha B,Not verified,KJU faculty achievements page — Designation not confirmed in source reviewed
18,Ms. Syalini S,Not verified,Previously compiled list; no current designation verified — Needs official confirmation
19,Dr. Bincy Ann Babu,Not verified,Previously compiled list; no current designation verified — Needs official confirmation
20,Dr. Manisha Seal,Not verified,KJU library listing identifies department affiliation — Designation not confirmed in source reviewed
21,Dr. Ashy Sebastian,Not verified,Previously compiled list; no current designation verified — Needs official confirmation
22,Dr. V. S. Divyasre,Not verified,KJU faculty achievements page — Designation not confirmed in source reviewed
23,Ms. Divya Sajan,Not verified,Previously compiled list; no current designation verified — Needs official confirmation
24,Ms. Shilpa Rao,Possible duplicate of Ms. C. Shilpa Rao,KJU records use 'Ms. Shilpa Rao C' and 'Ms. C. Shilpa Rao' — Likely duplicate; confirm
25,Dr. Marina Joshy C.,Not verified,Previously compiled list; no current designation verified — Needs official confirmation
26,Ms. Priya A,Not verified,Previously compiled list; no current designation verified — Needs official confirmation`;
      }

      const formData = new FormData();
      formData.append("raw_csv_text", text);

      const res: any = await apiRequest("/faculty-directory/preview-csv", {
        method: "POST",
        body: formData,
      });
      setCsvPreviewData(res);
      setCsvCommitConfirmed(false);
    } catch (err: any) {
      setCsvError(err?.message || "Failed to load bundled CSV preview.");
    } finally {
      setCsvPreviewLoading(false);
    }
  };

  const handleCommitCSVImport = async () => {
    if (!csvPreviewData || !csvCommitConfirmed) return;
    try {
      setCsvCommitLoading(true);
      setCsvError(null);

      const rowsPayload = csvPreviewData.rows.map((r) => ({
        full_name: r.full_name,
        designation: r.mapped_designation,
        source_notes: r.source_notes,
        unrecognized_columns: r.unrecognized_columns,
      }));

      const res: any = await apiRequest("/faculty-directory/commit-csv", {
        method: "POST",
        body: JSON.stringify({
          confirmed: true,
          overwrite_verified: csvOverwriteVerified,
          rows: rowsPayload,
        }),
      });

      setCsvResultSummary(res);
      setSuccessMessage(
        `Import completed: ${res.created_count} created, ${res.updated_count} updated, ${res.skipped_count} skipped.`
      );
      fetchFaculty();
    } catch (err: any) {
      setCsvError(err?.message || "Failed to commit CSV import.");
    } finally {
      setCsvCommitLoading(false);
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      {/* Institutional Department Header Banner */}
      <div className="bg-white border border-[#E2E7EE] rounded-2xl p-6 sm:p-8 shadow-xs">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="space-y-2">
            <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-full text-xs font-semibold bg-[#EEF2F6] text-[#17324D] border border-[#D0D7E2]">
              <Building2 className="w-3.5 h-3.5 text-[#2E6B9E]" />
              Kristu Jayanti University • Bengaluru
            </div>
            <h1 className="text-2xl sm:text-3xl font-bold text-[#17324D] tracking-tight">
              Faculty Directory
            </h1>
            <p className="text-sm font-medium text-[#4B5565]">
              Department of Professional Management Studies (DPMS)
            </p>
            <div className="flex items-start gap-2 pt-1 text-xs text-[#697586] max-w-3xl">
              <Info className="w-4 h-4 text-[#2E6B9E] shrink-0 mt-0.5" />
              <span>
                Faculty profiles reflect the current 26 official department records. Formal designations remain unverified
                until verified through official university registers by an authorized administrator. Missing information is
                honestly indicated without simulated values.
              </span>
            </div>
          </div>

          {/* Action Bar for Administrators */}
          {isAdmin && (
            <div className="flex flex-wrap items-center gap-3">
              <button
                onClick={() => {
                  setCsvPreviewData(null);
                  setCsvResultSummary(null);
                  setCsvError(null);
                  setIsCSVModalOpen(true);
                }}
                className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl border border-[#D0D7E2] bg-white text-[#17324D] hover:bg-[#F8FAFC] text-xs font-semibold shadow-xs transition"
              >
                <FileSpreadsheet className="w-4 h-4 text-[#2E6B9E]" />
                CSV Importer & Preview
              </button>

              <button
                onClick={handleOpenAdd}
                className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-[#17324D] hover:bg-[#1E4265] text-white text-xs font-semibold shadow-sm transition"
              >
                <Plus className="w-4 h-4" />
                Add Faculty Member
              </button>
            </div>
          )}
        </div>

        {/* Potential Duplicate Banner */}
        {duplicateCount > 0 && (
          <div className="mt-6 p-4 rounded-xl bg-amber-50 border border-amber-200 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="flex items-center gap-2.5 text-xs text-amber-900">
              <ShieldAlert className="w-4 h-4 text-amber-700 shrink-0" />
              <div>
                <span className="font-bold">{duplicateCount} Potential Duplicate Records Detected</span> (e.g.{" "}
                <span className="font-semibold">Ms. C. Shilpa Rao</span> and <span className="font-semibold">Ms. Shilpa Rao</span>).
                Preserved as separate entries for manual administrative review.
              </div>
            </div>
            <button
              onClick={() => setDuplicateFilterOnly(!duplicateFilterOnly)}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition shrink-0 ${
                duplicateFilterOnly
                  ? "bg-amber-700 text-white"
                  : "bg-white border border-amber-300 text-amber-900 hover:bg-amber-100"
              }`}
            >
              {duplicateFilterOnly ? "Show All Records" : "Review Potential Duplicates"}
            </button>
          </div>
        )}
      </div>

      {/* Global Alerts / Toasts */}
      {successMessage && (
        <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-200 flex items-center justify-between gap-3 text-xs text-emerald-800">
          <div className="flex items-center gap-2">
            <CheckCircle className="w-4 h-4 text-emerald-600 shrink-0" />
            <span className="font-medium">{successMessage}</span>
          </div>
          <button onClick={() => setSuccessMessage(null)} className="text-emerald-700 hover:text-emerald-900">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {error && (
        <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 flex items-center justify-between gap-3 text-xs text-rose-800">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
            <span className="font-medium">{error}</span>
          </div>
          <button onClick={() => setError(null)} className="text-rose-700 hover:text-rose-900">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Controls & Filtering Bar */}
      <div className="bg-white border border-[#E2E7EE] rounded-2xl p-4 sm:p-5 shadow-xs flex flex-col lg:flex-row items-stretch lg:items-center justify-between gap-4">
        {/* Search */}
        <div className="relative flex-1 min-w-[240px]">
          <Search className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-[#697586]" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search faculty name, designation, specialisation..."
            className="w-full pl-10 pr-4 py-2 text-xs rounded-xl border border-[#D0D7E2] bg-[#F8FAFC] focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#17324D]/20 focus:border-[#17324D] transition"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery("")}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>

        {/* Dropdowns */}
        <div className="flex flex-wrap items-center gap-2 sm:gap-3">
          {/* Designation Filter */}
          <div className="flex items-center gap-1.5 text-xs text-[#4B5565]">
            <Filter className="w-3.5 h-3.5 text-[#697586]" />
            <select
              value={selectedDesignation}
              onChange={(e) => setSelectedDesignation(e.target.value)}
              className="py-1.5 px-2.5 text-xs rounded-lg border border-[#D0D7E2] bg-[#F8FAFC] text-[#17324D] focus:outline-none focus:ring-1 focus:ring-[#17324D]"
            >
              <option value="ALL">All Designations</option>
              <option value="UNVERIFIED">Unverified / None</option>
              {availableDesignations.map((d) => (
                <option key={d} value={d}>
                  {d}
                </option>
              ))}
            </select>
          </div>

          {/* Status Filter */}
          <select
            value={selectedStatus}
            onChange={(e) => setSelectedStatus(e.target.value)}
            className="py-1.5 px-2.5 text-xs rounded-lg border border-[#D0D7E2] bg-[#F8FAFC] text-[#17324D] focus:outline-none focus:ring-1 focus:ring-[#17324D]"
          >
            <option value="ALL">All Statuses</option>
            <option value="PENDING_VERIFICATION">Pending Verification</option>
            <option value="ACTIVE">Active</option>
            <option value="INACTIVE">Inactive</option>
          </select>

          {/* Sort By */}
          <div className="flex items-center gap-1 text-xs text-[#4B5565]">
            <ArrowUpDown className="w-3.5 h-3.5 text-[#697586]" />
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
              className="py-1.5 px-2.5 text-xs rounded-lg border border-[#D0D7E2] bg-[#F8FAFC] text-[#17324D] focus:outline-none focus:ring-1 focus:ring-[#17324D]"
            >
              <option value="name_asc">Alphabetical (A - Z)</option>
              <option value="name_desc">Alphabetical (Z - A)</option>
              <option value="verified_first">Verified First</option>
              <option value="created_desc">Recently Added</option>
            </select>
          </div>

          {/* Archived Toggle */}
          {isAdmin && (
            <label className="flex items-center gap-1.5 text-xs text-[#4B5565] cursor-pointer ml-1">
              <input
                type="checkbox"
                checked={includeArchived}
                onChange={(e) => setIncludeArchived(e.target.checked)}
                className="rounded border-[#D0D7E2] text-[#17324D] focus:ring-0"
              />
              <span>Archived</span>
            </label>
          )}

          {/* Cards / Table View Toggle */}
          <div className="flex items-center border border-[#D0D7E2] rounded-lg p-0.5 bg-[#F8FAFC] ml-auto sm:ml-0">
            <button
              onClick={() => setViewMode("cards")}
              className={`p-1.5 rounded text-xs transition ${
                viewMode === "cards" ? "bg-white text-[#17324D] shadow-xs font-semibold" : "text-[#697586]"
              }`}
              title="Grid Card View"
            >
              <Layers className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={() => setViewMode("table")}
              className={`p-1.5 rounded text-xs transition ${
                viewMode === "table" ? "bg-white text-[#17324D] shadow-xs font-semibold" : "text-[#697586]"
              }`}
              title="Table View"
            >
              <TableIcon className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>

      {/* Directory Grid / Table Display */}
      {loading ? (
        <div className="bg-white border border-[#E2E7EE] rounded-2xl p-16 text-center space-y-3">
          <RefreshCw className="w-6 h-6 animate-spin text-[#17324D] mx-auto" />
          <p className="text-xs font-medium text-[#697586]">Loading Kristu Jayanti University faculty directory...</p>
        </div>
      ) : displayedMembers.length === 0 ? (
        <div className="bg-white border border-[#E2E7EE] rounded-2xl p-16 text-center space-y-4">
          <Users className="w-10 h-10 text-slate-300 mx-auto" />
          <div>
            <h3 className="text-base font-semibold text-[#17324D]">No Faculty Records Found</h3>
            <p className="text-xs text-[#697586] mt-1">
              {searchQuery || selectedDesignation !== "ALL" || selectedStatus !== "ALL"
                ? "Try clearing your search query or adjusting your filters."
                : "No faculty records currently exist in the database."}
            </p>
          </div>
          {(searchQuery || selectedDesignation !== "ALL" || selectedStatus !== "ALL") && (
            <button
              onClick={() => {
                setSearchQuery("");
                setSelectedDesignation("ALL");
                setSelectedStatus("ALL");
                setDuplicateFilterOnly(false);
              }}
              className="px-4 py-2 rounded-xl text-xs font-semibold bg-[#17324D] text-white hover:bg-[#1E4265] transition"
            >
              Reset Filters
            </button>
          )}
        </div>
      ) : viewMode === "cards" ? (
        /* Responsive Card Grid */
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {displayedMembers.map((m) => (
            <div
              key={m.id}
              className={`bg-white border rounded-2xl p-5 shadow-xs flex flex-col justify-between transition hover:shadow-md ${
                m.archived_at
                  ? "border-slate-200 opacity-60 bg-slate-50"
                  : m.duplicate_flag
                  ? "border-amber-300 ring-1 ring-amber-200"
                  : "border-[#E2E7EE] hover:border-[#17324D]/30"
              }`}
            >
              <div>
                {/* Status Badges */}
                <div className="flex items-center justify-between gap-2 mb-3">
                  <div className="flex items-center gap-1.5 flex-wrap">
                    {m.is_verified ? (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-50 text-emerald-800 border border-emerald-200">
                        <ShieldCheck className="w-3 h-3 text-emerald-600" />
                        Verified
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-amber-50 text-amber-800 border border-amber-200">
                        <Clock className="w-3 h-3 text-amber-600" />
                        Pending Verification
                      </span>
                    )}

                    {m.archived_at && (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-slate-100 text-slate-700 border border-slate-300">
                        <Archive className="w-3 h-3" />
                        Archived
                      </span>
                    )}
                  </div>

                  {m.duplicate_flag && (
                    <span
                      title={m.duplicate_notes || "Potential duplicate record flagged for manual review"}
                      className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-100 text-amber-900 border border-amber-300"
                    >
                      <AlertTriangle className="w-3 h-3 text-amber-700" />
                      Duplicate Review
                    </span>
                  )}
                </div>

                {/* Name & Academic Avatar */}
                <div className="flex items-start gap-3">
                  <div className="w-11 h-11 rounded-xl bg-[#EEF2F6] border border-[#D0D7E2] flex items-center justify-center shrink-0 text-[#17324D] font-bold text-sm">
                    {m.full_name
                      .replace(/^(Dr\.|Mr\.|Ms\.|Mrs\.|Prof\.)\s*/i, "")
                      .charAt(0)
                      .toUpperCase() || "F"}
                  </div>
                  <div className="space-y-1 min-w-0">
                    <h3 className="text-sm font-bold text-[#17324D] tracking-tight truncate" title={m.full_name}>
                      {m.full_name}
                    </h3>
                    <p className="text-xs font-semibold text-[#2E6B9E]">
                      {m.designation || (
                        <span className="text-[#9AA4B2] font-normal italic">Designation Unverified</span>
                      )}
                    </p>
                    <p className="text-[11px] text-[#697586]">{m.department}</p>
                  </div>
                </div>

                {/* Honest Missing Information Badges */}
                <div className="mt-4 pt-3 border-t border-[#F0F3F7] space-y-1.5">
                  {m.official_email ? (
                    <div className="flex items-center gap-2 text-xs text-[#4B5565] truncate">
                      <Mail className="w-3.5 h-3.5 text-[#697586] shrink-0" />
                      <span className="truncate">{m.official_email}</span>
                    </div>
                  ) : (
                    <div className="flex items-center gap-2 text-[11px] text-slate-400">
                      <Mail className="w-3 h-3 text-slate-300 shrink-0" />
                      <span className="italic">Email: Not provided</span>
                    </div>
                  )}

                  {m.faculty_id ? (
                    <div className="flex items-center gap-2 text-xs text-[#4B5565]">
                      <User className="w-3.5 h-3.5 text-[#697586] shrink-0" />
                      <span>ID: {m.faculty_id}</span>
                    </div>
                  ) : (
                    <div className="flex items-center gap-2 text-[11px] text-slate-400">
                      <User className="w-3 h-3 text-slate-300 shrink-0" />
                      <span className="italic">Faculty ID: Unassigned</span>
                    </div>
                  )}

                  {m.source_notes && (
                    <div className="mt-2 p-2 rounded-lg bg-[#F8FAFC] border border-[#E2E7EE] text-[11px] text-[#4B5565] line-clamp-2">
                      <span className="font-semibold text-[#17324D]">Source: </span>
                      {m.source_notes}
                    </div>
                  )}
                </div>
              </div>

              {/* Card Footer Actions */}
              <div className="mt-5 pt-3 border-t border-[#F0F3F7] flex items-center justify-between gap-2">
                <button
                  onClick={() => {
                    setSelectedMember(m);
                    setIsDetailOpen(true);
                  }}
                  className="inline-flex items-center gap-1.5 text-xs font-semibold text-[#17324D] hover:text-[#2E6B9E] transition"
                >
                  <Eye className="w-3.5 h-3.5" />
                  View Details
                </button>

                {isAdmin && (
                  <div className="flex items-center gap-1">
                    {!m.is_verified && !m.archived_at && (
                      <button
                        onClick={() => handleOpenVerify(m)}
                        className="px-2.5 py-1 rounded-lg text-xs font-semibold bg-emerald-50 text-emerald-700 hover:bg-emerald-100 border border-emerald-200 transition"
                        title="Formally verify this record"
                      >
                        Verify
                      </button>
                    )}

                    <button
                      onClick={() => handleOpenEdit(m)}
                      className="p-1.5 rounded-lg text-slate-500 hover:text-slate-800 hover:bg-slate-100 transition"
                      title="Edit Profile"
                    >
                      <Edit className="w-3.5 h-3.5" />
                    </button>

                    {m.archived_at ? (
                      <button
                        onClick={() => handleRestoreRecord(m)}
                        className="px-2 py-1 rounded-lg text-[11px] font-semibold bg-slate-200 text-slate-800 hover:bg-slate-300 transition"
                      >
                        Restore
                      </button>
                    ) : (
                      <button
                        onClick={() => handleOpenArchive(m)}
                        className="p-1.5 rounded-lg text-slate-400 hover:text-rose-600 hover:bg-rose-50 transition"
                        title="Archive Profile"
                      >
                        <Archive className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      ) : (
        /* Compact Accessible Table View */
        <div className="bg-white border border-[#E2E7EE] rounded-2xl shadow-xs overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="bg-[#F8FAFC] border-b border-[#E2E7EE] text-[#4B5565] font-semibold">
                  <th className="py-3 px-4">Faculty Member</th>
                  <th className="py-3 px-4">Designation</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4">Faculty ID</th>
                  <th className="py-3 px-4">Official Email</th>
                  <th className="py-3 px-4">Source Notes</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#F0F3F7]">
                {displayedMembers.map((m) => (
                  <tr
                    key={m.id}
                    className={`hover:bg-[#F8FAFC] transition ${
                      m.duplicate_flag ? "bg-amber-50/50" : m.archived_at ? "bg-slate-50/60 opacity-60" : ""
                    }`}
                  >
                    <td className="py-3 px-4 font-bold text-[#17324D] whitespace-nowrap">
                      <div className="flex items-center gap-2">
                        <span>{m.full_name}</span>
                        {m.duplicate_flag && (
                          <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-amber-100 text-amber-900 border border-amber-300">
                            Dup Flag
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="py-3 px-4 text-[#2E6B9E] font-medium whitespace-nowrap">
                      {m.designation || <span className="text-slate-400 italic">Unverified</span>}
                    </td>
                    <td className="py-3 px-4 whitespace-nowrap">
                      {m.is_verified ? (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-50 text-emerald-800 border border-emerald-200">
                          <Check className="w-3 h-3 text-emerald-600" /> Verified
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-amber-50 text-amber-800 border border-amber-200">
                          Pending
                        </span>
                      )}
                    </td>
                    <td className="py-3 px-4 text-[#4B5565] whitespace-nowrap">
                      {m.faculty_id || <span className="text-slate-400 italic">—</span>}
                    </td>
                    <td className="py-3 px-4 text-[#4B5565] whitespace-nowrap">
                      {m.official_email || <span className="text-slate-400 italic">—</span>}
                    </td>
                    <td className="py-3 px-4 text-[#697586] max-w-xs truncate" title={m.source_notes || ""}>
                      {m.source_notes || <span className="text-slate-400 italic">—</span>}
                    </td>
                    <td className="py-3 px-4 text-right whitespace-nowrap">
                      <div className="flex items-center justify-end gap-1.5">
                        <button
                          onClick={() => {
                            setSelectedMember(m);
                            setIsDetailOpen(true);
                          }}
                          className="px-2 py-1 rounded text-xs font-semibold text-[#17324D] hover:bg-slate-100"
                        >
                          Details
                        </button>

                        {isAdmin && (
                          <>
                            {!m.is_verified && !m.archived_at && (
                              <button
                                onClick={() => handleOpenVerify(m)}
                                className="px-2 py-1 rounded text-xs font-semibold text-emerald-700 bg-emerald-50 hover:bg-emerald-100"
                              >
                                Verify
                              </button>
                            )}
                            <button
                              onClick={() => handleOpenEdit(m)}
                              className="p-1 rounded text-slate-500 hover:text-slate-800 hover:bg-slate-100"
                            >
                              <Edit className="w-3.5 h-3.5" />
                            </button>
                            {m.archived_at ? (
                              <button
                                onClick={() => handleRestoreRecord(m)}
                                className="px-2 py-1 rounded text-[11px] font-semibold bg-slate-200 text-slate-800"
                              >
                                Restore
                              </button>
                            ) : (
                              <button
                                onClick={() => handleOpenArchive(m)}
                                className="p-1 rounded text-slate-400 hover:text-rose-600 hover:bg-rose-50"
                              >
                                <Archive className="w-3.5 h-3.5" />
                              </button>
                            )}
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Profile Details Modal / Slide-Over */}
      {isDetailOpen && selectedMember && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-xs">
          <div className="bg-white rounded-2xl border border-[#E2E7EE] shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
            {/* Modal Header */}
            <div className="p-6 border-b border-[#E2E7EE] flex items-start justify-between gap-4 sticky top-0 bg-white z-10">
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-[#EEF2F6] text-[#17324D]">
                    {selectedMember.department}
                  </span>
                  {selectedMember.is_verified ? (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-50 text-emerald-800 border border-emerald-200">
                      <ShieldCheck className="w-3 h-3 text-emerald-600" />
                      Verified
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-amber-50 text-amber-800 border border-amber-200">
                      <Clock className="w-3 h-3 text-amber-600" />
                      Pending Verification
                    </span>
                  )}
                </div>
                <h2 className="text-xl font-bold text-[#17324D] tracking-tight">{selectedMember.full_name}</h2>
                <p className="text-sm font-semibold text-[#2E6B9E]">
                  {selectedMember.designation || <span className="text-slate-400 italic">Formal Designation Unverified</span>}
                </p>
              </div>
              <button
                onClick={() => setIsDetailOpen(false)}
                className="p-2 rounded-xl text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-6 space-y-6">
              {/* Duplicate Flag Callout if active */}
              {selectedMember.duplicate_flag && (
                <div className="p-4 rounded-xl bg-amber-50 border border-amber-200 text-xs text-amber-900 space-y-1">
                  <div className="flex items-center gap-2 font-bold">
                    <AlertTriangle className="w-4 h-4 text-amber-700 shrink-0" />
                    Potential Duplicate Record Flag
                  </div>
                  <p>{selectedMember.duplicate_notes || "Flagged for manual review with another faculty record."}</p>
                </div>
              )}

              {/* Information Grid */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="p-3.5 rounded-xl bg-[#F8FAFC] border border-[#E2E7EE] space-y-1">
                  <span className="text-[11px] font-bold text-[#697586] uppercase tracking-wider">Institution</span>
                  <p className="text-xs font-semibold text-[#17324D]">{selectedMember.institution}</p>
                </div>

                <div className="p-3.5 rounded-xl bg-[#F8FAFC] border border-[#E2E7EE] space-y-1">
                  <span className="text-[11px] font-bold text-[#697586] uppercase tracking-wider">Department</span>
                  <p className="text-xs font-semibold text-[#17324D]">{selectedMember.department}</p>
                </div>

                <div className="p-3.5 rounded-xl bg-[#F8FAFC] border border-[#E2E7EE] space-y-1">
                  <span className="text-[11px] font-bold text-[#697586] uppercase tracking-wider">Faculty ID</span>
                  <p className="text-xs font-semibold text-[#17324D]">
                    {selectedMember.faculty_id || <span className="text-slate-400 italic">Not Assigned</span>}
                  </p>
                </div>

                <div className="p-3.5 rounded-xl bg-[#F8FAFC] border border-[#E2E7EE] space-y-1">
                  <span className="text-[11px] font-bold text-[#697586] uppercase tracking-wider">Official Email</span>
                  <p className="text-xs font-semibold text-[#17324D]">
                    {selectedMember.official_email || <span className="text-slate-400 italic">Not Provided</span>}
                  </p>
                </div>

                <div className="p-3.5 rounded-xl bg-[#F8FAFC] border border-[#E2E7EE] space-y-1">
                  <span className="text-[11px] font-bold text-[#697586] uppercase tracking-wider">Office Location</span>
                  <p className="text-xs font-semibold text-[#17324D]">
                    {selectedMember.office_location || <span className="text-slate-400 italic">Not Specified</span>}
                  </p>
                </div>

                <div className="p-3.5 rounded-xl bg-[#F8FAFC] border border-[#E2E7EE] space-y-1">
                  <span className="text-[11px] font-bold text-[#697586] uppercase tracking-wider">Profile Status</span>
                  <p className="text-xs font-semibold text-[#17324D]">{selectedMember.profile_status}</p>
                </div>
              </div>

              {/* Specialisation */}
              <div className="space-y-1.5">
                <h4 className="text-xs font-bold text-[#17324D] uppercase tracking-wider">Specialisation / Research</h4>
                <div className="p-3.5 rounded-xl bg-[#F8FAFC] border border-[#E2E7EE] text-xs text-[#4B5565]">
                  {selectedMember.specialisation || (
                    <span className="text-slate-400 italic">Specialisation not recorded.</span>
                  )}
                </div>
              </div>

              {/* Subjects Taught */}
              <div className="space-y-1.5">
                <h4 className="text-xs font-bold text-[#17324D] uppercase tracking-wider">Subjects Taught</h4>
                {selectedMember.subjects_taught && selectedMember.subjects_taught.length > 0 ? (
                  <div className="flex flex-wrap gap-2">
                    {selectedMember.subjects_taught.map((subj, idx) => (
                      <span
                        key={idx}
                        className="px-2.5 py-1 rounded-lg text-xs font-medium bg-[#EEF2F6] text-[#17324D] border border-[#D0D7E2]"
                      >
                        {subj}
                      </span>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-slate-400 italic">No course subjects assigned to this profile.</p>
                )}
              </div>

              {/* Source & Verification History Audit */}
              <div className="p-4 rounded-xl bg-[#F8FAFC] border border-[#E2E7EE] space-y-3">
                <h4 className="text-xs font-bold text-[#17324D] uppercase tracking-wider flex items-center gap-1.5">
                  <ShieldCheck className="w-4 h-4 text-[#2E6B9E]" />
                  Source & Verification Audit Ledger
                </h4>

                <div className="space-y-2 text-xs">
                  <div>
                    <span className="font-semibold text-[#4B5565]">Public / Citation Source Notes: </span>
                    <span className="text-[#697586]">
                      {selectedMember.source_notes || "No source notes available."}
                    </span>
                  </div>

                  {selectedMember.is_verified && (
                    <div className="pt-2 border-t border-[#E2E7EE] space-y-1">
                      <div className="text-emerald-800 font-semibold flex items-center gap-1">
                        <Check className="w-3.5 h-3.5" /> Certified Verification Details
                      </div>
                      <p className="text-slate-600">{selectedMember.verification_notes}</p>
                      {selectedMember.verified_at && (
                        <p className="text-[11px] text-slate-400">
                          Timestamp: {new Date(selectedMember.verified_at).toLocaleString()}
                        </p>
                      )}
                    </div>
                  )}
                </div>
              </div>

              {/* Missing Fields Summary */}
              {selectedMember.missing_fields && selectedMember.missing_fields.length > 0 && (
                <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-2">
                  <span className="text-xs font-bold text-slate-700">Missing Information Fields (Unverified)</span>
                  <div className="flex flex-wrap gap-1.5">
                    {selectedMember.missing_fields.map((f, idx) => (
                      <span
                        key={idx}
                        className="px-2 py-0.5 rounded text-[11px] font-medium bg-white text-slate-600 border border-slate-300"
                      >
                        {f}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Modal Footer */}
            <div className="p-6 border-t border-[#E2E7EE] bg-white flex items-center justify-between gap-3">
              <button
                onClick={() => setIsDetailOpen(false)}
                className="px-4 py-2 rounded-xl text-xs font-semibold text-[#697586] hover:bg-slate-100 transition"
              >
                Close
              </button>

              {isAdmin && (
                <div className="flex items-center gap-2">
                  {!selectedMember.is_verified && !selectedMember.archived_at && (
                    <button
                      onClick={() => handleOpenVerify(selectedMember)}
                      className="px-4 py-2 rounded-xl text-xs font-semibold bg-emerald-600 text-white hover:bg-emerald-700 transition"
                    >
                      Verify Profile
                    </button>
                  )}

                  <button
                    onClick={() => {
                      setIsDetailOpen(false);
                      handleOpenEdit(selectedMember);
                    }}
                    className="px-4 py-2 rounded-xl text-xs font-semibold bg-[#17324D] text-white hover:bg-[#1E4265] transition"
                  >
                    Edit Profile
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Add / Edit Faculty Member Modal */}
      {isAddEditOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-xs">
          <div className="bg-white rounded-2xl border border-[#E2E7EE] shadow-xl max-w-xl w-full max-h-[90vh] overflow-y-auto">
            <div className="p-6 border-b border-[#E2E7EE] flex items-center justify-between">
              <h3 className="text-lg font-bold text-[#17324D]">
                {editingMember ? `Edit Faculty Record — ${editingMember.full_name}` : "Add New Faculty Member"}
              </h3>
              <button onClick={() => setIsAddEditOpen(false)} className="text-slate-400 hover:text-slate-600">
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleSaveMember} className="p-6 space-y-4">
              {formError && (
                <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 text-xs text-rose-800">
                  {formError}
                </div>
              )}

              <div>
                <label className="block text-xs font-semibold text-[#17324D] mb-1">
                  Full Name <span className="text-rose-500">*</span> (Preserve exact academic spelling)
                </label>
                <input
                  type="text"
                  required
                  value={formFullName}
                  onChange={(e) => setFormFullName(e.target.value)}
                  placeholder="e.g. Dr. V. G. Jisha"
                  className="w-full px-3.5 py-2 text-xs rounded-xl border border-[#D0D7E2] bg-[#F8FAFC] focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#17324D]/20 focus:border-[#17324D]"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-[#17324D] mb-1">Formal Designation</label>
                <input
                  type="text"
                  value={formDesignation}
                  onChange={(e) => setFormDesignation(e.target.value)}
                  placeholder="e.g. Head, Department of Professional Management Studies"
                  className="w-full px-3.5 py-2 text-xs rounded-xl border border-[#D0D7E2] bg-[#F8FAFC] focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#17324D]/20 focus:border-[#17324D]"
                />
                <span className="text-[11px] text-[#697586]">Leave empty if unverified.</span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-[#17324D] mb-1">Faculty ID</label>
                  <input
                    type="text"
                    value={formFacultyId}
                    onChange={(e) => setFormFacultyId(e.target.value)}
                    placeholder="e.g. KJU-DPMS-042"
                    className="w-full px-3.5 py-2 text-xs rounded-xl border border-[#D0D7E2] bg-[#F8FAFC] focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#17324D]/20 focus:border-[#17324D]"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-[#17324D] mb-1">Official University Email</label>
                  <input
                    type="email"
                    value={formOfficialEmail}
                    onChange={(e) => setFormOfficialEmail(e.target.value)}
                    placeholder="name@kristujayanti.com"
                    className="w-full px-3.5 py-2 text-xs rounded-xl border border-[#D0D7E2] bg-[#F8FAFC] focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#17324D]/20 focus:border-[#17324D]"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-[#17324D] mb-1">
                  Subjects Taught (comma-separated)
                </label>
                <input
                  type="text"
                  value={formSubjectsTaught}
                  onChange={(e) => setFormSubjectsTaught(e.target.value)}
                  placeholder="e.g. Financial Management, Research Methodology"
                  className="w-full px-3.5 py-2 text-xs rounded-xl border border-[#D0D7E2] bg-[#F8FAFC] focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#17324D]/20 focus:border-[#17324D]"
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-[#17324D] mb-1">Specialisation / Research</label>
                  <input
                    type="text"
                    value={formSpecialisation}
                    onChange={(e) => setFormSpecialisation(e.target.value)}
                    placeholder="e.g. Strategic Management"
                    className="w-full px-3.5 py-2 text-xs rounded-xl border border-[#D0D7E2] bg-[#F8FAFC] focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#17324D]/20 focus:border-[#17324D]"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-[#17324D] mb-1">Office Location</label>
                  <input
                    type="text"
                    value={formOfficeLocation}
                    onChange={(e) => setFormOfficeLocation(e.target.value)}
                    placeholder="e.g. Main Block, Room 304"
                    className="w-full px-3.5 py-2 text-xs rounded-xl border border-[#D0D7E2] bg-[#F8FAFC] focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#17324D]/20 focus:border-[#17324D]"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-[#17324D] mb-1">Profile Status</label>
                <select
                  value={formProfileStatus}
                  onChange={(e: any) => setFormProfileStatus(e.target.value)}
                  className="w-full px-3.5 py-2 text-xs rounded-xl border border-[#D0D7E2] bg-[#F8FAFC] focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#17324D]/20 focus:border-[#17324D]"
                >
                  <option value="PENDING_VERIFICATION">Pending Verification</option>
                  <option value="ACTIVE">Active</option>
                  <option value="INACTIVE">Inactive</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-[#17324D] mb-1">Source / Citation Notes</label>
                <textarea
                  rows={2}
                  value={formSourceNotes}
                  onChange={(e) => setFormSourceNotes(e.target.value)}
                  placeholder="Record source documents, annual reports, or citation references..."
                  className="w-full px-3.5 py-2 text-xs rounded-xl border border-[#D0D7E2] bg-[#F8FAFC] focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#17324D]/20 focus:border-[#17324D]"
                />
              </div>

              <div className="pt-4 border-t border-[#E2E7EE] flex items-center justify-end gap-3">
                <button
                  type="button"
                  onClick={() => setIsAddEditOpen(false)}
                  className="px-4 py-2 rounded-xl text-xs font-semibold text-[#697586] hover:bg-slate-100"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submittingForm}
                  className="px-4 py-2 rounded-xl text-xs font-semibold bg-[#17324D] text-white hover:bg-[#1E4265] disabled:opacity-50"
                >
                  {submittingForm ? "Saving..." : editingMember ? "Save Changes" : "Create Record"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Formal Verification Modal */}
      {isVerifyOpen && memberToVerify && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-xs">
          <div className="bg-white rounded-2xl border border-[#E2E7EE] shadow-xl max-w-lg w-full p-6 space-y-5">
            <div className="flex items-center justify-between border-b border-[#E2E7EE] pb-4">
              <div className="flex items-center gap-2 text-[#17324D]">
                <ShieldCheck className="w-5 h-5 text-emerald-600" />
                <h3 className="text-base font-bold">Certify Faculty Profile Verification</h3>
              </div>
              <button onClick={() => setIsVerifyOpen(false)} className="text-slate-400 hover:text-slate-600">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-3">
              <p className="text-xs text-[#4B5565]">
                You are certifying verified status for <strong className="text-[#17324D]">{memberToVerify.full_name}</strong>.
                This action is audited and permanently attributed to your administrator account.
              </p>

              {verifyError && (
                <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 text-xs text-rose-800">
                  {verifyError}
                </div>
              )}

              <div>
                <label className="block text-xs font-semibold text-[#17324D] mb-1">
                  Confirmed Formal Academic Designation
                </label>
                <input
                  type="text"
                  value={verifyDesignation}
                  onChange={(e) => setVerifyDesignation(e.target.value)}
                  placeholder="e.g. Associate Professor"
                  className="w-full px-3.5 py-2 text-xs rounded-xl border border-[#D0D7E2] bg-[#F8FAFC] focus:bg-white focus:outline-none focus:ring-1 focus:ring-[#17324D]"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-[#17324D] mb-1">
                  Administrative Audit Statement <span className="text-rose-500">*</span>
                </label>
                <textarea
                  rows={3}
                  required
                  value={verifyNotes}
                  onChange={(e) => setVerifyNotes(e.target.value)}
                  placeholder="Explain the official university document, FDP register, or HR record verified..."
                  className="w-full px-3.5 py-2 text-xs rounded-xl border border-[#D0D7E2] bg-[#F8FAFC] focus:bg-white focus:outline-none focus:ring-1 focus:ring-[#17324D]"
                />
              </div>

              <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200">
                <label className="flex items-start gap-2.5 cursor-pointer text-xs text-[#17324D]">
                  <input
                    type="checkbox"
                    checked={verifyAcknowledged}
                    onChange={(e) => setVerifyAcknowledged(e.target.checked)}
                    className="mt-0.5 rounded border-[#D0D7E2] text-[#17324D] focus:ring-0"
                  />
                  <span className="font-medium">
                    I attest that I have verified this faculty member&apos;s information against official Kristu Jayanti
                    University documentation and acknowledge administrative responsibility for this certification.
                  </span>

                </label>
              </div>
            </div>

            <div className="flex items-center justify-end gap-3 pt-4 border-t border-[#E2E7EE]">
              <button
                onClick={() => setIsVerifyOpen(false)}
                className="px-4 py-2 rounded-xl text-xs font-semibold text-[#697586] hover:bg-slate-100"
              >
                Cancel
              </button>
              <button
                onClick={handleCommitVerify}
                disabled={verifySubmitting || !verifyAcknowledged}
                className="px-4 py-2 rounded-xl text-xs font-semibold bg-emerald-600 text-white hover:bg-emerald-700 disabled:opacity-50 transition"
              >
                {verifySubmitting ? "Certifying..." : "Confirm & Mark Verified"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Confirmation Archive Modal */}
      {isArchiveOpen && memberToArchive && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-xs">
          <div className="bg-white rounded-2xl border border-[#E2E7EE] shadow-xl max-w-md w-full p-6 space-y-4">
            <div className="flex items-center gap-3 text-rose-600">
              <Archive className="w-5 h-5 shrink-0" />
              <h3 className="text-base font-bold text-[#17324D]">Archive Faculty Record</h3>
            </div>

            <p className="text-xs text-[#4B5565]">
              Are you sure you want to archive the record for <strong className="text-[#17324D]">{memberToArchive.full_name}</strong>?
              This record will be soft-archived rather than permanently deleted, preserving all historical citations.
            </p>

            <div>
              <label className="block text-xs font-semibold text-[#17324D] mb-1">Reason for Archiving (optional)</label>
              <input
                type="text"
                value={archiveReason}
                onChange={(e) => setArchiveReason(e.target.value)}
                placeholder="e.g. Department transfer, sabbatical, historical list"
                className="w-full px-3.5 py-2 text-xs rounded-xl border border-[#D0D7E2] bg-[#F8FAFC] focus:bg-white focus:outline-none focus:ring-1 focus:ring-[#17324D]"
              />
            </div>

            <div className="p-3 rounded-xl bg-slate-50 border border-slate-200">
              <label className="flex items-center gap-2 cursor-pointer text-xs font-medium text-[#17324D]">
                <input
                  type="checkbox"
                  checked={archiveConfirmed}
                  onChange={(e) => setArchiveConfirmed(e.target.checked)}
                  className="rounded border-[#D0D7E2] text-rose-600 focus:ring-0"
                />
                <span>Confirm archiving of this faculty profile</span>
              </label>
            </div>

            <div className="flex items-center justify-end gap-3 pt-3 border-t border-[#E2E7EE]">
              <button
                onClick={() => setIsArchiveOpen(false)}
                className="px-4 py-2 rounded-xl text-xs font-semibold text-[#697586] hover:bg-slate-100"
              >
                Cancel
              </button>
              <button
                onClick={handleCommitArchive}
                disabled={archiveSubmitting || !archiveConfirmed}
                className="px-4 py-2 rounded-xl text-xs font-semibold bg-rose-600 text-white hover:bg-rose-700 disabled:opacity-50 transition"
              >
                {archiveSubmitting ? "Archiving..." : "Archive Record"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* CSV Import & Preview Modal */}
      {isCSVModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-xs">
          <div className="bg-white rounded-2xl border border-[#E2E7EE] shadow-2xl max-w-4xl w-full max-h-[92vh] flex flex-col overflow-hidden">
            {/* Modal Header */}
            <div className="p-6 border-b border-[#E2E7EE] flex items-center justify-between shrink-0">
              <div className="space-y-1">
                <div className="flex items-center gap-2 text-[#17324D]">
                  <FileSpreadsheet className="w-5 h-5 text-[#2E6B9E]" />
                  <h3 className="text-lg font-bold">CSV Import & Preview</h3>
                </div>
                <p className="text-xs text-[#697586]">
                  Supports <code className="font-semibold text-[#17324D]">KJU_DPMS_Faculty_and_Designations.csv</code>.
                  Detects column mapping, reports potential duplicates, and prevents unintentional overwrites.
                </p>
              </div>
              <button onClick={() => setIsCSVModalOpen(false)} className="text-slate-400 hover:text-slate-600">
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Modal Content */}
            <div className="p-6 space-y-6 overflow-y-auto flex-1">
              {csvError && (
                <div className="p-3.5 rounded-xl bg-rose-50 border border-rose-200 text-xs text-rose-800 flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
                  <span>{csvError}</span>
                </div>
              )}

              {/* Upload or Load Bundled File Controls */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="p-4 rounded-xl border-2 border-dashed border-[#D0D7E2] bg-[#F8FAFC] text-center space-y-2">
                  <Upload className="w-6 h-6 text-[#2E6B9E] mx-auto" />
                  <div className="text-xs font-semibold text-[#17324D]">Upload CSV File</div>
                  <input
                    type="file"
                    accept=".csv"
                    onChange={(e) => {
                      const file = e.target.files?.[0] || null;
                      setCsvFile(file);
                      if (file) handlePreviewCSVFile(file);
                    }}
                    className="text-xs text-[#697586] file:mr-2 file:py-1 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-[#17324D] file:text-white hover:file:bg-[#1E4265]"
                  />
                </div>

                <div className="p-4 rounded-xl border border-[#D0D7E2] bg-[#EEF2F6]/60 flex flex-col justify-between space-y-3">
                  <div>
                    <span className="text-xs font-bold text-[#17324D] block">Pre-loaded Dataset</span>
                    <p className="text-[11px] text-[#697586] mt-1">
                      Instantly preview the bundled <span className="font-semibold">KJU_DPMS_Faculty_and_Designations.csv</span> (26 DPMS records).
                    </p>
                  </div>
                  <button
                    onClick={handleLoadBundledCSV}
                    disabled={csvPreviewLoading}
                    className="w-full py-2 px-3 rounded-xl bg-white border border-[#D0D7E2] text-[#17324D] hover:bg-white/80 text-xs font-semibold shadow-xs transition"
                  >
                    {csvPreviewLoading ? "Loading Preview..." : "Load Bundled 26 Faculty CSV"}
                  </button>
                </div>
              </div>

              {/* CSV Preview Results Table */}
              {csvPreviewData && (
                <div className="space-y-4">
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                    <div className="p-3 rounded-xl bg-[#F8FAFC] border border-[#E2E7EE] text-center">
                      <span className="text-[11px] font-bold text-[#697586] uppercase">Total Rows</span>
                      <p className="text-lg font-bold text-[#17324D]">{csvPreviewData.total_rows}</p>
                    </div>
                    <div className="p-3 rounded-xl bg-emerald-50 border border-emerald-200 text-center">
                      <span className="text-[11px] font-bold text-emerald-700 uppercase">Valid Rows</span>
                      <p className="text-lg font-bold text-emerald-900">{csvPreviewData.valid_rows_count}</p>
                    </div>
                    <div className="p-3 rounded-xl bg-amber-50 border border-amber-200 text-center">
                      <span className="text-[11px] font-bold text-amber-700 uppercase">Potential Duplicates</span>
                      <p className="text-lg font-bold text-amber-900">{csvPreviewData.potential_duplicates_count}</p>
                    </div>
                    <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-center">
                      <span className="text-[11px] font-bold text-rose-700 uppercase">Invalid Rows</span>
                      <p className="text-lg font-bold text-rose-900">{csvPreviewData.invalid_rows_count}</p>
                    </div>
                  </div>

                  {/* Unrecognized Headers Report */}
                  {csvPreviewData.unrecognized_headers && csvPreviewData.unrecognized_headers.length > 0 && (
                    <div className="p-3 rounded-xl bg-blue-50 border border-blue-200 text-xs text-blue-900">
                      <span className="font-semibold">Unmapped / Additional Columns Detected: </span>
                      {csvPreviewData.unrecognized_headers.join(", ")}
                    </div>
                  )}

                  {/* Rows Table Preview */}
                  <div className="border border-[#E2E7EE] rounded-xl overflow-hidden max-h-64 overflow-y-auto">
                    <table className="w-full text-left text-xs border-collapse">
                      <thead className="bg-[#F8FAFC] border-b border-[#E2E7EE] text-[#4B5565] sticky top-0">
                        <tr>
                          <th className="py-2 px-3">#</th>
                          <th className="py-2 px-3">Faculty Member</th>
                          <th className="py-2 px-3">Mapped Designation</th>
                          <th className="py-2 px-3">Source Note</th>
                          <th className="py-2 px-3">Audit / Duplicate Warning</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[#F0F3F7]">
                        {csvPreviewData.rows.map((row) => (
                          <tr
                            key={row.row_number}
                            className={row.is_potential_duplicate ? "bg-amber-50/60" : !row.is_valid ? "bg-rose-50/60" : ""}
                          >
                            <td className="py-2 px-3 text-slate-400 font-mono">{row.row_number}</td>
                            <td className="py-2 px-3 font-semibold text-[#17324D]">{row.full_name}</td>
                            <td className="py-2 px-3 text-[#2E6B9E]">
                              {row.mapped_designation || <span className="text-slate-400 italic">Unverified</span>}
                            </td>
                            <td className="py-2 px-3 text-[#697586] max-w-xs truncate" title={row.source_notes || ""}>
                              {row.source_notes || "—"}
                            </td>
                            <td className="py-2 px-3">
                              {row.is_potential_duplicate ? (
                                <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-100 text-amber-900 border border-amber-300">
                                  {row.potential_duplicate_reason || "Potential Duplicate"}
                                </span>
                              ) : (
                                <span className="text-emerald-700 font-medium">Valid</span>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>

                  {/* Commitment Settings */}
                  <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-3">
                    <label className="flex items-start gap-2.5 cursor-pointer text-xs font-medium text-[#17324D]">
                      <input
                        type="checkbox"
                        checked={csvCommitConfirmed}
                        onChange={(e) => setCsvCommitConfirmed(e.target.checked)}
                        className="mt-0.5 rounded border-[#D0D7E2] text-[#17324D] focus:ring-0"
                      />
                      <span>
                        I confirm review of this CSV preview and authorize commit to the Kristu Jayanti University
                        database. (Idempotent: will not create unintended duplicates).
                      </span>
                    </label>

                    <label className="flex items-center gap-2 cursor-pointer text-xs text-[#697586]">
                      <input
                        type="checkbox"
                        checked={csvOverwriteVerified}
                        onChange={(e) => setCsvOverwriteVerified(e.target.checked)}
                        className="rounded border-[#D0D7E2] text-rose-600 focus:ring-0"
                      />
                      <span>Overwrite verified records (leave unchecked to protect certified administrative data)</span>
                    </label>
                  </div>
                </div>
              )}

              {/* Final Commit Summary Report if completed */}
              {csvResultSummary && (
                <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-xs text-emerald-900 space-y-2">
                  <h4 className="font-bold flex items-center gap-1.5 text-sm">
                    <CheckCircle className="w-4 h-4 text-emerald-600" /> Import Successfully Executed
                  </h4>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-center py-2">
                    <div className="p-2 rounded bg-white border border-emerald-200">
                      <span className="text-[10px] uppercase font-bold text-slate-500">Created</span>
                      <p className="font-bold text-emerald-700">{csvResultSummary.created_count}</p>
                    </div>
                    <div className="p-2 rounded bg-white border border-emerald-200">
                      <span className="text-[10px] uppercase font-bold text-slate-500">Updated</span>
                      <p className="font-bold text-blue-700">{csvResultSummary.updated_count}</p>
                    </div>
                    <div className="p-2 rounded bg-white border border-emerald-200">
                      <span className="text-[10px] uppercase font-bold text-slate-500">Skipped</span>
                      <p className="font-bold text-amber-700">{csvResultSummary.skipped_count}</p>
                    </div>
                    <div className="p-2 rounded bg-white border border-emerald-200">
                      <span className="text-[10px] uppercase font-bold text-slate-500">Rejected</span>
                      <p className="font-bold text-rose-700">{csvResultSummary.rejected_count}</p>
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Modal Footer */}
            <div className="p-6 border-t border-[#E2E7EE] bg-white flex items-center justify-between shrink-0">
              <button
                onClick={() => setIsCSVModalOpen(false)}
                className="px-4 py-2 rounded-xl text-xs font-semibold text-[#697586] hover:bg-slate-100"
              >
                Close
              </button>

              {csvPreviewData && !csvResultSummary && (
                <button
                  onClick={handleCommitCSVImport}
                  disabled={csvCommitLoading || !csvCommitConfirmed}
                  className="px-5 py-2.5 rounded-xl text-xs font-semibold bg-[#17324D] text-white hover:bg-[#1E4265] disabled:opacity-50 transition"
                >
                  {csvCommitLoading ? "Committing Import..." : "Commit CSV Import"}
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
