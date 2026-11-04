from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User, UserRole
from app.auth.schemas import (
    UserRegisterRequest,
    UserLoginRequest,
    UserResponse,
    TokenResponse,
    UserUpdateRequest,
)
from app.i18n.constants import SUPPORTED_LANGUAGES
from app.core.auth import (
    hash_password,
    verify_password,
    create_access_token,
    ACCESS_TOKEN_EXPIRE_MINUTES,
)
from app.auth.dependencies import get_current_user, require_roles

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new citizen user",
)
def register_user(
    request: UserRegisterRequest,
    db: Session = Depends(get_db),
):
    """
    Register a new user account.
    Public registration strictly creates CITIZEN accounts only.
    Attempts to self-assign OFFICER or ADMIN roles are blocked.
    """
    # Check if email is already taken
    existing_user = db.query(User).filter(User.email == request.email.lower()).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email address already exists.",
        )

    # Securely hash password using bcrypt
    hashed_pwd = hash_password(request.password)

    # Create citizen user in PostgreSQL
    new_user = User(
        name=request.name.strip(),
        email=request.email.lower().strip(),
        password_hash=hashed_pwd,
        role=UserRole.CITIZEN,  # Strictly CITIZEN for public registration
        preferred_language=request.preferred_language,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return new_user


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate user and receive JWT access token",
)
def login_user(
    request: UserLoginRequest,
    db: Session = Depends(get_db),
):
    """
    Authenticate user using email and password.
    Returns signed JWT access token containing identity and role claims.
    """
    user = db.query(User).filter(User.email == request.email.lower().strip()).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Token payload
    token_claims = {
        "sub": str(user.id),
        "email": user.email,
        "name": user.name,
        "role": user.role,
        "department_id": user.department_id,
    }
    access_token = create_access_token(token_claims)

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in_minutes=ACCESS_TOKEN_EXPIRE_MINUTES,
        user=UserResponse.model_validate(user),
    )


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get authenticated user profile",
)
def get_current_user_profile(
    current_user: User = Depends(get_current_user),
):
    """Return the profile of the currently authenticated user identified by JWT."""
    return current_user


@router.patch(
    "/me",
    response_model=UserResponse,
    summary="Update authenticated user profile",
)
@router.put(
    "/me",
    response_model=UserResponse,
    summary="Update authenticated user profile",
)
def update_current_user_profile(
    req: UserUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Update safe profile attributes (name, preferred_language) for the authenticated user.
    Role, email, password hash, and internal IDs cannot be modified through this endpoint.
    """
    if req.name is not None:
        clean_name = req.name.strip()
        if len(clean_name) < 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Name must be at least 2 characters long.",
            )
        current_user.name = clean_name

    if req.preferred_language is not None:
        clean_lang = req.preferred_language.strip().lower()
        if clean_lang not in SUPPORTED_LANGUAGES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Language '{req.preferred_language}' is not supported. Supported: {sorted(list(SUPPORTED_LANGUAGES))}",
            )
        current_user.preferred_language = clean_lang

    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return current_user


@router.get(
    "/protected",
    summary="Test endpoint requiring valid JWT authentication",
)
def test_protected_endpoint(
    current_user: User = Depends(get_current_user),
):
    """Accessible by any valid authenticated user (CITIZEN, OFFICER, ADMIN)."""
    return {
        "status": "success",
        "message": f"Hello, {current_user.name}! You have accessed the protected endpoint successfully.",
        "user_id": current_user.id,
        "email": current_user.email,
        "role": current_user.role,
    }


@router.get(
    "/officer-only",
    summary="Protected endpoint requiring OFFICER or ADMIN role",
)
def test_officer_endpoint(
    current_user: User = Depends(require_roles(UserRole.OFFICER, UserRole.ADMIN)),
):
    """Accessible only by users with role OFFICER or ADMIN."""
    return {
        "status": "success",
        "message": f"Welcome Officer/Admin {current_user.name}.",
        "role": current_user.role,
    }


@router.get(
    "/admin-only",
    summary="Protected endpoint requiring ADMIN role",
)
def test_admin_endpoint(
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    """Accessible only by users with role ADMIN."""
    return {
        "status": "success",
        "message": f"Welcome Administrator {current_user.name}.",
        "role": current_user.role,
    }
