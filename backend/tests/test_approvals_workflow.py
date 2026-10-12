import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.db.seed import DEFAULT_DEMO_PASSWORD, seed_demo_data
from app.db.session import AsyncSessionLocal
from app.models.timetable import TimetableSession


@pytest.fixture(scope="module", autouse=True)
async def seed_approvals_test_db():
    async with AsyncSessionLocal() as session:
        await seed_demo_data(session)


async def get_token(client: AsyncClient, email: str) -> str:
    res = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": DEFAULT_DEMO_PASSWORD},
    )
    assert res.status_code == 200
    return res.json()["tokens"]["access_token"]


@pytest.mark.asyncio
async def test_complete_change_request_lifecycle(client: AsyncClient):
    """
    Demonstrates full synthetic data lifecycle:
    Draft timetable -> validation -> proposal -> teacher request -> review & alternatives ->
    HOD approval -> pre-commit revalidation -> publication (v1.1).
    """
    coord_token = await get_token(client, "coord.cs@timewise.edu")
    teacher_token = await get_token(client, "teacher.sharma@timewise.edu")
    hod_token = await get_token(client, "hod.cs@timewise.edu")

    # 1. Coordinator generates draft timetable
    gen_res = await client.post(
        "/api/v1/timetables/generate",
        headers={"Authorization": f"Bearer {coord_token}"},
        json={
            "department_id": "dept_cs",
            "academic_term_id": "term_2026_odd",
            "time_limit_seconds": 15.0,
        },
    )
    assert gen_res.status_code == 200
    timetable_id = gen_res.json()["timetable_id"]

    # 2. Coordinator proposes draft timetable
    prop_res = await client.post(
        f"/api/v1/timetables/{timetable_id}/propose",
        headers={"Authorization": f"Bearer {coord_token}"},
    )
    assert prop_res.status_code == 200
    assert prop_res.json()["status"] == "PROPOSED"

    # Fetch a session to reschedule
    async with AsyncSessionLocal() as session:
        res = await session.execute(
            select(TimetableSession).where(TimetableSession.timetable_id == timetable_id)
        )
        target_session = res.scalars().first()
        target_session_id = target_session.id
        initial_slot = target_session.time_slot_id

    # 3. Teacher submits change request (Status -> SUBMITTED)
    req_res = await client.post(
        "/api/v1/approvals/requests",
        headers={"Authorization": f"Bearer {teacher_token}"},
        json={
            "timetable_id": timetable_id,
            "target_session_id": target_session_id,
            "request_type": "RESCHEDULE_SESSION",
            "reason": "Department research symposium conflict",
        },
    )
    assert req_res.status_code == 201
    req_data = req_res.json()
    assert req_data["status"] == "SUBMITTED"
    request_id = req_data["id"]

    # Verify official timetable was NOT altered by submission
    async with AsyncSessionLocal() as session:
        refreshed = await session.get(TimetableSession, target_session_id)
        assert refreshed.time_slot_id == initial_slot

    # 4. Coordinator reviews and proposes alternatives (Status -> ALTERNATIVES_PROPOSED)
    rev_res = await client.post(
        f"/api/v1/approvals/requests/{request_id}/review",
        headers={"Authorization": f"Bearer {coord_token}"},
    )
    assert rev_res.status_code == 200
    rev_data = rev_res.json()
    assert rev_data["status"] == "ALTERNATIVES_PROPOSED"
    assert len(rev_data["alternatives"]) > 0
    chosen_alt = rev_data["alternatives"][0]

    # 5. HOD approves request selecting the proposed alternative
    decide_res = await client.post(
        f"/api/v1/approvals/requests/{request_id}/decide",
        headers={"Authorization": f"Bearer {hod_token}"},
        json={
            "decision": "APPROVED",
            "decision_reason": "Approved: fits departmental workload criteria",
            "selected_alternative_id": chosen_alt["id"],
            "expected_lock_version": 1,
        },
    )
    assert decide_res.status_code == 200
    decide_data = decide_res.json()
    assert decide_data["status"] == "APPROVED"
    assert decide_data["review_decision_reason"] == "Approved: fits departmental workload criteria"

    # 6. Verify version bumped and published (v1.0 -> v1.1)
    tables_res = await client.get(
        "/api/v1/timetables?department_id=dept_cs",
        headers={"Authorization": f"Bearer {coord_token}"},
    )
    assert tables_res.status_code == 200
    all_tables = tables_res.json()
    published = next((t for t in all_tables if t["status"] == "PUBLISHED"), None)
    assert published is not None
    assert published["version_minor"] == 1  # Incremented from 0 to 1
    assert published["parent_version_id"] == timetable_id


@pytest.mark.asyncio
async def test_change_request_rejection(client: AsyncClient):
    """Verifies that rejection keeps the official timetable untouched."""
    coord_token = await get_token(client, "coord.cs@timewise.edu")
    teacher_token = await get_token(client, "teacher.sharma@timewise.edu")
    hod_token = await get_token(client, "hod.cs@timewise.edu")

    # Get active published timetable
    tables_res = await client.get(
        "/api/v1/timetables?department_id=dept_cs",
        headers={"Authorization": f"Bearer {coord_token}"},
    )
    timetable_id = tables_res.json()[0]["id"]

    async with AsyncSessionLocal() as session:
        res = await session.execute(
            select(TimetableSession).where(TimetableSession.timetable_id == timetable_id)
        )
        target_session = res.scalars().first()

    # Submit request
    req_res = await client.post(
        "/api/v1/approvals/requests",
        headers={"Authorization": f"Bearer {teacher_token}"},
        json={
            "timetable_id": timetable_id,
            "target_session_id": target_session.id,
            "request_type": "SWAP_ROOM",
            "reason": "Personal preference",
        },
    )
    request_id = req_res.json()["id"]

    # HOD Rejects
    decide_res = await client.post(
        f"/api/v1/approvals/requests/{request_id}/decide",
        headers={"Authorization": f"Bearer {hod_token}"},
        json={
            "decision": "REJECTED",
            "decision_reason": "Rejected: ungrounded room preference",
        },
    )
    assert decide_res.status_code == 200
    assert decide_res.json()["status"] == "REJECTED"


@pytest.mark.asyncio
async def test_change_request_cancellation(client: AsyncClient):
    """Verifies that requester can cancel their request."""
    coord_token = await get_token(client, "coord.cs@timewise.edu")
    teacher_token = await get_token(client, "teacher.sharma@timewise.edu")

    tables_res = await client.get(
        "/api/v1/timetables?department_id=dept_cs",
        headers={"Authorization": f"Bearer {coord_token}"},
    )
    timetable_id = tables_res.json()[0]["id"]

    async with AsyncSessionLocal() as session:
        res = await session.execute(
            select(TimetableSession).where(TimetableSession.timetable_id == timetable_id)
        )
        target_session = res.scalars().first()

    req_res = await client.post(
        "/api/v1/approvals/requests",
        headers={"Authorization": f"Bearer {teacher_token}"},
        json={
            "timetable_id": timetable_id,
            "target_session_id": target_session.id,
            "request_type": "RESCHEDULE_SESSION",
            "reason": "Temporary request",
        },
    )
    request_id = req_res.json()["id"]

    cancel_res = await client.post(
        f"/api/v1/approvals/requests/{request_id}/cancel",
        headers={"Authorization": f"Bearer {teacher_token}"},
    )
    assert cancel_res.status_code == 200
    assert cancel_res.json()["status"] == "CANCELLED"


@pytest.mark.asyncio
async def test_optimistic_concurrency_lock_version(client: AsyncClient):
    """Verifies that stale updates with mismatched lock_version are rejected with HTTP 409 Conflict."""
    coord_token = await get_token(client, "coord.cs@timewise.edu")
    teacher_token = await get_token(client, "teacher.sharma@timewise.edu")
    hod_token = await get_token(client, "hod.cs@timewise.edu")

    tables_res = await client.get(
        "/api/v1/timetables?department_id=dept_cs",
        headers={"Authorization": f"Bearer {coord_token}"},
    )
    timetable_id = tables_res.json()[0]["id"]

    async with AsyncSessionLocal() as session:
        res = await session.execute(
            select(TimetableSession).where(TimetableSession.timetable_id == timetable_id)
        )
        target_session = res.scalars().first()

    req_res = await client.post(
        "/api/v1/approvals/requests",
        headers={"Authorization": f"Bearer {teacher_token}"},
        json={
            "timetable_id": timetable_id,
            "target_session_id": target_session.id,
            "request_type": "RESCHEDULE_SESSION",
            "reason": "Test concurrency",
        },
    )
    request_id = req_res.json()["id"]

    # Try deciding with wrong expected lock version
    decide_res = await client.post(
        f"/api/v1/approvals/requests/{request_id}/decide",
        headers={"Authorization": f"Bearer {hod_token}"},
        json={
            "decision": "APPROVED",
            "decision_reason": "Test concurrency",
            "expected_lock_version": 999,  # Deliberate mismatch
        },
    )
    assert decide_res.status_code == 409
    assert "Concurrent modification detected" in decide_res.text


@pytest.mark.asyncio
async def test_rbac_approvals_enforcement(client: AsyncClient):
    """Verifies that students and teachers cannot approve change requests (HTTP 403 Forbidden)."""
    student_token = await get_token(client, "student.aarav@timewise.edu")
    teacher_token = await get_token(client, "teacher.sharma@timewise.edu")
    coord_token = await get_token(client, "coord.cs@timewise.edu")

    # 1. Student cannot submit change requests
    sub_res = await client.post(
        "/api/v1/approvals/requests",
        headers={"Authorization": f"Bearer {student_token}"},
        json={
            "timetable_id": "dummy",
            "target_session_id": "dummy",
            "request_type": "RESCHEDULE_SESSION",
            "reason": "Student request",
        },
    )
    assert sub_res.status_code == 403

    # 2. Teacher cannot decide/approve change requests
    dec_res = await client.post(
        "/api/v1/approvals/requests/dummy_id/decide",
        headers={"Authorization": f"Bearer {teacher_token}"},
        json={
            "decision": "APPROVED",
            "decision_reason": "Teacher attempting approval",
        },
    )
    assert dec_res.status_code == 403

    # 3. Coordinator cannot decide/approve (only HOD / Admin have CHANGE_REQUEST_DECIDE)
    coord_dec_res = await client.post(
        "/api/v1/approvals/requests/dummy_id/decide",
        headers={"Authorization": f"Bearer {coord_token}"},
        json={
            "decision": "APPROVED",
            "decision_reason": "Coordinator attempting approval",
        },
    )
    assert coord_dec_res.status_code == 403
