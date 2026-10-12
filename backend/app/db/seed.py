import os
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_password_hash
from app.models.cohort import CohortSection
from app.models.organization import AcademicTerm, Department, Institution
from app.models.user import (
    MentorAssignment,
    StudentEnrollment,
    User,
    UserDepartmentScope,
    UserRoleEnum,
)

# Configurable demo password without hardcoded production secrets
DEFAULT_DEMO_PASSWORD = os.getenv("DEMO_USER_PASSWORD", "DemoPass@2026!")


async def seed_demo_data(db: AsyncSession) -> dict[str, str]:
    """
    Seeds synthetic demo institution, departments, sections, and role-based test users.
    Returns mapping of role to user email for test automation.
    """
    # 1. Institution
    inst_stmt = select(Institution).where(Institution.id == "inst_01")
    inst = (await db.execute(inst_stmt)).scalars().first()
    if not inst:
        inst = Institution(
            id="inst_01",
            name="Kristu Jayanti College Autonomous",
            code="KJC",
            timezone="Asia/Kolkata",
            operating_hours={"start": "08:30", "end": "16:30", "days": [1, 2, 3, 4, 5, 6]},
        )
        db.add(inst)
        await db.flush()

    # 2. Departments
    dept_cs_stmt = select(Department).where(Department.id == "dept_cs")
    dept_cs = (await db.execute(dept_cs_stmt)).scalars().first()
    if not dept_cs:
        dept_cs = Department(
            id="dept_cs",
            institution_id="inst_01",
            name="Department of Computer Science",
            code="CS",
        )
        db.add(dept_cs)

    dept_ee_stmt = select(Department).where(Department.id == "dept_ee")
    dept_ee = (await db.execute(dept_ee_stmt)).scalars().first()
    if not dept_ee:
        dept_ee = Department(
            id="dept_ee",
            institution_id="inst_01",
            name="Department of Electronics Engineering",
            code="EE",
        )
        db.add(dept_ee)
    await db.flush()

    # 3. Academic Term
    term_stmt = select(AcademicTerm).where(AcademicTerm.id == "term_2026_odd")
    term = (await db.execute(term_stmt)).scalars().first()
    if not term:
        term = AcademicTerm(
            id="term_2026_odd",
            institution_id="inst_01",
            name="Odd Semester 2026-2027",
            start_date=date(2026, 7, 1),
            end_date=date(2026, 12, 15),
            is_active=True,
        )
        db.add(term)
        await db.flush()

    # 4. Cohort Sections
    sec_stmt = select(CohortSection).where(CohortSection.id == "sec_cs_3a")
    sec_cs_3a = (await db.execute(sec_stmt)).scalars().first()
    if not sec_cs_3a:
        sec_cs_3a = CohortSection(
            id="sec_cs_3a",
            department_id="dept_cs",
            academic_term_id="term_2026_odd",
            program_name="BSc Computer Science",
            year_level=3,
            section_name="A",
            student_count=45,
        )
        db.add(sec_cs_3a)

    sec_ee_stmt = select(CohortSection).where(CohortSection.id == "sec_ee_3a")
    sec_ee_3a = (await db.execute(sec_ee_stmt)).scalars().first()
    if not sec_ee_3a:
        sec_ee_3a = CohortSection(
            id="sec_ee_3a",
            department_id="dept_ee",
            academic_term_id="term_2026_odd",
            program_name="BTech Electronics",
            year_level=3,
            section_name="A",
            student_count=40,
        )
        db.add(sec_ee_3a)
    await db.flush()

    # 5. Synthetic Demo Users
    demo_users_spec = [
        {
            "id": "usr_demo_admin",
            "email": "admin@timewise.edu",
            "full_name": "Administrator Sister / Dean",
            "role": UserRoleEnum.ADMIN,
            "depts": [],
            "sections": [],
        },
        {
            "id": "usr_demo_hod_cs",
            "email": "hod.cs@timewise.edu",
            "full_name": "Dr. Joseph Varghese (HOD CS)",
            "role": UserRoleEnum.HOD,
            "depts": ["dept_cs"],
            "sections": [],
        },
        {
            "id": "usr_demo_coord_cs",
            "email": "coord.cs@timewise.edu",
            "full_name": "Prof. Anita Roy (Coordinator CS)",
            "role": UserRoleEnum.COORDINATOR,
            "depts": ["dept_cs"],
            "sections": [],
        },
        {
            "id": "usr_demo_teacher_sharma",
            "email": "teacher.sharma@timewise.edu",
            "full_name": "Dr. Rajesh Sharma (Faculty CS)",
            "role": UserRoleEnum.TEACHER,
            "depts": ["dept_cs"],
            "sections": [],
        },
        {
            "id": "usr_demo_cr_cs3a",
            "email": "cr.cs3a@timewise.edu",
            "full_name": "Ashutosh (CR CS-3A)",
            "role": UserRoleEnum.CR,
            "depts": ["dept_cs"],
            "sections": ["sec_cs_3a"],
        },
        {
            "id": "usr_demo_student_aarav",
            "email": "student.aarav@timewise.edu",
            "full_name": "Aarav Menon (Student CS-3A)",
            "role": UserRoleEnum.STUDENT,
            "depts": ["dept_cs"],
            "sections": ["sec_cs_3a"],
        },
        {
            "id": "usr_demo_mentor_rao",
            "email": "mentor.rao@timewise.edu",
            "full_name": "Prof. Sneha Rao (Mentor)",
            "role": UserRoleEnum.MENTOR,
            "depts": ["dept_cs"],
            "sections": [],
        },
    ]

    hashed_pw = get_password_hash(DEFAULT_DEMO_PASSWORD)

    for spec in demo_users_spec:
        user_stmt = select(User).where(User.email == spec["email"])
        user = (await db.execute(user_stmt)).scalars().first()
        if not user:
            user = User(
                id=spec["id"],
                institution_id="inst_01",
                email=spec["email"],
                hashed_password=hashed_pw,
                full_name=spec["full_name"],
                role=spec["role"],
                is_active=True,
            )
            db.add(user)
            await db.flush()

            for d_id in spec["depts"]:
                scope = UserDepartmentScope(
                    id=f"uds_{user.id}_{d_id}",
                    user_id=user.id,
                    department_id=d_id,
                    is_primary=True,
                )
                db.add(scope)

            for s_id in spec["sections"]:
                enrollment = StudentEnrollment(
                    id=f"enr_{user.id}_{s_id}",
                    student_user_id=user.id,
                    cohort_section_id=s_id,
                    is_active=True,
                )
                db.add(enrollment)

    # 6. Explicit Mentor Assignment (Prof. Sneha Rao -> Aarav Menon)
    mentor_stmt = select(MentorAssignment).where(
        MentorAssignment.mentor_user_id == "usr_demo_mentor_rao",
        MentorAssignment.student_user_id == "usr_demo_student_aarav",
    )
    assignment = (await db.execute(mentor_stmt)).scalars().first()
    if not assignment:
        assignment = MentorAssignment(
            id="mas_rao_aarav",
            mentor_user_id="usr_demo_mentor_rao",
            student_user_id="usr_demo_student_aarav",
            is_active=True,
        )
        db.add(assignment)

    # 7. College Scheduling Entities (Rooms, Slots, Teachers, Subjects, Requirements)
    from app.db.seed_scheduling import seed_scheduling_entities
    await seed_scheduling_entities(db)

    await db.commit()

    return {spec["role"].value: spec["email"] for spec in demo_users_spec}

