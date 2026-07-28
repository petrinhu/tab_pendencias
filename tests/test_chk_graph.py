"""CHK-GRAPH (W7, TODO.md): um walk no grafo de pre-requisitos.

  CHK-05 -- pre-requisito citando ID inexistente.
  CHK-06 -- ciclo de dependencia (ciclo INTEIRO reportado).
  CHK-07 -- Onda inconsistente com a dependencia: (a) mesma onda de um
            pre-requisito; (b) posicionado antes do proprio pre-requisito.

Ver `tools/checks/chk_graph.py` para o contrato completo (deteccao de
coluna por nome pt+en, politica de lista com virgula, travessao de Onda).
"""
import os

import pytest

import todo_audit as A
import todo_lib as L
from checks import chk_graph as G

CORPUS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "corpus")
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(name):
    with open(os.path.join(CORPUS_DIR, name), encoding="utf-8", newline="") as fh:
        return fh.read()


def _ctx(text):
    table = L.parse_table(text)
    return A.Context(root=".", todo_path=None, text=text, table=table,
                      profile="core", config=None)


HEADER = ("| ID | Onda | Grupo | Descrição | Prioridade | Pré-requisito | "
          "Dificuldade | Status | Estado Auditado |")
SEP = "| :- | :- | :- | :- | :- | :- | :- | :- | :- |"


def _row(iid, onda, prereq, status="⏳ Pendente"):
    return (f"| {iid} | {onda} | G | d | Alta | {prereq} | Média | "
            f"{status} | — |")


def _table(rows):
    return "\n".join([HEADER, SEP, *rows]) + "\n"


# ============================================================================
# Registro no motor
# ============================================================================

def test_chk05_06_07_registrados_como_core():
    ids = {c.id: c for c in A.CHECKS}
    for cid in ("CHK-05", "CHK-06", "CHK-07"):
        assert cid in ids, f"{cid} nao esta registrado em todo_audit.CHECKS"
        assert ids[cid].profile == "core"
    assert A.core_boundary_violations(A.CHECKS) == []


# ============================================================================
# CHK-05 -- pre-requisito inexistente
# ============================================================================

def test_chk05_silencio_quando_todos_os_prereqs_existem():
    text = _table([_row("V-1", "W1", "—"), _row("V-2", "W1", "V-1")])
    assert G.chk05(_ctx(text)) == []


def test_chk05_acusa_id_inexistente():
    text = _table([_row("V-1", "W1", "V-99")])
    out = G.chk05(_ctx(text))
    assert len(out) == 1
    assert out[0].check_id == "CHK-05"
    assert out[0].severity == "IMPORTANTE"
    assert "V-99" in out[0].message
    assert out[0].line_no == 2  # 0-based: 3a linha do arquivo


def test_chk05_lista_com_virgula_acusa_so_o_pedaco_inexistente():
    text = _table([
        _row("V-1", "W1", "—"),
        _row("V-2", "W1", "V-1, V-99"),
    ])
    out = G.chk05(_ctx(text))
    assert len(out) == 1
    assert "V-99" in out[0].message
    assert "V-1" not in out[0].message.replace("V-1, V-99", "")


def test_chk05_id_com_virgula_que_existe_nao_e_falso_positivo():
    """Politica 'ID inteiro vence': se a celula inteira bate com um ID
    conhecido (mesmo contendo virgula), NAO e tratada como lista de dois
    IDs separados."""
    text = _table([
        _row("OPS,1", "W1", "—"),
        _row("V-2", "W1", "OPS,1"),
    ])
    assert G.chk05(_ctx(text)) == []


def test_chk05_id_com_virgula_inexistente_e_reportado_por_pedaco():
    """Quando o texto INTEIRO da celula nao bate com nenhum ID conhecido,
    cai no fallback de divisao por virgula -- aqui os dois pedacos
    resultantes tambem nao existem, entao ambos sao reportados."""
    text = _table([_row("V-1", "W1", "GHOST,ALSO-GHOST")])
    out = G.chk05(_ctx(text))
    msgs = " ".join(f.message for f in out)
    assert "GHOST" in msgs and "ALSO-GHOST" in msgs
    assert len(out) == 2


def test_chk05_sem_coluna_prereq_nao_quebra():
    text = ("| ID | Status |\n| :- | :- |\n| V-1 | ⏳ Pendente |\n")
    assert G.chk05(_ctx(text)) == []


def test_chk05_tabela_ausente_devolve_lista_vazia():
    ctx = A.Context(root=".", todo_path=None, text=None, table=None,
                    profile="core", config=None)
    assert G.chk05(ctx) == []


def test_chk05_corpus_real_dois_invalidos():
    text = _read("defeito_prereq_inexistente.md")
    out = G.chk05(_ctx(text))
    assert len(out) == 2
    assert all(f.check_id == "CHK-05" for f in out)


def test_chk05_silencio_no_corpus_limpo():
    text = _read("clean.md")
    assert G.chk05(_ctx(text)) == []


# ============================================================================
# CHK-06 -- ciclo de dependencia
# ============================================================================

def test_chk06_silencio_sem_ciclo():
    text = _table([
        _row("V-1", "W1", "—"),
        _row("V-2", "W2", "V-1"),
        _row("V-3", "W3", "V-2"),
    ])
    assert G.chk06(_ctx(text)) == []


def test_chk06_acusa_ciclo_simples_com_caminho_inteiro():
    text = _table([
        _row("A", "W1", "C"),
        _row("B", "W1", "A"),
        _row("C", "W1", "B"),
    ])
    out = G.chk06(_ctx(text))
    assert len(out) == 1
    f = out[0]
    assert f.check_id == "CHK-06" and f.severity == "CRÍTICO"
    assert "A" in f.message and "B" in f.message and "C" in f.message
    assert "→" in f.message
    # o ciclo relatado fecha no proprio no de partida
    assert f.message.strip().endswith("A") or f.message.count("A") >= 2


def test_chk06_autoreferencia_e_ciclo_de_tamanho_1():
    text = _table([_row("V-1", "W1", "V-1")])
    out = G.chk06(_ctx(text))
    assert len(out) == 1
    assert "V-1" in out[0].message


def test_chk06_detecta_dois_ciclos_independentes_nao_so_o_primeiro():
    text = _read("defeito_ciclo_dependencia.md")
    out = G.chk06(_ctx(text))
    assert len(out) == 2, [f.message for f in out]
    juntos = " | ".join(f.message for f in out)
    assert all(n in juntos for n in ("A-1", "A-2", "A-3"))
    assert all(n in juntos for n in ("B-1", "B-2"))
    assert "C-1" not in juntos


def test_chk06_ignora_referencia_inexistente_ao_montar_grafo():
    """Uma referencia que nao existe (CHK-05 territory) nunca vira aresta
    do grafo de ciclo -- nao pode gerar falso ciclo nem quebrar o walk."""
    text = _table([_row("V-1", "W1", "GHOST")])
    assert G.chk06(_ctx(text)) == []


def test_chk06_orcamento_de_passos_declara_interrupcao_no_silent_caps():
    """Prova sintetica do guard: com o orcamento setado a 0 (via chamada
    direta de _find_all_cycles, nao do motor), a interrupcao e sempre
    declarada -- nunca silenciosa."""
    graph = {"A": ["B"], "B": ["A"]}
    order = ["A", "B"]
    cycles, estourado = G._find_all_cycles(graph, order, step_budget=0)
    assert estourado is True


def test_chk06_silencio_no_corpus_limpo():
    text = _read("clean.md")
    assert G.chk06(_ctx(text)) == []


# ============================================================================
# CHK-07 -- Onda inconsistente
# ============================================================================

def test_chk07_silencio_quando_ondas_diferentes_e_ordem_correta():
    text = _table([
        _row("V-1", "W1", "—"),
        _row("V-2", "W2", "V-1"),
    ])
    assert G.chk07(_ctx(text)) == []


def test_chk07_caso_a_mesma_onda_do_prerequisito():
    text = _table([
        _row("V-1", "W1", "—"),
        _row("V-2", "W1", "V-1"),
    ])
    out = G.chk07(_ctx(text))
    assert len(out) == 1
    assert "mesma onda" in out[0].message.lower() or "W1" in out[0].message
    assert out[0].severity == "IMPORTANTE"


def test_chk07_caso_b_ordem_antes_do_prerequisito():
    text = _table([
        _row("V-1", "W3", "V-2"),   # V-1 cita V-2, mas V-2 vem DEPOIS
        _row("V-2", "W2", "—"),
    ])
    out = G.chk07(_ctx(text))
    assert len(out) == 1
    assert "antes" in out[0].message.lower()


def test_chk07_travessao_de_onda_nao_dispara_caso_a():
    """Item concluido/fora do fluxo tem Onda == travessao -- nao deve ser
    comparado por igualdade de string com outro travessao."""
    text = _table([
        _row("V-1", "—", "—", status="✅ Concluído"),
        _row("V-2", "—", "V-1", status="✅ Concluído"),
    ])
    assert G.chk07(_ctx(text)) == []


def test_chk07_autoreferencia_nao_duplica_achado_do_chk06():
    text = _table([_row("V-1", "W1", "V-1")])
    assert G.chk07(_ctx(text)) == []


def test_chk07_sem_coluna_onda_so_avalia_ordem():
    text = ("| ID | Grupo | Descrição | Prioridade | Pré-requisito | "
            "Dificuldade | Status | Estado Auditado |\n"
            "| :- | :- | :- | :- | :- | :- | :- | :- |\n"
            "| V-1 | G | d | Alta | V-2 | Média | ⏳ Pendente | — |\n"
            "| V-2 | G | d | Alta | — | Média | ⏳ Pendente | — |\n")
    out = G.chk07(_ctx(text))
    assert len(out) == 1
    assert "antes" in out[0].message.lower()


def test_chk07_corpus_real_dois_casos_isolados():
    text = _read("defeito_onda_inconsistente.md")
    out = G.chk07(_ctx(text))
    assert len(out) == 2
    kinds = [("antes" in f.message.lower()) for f in out]
    assert any(kinds) and not all(kinds)


def test_chk07_id_conhecido_reaparece_em_corpus_limpo_mesma_onda():
    """Achado real (nao sintetico): `clean.md` (CORP-0, controle negativo
    para OUTROS checks) tem #02 (Wave W1) dependendo de #01 (Wave W1) --
    exatamente o caso (a) do CHK-07. Nao e falso positivo: e uma
    inconsistencia latente que ja existia no corpus antes deste check
    nascer, agora visivel. Este teste documenta o achado; nao "concerta"
    o corpus (fora de escopo desta fatia -- pertence a CORP-0)."""
    text = _read("clean.md")
    out = G.chk07(_ctx(text))
    assert len(out) >= 1
    assert any("#02" in f.message for f in out)


# ============================================================================
# Motor: run_audit end-to-end com os 3 checks juntos
# ============================================================================

def test_run_audit_agrega_os_tres_checks_de_grafo(tmp_path):
    import subprocess

    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, env=env, check=True,
                    capture_output=True)
    hooks_vazio = tmp_path / ".git" / "hooks-vazio-teste"
    hooks_vazio.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "config", "core.hooksPath", str(hooks_vazio)],
                    cwd=tmp_path, env=env, check=True, capture_output=True)

    text = _table([
        _row("V-1", "W1", "V-99"),          # CHK-05
        _row("A", "W1", "C"), _row("B", "W1", "A"), _row("C", "W1", "B"),  # CHK-06
        _row("X-1", "W2", "—"), _row("X-2", "W2", "X-1"),  # CHK-07 caso a
    ])
    (tmp_path / "TODO.md").write_text(text, encoding="utf-8")
    subprocess.run(["git", "add", "TODO.md"], cwd=tmp_path, env=env,
                    check=True, capture_output=True)
    subprocess.run(["git", "commit", "-qm", "t"], cwd=tmp_path, env=env,
                    check=True, capture_output=True)

    res = A.run_audit(str(tmp_path))
    ids_achados = {f.check_id for f in res.findings}
    assert {"CHK-05", "CHK-06", "CHK-07"} <= ids_achados


# ============================================================================
# Deteccao de coluna por nome (pt + en), agnostica a schema
# ============================================================================

def test_deteccao_de_coluna_onda_e_prereq_em_ingles():
    text = _read("clean.md")
    table = L.parse_table(text)
    assert G._onda_idx(table) == 1
    assert G._prereq_idx(table) == 5


def test_deteccao_de_coluna_em_portugues():
    table = L.parse_table(_table([_row("V-1", "W1", "—")]))
    assert G._onda_idx(table) == 1
    assert G._prereq_idx(table) == 5


def test_ausencia_de_coluna_onda_devolve_none():
    text = _read("defeito_tabela_legada_8_colunas.md")
    table = L.parse_table(text)
    assert G._onda_idx(table) is None
    assert G._prereq_idx(table) is not None


# ============================================================================
# Dogfooding: fixtures reais + TODO.md deste proprio repo
# ============================================================================

def test_dogfood_proprio_repo_chk_graph():
    """Roda os 3 checks contra o TODO.md deste repo e conta os achados --
    read-only (so leitura, nenhuma escrita)."""
    todo_path = os.path.join(REPO_ROOT, "TODO.md")
    with open(todo_path, encoding="utf-8", newline="") as fh:
        text = fh.read()
    ctx = _ctx(text)
    achados = G.chk05(ctx) + G.chk06(ctx) + G.chk07(ctx)
    # nao afirma zero -- so que roda sem excecao e devolve uma lista de
    # Finding valida; a contagem real vai no relatorio final do agente.
    assert isinstance(achados, list)
    for f in achados:
        assert f.check_id in ("CHK-05", "CHK-06", "CHK-07")


@pytest.mark.parametrize("env_var", ["TAB_PENDENCIAS_FIXTURE_A",
                                      "TAB_PENDENCIAS_FIXTURE_B"])
def test_dogfood_fixture_real_chk_graph(env_var):
    path = os.environ.get(env_var)
    if not path or not os.path.isfile(path):
        pytest.skip(f"{env_var} nao configurada (fixture local, nunca "
                    "commitada)")
    with open(path, encoding="utf-8", newline="") as fh:
        text = fh.read()
    ctx = _ctx(text)
    achados = G.chk05(ctx) + G.chk06(ctx) + G.chk07(ctx)
    assert isinstance(achados, list)
