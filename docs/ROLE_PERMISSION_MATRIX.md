# TIMEWISE — Role & Permission Matrix (RBAC & Resource Scoping)

**Version:** 1.0  
**Date:** October 2026  
**Status:** Approved for Implementation  
**Security Enforcement:** Mandatory Server-Side Gatekeeping (FastAPI Dependency Injection)

---

## 1. Security Philosophy & Architectural Guarantees

In accordance with PRD FR-01 and the System Architecture:
1. **The UI is Never a Security Boundary:** Visual navigation or client-side role toggles merely adapt the visual layout. Every single API request to `/api/v1/*` verifies the authenticated token, extracts assigned roles, and evaluates fine-grained resource permissions.
2. **Multi-Tenant & Hierarchical Resource Scoping:** Permissions are evaluated within explicit jurisdictional boundaries:
   * **Global Scope:** Institution-wide access (College Administrator).
   * **Department Scope:** Bounded to the user’s assigned department (HOD, Coordinator).
   * **Cohort/Section Scope:** Bounded to the student’s or CR's enrolled cohort.
   * **Self Scope:** Strictly bounded to the authenticated user’s own entity records (Teacher, Student).
3. **No Tentative Leaks:** Unapproved draft timetables, ongoing what-if simulations, and faculty medical/personal absence reasons are cryptographically protected and filtered from student and CR access.

---

## 2. Role Definitions

| Role Code | Role Name | Primary Responsibilities | Jurisdictional Scope |
|:---|:---|:---|:---|
| `ADMIN` | **College Administrator** | System configuration, user accounts, rooms, departments, cross-department audits | Institution-wide |
| `HOD` | **Head of Department** | Departmental constraints, timetable approval/publication, change request decisions | Assigned Department |
| `COORDINATOR` | **Timetable Coordinator** | Data import, constraint tuning, running solver, impact simulations, drafting schedules | Assigned Department(s) |
| `TEACHER` | **Teacher / Faculty** | Viewing assigned teaching schedule, setting availability preferences, change requests | Assigned Department & Self |
| `CR` | **Class Representative** | Viewing section timetable, reporting classroom/scheduling issues, relaying notices | Assigned Cohort/Section |
| `STUDENT` | **Student** | Viewing official published section timetable, managing personal study blocks | Assigned Cohort/Section & Self |

---

## 3. Comprehensive Role-Permission Matrix

Legend:
* **G**: Global / Institution-wide access
* **D**: Department-scoped access (user must belong to the target department)
* **C**: Cohort/Section-scoped access (user must be enrolled in the target section)
* **S**: Self-scoped access (user can only access their own records)
* **--**: Forbidden (HTTP 403 Forbidden returned by API)

| Functional Domain / Permission Key | ADMIN | HOD | COORDINATOR | TEACHER | CR | STUDENT | Server-Side Rule / Notes |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---|
| **Identity & Scoping** | | | | | | | |
| `user:create` / `user:update` | **G** | -- | -- | -- | -- | -- | Only Admin manages institutional user accounts |
| `user:assign_role` | **G** | -- | -- | -- | -- | -- | Role elevation is strictly audited |
| `user:view_profile` | **G** | **D** | **D** | **S** | **S** | **S** | Teachers/students see only their profile; HOD sees dept faculty |
| **Physical & Academic Master Data** | | | | | | | |
| `institution:manage_settings` | **G** | -- | -- | -- | -- | -- | Term dates, operating hours, day configuration |
| `department:manage` | **G** | -- | -- | -- | -- | -- | Create/archive academic departments |
| `room:create` / `room:update` | **G** | -- | -- | -- | -- | -- | Room dimensions, types, fixed equipment |
| `room:view_list` | **G** | **D** | **D** | **D** | -- | -- | View room inventory and availability |
| `course:manage` / `subject:manage` | **G** | **D** | **D** | -- | -- | -- | Syllabus, credit hours, subject room requirements |
| **Data Ingestion (CSV / XLSX)** | | | | | | | |
| `data_import:upload_preview` | **G** | **D** | **D** | -- | -- | -- | Parses CSV/XLSX and previews row validation errors |
| `data_import:commit` | **G** | **D** | **D** | -- | -- | -- | Commits validated batch into relational DB |
| `data_export:download` | **G** | **D** | **D** | **D** | -- | -- | Exports timetable matrices and utilization summaries |
| **Constraint Configuration** | | | | | | | |
| `constraint:configure_hard` | **G** | **D** | **D** | -- | -- | -- | Enforces mandatory hard rules (durations, no-overlap) |
| `constraint:configure_soft` | **G** | **D** | **D** | -- | -- | -- | Sets optimization penalty weights (gaps, preferences) |
| `teacher_pref:manage` | **G** | **D** | **D** | **S** | -- | -- | Faculty set own preferred slots; HOD/Coord can override |
| **Optimization & Timetable Drafting**| | | | | | | |
| `solver:run_generation` | **G** | **D** | **D** | -- | -- | -- | Triggers CP-SAT solver job |
| `solver:view_diagnostics` | **G** | **D** | **D** | -- | -- | -- | Inspects infeasibility reports and relaxation hints |
| `timetable:view_draft` | **G** | **D** | **D** | -- | -- | -- | Drafts are hidden from faculty, CRs, and students |
| **What-If Impact Simulator** | | | | | | | |
| `simulator:create_scenario` | **G** | **D** | **D** | -- | -- | -- | Tests hypothetical room closures or faculty leaves |
| `simulator:run_impact` | **G** | **D** | **D** | -- | -- | -- | Computes direct/indirect affected sessions and alternatives |
| `simulator:discard` | **G** | **D** | **D** | -- | -- | -- | Flushes sandbox simulation without altering production |
| **Approvals, Publishing & Versioning**| | | | | | | |
| `timetable:approve` | **G** | **D** | -- | -- | -- | -- | HOD approves official departmental timetable |
| `timetable:publish` | **G** | **D** | -- | -- | -- | -- | Increments version (v1.0), marks PUBLISHED, triggers alerts |
| `timetable:restore_version` | **G** | **D** | -- | -- | -- | -- | Rolls back to a previous validated version |
| **Timetable Consumption** | | | | | | | |
| `timetable:view_published_inst` | **G** | -- | -- | -- | -- | -- | Global master view across all departments |
| `timetable:view_published_dept` | **G** | **D** | **D** | **D** | -- | -- | Departmental weekly grid |
| `timetable:view_published_section`| **G** | **D** | **D** | **D** | **C** | **C** | Cohort schedule (CR & Students see only their section) |
| `timetable:view_published_teacher`| **G** | **D** | **D** | **S** | -- | -- | Faculty sees personal assigned teaching schedule |
| `study_block:manage` | -- | -- | -- | -- | **S** | **S** | Personal student self-study time blocks (Design Doc) |
| **Change Requests & Issue Reports** | | | | | | | |
| `change_request:submit` | **G** | **D** | **D** | **S** | -- | -- | Faculty submits reschedule or swap request |
| `change_request:review` | **G** | **D** | **D** | -- | -- | -- | Evaluates alternatives in Impact Simulator |
| `change_request:decide` | **G** | **D** | -- | -- | -- | -- | HOD approves or rejects change request |
| `issue_report:create` | **G** | **D** | **D** | **S** | **C** | -- | CR or Faculty reports room locked, equipment broken |
| `issue_report:resolve` | **G** | **D** | **D** | -- | -- | -- | Coordinator / HOD marks issue resolved |
| **Alerts & Notifications** | | | | | | | |
| `alert:view_inbox` | **S** | **S** | **S** | **S** | **S** | **S** | All users view their targeted personal alerts |
| `alert:mark_read` | **S** | **S** | **S** | **S** | **S** | **S** | Updates read status |
| `alert:broadcast_urgent` | **G** | **D** | -- | -- | -- | -- | Sends urgent priority notices (severe weather, emergency) |
| **Analytics & Audit Logs** | | | | | | | |
| `analytics:view_department` | **G** | **D** | **D** | -- | -- | -- | Room utilization, teacher workload balances |
| `analytics:view_institution` | **G** | -- | -- | -- | -- | -- | Cross-department utilization trends |
| `audit:view_logs` | **G** | **D** | -- | -- | -- | -- | Immutable event ledger (HOD sees dept, Admin sees all) |

---

## 4. Server-Side Enforcement Architecture

To guarantee security, FastAPI routes leverage dependency injection chains that validate identity, permission tokens, and resource scope before invoking service logic.

### 4.1 Dependency Injection Design Pattern

```python
# Conceptual Architecture: backend/app/api/deps.py

from fastapi import Depends, HTTPException, status
from app.models.user import User, UserRoleEnum
from app.services.auth import get_current_user

class PermissionChecker:
    def __init__(self, required_permission: str, require_department_match: bool = False):
        self.required_permission = required_permission
        self.require_department_match = require_department_match

    async def __call__(
        self,
        department_id: str | None = None,
        current_user: User = Depends(get_current_user),
    ) -> User:
        # 1. Administrator has global institutional authority
        if current_user.role == UserRoleEnum.ADMIN:
            return current_user

        # 2. Verify permission mapping for the user's role
        if not self._role_has_permission(current_user.role, self.required_permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{current_user.role}' lacks permission '{self.required_permission}'"
            )

        # 3. Verify departmental jurisdiction where applicable
        if self.require_department_match and department_id:
            user_dept_ids = [scope.department_id for scope in current_user.department_scopes]
            if department_id not in user_dept_ids:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"User is not authorized for department '{department_id}'"
                )

        return current_user

    def _role_has_permission(self, role: UserRoleEnum, perm: str) -> bool:
        return perm in ROLE_PERMISSIONS_MAP.get(role, set())
```

### 4.2 Route Application Example

```python
@router.post(
    "/departments/{department_id}/timetables/{timetable_id}/approve",
    dependencies=[Depends(PermissionChecker("timetable:approve", require_department_match=True))]
)
async def approve_timetable(
    department_id: str,
    timetable_id: str,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Guaranteed: Only HOD of this exact department or College Admin can execute this.
    Coordinators, Faculty, CRs, and Students are blocked with 403 Forbidden.
    """
    return await approval_service.approve_timetable(db, timetable_id)
```

---
*End of Role & Permission Matrix Specification.*
