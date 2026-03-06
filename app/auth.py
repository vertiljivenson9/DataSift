"""
Authentication Module - Enterprise-grade JWT authentication with API key management
"""

from fastapi import APIRouter, Depends, HTTPException, status, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from datetime import datetime, timedelta
from typing import Optional
import jwt
import os
import secrets
import re

from . import models, database

router = APIRouter()
security = HTTPBearer(auto_error=False)

pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12
)

SECRET_KEY = os.getenv("SECRET_KEY")

if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY must be set in environment variables")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30


class UserRegister(BaseModel):
    email: EmailStr
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    api_key: str


class UserProfile(BaseModel):
    id: str
    email: str
    plan_id: str
    api_key: str
    monthly_requests: int
    request_limit: int
    subscription_status: str
    subscription_end_date: Optional[str]
    created_at: Optional[str]


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def validate_password(password: str) -> tuple[bool, str]:

    if len(password) < 8:
        return False, "Password must be at least 8 characters"

    if not re.search(r"[A-Z]", password):
        return False, "Password must contain uppercase letter"

    if not re.search(r"[a-z]", password):
        return False, "Password must contain lowercase letter"

    if not re.search(r"\d", password):
        return False, "Password must contain a digit"

    return True, ""


def create_access_token(data: dict) -> str:

    to_encode = data.copy()

    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "access"
    })

    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def generate_api_key() -> str:

    return f"ds_{secrets.token_urlsafe(48)}"


def decode_token(token: str):

    try:

        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        return payload

    except jwt.ExpiredSignatureError:

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
            headers={"WWW-Authenticate": "Bearer"}
        )

    except jwt.InvalidTokenError:

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"}
        )


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    db: Session = Depends(database.get_db)
):

    user = None

    if x_api_key:

        user = db.query(models.User).filter(
            models.User.api_key == x_api_key
        ).first()

        if not user:
            raise HTTPException(
                status_code=401,
                detail="Invalid API key"
            )

    elif credentials:

        payload = decode_token(credentials.credentials)

        user_id = payload.get("sub")

        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token payload")

        user = db.query(models.User).filter(
            models.User.id == user_id
        ).first()

        if not user:
            raise HTTPException(status_code=401, detail="User not found")

    else:

        raise HTTPException(status_code=401, detail="Authentication required")

    # verificar suspensión
    if user.subscription_status == "suspended":

        raise HTTPException(
            status_code=403,
            detail="Account suspended"
        )

    # verificar expiración
    if user.subscription_end_date and user.subscription_end_date < datetime.utcnow():

        user.subscription_status = "expired"
        db.commit()

    return user


@router.post("/register", response_model=TokenResponse, status_code=201)
def register(user_data: UserRegister, db: Session = Depends(database.get_db)):

    email = user_data.email.lower().strip()
    password = user_data.password

    is_valid, error_msg = validate_password(password)

    if not is_valid:

        raise HTTPException(status_code=400, detail=error_msg)

    existing_user = db.query(models.User).filter(
        models.User.email == email
    ).first()

    if existing_user:

        raise HTTPException(status_code=409, detail="Email already registered")

    hashed_password = get_password_hash(password)

    api_key = generate_api_key()

    user = models.User(
        email=email,
        hashed_password=hashed_password,
        api_key=api_key,
        plan_id="free",
        subscription_status="active",
        monthly_requests=0,
        request_limit=1000
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    access_token = create_access_token({"sub": str(user.id)})

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "api_key": api_key
    }


@router.post("/login", response_model=TokenResponse)
def login(user_data: UserLogin, db: Session = Depends(database.get_db)):

    email = user_data.email.lower().strip()
    password = user_data.password

    user = db.query(models.User).filter(
        models.User.email == email
    ).first()

    if not user or not verify_password(password, user.hashed_password):

        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )

    user.last_login_at = datetime.utcnow()

    db.commit()

    access_token = create_access_token({"sub": str(user.id)})

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "api_key": user.api_key
    }


@router.get("/me", response_model=UserProfile)
async def get_me(user: models.User = Depends(get_current_user)):

    return {
        "id": str(user.id),
        "email": user.email,
        "plan_id": user.plan_id,
        "api_key": user.api_key,
        "monthly_requests": user.monthly_requests,
        "request_limit": user.request_limit,
        "subscription_status": user.subscription_status,
        "subscription_end_date": user.subscription_end_date.isoformat() if user.subscription_end_date else None,
        "created_at": user.created_at.isoformat() if user.created_at else None
    }


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(user: models.User = Depends(get_current_user)):

    access_token = create_access_token({"sub": str(user.id)})

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "api_key": user.api_key
    }


@router.post("/api-key/regenerate")
async def regenerate_api_key(
    user: models.User = Depends(get_current_user),
    db: Session = Depends(database.get_db)
):

    new_api_key = generate_api_key()

    user.api_key = new_api_key

    db.commit()

    return {
        "message": "API key regenerated successfully",
        "api_key": new_api_key
    }
