import pytest
from httpx import AsyncClient

from app.db.seed import DEFAULT_DEMO_PASSWORD, seed_demo_data
from app.db.session import AsyncSessionLocal


@pytest.fixture(scope="module", autouse=True)
async def seed_portal_test_db():
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
async def test_user_alerts_lifecycle(client: AsyncClient):
    """
    Verifies alert broadcast, receipt, unread counters, and mark-as-read updates.
    """
    admin_token = await get_token(client, "admin@timewise.edu")
    student_token = await get_token(client, "student.aarav@timewise.edu")

    # 1. Admin broadcasts official notice
    b_res = await client.post(
        "/api/v1/alerts/broadcast",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "title": "Autonomous Examination Schedule Published",
            "message": "The final timetable for Odd Term 2026 examinations is now official.",
            "severity": "INFORMATIONAL",
            "department_id": "dept_cs",
        },
    )
    assert b_res.status_code == 201
    assert b_res.json()["recipients_notified"] > 0

    # 2. Student queries their alerts
    s_res = await client.get(
        "/api/v1/alerts",
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert s_res.status_code == 200
    s_data = s_res.json()
    assert s_data["unread_count"] >= 1
    assert len(s_data["alerts"]) >= 1

    target_alert = s_data["alerts"][0]
    alert_id = target_alert["id"]

    # 3. Mark single alert as read
    r_res = await client.patch(
        f"/api/v1/alerts/{alert_id}/read",
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert r_res.status_code == 200
    assert r_res.json()["is_read"] is True

    # 4. Mark all read
    all_res = await client.post(
        "/api/v1/alerts/mark-all-read",
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert all_res.status_code == 200

    # 5. Verify unread count is 0
    after_res = await client.get(
        "/api/v1/alerts",
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert after_res.json()["unread_count"] == 0


@pytest.mark.asyncio
async def test_alert_deduplication(client: AsyncClient):
    """
    Verifies that identical broadcasts to the same recipients are deduplicated.
    """
    admin_token = await get_token(client, "admin@timewise.edu")

    # First send
    res1 = await client.post(
        "/api/v1/alerts/broadcast",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "title": "Library Book Return Reminder",
            "message": "All reserved materials must be cleared before term end.",
            "severity": "INFORMATIONAL",
            "cohort_section_id": "sec_cs_3a",
        },
    )
    assert res1.status_code == 201
    count1 = res1.json()["recipients_notified"]
    assert count1 > 0

    # Second immediate send (duplicate)
    res2 = await client.post(
        "/api/v1/alerts/broadcast",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "title": "Library Book Return Reminder",
            "message": "All reserved materials must be cleared before term end.",
            "severity": "INFORMATIONAL",
            "cohort_section_id": "sec_cs_3a",
        },
    )
    assert res2.status_code == 201
    assert res2.json()["recipients_notified"] == 0  # Deduplicated!


@pytest.mark.asyncio
async def test_role_dashboard_summaries(client: AsyncClient):
    """
    Verifies real database-aggregated summary metrics for distinct college roles.
    """
    admin_token = await get_token(client, "admin@timewise.edu")
    hod_token = await get_token(client, "hod.cs@timewise.edu")
    coord_token = await get_token(client, "coord.cs@timewise.edu")
    teacher_token = await get_token(client, "teacher.sharma@timewise.edu")
    student_token = await get_token(client, "student.aarav@timewise.edu")

    # Admin Summary
    a_res = await client.get("/api/v1/portal/summary", headers={"Authorization": f"Bearer {admin_token}"})
    assert a_res.status_code == 200
    a_data = a_res.json()
    assert a_data["user_role"] == "ADMIN"
    assert a_data["metrics"]["total_users"] > 0
    assert a_data["metrics"]["total_rooms"] > 0

    # HOD Summary
    h_res = await client.get("/api/v1/portal/summary", headers={"Authorization": f"Bearer {hod_token}"})
    assert h_res.status_code == 200
    h_data = h_res.json()
    assert h_data["user_role"] == "HOD"
    assert "capacity_utilization" in h_data["metrics"]

    # Coordinator Summary
    c_res = await client.get("/api/v1/portal/summary", headers={"Authorization": f"Bearer {coord_token}"})
    assert c_res.status_code == 200
    c_data = c_res.json()
    assert c_data["user_role"] == "COORDINATOR"
    assert "solver_engine" in c_data["metrics"]

    # Teacher Summary
    t_res = await client.get("/api/v1/portal/summary", headers={"Authorization": f"Bearer {teacher_token}"})
    assert t_res.status_code == 200
    t_data = t_res.json()
    assert t_data["user_role"] == "TEACHER"
    assert "weekly_teaching_sessions" in t_data["metrics"]

    # Student Summary
    s_res = await client.get("/api/v1/portal/summary", headers={"Authorization": f"Bearer {student_token}"})
    assert s_res.status_code == 200
    s_data = s_res.json()
    assert s_data["user_role"] == "STUDENT"
    assert "attendance_rate" in s_data["metrics"]


@pytest.mark.asyncio
async def test_student_records_and_appointments(client: AsyncClient):
    """
    Verifies hall-ticket, fee dues, appointments booking, and mentor authorization scoping.
    """
    student_token = await get_token(client, "student.aarav@timewise.edu")
    mentor_token = await get_token(client, "mentor.rao@timewise.edu")

    # Student records
    rec_res = await client.get("/api/v1/portal/student-records", headers={"Authorization": f"Bearer {student_token}"})
    assert rec_res.status_code == 200
    rec_data = rec_res.json()
    assert rec_data["hall_ticket"]["status"] == "AVAILABLE"
    assert rec_data["fee_details"]["pending_dues"] == "$0.00"

    # List appointments
    apt_res = await client.get("/api/v1/portal/appointments", headers={"Authorization": f"Bearer {student_token}"})
    assert apt_res.status_code == 200
    slots = apt_res.json()
    assert len(slots) > 0

    target_slot_id = slots[0]["id"]

    # Book appointment
    book_res = await client.post(
        f"/api/v1/portal/appointments/{target_slot_id}/book",
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert book_res.status_code == 200
    assert book_res.json()["status"] == "CONFIRMED"

    # Authorized Mentor access to mentees
    m_res = await client.get("/api/v1/portal/mentor-mentees", headers={"Authorization": f"Bearer {mentor_token}"})
    assert m_res.status_code == 200
    mentees = m_res.json()
    assert len(mentees) > 0
    assert "Aarav Menon" in mentees[0]["student_name"]

    # Unauthorized Student access to mentor-mentees -> 403 Forbidden
    unauth_res = await client.get("/api/v1/portal/mentor-mentees", headers={"Authorization": f"Bearer {student_token}"})
    assert unauth_res.status_code == 403
