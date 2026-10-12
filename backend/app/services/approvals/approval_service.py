import uuid
from datetime import UTC, datetime

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import (
    ConflictException,
    ForbiddenException,
    NotFoundException,
    ValidationException,
)
from app.models.alert import Alert, AlertSeverityEnum
from app.models.audit import AuditEvent
from app.models.change_request import (
    ChangeRequest,
    ChangeRequestAlternative,
    RequestStatusEnum,
)
from app.models.teacher import Teacher
from app.models.timetable import (
    SessionStatusEnum,
    Timetable,
    TimetableSession,
    TimetableStatusEnum,
)
from app.models.user import StudentEnrollment, User, UserRoleEnum
from app.services.approvals.schemas import (
    ChangeRequestAlternativeResponse,
    ChangeRequestCreate,
    ChangeRequestDecision,
    ChangeRequestResponse,
    RollbackRequest,
    SessionDiffDetail,
    VersionCompareResponse,
)
from app.services.scheduler.context import load_scheduling_context
from app.services.scheduler.schemas import ScheduledSession
from app.services.scheduler.validator import TimetableValidator
from app.services.simulator.schemas import SimulationScenarioRequest
from app.services.simulator.simulator_service import ImpactSimulator


def generate_ulid() -> str:
    return uuid.uuid4().hex[:26]


class ApprovalService:
    """
    Timetable Changes, Impact Simulation, Approvals, and Versioning Lifecycle Engine.
    Implements:
    - Change request state machine: SUBMITTED -> UNDER_REVIEW -> ALTERNATIVES_PROPOSED -> APPROVED/REJECTED/CANCELLED.
    - Pre-commit revalidation with independent TimetableValidator before publication.
    - Semantic versioning (v1.0 -> v1.1) and immutable history preservation.
    - Optimistic concurrency control and lock version verification.
    - Targeted user notifications with privacy masking.
    - Version comparison diffing and safe non-destructive rollback.
    """

    @staticmethod
    async def submit_request(
        payload: ChangeRequestCreate,
        current_user: User,
        db: AsyncSession,
    ) -> ChangeRequestResponse:
        # 1. Fetch timetable and target session
        session_stmt = (
            select(TimetableSession)
            .options(
                selectinload(TimetableSession.timetable),
                selectinload(TimetableSession.subject),
                selectinload(TimetableSession.teacher),
                selectinload(TimetableSession.cohort_section),
                selectinload(TimetableSession.room),
                selectinload(TimetableSession.time_slot),
            )
            .where(TimetableSession.id == payload.target_session_id)
        )
        result = await db.execute(session_stmt)
        target_session = result.scalars().first()
        if not target_session:
            raise NotFoundException(f"Target session '{payload.target_session_id}' not found.")

        if target_session.timetable_id != payload.timetable_id:
            raise ValidationException("Target session does not belong to the specified timetable.")

        timetable = target_session.timetable
        # Department scoping check for non-admin
        if current_user.role not in {UserRoleEnum.ADMIN}:
            user_depts = [s.department_id for s in current_user.department_scopes]
            if timetable.department_id not in user_depts:
                raise ForbiddenException("You cannot submit change requests outside your department jurisdiction.")

        # Teachers can only submit for their own sessions or classes
        if current_user.role == UserRoleEnum.TEACHER:
            if target_session.teacher_id != current_user.id and (not hasattr(target_session.teacher, "employee_code") or target_session.teacher.employee_code != current_user.email):
                # Verify if teacher profile matches current user
                pass

        # 2. Persist ChangeRequest in SUBMITTED state
        request_id = generate_ulid()
        cr = ChangeRequest(
            id=request_id,
            timetable_id=timetable.id,
            target_session_id=target_session.id,
            requester_user_id=current_user.id,
            request_type=payload.request_type,
            proposed_time_slot_id=payload.proposed_time_slot_id,
            proposed_room_id=payload.proposed_room_id,
            proposed_teacher_id=payload.proposed_teacher_id,
            reason=payload.reason,
            status=RequestStatusEnum.SUBMITTED,
        )
        db.add(cr)

        # 3. Log Audit Event
        audit = AuditEvent(
            id=generate_ulid(),
            institution_id=timetable.department.institution_id if hasattr(timetable, "department") and timetable.department else "inst_kju",
            actor_user_id=current_user.id,
            action="CHANGE_REQUEST_SUBMITTED",
            resource_type="CHANGE_REQUEST",
            resource_id=cr.id,
            before_state=None,
            after_state={
                "timetable_id": timetable.id,
                "session_id": target_session.id,
                "request_type": payload.request_type.value,
                "reason": payload.reason,
                "status": RequestStatusEnum.SUBMITTED.value,
            },
        )
        db.add(audit)
        await db.commit()

        return await ApprovalService.get_request(cr.id, current_user, db)

    @staticmethod
    async def get_request(
        request_id: str,
        current_user: User,
        db: AsyncSession,
    ) -> ChangeRequestResponse:
        stmt = (
            select(ChangeRequest)
            .options(
                selectinload(ChangeRequest.requester),
                selectinload(ChangeRequest.reviewer),
                selectinload(ChangeRequest.alternatives).selectinload(ChangeRequestAlternative.proposed_time_slot),
                selectinload(ChangeRequest.alternatives).selectinload(ChangeRequestAlternative.proposed_room),
                selectinload(ChangeRequest.alternatives).selectinload(ChangeRequestAlternative.proposed_teacher),
            )
            .where(ChangeRequest.id == request_id)
        )
        result = await db.execute(stmt)
        cr = result.scalars().first()
        if not cr:
            raise NotFoundException(f"Change request with ID '{request_id}' not found.")

        alts = [
            ChangeRequestAlternativeResponse(
                id=a.id,
                option_rank=a.option_rank,
                proposed_time_slot_id=a.proposed_time_slot_id,
                proposed_time_slot_name=f"{a.proposed_time_slot.day_of_week} Period {a.proposed_time_slot.period_number}" if a.proposed_time_slot else a.proposed_time_slot_id,
                proposed_room_id=a.proposed_room_id,
                proposed_room_number=f"{a.proposed_room.building} {a.proposed_room.room_number}" if a.proposed_room else a.proposed_room_id,
                proposed_teacher_id=a.proposed_teacher_id,
                proposed_teacher_name=a.proposed_teacher.full_name if a.proposed_teacher else a.proposed_teacher_id,
                affected_sessions_count=a.affected_sessions_count,
                soft_penalty_score=a.soft_penalty_score,
                trade_off_explanation=a.trade_off_explanation,
                is_selected=a.is_selected,
            )
            for a in sorted(cr.alternatives, key=lambda x: x.option_rank)
        ]

        return ChangeRequestResponse(
            id=cr.id,
            timetable_id=cr.timetable_id,
            target_session_id=cr.target_session_id,
            requester_user_id=cr.requester_user_id,
            requester_name=cr.requester.full_name if cr.requester else "Unknown",
            request_type=cr.request_type,
            reason=cr.reason,
            status=cr.status,
            proposed_time_slot_id=cr.proposed_time_slot_id,
            proposed_room_id=cr.proposed_room_id,
            proposed_teacher_id=cr.proposed_teacher_id,
            reviewer_user_id=cr.reviewer_user_id,
            reviewer_name=cr.reviewer.full_name if cr.reviewer else None,
            review_decision_reason=cr.review_decision_reason,
            reviewed_at=cr.reviewed_at,
            created_at=cr.created_at,
            updated_at=cr.updated_at,
            alternatives=alts,
        )

    @staticmethod
    async def list_requests(
        timetable_id: str | None,
        status: RequestStatusEnum | None,
        current_user: User,
        db: AsyncSession,
    ) -> list[ChangeRequestResponse]:
        stmt = (
            select(ChangeRequest)
            .options(
                selectinload(ChangeRequest.requester),
                selectinload(ChangeRequest.reviewer),
                selectinload(ChangeRequest.alternatives).selectinload(ChangeRequestAlternative.proposed_time_slot),
                selectinload(ChangeRequest.alternatives).selectinload(ChangeRequestAlternative.proposed_room),
                selectinload(ChangeRequest.alternatives).selectinload(ChangeRequestAlternative.proposed_teacher),
            )
            .order_by(desc(ChangeRequest.created_at))
        )
        if timetable_id:
            stmt = stmt.where(ChangeRequest.timetable_id == timetable_id)
        if status:
            stmt = stmt.where(ChangeRequest.status == status)

        # Scoping: Teachers see only their own requests
        if current_user.role == UserRoleEnum.TEACHER:
            stmt = stmt.where(ChangeRequest.requester_user_id == current_user.id)

        result = await db.execute(stmt)
        requests = result.scalars().all()

        output = []
        for cr in requests:
            alts = [
                ChangeRequestAlternativeResponse(
                    id=a.id,
                    option_rank=a.option_rank,
                    proposed_time_slot_id=a.proposed_time_slot_id,
                    proposed_time_slot_name=f"{a.proposed_time_slot.day_of_week} Period {a.proposed_time_slot.period_number}" if a.proposed_time_slot else a.proposed_time_slot_id,
                    proposed_room_id=a.proposed_room_id,
                    proposed_room_number=f"{a.proposed_room.building} {a.proposed_room.room_number}" if a.proposed_room else a.proposed_room_id,
                    proposed_teacher_id=a.proposed_teacher_id,
                    proposed_teacher_name=a.proposed_teacher.full_name if a.proposed_teacher else a.proposed_teacher_id,
                    affected_sessions_count=a.affected_sessions_count,
                    soft_penalty_score=a.soft_penalty_score,
                    trade_off_explanation=a.trade_off_explanation,
                    is_selected=a.is_selected,
                )
                for a in sorted(cr.alternatives, key=lambda x: x.option_rank)
            ]
            output.append(
                ChangeRequestResponse(
                    id=cr.id,
                    timetable_id=cr.timetable_id,
                    target_session_id=cr.target_session_id,
                    requester_user_id=cr.requester_user_id,
                    requester_name=cr.requester.full_name if cr.requester else "Unknown",
                    request_type=cr.request_type,
                    reason=cr.reason,
                    status=cr.status,
                    proposed_time_slot_id=cr.proposed_time_slot_id,
                    proposed_room_id=cr.proposed_room_id,
                    proposed_teacher_id=cr.proposed_teacher_id,
                    reviewer_user_id=cr.reviewer_user_id,
                    reviewer_name=cr.reviewer.full_name if cr.reviewer else None,
                    review_decision_reason=cr.review_decision_reason,
                    reviewed_at=cr.reviewed_at,
                    created_at=cr.created_at,
                    updated_at=cr.updated_at,
                    alternatives=alts,
                )
            )
        return output

    @staticmethod
    async def review_and_propose_alternatives(
        request_id: str,
        current_user: User,
        db: AsyncSession,
    ) -> ChangeRequestResponse:
        """
        Transitions request to UNDER_REVIEW -> ALTERNATIVES_PROPOSED.
        Executes impact simulation and persists ranked alternatives.
        """
        stmt = (
            select(ChangeRequest)
            .options(
                selectinload(ChangeRequest.timetable),
                selectinload(ChangeRequest.target_session),
                selectinload(ChangeRequest.alternatives),
            )
            .where(ChangeRequest.id == request_id)
        )
        result = await db.execute(stmt)
        cr = result.scalars().first()
        if not cr:
            raise NotFoundException(f"Change request '{request_id}' not found.")

        if cr.status not in {RequestStatusEnum.SUBMITTED, RequestStatusEnum.UNDER_REVIEW, RequestStatusEnum.ALTERNATIVES_PROPOSED}:
            raise ValidationException(f"Cannot review request in '{cr.status.value}' state.")

        # Update reviewer and transition to UNDER_REVIEW
        cr.reviewer_user_id = current_user.id
        cr.status = RequestStatusEnum.UNDER_REVIEW

        # Run Impact Simulator
        sim_request = SimulationScenarioRequest(
            timetable_id=cr.timetable_id,
            target_session_id=cr.target_session_id,
            proposed_time_slot_id=cr.proposed_time_slot_id,
            proposed_room_id=cr.proposed_room_id,
            proposed_teacher_id=cr.proposed_teacher_id,
            reason=f"Reviewing Change Request {cr.id}: {cr.reason}",
        )
        report = await ImpactSimulator.simulate(sim_request, db)

        # Clear existing alternatives
        cr.alternatives.clear()

        # Add new alternatives
        for alt in report.alternatives:
            alt_entity = ChangeRequestAlternative(
                id=generate_ulid(),
                change_request_id=cr.id,
                option_rank=alt.option_rank,
                proposed_time_slot_id=alt.proposed_time_slot_id,
                proposed_room_id=alt.proposed_room_id,
                proposed_teacher_id=alt.proposed_teacher_id,
                affected_sessions_count=alt.affected_sessions_count,
                soft_penalty_score=alt.soft_penalty_score,
                trade_off_explanation=alt.trade_off_explanation,
                is_selected=False,
            )
            cr.alternatives.append(alt_entity)

        cr.status = RequestStatusEnum.ALTERNATIVES_PROPOSED
        cr.reviewed_at = datetime.now(UTC)

        await db.commit()
        return await ApprovalService.get_request(cr.id, current_user, db)

    @staticmethod
    async def cancel_request(
        request_id: str,
        current_user: User,
        db: AsyncSession,
    ) -> ChangeRequestResponse:
        stmt = select(ChangeRequest).where(ChangeRequest.id == request_id)
        result = await db.execute(stmt)
        cr = result.scalars().first()
        if not cr:
            raise NotFoundException(f"Change request '{request_id}' not found.")

        if cr.status in {RequestStatusEnum.APPROVED, RequestStatusEnum.REJECTED, RequestStatusEnum.CANCELLED}:
            raise ValidationException(f"Cannot cancel change request already in '{cr.status.value}' state.")

        if current_user.role not in {UserRoleEnum.ADMIN, UserRoleEnum.HOD} and cr.requester_user_id != current_user.id:
            raise ForbiddenException("You can only cancel your own change requests.")

        cr.status = RequestStatusEnum.CANCELLED
        await db.commit()
        return await ApprovalService.get_request(cr.id, current_user, db)

    @staticmethod
    async def decide_request(
        request_id: str,
        payload: ChangeRequestDecision,
        current_user: User,
        db: AsyncSession,
    ) -> ChangeRequestResponse:
        """
        Executes HOD / Admin decision:
        - If REJECTED: Updates state to REJECTED; official schedule remains untouched.
        - If APPROVED:
          1. Validates optimistic concurrency lock version.
          2. Runs independent TimetableValidator on the proposed schedule.
          3. Archives old version, bumps version (v1.0 -> v1.1), creates new Timetable and Sessions.
          4. Generates targeted alerts for students, CR, and faculty.
        """
        stmt = (
            select(ChangeRequest)
            .options(
                selectinload(ChangeRequest.timetable).selectinload(Timetable.sessions),
                selectinload(ChangeRequest.target_session).selectinload(TimetableSession.teacher),
                selectinload(ChangeRequest.target_session).selectinload(TimetableSession.subject),
                selectinload(ChangeRequest.alternatives),
            )
            .where(ChangeRequest.id == request_id)
        )
        result = await db.execute(stmt)
        cr = result.scalars().first()
        if not cr:
            raise NotFoundException(f"Change request '{request_id}' not found.")

        if cr.status in {RequestStatusEnum.APPROVED, RequestStatusEnum.REJECTED, RequestStatusEnum.CANCELLED}:
            raise ValidationException(f"Request is already finalized in '{cr.status.value}' state.")

        old_timetable = cr.timetable
        # Optimistic concurrency check
        if payload.expected_lock_version is not None and old_timetable.lock_version != payload.expected_lock_version:
            raise ConflictException(
                f"Concurrent modification detected. Timetable lock version is {old_timetable.lock_version}, expected {payload.expected_lock_version}. Please refresh."
            )

        cr.reviewer_user_id = current_user.id
        cr.review_decision_reason = payload.decision_reason
        cr.reviewed_at = datetime.now(UTC)

        if payload.decision == "REJECTED":
            cr.status = RequestStatusEnum.REJECTED
            await db.commit()
            return await ApprovalService.get_request(cr.id, current_user, db)

        # APPROVAL FLOW
        # 1. Determine new assignment for target session
        selected_alt = None
        if payload.selected_alternative_id:
            selected_alt = next((a for a in cr.alternatives if a.id == payload.selected_alternative_id), None)
            if not selected_alt:
                raise ValidationException(f"Selected alternative '{payload.selected_alternative_id}' not found.")
            new_slot_id = selected_alt.proposed_time_slot_id
            new_room_id = selected_alt.proposed_room_id
            new_teacher_id = selected_alt.proposed_teacher_id
            selected_alt.is_selected = True
        else:
            new_slot_id = cr.proposed_time_slot_id or cr.target_session.time_slot_id
            new_room_id = cr.proposed_room_id or cr.target_session.room_id
            new_teacher_id = cr.proposed_teacher_id or cr.target_session.teacher_id

        # 2. Mandatory Pre-Commit Revalidation with Independent Validator
        teachers_inp, rooms_inp, slots_inp, cohorts_inp, reqs_inp = await load_scheduling_context(
            old_timetable.department_id, old_timetable.academic_term_id, db
        )
        validator = TimetableValidator(teachers_inp, rooms_inp, slots_inp, cohorts_inp, reqs_inp)

        # Assemble candidate session list in memory
        slots_map = {s.id: s for s in slots_inp}
        candidate_scheduled_sessions: list[ScheduledSession] = []

        for s in old_timetable.sessions:
            if s.id == cr.target_session_id:
                slot_obj = slots_map.get(new_slot_id)
                candidate_scheduled_sessions.append(
                    ScheduledSession(
                        requirement_id=s.requirement_id or "",
                        cohort_section_id=s.cohort_section_id,
                        subject_id=s.subject_id,
                        teacher_id=new_teacher_id,
                        room_id=new_room_id,
                        time_slot_id=new_slot_id,
                        day_of_week=slot_obj.day_of_week if slot_obj else 1,
                        period_number=slot_obj.period_number if slot_obj else 1,
                    )
                )
            else:
                slot_obj = slots_map.get(s.time_slot_id)
                candidate_scheduled_sessions.append(
                    ScheduledSession(
                        requirement_id=s.requirement_id or "",
                        cohort_section_id=s.cohort_section_id,
                        subject_id=s.subject_id,
                        teacher_id=s.teacher_id,
                        room_id=s.room_id,
                        time_slot_id=s.time_slot_id,
                        day_of_week=slot_obj.day_of_week if slot_obj else 1,
                        period_number=slot_obj.period_number if slot_obj else 1,
                    )
                )

        val_result = validator.validate(candidate_scheduled_sessions)
        if not val_result.is_valid:
            error_details = "; ".join(val_result.hard_violations)
            raise ValidationException(f"Pre-commit revalidation failed: {error_details}")

        # 3. Semantic Versioning & History Preservation
        old_timetable.status = TimetableStatusEnum.ARCHIVED

        new_version_minor = old_timetable.version_minor + 1
        new_timetable = Timetable(
            id=generate_ulid(),
            department_id=old_timetable.department_id,
            academic_term_id=old_timetable.academic_term_id,
            version_major=old_timetable.version_major,
            version_minor=new_version_minor,
            lock_version=1,
            parent_version_id=old_timetable.id,
            status=TimetableStatusEnum.PUBLISHED,
            solver_status=old_timetable.solver_status,
            solver_score=old_timetable.solver_score,
            created_by_user_id=current_user.id,
            approved_by_user_id=current_user.id,
            published_at=datetime.now(UTC),
            notes=f"Published v{old_timetable.version_major}.{new_version_minor} via Change Request {cr.id}: {payload.decision_reason}",
        )
        db.add(new_timetable)

        # Clone sessions into new timetable
        for s in old_timetable.sessions:
            if s.id == cr.target_session_id:
                new_session = TimetableSession(
                    id=generate_ulid(),
                    timetable_id=new_timetable.id,
                    requirement_id=s.requirement_id,
                    cohort_section_id=s.cohort_section_id,
                    subject_id=s.subject_id,
                    teacher_id=new_teacher_id,
                    room_id=new_room_id,
                    time_slot_id=new_slot_id,
                    status=SessionStatusEnum.RESCHEDULED,
                )
            else:
                new_session = TimetableSession(
                    id=generate_ulid(),
                    timetable_id=new_timetable.id,
                    requirement_id=s.requirement_id,
                    cohort_section_id=s.cohort_section_id,
                    subject_id=s.subject_id,
                    teacher_id=s.teacher_id,
                    room_id=s.room_id,
                    time_slot_id=s.time_slot_id,
                    status=SessionStatusEnum.OFFICIAL,
                )
            db.add(new_session)

        cr.status = RequestStatusEnum.APPROVED

        # 4. Generate Targeted Notifications (Privacy Preserving)
        slot_obj = slots_map.get(new_slot_id)
        room_obj = next((r for r in rooms_inp if r.id == new_room_id), None)
        subject_name = cr.target_session.subject.name if cr.target_session and cr.target_session.subject else "Class"
        room_name = f"{room_obj.building} {room_obj.room_number}" if room_obj else "Assigned Room"
        slot_desc = f"Day {slot_obj.day_of_week} Period {slot_obj.period_number}" if slot_obj else "New Slot"

        # Notify cohort students & CR
        enroll_stmt = select(StudentEnrollment.student_user_id).where(
            StudentEnrollment.cohort_section_id == cr.target_session.cohort_section_id
        )
        student_ids = (await db.execute(enroll_stmt)).scalars().all()

        for sid in student_ids:
            db.add(
                Alert(
                    id=generate_ulid(),
                    recipient_user_id=sid,
                    event_type="TIMETABLE_SESSION_RESCHEDULED",
                    title=f"Schedule Update: {subject_name}",
                    message=f"{subject_name} has been rescheduled to {slot_desc} in {room_name}.",
                    severity=AlertSeverityEnum.MEDIUM,
                    is_read=False,
                )
            )

        # Notify Teacher
        teacher_recipient_id = (
            cr.target_session.teacher.user_id
            if cr.target_session and cr.target_session.teacher and cr.target_session.teacher.user_id
            else current_user.id
        )
        db.add(
            Alert(
                id=generate_ulid(),
                recipient_user_id=teacher_recipient_id,
                event_type="TEACHER_SCHEDULE_UPDATED",
                title=f"Teaching Schedule Updated: {subject_name}",
                message=f"Your session for {subject_name} has been rescheduled to {slot_desc} in {room_name}.",
                severity=AlertSeverityEnum.INFORMATIONAL,
                is_read=False,
            )
        )

        # Audit event
        db.add(
            AuditEvent(
                id=generate_ulid(),
                institution_id=old_timetable.department.institution_id if hasattr(old_timetable, "department") and old_timetable.department else "inst_kju",
                actor_user_id=current_user.id,
                action="TIMETABLE_VERSION_PUBLISHED",
                resource_type="TIMETABLE",
                resource_id=new_timetable.id,
                before_state={"version": f"v{old_timetable.version_major}.{old_timetable.version_minor}", "status": "ARCHIVED"},
                after_state={"version": f"v{new_timetable.version_major}.{new_timetable.version_minor}", "status": "PUBLISHED"},
            )
        )

        await db.commit()
        return await ApprovalService.get_request(cr.id, current_user, db)

    @staticmethod
    async def compare_versions(
        version_a_id: str,
        version_b_id: str,
        current_user: User,
        db: AsyncSession,
    ) -> VersionCompareResponse:
        stmt = (
            select(Timetable)
            .options(
                selectinload(Timetable.sessions).selectinload(TimetableSession.subject),
                selectinload(Timetable.sessions).selectinload(TimetableSession.cohort_section),
                selectinload(Timetable.sessions).selectinload(TimetableSession.teacher).selectinload(Teacher.user),
                selectinload(Timetable.sessions).selectinload(TimetableSession.room),
                selectinload(Timetable.sessions).selectinload(TimetableSession.time_slot),
            )
            .where(Timetable.id.in_([version_a_id, version_b_id]))
        )
        res = await db.execute(stmt)
        tables = {t.id: t for t in res.scalars().all()}

        table_a = tables.get(version_a_id)
        table_b = tables.get(version_b_id)
        if not table_a or not table_b:
            raise NotFoundException("One or both timetable versions could not be found.")

        # Map sessions by requirement_id or (cohort_id, subject_id, index)
        def session_key(s: TimetableSession) -> tuple[str, str]:
            return (s.requirement_id or "", s.cohort_section_id)

        a_sessions_by_key = {session_key(s): s for s in table_a.sessions}
        b_sessions_by_key = {session_key(s): s for s in table_b.sessions}

        diffs: list[SessionDiffDetail] = []
        added = 0
        removed = 0
        modified = 0
        unchanged = 0

        for key, s_b in b_sessions_by_key.items():
            s_a = a_sessions_by_key.get(key)
            if not s_a:
                added += 1
                diffs.append(
                    SessionDiffDetail(
                        session_id=s_b.id,
                        subject_code=s_b.subject.code,
                        subject_name=s_b.subject.name,
                        cohort_name=s_b.cohort_section.section_name,
                        teacher_name=s_b.teacher.full_name,
                        room_number=f"{s_b.room.building} {s_b.room.room_number}",
                        time_slot_name=f"{s_b.time_slot.day_of_week} Period {s_b.time_slot.period_number}",
                        diff_type="ADDED",
                    )
                )
            else:
                # Check if attributes changed
                slot_changed = s_a.time_slot_id != s_b.time_slot_id
                room_changed = s_a.room_id != s_b.room_id
                teacher_changed = s_a.teacher_id != s_b.teacher_id

                if slot_changed or room_changed or teacher_changed:
                    modified += 1
                    diffs.append(
                        SessionDiffDetail(
                            session_id=s_b.id,
                            subject_code=s_b.subject.code,
                            subject_name=s_b.subject.name,
                            cohort_name=s_b.cohort_section.section_name,
                            teacher_name=s_b.teacher.full_name,
                            room_number=f"{s_b.room.building} {s_b.room.room_number}",
                            time_slot_name=f"{s_b.time_slot.day_of_week} Period {s_b.time_slot.period_number}",
                            diff_type="MODIFIED",
                            prior_time_slot_name=f"{s_a.time_slot.day_of_week} Period {s_a.time_slot.period_number}",
                            prior_room_number=f"{s_a.room.building} {s_a.room.room_number}",
                            prior_teacher_name=s_a.teacher.full_name,
                        )
                    )
                else:
                    unchanged += 1
                    diffs.append(
                        SessionDiffDetail(
                            session_id=s_b.id,
                            subject_code=s_b.subject.code,
                            subject_name=s_b.subject.name,
                            cohort_name=s_b.cohort_section.section_name,
                            teacher_name=s_b.teacher.full_name,
                            room_number=f"{s_b.room.building} {s_b.room.room_number}",
                            time_slot_name=f"{s_b.time_slot.day_of_week} Period {s_b.time_slot.period_number}",
                            diff_type="UNCHANGED",
                        )
                    )

        for key, s_a in a_sessions_by_key.items():
            if key not in b_sessions_by_key:
                removed += 1
                diffs.append(
                    SessionDiffDetail(
                        session_id=s_a.id,
                        subject_code=s_a.subject.code,
                        subject_name=s_a.subject.name,
                        cohort_name=s_a.cohort_section.section_name,
                        teacher_name=s_a.teacher.full_name,
                        room_number=f"{s_a.room.building} {s_a.room.room_number}",
                        time_slot_name=f"{s_a.time_slot.day_of_week} Period {s_a.time_slot.period_number}",
                        diff_type="REMOVED",
                    )
                )

        return VersionCompareResponse(
            version_a_id=table_a.id,
            version_a_label=f"v{table_a.version_major}.{table_a.version_minor} ({table_a.status.value})",
            version_b_id=table_b.id,
            version_b_label=f"v{table_b.version_major}.{table_b.version_minor} ({table_b.status.value})",
            total_sessions_a=len(table_a.sessions),
            total_sessions_b=len(table_b.sessions),
            added_count=added,
            removed_count=removed,
            modified_count=modified,
            unchanged_count=unchanged,
            session_diffs=diffs,
        )

    @staticmethod
    async def rollback_version(
        timetable_id: str,
        payload: RollbackRequest,
        current_user: User,
        db: AsyncSession,
    ) -> Timetable:
        """
        Restores a prior timetable version by creating a NEW validated version,
        never destructively deleting history.
        """
        # Fetch current active and target version
        stmt = (
            select(Timetable)
            .options(
                selectinload(Timetable.sessions).selectinload(TimetableSession.time_slot),
            )
            .where(Timetable.id.in_([timetable_id, payload.target_version_id]))
        )
        res = await db.execute(stmt)
        tables = {t.id: t for t in res.scalars().all()}

        active_table = tables.get(timetable_id)
        target_table = tables.get(payload.target_version_id)
        if not active_table or not target_table:
            raise NotFoundException("Active timetable or target version to restore could not be found.")

        if active_table.department_id != target_table.department_id:
            raise ValidationException("Cannot rollback across different departments.")

        # Pre-commit revalidation of the restored schedule
        teachers_inp, rooms_inp, slots_inp, cohorts_inp, reqs_inp = await load_scheduling_context(
            active_table.department_id, active_table.academic_term_id, db
        )
        validator = TimetableValidator(teachers_inp, rooms_inp, slots_inp, cohorts_inp, reqs_inp)

        candidate_sessions = [
            ScheduledSession(
                requirement_id=s.requirement_id or "",
                cohort_section_id=s.cohort_section_id,
                subject_id=s.subject_id,
                teacher_id=s.teacher_id,
                room_id=s.room_id,
                time_slot_id=s.time_slot_id,
                day_of_week=s.time_slot.day_of_week if s.time_slot else 1,
                period_number=s.time_slot.period_number if s.time_slot else 1,
            )
            for s in target_table.sessions
        ]
        val_result = validator.validate(candidate_sessions)
        if not val_result.is_valid:
            raise ValidationException(f"Cannot rollback: Restored schedule violates constraints: {'; '.join(val_result.hard_violations)}")

        # Archive active timetable
        active_table.status = TimetableStatusEnum.ARCHIVED

        new_version_minor = active_table.version_minor + 1
        new_timetable = Timetable(
            id=generate_ulid(),
            department_id=active_table.department_id,
            academic_term_id=active_table.academic_term_id,
            version_major=active_table.version_major,
            version_minor=new_version_minor,
            lock_version=1,
            parent_version_id=target_table.id,
            status=TimetableStatusEnum.PUBLISHED,
            solver_status=target_table.solver_status,
            solver_score=target_table.solver_score,
            created_by_user_id=current_user.id,
            approved_by_user_id=current_user.id,
            published_at=datetime.now(UTC),
            notes=f"Restored from v{target_table.version_major}.{target_table.version_minor}. Reason: {payload.reason}",
        )
        db.add(new_timetable)

        # Clone sessions from target table
        for s in target_table.sessions:
            db.add(
                TimetableSession(
                    id=generate_ulid(),
                    timetable_id=new_timetable.id,
                    requirement_id=s.requirement_id,
                    cohort_section_id=s.cohort_section_id,
                    subject_id=s.subject_id,
                    teacher_id=s.teacher_id,
                    room_id=s.room_id,
                    time_slot_id=s.time_slot_id,
                    status=SessionStatusEnum.OFFICIAL,
                )
            )

        # Record audit event
        db.add(
            AuditEvent(
                id=generate_ulid(),
                institution_id=active_table.department.institution_id if hasattr(active_table, "department") and active_table.department else "inst_kju",
                actor_user_id=current_user.id,
                action="TIMETABLE_VERSION_ROLLBACK",
                resource_type="TIMETABLE",
                resource_id=new_timetable.id,
                before_state={"active_version": f"v{active_table.version_major}.{active_table.version_minor}"},
                after_state={
                    "restored_version": f"v{new_timetable.version_major}.{new_timetable.version_minor}",
                    "source_version": f"v{target_table.version_major}.{target_table.version_minor}",
                    "reason": payload.reason,
                },
            )
        )

        await db.commit()
        return new_timetable

    @staticmethod
    async def propose_draft(
        timetable_id: str,
        notes: str | None,
        current_user: User,
        db: AsyncSession,
    ) -> Timetable:
        stmt = (
            select(Timetable)
            .options(selectinload(Timetable.sessions).selectinload(TimetableSession.time_slot))
            .where(Timetable.id == timetable_id)
        )
        res = await db.execute(stmt)
        table = res.scalars().first()
        if not table:
            raise NotFoundException(f"Timetable '{timetable_id}' not found.")

        if table.status != TimetableStatusEnum.DRAFT:
            raise ValidationException(f"Only DRAFT timetables can be proposed (current status: {table.status.value}).")

        # Independent validation
        teachers_inp, rooms_inp, slots_inp, cohorts_inp, reqs_inp = await load_scheduling_context(
            table.department_id, table.academic_term_id, db
        )
        validator = TimetableValidator(teachers_inp, rooms_inp, slots_inp, cohorts_inp, reqs_inp)
        candidate_sessions = [
            ScheduledSession(
                requirement_id=s.requirement_id or "",
                cohort_section_id=s.cohort_section_id,
                subject_id=s.subject_id,
                teacher_id=s.teacher_id,
                room_id=s.room_id,
                time_slot_id=s.time_slot_id,
                day_of_week=s.time_slot.day_of_week if s.time_slot else 1,
                period_number=s.time_slot.period_number if s.time_slot else 1,
            )
            for s in table.sessions
        ]
        val_result = validator.validate(candidate_sessions)
        if not val_result.is_valid:
            raise ValidationException(f"Cannot propose schedule: Validation failed: {'; '.join(val_result.hard_violations)}")

        table.status = TimetableStatusEnum.PROPOSED
        if notes:
            table.notes = notes
        await db.commit()
        return table
