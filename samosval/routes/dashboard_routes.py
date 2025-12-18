from flask import Blueprint, render_template
from flask_login import login_required, current_user

from ..db import get_db


dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.get("/dashboard")
@login_required
def dashboard():
    db = get_db()

    # Requests by status
    req_stats = db.execute(
        """
        SELECT status, COUNT(*) AS cnt
          FROM image_requests
         GROUP BY status
        """
    ).fetchall()

    # Deployments by status
    dep_stats = db.execute(
        """
        SELECT status, COUNT(*) AS cnt
          FROM deployments
         GROUP BY status
        """
    ).fetchall()

    # Latest audit log
    audit_rows = db.execute(
        """
        SELECT a.*, u.username
          FROM audit_log a
          LEFT JOIN users u ON a.user_id = u.id
         ORDER BY a.created_at DESC
         LIMIT 20
        """
    ).fetchall()

    return render_template(
        "dashboard.html",
        current_user=current_user,
        req_stats=req_stats,
        dep_stats=dep_stats,
        audit_rows=audit_rows,
    )


