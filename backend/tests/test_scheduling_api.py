import pytest
from httpx import AsyncClient

from app.db.seed import DEFAULT_DEMO_PASSWORD, seed_demo_data
from app.db.session import AsyncSessionLocal


@pytest.fixture(scope="module", autouse=True)
async def seed_api_test_db():
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
async def test_coordinator_can_generate_timetable(client: AsyncClient):
    """Verifies that Coordinator can invoke CP-SAT generator and receive a verified draft timetable."""
    token = await get_token_for(client, "coord.cs@timewise.edu")

    response = await client.post(
        "/api/v1/timetables/generate",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "department_id": "dept_cs",
            "academic_term_id": "term_2026_odd",
            "time_limit_seconds": 15.0,
            "weight_preferred_times": 10,
            "weight_balanced_daily_workload": 15,
            "weight_minimize_gaps": 10,
            "notes": "Automated test generation",
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] == "DRAFT"
    assert data["solver_status"] in {"OPTIMAL", "FEASIBLE"}
    assert data["is_valid"] is True
    assert data["total_sessions_scheduled"] > 0
    assert len(data["hard_violations"]) == 0
    timetable_id = data["timetable_id"]

    # Now verify the 2D Grid endpoint
    grid_resp = await client.get(
        f"/api/v1/timetables/{timetable_id}/grid",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert grid_resp.status_code == 200
    grid_data = grid_resp.json()
    assert len(grid_data["grid"]) == 5  # Mon-Fri
    assert len(grid_data["periods_header"]) == 6  # Periods 1-6

    # Now verify CSV Export
    csv_resp = await client.get(
        f"/api/v1/timetables/{timetable_id}/export?export_format=csv",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert csv_resp.status_code == 200
    assert "text/csv" in csv_resp.headers["content-type"]
    assert "Subject Code" in csv_resp.text

    # Now verify XLSX Export
    xlsx_resp = await client.get(
        f"/api/v1/timetables/{timetable_id}/export?export_format=xlsx",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert xlsx_resp.status_code == 200
    assert "spreadsheetml" in xlsx_resp.headers["content-type"]


@pytest.mark.asyncio
async def test_student_cannot_generate_timetable(client: AsyncClient):
    """Verifies that Student is forbidden (HTTP 403) from generating or modifying timetables."""
    student_token = await get_token_for(client, "student.aarav@timewise.edu")

    response = await client.post(
        "/api/v1/timetables/generate",
        headers={"Authorization": f"Bearer {student_token}"},
        json={
            "department_id": "dept_cs",
            "academic_term_id": "term_2026_odd",
        },
    )
    assert response.status_code == 403
    assert response.json()["code"] == "FORBIDDEN"
