"""Chunk 15a — In-memory rate limiter for setup backup endpoints.

Manager rules (Chunk 15a):
- New helper module. Do not touch machine.py (Chunk 13 production).
- Single shared bucket per IP across /setup/inspect-backup AND
  /setup/restore-from-file. Both are backup attack surface.
- 5 attempts / 10 min / IP.
- Reset on success.
- IP = request.client.host directly (LAN, no trusted proxy).
- Audit log is done by the caller (setup.py) using the decision fields.

Trade-off: in-memory state per uvicorn worker, lost on restart. Same
as Chunk 13 machine.py rate limiter. Acceptable for single-worker LAN
POS deployment.
"""
from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass

# Chunk 15a: env override for testing the timeout logic without waiting 10 minutes.
# Production uses defaults (600 sec, 5 attempts).
WINDOW_SECONDS = int(os.getenv('CHUNK15A_RATE_WINDOW_SECONDS', '600'))
MAX_ATTEMPTS = int(os.getenv('CHUNK15A_RATE_MAX_ATTEMPTS', '5'))

_lock = threading.Lock()
_buckets: dict[str, list[float]] = {}


@dataclass
class Decision:
    allowed: bool
    retry_after_seconds: int  # 0 when allowed
    attempts: int             # count BEFORE this check
    should_audit_hit: bool    # True on transition into blocked state


def check(ip: str) -> Decision:
    """Inspect bucket without recording. Caller records on allow."""
    now = time.time()
    with _lock:
        bucket = [t for t in _buckets.get(ip, []) if now - t < WINDOW_SECONDS]
        if len(bucket) >= MAX_ATTEMPTS:
            retry = max(1, int(WINDOW_SECONDS - (now - bucket[0])) + 1)
            _buckets[ip] = bucket  # prune stale timestamps
            return Decision(False, retry, len(bucket), True)
        if bucket != _buckets.get(ip, []):
            _buckets[ip] = bucket
        return Decision(True, 0, len(bucket), False)


def record(ip: str) -> int:
    """Record an attempt. Returns new count."""
    now = time.time()
    with _lock:
        bucket = [t for t in _buckets.get(ip, []) if now - t < WINDOW_SECONDS]
        bucket.append(now)
        _buckets[ip] = bucket
        return len(bucket)


def reset(ip: str) -> None:
    """Clear the bucket for an IP (called on successful operation)."""
    with _lock:
        _buckets.pop(ip, None)


def current_attempts(ip: str) -> int:
    """Peek at the current count without recording (for tests/logs)."""
    now = time.time()
    with _lock:
        bucket = [t for t in _buckets.get(ip, []) if now - t < WINDOW_SECONDS]
        if bucket != _buckets.get(ip, []):
            _buckets[ip] = bucket
        return len(bucket)


def reset_all() -> None:
    """Test helper. Clears all buckets."""
    with _lock:
        _buckets.clear()
