from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import PermissionGuard, get_current_user
from app.core.permissions import Permission
from app.db.session import get_db_session
from app.models.audit import AuditEvent
from app.models.user import User
from app.schemas.user import AuditLogResponse

router = APIRouter(prefix="/audit", tags=["Security Audit Logs"])


@router.get(
    "/logs",
    response_model=list[AuditLogResponse],
    summary="View Audit Logs",
    description="Administrators view immutable security audit logs.",
    dependencies=[Depends(PermissionGuard(Permission.AUDIT_VIEW))],
)
async def get_audit_logs(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[AuditLogResponse]:
    stmt = (
        select(AuditEvent)
        .where(AuditEvent.institution_id == current_user.institution_id)
        .order_by(AuditEvent.created_at.desc())
        .limit(100)
    )
    result = await db.execute(stmt)
    events = result.scalars().all()

    return [
        AuditLogResponse(
            id=e.id,
            actor_user_id=e.actor_user_id,
            action=e.action,
            resource_type=e.resource_type,
            resource_id=e.resource_id,
            before_state=e.before_state,
            after_state=e.after_state,
            reason=e.reason,
            ip_address=e.ip_address,
            created_at=e.created_at.isoformat(),
        )
        for e in events
    ]
