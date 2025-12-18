from __future__ import annotations

from functools import wraps
from typing import Callable, Iterable

from flask import abort
from flask_login import current_user, login_required


def role_required(*roles: str) -> Callable:
    """Decorator to require that current_user has one of given roles."""

    def decorator(view: Callable) -> Callable:
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            user_role = getattr(current_user, "role", None)
            if user_role not in roles:
                abort(403)
            return view(*args, **kwargs)

        return wrapped

    return decorator


def _normalize_collaborators(collaborators: str | None) -> set[str]:
    if not collaborators:
        return set()
    return {
        login.strip()
        for login in collaborators.split(",")
        if login.strip()
    }


def can_view_request(user, req_row) -> bool:
    """Return True if user may view the given image_request row."""
    role = getattr(user, "role", None)
    if role in {"admin", "operator"}:
        return True

    if role != "developer":
        return False

    user_id = int(getattr(user, "id", 0))
    if user_id in {req_row["created_by"], req_row["owner_id"]}:
        return True

    collab = _normalize_collaborators(req_row["collaborators"])
    username = getattr(user, "username", "")
    return username in collab


def can_edit_request(user, req_row) -> bool:
    """Editing rules: operator/admin anywhere; developer within own requests."""
    role = getattr(user, "role", None)
    if role in {"admin", "operator"}:
        return True
    if role != "developer":
        return False
    user_id = int(getattr(user, "id", 0))
    return user_id in {req_row["created_by"], req_row["owner_id"]}


def can_manage_deployment(user, deployment_row, owner_id: int) -> bool:
    """
    Deployment control rules:
    - operator/admin: full control
    - developer: may start/stop/restart only if he is owner and not stopped_by_operator.
    """
    role = getattr(user, "role", None)
    if role in {"admin", "operator"}:
        return True
    if role != "developer":
        return False

    user_id = int(getattr(user, "id", 0))
    if user_id != int(owner_id):
        return False
    if deployment_row["stopped_by_operator"]:
        return False
    return True


def filter_requests_for_user(rows: Iterable, user) -> list:
    """Return subset of image_requests rows visible to the user."""
    return [row for row in rows if can_view_request(user, row)]


