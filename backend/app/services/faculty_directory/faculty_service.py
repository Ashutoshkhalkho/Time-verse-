import csv
import io
import re
import uuid
from datetime import UTC, datetime
from typing import Any


from sqlalchemy import desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictException, NotFoundException, ValidationException
from app.models.audit import AuditEvent
from app.models.faculty_directory import (
    FacultyDirectoryMember,
    ProfileStatusEnum,
    generate_directory_id,
)
from app.models.user import User
from app.schemas.faculty_directory import (
    CSVCommitRequest,
    CSVCommitResponse,
    CSVPreviewResponse,
    CSVPreviewRow,
    FacultyMemberCreate,
    FacultyMemberResponse,
    FacultyMemberUpdate,
    FacultyMemberVerifyRequest,
)

# 26 Exact Initial Faculty Records for DPMS, Kristu Jayanti University
INITIAL_26_FACULTY_DATA = [
    {
        "no": 1,
        "full_name": "Dr. V. G. Jisha",
        "designation": "Head, Department of Professional Management Studies",
        "source_notes": "Official department FDP document (2025) — Confirmed in cited university source",
        "is_verified": False,  # Initial dataset: formal academic verification requires admin audit
        "profile_status": ProfileStatusEnum.PENDING_VERIFICATION,
    },
    {
        "no": 2,
        "full_name": "Dr. C. H. Raja Kamal",
        "designation": None,  # Not verified in reviewed source
        "source_notes": "KJU research-project records / staff coordinator listing — Designation not confirmed in source reviewed",
        "is_verified": False,
        "profile_status": ProfileStatusEnum.PENDING_VERIFICATION,
    },
    {
        "no": 3,
        "full_name": "Dr. A. J. Excelce",
        "designation": "Associate Professor",
        "source_notes": "Official KJU FDP page / 2025 FDP document — Confirmed in cited university source",
        "is_verified": False,
        "profile_status": ProfileStatusEnum.PENDING_VERIFICATION,
    },
    {
        "no": 4,
        "full_name": "Dr. Ajai Abraham Thomas",
        "designation": "Coordinator, Department of Professional Management Studies",
        "source_notes": "Official KJU FDP document (2025) — Confirmed in cited university source",
        "is_verified": False,
        "profile_status": ProfileStatusEnum.PENDING_VERIFICATION,
    },
    {
        "no": 5,
        "full_name": "Dr. Sivaprasad V",
        "designation": None,
        "source_notes": "KJU research-project records / staff coordinator listing — Designation not confirmed in source reviewed",
        "is_verified": False,
        "profile_status": ProfileStatusEnum.PENDING_VERIFICATION,
    },
    {
        "no": 6,
        "full_name": "Dr. Eshan M. R.",
        "designation": None,
        "source_notes": "KJU research-project records — Designation not confirmed in source reviewed",
        "is_verified": False,
        "profile_status": ProfileStatusEnum.PENDING_VERIFICATION,
    },
    {
        "no": 7,
        "full_name": "Dr. Roshen Therese Sebastian",
        "designation": "Assistant Professor (listed in 2023–24 report)",
        "source_notes": "KJU annual report 2023–24 — Historical designation; current status unverified",
        "is_verified": False,
        "profile_status": ProfileStatusEnum.PENDING_VERIFICATION,
    },
    {
        "no": 8,
        "full_name": "Dr. Jagdeep Singh",
        "designation": None,
        "source_notes": "KJU faculty achievements page — Designation not confirmed in source reviewed",
        "is_verified": False,
        "profile_status": ProfileStatusEnum.PENDING_VERIFICATION,
    },
    {
        "no": 9,
        "full_name": "Dr. Arunkumar B",
        "designation": "Assistant Professor",
        "source_notes": "Official KJU FDP document (2025) — Confirmed in cited university source",
        "is_verified": False,
        "profile_status": ProfileStatusEnum.PENDING_VERIFICATION,
    },
    {
        "no": 10,
        "full_name": "Mr. Haribaskar R",
        "designation": "Assistant Professor (listed in 2023–24 report)",
        "source_notes": "KJU annual report 2023–24 — Historical designation; current status unverified",
        "is_verified": False,
        "profile_status": ProfileStatusEnum.PENDING_VERIFICATION,
    },
    {
        "no": 11,
        "full_name": "Mr. Vipulkumar N. M.",
        "designation": None,
        "source_notes": "KJU research-project records — Designation not confirmed in source reviewed",
        "is_verified": False,
        "profile_status": ProfileStatusEnum.PENDING_VERIFICATION,
    },
    {
        "no": 12,
        "full_name": "Mr. Leslie Dass P",
        "designation": None,
        "source_notes": "KJU research-project records (listed as Mr. Leslie) — Name/designation needs confirmation",
        "is_verified": False,
        "profile_status": ProfileStatusEnum.PENDING_VERIFICATION,
    },
    {
        "no": 13,
        "full_name": "Ms. C. Shilpa Rao",
        "designation": "Assistant Professor (listed in 2023–24 report)",
        "source_notes": "KJU annual report 2023–24 — Historical designation; current status unverified",
        "is_verified": False,
        "profile_status": ProfileStatusEnum.PENDING_VERIFICATION,
        "duplicate_flag": True,
        "duplicate_notes": "Flagged for manual review with potential duplicate 'Ms. Shilpa Rao' (Record 24). Preserved as distinct record until administrator determination.",
    },
    {
        "no": 14,
        "full_name": "Ms. Rupashree R",
        "designation": "Assistant Professor (listed in 2023–24 report)",
        "source_notes": "KJU annual report 2023–24 — Historical designation; current status unverified",
        "is_verified": False,
        "profile_status": ProfileStatusEnum.PENDING_VERIFICATION,
    },
    {
        "no": 15,
        "full_name": "Ms. Ponny Thomas",
        "designation": None,
        "source_notes": "KJU research-project records — Designation not confirmed in source reviewed",
        "is_verified": False,
        "profile_status": ProfileStatusEnum.PENDING_VERIFICATION,
    },
    {
        "no": 16,
        "full_name": "Dr. Manju M. Kaimal",
        "designation": None,
        "source_notes": "KJU faculty achievements page lists Ms. Manju M Kaimal — Name/title discrepancy; verify with department",
        "is_verified": False,
        "profile_status": ProfileStatusEnum.PENDING_VERIFICATION,
    },
    {
        "no": 17,
        "full_name": "Dr. Subha B",
        "designation": None,
        "source_notes": "KJU faculty achievements page — Designation not confirmed in source reviewed",
        "is_verified": False,
        "profile_status": ProfileStatusEnum.PENDING_VERIFICATION,
    },
    {
        "no": 18,
        "full_name": "Ms. Syalini S",
        "designation": None,
        "source_notes": "Previously compiled list; no current designation verified — Needs official confirmation",
        "is_verified": False,
        "profile_status": ProfileStatusEnum.PENDING_VERIFICATION,
    },
    {
        "no": 19,
        "full_name": "Dr. Bincy Ann Babu",
        "designation": None,
        "source_notes": "Previously compiled list; no current designation verified — Needs official confirmation",
        "is_verified": False,
        "profile_status": ProfileStatusEnum.PENDING_VERIFICATION,
    },
    {
        "no": 20,
        "full_name": "Dr. Manisha Seal",
        "designation": None,
        "source_notes": "KJU library listing identifies department affiliation — Designation not confirmed in source reviewed",
        "is_verified": False,
        "profile_status": ProfileStatusEnum.PENDING_VERIFICATION,
    },
    {
        "no": 21,
        "full_name": "Dr. Ashy Sebastian",
        "designation": None,
        "source_notes": "Previously compiled list; no current designation verified — Needs official confirmation",
        "is_verified": False,
        "profile_status": ProfileStatusEnum.PENDING_VERIFICATION,
    },
    {
        "no": 22,
        "full_name": "Dr. V. S. Divyasre",
        "designation": None,
        "source_notes": "KJU faculty achievements page — Designation not confirmed in source reviewed",
        "is_verified": False,
        "profile_status": ProfileStatusEnum.PENDING_VERIFICATION,
    },
    {
        "no": 23,
        "full_name": "Ms. Divya Sajan",
        "designation": None,
        "source_notes": "Previously compiled list; no current designation verified — Needs official confirmation",
        "is_verified": False,
        "profile_status": ProfileStatusEnum.PENDING_VERIFICATION,
    },
    {
        "no": 24,
        "full_name": "Ms. Shilpa Rao",
        "designation": None,
        "source_notes": "Possible duplicate of Ms. C. Shilpa Rao; KJU records use 'Ms. Shilpa Rao C' and 'Ms. C. Shilpa Rao' — Likely duplicate; confirm",
        "is_verified": False,
        "profile_status": ProfileStatusEnum.PENDING_VERIFICATION,
        "duplicate_flag": True,
        "duplicate_notes": "Flagged for manual review with potential duplicate 'Ms. C. Shilpa Rao' (Record 13). Preserved as distinct record until administrator determination.",
    },
    {
        "no": 25,
        "full_name": "Dr. Marina Joshy C.",
        "designation": None,
        "source_notes": "Previously compiled list; no current designation verified — Needs official confirmation",
        "is_verified": False,
        "profile_status": ProfileStatusEnum.PENDING_VERIFICATION,
    },
    {
        "no": 26,
        "full_name": "Ms. Priya A",
        "designation": None,
        "source_notes": "Previously compiled list; no current designation verified — Needs official confirmation",
        "is_verified": False,
        "profile_status": ProfileStatusEnum.PENDING_VERIFICATION,
    },
]


def normalize_faculty_name(name: str) -> str:
    """
    Normalizes titles, initials, punctuation, and casing for duplicate matching.
    Leaves original strings unaffected in database storage.
    Examples:
      'Ms. C. Shilpa Rao' -> 'c shilpa rao'
      'Ms. Shilpa Rao' -> 'shilpa rao'
      'Dr. V. G. Jisha' -> 'v g jisha'
    """
    if not name:
        return ""
    # Strip common academic/honorific prefixes
    cleaned = re.sub(
        r"^(dr\.?|mr\.?|ms\.?|mrs\.?|prof\.?)\s+",
        "",
        name.strip(),
        flags=re.IGNORECASE,
    )
    # Replace dots and special punctuation with space
    cleaned = re.sub(r"[^\w\s]", " ", cleaned)
    # Collapse multiple spaces and lowercase
    cleaned = " ".join(cleaned.split()).lower()
    return cleaned


def extract_sort_key(full_name: str) -> str:
    """
    Extracts a sortable key ignoring title prefixes so sorting by name
    orders predictably by core family/given name rather than honorifics.
    """
    stripped = re.sub(
        r"^(dr\.?|mr\.?|ms\.?|mrs\.?|prof\.?)\s+",
        "",
        full_name.strip(),
        flags=re.IGNORECASE,
    )
    return stripped.strip().lower()


def compute_missing_fields(member: FacultyDirectoryMember) -> list[str]:
    """Identifies missing fields without inventing or falsifying information."""
    missing = []
    if not member.designation:
        missing.append("Formal Designation")
    if not member.faculty_id:
        missing.append("Faculty ID")
    if not member.official_email:
        missing.append("Official Email")
    if not member.profile_photo:
        missing.append("Profile Photograph")
    if not member.subjects_taught:
        missing.append("Subjects Taught")
    if not member.specialisation:
        missing.append("Specialisation / Research")
    if not member.office_location:
        missing.append("Office Location")
    return missing


def check_for_potential_duplicates(
    full_name: str,
    existing_members: list[FacultyDirectoryMember],
) -> tuple[bool, str | None, FacultyDirectoryMember | None]:
    """
    Checks if a name is an exact match or potential duplicate of existing records.
    Explicitly flags 'Ms. C. Shilpa Rao' and 'Ms. Shilpa Rao'.
    """
    norm_incoming = normalize_faculty_name(full_name)
    tokens_incoming = set(norm_incoming.split())

    for existing in existing_members:
        norm_existing = normalize_faculty_name(existing.full_name)
        if norm_incoming == norm_existing:
            return True, f"Exact normalized name match with existing record: '{existing.full_name}'", existing

        # Specific Shilpa Rao duplicate rule
        if ("shilpa" in tokens_incoming and "rao" in tokens_incoming) and (
            "shilpa" in norm_existing and "rao" in norm_existing
        ):
            return (
                True,
                f"Potential duplicate detected between '{full_name}' and '{existing.full_name}' (requires manual review).",
                existing,
            )

        # Cross-token overlap for middle initials (e.g., 'Leslie Dass P' vs 'Leslie Dass')
        tokens_existing = set(norm_existing.split())
        shared = tokens_incoming.intersection(tokens_existing)
        # If share 2 or more significant non-single-letter tokens
        significant_shared = [t for t in shared if len(t) > 1]
        if len(significant_shared) >= 2 and len(tokens_incoming) <= len(tokens_existing) + 1:
            if norm_incoming != norm_existing:
                return (
                    True,
                    f"Possible variation of existing record '{existing.full_name}' (shared tokens: {', '.join(significant_shared)}).",
                    existing,
                )

    return False, None, None


def map_member_to_response(member: FacultyDirectoryMember) -> FacultyMemberResponse:
    """Converts ORM model to API response schema."""
    verified_by_name = member.verified_by.full_name if member.verified_by else None
    return FacultyMemberResponse(
        id=member.id,
        full_name=member.full_name,
        normalized_name=member.normalized_name,
        designation=member.designation,
        department=member.department,
        institution=member.institution,
        faculty_id=member.faculty_id,
        official_email=member.official_email,
        profile_photo=member.profile_photo,
        subjects_taught=member.subjects_taught or [],
        specialisation=member.specialisation,
        office_location=member.office_location,
        profile_status=member.profile_status,
        is_verified=member.is_verified,
        source_notes=member.source_notes,
        verification_notes=member.verification_notes,
        verified_by_user_id=member.verified_by_user_id,
        verified_by_name=verified_by_name,
        verified_at=member.verified_at,
        archived_at=member.archived_at,
        duplicate_flag=member.duplicate_flag,
        duplicate_notes=member.duplicate_notes,
        potential_duplicate_of_id=member.potential_duplicate_of_id,
        missing_fields=compute_missing_fields(member),
        created_at=member.created_at,
        updated_at=member.updated_at,
    )


class FacultyDirectoryService:
    @staticmethod
    async def list_members(
        db: AsyncSession,
        search: str | None = None,
        designation: str | None = None,
        profile_status: ProfileStatusEnum | None = None,
        is_verified: bool | None = None,
        include_archived: bool = False,
        sort_by: str = "name_asc",
    ) -> list[FacultyMemberResponse]:
        stmt = select(FacultyDirectoryMember)

        if not include_archived:
            stmt = stmt.where(FacultyDirectoryMember.archived_at.is_(None))
        else:
            # If explicitly requested archived only or all
            pass

        if designation:
            if designation == "UNVERIFIED":
                stmt = stmt.where(FacultyDirectoryMember.designation.is_(None))
            else:
                stmt = stmt.where(FacultyDirectoryMember.designation == designation)

        if profile_status:
            stmt = stmt.where(FacultyDirectoryMember.profile_status == profile_status)

        if is_verified is not None:
            stmt = stmt.where(FacultyDirectoryMember.is_verified == is_verified)

        if search and search.strip():
            term = f"%{search.strip().lower()}%"
            stmt = stmt.where(
                or_(
                    func.lower(FacultyDirectoryMember.full_name).like(term),
                    func.lower(FacultyDirectoryMember.normalized_name).like(term),
                    func.lower(func.coalesce(FacultyDirectoryMember.designation, "")).like(term),
                    func.lower(func.coalesce(FacultyDirectoryMember.specialisation, "")).like(term),
                )
            )

        results = (await db.execute(stmt)).scalars().all()

        # In-memory alphabetical sorting with title-prefix stripping for predictability
        members = list(results)
        if sort_by == "name_asc":
            members.sort(key=lambda m: extract_sort_key(m.full_name))
        elif sort_by == "name_desc":
            members.sort(key=lambda m: extract_sort_key(m.full_name), reverse=True)
        elif sort_by == "verified_first":
            members.sort(key=lambda m: (not m.is_verified, extract_sort_key(m.full_name)))
        elif sort_by == "created_desc":
            members.sort(key=lambda m: m.created_at, reverse=True)
        else:
            members.sort(key=lambda m: extract_sort_key(m.full_name))

        return [map_member_to_response(m) for m in members]

    @staticmethod
    async def get_member(db: AsyncSession, member_id: str) -> FacultyMemberResponse:
        stmt = select(FacultyDirectoryMember).where(FacultyDirectoryMember.id == member_id)
        member = (await db.execute(stmt)).scalars().first()
        if not member:
            raise NotFoundException(f"Faculty directory record '{member_id}' not found.")
        return map_member_to_response(member)

    @staticmethod
    async def create_member(
        db: AsyncSession,
        data: FacultyMemberCreate,
        current_user: User,
    ) -> FacultyMemberResponse:
        # Check duplicate
        all_members = (await db.execute(select(FacultyDirectoryMember))).scalars().all()
        is_dup, dup_reason, existing_dup = check_for_potential_duplicates(data.full_name, list(all_members))

        norm_name = normalize_faculty_name(data.full_name)
        new_member = FacultyDirectoryMember(
            id=generate_directory_id(),
            full_name=data.full_name.strip(),
            normalized_name=norm_name,
            designation=data.designation.strip() if data.designation else None,
            department=data.department.strip(),
            institution=data.institution.strip(),
            faculty_id=data.faculty_id.strip() if data.faculty_id else None,
            official_email=data.official_email.strip() if data.official_email else None,
            profile_photo=data.profile_photo.strip() if data.profile_photo else None,
            subjects_taught=data.subjects_taught or [],
            specialisation=data.specialisation.strip() if data.specialisation else None,
            office_location=data.office_location.strip() if data.office_location else None,
            profile_status=data.profile_status,
            is_verified=data.is_verified,
            source_notes=data.source_notes,
            verification_notes=data.verification_notes,
            duplicate_flag=is_dup,
            duplicate_notes=dup_reason if is_dup else None,
            potential_duplicate_of_id=existing_dup.id if existing_dup else None,
        )

        db.add(new_member)
        await db.commit()
        await db.refresh(new_member)
        return map_member_to_response(new_member)

    @staticmethod
    async def update_member(
        db: AsyncSession,
        member_id: str,
        data: FacultyMemberUpdate,
        current_user: User,
    ) -> FacultyMemberResponse:
        stmt = select(FacultyDirectoryMember).where(FacultyDirectoryMember.id == member_id)
        member = (await db.execute(stmt)).scalars().first()
        if not member:
            raise NotFoundException(f"Faculty directory record '{member_id}' not found.")

        if member.archived_at is not None:
            raise ValidationException("Cannot modify an archived faculty record. Unarchive it first.")

        update_dict = data.model_dump(exclude_unset=True)
        if "full_name" in update_dict and update_dict["full_name"]:
            member.full_name = update_dict["full_name"].strip()
            member.normalized_name = normalize_faculty_name(member.full_name)

        if "designation" in update_dict:
            val = update_dict["designation"]
            member.designation = val.strip() if val else None

        if "department" in update_dict and update_dict["department"]:
            member.department = update_dict["department"].strip()

        if "institution" in update_dict and update_dict["institution"]:
            member.institution = update_dict["institution"].strip()

        if "faculty_id" in update_dict:
            val = update_dict["faculty_id"]
            member.faculty_id = val.strip() if val else None

        if "official_email" in update_dict:
            val = update_dict["official_email"]
            member.official_email = val.strip() if val else None

        if "profile_photo" in update_dict:
            val = update_dict["profile_photo"]
            member.profile_photo = val.strip() if val else None

        if "subjects_taught" in update_dict and update_dict["subjects_taught"] is not None:
            member.subjects_taught = update_dict["subjects_taught"]

        if "specialisation" in update_dict:
            val = update_dict["specialisation"]
            member.specialisation = val.strip() if val else None

        if "office_location" in update_dict:
            val = update_dict["office_location"]
            member.office_location = val.strip() if val else None

        if "profile_status" in update_dict and update_dict["profile_status"]:
            member.profile_status = update_dict["profile_status"]

        if "source_notes" in update_dict:
            member.source_notes = update_dict["source_notes"]

        if "verification_notes" in update_dict:
            member.verification_notes = update_dict["verification_notes"]

        member.updated_at = datetime.now(UTC)
        await db.commit()
        await db.refresh(member)
        return map_member_to_response(member)

    @staticmethod
    async def verify_member(
        db: AsyncSession,
        member_id: str,
        data: FacultyMemberVerifyRequest,
        current_user: User,
    ) -> FacultyMemberResponse:
        stmt = select(FacultyDirectoryMember).where(FacultyDirectoryMember.id == member_id)
        member = (await db.execute(stmt)).scalars().first()
        if not member:
            raise NotFoundException(f"Faculty directory record '{member_id}' not found.")

        if not data.acknowledged_responsibility:
            raise ValidationException("Verification requires explicit administrator acknowledgement of responsibility.")

        if data.designation:
            member.designation = data.designation.strip()

        member.is_verified = True
        member.profile_status = data.profile_status
        member.verified_by_user_id = current_user.id
        member.verified_at = datetime.now(UTC)
        member.verification_notes = (
            f"Verified by {current_user.full_name} ({current_user.role.value}) on "
            f"{datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}: {data.verification_notes}"
        )
        member.updated_at = datetime.now(UTC)

        # Audit Event logging
        audit_event = AuditEvent(
            id=f"aud_{uuid.uuid4().hex[:20]}",
            actor_user_id=current_user.id,
            institution_id=getattr(current_user, "institution_id", None) or "inst_01",
            action="FACULTY_PROFILE_VERIFIED",
            resource_type="FacultyDirectoryMember",
            resource_id=member.id[:26],
            after_state={
                "member_name": member.full_name,
                "verified_designation": member.designation,
                "verifier_email": current_user.email,
                "verifier_role": current_user.role.value,
            },
            reason=data.verification_notes,
            ip_address="internal_api",
        )
        db.add(audit_event)

        await db.commit()
        await db.refresh(member)
        return map_member_to_response(member)

    @staticmethod
    async def archive_member(
        db: AsyncSession,
        member_id: str,
        current_user: User,
        reason: str | None = None,
    ) -> FacultyMemberResponse:
        stmt = select(FacultyDirectoryMember).where(FacultyDirectoryMember.id == member_id)
        member = (await db.execute(stmt)).scalars().first()
        if not member:
            raise NotFoundException(f"Faculty directory record '{member_id}' not found.")

        member.archived_at = datetime.now(UTC)
        member.profile_status = ProfileStatusEnum.INACTIVE
        member.updated_at = datetime.now(UTC)

        # Audit event
        audit_event = AuditEvent(
            id=f"aud_{uuid.uuid4().hex[:20]}",
            actor_user_id=current_user.id,
            institution_id=getattr(current_user, "institution_id", None) or "inst_01",
            action="FACULTY_PROFILE_ARCHIVED",
            resource_type="FacultyDirectoryMember",
            resource_id=member.id[:26],
            after_state={
                "member_name": member.full_name,
                "archived_by": current_user.email,
            },
            reason=reason or "Soft-archived by authorized administrator",
            ip_address="internal_api",
        )
        db.add(audit_event)


        await db.commit()
        await db.refresh(member)
        return map_member_to_response(member)

    @staticmethod
    async def restore_member(
        db: AsyncSession,
        member_id: str,
        current_user: User,
    ) -> FacultyMemberResponse:
        stmt = select(FacultyDirectoryMember).where(FacultyDirectoryMember.id == member_id)
        member = (await db.execute(stmt)).scalars().first()
        if not member:
            raise NotFoundException(f"Faculty directory record '{member_id}' not found.")

        member.archived_at = None
        member.profile_status = ProfileStatusEnum.ACTIVE if member.is_verified else ProfileStatusEnum.PENDING_VERIFICATION
        member.updated_at = datetime.now(UTC)
        await db.commit()
        await db.refresh(member)
        return map_member_to_response(member)

    @staticmethod
    async def preview_csv(db: AsyncSession, csv_content: str) -> CSVPreviewResponse:
        """
        Parses CSV, validates headers and rows, reports unknown columns,
        and flags duplicates (including Ms. C. Shilpa Rao vs Ms. Shilpa Rao).
        """
        try:
            reader = csv.DictReader(io.StringIO(csv_content))
        except Exception as e:
            raise ValidationException(f"Unable to parse CSV data: {str(e)}")

        if not reader.fieldnames:
            raise ValidationException("CSV file contains no header row.")

        fieldnames = [f.strip() for f in reader.fieldnames if f]

        # Identify header mapping
        name_col = None
        desig_col = None
        notes_col = None

        for col in fieldnames:
            col_lower = col.lower()
            if "faculty" in col_lower or "name" in col_lower or "member" in col_lower:
                name_col = col
            elif "designation" in col_lower or "role" in col_lower or "post" in col_lower:
                desig_col = col
            elif "source" in col_lower or "note" in col_lower or "verification" in col_lower:
                notes_col = col

        if not name_col:
            raise ValidationException(
                f"Missing required faculty name column. Detected columns: {', '.join(fieldnames)}"
            )

        unrecognized = [c for c in fieldnames if c not in {name_col, desig_col, notes_col, "No.", "No", "no"}]

        # Fetch existing database records to compare
        existing_stmt = select(FacultyDirectoryMember)
        existing_members = list((await db.execute(existing_stmt)).scalars().all())

        preview_rows: list[CSVPreviewRow] = []
        valid_count = 0
        invalid_count = 0
        dup_count = 0

        row_idx = 1
        for row in reader:
            raw_name = (row.get(name_col) or "").strip()
            raw_desig = (row.get(desig_col) or "").strip() if desig_col else None
            raw_notes = (row.get(notes_col) or "").strip() if notes_col else None

            # Collect unmapped columns
            unrecognized_data = {k: row.get(k, "") for k in unrecognized if row.get(k)}

            errors = []
            if not raw_name:
                errors.append("Faculty member name is missing or empty.")

            # Map designation: if says 'Not verified', leave unverified (None)
            mapped_desig = None
            if raw_desig and raw_desig.lower() not in {"not verified", "unverified", "none", "n/a", ""}:
                mapped_desig = raw_desig

            is_dup = False
            dup_reason = None
            matched_member = None

            if raw_name:
                is_dup, dup_reason, matched_member = check_for_potential_duplicates(raw_name, existing_members)

            if is_dup:
                dup_count += 1

            is_valid = len(errors) == 0
            if is_valid:
                valid_count += 1
            else:
                invalid_count += 1

            preview_rows.append(
                CSVPreviewRow(
                    row_number=row_idx,
                    full_name=raw_name,
                    raw_designation=raw_desig,
                    mapped_designation=mapped_desig,
                    source_notes=raw_notes,
                    is_valid=is_valid,
                    validation_errors=errors,
                    is_potential_duplicate=is_dup,
                    potential_duplicate_reason=dup_reason,
                    existing_member_id=matched_member.id if matched_member else None,
                    existing_member_name=matched_member.full_name if matched_member else None,
                    existing_is_verified=matched_member.is_verified if matched_member else False,
                    unrecognized_columns=unrecognized_data,
                )
            )
            row_idx += 1

        return CSVPreviewResponse(
            total_rows=len(preview_rows),
            valid_rows_count=valid_count,
            invalid_rows_count=invalid_count,
            potential_duplicates_count=dup_count,
            detected_headers=fieldnames,
            unrecognized_headers=unrecognized,
            rows=preview_rows,
        )

    @staticmethod
    async def commit_csv(
        db: AsyncSession,
        request: CSVCommitRequest,
        current_user: User,
    ) -> CSVCommitResponse:
        """
        Idempotently commits CSV rows.
        Does NOT overwrite verified designations unless explicit overwrite_verified is true.
        Preserves potential duplicates (such as Ms. C. Shilpa Rao and Ms. Shilpa Rao) as separate records.
        """
        if not request.confirmed:
            raise ValidationException("Explicit administrator confirmation is required before committing CSV import.")

        existing_stmt = select(FacultyDirectoryMember)
        existing_members = {
            m.normalized_name: m
            for m in (await db.execute(existing_stmt)).scalars().all()
        }

        created = 0
        updated = 0
        skipped = 0
        rejected = 0
        messages: list[str] = []

        for row in request.rows:
            raw_name = row.full_name.strip()
            if not raw_name:
                rejected += 1
                messages.append("Rejected row with empty faculty name.")
                continue

            norm_name = normalize_faculty_name(raw_name)
            existing = existing_members.get(norm_name)

            # Map designation
            desig_to_use = None
            if row.designation and row.designation.lower() not in {"not verified", "unverified", "none", "n/a", ""}:
                desig_to_use = row.designation.strip()

            if existing:
                # Do not overwrite verified administrator information
                if existing.is_verified and not request.overwrite_verified:
                    skipped += 1
                    messages.append(
                        f"Skipped overwrite on verified member '{existing.full_name}'. Existing verified status preserved."
                    )
                    continue

                # If existing is unverified and has new data, update notes
                if desig_to_use and not existing.designation:
                    existing.designation = desig_to_use
                if row.source_notes and not existing.source_notes:
                    existing.source_notes = row.source_notes
                existing.updated_at = datetime.now(UTC)
                updated += 1
                messages.append(f"Updated source notes for existing record '{existing.full_name}'.")
            else:
                # Create new member
                is_dup, dup_reason, matched_dup = check_for_potential_duplicates(raw_name, list(existing_members.values()))
                new_m = FacultyDirectoryMember(
                    id=generate_directory_id(),
                    full_name=raw_name,
                    normalized_name=norm_name,
                    designation=desig_to_use,
                    department="Department of Professional Management Studies",
                    institution="Kristu Jayanti University",
                    profile_status=ProfileStatusEnum.PENDING_VERIFICATION,
                    is_verified=False,
                    source_notes=row.source_notes,
                    duplicate_flag=is_dup,
                    duplicate_notes=dup_reason if is_dup else None,
                    potential_duplicate_of_id=matched_dup.id if matched_dup else None,
                )
                db.add(new_m)
                existing_members[norm_name] = new_m
                created += 1
                messages.append(f"Created new faculty directory record: '{raw_name}'.")

        await db.commit()

        # Audit Event logging
        audit_event = AuditEvent(
            id=f"aud_{uuid.uuid4().hex[:20]}",
            actor_user_id=current_user.id,
            institution_id=getattr(current_user, "institution_id", None) or "inst_01",
            action="FACULTY_DIRECTORY_CSV_IMPORTED",
            resource_type="FacultyDirectoryMember",
            resource_id="batch_import",
            after_state={
                "imported_by": current_user.email,
                "created": created,
                "updated": updated,
                "skipped": skipped,
                "rejected": rejected,
            },
            reason="CSV Import batch committed",
            ip_address="internal_api",
        )
        db.add(audit_event)
        await db.commit()


        return CSVCommitResponse(
            total_processed=len(request.rows),
            created_count=created,
            updated_count=updated,
            skipped_count=skipped,
            rejected_count=rejected,
            messages=messages[:50],  # Return up to first 50 summary messages
        )

    @staticmethod
    async def seed_initial_records(db: AsyncSession) -> dict[str, int]:
        """
        Idempotently seeds all 26 initial records for DPMS, Kristu Jayanti University.
        Preserves exact supplied names, historical source citations, and duplicate flags.
        Does not overwrite administrator edits or certified records on re-runs.
        """
        existing_stmt = select(FacultyDirectoryMember)
        existing = {
            m.full_name.strip(): m
            for m in (await db.execute(existing_stmt)).scalars().all()
        }

        created = 0
        preserved = 0

        # Step 1: Insert missing records
        inserted_models: list[FacultyDirectoryMember] = []
        for rec in INITIAL_26_FACULTY_DATA:
            name = rec["full_name"].strip()
            if name in existing:
                preserved += 1
                continue

            member = FacultyDirectoryMember(
                id=generate_directory_id(),
                full_name=name,
                normalized_name=normalize_faculty_name(name),
                designation=rec["designation"],
                department="Department of Professional Management Studies",
                institution="Kristu Jayanti University",
                profile_status=rec["profile_status"],
                is_verified=rec["is_verified"],
                source_notes=rec["source_notes"],
                duplicate_flag=rec.get("duplicate_flag", False),
                duplicate_notes=rec.get("duplicate_notes"),
            )
            db.add(member)
            inserted_models.append(member)
            existing[name] = member
            created += 1

        if created > 0:
            await db.commit()

        # Step 2: Ensure mutual duplicate links between Ms. C. Shilpa Rao and Ms. Shilpa Rao
        m_c_shilpa = existing.get("Ms. C. Shilpa Rao")
        m_shilpa = existing.get("Ms. Shilpa Rao")
        if m_c_shilpa and m_shilpa:
            m_c_shilpa.potential_duplicate_of_id = m_shilpa.id
            m_c_shilpa.duplicate_flag = True
            m_shilpa.potential_duplicate_of_id = m_c_shilpa.id
            m_shilpa.duplicate_flag = True
            await db.commit()

        return {"created": created, "preserved": preserved, "total": len(INITIAL_26_FACULTY_DATA)}
