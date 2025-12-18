from datetime import datetime

from flask import Blueprint, abort, redirect, render_template, request, url_for, flash
from flask_login import current_user
from werkzeug.security import generate_password_hash

from ..access import role_required
from ..db import get_db, write_audit


admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.before_request
def _ensure_admin():
    # Extra safeguard in addition to decorators
    if not getattr(current_user, "is_authenticated", False):
        abort(401)
    if getattr(current_user, "role", None) != "admin":
        abort(403)


@admin_bp.get("/users")
@role_required("admin")
def users():
    db = get_db()
    rows = db.execute(
        "SELECT id, username, role, is_active, created_at FROM users ORDER BY id ASC"
    ).fetchall()
    return render_template("admin/users.html", users=rows)


@admin_bp.post("/users/create")
@role_required("admin")
def create_user():
    db = get_db()
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    role = request.form.get("role", "").strip()

    if not username or not password or role not in {"admin", "operator", "developer"}:
        flash("Неверные данные пользователя", "error")
        return redirect(url_for("admin.users"))

    existing = db.execute(
        "SELECT id FROM users WHERE username = ?", (username,)
    ).fetchone()
    if existing:
        flash("Пользователь с таким логином уже существует", "error")
        return redirect(url_for("admin.users"))

    now = datetime.utcnow().isoformat(timespec="seconds")
    password_hash = generate_password_hash(password)
    cur = db.execute(
        """
        INSERT INTO users (username, password_hash, role, is_active, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (username, password_hash, role, 1, now),
    )
    db.commit()
    user_id = cur.lastrowid
    write_audit(
        user_id=current_user.id,
        action="user_create",
        target_id=user_id,
        details=f"User {username} created with role {role}",
    )
    flash("Пользователь создан", "success")
    return redirect(url_for("admin.users"))


def _change_user_active(user_id: int, active: int, action: str):
    db = get_db()
    user = db.execute(
        "SELECT id, username FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    if not user:
        abort(404)

    if user["username"] == "root":
        flash("root нельзя блокировать или удалять", "error")
        return redirect(url_for("admin.users"))

    db.execute(
        "UPDATE users SET is_active = ? WHERE id = ?",
        (active, user_id),
    )
    db.commit()
    write_audit(
        user_id=current_user.id,
        action=action,
        target_id=user_id,
        details=f"User {user['username']} {'unblocked' if active else 'blocked'}",
    )
    flash("Статус пользователя обновлён", "success")
    return redirect(url_for("admin.users"))


@admin_bp.post("/users/<int:user_id>/block")
@role_required("admin")
def block_user(user_id: int):
    return _change_user_active(user_id, active=0, action="user_block")


@admin_bp.post("/users/<int:user_id>/unblock")
@role_required("admin")
def unblock_user(user_id: int):
    return _change_user_active(user_id, active=1, action="user_unblock")


@admin_bp.get("/audit")
@role_required("admin")
def audit():
    db = get_db()

    user_login = request.args.get("user", "").strip()
    action = request.args.get("action", "").strip()
    text = request.args.get("text", "").strip()

    query = """
        SELECT a.*, u.username
          FROM audit_log a
          LEFT JOIN users u ON a.user_id = u.id
         WHERE 1=1
    """
    params = []

    if user_login:
        query += " AND u.username = ?"
        params.append(user_login)
    if action:
        query += " AND a.action = ?"
        params.append(action)
    if text:
        query += " AND (a.details LIKE ? OR a.action LIKE ?)"
        like = f"%{text}%"
        params.extend([like, like])

    query += " ORDER BY a.created_at DESC LIMIT 200"

    rows = db.execute(query, params).fetchall()

    # For filter dropdowns
    distinct_actions = db.execute(
        "SELECT DISTINCT action FROM audit_log ORDER BY action ASC"
    ).fetchall()

    return render_template(
        "admin/audit.html",
        rows=rows,
        distinct_actions=distinct_actions,
        user_login=user_login,
        action_filter=action,
        text_filter=text,
    )


