"""One writer at a time: the SQLite catalog is only safe with a single writer (ADR 0003)."""

import fcntl
import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

LOCK_FILE = "ledger.lock"


class LockedError(RuntimeError):
    """Another ledger process holds the lock."""


@contextmanager
def exclusive(data_dir: Path) -> Iterator[None]:
    """Hold an exclusive, non-blocking lock on ``<data_dir>/ledger.lock``.

    The kernel releases a flock when its process exits, so a crashed run never leaves a stale
    lock. The holder's PID is written into the file for diagnostics.
    """
    data_dir.mkdir(parents=True, exist_ok=True)
    path = data_dir / LOCK_FILE
    with path.open("a+") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            handle.seek(0)
            holder = handle.read().strip() or "unknown"
            raise LockedError(f"another ledger run is in progress (pid {holder})") from None
        handle.seek(0)
        handle.truncate()
        handle.write(f"{os.getpid()}\n")
        handle.flush()
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)
