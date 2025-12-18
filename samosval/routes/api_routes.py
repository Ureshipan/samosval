from __future__ import annotations

import time
from datetime import datetime

from flask import (
    Blueprint,
    Response,
    abort,
    jsonify,
    request,
    stream_with_context,
)
from flask_login import login_required, current_user

from ..db import get_db, write_audit
from ..simulator import state


api_bp = Blueprint("api", __name__)


@api_bp.get("/users/search")
@login_required
def users_search():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify([])
    db = get_db()
    rows = db.execute(
        """
        SELECT username
          FROM users
         WHERE username LIKE ?
         ORDER BY username ASC
         LIMIT 20
        """,
        (f"{q}%",),
    ).fetchall()
    return jsonify([r["username"] for r in rows])


@api_bp.get("/builds/<int:build_id>/log")
@login_required
def build_log(build_id: int):
    db = get_db()
    row = db.execute(
        "SELECT id, status, build_log FROM builds WHERE id = ?",
        (build_id,),
    ).fetchone()
    if not row:
        abort(404)
    return jsonify(
        {
            "id": row["id"],
            "status": row["status"],
            "log": row["build_log"] or "",
        }
    )


@api_bp.get("/deployments/<int:deployment_id>/metrics")
@login_required
def deployment_metrics(deployment_id: int):
    # Ensure deployment exists
    db = get_db()
    dep = db.execute(
        "SELECT id FROM deployments WHERE id = ?",
        (deployment_id,),
    ).fetchone()
    if not dep:
        abort(404)

    points = state.get_metrics(deployment_id)
    labels = [p.ts.strftime("%H:%M:%S") for p in points]
    cpu = [p.cpu for p in points]
    ram = [p.ram for p in points]
    return jsonify({"labels": labels, "cpu": cpu, "ram": ram})


@api_bp.get("/deployments/<int:deployment_id>/logs/stream")
@login_required
def deployment_logs_stream(deployment_id: int):
    # Ensure deployment exists
    db = get_db()
    dep = db.execute(
        "SELECT id FROM deployments WHERE id = ?",
        (deployment_id,),
    ).fetchone()
    if not dep:
        abort(404)

    @stream_with_context
    def event_stream():
        last_len = 0
        while True:
            lines = state.get_log_buffer_snapshot(deployment_id)
            if len(lines) > last_len:
                new_lines = lines[last_len:]
                last_len = len(lines)
                for line in new_lines:
                    yield f"data: {line}\n\n"
            time.sleep(1.0)

    return Response(event_stream(), mimetype="text/event-stream")


@api_bp.post("/hooks/commit")
def commit_hook():
    """
    Endpoint for external integrations.
    Body: { "repo_url": "...", "branch": "...", "commit": "sha" }
    """
    payload = request.get_json(silent=True) or {}
    repo_url = (payload.get("repo_url") or "").strip()
    branch = (payload.get("branch") or "").strip()
    commit_sha = (payload.get("commit") or "").strip()

    if not repo_url or not branch or not commit_sha:
        return jsonify({"error": "repo_url, branch, commit required"}), 400

    db = get_db()
    rows = db.execute(
        """
        SELECT d.id,
               d.status,
               d.stopped_by_operator,
               d.needs_restart
          FROM deployments d
          JOIN images i ON d.image_id = i.id
          JOIN image_requests r ON i.request_id = r.id
         WHERE r.update_mode = 'continuous'
           AND r.repo_url = ?
           AND r.repo_branch = ?
        """,
        (repo_url, branch),
    ).fetchall()

    restarted = 0
    marked = 0
    now = datetime.utcnow().isoformat(timespec="seconds")

    for d in rows:
        # Respect operator stop: mark for restart but don't auto-restart
        if d["stopped_by_operator"]:
            db.execute(
                """
                UPDATE deployments
                   SET needs_restart = 1,
                       updated_at = ?
                 WHERE id = ?
                """,
                (now, d["id"]),
            )
            marked += 1
        else:
            db.execute(
                """
                UPDATE deployments
                   SET status = 'deploying',
                       needs_restart = 0,
                       updated_at = ?
                 WHERE id = ?
                """,
                (now, d["id"]),
            )
            restarted += 1
        # Log event to deployment logs
        state.append_log(
            d["id"],
            f"{now} [INFO] Commit {commit_sha} received for {repo_url}@{branch}, "
            f"{'marked for restart' if d['stopped_by_operator'] else 'auto-restart triggered'}",
        )

    if rows:
        db.commit()

    # Audit: commit_hook_received + deployments_restarted
    write_audit(
        user_id=None,
        action="commit_hook_received",
        target_id=None,
        details=f"Commit {commit_sha} for {repo_url}@{branch}, deployments={len(rows)}",
    )
    if restarted or marked:
        write_audit(
            user_id=None,
            action="deployments_restarted",
            target_id=None,
            details=f"Auto-restarted={restarted}, marked={marked}",
        )

    return jsonify(
        {
            "matched_deployments": len(rows),
            "restarted": restarted,
            "marked_for_restart": marked,
        }
    )


