#!/usr/bin/env python3
# tools/todo_lock.py -- lock de escrita do TODO.md (TAB-CONC-004)
# Copyright (C) 2026 Petrus Silva Costa
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.
"""
todo_lock -- lock exclusivo de escrita do TODO.md (stdlib only).

Preferencia de local do lockfile:
  1. <git-common-dir>/tab-pendencias/todo.write.lock  (compartilhado entre
     worktrees do mesmo repo)
  2. fallback: <dir-do-TODO>/.TODO.md.lock

Mecanismos (nessa ordem, o que estiver disponivel):
  - POSIX: fcntl.flock (LOCK_EX | LOCK_NB em loop ate timeout)
  - Windows: msvcrt.locking no mesmo arquivo
  - fallback universal: create exclusive (O_CREAT|O_EXCL) do lockfile com
    conteudo "pid\\ttimestamp"; stale apos `stale_seconds` (default 120s)
    e reclaimavel (apaga e tenta de novo)

Reentrant no mesmo thread: aninhamento (ex.: drain que chama intake) so
incrementa contador; so a saida mais externa libera o SO.

Timeout default 10s; em falha levanta TodoLockError com mensagem clara.
"""
from __future__ import annotations

import os
import subprocess
import threading
import time
from datetime import datetime, timezone

DEFAULT_TIMEOUT = 10.0
DEFAULT_STALE_SECONDS = 120.0
_LOCK_SUBPATH = ("tab-pendencias", "todo.write.lock")
_SIDE_CAR_NAME = ".TODO.md.lock"

# reentrancy por path absoluto do lockfile, por thread
_local = threading.local()


class TodoLockError(Exception):
    """Nao conseguiu adquirir o lock a tempo (ou erro de SO)."""


def _run_git(args, cwd):
    try:
        r = subprocess.run(
            ["git", *args],
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    return r.stdout.strip()


def resolve_git_common_dir(cwd=None):
    """Caminho absoluto do git common dir, ou None."""
    base = cwd if cwd is not None else os.getcwd()
    out = _run_git(["rev-parse", "--git-common-dir"], cwd=base)
    if not out:
        return None
    if os.path.isabs(out):
        resolved = out
    else:
        resolved = os.path.join(str(base), out)
    return os.path.normpath(os.path.abspath(resolved))


def default_lock_path(todo_path: str) -> str:
    """Resolve o caminho do lockfile para um TODO.md."""
    abs_todo = os.path.abspath(todo_path)
    parent = os.path.dirname(abs_todo) or os.getcwd()
    common = resolve_git_common_dir(cwd=parent)
    if common:
        lock_dir = os.path.join(common, _LOCK_SUBPATH[0])
        try:
            os.makedirs(lock_dir, mode=0o700, exist_ok=True)
        except OSError:
            pass
        return os.path.join(common, *_LOCK_SUBPATH)
    return os.path.join(parent, _SIDE_CAR_NAME)


def _held_map():
    if not hasattr(_local, "held"):
        _local.held = {}
    return _local.held


def _utc_now() -> float:
    return datetime.now(timezone.utc).timestamp()


def _fcntl_available() -> bool:
    try:
        import fcntl  # noqa: F401
        return True
    except ImportError:
        return False


def _msvcrt_available() -> bool:
    try:
        import msvcrt  # noqa: F401
        return True
    except ImportError:
        return False


def _try_fcntl(fh) -> bool:
    try:
        import fcntl
    except ImportError:
        return False
    try:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except (OSError, BlockingIOError):
        return False


def _release_fcntl(fh) -> None:
    try:
        import fcntl
        fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
    except (ImportError, OSError):
        pass


def _try_msvcrt(fh) -> bool:
    try:
        import msvcrt
    except ImportError:
        return False
    try:
        # 1 byte lock at offset 0
        fh.seek(0)
        msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
        return True
    except OSError:
        return False


def _release_msvcrt(fh) -> None:
    try:
        import msvcrt
        fh.seek(0)
        msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
    except (ImportError, OSError):
        pass


def _is_stale(lock_path: str, stale_seconds: float) -> bool:
    try:
        with open(lock_path, encoding="utf-8", errors="replace") as fh:
            body = fh.read().strip()
    except OSError:
        return True
    # formato: "pid\ttimestamp" ou so timestamp
    ts = None
    parts = body.split("\t")
    if len(parts) >= 2:
        try:
            ts = float(parts[1])
        except ValueError:
            ts = None
    if ts is None:
        try:
            ts = float(parts[0])
        except ValueError:
            # sem timestamp legivel: usa mtime
            try:
                ts = os.path.getmtime(lock_path)
            except OSError:
                return True
    return (_utc_now() - ts) >= stale_seconds


def _try_exclusive_create(lock_path: str, stale_seconds: float) -> bool:
    """Create exclusive lockfile; reclaim if stale."""
    payload = f"{os.getpid()}\t{_utc_now():.6f}\n"
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    try:
        fd = os.open(lock_path, flags, 0o600)
    except FileExistsError:
        if _is_stale(lock_path, stale_seconds):
            try:
                os.unlink(lock_path)
            except OSError:
                return False
            try:
                fd = os.open(lock_path, flags, 0o600)
            except FileExistsError:
                return False
        else:
            return False
    except OSError:
        return False
    try:
        os.write(fd, payload.encode("utf-8"))
    finally:
        os.close(fd)
    return True


def _release_exclusive(lock_path: str) -> None:
    try:
        with open(lock_path, encoding="utf-8", errors="replace") as fh:
            body = fh.read().strip()
        pid_s = body.split("\t", 1)[0]
        if pid_s.isdigit() and int(pid_s) != os.getpid():
            # nao apagar lock de outro processo
            return
    except OSError:
        pass
    try:
        os.unlink(lock_path)
    except OSError:
        pass


class TodoWriteLock:
    """Context manager: adquire lock de escrita do TODO.md.

    Parameters
    ----------
    path:
        Caminho do TODO.md (ou qualquer path cuja escrita deva serializar).
    timeout:
        Segundos maximos esperando o lock (default 10).
    stale_seconds:
        Idade apos a qual lockfile exclusive e reclaimavel (default 120).
    lock_path:
        Override do caminho do lockfile (testes).
    poll_interval:
        Intervalo entre tentativas (default 0.05s).
    """

    def __init__(
        self,
        path: str,
        *,
        timeout: float = DEFAULT_TIMEOUT,
        stale_seconds: float = DEFAULT_STALE_SECONDS,
        lock_path: str | None = None,
        poll_interval: float = 0.05,
    ):
        self.todo_path = os.path.abspath(path)
        self.timeout = float(timeout)
        self.stale_seconds = float(stale_seconds)
        self.poll_interval = float(poll_interval)
        self.lock_path = (
            os.path.abspath(lock_path)
            if lock_path
            else default_lock_path(self.todo_path)
        )
        self._fh = None
        self._mode = None  # "fcntl" | "msvcrt" | "file"
        self._nested = False

    def __enter__(self):
        held = _held_map()
        key = self.lock_path
        if key in held and held[key] > 0:
            held[key] += 1
            self._nested = True
            return self
        self._acquire()
        held[key] = 1
        self._nested = False
        return self

    def __exit__(self, exc_type, exc, tb):
        held = _held_map()
        key = self.lock_path
        if self._nested or (key in held and held[key] > 1):
            held[key] = held.get(key, 1) - 1
            if held[key] <= 0:
                held.pop(key, None)
            return False
        held.pop(key, None)
        self._release()
        return False

    def _acquire(self) -> None:
        parent = os.path.dirname(self.lock_path)
        if parent:
            try:
                os.makedirs(parent, mode=0o700, exist_ok=True)
            except OSError as exc:
                raise TodoLockError(
                    f"todo_lock: nao criou dir do lock {parent!r}: {exc}"
                ) from exc

        deadline = time.monotonic() + max(0.0, self.timeout)
        # Nunca misturar fcntl/msvcrt com exclusive-create: um holder em
        # modo "file" deixaria o segundo writer adquirir flock no mesmo
        # path e os dois "teriam" o lock.
        if _fcntl_available():
            backend = "fcntl"
        elif _msvcrt_available():
            backend = "msvcrt"
        else:
            backend = "file"

        while True:
            ok = self._try_once(backend=backend)
            if ok:
                return
            if time.monotonic() >= deadline:
                raise TodoLockError(
                    f"todo_lock: timeout ({self.timeout}s) ao adquirir "
                    f"lock {self.lock_path!r} para {self.todo_path!r}"
                )
            time.sleep(self.poll_interval)

    def _try_once(self, *, backend: str) -> bool:
        if backend == "fcntl":
            try:
                fh = open(self.lock_path, "a+b")
            except OSError:
                return False
            if _try_fcntl(fh):
                try:
                    fh.seek(0)
                    fh.truncate()
                    fh.write(
                        f"{os.getpid()}\t{_utc_now():.6f}\n".encode("utf-8")
                    )
                    fh.flush()
                except OSError:
                    pass
                self._fh = fh
                self._mode = "fcntl"
                return True
            fh.close()
            return False

        if backend == "msvcrt":
            try:
                fh = open(self.lock_path, "a+b")
            except OSError:
                return False
            if _try_msvcrt(fh):
                self._fh = fh
                self._mode = "msvcrt"
                return True
            fh.close()
            return False

        # backend == "file": exclusive create + stale reclaim
        if _try_exclusive_create(self.lock_path, self.stale_seconds):
            self._fh = None
            self._mode = "file"
            return True
        return False

    def _release(self) -> None:
        mode = self._mode
        fh = self._fh
        self._fh = None
        self._mode = None
        if mode == "fcntl" and fh is not None:
            _release_fcntl(fh)
            try:
                fh.close()
            except OSError:
                pass
            return
        if mode == "msvcrt" and fh is not None:
            _release_msvcrt(fh)
            try:
                fh.close()
            except OSError:
                pass
            return
        if mode == "file":
            _release_exclusive(self.lock_path)
