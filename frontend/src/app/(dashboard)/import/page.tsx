"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useAuth } from "@/context/AuthContext";
import { apiRequest } from "@/lib/api";
import {
  AlertCircle,
  AlertTriangle,
  ArrowRight,
  BookOpen,
  Calendar,
  CheckCircle,
  DoorOpen,
  Download,
  FileSpreadsheet,
  HelpCircle,
  Layers,
  ShieldAlert,
  Sparkles,
  UploadCloud,
  Users,
  XCircle,
} from "lucide-react";

type EntityType = "teachers" | "rooms" | "subjects" | "requirements";

interface RowError {
  row_number: number;
  field: string;
  error_message: string;
  value?: any;
}

interface ImportPreviewResponse {
  entity_type: EntityType;
  total_rows: number;
  valid_rows: number;
  invalid_rows: number;
  is_committable: boolean;
  errors: RowError[];
  preview_records: Array<Record<string, any>>;
}

const ENTITY_CONFIGS: Record<
  EntityType,
  { title: string; desc: string; icon: any; requiredCols: string[] }
> = {
  teachers: {
    title: "Faculty Teachers",
    desc: "Employee codes, faculty names, email addresses, and max daily workload limits.",
    icon: Users,
    requiredCols: ["employee_code", "email", "full_name", "department_code", "max_hours_per_day", "max_weekly_hours"],
  },
  subjects: {
    title: "Curriculum Subjects",
    desc: "Course codes, subject names, credit hours, subject type (THEORY/LAB), and room requirements.",
    icon: BookOpen,
    requiredCols: ["code", "name", "credits", "subject_type", "required_room_type", "department_code"],
  },
  rooms: {
    title: "Classrooms & Labs",
    desc: "Building names, room numbers, seating capacity, and room types (LECTURE_HALL/COMPUTER_LAB).",
    icon: DoorOpen,
    requiredCols: ["building", "room_number", "capacity", "room_type"],
  },
  requirements: {
    title: "Teaching Requirements",
    desc: "Mapping of student section to subject, assigned teacher code, and weekly session hours.",
    icon: Calendar,
    requiredCols: ["section_name", "subject_code", "employee_code", "required_sessions_per_week"],
  },
};

export default function ImportDataPage() {
  const { user, token } = useAuth();
  const [entityType, setEntityType] = useState<EntityType>("teachers");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<ImportPreviewResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [committing, setCommitting] = useState(false);
  const [message, setMessage] = useState<{ text: string; type: "success" | "error" | "info" } | null>(null);

  const handleDownloadTemplate = (format: "csv" | "xlsx") => {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
    const url = `${apiUrl}/import/templates/${entityType}?file_format=${format}`;

    fetch(url, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((res) => res.blob())
      .then((blob) => {
        const blobUrl = window.URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = blobUrl;
        a.download = `${entityType}_template.${format}`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        setMessage({
          text: `Sample ${format.toUpperCase()} template downloaded. Open in Excel, fill in your data, and upload below.`,
          type: "info",
        });
      })
      .catch(() => setMessage({ text: "Failed to download template.", type: "error" }));
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setSelectedFile(e.target.files[0]);
      setPreview(null);
      setMessage(null);
    }
  };

  const handlePreviewUpload = async () => {
    if (!selectedFile) {
      setMessage({ text: "Please select a CSV or Excel file to upload.", type: "info" });
      return;
    }
    setLoading(true);
    setMessage(null);

    const formData = new FormData();
    formData.append("file", selectedFile);

    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
      const res = await fetch(`${apiUrl}/import/preview?entity_type=${entityType}`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
        },
        body: formData,
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || "Validation analysis failed.");
      }

      const data: ImportPreviewResponse = await res.json();
      setPreview(data);

      if (data.is_committable) {
        setMessage({
          text: `Preflight analysis passed! All ${data.valid_rows} rows are valid and ready to import.`,
          type: "success",
        });
      } else {
        setMessage({
          text: `Found ${data.invalid_rows} invalid row(s). Review the diagnostic errors below before importing.`,
          type: "error",
        });
      }
    } catch (err: any) {
      setMessage({ text: err.message || "Failed to process import preview.", type: "error" });
    } finally {
      setLoading(false);
    }
  };

  const handleCommit = async () => {
    if (!preview || !preview.is_committable) return;
    setCommitting(true);
    setMessage(null);

    try {
      const res: any = await apiRequest("/import/commit", {
        method: "POST",
        body: JSON.stringify({
          entity_type: entityType,
          records: preview.preview_records,
        }),
      });

      setMessage({ text: res.message || "Successfully imported records into database!", type: "success" });
      setPreview(null);
      setSelectedFile(null);
    } catch (err: any) {
      setMessage({ text: err.detail || "Import commit failed.", type: "error" });
    } finally {
      setCommitting(false);
    }
  };

  const currentConfig = ENTITY_CONFIGS[entityType];

  if (user && !["ADMIN", "HOD", "COORDINATOR"].includes(user.role)) {
    return (
      <div className="bg-white rounded-xl border border-[#E2E7EE] p-8 text-center max-w-lg mx-auto my-12 shadow-xs">
        <ShieldAlert className="w-12 h-12 text-[#B42332] mx-auto mb-3" />
        <h2 className="text-lg font-bold text-[#17324D]">Access Restricted</h2>
        <p className="text-xs text-[#697586] mt-1.5 leading-relaxed">
          The Spreadsheet Importer is reserved for Department Heads and Administrative Coordinators.
          Your current role ({user.role}) does not have permission to upload master institution records.
        </p>
        <div className="mt-5 flex items-center justify-center space-x-3">
          <Link
            href="/timetables"
            className="px-4 py-2 bg-[#1261A0] text-white text-xs font-semibold rounded-lg hover:bg-[#0E4E82] transition-colors"
          >
            Go to Timetable
          </Link>
          <Link
            href="/guide"
            className="px-4 py-2 border border-[#E2E7EE] text-slate-700 text-xs font-semibold rounded-lg hover:bg-slate-50 transition-colors"
          >
            Open Guide
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto space-y-6 pb-12">
      {/* Page Header answering: Where am I? What can I do here? What should I do next? */}
      <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2 text-xs text-blue-700 font-semibold tracking-wide uppercase">
            <FileSpreadsheet className="w-4 h-4 text-blue-600" />
            <span>Excel & CSV Importer</span>
          </div>
          <h1 className="text-2xl font-bold text-slate-900 mt-1">Import College Scheduling Data</h1>
          <p className="text-sm text-slate-600 mt-1">
            Easily upload your existing college spreadsheets without manual data entry. Row-level error checks protect against mistakes.
          </p>
        </div>

        <div className="flex items-center space-x-3">
          <Link
            href="/setup"
            className="px-4 py-2 border border-slate-300 rounded-lg text-sm font-semibold text-slate-700 hover:bg-slate-50 transition-colors shadow-xs"
          >
            Semester Setup Wizard
          </Link>
          <Link
            href="/timetables"
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-semibold transition-colors shadow-xs"
          >
            Open Timetable Planner
          </Link>
        </div>
      </div>

      {/* Global Alert Notification */}
      {message && (
        <div
          className={`p-4 rounded-xl text-sm border flex items-center justify-between ${
            message.type === "success"
              ? "bg-emerald-50 text-emerald-900 border-emerald-200"
              : message.type === "error"
              ? "bg-rose-50 text-rose-900 border-rose-200"
              : "bg-blue-50 text-blue-900 border-blue-200"
          }`}
        >
          <div className="flex items-center space-x-2.5">
            {message.type === "success" ? (
              <CheckCircle className="w-5 h-5 text-emerald-600 flex-shrink-0" />
            ) : (
              <AlertCircle className="w-5 h-5 text-rose-600 flex-shrink-0" />
            )}
            <span>{message.text}</span>
          </div>
          <button onClick={() => setMessage(null)} className="text-xs font-semibold underline ml-4">
            Dismiss
          </button>
        </div>
      )}

      {/* Step 1: Select Data Category */}
      <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-xs space-y-4">
        <div>
          <span className="text-xs font-bold uppercase tracking-wider text-blue-700">Step 1</span>
          <h2 className="text-lg font-bold text-slate-900 mt-0.5">Select Data Category</h2>
          <p className="text-xs text-slate-500">Choose what type of scheduling data you are importing from your spreadsheet.</p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {(Object.keys(ENTITY_CONFIGS) as EntityType[]).map((key) => {
            const config = ENTITY_CONFIGS[key];
            const Icon = config.icon;
            const isSelected = entityType === key;

            return (
              <button
                key={key}
                type="button"
                onClick={() => {
                  setEntityType(key);
                  setPreview(null);
                  setSelectedFile(null);
                  setMessage(null);
                }}
                className={`text-left p-4 rounded-xl border transition-all ${
                  isSelected
                    ? "border-blue-600 bg-blue-50/70 shadow-xs"
                    : "border-slate-200 bg-white hover:bg-slate-50"
                }`}
              >
                <div
                  className={`w-9 h-9 rounded-lg flex items-center justify-center mb-3 ${
                    isSelected ? "bg-blue-600 text-white" : "bg-slate-100 text-slate-600"
                  }`}
                >
                  <Icon className="w-5 h-5" />
                </div>
                <div className="text-sm font-bold text-slate-900">{config.title}</div>
                <p className="text-xs text-slate-500 mt-1 line-clamp-2">{config.desc}</p>
              </button>
            );
          })}
        </div>
      </div>

      {/* Step 2: Download Template & Upload File */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Download Template Card */}
        <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-xs flex flex-col justify-between">
          <div>
            <span className="text-xs font-bold uppercase tracking-wider text-blue-700">Step 2A</span>
            <h3 className="text-base font-bold text-slate-900 mt-0.5">Download Sample Template</h3>
            <p className="text-xs text-slate-500 mt-1 leading-relaxed">
              Download a pre-formatted template with sample rows and the exact columns required for {currentConfig.title}.
            </p>

            <div className="mt-4 p-3 bg-slate-50 rounded-lg border border-slate-200">
              <span className="text-[11px] font-semibold text-slate-600 uppercase tracking-wider block mb-1.5">
                Expected Spreadsheet Columns:
              </span>
              <div className="flex flex-wrap gap-1.5">
                {currentConfig.requiredCols.map((col) => (
                  <span
                    key={col}
                    className="text-[11px] font-mono px-2 py-0.5 rounded bg-white border border-slate-300 text-slate-700"
                  >
                    {col}
                  </span>
                ))}
              </div>
            </div>
          </div>

          <div className="mt-6 flex items-center gap-2.5">
            <button
              onClick={() => handleDownloadTemplate("csv")}
              className="flex-1 flex items-center justify-center space-x-2 py-2.5 px-3 border border-slate-300 rounded-lg text-xs font-semibold text-slate-700 hover:bg-slate-50 transition-colors shadow-xs"
            >
              <Download className="w-3.5 h-3.5 text-slate-500" />
              <span>Download CSV Template</span>
            </button>
            <button
              onClick={() => handleDownloadTemplate("xlsx")}
              className="flex-1 flex items-center justify-center space-x-2 py-2.5 px-3 border border-emerald-300 bg-emerald-50 text-emerald-800 rounded-lg text-xs font-semibold hover:bg-emerald-100 transition-colors shadow-xs"
            >
              <Download className="w-3.5 h-3.5 text-emerald-700" />
              <span>Download Excel (.xlsx)</span>
            </button>
          </div>
        </div>

        {/* Upload File Card */}
        <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-xs flex flex-col justify-between">
          <div>
            <span className="text-xs font-bold uppercase tracking-wider text-blue-700">Step 2B</span>
            <h3 className="text-base font-bold text-slate-900 mt-0.5">Upload Spreadsheet</h3>
            <p className="text-xs text-slate-500 mt-1">
              Select your completed CSV or Excel (.xlsx) file to run validation analysis.
            </p>

            <div className="mt-4 border-2 border-dashed border-slate-300 hover:border-blue-400 rounded-xl p-6 text-center bg-slate-50/50 transition-colors cursor-pointer relative">
              <input
                type="file"
                accept=".csv, .xlsx, .xls"
                onChange={handleFileChange}
                className="absolute inset-0 opacity-0 cursor-pointer w-full h-full"
              />
              <UploadCloud className="w-8 h-8 text-blue-600 mx-auto mb-2" />
              <div className="text-xs font-bold text-slate-800">
                {selectedFile ? selectedFile.name : "Click to browse or drop file here"}
              </div>
              <p className="text-[11px] text-slate-500 mt-0.5">Supports standard CSV or Microsoft Excel (.xlsx)</p>
            </div>
          </div>

          <div className="mt-6 flex items-center justify-end">
            <button
              onClick={handlePreviewUpload}
              disabled={!selectedFile || loading}
              className="w-full py-2.5 px-4 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded-lg text-xs font-bold transition-colors shadow-xs flex items-center justify-center space-x-2"
            >
              <Sparkles className="w-4 h-4" />
              <span>{loading ? "Analyzing Spreadsheet..." : "Validate & Preview Records"}</span>
            </button>
          </div>
        </div>
      </div>

      {/* Step 3: Preflight Validation Report & Commit Card */}
      {preview && (
        <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-xs space-y-6">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-200">
            <div>
              <span className="text-xs font-bold uppercase tracking-wider text-blue-700">Step 3</span>
              <h2 className="text-lg font-bold text-slate-900 mt-0.5">Preflight Validation Analysis</h2>
              <p className="text-xs text-slate-500">
                Inspected {preview.total_rows} total rows for {currentConfig.title}.
              </p>
            </div>

            <div className="flex items-center space-x-3">
              <div className="flex items-center space-x-2 text-xs">
                <span className="px-3 py-1 rounded-full font-bold bg-emerald-100 text-emerald-800">
                  ✓ {preview.valid_rows} Valid Rows
                </span>
                {preview.invalid_rows > 0 && (
                  <span className="px-3 py-1 rounded-full font-bold bg-rose-100 text-rose-800">
                    ✕ {preview.invalid_rows} Invalid Rows
                  </span>
                )}
              </div>

              {preview.is_committable ? (
                <button
                  onClick={handleCommit}
                  disabled={committing}
                  className="px-5 py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-bold transition-colors shadow-xs flex items-center space-x-2 disabled:opacity-50"
                >
                  <CheckCircle className="w-4 h-4" />
                  <span>{committing ? "Importing Data..." : "Confirm & Commit Import"}</span>
                </button>
              ) : (
                <button
                  disabled
                  className="px-5 py-2.5 bg-slate-200 text-slate-400 rounded-lg text-xs font-bold cursor-not-allowed"
                >
                  Resolve Errors to Import
                </button>
              )}
            </div>
          </div>

          {/* Row-Level Diagnostics Error Table */}
          {preview.errors.length > 0 && (
            <div className="p-4 rounded-xl border border-rose-200 bg-rose-50/50 space-y-3">
              <div className="flex items-center space-x-2 text-rose-800 text-xs font-bold">
                <AlertTriangle className="w-4 h-4 flex-shrink-0" />
                <span>Issues Detected ({preview.errors.length} errors across rows)</span>
              </div>
              <div className="space-y-1.5 max-h-48 overflow-y-auto">
                {preview.errors.map((err, idx) => (
                  <div
                    key={idx}
                    className="text-xs p-2.5 rounded bg-white border border-rose-200 text-rose-900 flex items-start justify-between"
                  >
                    <div>
                      <span className="font-bold">Row {err.row_number}:</span> Column{" "}
                      <code className="font-mono bg-rose-100 px-1 rounded">{err.field}</code> — {err.error_message}
                    </div>
                    {err.value && (
                      <span className="text-[11px] text-slate-500 font-mono">Value: &quot;{String(err.value)}&quot;</span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Preview Records Table */}
          <div>
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700 mb-2">Record Preview</h3>
            <div className="border border-slate-200 rounded-lg overflow-x-auto max-h-72 overflow-y-auto">
              <table className="w-full text-left border-collapse text-xs">
                <thead className="bg-slate-50 sticky top-0 border-b border-slate-200">
                  <tr>
                    <th className="py-2.5 px-3 font-semibold text-slate-700">Row</th>
                    <th className="py-2.5 px-3 font-semibold text-slate-700">Status</th>
                    {currentConfig.requiredCols.map((col) => (
                      <th key={col} className="py-2.5 px-3 font-semibold text-slate-700">
                        {col}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200">
                  {preview.preview_records.map((rec, i) => (
                    <tr key={i} className={rec._is_valid ? "hover:bg-slate-50" : "bg-rose-50/40 hover:bg-rose-50/70"}>
                      <td className="py-2 px-3 font-mono text-slate-500">{rec._row_number || i + 2}</td>
                      <td className="py-2 px-3">
                        {rec._is_valid ? (
                          <span className="inline-flex items-center text-[10px] text-emerald-800 bg-emerald-100 px-2 py-0.5 rounded font-bold">
                            Valid
                          </span>
                        ) : (
                          <span className="inline-flex items-center text-[10px] text-rose-800 bg-rose-100 px-2 py-0.5 rounded font-bold">
                            Error
                          </span>
                        )}
                      </td>
                      {currentConfig.requiredCols.map((col) => (
                        <td key={col} className="py-2 px-3 text-slate-800 truncate max-w-xs">
                          {String(rec[col] ?? "")}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
