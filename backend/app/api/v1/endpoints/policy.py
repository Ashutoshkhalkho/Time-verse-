from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import PermissionGuard, get_current_user
from app.core.exceptions import ForbiddenException
from app.core.permissions import Permission
from app.db.session import get_db_session
from app.models.user import MentorAssignment, User, UserRoleEnum

router = APIRouter(tags=["Policy & Timetable Workflows"])


class DraftTimetableRequest(BaseModel):
    department_id: str
    academic_term_id: str
    notes: str | None = None


class ChangeRequestCreate(BaseModel):
    session_id: str
    reason: str
    requested_slot_id: str | None = None


class IssueReportCreate(BaseModel):
    room_id: str
    description: str


# Policy 1 & 2 & 3: Timetable Viewing with Scoping
@router.get(
    "/timetables/published",
    summary="View Published Timetables",
    description="Returns published sessions scoped strictly to the authenticated user's jurisdiction.",
    dependencies=[Depends(PermissionGuard(Permission.TIMETABLE_VIEW_PUBLISHED))],
)
async def view_published_timetables(
    current_user: Annotated[User, Depends(get_current_user)],
    section_id: str | None = Query(None, description="Requested section filter"),
    department_id: str | None = Query(None, description="Requested department filter"),
) -> dict:
    """
    Server enforces:
    - Student: can only view their own enrolled sections. Cannot view other sections.
    - CR: can only view their assigned section.
    - Teacher: views their assigned teaching schedule.
    - HOD/Coordinator: scoped to their departmental timetables.
    - Admin: institution-wide.
    """
    user_sections = [e.cohort_section_id for e in current_user.student_enrollments if e.is_active]
    user_depts = [s.department_id for s in current_user.department_scopes]

    if current_user.role in {UserRoleEnum.STUDENT, UserRoleEnum.CR}:
        # If client passes a section_id, verify it matches enrolled sections
        if section_id and section_id not in user_sections:
            raise ForbiddenException(
                f"Access denied: You are not authorized to view section '{section_id}'."
            )
        effective_sections = [section_id] if section_id else user_sections
        return {
            "scope": "SECTION",
            "allowed_sections": effective_sections,
            "can_edit": False,
            "message": "Authorized view for student/CR section.",
        }

    if current_user.role == UserRoleEnum.TEACHER:
        return {
            "scope": "TEACHER",
            "teacher_id": current_user.id,
            "can_edit": True,
            "message": "Authorized personal teaching schedule with faculty edit access.",
        }

    if current_user.role in {UserRoleEnum.HOD, UserRoleEnum.COORDINATOR}:
        if department_id and department_id not in user_depts:
            raise ForbiddenException(
                f"Access denied: You are not authorized for department '{department_id}'."
            )
        return {
            "scope": "DEPARTMENT",
            "allowed_departments": [department_id] if department_id else user_depts,
            "can_edit": True,
            "can_publish": current_user.role == UserRoleEnum.HOD,
        }

    return {
        "scope": "INSTITUTION",
        "institution_id": current_user.institution_id,
        "can_edit": True,
        "can_publish": True,
    }


# Policy 4: Coordinators can generate draft schedules
@router.post(
    "/timetables/draft",
    status_code=status.HTTP_201_CREATED,
    summary="Create Draft Timetable Proposal",
    description="Coordinators, HODs, and Admins can create draft schedules. Students, CRs, and Teachers are forbidden.",
    dependencies=[Depends(PermissionGuard(Permission.TIMETABLE_VIEW_DRAFT, require_department_scope=True))],
)
async def create_draft_schedule(
    payload: DraftTimetableRequest,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    return {
        "status": "DRAFT_CREATED",
        "department_id": payload.department_id,
        "created_by": current_user.id,
        "version": "1.0-draft",
    }


# Policy 5: HODs can approve publication within their department authority
@router.post(
    "/departments/{department_id}/timetables/{timetable_id}/publish",
    status_code=status.HTTP_200_OK,
    summary="Publish Timetable",
    description="Only HOD of the specified department or College Admin can publish. Coordinators and Students cannot.",
    dependencies=[Depends(PermissionGuard(Permission.TIMETABLE_PUBLISH, require_department_scope=True))],
)
async def publish_timetable(
    department_id: str,
    timetable_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    return {
        "status": "PUBLISHED",
        "timetable_id": timetable_id,
        "department_id": department_id,
        "approved_by": current_user.id,
        "version": "v1.0",
    }


# Policy 6: Faculty can submit change requests; students and CRs cannot
@router.post(
    "/change-requests",
    status_code=status.HTTP_201_CREATED,
    summary="Submit Change Request",
    description="Faculty and staff can submit change requests. Students and CRs cannot edit official schedules.",
    dependencies=[Depends(PermissionGuard(Permission.CHANGE_REQUEST_SUBMIT))],
)
async def submit_change_request(
    payload: ChangeRequestCreate,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    return {
        "status": "SUBMITTED",
        "requester_id": current_user.id,
        "session_id": payload.session_id,
        "reason": payload.reason,
    }


# Policy 7: CRs and faculty can report issues; general students cannot report directly
@router.post(
    "/issues",
    status_code=status.HTTP_201_CREATED,
    summary="Report Classroom/Schedule Issue",
    description="CRs and faculty can report room or scheduling issues.",
    dependencies=[Depends(PermissionGuard(Permission.ISSUE_REPORT_CREATE))],
)
async def report_issue(
    payload: IssueReportCreate,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    return {
        "status": "REPORTED",
        "reporter_id": current_user.id,
        "reporter_role": current_user.role.value,
        "room_id": payload.room_id,
        "description": payload.description,
    }


# Policy 8: Mentors have access ONLY to explicitly authorized mentees
@router.get(
    "/mentors/mentees",
    summary="View Assigned Mentees",
    description="Mentors can access records only for students explicitly assigned to them.",
    dependencies=[Depends(PermissionGuard(Permission.MENTEE_VIEW))],
)
async def view_assigned_mentees(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[dict]:
    stmt = (
        select(MentorAssignment)
        .where(
            MentorAssignment.mentor_user_id == current_user.id,
            MentorAssignment.is_active == True,  # noqa: E712
        )
    )
    result = await db.execute(stmt)
    assignments = result.scalars().all()

    return [
        {
            "assignment_id": a.id,
            "mentor_id": a.mentor_user_id,
            "student_id": a.student_user_id,
        }
        for a in assignments
    ]
