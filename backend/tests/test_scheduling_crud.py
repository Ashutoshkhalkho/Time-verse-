import pytest
from httpx import AsyncClient

from app.db.seed import DEFAULT_DEMO_PASSWORD, seed_demo_data
from app.db.session import AsyncSessionLocal


@pytest.fixture(scope="module", autouse=True)
async def seed_test_database():
    async with AsyncSessionLocal() as session:
        await seed_demo_data(session)


async def get_token_for(client: AsyncClient, email: str) -> str:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": DEFAULT_DEMO_PASSWORD},
    )
    assert response.status_code == 200
    return response.json()["tokens"]["access_token"]


@pytest.mark.asyncio
async def test_session_conflict_preflight_and_crud(client: AsyncClient):
    """Verifies preflight conflict detection and authorized CRUD operations for individual schedule entries."""
    admin_token = await get_token_for(client, "admin@timewise.edu")
    student_token = await get_token_for(client, "student.aarav@timewise.edu")

    # 1. Conflict Check: Teacher already scheduled on Monday Period 1 (Dr. Rajesh Sharma in LH-101)
    conflict_resp = await client.post(
        "/api/v1/timetables/sessions/check-conflict",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "timetable_id": "tt_dept_cs_master_v1",
            "time_slot_id": "ts_d1_p1",
            "teacher_id": "tch_sharma",
            "room_id": "rm_lh102",
            "cohort_section_id": "sec_cs_3b",
        },
    )
    assert conflict_resp.status_code == 200
    data = conflict_resp.json()
    assert data["has_conflict"] is True
    assert any("Faculty Double-Booking" in c for c in data["conflicts"])

    # 2. Reject Create when Conflict exists
    create_fail = await client.post(
        "/api/v1/timetables/tt_dept_cs_master_v1/sessions",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "subject_id": "sub_cs301",
            "teacher_id": "tch_sharma",
            "room_id": "rm_lh101",
            "cohort_section_id": "sec_cs_3a",
            "time_slot_id": "ts_d1_p1",  # already occupied
        },
    )
    assert create_fail.status_code == 409
    assert "Double-Booking" in create_fail.json()["detail"]

    # 3. Student cannot create sessions (403 Forbidden)
    student_fail = await client.post(
        "/api/v1/timetables/tt_dept_cs_master_v1/sessions",
        headers={"Authorization": f"Bearer {student_token}"},
        json={
            "subject_id": "sub_cs301",
            "teacher_id": "tch_sharma",
            "room_id": "rm_lh101",
            "cohort_section_id": "sec_cs_3a",
            "time_slot_id": "ts_d4_p6",
        },
    )
    assert student_fail.status_code == 403

    # 4. Successful creation on an open slot (Thursday Period 6)
    create_ok = await client.post(
        "/api/v1/timetables/tt_dept_cs_master_v1/sessions",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "subject_id": "sub_cs303",
            "teacher_id": "tch_patel",
            "room_id": "rm_lh101",
            "cohort_section_id": "sec_cs_3a",
            "time_slot_id": "ts_d4_p6",
        },
    )
    assert create_ok.status_code == 201
    created_session = create_ok.json()
    session_id = created_session["id"]
    assert created_session["time_slot_id"] == "ts_d4_p6"

    # 5. Successful Update of created session (move to Friday Period 6)
    update_ok = await client.put(
        f"/api/v1/timetables/tt_dept_cs_master_v1/sessions/{session_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"time_slot_id": "ts_d5_p6"},
    )
    assert update_ok.status_code == 200

    # 6. Delete created session
    del_ok = await client.delete(
        f"/api/v1/timetables/tt_dept_cs_master_v1/sessions/{session_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert del_ok.status_code == 200


@pytest.mark.asyncio
async def test_day_view_timeline_endpoint(client: AsyncClient):
    """Verifies daily timeline endpoint returns chronological sessions for Monday (Day 1)."""
    token = await get_token_for(client, "student.aarav@timewise.edu")

    response = await client.get(
        "/api/v1/timetables/tt_dept_cs_master_v1/day/1",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["day_name"] == "Monday"
    assert len(data["timeline"]) == 6
    # Period 4 is break
    assert data["timeline"][3]["is_break"] is True
    # Period 1 has class
    assert data["timeline"][0]["session"] is not None
    assert data["timeline"][0]["session"]["subject_code"] == "CS301"
