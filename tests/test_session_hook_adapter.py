"""tests/test_session_hook_adapter.py -- adapter Claude-Code (TAB-HOOK-001..004).

Fail-open, exit 0, emite TRIAGE quando ha classifiable. Sem regra de negocio
propria (so wiring para session_signals).
"""
from __future__ import annotations

import datetime
import json
import os
import subprocess
import sys
import time

from conftest import git_init_isolado as _git_init_isolado

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS_DIR = os.path.join(REPO_ROOT, "tools")
HOOKS_DIR = os.path.join(TOOLS_DIR, "hooks")
if HOOKS_DIR not in sys.path:
    sys.path.insert(0, HOOKS_DIR)
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)

import tab_pendencias_reminder as hook  # noqa: E402
import session_signals as SS  # noqa: E402

NOW = datetime.date(2026, 8, 16)

_ENV = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}

_HEADER_9 = (
    "| ID | Onda | Grupo | Descrição | Prioridade | Pré-requisito | "
    "Dificuldade | Status | Estado Auditado |\n"
    "| :- | :- | :- | :- | :- | :- | :- | :- | :- |\n"
)


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, env=_ENV, capture_output=True,
                   check=True)


def _repo_with_classifiable(tmp_path):
    _git_init_isolado(tmp_path)
    texto = (
        _HEADER_9
        + "| H-1 | W1 | G | d | Média | — | Baixa | ⏳ Pendente | — |\n"
        + "\n## INBOX (descobertas não priorizadas)\n"
        + "- C-1: bare discovery\n"
    )
    (tmp_path / "TODO.md").write_text(texto, encoding="utf-8")
    _git(tmp_path, "add", "TODO.md")
    _git(tmp_path, "commit", "-qm", "todo")
    return tmp_path


def test_parse_hook_stdin_invalid_uses_getcwd():
    data = hook.parse_hook_stdin("not-json{{{")
    assert "cwd" in data
    assert os.path.isdir(data["cwd"])


def test_parse_hook_stdin_empty_uses_getcwd():
    data = hook.parse_hook_stdin("")
    assert os.path.isdir(data["cwd"])


def test_parse_hook_stdin_none_uses_getcwd():
    data = hook.parse_hook_stdin(None)
    assert os.path.isdir(data["cwd"])


def test_parse_hook_stdin_respects_cwd(tmp_path):
    payload = json.dumps({"cwd": str(tmp_path), "hook_event_name": "SessionStart"})
    data = hook.parse_hook_stdin(payload)
    assert data["cwd"] == str(tmp_path)


def test_run_hook_fail_open_continue_true():
    out = hook.run_hook("{not json")
    assert out.get("continue") is True


def test_run_hook_emits_triage(tmp_path):
    root = _repo_with_classifiable(tmp_path)
    payload = json.dumps({"cwd": str(root)})
    out = hook.run_hook(payload, now=NOW)
    assert out["continue"] is True
    ctx = out.get("additionalContext") or ""
    assert "TAB_TRIAGE_REQUIRED" in ctx


def test_run_hook_cli_exit_zero(tmp_path):
    root = _repo_with_classifiable(tmp_path)
    script = os.path.join(HOOKS_DIR, "tab_pendencias_reminder.py")
    r = subprocess.run(
        [sys.executable, script],
        cwd=str(root),
        input=json.dumps({"cwd": str(root)}),
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert r.returncode == 0
    data = json.loads(r.stdout.strip())
    assert data["continue"] is True
    assert "TAB_TRIAGE_REQUIRED" in (data.get("additionalContext") or "")


def test_adapter_has_no_business_predicates():
    """Adapter so faz wiring -- predicados de aging/sync nao moram nele."""
    path = os.path.join(HOOKS_DIR, "tab_pendencias_reminder.py")
    src = open(path, encoding="utf-8").read()
    for term in (
        "residual_is_aged",
        "triage_max_cycles",
        "FULL_REORDER",
        "run_intake",
        "wsjf",
        "openai",
    ):
        assert term not in src, term
    assert "collect_signals" in src


# ---------------------------------------------------------------------------
# TAB-HOOK-005 -- roteamento por hook_event_name + dedup por sessao
# ---------------------------------------------------------------------------

def _meta(since, reason, cycles=0):
    import todo_lib as L
    return L.format_triage_metadata(since=since, reason=reason, cycles=cycles)


def _repo_todos_os_sinais(tmp_path):
    """Repositorio que ativa 6 dos 7 sinais de uma vez.

    O setimo (`TAB_TODO_CREATE_REQUIRED`) e mutuamente exclusivo com os
    demais por construcao (exige AUSENCIA de TODO.md), entao tem teste
    proprio. Ativar tantos sinais juntos e o que torna o teste de
    disjuncao real -- com um sinal so, "nao emitiu nos dois" seria trivial.
    """
    import intake_journal as J

    _git_init_isolado(tmp_path)
    linhas = "".join(
        f"| V-{i} | W1 | G | d | Média | — | Baixa | 🔍 Pendente verificação | — |\n"
        for i in range(1, 6)
    )
    texto = (
        _HEADER_9
        + "| H-1 | W1 | G | d | Média | — | Baixa | ⏳ Pendente | — |\n"
        + linhas
        + "\n## INBOX (descobertas não priorizadas)\n"
        + "- C-1: bare discovery\n"
        + "- L-1: " + _meta("2026-08-01", "needs-leader-decision", cycles=0)
        + "aguarda decisao do lider\n"
    )
    (tmp_path / "TODO.md").write_text(texto, encoding="utf-8")
    _git(tmp_path, "add", "TODO.md")
    _git(tmp_path, "commit", "-qm", "todo")
    for i in range(6):  # defasagem de commits para TAB_STATUS_SYNC_RECOMMENDED
        (tmp_path / f"f{i}.txt").write_text("x", encoding="utf-8")
        _git(tmp_path, "add", f"f{i}.txt")
        _git(tmp_path, "commit", "-qm", f"c{i}")
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    (inbox / "sessao-a.md").write_text("- X-1: concorrente\n", encoding="utf-8")
    J.write_candidate(
        candidate_id="orphan-1", description="lost mid-intake",
        source="agent", cwd=str(tmp_path),
    )
    return tmp_path


def _emitir(root, evento, state_dir, session_id=None, now=NOW):
    payload = {"cwd": str(root)}
    if evento is not None:
        payload["hook_event_name"] = evento
    if session_id is not None:
        payload["session_id"] = session_id
    return hook.run_hook(json.dumps(payload), now=now, state_dir=str(state_dir))


# --- particao sinal -> evento ---------------------------------------------

def test_particao_por_evento_e_exaustiva_e_disjunta():
    """Todo SIGNAL_ID pertence a EXATAMENTE um evento.

    Exaustiva: nenhum sinal fica orfao (emitido em evento nenhum).
    Disjunta: nenhum sinal em dois eventos -- que e literalmente o defeito
    consertado aqui.
    """
    grupos = [set(v) for v in SS.SIGNALS_BY_EVENT.values()]
    uniao = set().union(*grupos)
    assert uniao == set(SS.SIGNAL_IDS), "sinal orfao ou desconhecido no mapa"
    total = sum(len(g) for g in grupos)
    assert total == len(uniao), "sinal declarado em mais de um evento"


def test_mapa_sinal_evento_e_o_decidido_pelo_lider():
    """Enumera o mapa INTEIRO -- espaco pequeno se enumera, nao se busca.

    A exaustividade/disjuncao acima aceita QUALQUER particao; este teste fixa
    a particao que foi decidida. `TAB_INTAKE_RECOVERY_REQUIRED` fica no
    `SessionStart` por decisao do lider em 19/08/2026 (alinhamento com a letra
    do plano de campanha; criterio de desempate = zero repeticao ao usuario,
    aceitando que um orfao nascido no meio da sessao so apareca na sessao
    seguinte). Mover qualquer sinal de evento tem de passar por aqui.
    """
    esperado = {
        SS.EVENT_SESSION_START: {
            "TAB_TODO_CREATE_REQUIRED",
            "TAB_STATUS_SYNC_RECOMMENDED",
            "TAB_TRIAGE_REQUIRED",
            "TAB_LEADER_DECISION_AGED",
            "TAB_VERIFICATION_AGING",
            "TAB_INTAKE_RECOVERY_REQUIRED",
        },
        SS.EVENT_USER_PROMPT_SUBMIT: {
            "TAB_CONCURRENT_INBOX_PRESENT",
        },
    }
    assert {k: set(v) for k, v in SS.SIGNALS_BY_EVENT.items()} == esperado


def test_signals_for_event_filtra_por_evento():
    rep = SS.SignalReport(
        signals=[SS.Signal(id=sid, active=True) for sid in SS.SIGNAL_IDS]
    )
    ss = {s.id for s in SS.signals_for_event(rep, SS.EVENT_SESSION_START).signals}
    ups = {s.id for s in
           SS.signals_for_event(rep, SS.EVENT_USER_PROMPT_SUBMIT).signals}
    assert ss == set(SS.SIGNALS_BY_EVENT[SS.EVENT_SESSION_START])
    assert ups == set(SS.SIGNALS_BY_EVENT[SS.EVENT_USER_PROMPT_SUBMIT])
    assert ss & ups == set()


def test_signals_for_event_nao_muta_o_relatorio_de_origem():
    rep = SS.SignalReport(
        signals=[SS.Signal(id=sid, active=True) for sid in SS.SIGNAL_IDS],
        metrics={"n_items": 3},
    )
    filtrado = SS.signals_for_event(rep, SS.EVENT_USER_PROMPT_SUBMIT)
    assert len(rep.signals) == len(SS.SIGNAL_IDS)
    filtrado.metrics["n_items"] = 99
    assert rep.metrics["n_items"] == 3


def test_normalize_event_ausente_ou_vazio_cai_no_default():
    assert SS.normalize_event(None) == SS.DEFAULT_EVENT
    assert SS.normalize_event("") == SS.DEFAULT_EVENT
    assert SS.normalize_event("   ") == SS.DEFAULT_EVENT
    assert SS.DEFAULT_EVENT == SS.EVENT_SESSION_START


def test_normalize_event_case_insensitive_e_com_espaco():
    assert SS.normalize_event(" sessionstart ") == SS.EVENT_SESSION_START
    assert SS.normalize_event("USERPROMPTSUBMIT") == SS.EVENT_USER_PROMPT_SUBMIT


def test_normalize_event_desconhecido_nao_vira_default():
    assert SS.normalize_event("PreToolUse") == "PreToolUse"
    assert "PreToolUse" not in SS.SIGNALS_BY_EVENT


# --- roteamento ponta a ponta pelo adapter ---------------------------------

def test_session_start_emite_so_os_sinais_de_estado_do_repo(tmp_path):
    root = _repo_todos_os_sinais(tmp_path)
    out = _emitir(root, "SessionStart", tmp_path / "st")
    ctx = out.get("additionalContext") or ""
    for sid in SS.SIGNALS_BY_EVENT[SS.EVENT_SESSION_START]:
        if sid == "TAB_TODO_CREATE_REQUIRED":
            continue  # exige ausencia de TODO.md
        assert sid in ctx, sid
    for sid in SS.SIGNALS_BY_EVENT[SS.EVENT_USER_PROMPT_SUBMIT]:
        assert sid not in ctx, sid


def test_user_prompt_submit_emite_so_os_sinais_reativos(tmp_path):
    root = _repo_todos_os_sinais(tmp_path)
    out = _emitir(root, "UserPromptSubmit", tmp_path / "st")
    ctx = out.get("additionalContext") or ""
    for sid in SS.SIGNALS_BY_EVENT[SS.EVENT_USER_PROMPT_SUBMIT]:
        assert sid in ctx, sid
    for sid in SS.SIGNALS_BY_EVENT[SS.EVENT_SESSION_START]:
        assert sid not in ctx, sid


def test_nenhum_sinal_sai_nos_dois_eventos(tmp_path):
    """O defeito original: saida identica nos dois eventos.

    Enumera a lista fechada de SIGNAL_IDS em vez de procurar duplicata --
    espaco pequeno se enumera inteiro.
    """
    root = _repo_todos_os_sinais(tmp_path)
    ctx_ss = _emitir(root, "SessionStart", tmp_path / "a").get(
        "additionalContext") or ""
    ctx_up = _emitir(root, "UserPromptSubmit", tmp_path / "b").get(
        "additionalContext") or ""
    nos_dois = [sid for sid in SS.SIGNAL_IDS
                if sid in ctx_ss and sid in ctx_up]
    assert nos_dois == [], nos_dois
    assert ctx_ss != ctx_up
    # e nenhum sinal ativo se perdeu no caminho: a uniao cobre os 6 ativos
    ativos = {s.id for s in SS.collect_signals(str(root), now=NOW).active()}
    emitidos = {sid for sid in SS.SIGNAL_IDS
                if sid in ctx_ss or sid in ctx_up}
    assert emitidos == ativos


def test_todo_create_required_so_no_session_start(tmp_path):
    """Sinal de repo git SEM TODO.md -- mutuamente exclusivo com os outros."""
    _git_init_isolado(tmp_path)
    (tmp_path / "a.txt").write_text("x", encoding="utf-8")
    _git(tmp_path, "add", "a.txt")
    _git(tmp_path, "commit", "-qm", "c")
    ctx_ss = _emitir(tmp_path, "SessionStart", tmp_path / "a").get(
        "additionalContext") or ""
    ctx_up = _emitir(tmp_path, "UserPromptSubmit", tmp_path / "b").get(
        "additionalContext") or ""
    assert "TAB_TODO_CREATE_REQUIRED" in ctx_ss
    assert "TAB_TODO_CREATE_REQUIRED" not in ctx_up
    assert ctx_up == ""


def test_recovery_sai_no_session_start_e_nunca_no_turno(tmp_path):
    """Decisao do lider (19/08/2026): orfao de intake e sinal de SessionStart.

    Ponta a ponta, com o fato real (journal com registro `state != DONE`), e
    nao so pelo mapa -- se o roteamento parar de honrar o mapa, o teste do
    mapa sozinho nao pegaria.
    """
    root = _repo_todos_os_sinais(tmp_path)
    ctx_ss = _emitir(root, "SessionStart", tmp_path / "a").get(
        "additionalContext") or ""
    ctx_up = _emitir(root, "UserPromptSubmit", tmp_path / "b").get(
        "additionalContext") or ""
    assert "TAB_INTAKE_RECOVERY_REQUIRED" in ctx_ss
    assert "orphans=1" in ctx_ss
    assert "TAB_INTAKE_RECOVERY_REQUIRED" not in ctx_up


def test_turno_carrega_so_o_sinal_de_inbox_concorrente(tmp_path):
    """Depois da mudanca, `UserPromptSubmit` tem UM sinal so.

    Enumera os sete IDs contra a saida do turno em vez de conferir apenas o
    que se espera encontrar: qualquer sinal que reapareca no evento por-turno
    reprova.
    """
    root = _repo_todos_os_sinais(tmp_path)
    ctx_up = _emitir(root, "UserPromptSubmit", tmp_path / "st").get(
        "additionalContext") or ""
    presentes = [sid for sid in SS.SIGNAL_IDS if sid in ctx_up]
    assert presentes == ["TAB_CONCURRENT_INBOX_PRESENT"], presentes


def test_hook_event_name_ausente_nao_duplica(tmp_path):
    """Campo ausente cai no lado que NAO repete (SessionStart)."""
    root = _repo_todos_os_sinais(tmp_path)
    ctx_sem = _emitir(root, None, tmp_path / "a").get("additionalContext") or ""
    ctx_ss = _emitir(root, "SessionStart", tmp_path / "b").get(
        "additionalContext") or ""
    assert ctx_sem == ctx_ss
    for sid in SS.SIGNALS_BY_EVENT[SS.EVENT_USER_PROMPT_SUBMIT]:
        assert sid not in ctx_sem, sid


def test_evento_desconhecido_nao_emite_nada(tmp_path):
    root = _repo_todos_os_sinais(tmp_path)
    out = _emitir(root, "PreToolUse", tmp_path / "st")
    assert out["continue"] is True
    assert "additionalContext" not in out


def test_payload_corrompido_nao_quebra_o_roteamento(tmp_path):
    for bruto in ("{not json", "", "[]", '{"cwd": 12}', "null",
                  '{"cwd": "/nao/existe", "hook_event_name": 7}',
                  '{"hook_event_name": null, "session_id": 5}'):
        out = hook.run_hook(bruto, now=NOW, state_dir=str(tmp_path / "st"))
        assert out.get("continue") is True, bruto
        assert isinstance(out, dict)


def test_cli_roteia_por_evento_e_sai_zero(tmp_path):
    """Prova pelo processo real, nao so pela funcao importada."""
    root = _repo_todos_os_sinais(tmp_path)
    script = os.path.join(HOOKS_DIR, "tab_pendencias_reminder.py")
    saidas = {}
    for evento in ("SessionStart", "UserPromptSubmit"):
        r = subprocess.run(
            [sys.executable, script], cwd=str(root),
            input=json.dumps({"cwd": str(root), "hook_event_name": evento}),
            capture_output=True, text=True, encoding="utf-8",
        )
        assert r.returncode == 0, evento
        saidas[evento] = json.loads(r.stdout.strip()).get(
            "additionalContext") or ""
    assert "TAB_CONCURRENT_INBOX_PRESENT" in saidas["UserPromptSubmit"]
    assert "TAB_CONCURRENT_INBOX_PRESENT" not in saidas["SessionStart"]
    assert "TAB_STATUS_SYNC_RECOMMENDED" in saidas["SessionStart"]
    assert "TAB_STATUS_SYNC_RECOMMENDED" not in saidas["UserPromptSubmit"]
    # decisao do lider 19/08/2026: recuperacao de intake e do SessionStart.
    assert "TAB_INTAKE_RECOVERY_REQUIRED" in saidas["SessionStart"]
    assert "TAB_INTAKE_RECOVERY_REQUIRED" not in saidas["UserPromptSubmit"]


# --- dedup por sessao ------------------------------------------------------

def test_dedup_suprime_repeticao_no_mesmo_turno_seguinte(tmp_path):
    root = _repo_todos_os_sinais(tmp_path)
    st = tmp_path / "st"
    a = _emitir(root, "UserPromptSubmit", st, session_id="s1")
    b = _emitir(root, "UserPromptSubmit", st, session_id="s1")
    assert "TAB_CONCURRENT_INBOX_PRESENT" in (a.get("additionalContext") or "")
    assert "additionalContext" not in b
    assert b["continue"] is True


def test_dedup_reemite_quando_o_fato_muda(tmp_path):
    root = _repo_todos_os_sinais(tmp_path)
    st = tmp_path / "st"
    _emitir(root, "UserPromptSubmit", st, session_id="s1")
    (root / "inbox" / "sessao-b.md").write_text("- X-2: nova\n",
                                               encoding="utf-8")
    out = _emitir(root, "UserPromptSubmit", st, session_id="s1")
    ctx = out.get("additionalContext") or ""
    assert "inbox_files=2" in ctx


def test_dedup_e_por_sessao_nao_global(tmp_path):
    root = _repo_todos_os_sinais(tmp_path)
    st = tmp_path / "st"
    _emitir(root, "UserPromptSubmit", st, session_id="s1")
    out = _emitir(root, "UserPromptSubmit", st, session_id="s2")
    assert "TAB_CONCURRENT_INBOX_PRESENT" in (out.get("additionalContext") or "")


def test_sem_session_id_nao_deduplica(tmp_path):
    root = _repo_todos_os_sinais(tmp_path)
    st = tmp_path / "st"
    a = _emitir(root, "UserPromptSubmit", st)
    b = _emitir(root, "UserPromptSubmit", st)
    assert (a.get("additionalContext") or "") == (b.get("additionalContext") or "")
    assert "TAB_CONCURRENT_INBOX_PRESENT" in (b.get("additionalContext") or "")


def test_session_start_nao_e_deduplicado(tmp_path):
    """Compact/resume redisparam SessionStart apos reset de contexto --
    suprimir ali apagaria a injecao quando ela mais importa."""
    root = _repo_todos_os_sinais(tmp_path)
    st = tmp_path / "st"
    a = _emitir(root, "SessionStart", st, session_id="s1")
    b = _emitir(root, "SessionStart", st, session_id="s1")
    assert (a.get("additionalContext") or "") == (b.get("additionalContext") or "")
    assert "TAB_STATUS_SYNC_RECOMMENDED" in (b.get("additionalContext") or "")


def test_session_state_path_neutraliza_session_id_hostil(tmp_path):
    """session_id vem do harness: nao pode virar travessia de caminho."""
    base = str(tmp_path / "st")
    for sid in ("../../etc/passwd", "a/b\\c", "nome com espaço", "x" * 500):
        p = hook.session_state_path(sid, state_dir=base)
        assert os.path.dirname(os.path.abspath(p)) == os.path.abspath(base)
        assert p.endswith(".json")
    assert hook.session_state_path(None, state_dir=base) is None
    assert hook.session_state_path("  ", state_dir=base) is None


def test_prune_state_dir_remove_estado_vencido(tmp_path):
    st = tmp_path / "st"
    st.mkdir()
    velho = st / "velho.json"
    novo = st / "novo.json"
    for p in (velho, novo):
        p.write_text('{"emitted": []}', encoding="utf-8", newline="\n")
    agora = time.time()
    os.utime(velho, (agora - 30 * 24 * 3600, agora - 30 * 24 * 3600))
    hook.prune_state_dir(state_dir=str(st), now_ts=agora)
    assert not velho.exists()
    assert novo.exists()


def test_prune_state_dir_respeita_teto_de_arquivos(tmp_path):
    st = tmp_path / "st"
    st.mkdir()
    agora = time.time()
    total = hook._STATE_MAX_FILES + 10
    for i in range(total):
        p = st / f"s{i:04d}.json"
        p.write_text('{"emitted": []}', encoding="utf-8", newline="\n")
        os.utime(p, (agora - (total - i), agora - (total - i)))
    hook.prune_state_dir(state_dir=str(st), now_ts=agora)
    restantes = [n for n in os.listdir(st) if n.endswith(".json")]
    assert len(restantes) == hook._STATE_MAX_FILES


def test_dedup_fail_open_com_estado_ilegivel(tmp_path):
    """Estado corrompido nao pode engolir sinal: emitir de novo e o lado
    seguro quando o disco mente."""
    root = _repo_todos_os_sinais(tmp_path)
    st = tmp_path / "st"
    st.mkdir()
    p = hook.session_state_path("s1", state_dir=str(st))
    with open(p, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("}{ lixo nao-json")
    out = _emitir(root, "UserPromptSubmit", st, session_id="s1")
    assert "TAB_CONCURRENT_INBOX_PRESENT" in (out.get("additionalContext") or "")


def test_adapter_continua_sem_predicado_de_negocio():
    """O roteamento nao pode ter trazido regra de frescor para o adapter."""
    path = os.path.join(HOOKS_DIR, "tab_pendencias_reminder.py")
    src = open(path, encoding="utf-8").read()
    for term in ("residual_is_aged", "triage_max_cycles", "FULL_REORDER",
                 "run_intake", "wsjf", "openai"):
        assert term not in src, term
    # o mapa sinal->evento tambem e regra: mora no motor, nao aqui.
    assert "SIGNALS_BY_EVENT = " not in src
    assert "SIGNALS_BY_EVENT: " not in src
    assert "signals_for_event" in src
