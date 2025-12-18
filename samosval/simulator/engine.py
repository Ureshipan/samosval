from __future__ import annotations

import random
import threading
import time
from datetime import datetime

from flask import current_app

from ..db import get_db, write_audit
from . import state


class SimulationEngine(threading.Thread):
    """
    Background daemon thread that simulates:
    - builds lifecycle and logs
    - deployments lifecycle
    - runtime logs & metrics for running deployments
    """

    def __init__(self, app):
        super().__init__(daemon=True)
        self.app = app
        self._stop_event = threading.Event()

    def stop(self) -> None:
        self._stop_event.set()

    def run(self) -> None:  # pragma: no cover - background loop
        with self.app.app_context():
            while not self._stop_event.is_set():
                try:
                    self._tick()
                except Exception:  # log but never crash the thread
                    current_app.logger.exception("SimulationEngine tick failed")
                time.sleep(1.0)

    # --- internals -----------------------------------------------------

    def _tick(self) -> None:
        self._process_builds()
        self._process_deployments()
        self._generate_runtime()

    def _process_builds(self) -> None:
        """
        builds.status: queued -> building -> success/failed
        During building we enrich build_log.
        """
        db = get_db()
        rows = db.execute(
            "SELECT * FROM builds WHERE status IN ('queued', 'building')"
        ).fetchall()
        for row in rows:
            status = row["status"]
            log_text = row["build_log"] or ""

            if status == "queued":
                # Move to building
                log_text += "[engine] Build queued, starting...\n"
                db.execute(
                    "UPDATE builds SET status = ?, build_log = ? WHERE id = ?",
                    ("building", log_text, row["id"]),
                )
                self._audit(
                    user_id=row["built_by"],
                    action="build_start",
                    target_id=row["id"],
                    details=f"Build {row['id']} started by simulation engine",
                )
            elif status == "building":
                # Add random log lines
                for _ in range(random.randint(1, 3)):
                    log_text += self._random_build_log_line(row)

                # Randomly finish
                if random.random() < 0.3:
                    if random.random() < 0.85:
                        # success -> create image
                        image_id = self._create_image_for_build(db, row)
                        db.execute(
                            """
                            UPDATE builds
                               SET status = ?, image_id = ?, build_log = ?
                             WHERE id = ?
                            """,
                            ("success", image_id, log_text + "[engine] Build SUCCESS\n", row["id"]),
                        )
                        self._audit(
                            user_id=row["built_by"],
                            action="build_finish",
                            target_id=row["id"],
                            details=f"Build {row['id']} finished successfully (image_id={image_id})",
                        )
                    else:
                        error_message = "Simulated build failure"
                        db.execute(
                            """
                            UPDATE builds
                               SET status = ?, error_message = ?, build_log = ?
                             WHERE id = ?
                            """,
                            (
                                "failed",
                                error_message,
                                log_text + "[engine] Build FAILED\n",
                                row["id"],
                            ),
                        )
                        self._audit(
                            user_id=row["built_by"],
                            action="build_finish",
                            target_id=row["id"],
                            details=f"Build {row['id']} failed",
                        )
                else:
                    db.execute(
                        "UPDATE builds SET build_log = ? WHERE id = ?",
                        (log_text, row["id"]),
                    )

        if rows:
            db.commit()

    def _create_image_for_build(self, db, build_row):
        """Create image from build's request if not already linked."""
        req = db.execute(
            "SELECT * FROM image_requests WHERE id = ?", (build_row["request_id"],)
        ).fetchone()
        if not req:
            return None
        image_name = req["image_name"]
        version = req["version_tag"]
        image_tag = f"{image_name}:{version}"
        now = datetime.utcnow().isoformat(timespec="seconds")
        cur = db.execute(
            """
            INSERT INTO images (request_id, name, version, image_tag, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (req["id"], image_name, version, image_tag, now),
        )
        image_id = cur.lastrowid
        db.commit()
        return image_id

    def _random_build_log_line(self, build_row) -> str:
        messages = [
            "Cloning repository...",
            "Checking out commit...",
            "Running Docker build step...",
            "Installing dependencies...",
            "Optimizing layers...",
            "Pushing image to registry (simulated)...",
        ]
        msg = random.choice(messages)
        return f"[engine] {msg}\n"

    def _process_deployments(self) -> None:
        """
        deployments.status: deploying -> running/failed (with alerts on fail)
        """
        db = get_db()
        rows = db.execute(
            "SELECT * FROM deployments WHERE status = 'deploying'"
        ).fetchall()
        for row in rows:
            # Randomly decide final status
            if random.random() < 0.4:
                if random.random() < 0.85:
                    new_status = "running"
                    alert = None
                else:
                    new_status = "failed"
                    alert = "Deployment failed during startup (simulated)"

                now = datetime.utcnow().isoformat(timespec="seconds")
                db.execute(
                    """
                    UPDATE deployments
                       SET status = ?, updated_at = ?
                     WHERE id = ?
                    """,
                    (new_status, now, row["id"]),
                )

                if alert:
                    db.execute(
                        """
                        INSERT INTO alerts (alert_type, target_id, message, resolved, created_at)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        ("deployment", row["id"], alert, 0, now),
                    )
                    self._audit(
                        user_id=None,
                        action="deployment_failed",
                        target_id=row["id"],
                        details=alert,
                    )
                else:
                    self._audit(
                        user_id=None,
                        action="deployment_running",
                        target_id=row["id"],
                        details="Deployment is now running",
                    )
        if rows:
            db.commit()

    def _generate_runtime(self) -> None:
        """Generate runtime logs and metrics for running deployments."""
        db = get_db()
        deployments = db.execute(
            """
            SELECT d.id, d.name, d.environment, i.image_tag
              FROM deployments d
              JOIN images i ON d.image_id = i.id
             WHERE d.status = 'running'
            """
        ).fetchall()

        for d in deployments:
            # Logs
            for _ in range(random.randint(1, 3)):
                line = self._random_runtime_log_line(d)
                state.append_log(d["id"], line)
            # Metrics
            self._generate_metrics_for_deployment(d["id"])

    def _random_runtime_log_line(self, d_row) -> str:
        level = random.choices(
            population=["INFO", "WARN", "ERROR"],
            weights=[80, 15, 5],
        )[0]
        messages = {
            "INFO": [
                "Handling request",
                "Background job executed",
                "Health check OK",
            ],
            "WARN": [
                "Slow response detected",
                "Retrying external call",
            ],
            "ERROR": [
                "Unhandled exception in worker",
                "Database connection timeout",
            ],
        }
        msg = random.choice(messages[level])
        ts = datetime.utcnow().isoformat(timespec="seconds")
        return f"{ts} [{level}] {d_row['name']} ({d_row['image_tag']}) - {msg}"

    def _generate_metrics_for_deployment(self, deployment_id: int) -> None:
        cpu, ram = state.get_or_create_metric_state(deployment_id)
        # random walk
        cpu += random.uniform(-5.0, 5.0)
        ram += random.uniform(-5.0, 5.0)
        cpu = max(0.0, min(100.0, cpu))
        ram = max(0.0, min(100.0, ram))
        state.update_metric_state(deployment_id, cpu, ram)

        point = state.MetricPoint(
            ts=datetime.utcnow(),
            cpu=cpu,
            ram=ram,
        )
        state.append_metric_point(deployment_id, point)

    def _audit(self, user_id, action: str, target_id: int | None, details: str) -> None:
        write_audit(user_id=user_id, action=action, target_id=target_id, details=details)


