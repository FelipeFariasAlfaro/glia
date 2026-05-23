"""
Authentication API Routes.

Handles user login, registration, token refresh, and logout.
All endpoints use JWT tokens signed with RS256 (see ADR-001).
Token rotation was added after the March 2024 token leak incident.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel, EmailStr

from src.services.auth_service import AuthService
from src.middleware.rate_limiter import rate_limit
from src.utils.validators import validate_password_strength

router = APIRouter(prefix="/auth", tags=["authentication"])


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    role: str = "customer"


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 900  # 15 minutes, reduced from 1h after token leak incident


@router.post("/login", response_model=TokenResponse)
@rate_limit(max_requests=5, window_seconds=60)
async def login(request: LoginRequest, auth_service: AuthService = Depends()):
    """Authenticate user and return JWT token pair.
    
    Rate limited to 5 attempts per minute per IP.
    Failed attempts are logged for security monitoring.
    """
    user = await auth_service.authenticate(request.email, request.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    tokens = await auth_service.create_token_pair(user)
    return TokenResponse(**tokens)


@router.post("/register", response_model=TokenResponse, status_code=201)
@rate_limit(max_requests=3, window_seconds=300)
async def register(request: RegisterRequest, auth_service: AuthService = Depends()):
    """Register a new user account.
    
    Password must meet strength requirements (min 12 chars, mixed case, symbols).
    Sends welcome email via notification service after successful registration.
    """
    validate_password_strength(request.password)
    user = await auth_service.register_user(
        email=request.email, password=request.password,
        full_name=request.full_name, role=request.role
    )
    tokens = await auth_service.create_token_pair(user)
    return TokenResponse(**tokens)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(request: Request, auth_service: AuthService = Depends()):
    """Rotate refresh token and issue new access token.
    
    Implements token rotation: old refresh token is invalidated immediately.
    If a revoked token is reused, ALL sessions for that user are terminated
    (potential token theft detected). Added post-incident March 2024.
    """
    old_refresh = request.headers.get("X-Refresh-Token")
    if not old_refresh:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)
    tokens = await auth_service.rotate_tokens(old_refresh)
    return TokenResponse(**tokens)


@router.post("/logout", status_code=204)
async def logout(request: Request, auth_service: AuthService = Depends()):
    """Invalidate current session and revoke tokens.
    
    Adds token to Redis blacklist until expiration.
    Session data is cleared from Redis immediately.
    """
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    await auth_service.revoke_session(token)
