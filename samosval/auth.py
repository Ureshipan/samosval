from dataclasses import dataclass

from flask import abort
from flask_login import (
    LoginManager,
    UserMixin,
    current_user,
    login_required,
)
from werkzeug.security import check_password_hash

from .db import get_db


login_manager = LoginManager()
login_manager.login_view = "auth.login"


@dataclass
class User(UserMixin):
    id: int
    username: str
    role: str
    active: bool

    @property
    def is_active(self) -> bool:  # type: ignore[override]
        return self.active


@login_manager.user_loader
def load_user(user_id: str) -> User | None:
    db = get_db()
    row = db.execute(
        "SELECT id, username, role, is_active FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    if row is None:
        return None
    return User(
        id=row["id"],
        username=row["username"],
        role=row["role"],
        active=bool(row["is_active"]),
    )


def authenticate(username: str, password: str) -> User | None:
    """Return User if credentials are valid and user is active."""
    db = get_db()
    row = db.execute(
        "SELECT id, username, role, is_active, password_hash FROM users WHERE username = ?",
        (username,),
    ).fetchone()
    if row is None:
        return None
    if not row["is_active"]:
        return None
    if not check_password_hash(row["password_hash"], password):
        return None
    return User(
        id=row["id"],
        username=row["username"],
        role=row["role"],
        active=bool(row["is_active"]),
    )


def require_admin() -> None:
    """Abort with 403 if current user is not admin."""
    if not current_user.is_authenticated or getattr(current_user, "role", None) != "admin":
        abort(403)


def login_required_view(view):
    """Decorator alias kept for symmetry with access helpers."""
    return login_required(view)


