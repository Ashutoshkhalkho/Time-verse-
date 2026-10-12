# TIMEWISE — Institutional Security Review & Risk Assessment

**Document Version:** 1.0  
**Date:** October 2026  
**Auditor:** Lead Software Architect (TIMEWISE Security Team)  
**Standard Compliance Target:** OWASP Top 10 (2021), ISO/IEC 27001, FERPA / Student Privacy Guidelines

---

## 1. Executive Summary

This security review provides an end-to-end evaluation of the **TIMEWISE Autonomous Timetable Optimization & Academic Portal** architecture, covering authentication, authorization, data validation, file ingestion, cryptographic storage, session revocation, privacy masking, and tamper-evident audit logging.

All security controls are enforced strictly on the server; client-side route guards and UI state controls are treated strictly as presentation conveniences and never as security boundaries.

---

## 2. Threat Modeling & Scope

The application enforces a multi-tier, multi-tenant academic security model across seven personas:
1. `ADMIN` — College Administrator
2. `HOD` — Department Head
3. `COORDINATOR` — Timetable Coordinator
4. `TEACHER` — Faculty Member
5. `CR` — Class Representative
6. `STUDENT` — Student Cohort Member
7. `MENTOR` — Academic Mentor

---

## 3. Deep-Dive Security Architecture

### 3.1 Authentication & Credential Management
* **Password Hashing:** Passwords are never stored in plaintext. Passwords are derived using **Argon2id** (`argon2-cffi`), which provides memory-hard protection against ASIC/GPU offline cracking attacks.
* **Token Standard:** Authentication produces signed OAuth2 Bearer **JSON Web Tokens (JWT)** signed via asymmetric or HMAC-SHA256 with strong secrets (`SECRET_KEY`).
* **Token Lifetimes & Rotation:**
  * Access Tokens: Short-lived (15 minutes).
  * Refresh Tokens: Long-lived (7 days) with cryptographically unique UUID `jti` claim.
* **Revocation Ledger:** Refresh tokens are revoked immediately upon logout (`POST /api/v1/auth/logout`) and recorded in the database `revoked_tokens` table. Expired or revoked `jti` tokens are rejected unconditionally with HTTP 401.

### 3.2 Authorization & Resource Scoping (RBAC + ABAC)
* **Least Privilege:** Each endpoint enforces specific permissions using FastAPI's dependency injection (`PermissionGuard`).
* **Server-Side Enforcement:**
  * Students and Class Representatives cannot trigger timetable generation, publication, or rollback (`HTTP 403 Forbidden`).
  * Class Representatives can only broadcast alerts to their assigned section (`cohort_section_id`), preventing campus-wide spam.
  * Teachers can view assigned schedules and propose reschedules, but cannot approve change requests.
  * HODs are scoped to their respective department (`department_id`) and cannot approve cross-department changes.
* **Mentor Dossier Authorization:** Academic Mentors can access advising dossiers (`/api/v1/portal/mentor-mentees`) only for explicitly assigned mentees verified through `mentor_assignments` database records.

### 3.3 Input Validation & RFC 7807 Centralized Error Handling
* **Schema Enforcement:** All request payloads are strictly validated using **Pydantic v2** models before reaching domain logic.
* **RFC 7807 Standard:** Errors are formatted as RFC 7807 Problem Details (`application/problem+json`), preventing stack trace leaks or sensitive internal database schema exposure to callers.
* **SQL Injection Immunity:** All database interactions utilize SQLAlchemy 2.0 async ORM with parameterized queries and bind variables. Raw string interpolation in SQL is strictly prohibited.

### 3.4 File Ingestion & Preflight Validation Security
* **MIME Type & Extension Verification:** Uploaded files (`POST /api/v1/import/preview`) are verified for valid `text/csv` or `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` MIME types.
* **Size Limits:** File uploads are capped at 10 MB to prevent denial-of-service (DoS) via memory exhaustion.
* **Memory Buffer Safety:** File contents are parsed in memory with bounded stream limits. Executable macros and embedded scripts in Excel sheets are stripped or rejected.
* **Preflight Sandbox:** Ingestion files are completely validated against referential integrity constraints prior to database insertion; malformed rows are returned with line numbers and 0 database writes occur.

### 3.5 Student Privacy & Sensitive Data Masking (FERPA Compliance)
* **Private Faculty Reasons Masking:** When faculty members request schedule changes due to private or medical reasons, the notification pipeline strictly masks the justification. Students receive clean notifications citing `"Faculty Unavailable"` or `"Department Schedule Adjustment"`, with personal notes stripped.
* **Student PII Minimization:** Notifications and public timetables do not expose personal student emails, phone numbers, or academic grades.

### 3.6 Tamper-Evident Security Audit Ledger
* **Audit Model (`audit_events`):**
  * Captures `actor_user_id`, `action`, `resource_type`, `resource_id`, `before_state` JSON, `after_state` JSON, `ip_address`, and `created_at`.
  * Immutable ledger: Update and delete permissions are blocked at the ORM and database trigger levels.
  * Security-critical actions audited: user creation, role assignment, timetable generation, change request approval, and version rollback.

---

## 4. Security Test Verification Results

All security controls were tested and verified via automated test suites in `backend/tests/test_auth_rbac.py` and `backend/tests/test_milestone6_e2e_scenarios.py`:

| Threat Scenario | Tested Vector | Expected Outcome | Verification Status |
|:---|:---|:---|:---:|
| **Unauthorized Publishing** | Student calling `POST /api/v1/timetables/generate` | HTTP 403 Forbidden | **PASS** (`test_scenario_2`) |
| **Cross-Role Audit Access** | CR calling `GET /api/v1/audit/logs` | HTTP 403 Forbidden | **PASS** (`test_scenario_2`) |
| **Cross-Role User Mgmt** | CR calling `GET /api/v1/users` | HTTP 403 Forbidden | **PASS** (`test_scenario_2`) |
| **Unauthorized Mentee Access** | Student calling `GET /api/v1/portal/mentor-mentees` | HTTP 403 Forbidden | **PASS** (`test_scenario_2`) |
| **Unauthorized Decision** | Teacher calling `POST /api/v1/approvals/requests/.../decide` | HTTP 403 Forbidden | **PASS** (`test_scenario_2`) |
| **Session Invalidation** | Calling authenticated routes with revoked JWT | HTTP 401 Unauthorized | **PASS** (`test_logout_revokes_session`) |
| **Expired Token Rejection** | Calling authenticated routes with expired token | HTTP 401 Unauthorized | **PASS** (`test_expired_token_rejected`) |
| **Malicious File Ingestion** | Ingesting rooms CSV with negative capacity | HTTP 422 Unprocessable Entity | **PASS** (`test_scenario_3`) |
| **Notification Spam** | Dispatching duplicate broadcast within 5 minutes | Discarded as duplicate (0 recipients) | **PASS** (`test_scenario_5`) |

---

## 5. Residual Risks & Production Hardening Recommendations

1. **Production Secret Key Rotation:** Ensure `SECRET_KEY` is injected from an enterprise secret store (HashiCorp Vault, AWS Secrets Manager) and never committed to source repositories.
2. **Rate Limiting:** Implement IP-based and user-based token bucket rate limiting on `/api/v1/auth/login` to prevent credential stuffing attacks (recommended: Nginx `limit_req` or Redis rate limiter).
3. **Database Connection Encryption:** Enforce `sslmode=require` or `sslmode=verify-full` on production PostgreSQL connection strings.
4. **Content Security Policy (CSP):** Configure strict HTTP response headers (`Content-Security-Policy`, `X-Frame-Options: DENY`, `Strict-Transport-Security: max-age=31536000; includeSubDomains`).
