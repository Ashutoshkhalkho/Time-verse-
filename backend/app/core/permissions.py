from enum import StrEnum

from app.models.user import UserRoleEnum


class Permission(StrEnum):
    # Identity & User Management
    USER_CREATE = "user:create"
    USER_UPDATE = "user:update"
    USER_ASSIGN_ROLE = "user:assign_role"
    USER_VIEW_PROFILE = "user:view_profile"

    # Infrastructure & Academic Configuration
    INSTITUTION_SETTINGS = "institution:manage_settings"
    DEPARTMENT_MANAGE = "department:manage"
    ROOM_MANAGE = "room:manage"
    ROOM_VIEW = "room:view"

    # Data Ingestion
    DATA_IMPORT = "data_import:upload_preview"
    DATA_COMMIT = "data_import:commit"
    DATA_EXPORT = "data_export:download"

    # Constraints & Solvers
    CONSTRAINT_CONFIGURE = "constraint:configure"
    SOLVER_RUN = "solver:run"
    SOLVER_DIAGNOSTICS = "solver:view_diagnostics"
    TIMETABLE_VIEW_DRAFT = "timetable:view_draft"

    # What-If Impact Simulator
    SIMULATOR_RUN = "simulator:run"
    SIMULATOR_DISCARD = "simulator:discard"

    # Approvals & Publication
    TIMETABLE_APPROVE = "timetable:approve"
    TIMETABLE_PUBLISH = "timetable:publish"
    TIMETABLE_RESTORE = "timetable:restore_version"

    # Timetable Consumption
    TIMETABLE_VIEW_PUBLISHED = "timetable:view_published"

    # Change Requests & Issues
    CHANGE_REQUEST_SUBMIT = "change_request:submit"
    CHANGE_REQUEST_REVIEW = "change_request:review"
    CHANGE_REQUEST_DECIDE = "change_request:decide"
    ISSUE_REPORT_CREATE = "issue_report:create"
    ISSUE_REPORT_RESOLVE = "issue_report:resolve"

    # Alerts & Notifications
    ALERT_VIEW = "alert:view"
    ALERT_BROADCAST = "alert:broadcast_urgent"

    # Analytics & Audits
    ANALYTICS_VIEW = "analytics:view"
    AUDIT_VIEW = "audit:view"

    # Mentor Program
    MENTEE_VIEW = "mentee:view"


# Server-Enforced Role-to-Permissions Mapping conforming to docs/ROLE_PERMISSION_MATRIX.md
ROLE_PERMISSIONS_MAP: dict[UserRoleEnum, set[Permission]] = {
    UserRoleEnum.ADMIN: {
        Permission.USER_CREATE,
        Permission.USER_UPDATE,
        Permission.USER_ASSIGN_ROLE,
        Permission.USER_VIEW_PROFILE,
        Permission.INSTITUTION_SETTINGS,
        Permission.DEPARTMENT_MANAGE,
        Permission.ROOM_MANAGE,
        Permission.ROOM_VIEW,
        Permission.DATA_IMPORT,
        Permission.DATA_COMMIT,
        Permission.DATA_EXPORT,
        Permission.CONSTRAINT_CONFIGURE,
        Permission.SOLVER_RUN,
        Permission.SOLVER_DIAGNOSTICS,
        Permission.TIMETABLE_VIEW_DRAFT,
        Permission.SIMULATOR_RUN,
        Permission.SIMULATOR_DISCARD,
        Permission.TIMETABLE_APPROVE,
        Permission.TIMETABLE_PUBLISH,
        Permission.TIMETABLE_RESTORE,
        Permission.TIMETABLE_VIEW_PUBLISHED,
        Permission.CHANGE_REQUEST_SUBMIT,
        Permission.CHANGE_REQUEST_REVIEW,
        Permission.CHANGE_REQUEST_DECIDE,
        Permission.ISSUE_REPORT_CREATE,
        Permission.ISSUE_REPORT_RESOLVE,
        Permission.ALERT_VIEW,
        Permission.ALERT_BROADCAST,
        Permission.ANALYTICS_VIEW,
        Permission.AUDIT_VIEW,
    },
    UserRoleEnum.HOD: {
        Permission.USER_VIEW_PROFILE,
        Permission.ROOM_VIEW,
        Permission.DATA_IMPORT,
        Permission.DATA_COMMIT,
        Permission.DATA_EXPORT,
        Permission.CONSTRAINT_CONFIGURE,
        Permission.SOLVER_RUN,
        Permission.SOLVER_DIAGNOSTICS,
        Permission.TIMETABLE_VIEW_DRAFT,
        Permission.SIMULATOR_RUN,
        Permission.SIMULATOR_DISCARD,
        Permission.TIMETABLE_APPROVE,
        Permission.TIMETABLE_PUBLISH,
        Permission.TIMETABLE_RESTORE,
        Permission.TIMETABLE_VIEW_PUBLISHED,
        Permission.CHANGE_REQUEST_SUBMIT,
        Permission.CHANGE_REQUEST_REVIEW,
        Permission.CHANGE_REQUEST_DECIDE,
        Permission.ISSUE_REPORT_CREATE,
        Permission.ISSUE_REPORT_RESOLVE,
        Permission.ALERT_VIEW,
        Permission.ALERT_BROADCAST,
        Permission.ANALYTICS_VIEW,
    },
    UserRoleEnum.COORDINATOR: {
        Permission.USER_VIEW_PROFILE,
        Permission.ROOM_VIEW,
        Permission.DATA_IMPORT,
        Permission.DATA_COMMIT,
        Permission.DATA_EXPORT,
        Permission.CONSTRAINT_CONFIGURE,
        Permission.SOLVER_RUN,
        Permission.SOLVER_DIAGNOSTICS,
        Permission.TIMETABLE_VIEW_DRAFT,
        Permission.SIMULATOR_RUN,
        Permission.SIMULATOR_DISCARD,
        Permission.TIMETABLE_VIEW_PUBLISHED,
        Permission.CHANGE_REQUEST_SUBMIT,
        Permission.CHANGE_REQUEST_REVIEW,
        Permission.ISSUE_REPORT_CREATE,
        Permission.ISSUE_REPORT_RESOLVE,
        Permission.ALERT_VIEW,
        Permission.ANALYTICS_VIEW,
    },
    UserRoleEnum.TEACHER: {
        Permission.USER_VIEW_PROFILE,
        Permission.ROOM_VIEW,
        Permission.TIMETABLE_VIEW_PUBLISHED,
        Permission.CHANGE_REQUEST_SUBMIT,
        Permission.ISSUE_REPORT_CREATE,
        Permission.ALERT_VIEW,
    },
    UserRoleEnum.CR: {
        Permission.USER_VIEW_PROFILE,
        Permission.TIMETABLE_VIEW_PUBLISHED,
        Permission.ISSUE_REPORT_CREATE,
        Permission.ALERT_VIEW,
    },
    UserRoleEnum.STUDENT: {
        Permission.USER_VIEW_PROFILE,
        Permission.TIMETABLE_VIEW_PUBLISHED,
        Permission.ALERT_VIEW,
    },
    UserRoleEnum.MENTOR: {
        Permission.USER_VIEW_PROFILE,
        Permission.TIMETABLE_VIEW_PUBLISHED,
        Permission.ALERT_VIEW,
        Permission.MENTEE_VIEW,
    },
}
