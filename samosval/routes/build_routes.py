from flask import Blueprint, abort, render_template
from flask_login import login_required

from ..db import get_db


builds_bp = Blueprint("builds", __name__, url_prefix="/builds")


@builds_bp.get("")
@login_required
def list_builds():
    db = get_db()
    rows = db.execute(
        """
        SELECT b.*, r.image_name
          FROM builds b
          JOIN image_requests r ON b.request_id = r.id
         ORDER BY b.created_at DESC
        """
    ).fetchall()
    return render_template("builds/list.html", builds=rows)


@builds_bp.get("/<int:build_id>")
@login_required
def view_build(build_id: int):
    db = get_db()
    build = db.execute(
        """
        SELECT b.*, r.image_name
          FROM builds b
          JOIN image_requests r ON b.request_id = r.id
         WHERE b.id = ?
        """,
        (build_id,),
    ).fetchone()
    if not build:
        abort(404)
    return render_template("builds/detail.html", build=build)


