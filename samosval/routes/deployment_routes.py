from datetime import datetime

from flask import Blueprint, abort, redirect, render_template, request, url_for, flash
from flask_login import current_user, login_required

from ..access import can_manage_deployment
from ..db import get_db, write_audit
from ..simulator import state


deployments_bp = Blueprint("deployments", __name__, url_prefix="/deployments")


@deployments_bp.get("")
@login_required
def list_deployments():
    db = get_db()
    rows = db.execute(
        """
        SELECT d.*,
               i.image_tag,
               r.image_name,
               r.repo_url,
               r.repo_branch,
               r.update_mode,
               r.owner_id       AS req_owner_id,
               r.created_by     AS req_created_by,
               r.collaborators  AS req_collaborators
          FROM deployments d
          JOIN images i ON d.image_id = i.id
          JOIN image_requests r ON i.request_id = r.id
         ORDER BY d.created_at DESC
        """
    ).fetchall()

    def _can_view(row) -> bool:
        role = getattr(current_user, "role", None)
        if role in {"admin", "operator"}:
            return True
        if role != "developer":
            return False
        user_id = int(current_user.id)
        if user_id in {row["req_owner_id"], row["req_created_by"]}:
            return True
        from ..access import _normalize_collaborators  # reuse helper

        collab = _normalize_collaborators(row["req_collaborators"])
        return current_user.username in collab

    visible = [row for row in rows if _can_view(row)]
    return render_template("deployments/list.html", deployments=visible)


@deployments_bp.get("/<int:deployment_id>")
@login_required
def view_deployment(deployment_id: int):
    db = get_db()
    row = db.execute(
        """
        SELECT d.*,
               i.image_tag,
               r.image_name,
               r.owner_id       AS req_owner_id,
               r.created_by     AS req_created_by,
               r.collaborators  AS req_collaborators
          FROM deployments d
          JOIN images i ON d.image_id = i.id
          JOIN image_requests r ON i.request_id = r.id
         WHERE d.id = ?
        """,
        (deployment_id,),
    ).fetchone()
    if not row:
        abort(404)

    # visibility check (same as list)
    role = getattr(current_user, "role", None)
    allowed = False
    if role in {"admin", "operator"}:
        allowed = True
    elif role == "developer":
        user_id = int(current_user.id)
        if user_id in {row["req_owner_id"], row["req_created_by"]}:
            allowed = True
        else:
            from ..access import _normalize_collaborators

            collab = _normalize_collaborators(row["req_collaborators"])
            allowed = current_user.username in collab
    if not allowed:
        abort(403)

    recent_logs = state.get_recent_logs(deployment_id, limit=200)

    can_control = can_manage_deployment(
        current_user,
        row,
        owner_id=row["req_owner_id"],
    )

    return render_template(
        "deployments/detail.html",
        deployment=row,
        recent_logs=recent_logs,
        can_control=can_control,
    )


def _get_deployment_with_owner(deployment_id: int):
    db = get_db()
    row = db.execute(
        """
        SELECT d.*,
               r.owner_id AS req_owner_id
          FROM deployments d
          JOIN images i ON d.image_id = i.id
          JOIN image_requests r ON i.request_id = r.id
         WHERE d.id = ?
        """,
        (deployment_id,),
    ).fetchone()
    return row


def _ensure_can_manage(deployment_id: int):
    row = _get_deployment_with_owner(deployment_id)
    if not row:
        abort(404)
    if not can_manage_deployment(current_user, row, owner_id=row["req_owner_id"]):
        abort(403)
    return row


@deployments_bp.post("/<int:deployment_id>/start")
@login_required
def start_deployment(deployment_id: int):
    row = _ensure_can_manage(deployment_id)
    db = get_db()

    now = datetime.utcnow().isoformat(timespec="seconds")
    db.execute(
        """
        UPDATE deployments
           SET status = 'deploying',
               updated_at = ?,
               needs_restart = 0
         WHERE id = ?
        """,
        (now, deployment_id),
    )
    db.commit()
    write_audit(
        user_id=current_user.id,
        action="deployment_start",
        target_id=deployment_id,
        details=f"Deployment {deployment_id} start requested",
    )
    flash("Развёртывание запускается", "success")
    return redirect(url_for("deployments.view_deployment", deployment_id=deployment_id))


@deployments_bp.post("/<int:deployment_id>/stop")
@login_required
def stop_deployment(deployment_id: int):
    row = _ensure_can_manage(deployment_id)
    db = get_db()

    now = datetime.utcnow().isoformat(timespec="seconds")
    stopped_by_operator = 1 if getattr(current_user, "role", None) in {"admin", "operator"} else 0
    db.execute(
        """
        UPDATE deployments
           SET status = 'stopped',
               updated_at = ?,
               stopped_by_operator = ?
         WHERE id = ?
        """,
        (now, stopped_by_operator, deployment_id),
    )
    db.commit()
    write_audit(
        user_id=current_user.id,
        action="deployment_stop",
        target_id=deployment_id,
        details=f"Deployment {deployment_id} stopped",
    )
    flash("Развёртывание остановлено", "success")
    return redirect(url_for("deployments.view_deployment", deployment_id=deployment_id))


@deployments_bp.post("/<int:deployment_id>/restart")
@login_required
def restart_deployment(deployment_id: int):
    row = _ensure_can_manage(deployment_id)
    db = get_db()

    now = datetime.utcnow().isoformat(timespec="seconds")
    db.execute(
        """
        UPDATE deployments
           SET status = 'deploying',
               updated_at = ?,
               needs_restart = 0
         WHERE id = ?
        """,
        (now, deployment_id),
    )
    db.commit()
    write_audit(
        user_id=current_user.id,
        action="deployment_restart",
        target_id=deployment_id,
        details=f"Deployment {deployment_id} restart requested",
    )
    flash("Развёртывание перезапускается", "success")
    return redirect(url_for("deployments.view_deployment", deployment_id=deployment_id))


@deployments_bp.post("/<int:deployment_id>/delete")
@login_required
def delete_deployment(deployment_id: int):
    row = _ensure_can_manage(deployment_id)
    db = get_db()
    db.execute("DELETE FROM deployments WHERE id = ?", (deployment_id,))
    db.commit()
    write_audit(
        user_id=current_user.id,
        action="deployment_delete",
        target_id=deployment_id,
        details=f"Deployment {deployment_id} deleted",
    )
    flash("Развёртывание удалено", "success")
    return redirect(url_for("deployments.list_deployments"))


