# TIMEVERSE (TIMEWISE) — Data Nexus Final-Round Master Demo Guide

This document provides complete instructions for evaluating and demonstrating **TIMEVERSE (TIMEWISE)** during the Data Nexus Final Round presentation.

---

## 1. Executive Summary & Problem Solved

### The Problem
Higher education institutions face significant administrative friction:
1. **Scheduling Complexity**: Balancing 40+ faculty workloads, classroom capacities, multi-cohort subject requirements, and non-overlapping lab blocks manually creates clashes.
2. **Disruption Cascade**: A single faculty leave or emergency room maintenance triggers unplanned schedule chaos across cohorts.
3. **Communication Latency & Alert Fatigue**: Timetable modifications are often sent via chaotic chat groups or static notice boards, leading to missed lectures and attendance disputes.

### The TIMEVERSE Solution
TIMEVERSE provides a cohesive, full-lifecycle timetable platform:
- **Constraint-Satisfaction Engine**: Uses Google OR-Tools CP-SAT to generate mathematically clash-free schedules in seconds.
- **Manual Timetable Planner**: Interactive Weekly Matrix Grid and Daily Timeline Views with real-time preflight conflict detection (double-booking of teachers, rooms, and cohorts).
- **Official Announcements & Dynamic Alerts**: Administrative notice broadcaster with role-targeted delivery (All, Students, Faculty, Staff) and category tagging (`TIMETABLE_CHANGE`, `ACADEMIC_NOTICE`, etc.).
- **What-If Impact Simulator**: Simulates disruptions (faculty absence, room outage) in an isolated sandbox with automated recovery proposals.
- **Atomic Multi-Tier Approvals**: Faculty reschedule and leave workflows routed with coordinator/HOD sign-off.
- **Kristu Jayanti College Aesthetic**: Clean, responsive white-and-blue portal UX with tailored dashboards for Students, Faculty, Coordinators, HODs, and Administrators.

---

## 2. Technology Stack

| Layer | Technologies |
|---|---|
| **Frontend** | Next.js 14.2 (App Router), React 18, TypeScript, Tailwind CSS, Lucide Icons, Headless UI |
| **Backend** | FastAPI 0.115, Python 3.12, Async SQLAlchemy 2.0, Pydantic V2 Settings, Alembic |
| **Constraint Solver** | Google OR-Tools CP-SAT (Constraint Programming Satisfiability Engine) |
| **Database** | SQLite (`timewise_dev.db` with `aiosqlite`) for zero-dependency local demo; PostgreSQL 16+ production ready |
| **Authentication & RBAC** | JWT Bearer tokens with 7 role personas, granular hierarchical permission guards |

---

## 3. Demo User Accounts

All demo accounts share the password: **`DemoPass@2026!`**

| Persona | Role | Email | Key Capabilities |
|---|---|---|---|
| **Administrator** | `ADMIN` | `admin@timewise.edu` | Full administrative control, publish official announcements, user management, system metrics |
| **Coordinator** | `COORDINATOR` | `coord.cs@timewise.edu` | Generate timetables via CP-SAT, manual session CRUD, conflict resolution, approve requests |
| **Faculty / Teacher** | `TEACHER` | `teacher.sharma@timewise.edu` | View personal teaching schedule, submit reschedule/leave requests, broadcast class notices |
| **Student** | `STUDENT` | `student.aarav@timewise.edu` | View enrolled cohort timetable, today's schedule timeline, hall tickets, fee ledger, announcements |
| **Head of Department** | `HOD` | `hod.cs@timewise.edu` | Final timetable sign-off, departmental analytics, administrative overrides |
| **Class Representative** | `CR` | `cr.cs3a@timewise.edu` | View cohort timetable, broadcast class updates to cohort |
| **Academic Mentor** | `MENTOR` | `mentor.rao@timewise.edu` | View advisee schedule, academic counseling and advising slots |

---

## 4. How to Run Locally

### Terminal 1: Backend API (FastAPI)
```powershell
cd "c:\ML project\Timeverse (data nexus )\backend"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
- API Root: `http://localhost:8000`
- Swagger Interactive Docs: `http://localhost:8000/docs`
- Health Check: `http://localhost:8000/api/v1/health`

### Terminal 2: Frontend Client (Next.js)
```powershell
cd "c:\ML project\Timeverse (data nexus )\frontend"
npm run dev
```
- Web Application: `http://localhost:3000`
- Login Page: `http://localhost:3000/login`

*(Alternatively, to run the production build tested with `npm run build`):*
```powershell
cd "c:\ML project\Timeverse (data nexus )\frontend"
npm start
```

---

## 5. Step-by-Step Final-Round Demonstration Script

Follow this 7-step presentation flow to showcase the full end-to-end capabilities within 5–7 minutes:

### Step 1: Login & Student Dashboard Experience (Student Persona)
1. Navigate to `http://localhost:3000/login`.
2. Click the quick-fill pill **"Student"** (or enter `student.aarav@timewise.edu` / `DemoPass@2026!`) and click **"Sign In"**.
3. **Showcase**:
   - Clean Kristu Jayanti white-and-blue university portal design.
   - **Student Profile Header**: Cohort `CS-3A`, Roll `24CS014`, Semester III, CGPA 8.74, Attendance 91.2%.
   - **Academic Credentials**: Hall Ticket status `AVAILABLE`, Fee dues cleared, Academic Mentor Prof. Sneha Rao.
   - **Your Next Upcoming Class Card**: "CS301 — Data Structures & Algorithms", Room LH-101 with Instructor Prof. Vikram Sharma.
   - **Today's Class Schedule (Monday)**: Mon-Fri slots dynamically listed.
   - **Latest Academic Announcements**: Live campus notices.

### Step 2: Student Timetable Navigation (Weekly Grid & Daily Timeline)
1. Click **"Timetables"** in the sidebar navigation (or click "View Weekly Schedule").
2. **Showcase**:
   - Select section `CS-3A` or `CS-3B`.
   - **Weekly Matrix View**: 6-period daily grid showing Subject codes, Teacher badges, Room tags, and lunch breaks.
   - Switch to **"Daily Timeline View"**: Click day pills (`Monday`, `Tuesday`, `Wednesday`, etc.) to view hour-by-hour periods with start/end times and room occupancy.
   - Note that for Students, manual modification controls (`+ Add Class Entry`, edit, delete) are hidden to maintain academic integrity.

### Step 3: Faculty Schedule & Reschedule Request (Faculty Persona)
1. Click user profile in top-right &rarr; **"Sign Out"** (or switch user).
2. Login as **Faculty**: `teacher.sharma@timewise.edu` / `DemoPass@2026!`.
3. **Showcase**:
   - Faculty-tailored dashboard showing **Total Weekly Teaching Hours**, Assigned Classes, and quick action **"Broadcast Class Notice"**.
   - Navigate to **"Approvals"** (`/approvals`): View existing reschedule and leave requests.
   - Click **"Request Schedule Swap"**: Form allowing faculty to pick a source session, target date/period, target teacher, and reason.

### Step 4: Administrator / Coordinator Timetable Management & Conflict Preflight
1. Sign out and log in as **Coordinator**: `coord.cs@timewise.edu` / `DemoPass@2026!`.
2. Navigate to **"Timetables"** (`/timetables`).
3. **Showcase Authorized Scheduling Tools**:
   - Notice the **"+ Add Class Entry"** button is visible.
   - Hover over existing class cards to reveal the **Pencil (Edit)** and **Trash (Delete)** buttons.
4. **Demonstrate Conflict Detection**:
   - Click **"+ Add Class Entry"**.
   - Select Day: `Monday`, Period: `Period 1 (08:30 - 09:20)`, Subject: `Operating Systems`, Teacher: `Prof. Vikram Sharma` (who is ALREADY teaching Data Structures in Period 1 on Monday!).
   - Observe the live **Conflict Warning Banner**:
     > ⚠️ *"Teacher Double-Booking: Prof. Vikram Sharma is already assigned to CS301 in Room LH-101 during this slot."*
   - Change Teacher or Period to a free slot &rarr; conflict banner clears &rarr; Click **"Schedule Class"** &rarr; Entry instantly persists in the database.
   - Refresh the page to prove persistence!

### Step 5: Official Announcements Publishing (Admin Persona)
1. Sign out and log in as **Administrator**: `admin@timewise.edu` / `DemoPass@2026!`.
2. Navigate to **"Alerts & Notices"** (`/alerts`).
3. Click the **"Official Announcements"** tab.
4. Filter by category: `All`, `Timetable Change`, `Academic Notice`, `Examination`, `Emergency`.
5. Click **"+ Publish Announcement"**.
6. Enter:
   - **Title**: `Urgent: Room Shift for End-Semester Lab Evaluations`
   - **Category**: `TIMETABLE_CHANGE`
   - **Target Audience**: `ALL`
   - **Priority**: `Urgent`
   - **Content**: `All Computer Graphics practical sessions for CS-3A scheduled in Room LAB-201 are temporarily shifted to LAB-202 effective tomorrow.`
   - Check **"Pin to top of notice board"** and **"Dispatch high-priority alert to recipient feeds"**.
   - Click **"Publish Announcement"**.
7. Observe the announcement appearing with the red **PINNED** and **URGENT** badges.

### Step 6: Recipient Verification (Student sees Announcement & Alert)
1. Switch back to **Student** (`student.aarav@timewise.edu`).
2. Navigate to **"Alerts & Notices"** (`/alerts`):
   - In **"Official Announcements"**: The newly published announcement is visible at the very top.
   - In **"Personal Alerts"**: The high-priority alert appears in their inbox with **"Mark as Read"** functionality.
   - Dashboard (`/dashboard`) shows the updated notice card.

### Step 7: What-If Impact Simulator (Bonus Technical Showcase)
1. Log in as **Coordinator** (`coord.cs@timewise.edu`).
2. Navigate to **"Impact Simulator"** (`/simulator`).
3. Simulate an unforeseen disruption:
   - Select `Faculty Absenteeism`: Select `Prof. Vikram Sharma` for tomorrow.
   - Run Simulation &rarr; System detects affected lectures (e.g., CS301 for CS-3A).
   - Generates automated resolution options: Substitute Teacher, Room reallocation, or Asynchronous Assignment.

---

## 6. Verification and Test Results

### Backend Test Suite
Executed using `pytest` inside the Python virtual environment:
```
============================= test session starts =============================
platform win32 -- Python 3.12.13, pytest-8.4.2
collected 61 items

backend\tests\test_alerts_and_portal.py ....                             [  6%]
backend\tests\test_announcements.py .                                    [  8%]
backend\tests\test_approvals_workflow.py .....                           [ 16%]
backend\tests\test_auth_rbac.py .............                            [ 37%]
backend\tests\test_health.py .....                                       [ 45%]
backend\tests\test_impact_simulator.py ...                               [ 50%]
backend\tests\test_importer_preflight.py .....                           [ 59%]
backend\tests\test_milestone6_e2e_scenarios.py ......                    [ 68%]
backend\tests\test_scheduler_engine.py ....                              [ 75%]
backend\tests\test_scheduling_api.py ..                                  [ 78%]
backend\tests\test_scheduling_crud.py ..                                 [ 81%]
backend\tests\test_timetable_validator.py ........                       [ 95%]
backend\tests\test_versioning_and_rollback.py ...                        [100%]

============================= 61 passed in 16.47s =============================
```

### Frontend Production Build
Executed using `npm run build` in the `frontend` directory:
```
▲ Next.js 14.2.15
✓ Compiled successfully
✓ Linting and checking validity of types passed
✓ Generating static pages (15/15)
✓ Finalizing page optimization
Exit Code: 0 (Clean Build)
```

---

## 7. Architecture & Compliance

- **Role-Based Access Control**: Strict multi-tier enforcement in FastAPI dependency injection (`PermissionGuard`).
- **Data Integrity**: Relational SQLite / PostgreSQL schema managed by Alembic migrations with explicit foreign keys, indexes, and unique constraints.
- **Visual Design**: Strict adherence to the Kristu Jayanti white-and-blue theme tokens (`#1261A0` primary blue, `#0E4E82` hover blue, `#17324D` deep navy headings, `#F7F9FC` background).
