from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import PermissionGuard, get_current_user
from app.core.permissions import Permission
from app.db.session import get_db_session
from app.models.change_request import RequestStatusEnum
from app.models.user import User
from app.services.approvals.approval_service import ApprovalService
from app.services.approvals.schemas import (
    ChangeRequestCreate,
    ChangeRequestDecision,
    ChangeRequestResponse,
)

router = APIRouter(prefix="/approvals", tags=["Change Requests & Approvals"])


@router.post(
    "/requests",
    response_model=ChangeRequestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a Timetable Change Request",
    dependencies=[Depends(PermissionGuard(Permission.CHANGE_REQUEST_SUBMIT))],
)
async def submit_change_request(
    payload: ChangeRequestCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> ChangeRequestResponse:
    """Submits a change request with a reason and target session. Does not alter the official schedule."""
    return await ApprovalService.submit_request(payload, current_user, db)


@router.get(
    "/requests",
    response_model=list[ChangeRequestResponse],
    summary="List Change Requests",
)
async def list_change_requests(
    timetable_id: str | None = Query(None, description="Filter by timetable ID"),
    status: RequestStatusEnum | None = Query(None, description="Filter by status"),
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[AsyncSession, Depends(get_db_session)] = None,
) -> list[ChangeRequestResponse]:
    """Lists change requests with scoping (teachers see own requests, HODs/Coordinators see department)."""
    return await ApprovalService.list_requests(timetable_id, status, current_user, db)


@router.get(
    "/requests/{request_id}",
    response_model=ChangeRequestResponse,
    summary="Get Change Request Details",
)
async def get_change_request(
    request_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> ChangeRequestResponse:
    """Retrieves full details of a change request including proposed alternatives."""
    return await ApprovalService.get_request(request_id, current_user, db)


@router.post(
    "/requests/{request_id}/review",
    response_model=ChangeRequestResponse,
    summary="Review Change Request and Propose Alternatives",
    dependencies=[Depends(PermissionGuard(Permission.CHANGE_REQUEST_REVIEW))],
)
async def review_and_propose_alternatives(
    request_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> ChangeRequestResponse:
    """Runs the impact simulator and proposes ranked feasible alternatives."""
    return await ApprovalService.review_and_propose_alternatives(request_id, current_user, db)


@router.post(
    "/requests/{request_id}/cancel",
    response_model=ChangeRequestResponse,
    summary="Cancel Change Request",
)
async def cancel_change_request(
    request_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> ChangeRequestResponse:
    """Cancels a pending or under-review change request."""
    return await ApprovalService.cancel_request(request_id, current_user, db)


@router.post(
    "/requests/{request_id}/decide",
    response_model=ChangeRequestResponse,
    summary="Decide Change Request (Approve or Reject)",
    dependencies=[Depends(PermissionGuard(Permission.CHANGE_REQUEST_DECIDE))],
)
async def decide_change_request(
    request_id: str,
    payload: ChangeRequestDecision,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> ChangeRequestResponse:
    """
    Decides change request:
    - If APPROVED: Revalidates constraints immediately before commit, bumps version, creates new immutable schedule, and alerts affected users.
    - If REJECTED: Keeps schedule unchanged and records decision rationale.
    """
    return await ApprovalService.decide_request(request_id, payload, current_user, db)
