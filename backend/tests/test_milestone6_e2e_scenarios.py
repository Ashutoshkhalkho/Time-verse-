import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.db.seed import DEFAULT_DEMO_PASSWORD, seed_demo_data
from app.db.session import AsyncSessionLocal
from app.models.timetable import TimetableSession

DEMO_ACCOUNTS = {
    "ADMIN": "admin@timewise.edu",
    "HOD": "hod.cs@timewise.edu",
    "COORDINATOR": "coord.cs@timewise.edu",
    "TEACHER": "teacher.sharma@timewise.edu",
    "CR": "cr.cs3a@timewise.edu",
    "STUDENT": "student.aarav@timewise.edu",
    "MENTOR": "mentor.rao@timewise.edu",
}


@pytest.fixture(scope="module", autouse=True)
async def seed_m6_test_database():
    """Seeds synthetic demo users and organizations for Milestone 6 E2E test suite."""
    async with AsyncSessionLocal() as session:
        await seed_demo_data(session)


async def get_token_for(client: AsyncClient, email: str) -> str:
    res = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": DEFAULT_DEMO_PASSWORD},
    )
    assert res.status_code == 200, f"Login failed for {email}: {res.text}"
    return res.json()["tokens"]["access_token"]


@pytest.mark.asyncio
async def test_scenario_1_all_roles_authentication_and_dashboards(client: AsyncClient):
    """Scenario 1: Authenticate each persona and verify role-specific dashboard access."""
    for role, email in DEMO_ACCOUNTS.items():
        token = await get_token_for(client, email)
        res = await client.get(
            "/api/v1/portal/summary",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200, f"Dashboard summary failed for {role}: {res.text}"
        data = res.json()
        assert data["user_role"] == role
        assert "metrics" in data

        if role == "ADMIN":
            assert data["metrics"]["total_users"] >= 7
        elif role == "HOD":
            assert "capacity_utilization" in data["metrics"]
        elif role == "COORDINATOR":
            assert "solver_engine" in data["metrics"]
        elif role == "TEACHER":
            assert "weekly_teaching_sessions" in data["metrics"]
        elif role == "CR":
            assert "enrolled_section" in data["metrics"]
        elif role == "STUDENT":
            assert "attendance_rate" in data["metrics"]
        elif role == "MENTOR":
            assert "assigned_mentees" in data["metrics"]


@pytest.mark.asyncio
async def test_scenario_2_cross_role_and_cross_resource_unauthorized_rejection(client: AsyncClient):
    """Scenario 2: Verify server-side authorization blocks unauthorized cross-role API calls."""
    student_token = await get_token_for(client, DEMO_ACCOUNTS["STUDENT"])
    cr_token = await get_token_for(client, DEMO_ACCOUNTS["CR"])
    teacher_token = await get_token_for(client, DEMO_ACCOUNTS["TEACHER"])

    # 1. Student attempting to trigger CP-SAT schedule generation -> 403 Forbidden
    res = await client.post(
        "/api/v1/timetables/generate",
        headers={"Authorization": f"Bearer {student_token}"},
        json={"department_id": "dept_cs", "academic_term_id": "term_2026_odd", "time_limit_seconds": 10.0},
    )
    assert res.status_code == 403

    # 2. CR attempting to access user provisioning & security audit trail -> 403 Forbidden
    res = await client.get(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {cr_token}"},
    )
    assert res.status_code == 403

    res = await client.get(
        "/api/v1/audit/logs",
        headers={"Authorization": f"Bearer {cr_token}"},
    )
    assert res.status_code == 403

    # 3. Student attempting to access mentor-only mentee dossiers -> 403 Forbidden
    res = await client.get(
        "/api/v1/portal/mentor-mentees",
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert res.status_code == 403

    # 4. Teacher attempting to decide/approve a change request -> 403 Forbidden
    res = await client.post(
        "/api/v1/approvals/requests/req_dummy_123/decide",
        headers={"Authorization": f"Bearer {teacher_token}"},
        json={"decision": "APPROVED", "decision_reason": "Teacher attempt"},
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_scenario_3_data_ingestion_and_row_level_diagnostics(client: AsyncClient):
    """Scenario 3: Import valid and invalid CSV datasets and verify row-level error reporting."""
    coord_token = await get_token_for(client, DEMO_ACCOUNTS["COORDINATOR"])

    # Valid CSV import via preflight preview
    valid_csv = "building,room_number,capacity,room_type\nBlock C,301,60,LECTURE_HALL\nBlock C,302,40,COMPUTER_LAB\n"
    res_valid = await client.post(
        "/api/v1/import/preview",
        headers={"Authorization": f"Bearer {coord_token}"},
        params={"entity_type": "rooms"},
        files={"file": ("rooms_test.csv", valid_csv.encode("utf-8"), "text/csv")},
    )
    assert res_valid.status_code == 200
    preview_valid = res_valid.json()
    assert preview_valid["total_rows"] == 2
    assert preview_valid["valid_rows"] == 2
    assert preview_valid["is_committable"] is True

    # Malformed CSV with missing field and negative capacity
    invalid_csv = "building,room_number,capacity,room_type\nBlock C,,60,LECTURE_HALL\nBlock C,303,-5,LECTURE_HALL\n"
    res_invalid = await client.post(
        "/api/v1/import/preview",
        headers={"Authorization": f"Bearer {coord_token}"},
        params={"entity_type": "rooms"},
        files={"file": ("rooms_bad.csv", invalid_csv.encode("utf-8"), "text/csv")},
    )
    assert res_invalid.status_code == 200
    preview_invalid = res_invalid.json()
    assert preview_invalid["is_committable"] is False
    assert preview_invalid["invalid_rows"] == 2
    assert len(preview_invalid["errors"]) >= 2


@pytest.mark.asyncio
async def test_scenario_4_impact_simulator_zero_writes_and_discard(client: AsyncClient):
    """Scenario 4: Verify What-If simulation operates in sandbox with zero database writes."""
    coord_token = await get_token_for(client, DEMO_ACCOUNTS["COORDINATOR"])

    # Generate a draft timetable first
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

    # Record baseline database state
    async with AsyncSessionLocal() as session:
        res = await session.execute(
            select(TimetableSession).where(TimetableSession.timetable_id == timetable_id)
        )
        sessions_before = res.scalars().all()
        count_before = len(sessions_before)
        target_session = sessions_before[0]
        initial_slot_id = target_session.time_slot_id
        initial_room_id = target_session.room_id

    # Run What-If Simulation requesting a hypothetical change
    sim_res = await client.post(
        "/api/v1/simulator/simulate",
        headers={"Authorization": f"Bearer {coord_token}"},
        json={
            "timetable_id": timetable_id,
            "target_session_id": target_session.id,
            "proposed_time_slot_id": "slot_wed_p1",
            "proposed_room_id": "room_lh_102",
            "reason": "Hypothetical what-if testing",
        },
    )
    assert sim_res.status_code == 200
    sim_data = sim_res.json()
    assert "directly_affected_count" in sim_data
    assert len(sim_data["alternatives"]) <= 3

    # CRITICAL ASSERTION: Verify 0 database mutations
    async with AsyncSessionLocal() as session:
        res = await session.execute(
            select(TimetableSession).where(TimetableSession.timetable_id == timetable_id)
        )
        sessions_after = res.scalars().all()
        assert len(sessions_after) == count_before

        refreshed_target = await session.get(TimetableSession, target_session.id)
        assert refreshed_target.time_slot_id == initial_slot_id
        assert refreshed_target.room_id == initial_room_id


@pytest.mark.asyncio
async def test_scenario_5_targeted_alerts_and_deduplication(client: AsyncClient):
    """Scenario 5: Confirm alerts target affected cohorts and enforce 5-minute deduplication."""
    admin_token = await get_token_for(client, DEMO_ACCOUNTS["ADMIN"])
    student_token = await get_token_for(client, DEMO_ACCOUNTS["STUDENT"])

    # 1. Broadcast an alert targeting Section CS-3A
    res_broadcast = await client.post(
        "/api/v1/alerts/broadcast",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "title": "Room Relocation for Data Structures Exam",
            "message": "Section CS-3A report to Hall LH-102 instead of LH-101.",
            "severity": "HIGH",
            "cohort_section_id": "sec_cs_3a",
        },
    )
    assert res_broadcast.status_code == 201
    assert res_broadcast.json()["recipients_notified"] >= 1

    # 2. Confirm student in Section CS-3A receives the alert
    res_student_alerts = await client.get(
        "/api/v1/alerts?limit=10",
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert res_student_alerts.status_code == 200
    student_alerts = res_student_alerts.json()["alerts"]
    assert any(a["title"] == "Room Relocation for Data Structures Exam" for a in student_alerts)

    # 3. Duplicate broadcast sent immediately must be suppressed by deduplication cooldown
    res_duplicate = await client.post(
        "/api/v1/alerts/broadcast",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "title": "Room Relocation for Data Structures Exam",
            "message": "Section CS-3A report to Hall LH-102 instead of LH-101.",
            "severity": "HIGH",
            "cohort_section_id": "sec_cs_3a",
        },
    )
    assert res_duplicate.status_code == 201
    assert res_duplicate.json()["recipients_notified"] == 0


@pytest.mark.asyncio
async def test_scenario_6_system_health_and_audit_trail(client: AsyncClient):
    """Scenario 6: Verify health-check probes and tamper-evident audit logging."""
    # Liveness probe
    res_live = await client.get("/healthz")
    assert res_live.status_code == 200
    assert res_live.json()["status"] == "ok"

    # Readiness probe
    res_ready = await client.get("/healthz/ready")
    assert res_ready.status_code == 200
    assert res_ready.json()["status"] == "ok"

    # Admin audit events endpoint
    admin_token = await get_token_for(client, DEMO_ACCOUNTS["ADMIN"])
    res_audit = await client.get(
        "/api/v1/audit/logs",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res_audit.status_code == 200
    events = res_audit.json()
    assert isinstance(events, list)
    assert len(events) >= 1
    ev = events[0]
    assert "id" in ev
    assert "action" in ev
    assert "actor_user_id" in ev
    assert "created_at" in ev
