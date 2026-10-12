from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import PermissionGuard, get_current_user
from app.core.permissions import Permission
from app.db.session import get_db_session
from app.models.cohort import CohortSection
from app.models.curriculum import Subject, SubjectRequirement, SubjectTypeEnum
from app.models.infrastructure import Room, RoomTypeEnum
from app.models.teacher import Teacher
from app.models.user import User, UserRoleEnum
from app.services.audit.audit_service import record_audit_event
from app.services.importer.importer_service import ImporterService
from app.services.importer.schemas import (
    EntityImportType,
    ImportCommitRequest,
    ImportCommitResponse,
    ImportPreviewResponse,
)

router = APIRouter(prefix="/import", tags=["Data Ingestion & Validation"])


@router.get(
    "/templates/{entity_type}",
    summary="Download Import Template (CSV/XLSX)",
    dependencies=[Depends(PermissionGuard(Permission.DATA_IMPORT))],
)
async def download_template(
    entity_type: EntityImportType,
    file_format: str = Query("csv", regex="^(csv|xlsx)$"),
) -> Response:
    """
    Downloads standard CSV or Excel template pre-populated with example valid rows.
    """
    content, filename, media_type = ImporterService.generate_template(entity_type, file_format)
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.post(
    "/preview",
    response_model=ImportPreviewResponse,
    summary="Preflight Validate Ingestion File",
    dependencies=[Depends(PermissionGuard(Permission.DATA_IMPORT))],
)
async def preview_import_file(
    entity_type: EntityImportType,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db_session),
) -> ImportPreviewResponse:
    """
    Parses and runs preflight row-level validation without modifying the database.
    Detects missing fields, duplicate codes, invalid constraints, and unknown foreign keys.
    """
    content = await file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty.")

    return await ImporterService.parse_and_validate(
        content=content,
        filename=file.filename or "uploaded.csv",
        entity_type=entity_type,
        db_session=db,
    )


@router.post(
    "/commit",
    response_model=ImportCommitResponse,
    summary="Commit Validated Records into Database",
    dependencies=[Depends(PermissionGuard(Permission.DATA_IMPORT))],
)
async def commit_import_records(
    request: ImportCommitRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> ImportCommitResponse:
    """
    Commits validated preflight records into the production database with audit tracking.
    """
    committed_count = 0

    if request.entity_type == EntityImportType.ROOMS:
        for r in request.records:
            if not r.get("_is_valid", True):
                continue
            room = Room(
                id=f"rm_{r['building'][:3].lower()}_{r['room_number'].lower()}",
                institution_id="inst_01",
                building=r["building"],
                room_number=str(r["room_number"]),
                capacity=int(r["capacity"]),
                room_type=RoomTypeEnum(r["room_type"]),
                equipment=[],
                is_active=True,
            )
            db.add(room)
            committed_count += 1

    elif request.entity_type == EntityImportType.SUBJECTS:
        for s in request.records:
            if not s.get("_is_valid", True):
                continue
            subj = Subject(
                id=f"sub_{s['code'].lower()}",
                department_id=request.department_id or "dept_cs",
                code=s["code"],
                name=s["name"],
                credits=int(s["credits"]),
                subject_type=SubjectTypeEnum(s["subject_type"]),
                required_room_type=RoomTypeEnum(s["required_room_type"]),
                is_active=True,
            )
            db.add(subj)
            committed_count += 1

    elif request.entity_type == EntityImportType.TEACHERS:
        dept_id = request.department_id or "dept_cs"
        for t in request.records:
            if not t.get("_is_valid", True):
                continue
            email = str(t.get("email", "")).strip().lower()
            code = str(t.get("employee_code", "")).strip().upper()
            usr_stmt = select(User).where(User.email == email)
            usr = (await db.execute(usr_stmt)).scalars().first()
            if not usr:
                usr = User(
                    id=f"usr_tch_{code.lower()}",
                    institution_id="inst_01",
                    email=email,
                    hashed_password="$argon2id$v=19$m=65536,t=3,p=4$dummyhash",
                    full_name=t.get("full_name", code),
                    role=UserRoleEnum.TEACHER,
                    is_active=True,
                )
                db.add(usr)
                await db.flush()

            tch_stmt = select(Teacher).where(Teacher.employee_code == code)
            tch = (await db.execute(tch_stmt)).scalars().first()
            if not tch:
                teacher = Teacher(
                    id=f"tch_{code.lower()}",
                    user_id=usr.id,
                    department_id=dept_id,
                    employee_code=code,
                    max_hours_per_day=int(t.get("max_hours_per_day", 5)),
                    max_consecutive_hours=3,
                    max_weekly_hours=int(t.get("max_weekly_hours", 20)),
                )
                db.add(teacher)
                committed_count += 1

    elif request.entity_type == EntityImportType.REQUIREMENTS:
        for req in request.records:
            if not req.get("_is_valid", True):
                continue
            sec_name = str(req.get("section_name", "")).strip().upper()
            sub_code = str(req.get("subject_code", "")).strip().upper()
            emp_code = str(req.get("employee_code", "")).strip().upper()

            sec_res = await db.execute(select(CohortSection.id).where(CohortSection.section_name == sec_name))
            sec_id = sec_res.scalar_one_or_none()
            sub_res = await db.execute(select(Subject.id).where(Subject.code == sub_code))
            sub_id = sub_res.scalar_one_or_none()
            tch_res = await db.execute(select(Teacher.id).where(Teacher.employee_code == emp_code))
            tch_id = tch_res.scalar_one_or_none()

            if sec_id and sub_id and tch_id:
                req_obj = SubjectRequirement(
                    id=f"req_{sec_id}_{sub_id}",
                    cohort_section_id=sec_id,
                    subject_id=sub_id,
                    teacher_id=tch_id,
                    required_sessions_per_week=int(req.get("required_sessions_per_week", 4)),
                    duration_periods=1,
                    requires_consecutive_periods=False,
                )
                db.add(req_obj)
                committed_count += 1

    await db.commit()

    # Record Audit Event
    await record_audit_event(
        db=db,
        actor_user_id=current_user.id,
        action="DATA_IMPORT_COMMIT",
        resource_type=request.entity_type.value,
        resource_id="bulk_import",
        department_id=request.department_id,
        before_state={},
        after_state={"committed_records": committed_count, "entity_type": request.entity_type.value},
    )

    return ImportCommitResponse(
        entity_type=request.entity_type,
        committed_count=committed_count,
        message=f"Successfully imported {committed_count} {request.entity_type.value} records.",
    )
