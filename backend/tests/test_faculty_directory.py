import pytest
from httpx import AsyncClient

from app.db.seed import DEFAULT_DEMO_PASSWORD, seed_demo_data
from app.db.session import AsyncSessionLocal
from app.services.faculty_directory.faculty_service import (
    FacultyDirectoryService,
    INITIAL_26_FACULTY_DATA,
)


@pytest.fixture(scope="module", autouse=True)
async def seed_test_database():
    async with AsyncSessionLocal() as session:
        await seed_demo_data(session)
        await FacultyDirectoryService.seed_initial_records(session)


async def get_token_for(client: AsyncClient, email: str) -> str:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": DEFAULT_DEMO_PASSWORD},
    )
    assert response.status_code == 200
    return response.json()["tokens"]["access_token"]


@pytest.mark.asyncio
async def test_all_26_initial_records_present(client: AsyncClient):
    admin_token = await get_token_for(client, "admin@timewise.edu")
    res = await client.get(
        "/api/v1/faculty-directory",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert len(data) >= 26

    names_in_db = {m["full_name"] for m in data}
    for expected in INITIAL_26_FACULTY_DATA:
        assert expected["full_name"] in names_in_db, f"Missing faculty member: {expected['full_name']}"


@pytest.mark.asyncio
async def test_shilpa_rao_duplicate_flagging(client: AsyncClient):
    admin_token = await get_token_for(client, "admin@timewise.edu")
    res = await client.get(
        "/api/v1/faculty-directory?search=Shilpa",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    shilpas = res.json()
    assert len(shilpas) == 2
    names = {s["full_name"] for s in shilpas}
    assert "Ms. C. Shilpa Rao" in names
    assert "Ms. Shilpa Rao" in names
    for s in shilpas:
        assert s["duplicate_flag"] is True, f"Record {s['full_name']} was not flagged for duplicate review"


@pytest.mark.asyncio
async def test_case_insensitive_search(client: AsyncClient):
    admin_token = await get_token_for(client, "admin@timewise.edu")
    # Test lowercase
    res_lower = await client.get(
        "/api/v1/faculty-directory?search=jisha",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res_lower.status_code == 200
    assert any(m["full_name"] == "Dr. V. G. Jisha" for m in res_lower.json())

    # Test uppercase
    res_upper = await client.get(
        "/api/v1/faculty-directory?search=JISHA",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res_upper.status_code == 200
    assert any(m["full_name"] == "Dr. V. G. Jisha" for m in res_upper.json())


@pytest.mark.asyncio
async def test_designation_and_status_filtering(client: AsyncClient):
    admin_token = await get_token_for(client, "admin@timewise.edu")
    # Filter by unverified designation
    res_unverified = await client.get(
        "/api/v1/faculty-directory?designation=UNVERIFIED",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res_unverified.status_code == 200
    for m in res_unverified.json():
        assert m["designation"] is None

    # Filter by specific designation
    res_assoc = await client.get(
        "/api/v1/faculty-directory?designation=Associate Professor",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res_assoc.status_code == 200
    assert any("Excelce" in m["full_name"] for m in res_assoc.json())


@pytest.mark.asyncio
async def test_missing_fields_reporting(client: AsyncClient):
    admin_token = await get_token_for(client, "admin@timewise.edu")
    res = await client.get(
        "/api/v1/faculty-directory?search=Vipulkumar",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    members = res.json()
    assert len(members) >= 1
    vipul = members[0]
    # Verify missing fields are honestly indicated
    assert "Formal Designation" in vipul["missing_fields"]
    assert "Official Email" in vipul["missing_fields"]
    assert "Faculty ID" in vipul["missing_fields"]
    assert vipul["is_verified"] is False


@pytest.mark.asyncio
async def test_unauthorized_user_cannot_modify(client: AsyncClient):
    student_token = await get_token_for(client, "student.aarav@timewise.edu")
    # Attempt to create
    res_create = await client.post(
        "/api/v1/faculty-directory",
        json={"full_name": "Unauthorized Faculty"},
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert res_create.status_code == 403

    # Attempt to seed
    res_seed = await client.post(
        "/api/v1/faculty-directory/seed-initial",
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert res_seed.status_code == 403


@pytest.mark.asyncio
async def test_verification_workflow_requires_acknowledgement(client: AsyncClient):
    admin_token = await get_token_for(client, "admin@timewise.edu")
    res_list = await client.get(
        "/api/v1/faculty-directory?search=Excelce",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    member_id = res_list.json()[0]["id"]

    # Attempt verify without acknowledgement should fail with 422
    res_fail = await client.post(
        f"/api/v1/faculty-directory/{member_id}/verify",
        json={
            "verification_notes": "Official FDP Verified",
            "acknowledged_responsibility": False,
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res_fail.status_code == 422

    # Verification with acknowledgement succeeds
    res_ok = await client.post(
        f"/api/v1/faculty-directory/{member_id}/verify",
        json={
            "designation": "Associate Professor",
            "verification_notes": "Verified against Kristu Jayanti University FDP Official Register 2025",
            "acknowledged_responsibility": True,
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res_ok.status_code == 200
    verified_data = res_ok.json()
    assert verified_data["is_verified"] is True
    assert verified_data["designation"] == "Associate Professor"
    assert "Kristu Jayanti University FDP" in verified_data["verification_notes"]


@pytest.mark.asyncio
async def test_soft_archiving_and_restore(client: AsyncClient):
    admin_token = await get_token_for(client, "admin@timewise.edu")
    # Create temporary faculty record to test archive
    res_new = await client.post(
        "/api/v1/faculty-directory",
        json={"full_name": "Dr. Test Archive Record"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res_new.status_code == 201
    temp_id = res_new.json()["id"]

    # Archive without confirmed=True fails
    res_arch_fail = await client.post(
        f"/api/v1/faculty-directory/{temp_id}/archive",
        json={"confirmed": False},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res_arch_fail.status_code == 422

    # Archive with confirmed=True succeeds
    res_arch = await client.post(
        f"/api/v1/faculty-directory/{temp_id}/archive",
        json={"confirmed": True, "reason": "Testing soft archive"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res_arch.status_code == 200
    assert res_arch.json()["archived_at"] is not None

    # Should not appear in default directory listing
    res_active = await client.get(
        f"/api/v1/faculty-directory?search=Test%20Archive",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert len(res_active.json()) == 0

    # Appears when include_archived=true
    res_archived = await client.get(
        f"/api/v1/faculty-directory?search=Test%20Archive&include_archived=true",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert len(res_archived.json()) == 1


@pytest.mark.asyncio
async def test_csv_preview_and_idempotent_commit(client: AsyncClient):
    admin_token = await get_token_for(client, "admin@timewise.edu")
    sample_csv = """No.,Faculty member,Designation (as found in public sources),Source / verification note
1,Dr. V. G. Jisha,"Head, Department of Professional Management Studies",Official department FDP document (2025)
2,Ms. Shilpa Rao,Possible duplicate of Ms. C. Shilpa Rao,KJU records
3,Dr. Brand New Faculty,Assistant Professor,New hire 2026
"""
    # Preview
    res_preview = await client.post(
        "/api/v1/faculty-directory/preview-csv",
        data={"raw_csv_text": sample_csv},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res_preview.status_code == 200
    preview = res_preview.json()
    assert preview["total_rows"] == 3
    assert preview["valid_rows_count"] == 3
    # Ms. Shilpa Rao flagged as potential duplicate
    assert preview["potential_duplicates_count"] >= 1

    # Commit with confirmed=True
    res_commit = await client.post(
        "/api/v1/faculty-directory/commit-csv",
        json={
            "confirmed": True,
            "overwrite_verified": False,
            "rows": [
                {
                    "full_name": "Dr. Brand New Faculty",
                    "designation": "Assistant Professor",
                    "source_notes": "New hire 2026",
                }
            ],
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res_commit.status_code == 200
    commit_res = res_commit.json()
    assert commit_res["created_count"] == 1
