"""Server-side business membership resolution and trusted BusinessContext."""

from fastapi import Depends, Header, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.core.errors import ForbiddenError, UnauthorizedError
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.identity import Business, BusinessMembership, User


class BusinessContext(BaseModel):
    """Trusted, server-verified tenant context for request processing.

    Invariant: Constructed strictly by server-side authentication and membership checks.
    Client-provided business IDs are never trusted directly without membership verification.
    """

    model_config = ConfigDict(frozen=True)

    business_id: str
    user_id: str
    role: str  # "owner", "manager", "staff"
    business_name: str
    currency: str = "INR"
    timezone: str = "Asia/Kolkata"


async def get_current_user(
    request: Request,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    """Extract and authenticate the user from Bearer token."""
    if not authorization or not authorization.startswith("Bearer "):
        raise UnauthorizedError("Missing or invalid Authorization header")

    token = authorization[7:].strip()
    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        raise UnauthorizedError("Invalid or expired authentication token")

    user_id = payload["sub"]
    user = db.query(User).filter(User.id == user_id, User.is_active.is_(True)).first()
    if not user:
        raise UnauthorizedError("Authenticated user not found or inactive")

    return user


async def get_business_context(
    current_user: User = Depends(get_current_user),
    x_business_id: str | None = Header(default=None, alias="X-Business-ID"),
    db: Session = Depends(get_db),
) -> BusinessContext:
    """Resolve and verify business membership server-side.

    If the client requests a specific business via X-Business-ID, verify membership.
    Otherwise, default to the user's primary/first active business membership.
    """
    query = (
        db.query(BusinessMembership, Business)
        .join(Business, BusinessMembership.business_id == Business.id)
        .filter(
            BusinessMembership.user_id == current_user.id,
            Business.is_active.is_(True),
        )
    )

    if x_business_id:
        membership_row = query.filter(BusinessMembership.business_id == x_business_id).first()
        if not membership_row:
            raise ForbiddenError(
                f"User {current_user.id} has no membership in business {x_business_id}"
            )
    else:
        membership_row = query.first()
        if not membership_row:
            raise ForbiddenError(f"User {current_user.id} does not belong to any active business")

    membership, business = membership_row

    return BusinessContext(
        business_id=business.id,
        user_id=current_user.id,
        role=membership.role,
        business_name=business.name,
        currency=business.currency,
        timezone=business.timezone,
    )
