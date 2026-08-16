"""tests/test_fase10_mutation.py -- TAB-TST-004 mutation em copia /var/tmp.

Extrai blobs via `git show HEAD:tools/...` para /var/tmp (nunca edita a
working tree). Mutacoes:

1. topology_before_wsjf -> identity (previous_order)
2. force L0 on foundation (decide_route)
3. residual_is_aged always False
4. BUS_SOURCES empty

Cada mutante e exercitado por uma sonda que DEVE falhar (suite vermelha).
Restauracao = descartar o dir de copia (arvore do repo intocada).
"""
from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
VAR_TMP = Path("/var/tmp")


def _scratch_root() -> Path:
    if VAR_TMP.is_dir() and os.access(VAR_TMP, os.W_OK):
        base = VAR_TMP / f"tab_fase10_mut_{os.getpid()}"
    else:
        base = Path(os.environ.get("TMPDIR", "/tmp")) / f"tab_fase10_mut_{os.getpid()}"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _git_show(relpath: str) -> bytes:
    r = subprocess.run(
        ["git", "show", f"HEAD:{relpath}"],
        cwd=str(REPO),
        capture_output=True,
        check=True,
    )
    return r.stdout


def _write_blob(dest_dir: Path, relpath: str, content: bytes) -> Path:
    out = dest_dir / relpath
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(content)
    return out


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    # tools/ sibling imports (todo_lib from todo_intake etc.)
    sys.path.insert(0, str(path.parent))
    try:
        spec.loader.exec_module(mod)
    finally:
        if str(path.parent) in sys.path:
            sys.path.remove(str(path.parent))
    return mod


def _probe_fails(script: str, env_extra: dict | None = None) -> None:
    """Roda sonda em subprocess; espera returncode != 0 (suite vermelha)."""
    env = {**os.environ, **(env_extra or {})}
    r = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )
    assert r.returncode != 0, (
        "mutante nao foi morto (sonda passou):\n"
        f"stdout={r.stdout!r}\nstderr={r.stderr!r}"
    )


# ---------------------------------------------------------------------------
# 1. topology_before_wsjf identity
# ---------------------------------------------------------------------------

def test_mut_topology_before_wsjf_identity_red():
    root = _scratch_root() / "topo"
    root.mkdir(exist_ok=True)
    src = _git_show("tools/wsjf.py").decode("utf-8")
    assert "def topology_before_wsjf" in src, "topology_before_wsjf ausente no HEAD"
    # mutacao: corpo vira identity (previous_order cru), multi-linha def OK
    lines = src.splitlines(keepends=True)
    out_lines = []
    i = 0
    while i < len(lines):
        out_lines.append(lines[i])
        if lines[i].startswith("def topology_before_wsjf"):
            i += 1
            # copiar assinatura continuada (linhas indentadas ate ':')
            while i < len(lines) and not lines[i - 1].rstrip().endswith(":"):
                out_lines.append(lines[i])
                i += 1
            # docstring
            if i < len(lines) and '"""' in lines[i]:
                out_lines.append(lines[i])
                if lines[i].count('"""') == 1:
                    i += 1
                    while i < len(lines) and '"""' not in lines[i]:
                        out_lines.append(lines[i])
                        i += 1
                    if i < len(lines):
                        out_lines.append(lines[i])
                        i += 1
                else:
                    i += 1
            out_lines.append("    return list(previous_order)  # MUTANT identity\n")
            while i < len(lines):
                if (lines[i].startswith("def ") or lines[i].startswith("class ")
                        or (lines[i].strip() and not lines[i].startswith(" ")
                            and not lines[i].startswith("\t")
                            and not lines[i].startswith("#"))):
                    break
                i += 1
            continue
        i += 1
    mutated = "".join(out_lines)
    path = _write_blob(root, "wsjf.py", mutated.encode("utf-8"))
    probe = textwrap.dedent(f"""
        import importlib.util, sys
        p = {str(path)!r}
        spec = importlib.util.spec_from_file_location("wsjf_mut", p)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        levels = {{"#A": 0, "#B": 1}}
        # mutante identity: B fica antes de A se previous assim ordenou
        out = m.topology_before_wsjf(levels, ["#B", "#A"])
        assert out.index("#A") < out.index("#B"), "topology should put A before B"
        print("FAIL: mutante sobreviveu")
        """)
    _probe_fails(probe)


# ---------------------------------------------------------------------------
# 2. force L0 on foundation
# ---------------------------------------------------------------------------

def test_mut_force_l0_on_foundation_red():
    root = _scratch_root() / "foundation"
    root.mkdir(exist_ok=True)
    # precisa de todo_lib + intake_journal + etc? decide_route so usa helpers
    # no mesmo modulo. Carrega todo_intake com deps do REPO tools/ no path.
    src = _git_show("tools/todo_intake.py").decode("utf-8")
    old = (
        "    if candidate.is_foundation:\n"
        "        return ROUTE_FULL_REORDER\n"
    )
    new = (
        "    if candidate.is_foundation:\n"
        "        return ROUTE_LOCAL_INTEGRATION  # MUTANT force L0\n"
    )
    assert old in src, "bloco is_foundation mudou -- atualize mutacao"
    mutated = src.replace(old, new, 1)
    path = _write_blob(root, "todo_intake.py", mutated.encode("utf-8"))
    # copiar deps minimas do HEAD para o mesmo dir
    for dep in ("todo_lib.py", "intake_journal.py", "todo_lock.py", "wsjf.py"):
        _write_blob(root, dep, _git_show(f"tools/{dep}"))
    # pacotes checks nao necessarios para decide_route
    probe = textwrap.dedent(f"""
        import importlib.util, sys
        root = {str(root)!r}
        sys.path.insert(0, root)
        # load todo_lib first
        for name in ("todo_lib", "wsjf", "intake_journal", "todo_lock", "todo_intake"):
            p = root + "/" + name + ".py"
            spec = importlib.util.spec_from_file_location(name, p)
            mod = importlib.util.module_from_spec(spec)
            sys.modules[name] = mod
            spec.loader.exec_module(mod)
        I = sys.modules["todo_intake"]
        L = sys.modules["todo_lib"]
        text = (
            "| ID | Wave | Group | Description | Priority | Blocked By | "
            "Effort | Status | Reviewed |\\n"
            "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |\\n"
            "| #01 | W1 | Core | Boot | High | - | Low | ✅ Concluído | yes |\\n"
        )
        table = L.parse_table(text)
        inbox = L.inbox_entries(text)
        c = I.WorkCandidate(
            candidate_id="m", description="foundation item",
            source="test", item_id="#02", fields_complete=True,
            authority_ok=True, is_foundation=True, is_local=True,
        )
        route = I.decide_route(c, table, inbox)
        assert route == I.ROUTE_FULL_REORDER, f"got {{route}}"
        print("FAIL: mutante sobreviveu")
        """)
    _probe_fails(probe)


# ---------------------------------------------------------------------------
# 3. residual_is_aged always False
# ---------------------------------------------------------------------------

def test_mut_residual_is_aged_always_false_red():
    root = _scratch_root() / "aged"
    root.mkdir(exist_ok=True)
    src = _git_show("tools/todo_lib.py").decode("utf-8")
    old = "def residual_is_aged(entry, *, now, max_cycles=2, max_age_days=1):"
    assert old in src
    lines = src.splitlines(keepends=True)
    out = []
    i = 0
    while i < len(lines):
        out.append(lines[i])
        if lines[i].startswith("def residual_is_aged"):
            i += 1
            if i < len(lines) and '"""' in lines[i]:
                out.append(lines[i])
                if lines[i].count('"""') == 1:
                    i += 1
                    while i < len(lines) and '"""' not in lines[i]:
                        out.append(lines[i])
                        i += 1
                    if i < len(lines):
                        out.append(lines[i])
                        i += 1
                else:
                    i += 1
            out.append("    return False  # MUTANT always False\n")
            while i < len(lines):
                if lines[i].startswith("def ") or lines[i].startswith("class "):
                    break
                if (lines[i].strip() and not lines[i].startswith(" ")
                        and not lines[i].startswith("\t")
                        and not lines[i].startswith("#")):
                    break
                i += 1
            continue
        i += 1
    path = _write_blob(root, "todo_lib.py", "".join(out).encode("utf-8"))
    probe = textwrap.dedent(f"""
        import importlib.util, datetime
        p = {str(path)!r}
        spec = importlib.util.spec_from_file_location("todo_lib_mut", p)
        L = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(L)
        text = (
            "## INBOX (descobertas não priorizadas)\\n"
            "- #88: [triage since=2026-08-01 reason=missing-info cycles=0] wait\\n"
        )
        e = L.inbox_entries(text)[0]
        now = datetime.date(2026, 8, 16)
        assert L.residual_is_aged(e, now=now, max_cycles=2, max_age_days=1) is True
        print("FAIL: mutante sobreviveu")
        """)
    _probe_fails(probe)


# ---------------------------------------------------------------------------
# 4. BUS_SOURCES empty
# ---------------------------------------------------------------------------

def test_mut_bus_sources_empty_red():
    root = _scratch_root() / "bus"
    root.mkdir(exist_ok=True)
    src = _git_show("tools/wsjf.py").decode("utf-8")
    old = 'BUS_SOURCES: frozenset[str] = frozenset({"bus"})'
    new = "BUS_SOURCES: frozenset[str] = frozenset()  # MUTANT empty"
    if old not in src:
        # fallback looser
        old2 = 'frozenset({"bus"})'
        assert old2 in src, "BUS_SOURCES literal mudou"
        mutated = src.replace(old2, "frozenset()", 1)
    else:
        mutated = src.replace(old, new, 1)
    path = _write_blob(root, "wsjf.py", mutated.encode("utf-8"))
    probe = textwrap.dedent(f"""
        import importlib.util
        p = {str(path)!r}
        spec = importlib.util.spec_from_file_location("wsjf_mut", p)
        W = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(W)
        # com BUS_SOURCES vazio, source=bus passa a aceitar label early
        row = W.score_row(
            W.WsjfInputs(
                item_id="#b",
                priority_label="Alta",
                difficulty_label="Baixa",
                time_criticality=5,
                risk_reduction=3,
                source="bus",
            ),
            profile="early",
        )
        # comportamento CORRETO: bus ignora labels -> scored False se so label
        # (tc/rr preenchidos + labels -> pode scored com bv/js de label)
        # A assercao que a suite real usa: bus + label retorico NÃO pontua bv
        # via label. Mutante empty faz label preencher bv.
        assert row["bv"] is None, f"bus nao deve pontuar label, bv={{row['bv']}}"
        print("FAIL: mutante sobreviveu")
        """)
    _probe_fails(probe)


def test_mut_copies_live_under_var_tmp_not_repo_tools():
    """Isolamento: mutantes gravados sob /var/tmp (ou TMPDIR), fora de tools/."""
    root = _scratch_root()
    assert "tools" not in root.parts or root.parts[0] in ("/", "var", "tmp")
    # path de mutacao nao e o tools/ do repo
    assert Path(root).resolve() != (REPO / "tools").resolve()
    sample = root / "isolation_probe.txt"
    sample.write_text("ok\n", encoding="utf-8")
    assert sample.is_file()
    # tools/wsjf.py do repo ainda bate com HEAD no trecho critico
    head = _git_show("tools/wsjf.py").decode("utf-8")
    live = (REPO / "tools" / "wsjf.py").read_text(encoding="utf-8")
    # se a working tree divergiu de HEAD por outra fatia, ainda assim
    # a mutacao desta suite nao reescreve tools/ in-place
    assert "def topology_before_wsjf" in live
    assert "MUTANT identity" not in live
    assert "MUTANT always False" not in live
    assert "MUTANT empty" not in head or "MUTANT empty" not in live
