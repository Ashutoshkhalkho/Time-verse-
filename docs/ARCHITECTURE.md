# TIMEWISE — System Architecture & Technical Specification

**Version:** 1.0  
**Date:** October 2026  
**Status:** Approved for Implementation  
**Lead Architect:** Antigravity Engineering (TIMEWISE Core Team)

---

## 1. Executive Summary & Architectural Decisions

TIMEWISE is an intelligent college timetable planning, validation, impact simulation, and smart alert platform. Modern college operations suffer from brittle manual scheduling where a single faculty leave or room maintenance event triggers a cascading chain of room, cohort, and teacher conflicts. 

### 1.1 Core Architecture Decision
In accordance with the project requirements and technology stack documentation:
* **Frontend:** **React 18+ / Next.js 14+ (App Router)** with TypeScript, Tailwind CSS, and Vanilla CSS design tokens. A single production-grade frontend will be implemented following the Kristu Jayanti University-inspired portal design system documented in `TIMEWISE-Design-Documentation.docx`. (Streamlit is strictly avoided to eliminate parallel frontend maintenance).
* **Backend:** **Python 3.12+ with FastAPI**, structured asynchronously with strict separation of concerns into isolated modular domains.
* **Optimization Subsystem:** **Google OR-Tools CP-SAT (Constraint Programming - Satisfiability)** for deterministic, reproducible mathematical scheduling, hard constraint enforcement, and weighted soft-preference minimization.
* **Constraint Validation Subsystem:** An **independent Python validation engine** decoupled from OR-Tools. The validator acts as the ultimate gatekeeper: no timetable can be published or updated without passing hard-constraint validation.
* **Database & Persistence:** **PostgreSQL 16+** with **SQLAlchemy 2.0 (async)** ORM and **Alembic** for schema migrations.
* **Caching, Tasks & Pub/Sub:** **Redis 7+** with Celery/RQ or FastAPI background workers for solver execution, batch notification delivery, and alert deduplication caches.
* **Security & Authorization:** Server-enforced Role-Based Access Control (RBAC) with JSON Web Tokens (JWT, OAuth2 Bearer), row- and resource-level scoping (Institution, Department, Cohort, Self).

```
+---------------------------------------------------------------------------------------+
|                                    CLIENT TIER                                        |
|   Next.js 14+ SPA / SSR (TypeScript + Tailwind / Design Tokens + WCAG 2.2 AA)         |
|   Role Dashboards: Admin | HOD | Coordinator | Faculty | CR | Student                  |
+-------------------------------------------+-------------------------------------------+
                                            | HTTPS / WSS / REST API (JSON)
                                            v
+---------------------------------------------------------------------------------------+
|                                 APPLICATION TIER (FastAPI)                            |
|  +---------------------------------------------------------------------------------+  |
|  | Middleware: CORS | Request ID | Structured Logging | JWT Auth | Exception Filter|  |
|  +---------------------------------------------------------------------------------+  |
|  | API Routers (/api/v1):                                                          |  |
|  |  * /auth           * /departments     * /teachers        * /rooms               |  |
|  |  * /timetables     * /optimizer       * /simulator       * /approvals           |  |
|  |  * /issues         * /alerts          * /analytics       * /audit               |  |
|  +---------------------------------------------------------------------------------+  |
|  | Core Subsystems:                                                                |  |
|  |  1. Auth & RBAC Domain          2. Importer & Ingestion Engine                  |  |
|  |  3. Independent Validator Engine 4. CP-SAT Solver Wrapper                        |  |
|  |  5. Impact Simulator Engine     6. Workflow & Approval State Machine             |  |
|  |  7. Alert Routing & Deduplicator 8. Audit Logging Subsystem                     |  |
+------------------------------------+-----------------------------+--------------------+
                                     |                             |
                                     v                             v
+------------------------------------+-------+       +-------------+--------------------+
|            DATA TIER (PostgreSQL 16)       |       |            CACHE / BROKER        |
|  - Relational Schema (Alembic Managed)     |       |  Redis 7:                        |
|  - Timetable Versions & Slot Partitions    |       |  - Alert Deduplication Window    |
|  - Immutable Audit Event Ledger            |       |  - Long-running Solver Jobs      |
|  - Automated WAL Archiving & Daily Backups |       |  - WebSocket Connection Sessions |
+--------------------------------------------+       +----------------------------------+
```

---

## 2. Decoupled Modular Subsystems

To prevent domain entangling, logic is separated into independent packages under `backend/app/`:

```
backend/
├── app/
│   ├── api/                  # FastAPI routers and HTTP schemas
│   │   ├── v1/
│   │   │   ├── endpoints/    # Auth, timetables, optimizer, simulator, alerts, etc.
│   │   │   └── api_router.py
│   ├── core/                 # App configuration, security, exceptions, logging
│   │   ├── config.py         # Pydantic BaseSettings
│   │   ├── security.py       # JWT creation, password hashing (Argon2id)
│   │   ├── logging.py        # Structured JSON logger
│   │   └── exceptions.py     # RFC 7807 problem details
│   ├── db/                   # Database setup and session management
│   │   ├── base.py           # Declarative base
│   │   └── session.py        # Async engine & sessionmaker
│   ├── models/               # SQLAlchemy ORM database models
│   ├── schemas/              # Pydantic validation schemas (DTOs)
│   ├── services/             # Core business modules (Strictly Decoupled)
│   │   ├── auth/             # Token issuance, user verification, permission checks
│   │   ├── importer/         # CSV/XLSX preflight parsing and validation
│   │   ├── validator/        # Pure Python hard & soft constraint checker
│   │   ├── optimizer/        # Google OR-Tools CP-SAT formulation and solver
│   │   ├── simulator/        # What-if impact simulation and diff calculator
│   │   ├── approvals/        # Request lifecycle, state transitions, version bumping
│   │   ├── notifications/    # Alert routing, deduplication, in-app dispatch
│   │   └── audit/            # Immutable audit event recorder
│   └── tests/                # Unit, integration, solver, and RBAC tests
├── alembic/                  # Database migration scripts
│   └── versions/
├── Dockerfile
├── requirements.txt
└── pyproject.toml
```

### 2.1 Subsystem Responsibilities

1. **Scheduling Engine (`app/services/optimizer/`)**:
   * Translates institutional requirements, room capacities, teacher availabilities, and cohorts into a CP-SAT mathematical model.
   * Enforces hard constraints via `model.Add(...)`.
   * Formulates weighted soft constraints (minimizing teacher gaps, honoring time preferences, balancing daily workload).
   * Executes solver with configurable timeout (default: 60s) and returns status: `FEASIBLE`, `OPTIMAL`, `INFEASIBLE`, or `TIMEOUT`.
   * Never directly modifies published timetables; emits a candidate assignment structure.

2. **Validation Engine (`app/services/validator/`)**:
   * Independent verification logic that checks schedule candidate matrices against all hard constraints.
   * Operates completely independently of OR-Tools to guard against solver modeling oversights or database corruptions.
   * Runs:
     1. Prior to publishing any timetable draft.
     2. Immediately before committing any approved change request (atomic revalidation to prevent race conditions).
     3. As a background integrity monitor.
   * Returns a deterministic `ValidationReport` with passed flags and granular, human-readable conflict diagnostics.

3. **Database & Persistence (`app/db/` & `app/models/`)**:
   * Provides ACID transaction boundaries.
   * Maintains timetable versioning (`version_major.version_minor`).
   * Manages soft-delete and state tags (`DRAFT`, `SIMULATED`, `PROPOSED`, `PUBLISHED`, `ARCHIVED`).

4. **Authorization & RBAC (`app/services/auth/`)**:
   * Decodes JWT tokens and verifies user active status.
   * Enforces resource-level permission rules on FastAPI endpoints using dependency injection (`Depends(require_permission(...))`).
   * Prevents horizontal and vertical privilege escalation (e.g., HOD of Department A cannot approve timetables for Department B).

5. **Impact Simulator (`app/services/simulator/`)**:
   * Takes a proposed delta (e.g., room offline, teacher leave, session reschedule) and copies current schedule state into an isolated memory sandbox.
   * Identifies direct clashes (the swapped slot) and second-order cascading disruptions (rescheduled cohort slots).
   * Invokes the optimizer locally to generate up to 3 feasible alternative options, ranking them by soft-preference penalty score.
   * Guarantees zero write-back to production tables during simulation.

6. **Approvals & Workflow Engine (`app/services/approvals/`)**:
   * Manages state machine for change requests: `SUBMITTED` → `UNDER_REVIEW` → `ALTERNATIVES_PROPOSED` → `APPROVED` / `REJECTED` / `CANCELLED`.
   * Revalidates hard constraints within the same database transaction as the approval commit.
   * Clones current timetable into a newly incremented version, commits the updated session, and marks prior version as `ARCHIVED`.

7. **Notification & Alert Subsystem (`app/services/notifications/`)**:
   * Categorizes alerts into `CRITICAL`, `HIGH`, `MEDIUM`, and `INFORMATIONAL`.
   * Filters and targets recipients strictly based on session cohort and teacher assignment (avoiding alert fatigue).
   * Implements deduplication using Redis key locks (`hash(recipient_id, event_type, session_id)` with a 5-minute cooldown window).
   * Never leaks tentative/proposed changes or private absence reasons to student-facing channels.

8. **Audit Trail Subsystem (`app/services/audit/`)**:
   * Intercepts mutations on administrative entities, timetable versions, approvals, and imports.
   * Captures actor ID, IP address, timestamp, action type, resource reference, and structured JSON diffs (`before_state`, `after_state`).

---

## 3. End-to-End Timetable Lifecycle

The system enforces a rigid seven-step operational lifecycle:

```
[ 1. PLAN ]      Coordinator imports CSV/XLSX -> Preflight validation -> Configures constraints
      |
      v
[ 2. SOLVE ]     Coordinator runs CP-SAT Solver -> Emits Draft Candidate -> Diagnostics returned
      |
      v
[ 3. VALIDATE ]  Independent Validator runs Hard Constraint Check -> Must return 0 violations
      |
      v
[ 4. SIMULATE ]  Impact Simulator tests what-if scenarios or teacher change requests in sandbox
      |
      v
[ 5. APPROVE ]   HOD / Admin reviews request & alternatives -> Approves change
      |
      v
[ 6. PUBLISH ]   Atomic revalidation passes -> Version incremented (v1.0 -> v1.1) -> Published
      |
      v
[ 7. NOTIFY ]    Alert Engine calculates delta -> Dispatches targeted in-app alerts to affected users
```

---

## 4. Authentication, Authorization & Security Architecture

### 4.1 Authentication Workflow
* **Authentication Standard:** OAuth2 Password Bearer flow with JSON Web Tokens (JWT).
* **Password Hashing:** `Argon2id` (memory cost 64MB, time cost 3 iterations, parallelism 4) via `pwdlib` / `passlib`.
* **Access Tokens:** Signed with HMAC-SHA256 (`HS256`) or RS256, expiration: 30 minutes.
* **Refresh Tokens:** Cryptographically random 256-bit entropy stored in PostgreSQL, expiration: 7 days with rotation and revocation on logout.
* **Session Claims:**
  ```json
  {
    "sub": "usr_01J8X9V2M...",
    "email": "hod.cs@college.edu",
    "role": "HOD",
    "institution_id": "inst_01",
    "department_id": "dept_cs",
    "section_ids": [],
    "exp": 1728645000,
    "jti": "uuid-v4-token-id"
  }
  ```

### 4.2 Server-Side Resource Scoping
Authorization is enforced server-side via composable FastAPI dependency injectors:

```python
# Conceptual Architecture Pattern
@router.post("/departments/{dept_id}/timetables/{timetable_id}/publish")
async def publish_timetable(
    dept_id: str,
    timetable_id: str,
    current_user: User = Depends(get_current_active_user),
    auth_service: AuthService = Depends(get_auth_service)
):
    # Enforces role AND resource jurisdiction
    await auth_service.authorize(
        user=current_user,
        permission=Permission.TIMETABLE_PUBLISH,
        scope=DepartmentScope(department_id=dept_id)
    )
    ...
```

* Administrators hold global institution scope.
* HODs hold jurisdiction over their specific `department_id`.
* Timetable Coordinators hold schedule generation/proposal jurisdiction for their assigned department(s).
* Faculty have read access to their department and full view of their assigned sessions; write access is restricted to personal availability and change requests.
* Class Representatives (CRs) have read access to their cohort timetable and write access to report classroom/schedule issues.
* Students have read-only access strictly restricted to published timetables for their enrolled section and personal study block CRUD.

---

## 5. Error Handling & Diagnostic Architecture

All API endpoints follow RFC 7807 (Problem Details for HTTP APIs) to ensure client predictability:

```json
{
  "type": "https://timewise.internal/errors/hard-constraint-violation",
  "title": "Hard Constraint Violation During Revalidation",
  "status": 409,
  "detail": "Room 304 is double-booked for period 3 on Wednesday by CS-Section-A and EE-Section-B.",
  "instance": "/api/v1/timetables/tt_9281/publish",
  "code": "ROOM_DOUBLE_BOOKING",
  "conflicts": [
    {
      "entity_type": "room",
      "entity_id": "room_304",
      "conflicting_session_id": "sess_8102",
      "target_session_id": "sess_4910",
      "day": "WEDNESDAY",
      "period": 3
    }
  ],
  "timestamp": "2026-10-11T12:00:00Z"
}
```

### Infeasibility Diagnostics
When Google OR-Tools CP-SAT fails to discover a feasible solution within the time limit:
1. The solver returns `status = INFEASIBLE` or `TIMEOUT`.
2. The diagnostic analyzer runs constraint relaxation passes to identify the minimal conflicting subset (e.g., "Teacher Dr. Sharma required 18 lecture hours, but their availability mask only offers 12 open periods").
3. A diagnostic report is returned with actionable recommendations rather than a generic failure screen.

---

## 6. Logging, Monitoring & Observability

### 6.1 Structured Logging
All application events are logged via `structlog` in JSON format to `stdout`:
* **Attributes:** `timestamp`, `level`, `logger`, `request_id`, `actor_id`, `endpoint`, `duration_ms`, `event_type`.
* **Redaction Policy:** Automatic sanitization filters mask passwords, authentication tokens, student identity numbers (outside user IDs), and medical/private absence reasons.

### 6.2 Health & Metrics Endpoints
* `GET /healthz/live`: Liveness probe ensuring the FastAPI process is responsive.
* `GET /healthz/ready`: Readiness probe verifying active database connection pool and Redis reachability.
* `GET /metrics`: Prometheus-compatible endpoint tracking:
  * `timewise_solver_duration_seconds` (histogram)
  * `timewise_solver_outcome_total{status="FEASIBLE|INFEASIBLE|TIMEOUT"}`
  * `timewise_change_requests_total{status="APPROVED|REJECTED"}`
  * `timewise_alerts_dispatched_total{severity="CRITICAL|HIGH|MEDIUM|INFO"}`

---

## 7. Database Migrations, Backup & Disaster Recovery

### 7.1 Migration Strategy (Alembic)
* Every schema modification is represented by an immutable Alembic revision script in `backend/alembic/versions/`.
* Revisions must be forward- and backward-compatible (two-phase migrations for column renames/drops).
* Automated CI pipeline validates migration up and rollback (`alembic upgrade head && alembic downgrade base`).

### 7.2 Backup & Disaster Recovery
* **Point-In-Time Recovery (PITR):** PostgreSQL Write-Ahead Logging (WAL) archiving enabled.
* **Automated Daily Snapshots:** `pg_dump -Fc` compressed backups executed at 02:00 UTC, encrypted with AES-256 and stored off-site.
* **Retention Policy:**
  * Daily backups retained for 30 days.
  * Weekly backups retained for 12 weeks.
  * Monthly semester archives retained for 3 years (academic audit compliance).
* **Recovery Time Objective (RTO):** < 30 minutes.
* **Recovery Point Objective (RPO):** < 15 minutes (via WAL streaming).

---

## 8. Configuration & Secrets Management

Configuration conforms to the 12-Factor App methodology using `pydantic_settings`:

```python
class Settings(BaseSettings):
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"
    DATABASE_URL: PostgresDsn
    REDIS_URL: RedisDsn
    SECRET_KEY: str  # 64-char random hexadecimal
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    SOLVER_TIMEOUT_SECONDS: int = 60
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]
    ALERT_DEDUPLICATION_WINDOW_SECONDS: int = 300

    class Config:
        env_file = ".env"
        extra = "forbid"
```

---

## 9. Deployment Architecture

The system deploys as coordinated, stateless container images orchestrated via Docker Compose (development/testing) and Kubernetes / Managed Cloud Containers (production):

* **Frontend Container:** Node.js Alpine multi-stage build running `next start` on port 3000.
* **Backend API Container:** Python 3.12-slim running `uvicorn app.main:app --workers 4` on port 8000.
* **Worker Container:** Python 3.12-slim executing asynchronous task workers for long-running optimization simulations and notification dispatches.
* **Reverse Proxy / Ingress:** Caddy or Nginx handling TLS termination, HTTP/2, WebSocket upgrades, and path-based routing (`/api` -> backend, `/` -> frontend).

---

## 10. Unresolved Institutional Scheduling Rules & Configurable Defaults

Institutions vary widely in operational policies. Rather than hard-coding assumptions, TIMEWISE defines explicit configurable defaults for development and flags each for college administrator review:

| Scheduling Rule Parameter | Configurable Development Default | Architectural Default Rationale | Review Flag for Institution |
|:---|:---|:---|:---|
| **Period Duration** | 50 minutes | Standard collegiate lecture slot | Validate whether labs require 100 min or 150 min (2-3 contiguous slots) |
| **Operating Days** | Monday to Friday (5 days) + Saturday (half day, 4 periods) | Common Indian/Global collegiate schedule pattern | Confirm if Saturday is teaching, lab only, or off |
| **Daily Periods** | 7 periods/day (8:30 AM to 3:45 PM) | Fits 6 lectures + 1 lunch break | Confirm college start time and period count |
| **Lunch Break Window** | Period 4 or Period 5 (fixed 45 min) | Staggered lunch breaks reduce cafeteria bottlenecks | Confirm if lunch is fixed institution-wide or by department |
| **Max Faculty Consecutive Hours**| 3 periods | Prevents teacher burnout and teaching fatigue | Confirm department workload agreements |
| **Max Faculty Daily Load** | 5 periods / day | Balances faculty preparation and grading time | Review departmental guidelines |
| **Cohort Gap Periods** | 0 allowed (Strictly contiguous) | Students should not have idle gaps between classes | Confirm if voluntary library/study gaps are allowed |
| **Session Split Policy** | 3-credit subject = 3 x 1-hr single periods across distinct days | Spaced learning pedagogy | Confirm if 2-hr block lectures are permitted for theory |
| **Emergency Room Relocation** | Timetable Coordinator can reassign room directly without HOD signature | Operational urgency requires fast resolution | Confirm if HOD signoff is required even for same-day room moves |
| **Absence Reason Privacy** | Masked to students; visible to HOD and Admin | Protects faculty HIPAA/privacy rights | Confirm institutional HR disclosure guidelines |

---
*End of Architectural Specification.*
