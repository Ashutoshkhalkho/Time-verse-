import io
import re
from typing import Any

import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cohort import CohortSection
from app.models.curriculum import Subject, SubjectTypeEnum
from app.models.infrastructure import Room, RoomTypeEnum
from app.models.organization import Department
from app.models.teacher import Teacher
from app.models.user import User
from app.services.importer.schemas import (
    EntityImportType,
    ImportPreviewResponse,
    RowError,
)


class ImporterService:
    """
    Ingestion & Preflight Validation Engine for College Scheduling Data.
    Uses Pandas & OpenPyXL for parsing, duplicate detection, and referential validation.
    Zero silent data loss: malformed records are blocked with row-level diagnostics.
    """

    TEMPLATES = {
        EntityImportType.TEACHERS: [
            {"employee_code": "T001", "email": "dr.sharma@timewise.edu", "full_name": "Dr. Rohit Sharma", "department_code": "CS", "max_hours_per_day": 5, "max_weekly_hours": 20},
            {"employee_code": "T002", "email": "prof.gupta@timewise.edu", "full_name": "Prof. Anita Gupta", "department_code": "CS", "max_hours_per_day": 4, "max_weekly_hours": 18},
        ],
        EntityImportType.ROOMS: [
            {"building": "Main Block", "room_number": "101", "capacity": 50, "room_type": "LECTURE_HALL"},
            {"building": "Science Block", "room_number": "LAB-1", "capacity": 40, "room_type": "COMPUTER_LAB"},
        ],
        EntityImportType.SUBJECTS: [
            {"code": "CS301", "name": "Data Structures", "credits": 4, "subject_type": "THEORY", "required_room_type": "LECTURE_HALL", "department_code": "CS"},
            {"code": "CS301L", "name": "Data Structures Lab", "credits": 2, "subject_type": "LABORATORY", "required_room_type": "COMPUTER_LAB", "department_code": "CS"},
        ],
        EntityImportType.REQUIREMENTS: [
            {"section_name": "CS-3A", "subject_code": "CS301", "employee_code": "T001", "required_sessions_per_week": 4},
            {"section_name": "CS-3A", "subject_code": "CS301L", "employee_code": "T001", "required_sessions_per_week": 2},
        ],
    }

    @staticmethod
    def generate_template(entity_type: EntityImportType, file_format: str = "csv") -> tuple[bytes, str, str]:
        data = ImporterService.TEMPLATES.get(entity_type, [])
        df = pd.DataFrame(data)

        if file_format.lower() == "xlsx":
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                df.to_excel(writer, index=False, sheet_name=f"{entity_type.value.title()} Template")
            return (
                output.getvalue(),
                f"{entity_type.value}_template.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        else:
            csv_str = df.to_csv(index=False)
            return (
                csv_str.encode("utf-8"),
                f"{entity_type.value}_template.csv",
                "text/csv",
            )

    @staticmethod
    async def parse_and_validate(
        content: bytes,
        filename: str,
        entity_type: EntityImportType,
        db_session: AsyncSession,
    ) -> ImportPreviewResponse:
        errors: list[RowError] = []

        try:
            if filename.endswith(".xlsx") or filename.endswith(".xls"):
                df = pd.read_excel(io.BytesIO(content), engine="openpyxl")
            else:
                df = pd.read_csv(io.BytesIO(content))
        except Exception as e:
            return ImportPreviewResponse(
                entity_type=entity_type,
                total_rows=0,
                valid_rows=0,
                invalid_rows=0,
                is_committable=False,
                errors=[RowError(row_number=0, field="file", error_message=f"Failed to parse file: {str(e)}")],
                preview_records=[],
            )

        # Replace NaN with None
        df = df.where(pd.notnull(df), None)
        total_rows = len(df)
        if total_rows == 0:
            return ImportPreviewResponse(
                entity_type=entity_type,
                total_rows=0,
                valid_rows=0,
                invalid_rows=0,
                is_committable=False,
                errors=[RowError(row_number=0, field="file", error_message="Uploaded file contains 0 rows.")],
                preview_records=[],
            )

        # Fetch reference entities from DB for foreign key / cross-validation
        dept_result = await db_session.execute(select(Department.code, Department.id))
        departments = {row[0].upper(): row[1] for row in dept_result.fetchall()}

        room_result = await db_session.execute(select(Room.building, Room.room_number, Room.id))
        existing_rooms = {(b.upper(), r.upper()): rid for b, r, rid in room_result.fetchall()}

        teacher_result = await db_session.execute(select(Teacher.employee_code, Teacher.id))
        existing_teachers = {code.upper(): tid for code, tid in teacher_result.fetchall()}

        subject_result = await db_session.execute(select(Subject.code, Subject.id))
        existing_subjects = {code.upper(): sid for code, sid in subject_result.fetchall()}

        cohort_result = await db_session.execute(select(CohortSection.section_name, CohortSection.id))
        existing_cohorts = {name.upper(): cid for name, cid in cohort_result.fetchall()}

        user_result = await db_session.execute(select(User.email))
        existing_emails = {row[0].lower() for row in user_result.fetchall()}

        seen_keys: set[Any] = set()
        invalid_row_indices: set[int] = set()

        for idx, row in df.iterrows():
            row_num = idx + 2  # 1-indexed header + row

            if entity_type == EntityImportType.TEACHERS:
                ImporterService._validate_teacher_row(
                    row, row_num, departments, existing_emails, seen_keys, errors, invalid_row_indices, idx
                )
            elif entity_type == EntityImportType.ROOMS:
                ImporterService._validate_room_row(
                    row, row_num, existing_rooms, seen_keys, errors, invalid_row_indices, idx
                )
            elif entity_type == EntityImportType.SUBJECTS:
                ImporterService._validate_subject_row(
                    row, row_num, departments, seen_keys, errors, invalid_row_indices, idx
                )
            elif entity_type == EntityImportType.REQUIREMENTS:
                ImporterService._validate_requirement_row(
                    row, row_num, existing_cohorts, existing_subjects, existing_teachers, seen_keys, errors, invalid_row_indices, idx
                )

        invalid_count = len(invalid_row_indices)
        valid_count = total_rows - invalid_count
        is_committable = invalid_count == 0

        # Create serializable preview records with row status
        preview_records: list[dict[str, Any]] = []
        for idx, row in df.iterrows():
            row_dict = row.to_dict()
            row_dict["_row_number"] = idx + 2
            row_dict["_is_valid"] = idx not in invalid_row_indices
            row_dict["_errors"] = [e.error_message for e in errors if e.row_number == (idx + 2)]
            preview_records.append(row_dict)

        return ImportPreviewResponse(
            entity_type=entity_type,
            total_rows=total_rows,
            valid_rows=valid_count,
            invalid_rows=invalid_count,
            is_committable=is_committable,
            errors=errors,
            preview_records=preview_records[:50],  # Return up to 50 for preview
        )

    @staticmethod
    def _is_blank(val: Any) -> bool:
        if val is None:
            return True
        if pd.isna(val):
            return True
        s = str(val).strip().lower()
        return s in {"", "nan", "none", "<na>"}

    @staticmethod
    def _validate_teacher_row(row, row_num, departments, existing_emails, seen_keys, errors, invalid_indices, idx):
        required = ["employee_code", "email", "full_name", "department_code"]
        for field in required:
            if ImporterService._is_blank(row.get(field)):
                errors.append(RowError(row_number=row_num, field=field, error_message=f"Missing required field '{field}'."))
                invalid_indices.add(idx)

        if not ImporterService._is_blank(row.get("employee_code")):
            code = str(row.get("employee_code")).strip().upper()
            if code in seen_keys:
                errors.append(RowError(row_number=row_num, field="employee_code", error_message=f"Duplicate employee code '{code}' in file.", value=code))
                invalid_indices.add(idx)
            seen_keys.add(code)

        if not ImporterService._is_blank(row.get("email")):
            email = str(row.get("email")).strip().lower()
            if not re.match(r"^[^@]+@[^@]+\.[^@]+$", email):
                errors.append(RowError(row_number=row_num, field="email", error_message=f"Invalid email format '{email}'.", value=email))
                invalid_indices.add(idx)
            elif email in existing_emails:
                errors.append(RowError(row_number=row_num, field="email", error_message=f"User with email '{email}' already exists in system.", value=email))
                invalid_indices.add(idx)

        if not ImporterService._is_blank(row.get("department_code")):
            dept_code = str(row.get("department_code")).strip().upper()
            if dept_code not in departments:
                errors.append(RowError(row_number=row_num, field="department_code", error_message=f"Department code '{dept_code}' not found.", value=dept_code))
                invalid_indices.add(idx)

    @staticmethod
    def _validate_room_row(row, row_num, existing_rooms, seen_keys, errors, invalid_indices, idx):
        required = ["building", "room_number", "capacity", "room_type"]
        for field in required:
            if ImporterService._is_blank(row.get(field)):
                errors.append(RowError(row_number=row_num, field=field, error_message=f"Missing required field '{field}'."))
                invalid_indices.add(idx)

        bldg = "" if ImporterService._is_blank(row.get("building")) else str(row.get("building")).strip().upper()
        num = "" if ImporterService._is_blank(row.get("room_number")) else str(row.get("room_number")).strip().upper()
        key = (bldg, num)
        if bldg and num:
            if key in seen_keys:
                errors.append(RowError(row_number=row_num, field="room_number", error_message=f"Duplicate room '{bldg} {num}' in file."))
                invalid_indices.add(idx)
            seen_keys.add(key)
            if key in existing_rooms:
                errors.append(RowError(row_number=row_num, field="room_number", error_message=f"Room '{bldg} {num}' already exists in database."))
                invalid_indices.add(idx)

        cap = row.get("capacity")
        if not ImporterService._is_blank(cap):
            try:
                cap_val = int(float(cap))
                if cap_val <= 0:
                    errors.append(RowError(row_number=row_num, field="capacity", error_message="Room capacity must be greater than 0.", value=cap))
                    invalid_indices.add(idx)
            except (ValueError, TypeError):
                errors.append(RowError(row_number=row_num, field="capacity", error_message="Room capacity must be a valid integer.", value=cap))
                invalid_indices.add(idx)

        if not ImporterService._is_blank(row.get("room_type")):
            rtype = str(row.get("room_type")).strip().upper()
            valid_types = {e.value for e in RoomTypeEnum}
            if rtype not in valid_types:
                errors.append(RowError(row_number=row_num, field="room_type", error_message=f"Invalid room type '{rtype}'. Allowed: {sorted(valid_types)}", value=rtype))
                invalid_indices.add(idx)

    @staticmethod
    def _validate_subject_row(row, row_num, departments, seen_keys, errors, invalid_indices, idx):
        required = ["code", "name", "credits", "subject_type", "required_room_type", "department_code"]
        for field in required:
            if ImporterService._is_blank(row.get(field)):
                errors.append(RowError(row_number=row_num, field=field, error_message=f"Missing required field '{field}'."))
                invalid_indices.add(idx)

        if not ImporterService._is_blank(row.get("code")):
            code = str(row.get("code")).strip().upper()
            if code in seen_keys:
                errors.append(RowError(row_number=row_num, field="code", error_message=f"Duplicate subject code '{code}' in file.", value=code))
                invalid_indices.add(idx)
            seen_keys.add(code)

        if not ImporterService._is_blank(row.get("subject_type")):
            stype = str(row.get("subject_type")).strip().upper()
            valid_stypes = {e.value for e in SubjectTypeEnum}
            if stype not in valid_stypes:
                errors.append(RowError(row_number=row_num, field="subject_type", error_message=f"Invalid subject type '{stype}'. Allowed: {sorted(valid_stypes)}", value=stype))
                invalid_indices.add(idx)

        if not ImporterService._is_blank(row.get("required_room_type")):
            rtype = str(row.get("required_room_type")).strip().upper()
            valid_rtypes = {e.value for e in RoomTypeEnum}
            if rtype not in valid_rtypes:
                errors.append(RowError(row_number=row_num, field="required_room_type", error_message=f"Invalid room type '{rtype}'. Allowed: {sorted(valid_rtypes)}", value=rtype))
                invalid_indices.add(idx)

        if not ImporterService._is_blank(row.get("department_code")):
            dept_code = str(row.get("department_code")).strip().upper()
            if dept_code not in departments:
                errors.append(RowError(row_number=row_num, field="department_code", error_message=f"Department code '{dept_code}' not found.", value=dept_code))
                invalid_indices.add(idx)

    @staticmethod
    def _validate_requirement_row(row, row_num, cohorts, subjects, teachers, seen_keys, errors, invalid_indices, idx):
        required = ["section_name", "subject_code", "employee_code", "required_sessions_per_week"]
        for field in required:
            if ImporterService._is_blank(row.get(field)):
                errors.append(RowError(row_number=row_num, field=field, error_message=f"Missing required field '{field}'."))
                invalid_indices.add(idx)

        sname = None
        if not ImporterService._is_blank(row.get("section_name")):
            sname = str(row.get("section_name")).strip().upper()
            if sname not in cohorts:
                errors.append(RowError(row_number=row_num, field="section_name", error_message=f"Section '{sname}' does not exist.", value=sname))
                invalid_indices.add(idx)

        scode = None
        if not ImporterService._is_blank(row.get("subject_code")):
            scode = str(row.get("subject_code")).strip().upper()
            if scode not in subjects:
                errors.append(RowError(row_number=row_num, field="subject_code", error_message=f"Subject code '{scode}' does not exist.", value=scode))
                invalid_indices.add(idx)

        if not ImporterService._is_blank(row.get("employee_code")):
            ecode = str(row.get("employee_code")).strip().upper()
            if ecode not in teachers:
                errors.append(RowError(row_number=row_num, field="employee_code", error_message=f"Teacher with employee code '{ecode}' does not exist.", value=ecode))
                invalid_indices.add(idx)

        if sname and scode:
            key = (sname, scode)
            if key in seen_keys:
                errors.append(RowError(row_number=row_num, field="subject_code", error_message=f"Duplicate mapping for Section '{sname}' and Subject '{scode}' in file."))
                invalid_indices.add(idx)
            seen_keys.add(key)

        periods = row.get("required_sessions_per_week")
        if not ImporterService._is_blank(periods):
            try:
                pval = int(float(periods))
                if pval <= 0:
                    errors.append(RowError(row_number=row_num, field="required_sessions_per_week", error_message="Required sessions per week must be > 0.", value=periods))
                    invalid_indices.add(idx)
            except (ValueError, TypeError):
                errors.append(RowError(row_number=row_num, field="required_sessions_per_week", error_message="Required sessions per week must be a valid integer.", value=periods))
                invalid_indices.add(idx)

