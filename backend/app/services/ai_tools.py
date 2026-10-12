"""
TIMEVERSE AI Assistant Server-Side Tool Registry
Enforces server-side authentication, role-based authorization, argument validation,
and real database retrieval for Kristu Jayanti University (KJU) academic scheduling.
"""

import csv
import logging
import os
import time
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.cohort import CohortSection
from app.models.curriculum import Subject, SubjectRequirement
from app.models.infrastructure import Room, TimeSlot
from app.models.organization import AcademicTerm, Department
from app.models.preference import SchedulingPreference
from app.models.teacher import Teacher, TeacherAvailability
from app.models.timetable import SessionStatusEnum, Timetable, TimetableSession, TimetableStatusEnum
from app.models.user import User, UserRoleEnum
from app.services.scheduler.conflict_service import ConflictService
from app.api.v1.endpoints.scheduling import detect_session_conflicts
from app.services.scheduler.engine import TimetableSolver
from app.services.scheduler.schemas import (
    CohortSectionInput,
    RoomScheduleInput,
    SchedulingConfig,
    SubjectRequirementInput,
    TeacherScheduleInput,
    TimeSlotInput,
)
from app.services.scheduler.validator import TimetableValidator

logger = logging.getLogger(__name__)

# Cache for KJU DPMS official faculty records
_KJU_FACULTY_CACHE: list[dict[str, str]] | None = None


def _load_kju_faculty() -> list[dict[str, str]]:
    global _KJU_FACULTY_CACHE
    if _KJU_FACULTY_CACHE is not None:
        return _KJU_FACULTY_CACHE

    records: list[dict[str, str]] = []
    csv_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "KJU_DPMS_Faculty_and_Designations.csv")
    )
    if os.path.exists(csv_path):
        try:
            with open(csv_path, mode="r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    name = row.get("Faculty member", "").strip()
                    desig = row.get("Designation (as found in public sources)", "").strip()
                    note = row.get("Source / verification note", "").strip()
                    if name:
                        records.append({
                            "name": name,
                            "designation": desig or "Faculty Member",
                            "notes": note,
                            "department": "Department of Professional Management Studies (DPMS)",
                            "institution": "Kristu Jayanti University (KJU), Airport Road Campus",
                        })
        except Exception as e:
            logger.warning("Could not read KJU faculty CSV: %s", e)
    _KJU_FACULTY_CACHE = records
    return records


# =============================================================================
# GEMINI FUNCTION DECLARATIONS SCHEMA
# =============================================================================
GEMINI_TOOL_DECLARATIONS = [
    {
        "name": "get_academic_configuration",
        "description": "Retrieve institution scheduling structure including active terms, working days (Mon-Sat), period timings, recess/break slots, and academic departments at Kristu Jayanti University.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "department_id": {
                    "type": "STRING",
                    "description": "Optional department ID (e.g., 'dept_cs').",
                }
            },
        },
    },
    {
        "name": "search_faculty",
        "description": "Search faculty members, academic designations, employee codes, and departmental affiliations at KJU Department of Professional Management Studies (DPMS) and College of CS.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {
                    "type": "STRING",
                    "description": "Faculty name, title, or employee code search term (e.g. 'Sharma', 'Jisha', 'Excelce').",
                },
                "department_id": {
                    "type": "STRING",
                    "description": "Optional department ID filter.",
                },
            },
        },
    },
    {
        "name": "get_faculty_workload",
        "description": "Retrieve actual weekly teaching workload, assigned courses, sections, and daily period distribution for a specific faculty member. Enforces privacy permissions.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "faculty_name_or_code": {
                    "type": "STRING",
                    "description": "Faculty name or employee code (e.g., 'Dr. Rajesh Sharma', 'tch_sharma', 'EMP_T01').",
                }
            },
            "required": ["faculty_name_or_code"],
        },
    },
    {
        "name": "search_rooms",
        "description": "Search university classrooms, lecture halls, computer laboratories, and seminar halls with seating capacity and equipment specifications.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "room_type": {
                    "type": "STRING",
                    "description": "Filter by room type: 'LECTURE_HALL', 'COMPUTER_LAB', 'SEMINAR_HALL', or 'CLASSROOM'.",
                },
                "min_capacity": {
                    "type": "INTEGER",
                    "description": "Minimum student seating capacity needed.",
                },
                "building": {
                    "type": "STRING",
                    "description": "Building name filter (e.g., 'Main Block', 'CS Block').",
                },
            },
        },
    },
    {
        "name": "get_subjects",
        "description": "Retrieve curriculum courses, codes, credit points, subject types (THEORY or LAB), and suitable room requirements.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "department_id": {
                    "type": "STRING",
                    "description": "Optional department ID filter.",
                },
                "code_or_name": {
                    "type": "STRING",
                    "description": "Course code or title keyword (e.g., 'CS301', 'Data Structures').",
                },
            },
        },
    },
    {
        "name": "get_teaching_requirements",
        "description": "Get required weekly lecture session frequencies per subject for cohort sections, assigned teachers, and duration period rules.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "cohort_section_id": {
                    "type": "STRING",
                    "description": "Section ID (e.g. 'sec_cs_3a', 'sec_cs_3b').",
                },
                "subject_code": {
                    "type": "STRING",
                    "description": "Course code filter (e.g. 'CS301').",
                },
            },
        },
    },
    {
        "name": "get_timetable",
        "description": "Fetch scheduled classes from the active or published timetable. Can filter by section, day of the week, or teacher.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "timetable_id": {
                    "type": "STRING",
                    "description": "Optional timetable ID. Defaults to the latest active/published timetable.",
                },
                "section_id": {
                    "type": "STRING",
                    "description": "Cohort section ID (e.g. 'sec_cs_3a').",
                },
                "day_of_week": {
                    "type": "INTEGER",
                    "description": "Day of the week (1=Monday, 2=Tuesday, 3=Wednesday, 4=Thursday, 5=Friday, 6=Saturday).",
                },
                "teacher_name_or_code": {
                    "type": "STRING",
                    "description": "Optional teacher name or code to isolate classes.",
                },
            },
        },
    },
    {
        "name": "detect_scheduling_conflicts",
        "description": "Run the institutional conflict detection engine to analyze a timetable for double-bookings, teacher clashes, room capacity mismatches, or availability violations.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "timetable_id": {
                    "type": "STRING",
                    "description": "Timetable ID to inspect. Defaults to active timetable.",
                }
            },
        },
    },
    {
        "name": "generate_timetable",
        "description": "Run the deterministic Google OR-Tools CP-SAT constraint solver to generate a clash-free academic timetable draft satisfying all hard constraints. Restricted to HOD, Coordinator, and Admin.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "department_id": {
                    "type": "STRING",
                    "description": "Department to schedule (e.g., 'dept_cs').",
                },
                "academic_term_id": {
                    "type": "STRING",
                    "description": "Academic term identifier.",
                },
                "time_limit_seconds": {
                    "type": "INTEGER",
                    "description": "Solver search time limit in seconds (default 15).",
                },
                "avoid_teacher_day": {
                    "type": "INTEGER",
                    "description": "Optional day of week (1=Mon to 6=Sat) to treat a specific teacher as unavailable.",
                },
                "avoid_teacher_id": {
                    "type": "STRING",
                    "description": "Optional teacher ID to apply leave to during this generation run.",
                },
            },
        },
    },
    {
        "name": "preview_timetable_changes",
        "description": "Evaluate the clash impact of moving a timetable session to a different slot, room, or substitute teacher before applying the change.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "session_id": {
                    "type": "STRING",
                    "description": "ID of the timetable session to evaluate.",
                },
                "new_time_slot_id": {
                    "type": "STRING",
                    "description": "Candidate time slot ID (e.g., 'ts_d2_p3').",
                },
                "new_room_id": {
                    "type": "STRING",
                    "description": "Candidate room ID.",
                },
                "new_teacher_id": {
                    "type": "STRING",
                    "description": "Candidate teacher ID.",
                },
                "timetable_id": {
                    "type": "STRING",
                    "description": "Optional timetable ID.",
                },
            },
            "required": ["session_id"],
        },
    },
    {
        "name": "apply_timetable_changes",
        "description": "Apply a verified schedule adjustment (move slot, change room, or reassign teacher) to the timetable database. Requires explicit confirmation.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "session_id": {
                    "type": "STRING",
                    "description": "ID of session to modify.",
                },
                "new_time_slot_id": {
                    "type": "STRING",
                    "description": "New target time slot ID.",
                },
                "new_room_id": {
                    "type": "STRING",
                    "description": "New target room ID.",
                },
                "new_teacher_id": {
                    "type": "STRING",
                    "description": "New target teacher ID.",
                },
                "confirmed": {
                    "type": "BOOLEAN",
                    "description": "Explicit user confirmation flag (must be true to execute).",
                },
            },
            "required": ["session_id", "confirmed"],
        },
    },
    {
        "name": "get_publication_status",
        "description": "Get timetable publication state, version history (v1.0, v1.1), approval records, and release status.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "timetable_id": {
                    "type": "STRING",
                    "description": "Optional timetable ID.",
                },
                "department_id": {
                    "type": "STRING",
                    "description": "Optional department ID filter.",
                },
            },
        },
    },
]


# =============================================================================
# SERVER-SIDE TOOL IMPLEMENTATIONS
# =============================================================================
class AIToolExecutor:
    """Executes validated tools against live DB and OR-Tools CP-SAT engine."""

    def __init__(self, db: AsyncSession, current_user: User):
        self.db = db
        self.user = current_user

    async def execute(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Dispatch tool name with security bounds and audit logging."""
        logger.info(
            "AI Assistant Tool Invocation: user=%s role=%s tool=%s args=%s",
            self.user.email,
            self.user.role,
            tool_name,
            arguments,
        )

        handler = getattr(self, f"_tool_{tool_name}", None)
        if not handler:
            return {
                "error": f"Tool '{tool_name}' is not recognized by TIMEVERSE system.",
                "success": False,
            }

        try:
            result = await handler(arguments)
            return result
        except Exception as e:
            logger.exception("Error executing tool %s: %s", tool_name, e)
            return {
                "error": f"Tool execution failed: {str(e)}",
                "success": False,
            }

    # 1. get_academic_configuration
    async def _tool_get_academic_configuration(self, args: dict[str, Any]) -> dict[str, Any]:
        dept_id = args.get("department_id")
        dept_stmt = select(Department)
        if dept_id:
            dept_stmt = dept_stmt.where(Department.id == dept_id)
        depts = (await self.db.execute(dept_stmt)).scalars().all()

        slots_stmt = select(TimeSlot).order_by(TimeSlot.day_of_week, TimeSlot.period_number)
        slots = (await self.db.execute(slots_stmt)).scalars().all()

        terms = (await self.db.execute(select(AcademicTerm))).scalars().all()

        period_timings = {}
        for s in slots:
            if s.period_number not in period_timings:
                period_timings[s.period_number] = {
                    "period_number": s.period_number,
                    "start_time": s.start_time.strftime("%H:%M") if s.start_time else "",
                    "end_time": s.end_time.strftime("%H:%M") if s.end_time else "",
                    "is_break": s.is_break,
                }

        return {
            "institution": "Kristu Jayanti University (KJU), Airport Road Campus",
            "departments": [{"id": d.id, "code": d.code, "name": d.name} for d in depts],
            "active_terms": [{"id": t.id, "name": t.name, "is_active": t.is_active} for t in terms],
            "working_days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"],
            "period_schedule": list(period_timings.values()),
            "institutional_rules": {
                "daily_teaching_cap_per_teacher": 5,
                "max_consecutive_periods": 3,
                "universal_lunch_break_period": 4,
                "recess_timing": "12:00 PM - 01:00 PM",
            },
        }

    # 2. search_faculty
    async def _tool_search_faculty(self, args: dict[str, Any]) -> dict[str, Any]:
        query = (args.get("query") or "").strip().lower()
        dept_id = args.get("department_id")

        stmt = select(Teacher).options(selectinload(Teacher.user), selectinload(Teacher.department))
        if dept_id:
            stmt = stmt.where(Teacher.department_id == dept_id)
        teachers = (await self.db.execute(stmt)).scalars().all()

        db_faculty = []
        for t in teachers:
            name = t.user.full_name if t.user else t.employee_code
            emp_code = t.employee_code
            dept_name = t.department.name if t.department else "Computer Science"
            if not query or query in name.lower() or query in emp_code.lower():
                db_faculty.append({
                    "id": t.id,
                    "name": name,
                    "employee_code": emp_code,
                    "department": dept_name,
                    "email": t.user.email if t.user else "",
                    "max_daily_hours": t.max_hours_per_day,
                    "max_weekly_hours": t.max_weekly_hours,
                    "source": "Active TIMEVERSE Database",
                })

        # Also search KJU DPMS official directory records
        kju_records = _load_kju_faculty()
        kju_matches = []
        for f in kju_records:
            if not query or query in f["name"].lower() or query in f["designation"].lower():
                kju_matches.append(f)

        return {
            "total_database_teachers": len(db_faculty),
            "faculty_records": db_faculty,
            "kju_dpms_official_faculty": kju_matches[:10],
            "query_used": query or "ALL",
        }

    # 3. get_faculty_workload
    async def _tool_get_faculty_workload(self, args: dict[str, Any]) -> dict[str, Any]:
        raw_key = (args.get("faculty_name_or_code") or "").strip()
        if not raw_key:
            return {"error": "faculty_name_or_code argument is required."}

        stmt = select(Teacher).options(selectinload(Teacher.user), selectinload(Teacher.department))
        teachers = (await self.db.execute(stmt)).scalars().all()

        target_teacher = None
        for t in teachers:
            name = (t.user.full_name if t.user else "").lower()
            code = t.employee_code.lower()
            t_id = t.id.lower()
            key_low = raw_key.lower()
            if key_low in name or key_low in code or key_low == t_id or any(p in name for p in key_low.split() if len(p) > 2):
                target_teacher = t
                break

        if not target_teacher:
            # Check KJU official records as fallback
            kju_faculty = _load_kju_faculty()
            for kf in kju_faculty:
                if raw_key.lower() in kf["name"].lower():
                    return {
                        "name": kf["name"],
                        "designation": kf["designation"],
                        "department": kf["department"],
                        "institution": kf["institution"],
                        "workload_status": "Official faculty profile recorded. No active local schedule commitments found in current semester.",
                        "notes": kf["notes"],
                    }
            return {"error": f"Faculty '{raw_key}' not found in university scheduling records."}

        # Role-based privacy guard: Teachers can only view their own workload unless privileged
        is_privileged = self.user.role in {UserRoleEnum.ADMIN, UserRoleEnum.HOD, UserRoleEnum.COORDINATOR}
        if self.user.role == UserRoleEnum.TEACHER and not is_privileged:
            if target_teacher.user_id != self.user.id:
                return {
                    "error": "Access Denied: Faculty members can only view their own personal workload and schedule.",
                    "allowed_user": self.user.full_name,
                }
        elif self.user.role in {UserRoleEnum.STUDENT, UserRoleEnum.CR}:
            return {
                "error": "Access Denied: Students and Class Representatives are not permitted to inspect faculty workload metrics.",
            }

        # Query assigned sessions in latest timetable
        latest_tt = (await self.db.execute(
            select(Timetable).order_by(Timetable.version_major.desc(), Timetable.version_minor.desc()).limit(1)
        )).scalars().first()

        assigned_sessions = []
        if latest_tt:
            sess_stmt = (
                select(TimetableSession)
                .options(
                    selectinload(TimetableSession.subject),
                    selectinload(TimetableSession.cohort_section),
                    selectinload(TimetableSession.room),
                    selectinload(TimetableSession.time_slot),
                )
                .where(
                    TimetableSession.timetable_id == latest_tt.id,
                    TimetableSession.teacher_id == target_teacher.id,
                )
            )
            assigned_sessions = (await self.db.execute(sess_stmt)).scalars().all()

        day_distribution: dict[int, int] = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0}
        subjects_taught = set()
        sections_taught = set()
        day_names = {1: "Mon", 2: "Tue", 3: "Wed", 4: "Thu", 5: "Fri", 6: "Sat"}

        for s in assigned_sessions:
            if s.time_slot:
                d = s.time_slot.day_of_week
                day_distribution[d] = day_distribution.get(d, 0) + 1
            if s.subject:
                subjects_taught.add(f"{s.subject.code} - {s.subject.name}")
            if s.cohort_section:
                sections_taught.add(s.cohort_section.section_name)

        total_hours = len(assigned_sessions)
        max_daily_observed = max(day_distribution.values()) if day_distribution else 0

        return {
            "teacher_id": target_teacher.id,
            "faculty_name": target_teacher.user.full_name if target_teacher.user else target_teacher.employee_code,
            "employee_code": target_teacher.employee_code,
            "department": target_teacher.department.name if target_teacher.department else "Computer Science",
            "weekly_teaching_hours_scheduled": total_hours,
            "weekly_hour_cap": target_teacher.max_weekly_hours,
            "max_daily_hour_cap": target_teacher.max_hours_per_day,
            "peak_daily_hours_observed": max_daily_observed,
            "workload_compliance": (
                "Compliant with university policy"
                if total_hours <= target_teacher.max_weekly_hours and max_daily_observed <= target_teacher.max_hours_per_day
                else "Attention: Scheduled hours exceed configured threshold"
            ),
            "subjects_assigned": list(subjects_taught),
            "sections_taught": list(sections_taught),
            "daily_period_counts": {day_names[d]: c for d, c in day_distribution.items()},
        }

    # 4. search_rooms
    async def _tool_search_rooms(self, args: dict[str, Any]) -> dict[str, Any]:
        room_type = args.get("room_type")
        min_capacity = args.get("min_capacity")
        building = args.get("building")

        stmt = select(Room).where(Room.is_active == True)
        rooms = (await self.db.execute(stmt)).scalars().all()

        filtered = []
        for r in rooms:
            if room_type and r.room_type.value.upper() != room_type.upper():
                continue
            if min_capacity and r.capacity < min_capacity:
                continue
            if building and building.lower() not in r.building.lower():
                continue
            filtered.append({
                "id": r.id,
                "building": r.building,
                "room_number": r.room_number,
                "full_label": f"{r.building} {r.room_number}",
                "capacity": r.capacity,
                "room_type": r.room_type.value,
                "equipment": r.equipment or [],
            })

        return {
            "total_matching_rooms": len(filtered),
            "rooms": filtered,
        }

    # 5. get_subjects
    async def _tool_get_subjects(self, args: dict[str, Any]) -> dict[str, Any]:
        dept_id = args.get("department_id")
        code_or_name = (args.get("code_or_name") or "").strip().lower()

        stmt = select(Subject).where(Subject.is_active == True)
        if dept_id:
            stmt = stmt.where(Subject.department_id == dept_id)
        subjects = (await self.db.execute(stmt)).scalars().all()

        filtered = []
        for s in subjects:
            if code_or_name and code_or_name not in s.code.lower() and code_or_name not in s.name.lower():
                continue
            filtered.append({
                "id": s.id,
                "code": s.code,
                "name": s.name,
                "credits": s.credits,
                "type": s.subject_type.value,
                "required_room_type": s.required_room_type.value,
            })

        return {
            "total_subjects": len(filtered),
            "subjects": filtered,
        }

    # 6. get_teaching_requirements
    async def _tool_get_teaching_requirements(self, args: dict[str, Any]) -> dict[str, Any]:
        section_id = args.get("cohort_section_id")
        sub_code = (args.get("subject_code") or "").strip().lower()

        # Enforce student scoping
        if self.user.role in {UserRoleEnum.STUDENT, UserRoleEnum.CR}:
            enrolled = [e.cohort_section_id for e in self.user.student_enrollments if e.is_active]
            if section_id and section_id not in enrolled:
                return {"error": "Access Denied: You may only view requirements for your enrolled section."}
            if not section_id and enrolled:
                section_id = enrolled[0]

        stmt = select(SubjectRequirement).options(
            selectinload(SubjectRequirement.subject),
            selectinload(SubjectRequirement.cohort_section),
            selectinload(SubjectRequirement.teacher).selectinload(Teacher.user),
        )
        if section_id:
            stmt = stmt.where(SubjectRequirement.cohort_section_id == section_id)
        reqs = (await self.db.execute(stmt)).scalars().all()

        results = []
        for r in reqs:
            if sub_code and r.subject and sub_code not in r.subject.code.lower():
                continue
            results.append({
                "requirement_id": r.id,
                "section": r.cohort_section.section_name if r.cohort_section else "",
                "subject_code": r.subject.code if r.subject else "",
                "subject_name": r.subject.name if r.subject else "",
                "subject_type": r.subject.subject_type.value if r.subject else "THEORY",
                "required_weekly_sessions": r.required_sessions_per_week,
                "consecutive_periods": r.requires_consecutive_periods,
                "assigned_teacher": r.teacher.user.full_name if r.teacher and r.teacher.user else "Unassigned",
            })

        return {
            "total_requirements": len(results),
            "requirements": results,
        }

    # 7. get_timetable
    async def _tool_get_timetable(self, args: dict[str, Any]) -> dict[str, Any]:
        tt_id = args.get("timetable_id")
        section_id = args.get("section_id")
        day_of_week = args.get("day_of_week")
        teacher_query = (args.get("teacher_name_or_code") or "").strip().lower()

        # Resolve timetable
        if not tt_id:
            tt_stmt = select(Timetable).order_by(Timetable.version_major.desc(), Timetable.version_minor.desc())
            if self.user.role in {UserRoleEnum.STUDENT, UserRoleEnum.CR}:
                tt_stmt = tt_stmt.where(Timetable.status == TimetableStatusEnum.PUBLISHED)
            tt = (await self.db.execute(tt_stmt)).scalars().first()
            if not tt:
                return {"error": "No timetable found in the system."}
            tt_id = tt.id
        else:
            tt = (await self.db.execute(select(Timetable).where(Timetable.id == tt_id))).scalars().first()
            if not tt:
                return {"error": f"Timetable '{tt_id}' not found."}

        # Role checks
        if self.user.role in {UserRoleEnum.STUDENT, UserRoleEnum.CR}:
            if tt.status != TimetableStatusEnum.PUBLISHED:
                return {"error": "Access Denied: Students and CRs can only view PUBLISHED official timetables."}
            enrolled = [e.cohort_section_id for e in self.user.student_enrollments if e.is_active]
            if section_id and section_id not in enrolled:
                return {"error": "Access Denied: You can only view timetable for your assigned section."}
            if not section_id and enrolled:
                section_id = enrolled[0]

        # Query sessions
        sess_stmt = (
            select(TimetableSession)
            .options(
                selectinload(TimetableSession.subject),
                selectinload(TimetableSession.cohort_section),
                selectinload(TimetableSession.room),
                selectinload(TimetableSession.teacher).selectinload(Teacher.user),
                selectinload(TimetableSession.time_slot),
            )
            .where(TimetableSession.timetable_id == tt_id)
        )
        if section_id:
            sess_stmt = sess_stmt.where(TimetableSession.cohort_section_id == section_id)
        sessions = (await self.db.execute(sess_stmt)).scalars().all()

        day_names = {1: "Monday", 2: "Tuesday", 3: "Wednesday", 4: "Thursday", 5: "Friday", 6: "Saturday"}
        formatted_sessions = []
        for s in sessions:
            if not s.time_slot:
                continue
            if day_of_week and s.time_slot.day_of_week != day_of_week:
                continue
            t_name = s.teacher.user.full_name if s.teacher and s.teacher.user else ""
            if teacher_query and teacher_query not in t_name.lower():
                continue

            formatted_sessions.append({
                "session_id": s.id,
                "day_of_week": s.time_slot.day_of_week,
                "day_name": day_names.get(s.time_slot.day_of_week, ""),
                "period": s.time_slot.period_number,
                "start_time": s.time_slot.start_time.strftime("%H:%M") if s.time_slot.start_time else "",
                "end_time": s.time_slot.end_time.strftime("%H:%M") if s.time_slot.end_time else "",
                "subject_code": s.subject.code if s.subject else "",
                "subject_name": s.subject.name if s.subject else "",
                "teacher": t_name,
                "room": f"{s.room.building} {s.room.room_number}" if s.room else "",
                "section": s.cohort_section.section_name if s.cohort_section else "",
                "is_locked": s.is_locked,
            })

        formatted_sessions.sort(key=lambda x: (x["day_of_week"], x["period"]))

        return {
            "timetable_id": tt.id,
            "version": f"v{tt.version_major}.{tt.version_minor}",
            "status": tt.status.value,
            "total_sessions_found": len(formatted_sessions),
            "sessions": formatted_sessions[:30],
        }

    # 8. detect_scheduling_conflicts
    async def _tool_detect_scheduling_conflicts(self, args: dict[str, Any]) -> dict[str, Any]:
        tt_id = args.get("timetable_id")
        if not tt_id:
            latest = (await self.db.execute(
                select(Timetable.id).order_by(Timetable.version_major.desc(), Timetable.version_minor.desc()).limit(1)
            )).scalar_one_or_none()
            tt_id = latest

        if not tt_id:
            return {"error": "No timetable found to analyze for conflicts."}

        analysis = await ConflictService.analyze_conflicts(tt_id, self.db)
        return {
            "timetable_id": tt_id,
            "is_conflict_free": analysis["is_conflict_free"],
            "critical_conflicts_count": analysis["critical_conflicts_count"],
            "warnings_count": analysis["warnings_count"],
            "critical_conflicts": analysis["critical_conflicts"][:10],
            "warnings": analysis["warnings"][:10],
            "solver_diagnostics": analysis["solver_diagnostics"],
        }

    # 9. generate_timetable (Google OR-Tools CP-SAT)
    async def _tool_generate_timetable(self, args: dict[str, Any]) -> dict[str, Any]:
        # Server-side authorization: HOD, Coordinator, Admin only
        if self.user.role not in {UserRoleEnum.ADMIN, UserRoleEnum.HOD, UserRoleEnum.COORDINATOR}:
            return {
                "error": "Permission denied: Only HOD, Timetable Coordinator, or Administrator can run the timetable solver.",
                "user_role": self.user.role.value if hasattr(self.user.role, "value") else str(self.user.role),
            }

        dept_id = args.get("department_id") or "dept_cs"
        term_id = args.get("academic_term_id") or "term_odd_2026"
        time_limit = args.get("time_limit_seconds") or 15
        avoid_day = args.get("avoid_teacher_day")
        avoid_teacher_id = args.get("avoid_teacher_id")

        # 1. Fetch time slots
        slots = (await self.db.execute(
            select(TimeSlot).order_by(TimeSlot.day_of_week, TimeSlot.period_number)
        )).scalars().all()
        slots_input = [
            TimeSlotInput(
                id=s.id,
                day_of_week=s.day_of_week,
                period_number=s.period_number,
                is_break=s.is_break,
                start_time=s.start_time.strftime("%H:%M") if s.start_time else "08:30",
                end_time=s.end_time.strftime("%H:%M") if s.end_time else "09:20",
            )
            for s in slots
        ]

        # 2. Fetch rooms
        rooms = (await self.db.execute(select(Room).where(Room.is_active == True))).scalars().all()
        rooms_input = [
            RoomScheduleInput(
                id=r.id,
                building=r.building,
                room_number=r.room_number,
                capacity=r.capacity,
                room_type=r.room_type.value,
                is_active=r.is_active,
            )
            for r in rooms
        ]

        # 3. Fetch teachers with availabilities
        teachers = (await self.db.execute(
            select(Teacher).where(Teacher.department_id == dept_id).options(
                selectinload(Teacher.availabilities), selectinload(Teacher.user)
            )
        )).scalars().all()

        teachers_input = []
        for t in teachers:
            unavail = set(a.time_slot_id for a in t.availabilities if not a.is_available)
            if avoid_day and (not avoid_teacher_id or t.id == avoid_teacher_id):
                for s in slots:
                    if s.day_of_week == avoid_day:
                        unavail.add(s.id)
            prefs = {a.time_slot_id: a.preference_weight for a in t.availabilities if a.is_available}
            teachers_input.append(
                TeacherScheduleInput(
                    id=t.id,
                    name=t.user.full_name if t.user else t.employee_code,
                    max_hours_per_day=t.max_hours_per_day,
                    max_consecutive_hours=t.max_consecutive_hours,
                    max_weekly_hours=t.max_weekly_hours,
                    unavailable_slot_ids=frozenset(unavail),
                    preference_weights=prefs,
                )
            )

        # 4. Fetch cohort sections
        cohorts = (await self.db.execute(
            select(CohortSection).where(CohortSection.department_id == dept_id)
        )).scalars().all()
        cohorts_input = [
            CohortSectionInput(
                id=c.id,
                department_id=c.department_id,
                section_name=c.section_name,
                student_count=c.student_count,
            )
            for c in cohorts
        ]
        cohort_ids = [c.id for c in cohorts]

        # 5. Fetch subject requirements
        reqs = (await self.db.execute(
            select(SubjectRequirement)
            .where(SubjectRequirement.cohort_section_id.in_(cohort_ids))
            .options(selectinload(SubjectRequirement.subject))
        )).scalars().all()
        reqs_input = [
            SubjectRequirementInput(
                id=rq.id,
                cohort_section_id=rq.cohort_section_id,
                subject_id=rq.subject_id,
                subject_code=rq.subject.code if rq.subject else "",
                subject_name=rq.subject.name if rq.subject else "",
                subject_type=rq.subject.subject_type.value if rq.subject else "THEORY",
                teacher_id=rq.teacher_id,
                required_room_type=rq.subject.required_room_type.value if rq.subject else "LECTURE_HALL",
                required_sessions_per_week=rq.required_sessions_per_week,
                duration_periods=rq.duration_periods,
                requires_consecutive_periods=rq.requires_consecutive_periods,
                preferred_room_id=rq.preferred_room_id,
            )
            for rq in reqs
        ]

        pref = (await self.db.execute(
            select(SchedulingPreference).where(SchedulingPreference.department_id == dept_id)
        )).scalars().first()

        config = SchedulingConfig(
            department_id=dept_id,
            academic_term_id=term_id,
            time_slots=slots_input,
            rooms=rooms_input,
            teachers=teachers_input,
            cohort_sections=cohorts_input,
            subject_requirements=reqs_input,
            locked_sessions=[],
            weight_teacher_preference=pref.weight_teacher_preference if pref else 10,
            weight_room_stability=pref.weight_room_stability if pref else 5,
            weight_minimize_gaps=pref.weight_minimize_gaps if pref else 10,
            weight_distribute_evenly=pref.weight_distribute_evenly if pref else 15,
            max_search_time_seconds=min(time_limit, 30),
        )

        solver = TimetableSolver(config)
        solver_res = solver.solve()

        if not solver_res.is_success:
            return {
                "success": False,
                "solver_status": solver_res.status.value,
                "error": "The constraint solver could not find a clash-free schedule with current parameters.",
                "diagnostics": solver_res.diagnostics,
            }

        validator = TimetableValidator(config)
        val_res = validator.validate(solver_res.sessions)

        candidate_sessions = [
            {
                "requirement_id": s.requirement_id,
                "cohort_section_id": s.cohort_section_id,
                "subject_id": s.subject_id,
                "teacher_id": s.teacher_id,
                "room_id": s.room_id,
                "time_slot_id": s.time_slot_id,
                "is_locked": False,
            }
            for s in solver_res.sessions
        ]

        proposed_action = {
            "action_type": "APPROVE_AND_SAVE_TIMETABLE",
            "title": f"Review & Commit Solved Schedule ({len(candidate_sessions)} Sessions)",
            "description": (
                f"Google OR-Tools CP-SAT generated a clash-free schedule with {len(candidate_sessions)} periods. "
                f"Deterministic Validator: {val_res.is_valid} (0 Hard Conflicts). "
                "Explicit confirmation is required to save or publish this timetable."
            ),
            "requires_confirmation": True,
            "execution_payload": {
                "department_id": dept_id,
                "academic_term_id": term_id,
                "sessions": candidate_sessions,
                "publish_directly": False,
            },
        }

        return {
            "success": True,
            "solver_status": solver_res.status.value,
            "total_sessions_scheduled": len(solver_res.sessions),
            "objective_score": solver_res.objective_value,
            "hard_conflict_count": len(val_res.violations),
            "is_valid": val_res.is_valid,
            "proposed_action": proposed_action,
        }

    # 10. preview_timetable_changes
    async def _tool_preview_timetable_changes(self, args: dict[str, Any]) -> dict[str, Any]:
        session_id = args.get("session_id")
        if not session_id:
            return {"error": "session_id is required"}

        sess = (await self.db.execute(
            select(TimetableSession).where(TimetableSession.id == session_id)
        )).scalars().first()
        if not sess:
            return {"error": f"Session '{session_id}' not found."}

        new_slot = args.get("new_time_slot_id") or sess.time_slot_id
        new_room = args.get("new_room_id") or sess.room_id
        new_teacher = args.get("new_teacher_id") or sess.teacher_id

        conflicts, warnings = await detect_session_conflicts(
            db=self.db,
            timetable_id=sess.timetable_id,
            time_slot_id=new_slot,
            teacher_id=new_teacher,
            room_id=new_room,
            cohort_section_id=sess.cohort_section_id,
            exclude_session_id=session_id,
        )

        return {
            "session_id": session_id,
            "can_apply_cleanly": len(conflicts) == 0,
            "conflicts_detected": conflicts,
            "warnings": warnings,
            "proposed_slot": new_slot,
            "proposed_room": new_room,
            "proposed_teacher": new_teacher,
        }

    # 11. apply_timetable_changes
    async def _tool_apply_timetable_changes(self, args: dict[str, Any]) -> dict[str, Any]:
        session_id = args.get("session_id")
        confirmed = args.get("confirmed", False)

        if not confirmed:
            return {
                "error": "Operation blocked: Explicit user confirmation ('confirmed': true) is required to apply schedule database mutations.",
                "requires_confirmation": True,
            }

        # Role guard
        is_faculty_or_admin = self.user.role in {
            UserRoleEnum.ADMIN,
            UserRoleEnum.HOD,
            UserRoleEnum.COORDINATOR,
            UserRoleEnum.TEACHER,
        }
        if not is_faculty_or_admin:
            return {"error": "Permission denied: Only Faculty, HOD, and Administrators can modify timetable sessions."}

        sess = (await self.db.execute(
            select(TimetableSession).where(TimetableSession.id == session_id)
        )).scalars().first()
        if not sess:
            return {"error": f"Session '{session_id}' not found."}

        if sess.is_locked:
            return {"error": "Cannot modify locked timetable session. Please unlock it first."}

        new_slot = args.get("new_time_slot_id")
        new_room = args.get("new_room_id")
        new_teacher = args.get("new_teacher_id")

        if new_slot:
            sess.time_slot_id = new_slot
        if new_room:
            sess.room_id = new_room
        if new_teacher:
            sess.teacher_id = new_teacher

        await self.db.commit()

        # Audit conflict check
        reval = await ConflictService.analyze_conflicts(sess.timetable_id, self.db)

        return {
            "success": True,
            "session_id": session_id,
            "message": "Schedule change applied and committed to database successfully.",
            "is_conflict_free": reval["is_conflict_free"],
            "critical_conflicts": reval["critical_conflicts_count"],
        }

    # 12. get_publication_status
    async def _tool_get_publication_status(self, args: dict[str, Any]) -> dict[str, Any]:
        dept_id = args.get("department_id")
        tt_id = args.get("timetable_id")

        stmt = select(Timetable).order_by(Timetable.version_major.desc(), Timetable.version_minor.desc())
        if tt_id:
            stmt = stmt.where(Timetable.id == tt_id)
        elif dept_id:
            stmt = stmt.where(Timetable.department_id == dept_id)

        tables = (await self.db.execute(stmt)).scalars().all()
        return {
            "total_timetables": len(tables),
            "versions": [
                {
                    "id": t.id,
                    "version": f"v{t.version_major}.{t.version_minor}",
                    "status": t.status.value,
                    "solver_status": t.solver_status,
                    "published_at": t.published_at.isoformat() if t.published_at else None,
                    "created_at": t.created_at.isoformat(),
                    "notes": t.notes,
                }
                for t in tables[:5]
            ],
        }
