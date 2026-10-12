import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditEvent


async def record_audit_event(
    db: AsyncSession,
    action: str,
    resource_type: str,
    resource_id: str,
    institution_id: str,
    actor_user_id: str | None = None,
    before_state: dict[str, Any] | None = None,
    after_state: dict[str, Any] | None = None,
    reason: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> AuditEvent:
    """Persists an immutable audit log record for security and regulatory compliance."""
    event = AuditEvent(
        id=f"aud_{uuid.uuid4().hex[:22]}",
        actor_user_id=actor_user_id,
        institution_id=institution_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        before_state=before_state,
        after_state=after_state,
        reason=reason,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.add(event)
    await db.flush()
    return event
