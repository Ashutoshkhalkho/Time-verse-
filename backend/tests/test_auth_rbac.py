from datetime import timedelta

import pytest
from httpx import AsyncClient

from app.core.security import create_token
from app.db.seed import DEFAULT_DEMO_PASSWORD, seed_demo_data
from app.db.session import AsyncSessionLocal


@pytest.fixture(scope="module", autouse=True)
async def seed_test_database():
    """Seeds synthetic demo users and organizations for RBAC test suite."""
    async with AsyncSessionLocal() as session:
        await seed_demo_data(session)


async def get_token_for(client: AsyncClient, email: str) -> str:
    """Helper to authenticate a synthetic user and extract the JWT access token."""
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": DEFAULT_DEMO_PASSWORD},
    )
    assert response.status_code == 200, f"Login failed for {email}: {response.text}"
    return response.json()["tokens"]["access_token"]


# ==============================================================================
# 1. AUTHENTICATION & SESSION TESTS
# ==============================================================================

@pytest.mark.asyncio
async def test_successful_login_all_roles(client: AsyncClient):
    """Verifies that all 6+ synthetic demo user personas can securely authenticate."""
    role_emails = [
        "admin@timewise.edu",
        "hod.cs@timewise.edu",
        "coord.cs@timewise.edu",
        "teacher.sharma@timewise.edu",
        "cr.cs3a@timewise.edu",
        "student.aarav@timewise.edu",
        "mentor.rao@timewise.edu",
    ]
    for email in role_emails:
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": DEFAULT_DEMO_PASSWORD},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data["tokens"]
        assert "refresh_token" in data["tokens"]
        assert data["user"]["email"] == email
        assert len(data["user"]["permissions"]) > 0


@pytest.mark.asyncio
async def test_login_invalid_password(client: AsyncClient):
    """Rejects incorrect password with 401 Unauthorized."""
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@timewise.edu", "password": "WrongPassword123!"},
    )
    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_login_nonexistent_email(client: AsyncClient):
    """Rejects unknown email with 401 Unauthorized without disclosing user existence."""
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "ghost@timewise.edu", "password": "AnyPassword123!"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token_lifecycle(client: AsyncClient):
    """Exchanges valid refresh token for a newly issued access token."""
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@timewise.edu", "password": DEFAULT_DEMO_PASSWORD},
    )
    refresh_token = login_res.json()["tokens"]["refresh_token"]

    refresh_res = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert refresh_res.status_code == 200
    assert "access_token" in refresh_res.json()


@pytest.mark.asyncio
async def test_logout_revokes_session(client: AsyncClient):
    """Verifies that logging out revokes the access token from subsequent requests."""
    token = await get_token_for(client, "admin@timewise.edu")
    headers = {"Authorization": f"Bearer {token}"}

    # Verify token works before logout
    me_res1 = await client.get("/api/v1/auth/me", headers=headers)
    assert me_res1.status_code == 200

    # Logout
    logout_res = await client.post("/api/v1/auth/logout", headers=headers)
    assert logout_res.status_code == 200

    # Verify token is rejected after logout
    me_res2 = await client.get("/api/v1/auth/me", headers=headers)
    assert me_res2.status_code == 401
    assert "terminated" in me_res2.json()["detail"].lower()


@pytest.mark.asyncio
async def test_expired_token_rejected(client: AsyncClient):
    """Verifies that expired access tokens are rejected with 401."""
    expired_token, _, _ = create_token(
        subject="usr_demo_admin",
        token_type="access",
        expires_delta=timedelta(seconds=-10),  # expired 10 seconds ago
    )
    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert response.status_code == 401
    assert "expired" in response.json()["detail"].lower()


# ==============================================================================
# 2. ROLE & RESOURCE PERMISSION TESTS (POSITIVE & NEGATIVE)
# ==============================================================================

@pytest.mark.asyncio
async def test_admin_permissions(client: AsyncClient):
    """
    Administrator:
    + Positive: Can provision users
    + Positive: Can view security audit logs
    + Positive: Can publish timetables
    """
    admin_token = await get_token_for(client, "admin@timewise.edu")
    headers = {"Authorization": f"Bearer {admin_token}"}

    # 1. Positive: Provision a user
    create_res = await client.post(
        "/api/v1/users",
        headers=headers,
        json={
            "email": "new.faculty@timewise.edu",
            "password": "TempPassword123!",
            "full_name": "New Test Faculty",
            "role": "TEACHER",
            "department_ids": ["dept_cs"],
            "section_ids": [],
        },
    )
    assert create_res.status_code == 201
    created_id = create_res.json()["id"]

    # 2. Positive: View audit logs
    audit_res = await client.get("/api/v1/audit/logs", headers=headers)
    assert audit_res.status_code == 200
    assert len(audit_res.json()) > 0
    assert any(log["action"] == "USER_PROVISION" for log in audit_res.json())

    # 3. Positive: Update user role
    patch_res = await client.patch(
        f"/api/v1/users/{created_id}",
        headers=headers,
        json={"role": "COORDINATOR"},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["role"] == "COORDINATOR"


@pytest.mark.asyncio
async def test_hod_permissions_and_scoping(client: AsyncClient):
    """
    Head of Department:
    + Positive: Can publish timetable for assigned department (dept_cs)
    - Negative: Cannot publish timetable for other department (dept_ee) -> 403 Forbidden
    - Negative: Cannot provision new users -> 403 Forbidden
    - Negative: Cannot view system audit logs -> 403 Forbidden
    """
    hod_token = await get_token_for(client, "hod.cs@timewise.edu")
    headers = {"Authorization": f"Bearer {hod_token}"}

    # 1. Positive: Publish timetable in assigned department
    pub_own = await client.post(
        "/api/v1/departments/dept_cs/timetables/tt_01/publish",
        headers=headers,
    )
    assert pub_own.status_code == 200
    assert pub_own.json()["status"] == "PUBLISHED"

    # 2. Negative: Publish timetable in unassigned department
    pub_other = await client.post(
        "/api/v1/departments/dept_ee/timetables/tt_01/publish",
        headers=headers,
    )
    assert pub_other.status_code == 403
    assert "not authorized for department" in pub_other.json()["detail"].lower()

    # 3. Negative: Provision new users
    create_res = await client.post(
        "/api/v1/users",
        headers=headers,
        json={
            "email": "unauthorized.user@timewise.edu",
            "password": "Password123!",
            "full_name": "Should Fail",
            "role": "STUDENT",
        },
    )
    assert create_res.status_code == 403

    # 4. Negative: View security audit logs
    audit_res = await client.get("/api/v1/audit/logs", headers=headers)
    assert audit_res.status_code == 403


@pytest.mark.asyncio
async def test_coordinator_permissions(client: AsyncClient):
    """
    Timetable Coordinator:
    + Positive: Can create draft timetables in assigned department
    - Negative: Cannot publish timetables -> 403 Forbidden
    - Negative: Cannot provision users -> 403 Forbidden
    """
    coord_token = await get_token_for(client, "coord.cs@timewise.edu")
    headers = {"Authorization": f"Bearer {coord_token}"}

    # 1. Positive: Create draft schedule
    draft_res = await client.post(
        "/api/v1/timetables/draft",
        headers=headers,
        json={"department_id": "dept_cs", "academic_term_id": "term_2026_odd"},
    )
    assert draft_res.status_code == 201

    # 2. Negative: Cannot publish timetables (HOD/Admin only)
    pub_res = await client.post(
        "/api/v1/departments/dept_cs/timetables/tt_01/publish",
        headers=headers,
    )
    assert pub_res.status_code == 403
    assert "lacks permission" in pub_res.json()["detail"].lower()

    # 3. Negative: Cannot provision users
    user_res = await client.post(
        "/api/v1/users",
        headers=headers,
        json={"email": "fail@timewise.edu", "password": "Password123!", "full_name": "Fail", "role": "STUDENT"},
    )
    assert user_res.status_code == 403


@pytest.mark.asyncio
async def test_teacher_permissions(client: AsyncClient):
    """
    Teacher / Faculty:
    + Positive: Can view assigned schedule
    + Positive: Can submit change request
    - Negative: Cannot create draft schedule -> 403 Forbidden
    - Negative: Cannot publish timetable -> 403 Forbidden
    """
    teacher_token = await get_token_for(client, "teacher.sharma@timewise.edu")
    headers = {"Authorization": f"Bearer {teacher_token}"}

    # 1. Positive: View schedule
    sched_res = await client.get("/api/v1/timetables/published", headers=headers)
    assert sched_res.status_code == 200
    assert sched_res.json()["scope"] == "TEACHER"

    # 2. Positive: Submit change request
    cr_res = await client.post(
        "/api/v1/change-requests",
        headers=headers,
        json={"session_id": "sess_101", "reason": "Academic conference attendance"},
    )
    assert cr_res.status_code == 201

    # 3. Negative: Cannot draft schedule
    draft_res = await client.post(
        "/api/v1/timetables/draft",
        headers=headers,
        json={"department_id": "dept_cs", "academic_term_id": "term_2026_odd"},
    )
    assert draft_res.status_code == 403


@pytest.mark.asyncio
async def test_cr_permissions_and_scoping(client: AsyncClient):
    """
    Class Representative (CR):
    + Positive: Can view enrolled section schedule (sec_cs_3a)
    + Positive: Can report classroom issue
    - Negative: Cannot view other section schedule (sec_ee_3a) -> 403 Forbidden
    - Negative: Cannot submit official change requests -> 403 Forbidden
    - Negative: Cannot publish timetables -> 403 Forbidden
    """
    cr_token = await get_token_for(client, "cr.cs3a@timewise.edu")
    headers = {"Authorization": f"Bearer {cr_token}"}

    # 1. Positive: View enrolled section schedule
    view_own = await client.get(
        "/api/v1/timetables/published?section_id=sec_cs_3a",
        headers=headers,
    )
    assert view_own.status_code == 200
    assert "sec_cs_3a" in view_own.json()["allowed_sections"]

    # 2. Negative: Cannot view unassigned section schedule
    view_other = await client.get(
        "/api/v1/timetables/published?section_id=sec_ee_3a",
        headers=headers,
    )
    assert view_other.status_code == 403

    # 3. Positive: Report classroom issue
    issue_res = await client.post(
        "/api/v1/issues",
        headers=headers,
        json={"room_id": "room_304", "description": "Projector HDMI cable broken"},
    )
    assert issue_res.status_code == 201
    assert issue_res.json()["status"] == "REPORTED"

    # 4. Negative: Cannot submit timetable change request
    cr_fail = await client.post(
        "/api/v1/change-requests",
        headers=headers,
        json={"session_id": "sess_101", "reason": "Attempting unauthorized reschedule"},
    )
    assert cr_fail.status_code == 403


@pytest.mark.asyncio
async def test_student_permissions_and_scoping(client: AsyncClient):
    """
    Student:
    + Positive: Can view enrolled section schedule (sec_cs_3a)
    - Negative: Cannot view other section schedule (sec_ee_3a) -> 403 Forbidden
    - Negative: Cannot edit official schedules / change request -> 403 Forbidden
    - Negative: Cannot report issues directly -> 403 Forbidden
    - Negative: Cannot publish timetables -> 403 Forbidden
    """
    student_token = await get_token_for(client, "student.aarav@timewise.edu")
    headers = {"Authorization": f"Bearer {student_token}"}

    # 1. Positive: View enrolled section
    view_own = await client.get(
        "/api/v1/timetables/published?section_id=sec_cs_3a",
        headers=headers,
    )
    assert view_own.status_code == 200

    # 2. Negative: View other section
    view_other = await client.get(
        "/api/v1/timetables/published?section_id=sec_ee_3a",
        headers=headers,
    )
    assert view_other.status_code == 403

    # 3. Negative: Cannot submit change request
    cr_res = await client.post(
        "/api/v1/change-requests",
        headers=headers,
        json={"session_id": "sess_101", "reason": "Student trying to move exam"},
    )
    assert cr_res.status_code == 403

    # 4. Negative: Cannot report issue directly
    issue_res = await client.post(
        "/api/v1/issues",
        headers=headers,
        json={"room_id": "room_101", "description": "Direct student complaint"},
    )
    assert issue_res.status_code == 403


@pytest.mark.asyncio
async def test_mentor_explicit_authorization(client: AsyncClient):
    """
    Mentor:
    + Positive: Can view explicitly authorized mentee (student.aarav)
    - Negative: Teacher without mentor role cannot access mentee endpoint -> 403 Forbidden
    """
    mentor_token = await get_token_for(client, "mentor.rao@timewise.edu")
    mentor_headers = {"Authorization": f"Bearer {mentor_token}"}

    # Positive: Mentor views assigned mentees
    mentee_res = await client.get("/api/v1/mentors/mentees", headers=mentor_headers)
    assert mentee_res.status_code == 200
    data = mentee_res.json()
    assert len(data) == 1
    assert data[0]["student_id"] == "usr_demo_student_aarav"

    # Negative: Regular teacher without mentor assignment
    teacher_token = await get_token_for(client, "teacher.sharma@timewise.edu")
    teacher_headers = {"Authorization": f"Bearer {teacher_token}"}
    fail_res = await client.get("/api/v1/mentors/mentees", headers=teacher_headers)
    assert fail_res.status_code == 403
