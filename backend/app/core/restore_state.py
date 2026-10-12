from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
import json
import os
from pathlib import Path
import tempfile
import uuid

try:
    import fcntl
except ImportError:  # pragma: no cover - exercised on Windows
    fcntl = None

if os.name == "nt":  # pragma: no cover - exercised on Windows
    import msvcrt
else:
    msvcrt = None


class RestoreState(StrEnum):
    READY = "READY"
    RESTORE_IN_PROGRESS = "RESTORE_IN_PROGRESS"
    RECOVERY_REQUIRED = "RECOVERY_REQUIRED"


class RestoreStateError(RuntimeError):
    pass


class RestoreInterlockBusy(RestoreStateError):
    """Another bootstrap/restore operation currently owns the interlock."""


@contextmanager
def acquire_restore_interlock(backup_root: str | Path, *, wait: bool = False):
    """Coordinate bootstrap and restore on one host.

    This narrow advisory lock does not fence ordinary business writes or
    provide distributed/multi-server locking.
    """
    root = Path(backup_root)
    try:
        root.mkdir(parents=True, exist_ok=True)
        handle = (root / "restore-interlock.lock").open("a+b")
    except OSError as exc:
        raise RestoreStateError("Unable to access the restore interlock.") from exc
    try:
        try:
            if fcntl is not None:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX if wait else fcntl.LOCK_EX | fcntl.LOCK_NB)
            else:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK if wait else msvcrt.LK_NBLCK, 1)
        except (BlockingIOError, OSError) as exc:
            raise RestoreInterlockBusy(
                "Bootstrap or restore is already in progress."
            ) from exc
        try:
            yield
        finally:
            if fcntl is not None:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            else:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    finally:
        handle.close()


@dataclass(frozen=True)
class RestoreStateRecord:
    state: RestoreState
    operation_id: uuid.UUID | None
    expected_shop_id: uuid.UUID | None
    actual_shop_id: uuid.UUID | None
    phase: str
    error: str | None
    updated_at: str


def restore_state_path(backup_root: str | Path) -> Path:
    return Path(backup_root) / "restore-state.json"


def restore_journal_path(backup_root: str | Path) -> Path:
    return Path(backup_root) / "restore-journal.log"


def _uuid_or_none(value: object, field: str) -> uuid.UUID | None:
    if value is None:
        return None
    try:
        return uuid.UUID(str(value))
    except (AttributeError, TypeError, ValueError) as exc:
        raise RestoreStateError(f"Invalid restore state {field}.") from exc


def read_restore_state(path: str | Path) -> RestoreStateRecord:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        state = RestoreState(payload["state"])
        operation_id = _uuid_or_none(payload.get("operation_id"), "operation_id")
        expected_shop_id = _uuid_or_none(payload.get("expected_shop_id"), "expected_shop_id")
        actual_shop_id = _uuid_or_none(payload.get("actual_shop_id"), "actual_shop_id")
        phase = payload["phase"]
        updated_at = payload["updated_at"]
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise RestoreStateError("Unable to read durable restore state.") from exc
    if not isinstance(phase, str) or not isinstance(updated_at, str):
        raise RestoreStateError("Invalid durable restore state fields.")
    error = payload.get("error")
    if error is not None and not isinstance(error, str):
        raise RestoreStateError("Invalid durable restore state error.")
    if state is RestoreState.READY and any(
        value is not None for value in (operation_id, expected_shop_id, actual_shop_id)
    ):
        raise RestoreStateError("READY restore state cannot contain active identity data.")
    if state is not RestoreState.READY and (
        operation_id is None or expected_shop_id is None
    ):
        raise RestoreStateError("Active restore state is missing operation identity data.")
    return RestoreStateRecord(
        state=state,
        operation_id=operation_id,
        expected_shop_id=expected_shop_id,
        actual_shop_id=actual_shop_id,
        phase=phase,
        error=error,
        updated_at=updated_at,
    )


def _write_json_atomically(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, sort_keys=True, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    except Exception:
        try:
            os.unlink(temporary_name)
        except OSError:
            pass
        raise


def write_restore_state(
    path: str | Path,
    *,
    state: RestoreState,
    phase: str,
    operation_id: uuid.UUID | None = None,
    expected_shop_id: uuid.UUID | None = None,
    actual_shop_id: uuid.UUID | None = None,
    error: str | None = None,
) -> RestoreStateRecord:
    payload = {
        "state": state.value,
        "operation_id": str(operation_id) if operation_id else None,
        "expected_shop_id": str(expected_shop_id) if expected_shop_id else None,
        "actual_shop_id": str(actual_shop_id) if actual_shop_id else None,
        "phase": phase,
        "error": error,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    _write_json_atomically(Path(path), payload)
    return read_restore_state(path)


def initialize_restore_state(backup_root: str | Path) -> RestoreStateRecord:
    path = restore_state_path(backup_root)
    if path.exists():
        return read_restore_state(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8") as handle:
            json.dump(
                {
                    "state": RestoreState.READY.value,
                    "operation_id": None,
                    "expected_shop_id": None,
                    "actual_shop_id": None,
                    "phase": "INITIALIZED",
                    "error": None,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                },
                handle,
                sort_keys=True,
                separators=(",", ":"),
            )
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError:
        pass
    return read_restore_state(path)


def ensure_restore_state(backup_root: str | Path) -> RestoreStateRecord:
    return read_restore_state(restore_state_path(backup_root))


def append_restore_journal(backup_root: str | Path, event: dict[str, object]) -> None:
    path = restore_journal_path(backup_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
