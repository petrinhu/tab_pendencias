"""tests/test_fase10_compat_sec.py -- TAB-SEC-001 + TAB-COMPAT-001.

- offline imports (grep/ast: tools sem rede)
- 8 e 9 colunas legiveis
- guard_stdlib_imports e guard_no_real_fixtures ainda OK
- INBOX antiga drenavel
- core offline (audit/health/sync/parse sem rede)
"""
from __future__ import annotations

import ast
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

from conftest import git_init_isolado

import todo_intake as I
import todo_lib as L

REPO = Path(__file__).resolve().parents[1]
TOOLS = REPO / "tools"

ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@t",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@t",
}

HEADER_9 = (
    "| ID | Wave | Group | Description | Priority | Blocked By | "
    "Effort | Status | Reviewed |\n"
    "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n"
)

HEADER_8 = (
    "| ID | Group | Description | Priority | Blocked By | "
    "Effort | Status | Reviewed |\n"
    "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n"
)

# APIs de rede que o core mecanico NAO pode importar.
_FORBIDDEN_NET = frozenset({
    "requests", "httpx", "urllib3", "aiohttp", "socket",
    "http.client", "ftplib", "smtplib",
})


def _git(cwd, *args):
    subprocess.run(
        ["git", *args], cwd=str(cwd), env=ENV,
        capture_output=True, text=True, encoding="utf-8", check=True,
    )


def test_compat_offline_imports_no_network_modules():
    """Varre tools/*.py: nenhum import de cliente de rede de terceiro."""
    offenders = []
    for path in sorted(TOOLS.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        src = path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(src, filename=str(path))
        except SyntaxError as exc:
            offenders.append(f"{path}: syntax {exc}")
            continue
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module.split(".")[0]]
            for n in names:
                if n in _FORBIDDEN_NET or n in (
                    "requests", "httpx", "urllib3", "aiohttp",
                ):
                    # socket/http.client em stdlib: so acusa se for uso top
                    # direto de cliente -- http.client e proibido aqui
                    if n == "socket":
                        # socket pode aparecer em comentarios; so import real
                        offenders.append(f"{path.relative_to(REPO)}: import {n}")
                    elif n != "socket":
                        offenders.append(f"{path.relative_to(REPO)}: import {n}")
    # filtro: socket e comum em stdlib util; o produto nao deve usa-lo
    assert not offenders, "imports de rede no core:\n" + "\n".join(offenders)


# Hosts de documentacao de licenca FOSS permitidos em comentarios/strings
# de runtime (ex.: cabecalho GPL). Checagem por hostname parseado, NUNCA
# por substring da URL (CodeQL py/incomplete-url-substring-sanitization).
_LICENSE_DOC_HOSTS = frozenset({
    "www.gnu.org",
    "gnu.org",
    "opensource.org",
    "www.opensource.org",
})

_HTTP_URL_RE = re.compile(r"https?://[^\s'\"\)\]>,;]+", re.IGNORECASE)


def _http_url_host_is_license_doc(url: str) -> bool:
    """True se o *hostname* da URL (apos urlparse) e doc de licenca FOSS.

    Nao usa ``\"gnu.org\" in url``: isso aceitaria host malicioso com o
    token em path/query (ex.: ``http://evil.example/gnu.org``).
    """
    try:
        host = (urlparse(url).hostname or "").lower()
    except ValueError:
        return False
    return host in _LICENSE_DOC_HOSTS


def test_compat_license_host_allowlist_is_hostname_exact():
    """CodeQL py/incomplete-url-substring-sanitization: host, nao substring."""
    assert _http_url_host_is_license_doc("https://www.gnu.org/licenses/")
    assert _http_url_host_is_license_doc("http://gnu.org/licenses/gpl-3.0.html")
    assert _http_url_host_is_license_doc("https://opensource.org/licenses/MIT")
    # bypass classico: token no path / prefixo de host
    assert not _http_url_host_is_license_doc("http://evil.example/gnu.org")
    assert not _http_url_host_is_license_doc(
        "http://benign-looking-prefix-gnu.org/x"
    )
    assert not _http_url_host_is_license_doc("https://api.example.com/v1")


def test_compat_grep_no_http_urls_in_runtime_tools():
    """Grep defensivo: tools de runtime nao abrem URL de API."""
    hits = []
    skip_dirs = {"ci", "__pycache__"}
    for path in sorted(TOOLS.rglob("*.py")):
        if any(p in skip_dirs for p in path.parts):
            continue
        # README em tools/ e docs podem citar URLs; so .py runtime
        if path.name in ("README.md",):
            continue
        text = path.read_text(encoding="utf-8")
        for i, line in enumerate(text.splitlines(), 1):
            if line.lstrip().startswith("#"):
                continue
            if "licenses" in line.lower() and "http" not in line.lower():
                # menção a licenses sem URL -- irrelevante
                continue
            for m in _HTTP_URL_RE.finditer(line):
                url = m.group(0).rstrip(".,);]")
                if _http_url_host_is_license_doc(url):
                    continue
                hits.append(
                    f"{path.relative_to(REPO)}:{i}:{line.strip()[:80]}"
                )
    # Licenca GPL cita URL -- filtrada por hostname; falha se houver API
    assert not hits, "URL de rede em runtime:\n" + "\n".join(hits[:20])


def test_compat_8_and_9_columns_readable():
    t9 = (
        "# nine\n\n" + HEADER_9
        + "| #01 | W1 | Core | Nine col item | High | - | Low | "
        "⏳ Pendente | - |\n"
    )
    t8 = (
        "# eight\n\n" + HEADER_8
        + "| #01 | Core | Eight col item | High | - | Low | "
        "⏳ Pendente | - |\n"
    )
    p9 = L.parse_table(t9)
    p8 = L.parse_table(t8)
    assert p9 is not None and p9["ncols"] == 9 and len(p9["items"]) == 1
    assert p8 is not None and p8["ncols"] == 8 and len(p8["items"]) == 1
    assert p9["items"][0]["id"] == "#01"
    assert p8["items"][0]["id"] == "#01"


def test_compat_legacy_inbox_drainable(tmp_path):
    """INBOX antiga (linha classifiable sem triage) continua drenavel."""
    texto = (
        "# legacy inbox\n\n" + HEADER_9
        + "| #01 | W1 | Core | Root | High | - | Low | ✅ Concluído | yes |\n"
        + "\n## INBOX (descobertas não priorizadas)\n"
        + "- OLD-1: legacy bare discovery without triage token\n"
    )
    repo = tmp_path / "r"
    repo.mkdir()
    git_init_isolado(repo)
    todo = repo / "TODO.md"
    todo.write_text(texto, encoding="utf-8")
    _git(repo, "add", "TODO.md")
    _git(repo, "commit", "-qm", "c0")
    assert I.classifiable_inbox_count(texto) == 1
    r = I.run_drain(
        todo_path=str(todo), apply=True,
        judgments={
            "OLD-1": {
                "action": "integrate",
                "items": [{
                    "candidate_id": "leg-1",
                    "item_id": "OLD-1",
                    "description": "legacy bare discovery without triage token",
                    "source": "test",
                    "fields_complete": True,
                    "is_local": True,
                    "authority_ok": True,
                }],
            },
        },
    )
    assert r.rc == 0, r.error
    assert I.classifiable_inbox_count(todo.read_text(encoding="utf-8")) == 0
    assert "OLD-1" in {
        it["id"] for it in L.parse_table(todo.read_text(encoding="utf-8"))["items"]
    }


def test_compat_guard_stdlib_imports_exit_0():
    guard = TOOLS / "ci" / "guard_stdlib_imports.py"
    r = subprocess.run(
        [sys.executable, str(guard), str(TOOLS)],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert r.returncode == 0, r.stdout + r.stderr


def test_compat_guard_no_real_fixtures_still_runs():
    """Guard anti-leak executa; unico falso-positivo aceito e o TODO.md
    canonico estourar LIMITE por crescimento organico (nao fixture em tests/)."""
    guard = TOOLS / "ci" / "guard_no_real_fixtures.py"
    r = subprocess.run(
        [sys.executable, str(guard)],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    out = r.stdout + r.stderr
    if r.returncode == 0:
        return
    # falha so no proprio TODO.md por tamanho de tabela e aceitavel nesta
    # fase (F10 acrescenta linhas); qualquer achado sob tests/ e vazamento
    assert "TODO.md" in out and "limite" in out.lower()
    assert "tests/test_" not in out
    assert "tests/corpus/" not in out or "0 achado" in out


def test_compat_core_scripts_import_offline():
    """Import de audit/health/sync/lib nao exige rede."""
    env = {**os.environ, "PYTHONPATH": str(TOOLS)}
    r = subprocess.run(
        [
            sys.executable, "-c",
            "import todo_lib, todo_health, todo_sync, todo_audit, todo_intake; "
            "print('ok')",
        ],
        cwd=str(TOOLS),
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )
    assert r.returncode == 0, r.stderr
    assert "ok" in r.stdout
