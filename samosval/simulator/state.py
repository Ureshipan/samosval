from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from typing import Deque, Dict, List, Tuple


LOG_MAX_LINES = 1000
METRICS_MAX_POINTS = 900


@dataclass
class MetricPoint:
    ts: datetime
    cpu: float
    ram: float


_logs_lock = threading.Lock()
_metrics_lock = threading.Lock()

_deployment_logs: Dict[int, Deque[str]] = {}
_deployment_metrics: Dict[int, Deque[MetricPoint]] = {}
# for random walk
_metric_state: Dict[int, Tuple[float, float]] = {}


def append_log(deployment_id: int, line: str) -> None:
    with _logs_lock:
        buf = _deployment_logs.setdefault(deployment_id, deque(maxlen=LOG_MAX_LINES))
        buf.append(line)


def get_recent_logs(deployment_id: int, limit: int = 200) -> List[str]:
    with _logs_lock:
        buf = _deployment_logs.get(deployment_id)
        if not buf:
            return []
        if limit <= 0 or limit >= len(buf):
            return list(buf)
        return list(buf)[-limit:]


def get_log_buffer_snapshot(deployment_id: int) -> List[str]:
    """Snapshot of full log buffer for SSE cursoring."""
    with _logs_lock:
        buf = _deployment_logs.get(deployment_id)
        if not buf:
            return []
        return list(buf)


def append_metric_point(deployment_id: int, point: MetricPoint) -> None:
    with _metrics_lock:
        buf = _deployment_metrics.setdefault(
            deployment_id, deque(maxlen=METRICS_MAX_POINTS)
        )
        buf.append(point)


def get_metrics(deployment_id: int) -> List[MetricPoint]:
    with _metrics_lock:
        buf = _deployment_metrics.get(deployment_id)
        if not buf:
            return []
        return list(buf)


def get_or_create_metric_state(deployment_id: int) -> Tuple[float, float]:
    with _metrics_lock:
        if deployment_id not in _metric_state:
            _metric_state[deployment_id] = (50.0, 50.0)
        return _metric_state[deployment_id]


def update_metric_state(deployment_id: int, cpu: float, ram: float) -> None:
    with _metrics_lock:
        _metric_state[deployment_id] = (cpu, ram)


