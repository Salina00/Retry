import hashlib
import os
import secrets
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Header, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.db import get_db
from backend.app.models import User, SessionToken

router = APIRouter(prefix="/auth", tags=["auth"])

# --- Cryptographic Utilities ---
def hash_password(password: str) -> str:
    """Generate salted PBKDF2 SHA-256 hash with 100,000 iterations."""
    salt = os.urandom(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100000)
    return f"{salt.hex()}:{key.hex()}"

def verify_password(password: str, hashed: str) -> bool:
    """Verify password against salted PBKDF2 SHA-256 hash using constant-time comparison."""
    try:
        salt_hex, key_hex = hashed.split(":")
        salt = bytes.fromhex(salt_hex)
        key = bytes.fromhex(key_hex)
        new_key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100000)
        return secrets.compare_digest(key, new_key)
    except Exception:
        return False

def create_session(db: Session, user_id: str) -> str:
    """Create a secure session token valid for 7 days."""
    token = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(days=7)
    session_obj = SessionToken(token=token, user_id=user_id, expires_at=expires_at)
    db.add(session_obj)
    db.commit()
    return token

def ensure_demo_user(db: Session):
    """Ensure a ready-to-use demo account exists for zero-friction evaluation."""
    demo_email = "demo@razorpay.com"
    existing = db.query(User).filter(User.email == demo_email).first()
    if not existing:
        demo = User(
            name="Demo Specialist",
            email=demo_email,
            hashed_password=hash_password("password123"),
            role="compliance_manager"
        )
        db.add(demo)
        db.commit()


# --- Pydantic Schemas ---
class SignUpRequest(BaseModel):
    name: str
    email: str
    password: str
    role: Optional[str] = "recovery_specialist"

class LoginRequest(BaseModel):
    email: str
    password: str

class UserResponse(BaseModel):
    id: str
    name: str
    email: str
    role: str
    created_at: datetime

    class Config:
        from_attributes = True

class AuthResponse(BaseModel):
    token: str
    user: UserResponse


# --- Endpoints ---
@router.post("/signup", response_model=AuthResponse)
def signup(req: SignUpRequest, db: Session = Depends(get_db)):
    """Register a new user account."""
    existing = db.query(User).filter(User.email == req.email.lower()).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email already exists."
        )
    
    if len(req.password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 6 characters long."
        )

    user = User(
        name=req.name.strip(),
        email=req.email.lower().strip(),
        hashed_password=hash_password(req.password),
        role=req.role or "recovery_specialist"
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_session(db, user.id)
    return AuthResponse(token=token, user=UserResponse.from_orm(user))


@router.post("/login", response_model=AuthResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    """Authenticate with email and password."""
    # Ensure demo user exists on first login attempt if needed
    ensure_demo_user(db)

    user = db.query(User).filter(User.email == req.email.lower().strip()).first()
    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password."
        )

    token = create_session(db, user.id)
    return AuthResponse(token=token, user=UserResponse.from_orm(user))


@router.get("/me", response_model=UserResponse)
def get_current_user(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """Retrieve authenticated user from Authorization header."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authentication token."
        )

    token = authorization.split(" ")[1]
    session_obj = db.query(SessionToken).filter(
        SessionToken.token == token,
        SessionToken.expires_at > datetime.utcnow()
    ).first()

    if not session_obj or not session_obj.user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session has expired or is invalid. Please log in again."
        )

    return UserResponse.from_orm(session_obj.user)


@router.post("/logout")
def logout(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """Revoke active session token."""
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
        session_obj = db.query(SessionToken).filter(SessionToken.token == token).first()
        if session_obj:
            db.delete(session_obj)
            db.commit()
    return {"status": "logged_out"}
