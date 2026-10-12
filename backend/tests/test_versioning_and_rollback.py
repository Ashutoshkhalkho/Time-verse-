import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.db.seed import DEFAULT_DEMO_PASSWORD, seed_demo_data
from app.db.session import AsyncSessionLocal
from app.models.alert import Alert
from app.models.timetable import Timetable, TimetableSession


@pytest.fixture(scope="module", autouse=True)
async def seed_versioning_test_db():
    async with AsyncSessionLocal() as session:
        await seed_demo_data(session)


async def get_token(client: AsyncClient, email: str) -> str:
    res = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": DEFAULT_DEMO_PASSWORD},
    )
    assert res.status_code == 200
    return res.json()["tokens"]["access_token"]


async def ensure_two_versions(client: AsyncClient):
    coord_token = await get_token(client, "coord.cs@timewise.edu")
    teacher_token = await get_token(client, "teacher.sharma@timewise.edu")
    hod_token = await get_token(client, "hod.cs@timewise.edu")

    tables_res = await client.get(
        "/api/v1/timetables?department_id=dept_cs",
        headers={"Authorization": f"Bearer {coord_token}"},
    )
    tables = tables_res.json()
    if len(tables) >= 2:
        return

    # 1. Coordinator generates draft timetable v1.0
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
    await client.post(
        f"/api/v1/timetables/{timetable_id}/propose",
        headers={"Authorization": f"Bearer {coord_token}"},
    )

    # 3. Fetch a session to reschedule
    async with AsyncSessionLocal() as session:
        res = await session.execute(
            select(TimetableSession).where(TimetableSession.timetable_id == timetable_id)
        )
        target_session = res.scalars().first()
        target_session_id = target_session.id

    # 4. Teacher submits change request with sensitive reason
    req_res = await client.post(
        "/api/v1/approvals/requests",
        headers={"Authorization": f"Bearer {teacher_token}"},
        json={
            "timetable_id": timetable_id,
            "target_session_id": target_session_id,
            "request_type": "RESCHEDULE_SESSION",
            "reason": "Attending research symposium and urgent personal medical consultation",
        },
    )
    assert req_res.status_code == 201
    req_data = req_res.json()
    request_id = req_data["id"]

    # 5. Coordinator reviews request (generates alternatives)
    rev_res = await client.post(
        f"/api/v1/approvals/requests/{request_id}/review",
        headers={"Authorization": f"Bearer {coord_token}"},
    )
    assert rev_res.status_code == 200
    alts = rev_res.json()["alternatives"]
    selected_alt_id = alts[0]["id"] if alts else None

    # 6. HOD approves change -> triggers publication (v1.1) and notifications
    dec_res = await client.post(
        f"/api/v1/approvals/requests/{request_id}/decide",
        headers={"Authorization": f"Bearer {hod_token}"},
        json={
            "decision": "APPROVED",
            "decision_reason": "Approved by HOD with faculty approval",
            "selected_alternative_id": selected_alt_id,
        },
    )
    assert dec_res.status_code == 200


@pytest.mark.asyncio
async def test_version_comparison_diff(client: AsyncClient):
    """
    Verifies side-by-side comparison between previous and current timetable versions.
    """
    await ensure_two_versions(client)
    coord_token = await get_token(client, "coord.cs@timewise.edu")

    # Fetch existing versions
    tables_res = await client.get(
        "/api/v1/timetables?department_id=dept_cs",
        headers={"Authorization": f"Bearer {coord_token}"},
    )
    assert tables_res.status_code == 200
    tables = tables_res.json()
    assert len(tables) >= 2

    version_a = tables[1]  # older
    version_b = tables[0]  # newer

    comp_res = await client.get(
        f"/api/v1/timetables/compare/diff?version_a_id={version_a['id']}&version_b_id={version_b['id']}",
        headers={"Authorization": f"Bearer {coord_token}"},
    )
    assert comp_res.status_code == 200
    diff_data = comp_res.json()
    assert diff_data["version_a_id"] == version_a["id"]
    assert diff_data["version_b_id"] == version_b["id"]
    assert diff_data["total_sessions_a"] > 0
    assert diff_data["total_sessions_b"] > 0
    assert len(diff_data["session_diffs"]) > 0


@pytest.mark.asyncio
async def test_safe_version_rollback_preserves_history(client: AsyncClient):
    """
    FR-10:
    Verifies that rollback restores a prior schedule through a NEW validated version,
    never destructively deleting history.
    """
    await ensure_two_versions(client)
    hod_token = await get_token(client, "hod.cs@timewise.edu")

    # Fetch versions
    tables_res = await client.get(
        "/api/v1/timetables?department_id=dept_cs",
        headers={"Authorization": f"Bearer {hod_token}"},
    )
    tables = tables_res.json()
    active_table = tables[0]
    target_table = tables[-1]  # original v1.0
    initial_version_count = len(tables)

    # Perform safe rollback
    rb_res = await client.post(
        f"/api/v1/timetables/{active_table['id']}/rollback",
        headers={"Authorization": f"Bearer {hod_token}"},
        json={
            "target_version_id": target_table["id"],
            "reason": "Restoring baseline schedule for term adjustment",
        },
    )
    assert rb_res.status_code == 200
    rb_data = rb_res.json()
    assert rb_data["status"] == "PUBLISHED"
    new_table_id = rb_data["id"]

    # Verify history preservation: total versions increased by 1 (no deletion)
    after_res = await client.get(
        "/api/v1/timetables?department_id=dept_cs",
        headers={"Authorization": f"Bearer {hod_token}"},
    )
    after_tables = after_res.json()
    assert len(after_tables) == initial_version_count + 1

    # Verify prior versions still exist in database
    async with AsyncSessionLocal() as session:
        old_v = await session.get(Timetable, active_table["id"])
        assert old_v is not None
        assert old_v.status.value == "ARCHIVED"

        orig_v = await session.get(Timetable, target_table["id"])
        assert orig_v is not None

        new_v = await session.get(Timetable, new_table_id)
        assert new_v is not None
        assert new_v.parent_version_id == target_table["id"]


@pytest.mark.asyncio
async def test_targeted_notifications_and_privacy_masking(client: AsyncClient):
    """
    FR-11 / Acceptance Test 7:
    Verifies that reschedule events generate targeted alerts in the database,
    and private medical/personal reasons are masked from notifications.
    """
    await ensure_two_versions(client)
    async with AsyncSessionLocal() as session:
        alerts_res = await session.execute(select(Alert).order_by(Alert.created_at.desc()))
        alerts = alerts_res.scalars().all()
        assert len(alerts) > 0

        for a in alerts:
            # Sensitive words must never appear in alert titles or messages
            assert "research symposium" not in a.message.lower()
            assert "medical" not in a.message.lower()
            assert "personal" not in a.message.lower()
            assert a.recipient_user_id is not None
