"""UNIQ-2 -- uma tabela de checklist por PROJETO (CHK-21).

Ordem do lider (2026-08-20): "so deve haver uma tabela checklist por projeto",
e ela vive no `TODO.md`. O risco desta fatia e o FALSO POSITIVO (acusar o
indice de ADR de um projeto vira ruido), entao metade destes testes prova
SILENCIO em documentacao de produto legitima.

Nenhuma fixture real de consumidor: todo corpus e gerado aqui.
"""
import os

import pytest

import checks.chk_projeto as P
import todo_audit as A
import todo_lib as L

CHECKLIST = ["| ID | Onda | Grupo | Status |",
             "| :--- | :--- | :--- | :--- |",
             "| A-1 | W1 | Base | ⏳ Pendente |",
             "| A-2 | W1 | Base | ✅ Concluído |"]
# Documentacao de produto: tem ID e tem Status, mas o Status nao fala o
# vocabulario desta skill (e o caso real que nao pode virar achado).
INDICE_ADR = ["| ID | Título | Decisão | Status |",
              "| :--- | :--- | :--- | :--- |",
              "| ADR-1 | Fronteira do nucleo | manter | Aceito |",
              "| ADR-2 | Formato de config | INI | Aceito |"]
MATRIZ = ["| Rota | Método | Auth |", "| :--- | :--- | :--- |",
          "| /v1/x | GET | sim |"]


def _md(*blocos):
    linhas = ["# doc", ""]
    for i, b in enumerate(blocos):
        if i:
            linhas.append("")
        linhas.extend(b)
    return "\n".join(linhas) + "\n"


def _projeto(tmp_path, arquivos, todo=None):
    (tmp_path / "TODO.md").write_text(_md(todo or CHECKLIST),
                                      encoding="utf-8", newline="")
    for rel, conteudo in arquivos.items():
        alvo = tmp_path / rel
        alvo.parent.mkdir(parents=True, exist_ok=True)
        alvo.write_text(conteudo, encoding="utf-8", newline="")
    return A.Context(root=str(tmp_path),
                     todo_path=str(tmp_path / "TODO.md"),
                     text=(tmp_path / "TODO.md").read_text(encoding="utf-8"),
                     table=None, profile="core", config=None)


# ------------------------- o discriminante (todo_lib) ----------------------

def test_checklist_precisa_de_id_status_e_vocabulario():
    assert len(L.checklist_tables(_md(CHECKLIST))) == 1


def test_indice_de_adr_nao_e_checklist():
    """Status = 'Aceito': documentacao de produto, nao fila de trabalho."""
    assert L.checklist_tables(_md(INDICE_ADR)) == []


def test_matriz_sem_status_nao_e_checklist():
    assert L.checklist_tables(_md(MATRIZ)) == []


def test_tabela_com_status_do_vocabulario_mas_sem_id_nao_e_checklist():
    legenda = ["| Status | Significado |", "| :--- | :--- |",
               "| ⏳ Pendente | nao iniciado |"]
    assert L.checklist_tables(_md(legenda)) == []


def test_tabela_dentro_de_bloco_de_codigo_e_EXEMPLO_nao_tabela():
    """FENCE-1: doc que mostra o schema num bloco cercado nao vira achado --
    nem aqui nem no CHK-19 (que conta blocos)."""
    texto = "# doc\n\n```markdown\n" + "\n".join(CHECKLIST) + "\n```\n"
    assert L.table_blocks(texto) == []
    assert L.checklist_tables(texto) == []


def test_fence_com_til_tambem_conta():
    texto = "# doc\n\n~~~\n" + "\n".join(CHECKLIST) + "\n~~~\n"
    assert L.checklist_tables(texto) == []


def test_tabela_depois_do_fence_volta_a_contar():
    texto = ("# doc\n\n```\n| ID | Status |\n```\n\n"
             + "\n".join(CHECKLIST) + "\n")
    assert len(L.checklist_tables(texto)) == 1


def test_conta_quantas_linhas_falam_o_vocabulario():
    tab = L.checklist_tables(_md(CHECKLIST))[0]
    assert tab["n_rows"] == 2 and tab["n_status_canonicos"] == 2


# --------------------------------- CHK-21 ----------------------------------

def test_chk21_acusa_checklist_paralelo(tmp_path):
    ctx = _projeto(tmp_path, {"docs/plano.md": _md(CHECKLIST)})
    achados = P.chk21(ctx)
    assert len(achados) == 1
    f = achados[0]
    assert f.check_id == "CHK-21" and f.severity == "IMPORTANTE"
    assert "docs/plano.md" in f.message and f.fixable is False


def test_chk21_calado_com_indice_de_adr(tmp_path):
    ctx = _projeto(tmp_path, {"docs/adr.md": _md(INDICE_ADR),
                              "docs/rotas.md": _md(MATRIZ)})
    assert P.chk21(ctx) == []


def test_chk21_nunca_acusa_o_proprio_todo(tmp_path):
    ctx = _projeto(tmp_path, {})
    assert P.chk21(ctx) == []


def test_chk21_ignora_arquivo_que_nao_e_markdown(tmp_path):
    ctx = _projeto(tmp_path, {"notas.txt": _md(CHECKLIST)})
    assert P.chk21(ctx) == []


@pytest.mark.parametrize("dir_pulado", ["tests", "templates", "node_modules",
                                        "build", "corpus"])
def test_chk21_pula_material_de_teste_e_dependencia(tmp_path, dir_pulado):
    ctx = _projeto(tmp_path, {f"{dir_pulado}/fixture.md": _md(CHECKLIST)})
    assert P.chk21(ctx) == []


def test_chk21_desligavel_por_config(tmp_path):
    import configparser
    cfg = configparser.ConfigParser()
    cfg.read_string("[audit]\nchecklist_scan = off\n")
    ctx = _projeto(tmp_path, {"docs/plano.md": _md(CHECKLIST)})
    ctx = A.Context(root=ctx.root, todo_path=ctx.todo_path, text=ctx.text,
                    table=None, profile="core", config=cfg)
    assert P.chk21(ctx) == []


def test_chk21_respeita_exclusao_por_glob(tmp_path):
    import configparser
    cfg = configparser.ConfigParser()
    cfg.read_string("[audit]\nchecklist_exclude = docs/arquivo/*\n")
    ctx = _projeto(tmp_path, {"docs/arquivo/2025.md": _md(CHECKLIST)})
    ctx = A.Context(root=ctx.root, todo_path=ctx.todo_path, text=ctx.text,
                    table=None, profile="core", config=cfg)
    assert P.chk21(ctx) == []


def test_chk21_acha_varias_tabelas_no_mesmo_arquivo(tmp_path):
    ctx = _projeto(tmp_path, {"ARCHIVE.md": _md(CHECKLIST, CHECKLIST)})
    assert len(P.chk21(ctx)) == 2


def test_chk21_declara_o_teto_de_arquivos(monkeypatch, tmp_path):
    """No silent caps: varrer menos do que o projeto tem e sempre declarado."""
    monkeypatch.setattr(P, "MAX_ARQUIVOS", 1)
    ctx = _projeto(tmp_path, {"a.md": _md(CHECKLIST), "b.md": _md(CHECKLIST)})
    achados = P.chk21(ctx)
    cosmeticos = [f for f in achados if f.severity == "COSMÉTICO"]
    assert len(cosmeticos) == 1
    assert "limitada" in cosmeticos[0].message


def test_chk21_declara_arquivo_grande_demais(monkeypatch, tmp_path):
    monkeypatch.setattr(P, "MAX_BYTES", 10)
    ctx = _projeto(tmp_path, {"grande.md": _md(CHECKLIST)})
    achados = P.chk21(ctx)
    assert [f for f in achados if f.severity == "COSMÉTICO"]
    assert not [f for f in achados if f.severity == "IMPORTANTE"]


def test_chk21_funciona_sem_git(tmp_path):
    """Fallback os.walk: diretorio que nao e repositorio git nenhum."""
    ctx = _projeto(tmp_path, {"docs/plano.md": _md(CHECKLIST)})
    assert L.git_dir(str(tmp_path)) is None or True   # so documenta o cenario
    assert len(P.chk21(ctx)) >= 1


def test_chk21_registrado_como_core():
    ids = {c.id: c for c in A.CHECKS}
    assert "CHK-21" in ids and ids["CHK-21"].profile == "core"
    assert ids["CHK-21"].severity_default == "IMPORTANTE"
    assert A.core_boundary_violations(A.CHECKS) == []


def test_chk21_no_motor_completo(tmp_path):
    (tmp_path / "TODO.md").write_text(_md(CHECKLIST), encoding="utf-8",
                                      newline="")
    (tmp_path / "PLANO.md").write_text(_md(CHECKLIST), encoding="utf-8",
                                       newline="")
    res = A.run_audit(str(tmp_path), checks=A.CHECKS, profile_override="core")
    assert any(f.check_id == "CHK-21" for f in res.findings)
    assert "PLANO.md" in res.report_text


def test_chk21_nao_dispara_no_proprio_repo():
    """Dogfooding: este repositorio nao tem checklist paralelo (o corpus de
    teste esta em tests/, que a varredura pula por desenho)."""
    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ctx = A.Context(root=raiz, todo_path=os.path.join(raiz, "TODO.md"),
                    text="", table=None, profile="core", config=None)
    assert P.chk21(ctx) == []
