"""Authentication and demo session token endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import BadRequestError, UnauthorizedError
from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import get_db
from app.models.identity import Business, BusinessMembership, User

router = APIRouter(prefix="/auth", tags=["Authentication"])


class LoginRequest(BaseModel):
    email: str
    password: str


class AuthTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    full_name: str
    business_id: str
    business_name: str


@router.post("/demo-token", response_model=AuthTokenResponse)
def get_demo_token(db: Session = Depends(get_db)) -> AuthTokenResponse:
    """Issue a verified access token for the default demo kirana store."""
    if get_settings().APP_ENV.lower() not in {"development", "test"}:
        raise HTTPException(status_code=404, detail="Not found")
    user = db.query(User).filter(User.is_active.is_(True)).first()
    business = db.query(Business).filter(Business.is_active.is_(True)).first()

    if not user or not business:
        # Auto-seed Sharma Kirana Store if database is empty
        user = User(
            email="sharma@sharmakirana.test",
            hashed_password=hash_password("Kirana@12345"),
            full_name="Rajesh Sharma",
        )
        db.add(user)
        db.flush()

        business = Business(
            name="Sharma Kirana Store",
            slug="sharma-kirana",
            region="Delhi-NCR",
            currency="INR",
            timezone="Asia/Kolkata",
        )
        db.add(business)
        db.flush()

        membership = BusinessMembership(
            user_id=user.id,
            business_id=business.id,
            role="owner",
        )
        db.add(membership)
        db.commit()

    token = create_access_token({"sub": user.id})

    return AuthTokenResponse(
        access_token=token,
        token_type="bearer",
        user_id=user.id,
        full_name=user.full_name,
        business_id=business.id,
        business_name=business.name,
    )


@router.post("/login", response_model=AuthTokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> AuthTokenResponse:
    """Authenticate with email and password."""
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise UnauthorizedError("Invalid email or password")

    membership = (
        db.query(BusinessMembership, Business)
        .join(Business, BusinessMembership.business_id == Business.id)
        .filter(BusinessMembership.user_id == user.id, Business.is_active.is_(True))
        .first()
    )
    if not membership:
        raise BadRequestError("User has no active business membership")

    _, business = membership
    token = create_access_token({"sub": user.id})

    return AuthTokenResponse(
        access_token=token,
        token_type="bearer",
        user_id=user.id,
        full_name=user.full_name,
        business_id=business.id,
        business_name=business.name,
    )
