"""
Authentication: email/password for now, Google login layered on top later.

How it works:
1. /auth/register or /auth/login returns a JWT access token.
2. The frontend stores that token and sends it as
   "Authorization: Bearer <token>" on every request.
3. get_current_user() (a FastAPI dependency) verifies the token and
   returns the user dict, or raises 401 if missing/invalid/expired.

Per-user data isolation: main.py uses scoped_subject() to turn a
user-facing subject name like "biology" into "u5_biology" before passing
it to any agent/pipeline function. This means Chroma collections and
SQLite rows are automatically separated per user, with ZERO changes
needed in ingestion/pipeline.py, agents/, or db/database.py's existing
plan/quiz functions — they just see a different subject string.
"""

import os
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Header, HTTPException

from db.database import get_user_by_id

# In a real deployment this MUST come from an environment variable, not be
# hardcoded. For a college project, a .env value is enough — just don't
# commit the real secret to a public repo.
JWT_SECRET = os.environ.get("JWT_SECRET", "dev-secret-change-this-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_DAYS = 7


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(user_id: int, email: str) -> str:
    payload = {
        "sub": str(user_id),
        "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(days=JWT_EXPIRY_DAYS),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])


def get_current_user(authorization: str = Header(default=None)) -> dict:
    """
    FastAPI dependency: add `user: dict = Depends(get_current_user)` to any
    endpoint to require login. Raises 401 if the token is missing, invalid,
    or expired.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = authorization.removeprefix("Bearer ").strip()
    try:
        payload = decode_access_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired, please log in again")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

    user = get_user_by_id(int(payload["sub"]))
    if not user:
        raise HTTPException(status_code=401, detail="User no longer exists")
    return user


def scoped_subject(subject: str, user: dict) -> str:
    """Turn a user-facing subject name into a per-user-isolated key."""
    return f"u{user['id']}_{subject}"