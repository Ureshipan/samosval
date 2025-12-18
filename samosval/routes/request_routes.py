from datetime import datetime

from flask import Blueprint, abort, redirect, render_template, request, url_for, flash
from flask_login import current_user, login_required

from ..access import can_edit_request, can_view_request, role_required
from ..db import get_db


requests_bp = Blueprint("requests", __name__, url_prefix="/requests")


@requests_bp.get("")
@login_required
def list_requests():
    db = get_db()
    status = request.args.get("status")
    if status:
        rows = db.execute(
            "SELECT * FROM image_requests WHERE status = ? ORDER BY created_at DESC",
            (status,),
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT * FROM image_requests ORDER BY created_at DESC"
        ).fetchall()

    # Filter for developer visibility
    visible = [r for r in rows if can_view_request(current_user, r)]
    return render_template("requests/list.html", requests=visible, selected_status=status)


@requests_bp.get("/new")
@role_required("developer")
def new_request():
    return render_template("requests/form.html", req=None)


@requests_bp.get("/<int:request_id>/edit")
@login_required
def edit_request_get(request_id: int):
    db = get_db()
    req = db.execute(
        """
        SELECT r.*, u.username AS owner_username
          FROM image_requests r
          JOIN users u ON r.owner_id = u.id
         WHERE r.id = ?
        """,
        (request_id,),
    ).fetchone()
    if not req or not can_edit_request(current_user, req):
        abort(403)
    return render_template(
        "requests/form.html",
        req=req,
        request_id=request_id,
        owner_login=req["owner_username"],
    )


def _parse_request_form(existing=None):
    form = request.form
    data = {
        "image_name": form.get("image_name", "").strip(),
        "repo_url": form.get("repo_url", "").strip(),
        "repo_branch": form.get("repo_branch", "main").strip() or "main",
        "update_mode": form.get("update_mode", "static"),
        "target_commit": form.get("target_commit", "").strip() or None,
        "base_image": form.get("base_image", "").strip(),
        "run_commands": form.get("run_commands", "").strip() or None,
        "entrypoint": form.get("entrypoint", "").strip() or None,
        "ram_mb": int(form.get("ram_mb", "0") or 0),
        "vcpu": float(form.get("vcpu", "0") or 0),
        "version_tag": form.get("version_tag", "").strip(),
        "collaborators": form.get("collaborators", "").strip() or None,
        "owner_login": form.get("owner_login", "").strip(),
    }
    return data


def _validate_request_form(data):
    errors = []
    if not data["image_name"]:
        errors.append("Имя образа обязательно")
    if not data["repo_url"]:
        errors.append("URL репозитория обязателен")
    if not data["base_image"]:
        errors.append("Базовый образ обязателен")
    if not data["version_tag"]:
        errors.append("Версия/метка обязательна")
    if data["ram_mb"] <= 0 or data["vcpu"] <= 0:
        errors.append("RAM и vCPU должны быть больше 0")
    if data["update_mode"] == "static" and not data["target_commit"]:
        errors.append("Для режима static commit обязателен")
    if not data["owner_login"]:
        errors.append("Необходимо указать owner")
    return errors


@requests_bp.post("/new")
@role_required("developer")
def create_request():
    db = get_db()
    form_data = _parse_request_form()
    errors = _validate_request_form(form_data)
    owner = None
    if form_data["owner_login"]:
        owner = db.execute(
            "SELECT id, username, role FROM users WHERE username = ?", (form_data["owner_login"],)
        ).fetchone()
        if not owner or owner["role"] != "developer":
            errors.append("Owner должен быть существующим пользователем с ролью developer")

    if errors:
        for e in errors:
            flash(e, "error")
        return render_template("requests/form.html", req=form_data)

    now = datetime.utcnow().isoformat(timespec="seconds")
    cur = db.execute(
        """
        INSERT INTO image_requests (
            image_name, repo_url, repo_branch, update_mode, target_commit,
            base_image, run_commands, entrypoint, dockerfile_content,
            ram_mb, vcpu, version_tag, owner_id, status, collaborators,
            created_by, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            form_data["image_name"],
            form_data["repo_url"],
            form_data["repo_branch"],
            form_data["update_mode"],
            form_data["target_commit"],
            form_data["base_image"],
            form_data["run_commands"],
            form_data["entrypoint"],
            None,
            form_data["ram_mb"],
            form_data["vcpu"],
            form_data["version_tag"],
            owner["id"],
            "draft",
            form_data["collaborators"],
            current_user.id,
            now,
            now,
        ),
    )
    db.commit()
    req_id = cur.lastrowid
    flash("Заявка создана как draft", "success")
    return redirect(url_for("requests.view_request", request_id=req_id))


@requests_bp.get("/<int:request_id>")
@login_required
def view_request(request_id: int):
    db = get_db()
    req = db.execute(
        """
        SELECT r.*, u.username AS owner_username, c.username AS created_by_username
          FROM image_requests r
          JOIN users u ON r.owner_id = u.id
          JOIN users c ON r.created_by = c.id
         WHERE r.id = ?
        """,
        (request_id,),
    ).fetchone()
    if not req or not can_view_request(current_user, req):
        abort(403)

    builds = db.execute(
        "SELECT * FROM builds WHERE request_id = ? ORDER BY created_at DESC",
        (request_id,),
    ).fetchall()
    images = db.execute(
        "SELECT * FROM images WHERE request_id = ? ORDER BY created_at DESC",
        (request_id,),
    ).fetchall()
    return render_template(
        "requests/detail.html",
        req=req,
        builds=builds,
        images=images,
    )


@requests_bp.post("/<int:request_id>/submit")
@role_required("developer")
def submit_request(request_id: int):
    db = get_db()
    req = db.execute(
        "SELECT * FROM image_requests WHERE id = ?", (request_id,)
    ).fetchone()
    if not req or not can_view_request(current_user, req):
        abort(403)
    if req["status"] != "draft":
        flash("Можно отправить только draft заявку", "error")
        return redirect(url_for("requests.view_request", request_id=request_id))

    db.execute(
        "UPDATE image_requests SET status = ?, updated_at = ? WHERE id = ?",
        ("submitted", datetime.utcnow().isoformat(timespec="seconds"), request_id),
    )
    db.commit()
    flash("Заявка отправлена оператору", "success")
    return redirect(url_for("requests.view_request", request_id=request_id))


@requests_bp.post("/<int:request_id>/edit")
@login_required
def edit_request(request_id: int):
    db = get_db()
    req = db.execute(
        "SELECT * FROM image_requests WHERE id = ?", (request_id,)
    ).fetchone()
    if not req or not can_edit_request(current_user, req):
        abort(403)

    form_data = _parse_request_form(existing=req)
    errors = _validate_request_form(form_data)
    owner = None
    if form_data["owner_login"]:
        owner = db.execute(
            "SELECT id, username, role FROM users WHERE username = ?", (form_data["owner_login"],)
        ).fetchone()
        if not owner or owner["role"] != "developer":
            errors.append("Owner должен быть существующим пользователем с ролью developer")

    if errors:
        for e in errors:
            flash(e, "error")
        # Reopen detail page with form data
        return render_template("requests/form.html", req=form_data, request_id=request_id)

    now = datetime.utcnow().isoformat(timespec="seconds")
    db.execute(
        """
        UPDATE image_requests
           SET image_name = ?, repo_url = ?, repo_branch = ?,
               update_mode = ?, target_commit = ?, base_image = ?,
               run_commands = ?, entrypoint = ?, ram_mb = ?, vcpu = ?,
               version_tag = ?, owner_id = ?, collaborators = ?, updated_at = ?
         WHERE id = ?
        """,
        (
            form_data["image_name"],
            form_data["repo_url"],
            form_data["repo_branch"],
            form_data["update_mode"],
            form_data["target_commit"],
            form_data["base_image"],
            form_data["run_commands"],
            form_data["entrypoint"],
            form_data["ram_mb"],
            form_data["vcpu"],
            form_data["version_tag"],
            owner["id"] if owner else req["owner_id"],
            form_data["collaborators"],
            now,
            request_id,
        ),
    )
    db.commit()
    flash("Заявка обновлена", "success")
    return redirect(url_for("requests.view_request", request_id=request_id))


@requests_bp.post("/<int:request_id>/status")
@role_required("operator", "admin")
def change_status(request_id: int):
    db = get_db()
    new_status = request.form.get("status")
    if new_status not in {
        "draft",
        "submitted",
        "in_review",
        "approved",
        "rejected",
    }:
        flash("Недопустимый статус", "error")
        return redirect(url_for("requests.view_request", request_id=request_id))

    db.execute(
        "UPDATE image_requests SET status = ?, updated_at = ? WHERE id = ?",
        (new_status, datetime.utcnow().isoformat(timespec="seconds"), request_id),
    )
    db.commit()
    flash(f"Статус заявки изменён на {new_status}", "success")
    return redirect(url_for("requests.view_request", request_id=request_id))


@requests_bp.post("/<int:request_id>/build")
@role_required("operator", "admin")
def trigger_build(request_id: int):
    db = get_db()
    req = db.execute(
        "SELECT * FROM image_requests WHERE id = ?", (request_id,)
    ).fetchone()
    if not req:
        abort(404)

    now = datetime.utcnow().isoformat(timespec="seconds")
    cur = db.execute(
        """
        INSERT INTO builds (request_id, image_id, status, build_log, error_message,
                            built_by, created_at)
        VALUES (?, NULL, ?, ?, NULL, ?, ?)
        """,
        (
            request_id,
            "queued",
            "[ui] Build requested by operator\n",
            current_user.id,
            now,
        ),
    )
    db.commit()
    build_id = cur.lastrowid
    flash(f"Сборка #{build_id} поставлена в очередь", "success")
    return redirect(url_for("requests.view_request", request_id=request_id))


