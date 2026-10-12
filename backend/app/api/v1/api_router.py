from fastapi import APIRouter

from app.api.v1.endpoints import (
    alerts,
    announcements,
    approvals,
    assistant,
    audit,
    auth,
    conflicts,
    faculty_directory,
    health,
    importer,
    policy,
    portal,
    rescheduler,
    scheduling,
    setup,
    simulator,
    users,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(policy.router)
api_router.include_router(audit.router)
api_router.include_router(scheduling.router)
api_router.include_router(importer.router)
api_router.include_router(setup.router)
api_router.include_router(assistant.router)
api_router.include_router(approvals.router)
api_router.include_router(simulator.router)
api_router.include_router(conflicts.router)
api_router.include_router(rescheduler.router)
api_router.include_router(alerts.router)
api_router.include_router(announcements.router)
api_router.include_router(portal.router)
api_router.include_router(faculty_directory.router)



