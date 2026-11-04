import sys
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any, Callable
from functools import wraps

import bcrypt
import jwt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.user import User, UserRole

# Secret and Algorithm from central settings
SECRET_KEY = settings.JWT_SECRET_KEY
ALGORITHM = settings.JWT_ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES


def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt with automatic salt."""
    if not password:
        raise ValueError("Password cannot be empty")
    # Truncate at 72 bytes to respect bcrypt specification limit
    pwd_bytes = password.encode("utf-8")[:72]
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(pwd_bytes, salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    if not plain_password or not hashed_password:
        return False
    try:
        pwd_bytes = plain_password.encode("utf-8")[:72]
        hash_bytes = hashed_password.encode("utf-8")
        return bcrypt.checkpw(pwd_bytes, hash_bytes)
    except Exception:
        return False


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Create a signed JWT access token containing user claims."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "iss": settings.PROJECT_NAME,
    })
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Dict[str, Any]:
    """
    Decode and validate a JWT access token.
    Raises jwt.PyJWTError on invalid/expired token.
    """
    payload = jwt.decode(
        token,
        SECRET_KEY,
        algorithms=[ALGORITHM],
        options={"require": ["exp", "sub"]},
    )
    return payload


# --- Flask JWT Integration Helper & Decorators ---

def get_token_from_header(auth_header: Optional[str]) -> Optional[str]:
    """Extract Bearer token from Authorization header string."""
    if not auth_header:
        return None
    parts = auth_header.strip().split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1]
    return None


def flask_jwt_required(roles: Optional[List[str]] = None) -> Callable:
    """
    Flask decorator to protect endpoints with the same JWT issued by FastAPI.
    Extracts Authorization: Bearer <token>, verifies signature and claims,
    and checks roles if specified.
    """
    def decorator(fn: Callable) -> Callable:
        @wraps(fn)
        def wrapper(*args, **kwargs):
            from flask import request, jsonify, g, session
            auth_header = request.headers.get("Authorization")
            token = get_token_from_header(auth_header)
            if not token:
                token = request.cookies.get("auth_token") or session.get("auth_token")
            if not token:
                return jsonify({
                    "error": "Unauthorized",
                    "detail": "Missing or invalid Authorization credentials. Expected: Bearer <token> or active session.",
                }), 401

            try:
                payload = decode_access_token(token)
                user_id = payload.get("sub")
                user_role = payload.get("role")
                if not user_id:
                    return jsonify({"error": "Unauthorized", "detail": "Token missing subject claim"}), 401

                # Role check if required
                if roles and user_role not in roles:
                    return jsonify({
                        "error": "Forbidden",
                        "detail": f"Access denied. Requires one of roles: {roles}. Current role: {user_role}",
                    }), 403

                # Store user info on Flask g context
                g.current_user_id = int(user_id)
                g.current_user_email = payload.get("email")
                g.current_user_role = user_role
                g.token_payload = payload

            except jwt.ExpiredSignatureError:
                return jsonify({"error": "Unauthorized", "detail": "Token has expired"}), 401
            except jwt.PyJWTError as e:
                return jsonify({"error": "Unauthorized", "detail": f"Invalid token: {str(e)}"}), 401

            return fn(*args, **kwargs)
        return wrapper
    return decorator
