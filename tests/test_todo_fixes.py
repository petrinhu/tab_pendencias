"""Regressao dos achados da verificacao adversarial (qa-engineer + code-reviewer)."""
import os
import subprocess

import todo_lib as L
import todo_sync as S

TODO_9 = (
    "| ID | Onda | Grupo | Descrição | Prioridade | Pré-requisito | "
    "Dificuldade | Status | Estado Auditado |\n"
    "| :- | :- | :- | :- | :- | :- | :- | :- | :- |\n"
    "| V-01 | W1 | Core | Fund | Alta | — | Média | ✅ Concluído | ✓ |\n"
    "| V-12 | W2 | Auth | Login | Alta | V-01 | Média | ⏳ Pendente | — |\n"
)


# ---- C1: CRLF preservado (era CRITICO: corrompia arquivo Windows inteiro) ----

def test_set_status_cell_preserva_crlf():
    assert L.set_status_cell("| a | ⏳ Pendente |\r\n", 1, "X").endswith("|\r\n")
    assert L.set_status_cell("| a | ⏳ Pendente |\n", 1, "X").endswith("|\n")
    assert L.set_status_cell("| a | ⏳ Pendente |", 1, "X").endswith("|")


def test_roundtrip_crlf_preserva_eol_e_so_muda_alvo():
    txt = ("| ID | Status |\r\n| :- | :- |\r\n"
           "| V-1 | ⏳ Pendente |\r\n| V-2 | 🔄 Em andamento |\r\n")
    t = L.parse_table(txt)
    it = next(i for i in t["items"] if i["id"] == "V-1")
    t["lines"][it["line_no"]] = L.set_status_cell(
        t["lines"][it["line_no"]], t["status_idx"], "🔍 Pendente verificação")
    out = "\n".join(t["lines"])
    assert out.count("\r\n") == txt.count("\r\n")          # EOL preservado
    assert "🔍 Pendente verificação" in out
    assert "| V-2 | 🔄 Em andamento |\r" in out            # V-2 byte-intacto


# ---- M5: BOM tolerado ----

def test_parse_tolera_bom():
    t = L.parse_table("﻿| ID | Status |\n| :- | :- |\n| V-1 | ⏳ Pendente |\n")
    assert t is not None and t["items"][0]["id"] == "V-1"


# ---- I4: so a 1a tabela; 2o cabecalho nao vira item ----

def test_parse_so_primeira_tabela():
    txt = TODO_9 + "\n## Legenda\n\n| ID | Status | Nota |\n| :- | :- |\n| X | ✅ | n |\n"
    ids = [it["id"] for it in L.parse_table(txt)["items"]]
    assert ids == ["V-01", "V-12"] and "ID" not in ids and "X" not in ids


# ---- M6/I2: linha com nº de celulas != cabecalho e ignorada (nao corrompe) --

def test_parse_ignora_linha_malformada():
    ids = [it["id"] for it in L.parse_table(TODO_9 + "| Z-9 | so tres |\n")["items"]]
    assert "Z-9" not in ids


# ---- I3: sync NAO flipa 🎨/🟡/💡 (so ⏳/🔄) ----

def test_is_flip_eligible():
    assert L.is_flip_eligible("⏳ Pendente")
    assert L.is_flip_eligible("🔄 Em andamento")
    assert not L.is_flip_eligible("🎨 Pendente design")
    assert not L.is_flip_eligible("🔍 Pendente verificação")
    assert not L.is_flip_eligible("🟡 Parcial")
    assert not L.is_flip_eligible("💡 Decisão tomada")
    assert not L.is_flip_eligible("✅ Concluído")


# ----------------------- e2e (repo git temporario) ---------------------------

def _repo(tmp_path, status="⏳ Pendente", crlf=False):
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}

    def g(*a):
        subprocess.run(["git", *a], cwd=tmp_path, env=env,
                       capture_output=True, check=True)

    g("init", "-q")
    g("config", "core.autocrlf", "false")
    eol = "\r\n" if crlf else "\n"
    body = (
        f"| ID | Onda | Grupo | D | P | Pre | Dif | Status | EA |{eol}"
        f"| :- | :- | :- | :- | :- | :- | :- | :- | :- |{eol}"
        f"| V-12 | W2 | A | L | Alta | — | Média | {status} | — |{eol}")
    (tmp_path / "TODO.md").write_bytes(body.encode("utf-8"))
    g("add", "TODO.md")
    g("commit", "-qm", "tabela")
    base = subprocess.run(["git", "rev-list", "--max-parents=0", "HEAD"],
                          cwd=tmp_path, capture_output=True, text=True,
                          encoding="utf-8", errors="replace"
                          ).stdout.split()[0]
    (tmp_path / "a.py").write_text("x")
    g("add", "a.py")
    g("commit", "-qm", "feat: pronto V-12")
    # E2 (2026-07-27): a entrega ficou ANTES da 1a execucao do sync, que agora
    # semeia a base em HEAD em vez de varrer o historico -- estes e2e passam
    # --since <base> para exercitar de proposito a janela que contem a entrega.
    return tmp_path, g, tmp_path / "TODO.md", base


def test_apply_preserva_crlf_e2e(tmp_path):
    root, g, todo, base = _repo(tmp_path, crlf=True)
    antes = todo.read_bytes().count(b"\r\n")
    S.run(["--apply", "--since", base], root=str(root))
    depois = todo.read_bytes()
    assert depois.count(b"\r\n") == antes               # CRLF intacto
    assert "🔍 Pendente verificação".encode() in depois


def test_sync_nao_flipa_design_e2e(tmp_path):
    root, g, todo, base = _repo(tmp_path, status="🎨 Pendente design")
    # --since <base>: sem ele a janela ficaria vazia e o teste passaria por
    # motivo errado (nada a flipar), sem provar que 🎨 e poupado.
    rc, flip, _ = S.run(["--apply", "--since", base], root=str(root))
    assert flip == [] and "🎨 Pendente design" in todo.read_text(encoding="utf-8")


# ---- E1: pipe escapado (GFM '\|') nao e separador de celula ----
#
# Achado no consumidor A (2026-07-27): 6 linhas da tabela citavam comando de
# shell com pipe DENTRO de code span, escapado corretamente como '\|' pelo GFM
# (ex.: `nm libexemplo.a \| grep gl`). O split("|") cru contava celula demais,
# a guarda de ncols descartava a linha, e o item ficava INVISIVEL ao sync e ao
# health -- silenciosamente. O parser tem de conhecer o escape; e o
# set_status_cell tem de contar do MESMO jeito, senao escreveria o status na
# celula errada dessas linhas (trocaria "invisivel" por "corrompido").

TODO_PIPE = (
    "| ID | Onda | Grupo | Descrição | Prioridade | Pré-requisito | "
    "Dificuldade | Status | Estado Auditado |\n"
    "| :- | :- | :- | :- | :- | :- | :- | :- | :- |\n"
    "| P-01 | W1 | Core | Prova `nm x.a \\| grep -E ' [BbDd] gl'` = 0 | Alta | "
    "— | Média | ⏳ Pendente | — |\n"
    "| P-02 | W1 | Core | Guarda `w<=0\\|\\|h<=0` silenciosa | Alta | — | "
    "Média | 🔄 Em andamento | — |\n"
)


def test_parse_ve_linha_com_pipe_escapado():
    tbl = L.parse_table(TODO_PIPE)
    ids = [it["id"] for it in tbl["items"]]
    assert ids == ["P-01", "P-02"], ids


def test_parse_le_status_certo_com_pipe_escapado():
    m = L.parse_status_map(TODO_PIPE)
    assert m["P-01"] == "⏳ Pendente"
    assert m["P-02"] == "🔄 Em andamento"


def test_set_status_cell_com_pipe_escapado_nao_corrompe_descricao():
    tbl = L.parse_table(TODO_PIPE)
    it = next(i for i in tbl["items"] if i["id"] == "P-02")
    linha = tbl["lines"][it["line_no"]]
    nova = L.set_status_cell(linha, tbl["status_idx"], "🔍 Pendente verificação")
    # a descricao (com os dois pipes escapados) sai byte-identica
    assert "`w<=0\\|\\|h<=0`" in nova
    # e o status novo caiu na celula de Status, nao noutra
    cells = L._cells(nova)
    assert len(cells) == 9
    assert cells[tbl["status_idx"]] == "🔍 Pendente verificação"
    assert cells[3] == "Guarda `w<=0\\|\\|h<=0` silenciosa"
    assert cells[0] == "P-02" and cells[8] == "—"


def test_linha_genuinamente_malformada_segue_ignorada():
    # a guarda de seguranca nao pode ser afrouxada pelo conserto do escape
    ids = [it["id"] for it in
           L.parse_table(TODO_PIPE + "| Z-9 | so tres |\n")["items"]]
    assert "Z-9" not in ids
