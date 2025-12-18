from flask import Blueprint, abort, redirect, render_template, request, url_for, flash
from flask_login import login_required, current_user

from ..access import role_required
from ..db import get_db


images_bp = Blueprint("images", __name__, url_prefix="/images")


@images_bp.get("")
@login_required
def list_images():
    db = get_db()
    rows = db.execute(
        """
        SELECT i.*, r.image_name, r.repo_url
          FROM images i
          JOIN image_requests r ON i.request_id = r.id
         ORDER BY i.created_at DESC
        """
    ).fetchall()
    return render_template("images/list.html", images=rows)


@images_bp.get("/<int:image_id>")
@login_required
def view_image(image_id: int):
    db = get_db()
    img = db.execute(
        """
        SELECT i.*, r.image_name, r.repo_url, r.repo_branch, r.update_mode
          FROM images i
          JOIN image_requests r ON i.request_id = r.id
         WHERE i.id = ?
        """,
        (image_id,),
    ).fetchone()
    if not img:
        abort(404)
    deployments = db.execute(
        "SELECT * FROM deployments WHERE image_id = ? ORDER BY created_at DESC",
        (image_id,),
    ).fetchall()
    return render_template("images/detail.html", img=img, deployments=deployments)


@images_bp.post("/<int:image_id>/create_deployment")
@role_required("operator", "admin")
def create_deployment_from_image(image_id: int):
    db = get_db()
    img = db.execute("SELECT * FROM images WHERE id = ?", (image_id,)).fetchone()
    if not img:
        abort(404)

    name = request.form.get("name", "").strip() or f"deploy-{image_id}-{int(current_user.id)}"
    environment = request.form.get("environment", "dev")
    replicas = int(request.form.get("replicas", "1") or 1)
    ports = request.form.get("ports", "").strip() or None

    from datetime import datetime

    now = datetime.utcnow().isoformat(timespec="seconds")
    db.execute(
        """
        INSERT INTO deployments (
            image_id, name, environment, status, replicas,
            ports, stopped_by_operator, needs_restart,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (image_id, name, environment, "deploying", replicas, ports, 0, 0, now, now),
    )
    db.commit()
    flash("Развёртывание создаётся (deploying)", "success")
    return redirect(url_for("images.view_image", image_id=image_id))


