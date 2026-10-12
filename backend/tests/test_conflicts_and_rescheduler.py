import pytest
from httpx import AsyncClient

from app.db.seed import DEFAULT_DEMO_PASSWORD, seed_demo_data
from app.db.seed_scheduling import seed_scheduling_entities
from app.db.session import AsyncSessionLocal


@pytest.fixture(scope="module", autouse=True)
async def seed_test_db():
    async with AsyncSessionLocal() as session:
        await seed_demo_data(session)
        await seed_scheduling_entities(session)


async def get_token(client: AsyncClient, email: str) -> str:
    res = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": DEFAULT_DEMO_PASSWORD},
    )
    assert res.status_code == 200
    return res.json()["tokens"]["access_token"]


@pytest.mark.asyncio
async def test_conflict_detector_lifecycle(client: AsyncClient):
    """
    1. Verify default timetable is conflict-free.
    2. Inject deliberate clash and verify Conflict Detector immediately flags it.
    3. Verify that resolution suggestions are returned.
    4. Restore and verify revalidation confirms conflict-free state.
    """
    token = await get_token(client, "hod.cs@timewise.edu")

    # Step 1: Query conflicts on verified timetable
    res = await client.get("/api/v1/conflicts?timetable_id=tt_dept_cs_master_v1", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["is_conflict_free"] is True
    assert data["critical_conflicts_count"] == 0

    # Step 2: Inject deliberate teacher clash
    inject_res = await client.post("/api/v1/conflicts/inject-demo-clash?timetable_id=tt_dept_cs_master_v1", headers={"Authorization": f"Bearer {token}"})
    assert inject_res.status_code == 200

    # Step 3: Conflict Detector MUST detect the clash and NEVER report conflict-free
    check_res = await client.get("/api/v1/conflicts?timetable_id=tt_dept_cs_master_v1", headers={"Authorization": f"Bearer {token}"})
    assert check_res.status_code == 200
    check_data = check_res.json()
    assert check_data["is_conflict_free"] is False
    assert check_data["critical_conflicts_count"] > 0
    assert len(check_data["conflicts"]) > 0

    first_clash = check_data["conflicts"][0]
    assert "TEACHER_DOUBLE_BOOKING" in first_clash["type"] or "ROOM_DOUBLE_BOOKING" in first_clash["type"]
    assert len(first_clash["feasible_resolutions"]) > 0

    # Step 4: Restore clean schedule
    restore_res = await client.post("/api/v1/conflicts/restore-conflict-free?timetable_id=tt_dept_cs_master_v1", headers={"Authorization": f"Bearer {token}"})
    assert restore_res.status_code == 200

    # Step 5: Verify back to conflict-free
    final_res = await client.get("/api/v1/conflicts?timetable_id=tt_dept_cs_master_v1", headers={"Authorization": f"Bearer {token}"})
    assert final_res.status_code == 200
    final_json = final_res.json()
    assert final_json["is_conflict_free"] is True, final_json.get("conflicts", [])


@pytest.mark.asyncio
async def test_smart_rescheduler_lifecycle(client: AsyncClient):
    """
    1. Analyze disruption scenario (teacher absence).
    2. Verify affected classes are isolated and unaffected classes are preserved.
    3. Verify ranked feasible alternatives are generated.
    4. Apply an alternative and verify the timetable is automatically revalidated.
    """
    token = await get_token(client, "hod.cs@timewise.edu")

    # 1. Analyze teacher absence
    ana_res = await client.post(
        "/api/v1/rescheduler/analyze",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "disruption_type": "TEACHER_ABSENCE",
            "teacher_id": "tch_sharma",
            "day_of_week": 1,
        },
    )
    assert ana_res.status_code == 200
    ana_data = ana_res.json()
    assert ana_data["affected_count"] > 0
    assert ana_data["unaffected_preserved_count"] > 0
    assert ana_data["preservation_rate_percent"] > 80.0
    assert len(ana_data["affected_sessions"]) > 0

    first_affected = ana_data["affected_sessions"][0]
    assert len(first_affected["suggested_alternatives"]) > 0

    chosen_alt = first_affected["suggested_alternatives"][0]

    # 2. Apply alternative
    apply_res = await client.post(
        "/api/v1/rescheduler/apply",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "session_id": first_affected["session_id"],
            "new_time_slot_id": chosen_alt["new_time_slot_id"],
            "new_teacher_id": chosen_alt["new_teacher_id"],
            "new_room_id": chosen_alt["new_room_id"],
        },
    )
    assert apply_res.status_code == 200
    apply_data = apply_res.json()
    assert apply_data["status"] == "APPLIED_AND_VERIFIED"
    assert "revalidation" in apply_data
