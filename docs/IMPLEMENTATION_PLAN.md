# TIMEWISE — Implementation Plan & Engineering Roadmap

**Version:** 1.0  
**Date:** October 2026  
**Status:** Approved for Implementation  
**Technology Stack:** React/Next.js 14+ (TypeScript) + FastAPI (Python 3.12+) + Google OR-Tools CP-SAT + PostgreSQL 16+ + Alembic + Redis

---

## 1. Architectural Strategy & Frontend Selection Justification

### 1.1 Technical Stack Confirmation
As established in `TIMEWISE_Tech_Stack_v1.docx` and the project requirements:
* **Production-Style Split Architecture:** The system implements a dedicated **React/Next.js frontend** and **FastAPI backend**.
* **Streamlit Decision:** Streamlit is intentionally **excluded** from implementation. While suitable for quick single-user prototypes, Streamlit cannot cleanly support:
  1. True multi-user production portals with independent client sessions and server-side RBAC token boundaries.
  2. The custom university portal design system documented in `TIMEWISE-Design-Documentation.docx` (persistent sidebar, responsive mobile drawers, breadcrumbs, modal dialogs, and high-density timetable grids).
  3. Real-time in-app notification toasts and sub-second grid updates without full-page re-renders.
  4. Building and maintaining both Streamlit and React frontends simultaneously wastes engineering capacity. A unified Next.js + FastAPI stack delivers an enterprise-grade solution from Day 1.

---

## 2. Directory Structure & Codebase Layout

```
timewise/
├── backend/
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/
│   ├── app/
│   │   ├── api/
│   │   │   ├── deps.py                  # Server-side auth & scope guards
│   │   │   └── v1/
│   │   │       ├── api_router.py
│   │   │       ├── endpoints/
│   │   │       │   ├── auth.py          # Sign-in, token refresh, profile
│   │   │       │   ├── users.py         # User administration
│   │   │       │   ├── departments.py   # Departments & academic terms
│   │   │       │   ├── rooms.py         # Rooms & physical infrastructure
│   │   │       │   ├── teachers.py      # Faculty, workload limits, preferences
│   │   │       │   ├── courses.py       # Subjects & requirements
│   │   │       │   ├── ingestion.py     # CSV/XLSX import & preflight validation
│   │   │       │   ├── timetables.py    # Timetable versions, grid queries
│   │   │       │   ├── optimizer.py     # CP-SAT solve execution & diagnostics
│   │   │       │   ├── simulator.py     # What-If Impact Simulator sandbox
│   │   │       │   ├── approvals.py     # Change requests & HOD approval
│   │   │       │   ├── issues.py        # CR / Staff issue reporting
│   │   │       │   ├── alerts.py        # Targeted in-app notification center
│   │   │       │   ├── study_blocks.py  # Personal student study blocks
│   │   │       │   ├── analytics.py     # Room utilization & teacher workload
│   │   │       │   └── audit.py         # Audit log inspection
│   │   ├── core/
│   │   │   ├── config.py                # Pydantic Settings
│   │   │   ├── security.py              # Argon2id & JWT issuance
│   │   │   ├── logging.py               # Structured JSON logger
│   │   │   └── exceptions.py            # RFC 7807 problem details
│   │   ├── db/
│   │   │   ├── base.py
│   │   │   └── session.py               # Async SQLAlchemy engine
│   │   ├── models/                      # SQLAlchemy ORM models
│   │   ├── schemas/                     # Pydantic schemas (DTOs)
│   │   └── services/                    # Isolated domain logic
│   │       ├── auth/
│   │       ├── importer/
│   │       ├── validator/               # Independent hard constraint checker
│   │       ├── optimizer/               # Google OR-Tools CP-SAT formulation
│   │       ├── simulator/               # Impact analysis & alternative ranking
│   │       ├── approvals/
│   │       ├── notifications/
│   │       └── audit/
│   ├── data/
│   │   └── templates/                   # CSV and XLSX sample import files
│   ├── tests/
│   │   ├── conftest.py
│   │   ├── test_auth_rbac.py
│   │   ├── test_importer.py
│   │   ├── test_validator.py
│   │   ├── test_optimizer.py
│   │   ├── test_impact_simulator.py
│   │   ├── test_approvals_workflow.py
│   │   └── test_alerts_routing.py
│   ├── Dockerfile
│   ├── pyproject.toml
│   └── requirements.txt
├── frontend/
│   ├── public/
│   │   └── assets/
│   ├── src/
│   │   ├── app/                         # Next.js App Router
│   │   │   ├── (auth)/
│   │   │   │   └── login/
│   │   │   ├── (dashboard)/
│   │   │   │   ├── layout.tsx           # Global portal shell (sidebar, header)
│   │   │   │   ├── page.tsx             # Role-specific dashboard hub
│   │   │   │   ├── timetable/           # Interactive Day/Week Grid view
│   │   │   │   ├── simulator/           # What-If Impact Simulator UI
│   │   │   │   ├── approvals/           # HOD Request review & alternative diffs
│   │   │   │   ├── import/              # CSV/XLSX Upload & Preflight preview
│   │   │   │   ├── issues/              # Issue reporting & resolution
│   │   │   │   ├── alerts/              # Notification inbox & preferences
│   │   │   │   ├── analytics/           # Utilization charts & workload metrics
│   │   │   │   └── audit/               # Compliance audit viewer
│   │   ├── components/                  # Reusable UI components
│   │   │   ├── ui/                      # Buttons, Cards, Inputs, Modals, Badges
│   │   │   ├── timetable/               # Grid, slot cards, conflict highlights
│   │   │   ├── simulator/               # Diff panel, alternative cards
│   │   │   └── layout/                  # Sidebar, Header, Breadcrumbs, Drawer
│   │   ├── hooks/                       # Custom React hooks (useAuth, useTimetable)
│   │   ├── lib/                         # Axios client, auth token store, utils
│   │   ├── styles/                      # Design tokens (colors, typography)
│   │   └── types/                       # TypeScript interfaces
│   ├── package.json
│   ├── tsconfig.json
│   ├── tailwind.config.ts
│   └── Dockerfile
├── docs/                                # Architectural & specification documents
├── docker-compose.yml
└── README.md
```

---

## 3. Phased Implementation Roadmap

```
M0: Foundations & Scaffolding ──► M1: Auth & Server RBAC ──► M2: Ingestion & Preflight Validation
                                                                     │
                                                                     ▼
M5: Impact Simulator ◄── M4: Timetable Grid & Versions ◄── M3: Optimizer & Validator Subsystems
       │
       ▼
M6: Approvals & Workflow ──► M7: Targeted Alerts ──► M8: Analytics & Audit ──► M9: E2E Validation
```

### Phase 1: Foundations & Core Engines

#### Milestone 0: Project Scaffolding, Tooling & Database Foundation
* **Deliverables:**
  * Docker Compose environment orchestrating PostgreSQL 16, Redis 7, Backend, and Frontend.
  * FastAPI application scaffolding with Pydantic settings, async SQLAlchemy session handling, and structured JSON logging.
  * Next.js 14 project initialization with TypeScript, Tailwind CSS configured with TIMEWISE design tokens (#1261A0 primary blue, #17324D navy, #EAF3FB pale blue, #F7F9FC canvas).
  * Alembic configuration and initial migration initializing organization and user tables.
* **Exit Criteria:** `docker compose up` starts both servers; health check endpoints return 200 OK.

#### Milestone 1: Authentication & Server-Side RBAC Subsystem
* **Deliverables:**
  * User model, password hashing with Argon2id, and JWT issuance (`/api/v1/auth/login`, `/refresh`).
  * Server-side `PermissionChecker` dependency evaluating roles (`ADMIN`, `HOD`, `COORDINATOR`, `TEACHER`, `CR`, `STUDENT`) and departmental jurisdiction scopes.
  * Role simulation seeder populating test users for each of the 6 roles.
  * Next.js authentication context, route middleware, and login page adhering to portal design.
* **Exit Criteria:** Direct API requests to unauthorized endpoints return HTTP 403; token authentication succeeds with valid claims.

#### Milestone 2: Data Ingestion & Preflight Validation Engine
* **Deliverables:**
  * CSV/XLSX template generators and parsers (`pandas` + `openpyxl`).
  * Preflight validation service reporting row-level and field-level errors (missing keys, unknown teacher IDs, capacity < 1, duplicate records).
  * Data management endpoints and UI preview table showing valid rows in green and invalid rows in red with error messages.
  * Zero silent data loss guarantee: Batch rejects or requests correction if validation fails.
* **Exit Criteria:** Ingestion test suite verifies that invalid CSV rows are rejected with explicit field-level error messages.

---

### Phase 2: Scheduling, Optimization & Timetable Views

#### Milestone 3: Constraint Optimization & Independent Validation Subsystems
* **Deliverables:**
  * **Google OR-Tools CP-SAT Model (`app/services/optimizer/`):**
    * Hard constraints: No teacher double-booking, no room double-booking, no cohort clash, room capacity >= student count, lab room type match, availability adherence.
    * Soft constraints: Minimize teacher gaps, honor preferred slots, balance daily load.
    * Configurable solver timeout (default 60 seconds) and clear status outputs (`OPTIMAL`, `FEASIBLE`, `INFEASIBLE`, `TIMEOUT`).
    * Infeasibility diagnostic report pinpointing conflicting requirements.
  * **Independent Validation Engine (`app/services/validator/`):**
    * Pure Python validation module running independently of OR-Tools.
    * Detects double-bookings, capacity violations, and invalid room types with plain-language explanations.
* **Exit Criteria:** Validator passes 100% on generated feasible timetables and correctly identifies seeded hard conflicts.

#### Milestone 4: Timetable Views, Interactive Grid & Versioning
* **Deliverables:**
  * Relational storage of generated timetables and sessions with semantic versioning (`v1.0`).
  * Interactive responsive weekly grid component in Next.js:
    * Switchable views: Department master, Teacher personal, Room schedule, Cohort section.
    * Visual status indicators: Official, Tentative, Rescheduled.
    * Accessible keyboard navigation and mobile card stack for viewports < 640px.
  * Student personal study block CRUD integrated into student view.
* **Exit Criteria:** Responsive grid renders without horizontal overflow at 360px viewport; filters accurately isolate cohort and teacher schedules.

---

### Phase 3: What-If Simulation, Approvals & Workflows

#### Milestone 5: What-If Impact Simulator Subsystem
* **Deliverables:**
  * Impact Simulator service (`app/services/simulator/`):
    * Sandbox memory copy of active timetable; zero production writes.
    * Analyzes directly and indirectly affected sessions for a simulated disruption (e.g., room closure, teacher leave).
    * Evaluates feasibility and invokes local optimizer to generate up to 3 feasible alternatives ranked by penalty score.
  * Next.js Impact Simulator UI:
    * Side-by-side diff comparison between current and simulated schedules.
    * Trade-off summary cards explaining slot changes, teacher gaps, and room shifts.
* **Exit Criteria:** Simulation does not mutate active timetable records; generates ranked alternatives with trade-off metrics.

#### Milestone 6: Requests, Issue Reporting & Approval Workflow
* **Deliverables:**
  * **Faculty Change Request Flow:** Submit reschedule/swap request → System identifies affected sessions → Optimizer proposes alternatives.
  * **CR Issue Reporting Flow:** CR reports room locked/projector failure → Notification routed to Coordinator.
  * **HOD Approval Workflow:**
    * HOD reviews change request and selected alternative.
    * Atomic revalidation check immediately before database commit.
    * On approval: Creates new timetable version (e.g., `v1.0` → `v1.1`), archives previous version, commits session updates.
* **Exit Criteria:** Approving a change increments timetable version and atomic revalidation prevents concurrent double-booking.

---

### Phase 4: Targeted Alerts, Analytics, Audit & Hardening

#### Milestone 7: Smart Targeted Alerts & Notification Subsystem
* **Deliverables:**
  * Alert dispatch and routing engine (`app/services/notifications/`):
    * Dispatches alerts only to affected users (affected teacher, section CR, and enrolled students).
    * Severity levels: `CRITICAL`, `HIGH`, `MEDIUM`, `INFORMATIONAL`.
    * Privacy rule: Absence medical reasons stripped from student alerts.
    * Strict state tagging: Never claims a proposed change is official.
  * Redis-backed deduplication key (`hash(user_id, event_type, session_id)` with 5-minute cooldown).
  * Next.js Notification Drawer and Alert Center with read/unread filtering.
* **Exit Criteria:** Tests confirm unaffected students receive zero notifications; duplicate alerts within cooldown window are suppressed.

#### Milestone 8: Analytics, Audit Trail & Security Hardening
* **Deliverables:**
  * **Analytics Dashboard:**
    * Room utilization rates calculated transparently (`(occupied_hours / available_operating_hours) * 100`).
    * Faculty workload distribution charts.
    * Pending change requests and conflict resolution turnaround times.
  * **Immutable Audit Trail:**
    * Interceptor recording all mutations with actor ID, IP address, timestamp, and JSON before/after state diff.
    * Administrator audit log viewer with filtering.
  * **Accessibility & UI Hardening:**
    * WCAG 2.2 AA audit (color contrast >= 4.5:1, visible focus outlines, screen-reader labels).
* **Exit Criteria:** All sensitive administrative mutations produce immutable audit log entries; room utilization formulas validated.

#### Milestone 9: End-to-End Validation, Performance Benchmarking & Packaging
* **Deliverables:**
  * Automated E2E test suite running full user journeys.
  * Performance benchmarking: Solver execution on 1-department standard college dataset completes within 60 seconds.
  * Deployment configuration, README setup instructions, and database backup verification scripts.
* **Exit Criteria:** All acceptance criteria in `ACCEPTANCE_CHECKLIST.md` pass.

---

## 4. Risk Matrix & Mitigation Strategies

| Risk Description | Severity | Probability | Architectural Mitigation |
|:---|:---:|:---:|:---|
| **CP-SAT Solver Infeasibility / Timeout** | High | Medium | Enforce configurable solver timeout (60s); implement diagnostic relaxation pass identifying conflicting constraints; return actionable guidance to coordinator. |
| **Race Conditions During Change Approvals** | High | Low | Enforce database-level serializable isolation and run independent validator pass within the same database transaction immediately prior to committing approval. |
| **Alert Fatigue & Duplicate Notifications** | Medium | High | Target alerts strictly to affected cohort/teacher; implement Redis deduplication window (5 mins); batch non-critical notifications. |
| **Unapproved Changes Leaking to Students** | High | Low | Isolate states (`DRAFT`, `SIMULATED`, `PROPOSED`, `PUBLISHED`); student API queries strictly filter on `status = 'PUBLISHED'` and approved sessions only. |
| **Dirty or Inconsistent College Data Imports** | High | High | Preflight validation pipeline validates data row-by-row before database insertion; provides downloadable CSV templates with exact schemas. |
| **Privilege Escalation across Departments** | High | Low | Server-side dependency injection validates both role permissions and departmental foreign-key scopes on every endpoint. |

---
*End of Implementation Plan.*
