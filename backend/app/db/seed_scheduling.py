from datetime import time

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_password_hash
from app.db.seed import DEFAULT_DEMO_PASSWORD
from app.models.cohort import CohortSection
from app.models.curriculum import Subject, SubjectRequirement, SubjectTypeEnum
from app.models.infrastructure import Room, RoomTypeEnum, TimeSlot
from app.models.preference import SchedulingPreference
from app.models.teacher import Teacher, TeacherAvailability
from app.models.timetable import (
    SessionStatusEnum,
    Timetable,
    TimetableSession,
    TimetableStatusEnum,
)
from app.models.user import User, UserRoleEnum


async def seed_scheduling_entities(db: AsyncSession) -> dict[str, int]:
    """
    Seeds deterministic synthetic college scheduling data for local development & automated tests:
    - Time Slots (Mon-Fri, Periods 1-6 with Period 4 Lunch Break)
    - Lecture Halls & Computer Labs
    - Teachers with availability and preferences
    - Subjects (Theory & Lab)
    - Cohort Sections (CS-3A, CS-3B)
    - Subject Requirements
    - Departmental Scheduling Preferences
    """
    counts = {}

    # 1. Time Slots
    # 5 Days (Mon=1 .. Fri=5), 6 Periods each. Period 4 is lunch break.
    slots_created = 0
    slot_ids = []
    period_times = [
        (1, time(8, 30), time(9, 30)),
        (2, time(9, 30), time(10, 30)),
        (3, time(10, 45), time(11, 45)),
        (4, time(11, 45), time(12, 45)),  # Break
        (5, time(13, 30), time(14, 30)),
        (6, time(14, 30), time(15, 30)),
    ]

    for day in range(1, 6):
        for period, start_t, end_t in period_times:
            slot_id = f"ts_d{day}_p{period}"
            slot_ids.append(slot_id)
            stmt = select(TimeSlot).where(TimeSlot.id == slot_id)
            existing = (await db.execute(stmt)).scalars().first()
            if not existing:
                is_break = period == 4
                ts = TimeSlot(
                    id=slot_id,
                    institution_id="inst_01",
                    day_of_week=day,
                    period_number=period,
                    start_time=start_t,
                    end_time=end_t,
                    is_break=is_break,
                )
                db.add(ts)
                slots_created += 1

    await db.flush()
    counts["time_slots"] = slots_created

    # 2. Rooms
    rooms_spec = [
        {"id": "rm_lh101", "bldg": "Main Academic Block", "num": "LH-101", "cap": 60, "type": RoomTypeEnum.LECTURE_HALL},
        {"id": "rm_lh102", "bldg": "Main Academic Block", "num": "LH-102", "cap": 50, "type": RoomTypeEnum.LECTURE_HALL},
        {"id": "rm_lab1", "bldg": "Science & Tech Block", "num": "LAB-CS1", "cap": 50, "type": RoomTypeEnum.COMPUTER_LAB},
        {"id": "rm_lab2", "bldg": "Science & Tech Block", "num": "LAB-CS2", "cap": 50, "type": RoomTypeEnum.COMPUTER_LAB},
    ]
    rooms_created = 0
    for r in rooms_spec:
        stmt = select(Room).where(Room.id == r["id"])
        existing = (await db.execute(stmt)).scalars().first()
        if not existing:
            rm = Room(
                id=r["id"],
                institution_id="inst_01",
                building=r["bldg"],
                room_number=r["num"],
                capacity=r["cap"],
                room_type=r["type"],
                equipment=["Projector", "Audio System"] if r["type"] == RoomTypeEnum.LECTURE_HALL else ["Desktop PCs", "LAN", "Compiler Suite"],
                is_active=True,
            )
            db.add(rm)
            rooms_created += 1

    await db.flush()
    counts["rooms"] = rooms_created

    # 3. Teachers & Users
    teachers_spec = [
        {"uid": "usr_demo_teacher_sharma", "tid": "tch_sharma", "code": "EMP_T01", "name": "Dr. Rajesh Sharma", "email": "teacher.sharma@timewise.edu"},
        {"uid": "usr_teacher_gupta", "tid": "tch_gupta", "code": "EMP_T02", "name": "Prof. Anita Gupta", "email": "teacher.gupta@timewise.edu"},
        {"uid": "usr_teacher_patel", "tid": "tch_patel", "code": "EMP_T03", "name": "Dr. Vikram Patel", "email": "teacher.patel@timewise.edu"},
        {"uid": "usr_teacher_rao", "tid": "tch_rao", "code": "EMP_T04", "name": "Prof. Sneha Rao", "email": "teacher.rao@timewise.edu"},
    ]
    hashed_pw = get_password_hash(DEFAULT_DEMO_PASSWORD)
    teachers_created = 0

    for t in teachers_spec:
        u_stmt = select(User).where(User.id == t["uid"])
        user = (await db.execute(u_stmt)).scalars().first()
        if not user:
            user = User(
                id=t["uid"],
                institution_id="inst_01",
                email=t["email"],
                hashed_password=hashed_pw,
                full_name=t["name"],
                role=UserRoleEnum.TEACHER,
                is_active=True,
            )
            db.add(user)
            await db.flush()

        t_stmt = select(Teacher).where(Teacher.id == t["tid"])
        teacher = (await db.execute(t_stmt)).scalars().first()
        if not teacher:
            teacher = Teacher(
                id=t["tid"],
                user_id=user.id,
                department_id="dept_cs",
                employee_code=t["code"],
                max_hours_per_day=5,
                max_consecutive_hours=3,
                max_weekly_hours=20,
            )
            db.add(teacher)
            teachers_created += 1

    await db.flush()
    counts["teachers"] = teachers_created

    # 4. Teacher Availabilities (Sample: Friday afternoon unavailable for Dr. Sharma)
    sharma_unavail_stmt = select(TeacherAvailability).where(
        TeacherAvailability.teacher_id == "tch_sharma",
        TeacherAvailability.time_slot_id == "ts_d5_p6",
    )
    unavail = (await db.execute(sharma_unavail_stmt)).scalars().first()
    if not unavail:
        db.add(
            TeacherAvailability(
                id="tav_sharma_fri_p6",
                teacher_id="tch_sharma",
                time_slot_id="ts_d5_p6",
                is_available=False,
                preference_weight=-2,
                reason="Departmental Academic Committee Meeting",
            )
        )

    # 5. Cohort Sections: Section B
    sec_b_stmt = select(CohortSection).where(CohortSection.id == "sec_cs_3b")
    sec_cs_3b = (await db.execute(sec_b_stmt)).scalars().first()
    if not sec_cs_3b:
        sec_cs_3b = CohortSection(
            id="sec_cs_3b",
            department_id="dept_cs",
            academic_term_id="term_2026_odd",
            program_name="BSc Computer Science",
            year_level=3,
            section_name="B",
            student_count=38,
        )
        db.add(sec_cs_3b)
        await db.flush()

    # 6. Subjects
    subjects_spec = [
        {"id": "sub_cs301", "code": "CS301", "name": "Data Structures & Algorithms", "cred": 4, "type": SubjectTypeEnum.THEORY, "room": RoomTypeEnum.LECTURE_HALL},
        {"id": "sub_cs301l", "code": "CS301L", "name": "Data Structures Lab", "cred": 2, "type": SubjectTypeEnum.LABORATORY, "room": RoomTypeEnum.COMPUTER_LAB},
        {"id": "sub_cs302", "code": "CS302", "name": "Database Management Systems", "cred": 4, "type": SubjectTypeEnum.THEORY, "room": RoomTypeEnum.LECTURE_HALL},
        {"id": "sub_cs302l", "code": "CS302L", "name": "DBMS Lab", "cred": 2, "type": SubjectTypeEnum.LABORATORY, "room": RoomTypeEnum.COMPUTER_LAB},
        {"id": "sub_cs303", "code": "CS303", "name": "Computer Networks", "cred": 3, "type": SubjectTypeEnum.THEORY, "room": RoomTypeEnum.LECTURE_HALL},
        {"id": "sub_cs304", "code": "CS304", "name": "Operating Systems", "cred": 3, "type": SubjectTypeEnum.THEORY, "room": RoomTypeEnum.LECTURE_HALL},
    ]
    subjects_created = 0
    for s in subjects_spec:
        s_stmt = select(Subject).where(Subject.id == s["id"])
        existing = (await db.execute(s_stmt)).scalars().first()
        if not existing:
            subj = Subject(
                id=s["id"],
                department_id="dept_cs",
                code=s["code"],
                name=s["name"],
                credits=s["cred"],
                subject_type=s["type"],
                required_room_type=s["room"],
                is_active=True,
            )
            db.add(subj)
            subjects_created += 1

    await db.flush()
    counts["subjects"] = subjects_created

    # 7. Subject Requirements (CS-3A and CS-3B)
    requirements_spec = [
        # CS-3A
        {"id": "req_3a_cs301", "sec": "sec_cs_3a", "sub": "sub_cs301", "tch": "tch_sharma", "periods": 3, "room": "rm_lh101"},
        {"id": "req_3a_cs301l", "sec": "sec_cs_3a", "sub": "sub_cs301l", "tch": "tch_sharma", "periods": 2, "room": "rm_lab1"},
        {"id": "req_3a_cs302", "sec": "sec_cs_3a", "sub": "sub_cs302", "tch": "tch_gupta", "periods": 3, "room": "rm_lh101"},
        {"id": "req_3a_cs302l", "sec": "sec_cs_3a", "sub": "sub_cs302l", "tch": "tch_gupta", "periods": 2, "room": "rm_lab1"},
        {"id": "req_3a_cs303", "sec": "sec_cs_3a", "sub": "sub_cs303", "tch": "tch_patel", "periods": 3, "room": "rm_lh101"},
        {"id": "req_3a_cs304", "sec": "sec_cs_3a", "sub": "sub_cs304", "tch": "tch_rao", "periods": 3, "room": "rm_lh101"},
        # CS-3B
        {"id": "req_3b_cs301", "sec": "sec_cs_3b", "sub": "sub_cs301", "tch": "tch_sharma", "periods": 3, "room": "rm_lh102"},
        {"id": "req_3b_cs301l", "sec": "sec_cs_3b", "sub": "sub_cs301l", "tch": "tch_sharma", "periods": 2, "room": "rm_lab2"},
        {"id": "req_3b_cs302", "sec": "sec_cs_3b", "sub": "sub_cs302", "tch": "tch_gupta", "periods": 3, "room": "rm_lh102"},
        {"id": "req_3b_cs302l", "sec": "sec_cs_3b", "sub": "sub_cs302l", "tch": "tch_gupta", "periods": 2, "room": "rm_lab2"},
        {"id": "req_3b_cs303", "sec": "sec_cs_3b", "sub": "sub_cs303", "tch": "tch_patel", "periods": 3, "room": "rm_lh102"},
        {"id": "req_3b_cs304", "sec": "sec_cs_3b", "sub": "sub_cs304", "tch": "tch_rao", "periods": 3, "room": "rm_lh102"},
    ]
    reqs_created = 0
    for rq in requirements_spec:
        rq_stmt = select(SubjectRequirement).where(SubjectRequirement.id == rq["id"])
        existing = (await db.execute(rq_stmt)).scalars().first()
        if not existing:
            sreq = SubjectRequirement(
                id=rq["id"],
                cohort_section_id=rq["sec"],
                subject_id=rq["sub"],
                teacher_id=rq["tch"],
                required_sessions_per_week=rq["periods"],
                duration_periods=1,
                requires_consecutive_periods=False,
                preferred_room_id=rq["room"],
            )
            db.add(sreq)
            reqs_created += 1

    await db.flush()
    counts["requirements"] = reqs_created

    # 8. Department Scheduling Preferences
    pref_stmt = select(SchedulingPreference).where(SchedulingPreference.department_id == "dept_cs")
    pref = (await db.execute(pref_stmt)).scalars().first()
    if not pref:
        pref = SchedulingPreference(
            id="pref_dept_cs",
            department_id="dept_cs",
            weight_preferred_times=10,
            weight_balanced_daily_workload=15,
            weight_minimize_gaps=10,
            max_daily_sessions_per_teacher=5,
            max_daily_sessions_per_cohort=6,
            custom_rules={},
        )
        db.add(pref)

    await db.flush()

    # 9. Initial Master Published Timetable (v1.0)
    tt_stmt = select(Timetable).where(Timetable.id == "tt_dept_cs_master_v1")
    master_tt = (await db.execute(tt_stmt)).scalars().first()
    if not master_tt:
        from datetime import datetime, UTC
        master_tt = Timetable(
            id="tt_dept_cs_master_v1",
            department_id="dept_cs",
            academic_term_id="term_2026_odd",
            version_major=1,
            version_minor=0,
            status=TimetableStatusEnum.PUBLISHED,
            solver_status="OPTIMAL",
            solver_score={"objective_value": 0, "hard_conflicts": 0},
            created_by_user_id="usr_demo_admin",
            published_at=datetime.now(UTC),
            notes="Official Odd Semester 2026 Master Timetable — Verified Clash-Free",
        )
        db.add(master_tt)
        await db.flush()

        # Seed realistic sessions for CS-3A and CS-3B
        demo_sessions = [
            # Monday (Day 1)
            ("sess_m1_3a", "req_3a_cs301", "sec_cs_3a", "sub_cs301", "tch_sharma", "rm_lh101", "ts_d1_p1"),
            ("sess_m1_3b", "req_3b_cs302", "sec_cs_3b", "sub_cs302", "tch_gupta", "rm_lh102", "ts_d1_p1"),
            ("sess_m2_3a", "req_3a_cs302", "sec_cs_3a", "sub_cs302", "tch_gupta", "rm_lh101", "ts_d1_p2"),
            ("sess_m2_3b", "req_3b_cs301", "sec_cs_3b", "sub_cs301", "tch_sharma", "rm_lh102", "ts_d1_p2"),
            ("sess_m3_3a", "req_3a_cs303", "sec_cs_3a", "sub_cs303", "tch_patel", "rm_lh101", "ts_d1_p3"),
            ("sess_m3_3b", "req_3b_cs304", "sec_cs_3b", "sub_cs304", "tch_rao", "rm_lh102", "ts_d1_p3"),
            ("sess_m5_3a", "req_3a_cs301l", "sec_cs_3a", "sub_cs301l", "tch_sharma", "rm_lab1", "ts_d1_p5"),
            ("sess_m5_3b", "req_3b_cs303", "sec_cs_3b", "sub_cs303", "tch_patel", "rm_lh102", "ts_d1_p5"),
            ("sess_m6_3a", "req_3a_cs301l", "sec_cs_3a", "sub_cs301l", "tch_sharma", "rm_lab1", "ts_d1_p6"),
            ("sess_m6_3b", "req_3b_cs304", "sec_cs_3b", "sub_cs304", "tch_rao", "rm_lh102", "ts_d1_p6"),

            # Tuesday (Day 2)
            ("sess_t1_3a", "req_3a_cs304", "sec_cs_3a", "sub_cs304", "tch_rao", "rm_lh101", "ts_d2_p1"),
            ("sess_t1_3b", "req_3b_cs301l", "sec_cs_3b", "sub_cs301l", "tch_sharma", "rm_lab2", "ts_d2_p1"),
            ("sess_t2_3a", "req_3a_cs303", "sec_cs_3a", "sub_cs303", "tch_patel", "rm_lh101", "ts_d2_p2"),
            ("sess_t2_3b", "req_3b_cs301l", "sec_cs_3b", "sub_cs301l", "tch_sharma", "rm_lab2", "ts_d2_p2"),
            ("sess_t3_3a", "req_3a_cs301", "sec_cs_3a", "sub_cs301", "tch_sharma", "rm_lh101", "ts_d2_p3"),
            ("sess_t3_3b", "req_3b_cs302", "sec_cs_3b", "sub_cs302", "tch_gupta", "rm_lh102", "ts_d2_p3"),
            ("sess_t5_3a", "req_3a_cs302l", "sec_cs_3a", "sub_cs302l", "tch_gupta", "rm_lab1", "ts_d2_p5"),
            ("sess_t5_3b", "req_3b_cs301", "sec_cs_3b", "sub_cs301", "tch_sharma", "rm_lh102", "ts_d2_p5"),
            ("sess_t6_3a", "req_3a_cs302l", "sec_cs_3a", "sub_cs302l", "tch_gupta", "rm_lab1", "ts_d2_p6"),
            ("sess_t6_3b", "req_3b_cs303", "sec_cs_3b", "sub_cs303", "tch_patel", "rm_lh102", "ts_d2_p6"),

            # Wednesday (Day 3)
            ("sess_w1_3a", "req_3a_cs302", "sec_cs_3a", "sub_cs302", "tch_gupta", "rm_lh101", "ts_d3_p1"),
            ("sess_w1_3b", "req_3b_cs303", "sec_cs_3b", "sub_cs303", "tch_patel", "rm_lh102", "ts_d3_p1"),
            ("sess_w2_3a", "req_3a_cs301", "sec_cs_3a", "sub_cs301", "tch_sharma", "rm_lh101", "ts_d3_p2"),
            ("sess_w2_3b", "req_3b_cs304", "sec_cs_3b", "sub_cs304", "tch_rao", "rm_lh102", "ts_d3_p2"),
            ("sess_w3_3a", "req_3a_cs304", "sec_cs_3a", "sub_cs304", "tch_rao", "rm_lh101", "ts_d3_p3"),
            ("sess_w3_3b", "req_3b_cs301", "sec_cs_3b", "sub_cs301", "tch_sharma", "rm_lh102", "ts_d3_p3"),
            ("sess_w5_3a", "req_3a_cs303", "sec_cs_3a", "sub_cs303", "tch_patel", "rm_lh101", "ts_d3_p5"),
            ("sess_w5_3b", "req_3b_cs302l", "sec_cs_3b", "sub_cs302l", "tch_gupta", "rm_lab2", "ts_d3_p5"),
            ("sess_w6_3a", "req_3a_cs301", "sec_cs_3a", "sub_cs301", "tch_sharma", "rm_lh101", "ts_d3_p6"),
            ("sess_w6_3b", "req_3b_cs302l", "sec_cs_3b", "sub_cs302l", "tch_gupta", "rm_lab2", "ts_d3_p6"),

            # Thursday (Day 4)
            ("sess_th1_3a", "req_3a_cs303", "sec_cs_3a", "sub_cs303", "tch_patel", "rm_lh101", "ts_d4_p1"),
            ("sess_th1_3b", "req_3b_cs301", "sec_cs_3b", "sub_cs301", "tch_sharma", "rm_lh102", "ts_d4_p1"),
            ("sess_th2_3a", "req_3a_cs304", "sec_cs_3a", "sub_cs304", "tch_rao", "rm_lh101", "ts_d4_p2"),
            ("sess_th2_3b", "req_3b_cs302", "sec_cs_3b", "sub_cs302", "tch_gupta", "rm_lh102", "ts_d4_p2"),
            ("sess_th3_3a", "req_3a_cs301", "sec_cs_3a", "sub_cs301", "tch_sharma", "rm_lh101", "ts_d4_p3"),
            ("sess_th3_3b", "req_3b_cs303", "sec_cs_3b", "sub_cs303", "tch_patel", "rm_lh102", "ts_d4_p3"),
            ("sess_th5_3a", "req_3a_cs302", "sec_cs_3a", "sub_cs302", "tch_gupta", "rm_lh101", "ts_d4_p5"),
            ("sess_th5_3b", "req_3b_cs304", "sec_cs_3b", "sub_cs304", "tch_rao", "rm_lh102", "ts_d4_p5"),

            # Friday (Day 5)
            ("sess_f1_3a", "req_3a_cs301", "sec_cs_3a", "sub_cs301", "tch_sharma", "rm_lh101", "ts_d5_p1"),
            ("sess_f1_3b", "req_3b_cs302", "sec_cs_3b", "sub_cs302", "tch_gupta", "rm_lh102", "ts_d5_p1"),
            ("sess_f2_3a", "req_3a_cs302", "sec_cs_3a", "sub_cs302", "tch_gupta", "rm_lh101", "ts_d5_p2"),
            ("sess_f2_3b", "req_3b_cs301", "sec_cs_3b", "sub_cs301", "tch_sharma", "rm_lh102", "ts_d5_p2"),
            ("sess_f3_3a", "req_3a_cs303", "sec_cs_3a", "sub_cs303", "tch_patel", "rm_lh101", "ts_d5_p3"),
            ("sess_f3_3b", "req_3b_cs304", "sec_cs_3b", "sub_cs304", "tch_rao", "rm_lh102", "ts_d5_p3"),
            ("sess_f5_3a", "req_3a_cs304", "sec_cs_3a", "sub_cs304", "tch_rao", "rm_lh101", "ts_d5_p5"),
            ("sess_f5_3b", "req_3b_cs303", "sec_cs_3b", "sub_cs303", "tch_patel", "rm_lh102", "ts_d5_p5"),
        ]

        from app.models.timetable import TimetableSession, SessionStatusEnum
        for sid, rid, sec, sub, tch, rm, ts in demo_sessions:
            session_obj = TimetableSession(
                id=sid,
                timetable_id="tt_dept_cs_master_v1",
                requirement_id=rid,
                cohort_section_id=sec,
                subject_id=sub,
                teacher_id=tch,
                room_id=rm,
                time_slot_id=ts,
                status=SessionStatusEnum.OFFICIAL,
            )
            db.add(session_obj)

        counts["master_sessions"] = len(demo_sessions)

    # 10. Seed Sample Announcements
    from app.models.announcement import (
        Announcement,
        AnnouncementCategoryEnum,
        AnnouncementTargetAudienceEnum,
    )
    from app.models.alert import Alert, AlertSeverityEnum
    from datetime import datetime, UTC

    ann_stmt = select(Announcement).where(Announcement.id == "ann_01")
    existing_ann = (await db.execute(ann_stmt)).scalars().first()
    if not existing_ann:
        sample_announcements = [
            Announcement(
                id="ann_01",
                title="Mid-Term Examination Schedule & Hall Ticket Clearance",
                content="The mid-semester examination timetable for all B.Tech and BSc programmes has been uploaded. Ensure all departmental fee clearances are settled prior to hall ticket printing.",
                category=AnnouncementCategoryEnum.EXAMINATION,
                severity=AlertSeverityEnum.HIGH,
                target_audience=AnnouncementTargetAudienceEnum.STUDENTS,
                department_id="dept_cs",
                author_user_id="usr_demo_admin",
                is_published=True,
                is_pinned=True,
                published_at=datetime.now(UTC),
            ),
            Announcement(
                id="ann_02",
                title="Odd Semester 2026 Master Timetable (v1.0) Officially Published",
                content="The master timetable version 1.0 has been validated clash-free by the Academic Scheduling Committee and is now live across student and faculty portals.",
                category=AnnouncementCategoryEnum.TIMETABLE_CHANGE,
                severity=AlertSeverityEnum.INFORMATIONAL,
                target_audience=AnnouncementTargetAudienceEnum.ALL,
                department_id="dept_cs",
                author_user_id="usr_demo_admin",
                is_published=True,
                is_pinned=False,
                published_at=datetime.now(UTC),
            ),
            Announcement(
                id="ann_03",
                title="AI & Cloud Computing Research Colloquium",
                content="Department of Computer Science invites faculty and final year researchers to the annual research colloquium on distributed systems and impact optimization.",
                category=AnnouncementCategoryEnum.ACADEMIC_NOTICE,
                severity=AlertSeverityEnum.INFORMATIONAL,
                target_audience=AnnouncementTargetAudienceEnum.FACULTY,
                department_id="dept_cs",
                author_user_id="usr_demo_hod_cs",
                is_published=True,
                is_pinned=False,
                published_at=datetime.now(UTC),
            ),
            Announcement(
                id="ann_04",
                title="Campus Infrastructure: Lab CS-1 Hardware Upgrade",
                content="Computer Lab CS-1 workstations have been updated with high-performance compilers and dual monitors. All lab sessions proceed as scheduled.",
                category=AnnouncementCategoryEnum.INSTITUTIONAL,
                severity=AlertSeverityEnum.INFORMATIONAL,
                target_audience=AnnouncementTargetAudienceEnum.ALL,
                department_id="dept_cs",
                author_user_id="usr_demo_coord_cs",
                is_published=True,
                is_pinned=False,
                published_at=datetime.now(UTC),
            ),
        ]
        for a in sample_announcements:
            db.add(a)

        # Also add initial Alerts for demo users
        initial_alerts = [
            Alert(
                id="alt_demo_01",
                recipient_user_id="usr_demo_student_aarav",
                event_type="EXAMINATION",
                title="Hall Ticket Ready for Download",
                message="Your Odd Semester 2026 Hall Ticket is now cleared and available in the Academics tab.",
                severity=AlertSeverityEnum.HIGH,
                is_read=False,
            ),
            Alert(
                id="alt_demo_02",
                recipient_user_id="usr_demo_student_aarav",
                event_type="TIMETABLE_CHANGE",
                title="Master Timetable v1.0 Live",
                message="Your weekly schedule for Section CS-3A is now published and active.",
                severity=AlertSeverityEnum.INFORMATIONAL,
                is_read=False,
            ),
            Alert(
                id="alt_demo_03",
                recipient_user_id="usr_demo_teacher_sharma",
                event_type="TIMETABLE_CHANGE",
                title="Assigned Teaching Schedule Finalized",
                message="You are assigned 12 weekly lecture hours across Section CS-3A and CS-3B.",
                severity=AlertSeverityEnum.INFORMATIONAL,
                is_read=False,
            ),
            Alert(
                id="alt_demo_04",
                recipient_user_id="usr_demo_admin",
                event_type="SYSTEM",
                title="Full System Health Audit Normal",
                message="Constraint solver CP-SAT completed preflight verification with 0 hard clashes.",
                severity=AlertSeverityEnum.INFORMATIONAL,
                is_read=True,
            ),
        ]
        for alt in initial_alerts:
            db.add(alt)

    await db.commit()
    return counts

