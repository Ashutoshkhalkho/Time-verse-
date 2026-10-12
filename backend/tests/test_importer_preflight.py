import pytest

from app.db.seed import seed_demo_data
from app.db.session import AsyncSessionLocal
from app.services.importer.importer_service import ImporterService
from app.services.importer.schemas import EntityImportType


@pytest.fixture(scope="module", autouse=True)
async def seed_importer_db():
    async with AsyncSessionLocal() as session:
        await seed_demo_data(session)


@pytest.mark.asyncio
async def test_importer_positive_rooms_csv():
    """Verifies that a well-formed CSV file is successfully validated with is_committable=True."""
    csv_content = (
        b"building,room_number,capacity,room_type\n"
        b"Block C,301,60,LECTURE_HALL\n"
        b"Block C,302,40,COMPUTER_LAB\n"
    )

    async with AsyncSessionLocal() as session:
        preview = await ImporterService.parse_and_validate(
            content=csv_content,
            filename="rooms_test.csv",
            entity_type=EntityImportType.ROOMS,
            db_session=session,
        )

    assert preview.total_rows == 2
    assert preview.valid_rows == 2
    assert preview.invalid_rows == 0
    assert preview.is_committable is True
    assert len(preview.errors) == 0


@pytest.mark.asyncio
async def test_importer_detects_missing_fields_and_invalid_capacity():
    """Verifies that missing fields and negative capacity are caught with exact row numbers."""
    csv_content = (
        b"building,room_number,capacity,room_type\n"
        b"Block C,,60,LECTURE_HALL\n"  # row 2: missing room_number
        b"Block C,303,-5,LECTURE_HALL\n"  # row 3: capacity <= 0
    )

    async with AsyncSessionLocal() as session:
        preview = await ImporterService.parse_and_validate(
            content=csv_content,
            filename="rooms_bad.csv",
            entity_type=EntityImportType.ROOMS,
            db_session=session,
        )

    assert preview.total_rows == 2
    assert preview.is_committable is False
    assert preview.invalid_rows == 2
    assert len(preview.errors) >= 2

    row_numbers = [e.row_number for e in preview.errors]
    assert 2 in row_numbers
    assert 3 in row_numbers


@pytest.mark.asyncio
async def test_importer_detects_duplicate_codes():
    """Verifies that duplicate employee codes within the file are blocked."""
    csv_content = (
        b"employee_code,email,full_name,department_code,max_hours_per_day,max_weekly_hours\n"
        b"EMP_X1,faculty1@timewise.edu,Dr. One,CS,5,20\n"
        b"EMP_X1,faculty2@timewise.edu,Dr. Two,CS,5,20\n"  # Duplicate EMP_X1
    )

    async with AsyncSessionLocal() as session:
        preview = await ImporterService.parse_and_validate(
            content=csv_content,
            filename="teachers_dup.csv",
            entity_type=EntityImportType.TEACHERS,
            db_session=session,
        )

    assert preview.is_committable is False
    assert any("Duplicate employee code" in e.error_message for e in preview.errors)


@pytest.mark.asyncio
async def test_importer_detects_foreign_key_failures():
    """Verifies that non-existent department or section references are rejected."""
    csv_content = (
        b"code,name,credits,subject_type,required_room_type,department_code\n"
        b"BIO101,Cell Biology,3,THEORY,LECTURE_HALL,NON_EXISTENT_DEPT\n"
    )

    async with AsyncSessionLocal() as session:
        preview = await ImporterService.parse_and_validate(
            content=csv_content,
            filename="subjects_bad_fk.csv",
            entity_type=EntityImportType.SUBJECTS,
            db_session=session,
        )

    assert preview.is_committable is False
    assert any("Department code 'NON_EXISTENT_DEPT' not found" in e.error_message for e in preview.errors)


@pytest.mark.asyncio
async def test_template_generation():
    """Verifies CSV and Excel template generation generates non-empty byte arrays."""
    csv_bytes, csv_name, csv_mime = ImporterService.generate_template(EntityImportType.ROOMS, "csv")
    assert len(csv_bytes) > 0
    assert "room_number" in csv_bytes.decode("utf-8")
    assert csv_mime == "text/csv"

    xlsx_bytes, xlsx_name, xlsx_mime = ImporterService.generate_template(EntityImportType.ROOMS, "xlsx")
    assert len(xlsx_bytes) > 0
    assert xlsx_name.endswith(".xlsx")
