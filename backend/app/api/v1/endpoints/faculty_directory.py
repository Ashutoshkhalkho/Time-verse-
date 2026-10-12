from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.exceptions import ForbiddenException, ValidationException
from app.db.session import get_db_session
from app.models.faculty_directory import ProfileStatusEnum
from app.models.user import User, UserRoleEnum
from app.schemas.faculty_directory import (
    CSVCommitRequest,
    CSVCommitResponse,
    CSVPreviewResponse,
    FacultyMemberArchiveRequest,
    FacultyMemberCreate,
    FacultyMemberResponse,
    FacultyMemberUpdate,
    FacultyMemberVerifyRequest,
)
from app.services.faculty_directory.faculty_service import FacultyDirectoryService

router = APIRouter(prefix="/faculty-directory", tags=["Faculty Directory"])

ADMIN_ROLES = {UserRoleEnum.ADMIN, UserRoleEnum.HOD, UserRoleEnum.COORDINATOR}


def require_directory_admin(user: User) -> None:
    if user.role not in ADMIN_ROLES:
        raise ForbiddenException(
            f"Role '{user.role.value}' lacks administrative authority to modify faculty directory records."
        )


@router.get("", response_model=list[FacultyMemberResponse])
async def list_faculty_members(
    search: str | None = Query(default=None, description="Case-insensitive search by name, designation, or specialisation"),
    designation: str | None = Query(default=None, description="Filter by designation or 'UNVERIFIED'"),
    profile_status: ProfileStatusEnum | None = Query(default=None, description="Filter by profile status"),
    is_verified: bool | None = Query(default=None, description="Filter by verification state"),
    include_archived: bool = Query(default=False, description="Include archived faculty profiles"),
    sort_by: str = Query(default="name_asc", description="Sort option: name_asc, name_desc, verified_first, created_desc"),
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[AsyncSession, Depends(get_db_session)] = None,
) -> list[FacultyMemberResponse]:
    """
    Returns faculty directory records for Department of Professional Management Studies (DPMS),
    Kristu Jayanti University (KJU). Supports case-insensitive search, status/designation filters,
    and alphabetical sorting with title-prefix handling.
    """
    return await FacultyDirectoryService.list_members(
        db=db,
        search=search,
        designation=designation,
        profile_status=profile_status,
        is_verified=is_verified,
        include_archived=include_archived,
        sort_by=sort_by,
    )


@router.get("/designations", response_model=list[str])
async def list_available_designations(
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[AsyncSession, Depends(get_db_session)] = None,
) -> list[str]:
    """Returns unique verified designations currently present in the directory."""
    members = await FacultyDirectoryService.list_members(db=db, include_archived=True)
    desigs = sorted({m.designation for m in members if m.designation})
    return desigs


@router.get("/{member_id}", response_model=FacultyMemberResponse)
async def get_faculty_member_details(
    member_id: str,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[AsyncSession, Depends(get_db_session)] = None,
) -> FacultyMemberResponse:
    """Returns detailed profile for a specific faculty member, including missing field indicators."""
    return await FacultyDirectoryService.get_member(db=db, member_id=member_id)


@router.post("", response_model=FacultyMemberResponse, status_code=status.HTTP_201_CREATED)
async def create_faculty_member(
    payload: FacultyMemberCreate,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[AsyncSession, Depends(get_db_session)] = None,
) -> FacultyMemberResponse:
    """Administrator only: Add a new faculty member record."""
    require_directory_admin(current_user)
    return await FacultyDirectoryService.create_member(db=db, data=payload, current_user=current_user)


@router.put("/{member_id}", response_model=FacultyMemberResponse)
async def update_faculty_member(
    member_id: str,
    payload: FacultyMemberUpdate,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[AsyncSession, Depends(get_db_session)] = None,
) -> FacultyMemberResponse:
    """Administrator only: Update an existing faculty member record."""
    require_directory_admin(current_user)
    return await FacultyDirectoryService.update_member(
        db=db, member_id=member_id, data=payload, current_user=current_user
    )


@router.post("/{member_id}/verify", response_model=FacultyMemberResponse)
async def verify_faculty_member(
    member_id: str,
    payload: FacultyMemberVerifyRequest,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[AsyncSession, Depends(get_db_session)] = None,
) -> FacultyMemberResponse:
    """
    Administrator only: Formally mark a faculty profile as verified after audit.
    Requires explicit administrative attestation and audit statement.
    """
    require_directory_admin(current_user)
    return await FacultyDirectoryService.verify_member(
        db=db, member_id=member_id, data=payload, current_user=current_user
    )


@router.post("/{member_id}/archive", response_model=FacultyMemberResponse)
async def archive_faculty_member(
    member_id: str,
    payload: FacultyMemberArchiveRequest,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[AsyncSession, Depends(get_db_session)] = None,
) -> FacultyMemberResponse:
    """Administrator only: Soft-archive a faculty record with confirmation."""
    require_directory_admin(current_user)
    return await FacultyDirectoryService.archive_member(
        db=db, member_id=member_id, current_user=current_user, reason=payload.reason
    )


@router.post("/{member_id}/restore", response_model=FacultyMemberResponse)
async def restore_faculty_member(
    member_id: str,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[AsyncSession, Depends(get_db_session)] = None,
) -> FacultyMemberResponse:
    """Administrator only: Restore a soft-archived faculty record."""
    require_directory_admin(current_user)
    return await FacultyDirectoryService.restore_member(
        db=db, member_id=member_id, current_user=current_user
    )


@router.post("/preview-csv", response_model=CSVPreviewResponse)
async def preview_csv_upload(
    file: UploadFile | None = File(default=None),
    raw_csv_text: str | None = Form(default=None),
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[AsyncSession, Depends(get_db_session)] = None,
) -> CSVPreviewResponse:
    """
    Administrator only: Previews CSV import before committing.
    Validates headers, rows, unmapped columns, and potential duplicates (e.g. Ms. C. Shilpa Rao vs Ms. Shilpa Rao).
    """
    require_directory_admin(current_user)

    csv_content = ""
    if file:
        content_bytes = await file.read()
        try:
            csv_content = content_bytes.decode("utf-8-sig")
        except UnicodeDecodeError:
            try:
                csv_content = content_bytes.decode("latin-1")
            except Exception as e:
                raise ValidationException(f"Failed to decode CSV file: {str(e)}")
    elif raw_csv_text:
        csv_content = raw_csv_text
    else:
        raise ValidationException("Please upload a CSV file or provide CSV text content.")

    return await FacultyDirectoryService.preview_csv(db=db, csv_content=csv_content)


@router.post("/commit-csv", response_model=CSVCommitResponse)
async def commit_csv_import(
    payload: CSVCommitRequest,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[AsyncSession, Depends(get_db_session)] = None,
) -> CSVCommitResponse:
    """
    Administrator only: Executes verified CSV import with explicit confirmation.
    Idempotent: prevents duplicate records and protects verified administrative records.
    """
    require_directory_admin(current_user)
    return await FacultyDirectoryService.commit_csv(
        db=db, request=payload, current_user=current_user
    )


@router.post("/seed-initial")
async def seed_initial_records(
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[AsyncSession, Depends(get_db_session)] = None,
) -> dict[str, Any]:
    """
    Administrator only: Idempotently seeds the 26 DPMS faculty records.
    """
    require_directory_admin(current_user)
    res = await FacultyDirectoryService.seed_initial_records(db=db)
    return {"status": "success", "counts": res}
