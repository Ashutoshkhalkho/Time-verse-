import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.db.seed import DEFAULT_DEMO_PASSWORD, seed_demo_data
from app.db.session import AsyncSessionLocal
from app.models.timetable import TimetableSession


@pytest.fixture(scope="module", autouse=True)
async def seed_simulator_test_db():
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
async def test_simulator_sandbox_zero_writes(client: AsyncClient):
    """
    FR-08 / Acceptance Test 4:
    Verifies that What-If Impact Simulation sandbox executes in pure memory
    with ZERO database writes to timetables or timetable_sessions.
    """
    coord_token = await get_token(client, "coord.cs@timewise.edu")

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
async def test_simulator_detects_directly_affected_sessions(client: AsyncClient):
    """
    Verifies that the simulator identifies target session and conflicting sessions
    at the proposed slot and room.
    """
    coord_token = await get_token(client, "coord.cs@timewise.edu")

    # Fetch existing draft timetable
    tables_res = await client.get(
        "/api/v1/timetables?department_id=dept_cs",
        headers={"Authorization": f"Bearer {coord_token}"},
    )
    assert tables_res.status_code == 200
    timetable_id = tables_res.json()[0]["id"]

    async with AsyncSessionLocal() as session:
        res = await session.execute(
            select(TimetableSession).where(TimetableSession.timetable_id == timetable_id)
        )
        sessions = res.scalars().all()
        sess_a = sessions[0]
        sess_b = sessions[1]

    # Propose moving sess_a to sess_b's current slot and room (intentional collision)
    sim_res = await client.post(
        "/api/v1/simulator/simulate",
        headers={"Authorization": f"Bearer {coord_token}"},
        json={
            "timetable_id": timetable_id,
            "target_session_id": sess_a.id,
            "proposed_time_slot_id": sess_b.time_slot_id,
            "proposed_room_id": sess_b.room_id,
        },
    )
    assert sim_res.status_code == 200
    report = sim_res.json()
    assert report["directly_affected_count"] >= 2
    session_ids = [s["session_id"] for s in report["affected_sessions"]]
    assert sess_a.id in session_ids
    assert sess_b.id in session_ids


@pytest.mark.asyncio
async def test_simulator_generates_ranked_feasible_alternatives(client: AsyncClient):
    """
    Verifies that the simulator generates clash-free alternatives ranked by soft penalty.
    """
    coord_token = await get_token(client, "coord.cs@timewise.edu")

    tables_res = await client.get(
        "/api/v1/timetables?department_id=dept_cs",
        headers={"Authorization": f"Bearer {coord_token}"},
    )
    timetable_id = tables_res.json()[0]["id"]

    async with AsyncSessionLocal() as session:
        res = await session.execute(
            select(TimetableSession).where(TimetableSession.timetable_id == timetable_id)
        )
        target = res.scalars().first()

    sim_res = await client.post(
        "/api/v1/simulator/simulate",
        headers={"Authorization": f"Bearer {coord_token}"},
        json={
            "timetable_id": timetable_id,
            "target_session_id": target.id,
        },
    )
    assert sim_res.status_code == 200
    report = sim_res.json()
    assert len(report["alternatives"]) > 0
    ranks = [alt["option_rank"] for alt in report["alternatives"]]
    assert ranks == list(range(1, len(report["alternatives"]) + 1))
    for alt in report["alternatives"]:
        assert alt["is_feasible"] is True
        assert "capacity_margin" in alt["trade_off_explanation"]
