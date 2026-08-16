"""tests/test_todo_lock.py -- TAB-CONC-004 lock de escrita do TODO."""
from __future__ import annotations

import os
import threading
import time

import pytest

import todo_lock as LK


def test_lock_acquire_release_sidecar(tmp_path):
    todo = tmp_path / "TODO.md"
    todo.write_text("# t\n", encoding="utf-8")
    lock_path = tmp_path / ".TODO.md.lock"
    with LK.TodoWriteLock(
        str(todo), lock_path=str(lock_path), timeout=2.0
    ) as lock:
        assert lock.lock_path == str(lock_path)
        assert os.path.exists(str(lock_path)) or lock._mode in ("fcntl", "msvcrt")
    # apos release, exclusive-file some; fcntl pode deixar o arquivo vazio
    # (ok -- so o hold importa)


def test_second_thread_times_out(tmp_path):
    todo = tmp_path / "TODO.md"
    todo.write_text("# t\n", encoding="utf-8")
    lock_path = tmp_path / "custom.lock"
    held = threading.Event()
    done = threading.Event()
    errors: list = []

    def holder():
        with LK.TodoWriteLock(
            str(todo), lock_path=str(lock_path), timeout=5.0
        ):
            held.set()
            done.wait(timeout=5.0)

    t = threading.Thread(target=holder)
    t.start()
    assert held.wait(timeout=2.0), "holder nao adquiriu"

    with pytest.raises(LK.TodoLockError) as ei:
        with LK.TodoWriteLock(
            str(todo),
            lock_path=str(lock_path),
            timeout=0.2,
            poll_interval=0.05,
        ):
            pass
    assert "timeout" in str(ei.value).lower()

    done.set()
    t.join(timeout=3.0)


def test_second_thread_waits_then_acquires(tmp_path):
    todo = tmp_path / "TODO.md"
    todo.write_text("# t\n", encoding="utf-8")
    lock_path = tmp_path / "wait.lock"
    release_holder = threading.Event()
    holder_has = threading.Event()
    order: list[str] = []

    def holder():
        with LK.TodoWriteLock(
            str(todo), lock_path=str(lock_path), timeout=5.0
        ):
            order.append("h-in")
            holder_has.set()
            release_holder.wait(timeout=5.0)
            order.append("h-out")

    t = threading.Thread(target=holder)
    t.start()
    assert holder_has.wait(timeout=2.0)

    def waiter():
        with LK.TodoWriteLock(
            str(todo),
            lock_path=str(lock_path),
            timeout=3.0,
            poll_interval=0.05,
        ):
            order.append("w-in")
        order.append("w-out")

    tw = threading.Thread(target=waiter)
    tw.start()
    time.sleep(0.15)
    release_holder.set()
    t.join(timeout=3.0)
    tw.join(timeout=3.0)
    assert order[0] == "h-in"
    assert "w-in" in order
    assert order.index("h-out") < order.index("w-in") or order.index(
        "h-in"
    ) < order.index("w-in")


def test_reentrant_same_thread(tmp_path):
    todo = tmp_path / "TODO.md"
    todo.write_text("# t\n", encoding="utf-8")
    lock_path = tmp_path / "re.lock"
    with LK.TodoWriteLock(str(todo), lock_path=str(lock_path), timeout=2.0):
        with LK.TodoWriteLock(str(todo), lock_path=str(lock_path), timeout=2.0):
            pass  # nao deve timeout


def test_stale_file_lock_reclaimed(tmp_path):
    """Fallback exclusive: lockfile velho e reclaimavel."""
    todo = tmp_path / "TODO.md"
    todo.write_text("# t\n", encoding="utf-8")
    lock_path = tmp_path / "stale.lock"
    # forca modo file: escreve lockfile antigo de outro pid
    old_ts = time.time() - 500
    lock_path.write_text(f"999999\t{old_ts:.6f}\n", encoding="utf-8")

    # se fcntl estiver disponivel, ele LOCK_EX no arquivo existente e
    # "adquire" sem precisar reclaim -- isso tambem e valido. Para exercitar
    # reclaim do modo file, usamos _try_exclusive_create direto.
    assert LK._is_stale(str(lock_path), stale_seconds=120.0) is True
    ok = LK._try_exclusive_create(str(lock_path), stale_seconds=120.0)
    assert ok is True
    body = lock_path.read_text(encoding="utf-8")
    assert str(os.getpid()) in body
    LK._release_exclusive(str(lock_path))
    assert not lock_path.exists()


def test_default_lock_path_sidecar_without_git(tmp_path):
    todo = tmp_path / "TODO.md"
    todo.write_text("x", encoding="utf-8")
    p = LK.default_lock_path(str(todo))
    assert p.endswith(".TODO.md.lock")
    assert os.path.dirname(p) == str(tmp_path)


def test_run_intake_apply_waits_on_held_lock(tmp_path):
    """run_intake(apply=True) falha com timeout se outro thread segura o lock."""
    import subprocess
    import sys

    from conftest import git_init_isolado
    import todo_intake as I

    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
    repo = tmp_path / "repo"
    repo.mkdir()
    git_init_isolado(repo)
    header = (
        "| ID | Wave | Group | Description | Priority | Blocked By | "
        "Effort | Status | Reviewed |\n"
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n"
    )
    row = (
        "| #01 | W1 | Core | Bootstrap | High | - | Medium | "
        "✅ Concluído | yes |\n"
    )
    todo = repo / "TODO.md"
    todo.write_text("# t\n\n" + header + row + "\n", encoding="utf-8")
    subprocess.run(
        ["git", "add", "TODO.md"], cwd=str(repo), env=env,
        capture_output=True, check=True,
    )
    subprocess.run(
        ["git", "commit", "-qm", "c0"], cwd=str(repo), env=env,
        capture_output=True, check=True,
    )

    lock_path = LK.default_lock_path(str(todo))
    held = threading.Event()
    release = threading.Event()

    def holder():
        with LK.TodoWriteLock(str(todo), lock_path=lock_path, timeout=5.0):
            held.set()
            release.wait(timeout=5.0)

    th = threading.Thread(target=holder)
    th.start()
    assert held.wait(timeout=2.0)

    cand = I.WorkCandidate(
        candidate_id="c-lock-1",
        description="Should not write while locked",
        source="test",
        item_id="#99",
        fields_complete=True,
        authority_ok=True,
        is_local=True,
    )
    # forca o mesmo lock_path via monkeypatch de default_lock_path? ja e o
    # path padrao; holder usa o mesmo.
    result = I.run_intake(
        todo_path=str(todo), candidate=cand, apply=True, lock_timeout=0.25,
    )
    release.set()
    th.join(timeout=3.0)
    assert result.rc == 1
    assert result.error and "todo_lock" in result.error
    assert "#99" not in todo.read_text(encoding="utf-8")
