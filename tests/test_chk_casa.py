"""Suite do CHK-CASA (TODO.md, item W8): CHK-12/13/14 -- convencoes da
CASA (opt-in, `profile == "casa"`, ADR-0001 secao a), em
`tools/casa/chk_casa.py`.

Esta e a fatia que torna a fronteira nucleo-generico x convencoes-da-casa
REAL: ate aqui `tools/casa/` so continha uma funcao sintetica nunca
registrada em producao (`_only_for_boundary_test`). Por isso, alem dos
testes unitarios de cada check, esta suite prova as DUAS pontas da
fronteira: (1) sob o perfil "core" (default), CHK-12/13/14 nao aparecem em
NENHUM relatorio, mesmo quando a tabela contem os tres defeitos que eles
detectam; (2) sob o perfil "casa", os tres rodam e acusam.

  CHK-12 -- item TST-*/AUD-* agendado antes do que cobre (ordem inviolavel).
  CHK-13 -- INBOX: formato de linha e ID duplicando a tabela canonica.
  CHK-14 -- item de Wiki + doc para iniciante ausente na ultima onda.
"""
import configparser
import os

import todo_audit as A
import todo_lib as L
from casa import chk_casa as C

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _ctx(text, profile="casa", config=None):
    table = L.parse_table(text)
    return A.Context(root=".", todo_path=None, text=text, table=table,
                      profile=profile, config=config)


HEADER = ("| ID | Onda | Grupo | Descrição | Prioridade | Pré-requisito | "
          "Dificuldade | Status | Estado Auditado |")
SEP = "| :- | :- | :- | :- | :- | :- | :- | :- | :- |"


def _row(iid, onda, prereq, desc="d", status="⏳ Pendente"):
    return (f"| {iid} | {onda} | G | {desc} | Alta | {prereq} | Média | "
            f"{status} | — |")


def _table(rows, extra=""):
    return "\n".join([HEADER, SEP, *rows]) + "\n" + extra


# ============================================================================
# Registro no motor + fronteira core x casa
# ============================================================================

def test_chk12_13_14_registrados_como_casa():
    ids = {c.id: c for c in A.CHECKS}
    for cid in ("CHK-12", "CHK-13", "CHK-14"):
        assert cid in ids, f"{cid} nao esta registrado em todo_audit.CHECKS"
        assert ids[cid].profile == "casa"


def test_fronteira_continua_verde_com_checks_casa_reais():
    """A regra 'nenhum check core depende de tools/casa/' continua provada
    em CI mesmo agora que CHK-12/13/14 sao REAIS (nao mais so a funcao
    sintetica de `tools/casa/__init__.py`) -- o teste deixou de ser
    vacuamente verdadeiro: ha 3 checks 'casa' de verdade no registro, e a
    fronteira segue intacta porque eles moram fisicamente em tools/casa/."""
    assert A.core_boundary_violations(A.CHECKS) == []
    # e discriminante de verdade: um check FAKE "core" cujo run mora em
    # tools/casa/ ainda e pego (nao virou frouxo por acomodar os 3 reais).
    fake = A.Check(id="CHK-FAKE-CASA", title="violacao", profile="core",
                   severity_default="COSMÉTICO", run=C.chk12)
    assert A.core_boundary_violations([fake]) == ["CHK-FAKE-CASA"]


# Tabela sintetica que dispara os TRES achados simultaneamente: CHK-12
# (TST-1 cita AUD-CODE, que vem DEPOIS dele na ordem das linhas), CHK-13
# (INBOX cita um ID que ja existe na tabela) e CHK-14 (ultima onda sem
# nenhuma mencao a wiki/doc-iniciante).
_TABELA_COM_OS_TRES_DEFEITOS = _table(
    [
        _row("TST-1", "W2", "AUD-CODE", desc="testa o modulo X"),
        _row("AUD-CODE", "W3", "—", desc="implementa o modulo X"),
        _row("Z-9", "W4", "—", desc="ultimo item, so mais um trabalho comum"),
    ],
    extra=(
        "\n## INBOX (descobertas não priorizadas)\n\n"
        "- Z-9: descoberta que colide com um ID ja existente na tabela\n"
    ),
)


def test_perfil_core_nao_produz_nenhum_achado_casa(tmp_path):
    """Sob o perfil default (core), rodar --audit contra uma tabela que
    contem os TRES defeitos nao deve produzir NENHUM achado CHK-12/13/14 --
    e o motor declara (no silent caps) quantos checks 'casa' foram
    pulados."""
    # run_audit precisa de um TODO.md em disco (usa L.find_todo); monta um
    # repo minimo aqui em vez de reusar _ctx (que so serve para chamar o
    # check isolado).
    (tmp_path / "TODO.md").write_text(_TABELA_COM_OS_TRES_DEFEITOS,
                                       encoding="utf-8")
    res = A.run_audit(str(tmp_path), checks=A.CHECKS, profile_override="core")
    casa_findings = [f for f in res.findings if f.check_id in
                     ("CHK-12", "CHK-13", "CHK-14")]
    assert casa_findings == []
    for cid in ("CHK-12", "CHK-13", "CHK-14"):
        assert any(cid in n and "core" in n for n in res.notices), (
            f"aviso 'no silent caps' de {cid} pulado nao apareceu: "
            f"{res.notices}")
    # e o relatorio textual tambem nao menciona os 3 checks fora da secao
    # de avisos (garante que nao vazou achado nenhum para o corpo visivel).
    corpo = res.report_text.split("Avisos do motor")[0]
    for cid in ("CHK-12", "CHK-13", "CHK-14"):
        assert cid not in corpo


def test_perfil_casa_produz_os_tres_achados(tmp_path):
    (tmp_path / "TODO.md").write_text(_TABELA_COM_OS_TRES_DEFEITOS,
                                       encoding="utf-8")
    (tmp_path / ".tab_pendencias.ini").write_text(
        "[profile]\nname = casa\n", encoding="utf-8")
    res = A.run_audit(str(tmp_path), checks=A.CHECKS)
    achados_por_check = {}
    for f in res.findings:
        achados_por_check.setdefault(f.check_id, []).append(f)
    assert "CHK-12" in achados_por_check
    assert "CHK-13" in achados_por_check
    assert "CHK-14" in achados_por_check


# ============================================================================
# CHK-12 -- ordem inviolavel de TST-*/AUD-*
# ============================================================================

def test_chk12_silencio_quando_ordem_correta():
    text = _table([
        _row("V-1", "W1", "—", desc="implementa"),
        _row("TST-1", "W2", "V-1", desc="testa V-1"),
        _row("AUD-1", "W3", "TST-1", desc="audita V-1 e TST-1"),
    ])
    assert C.chk12(_ctx(text)) == []


def test_chk12_acusa_ordem_invertida_como_critico():
    text = _table([
        _row("TST-1", "W1", "V-1", desc="testa V-1"),
        _row("V-1", "W2", "—", desc="implementa"),
    ])
    out = C.chk12(_ctx(text))
    assert len(out) == 1
    f = out[0]
    assert f.check_id == "CHK-12"
    assert f.severity == "CRÍTICO"
    assert "TST-1" in f.message and "V-1" in f.message
    assert f.line_no == 2  # 0-based: 3a linha do arquivo (a linha de TST-1)


def test_chk12_acusa_falta_de_prerequisito_como_importante():
    text = _table([_row("AUD-1", "W1", "—", desc="audita algo")])
    out = C.chk12(_ctx(text))
    assert len(out) == 1
    assert out[0].check_id == "CHK-12"
    assert out[0].severity == "IMPORTANTE"
    assert "AUD-1" in out[0].message
    assert "pré-requisito" in out[0].message.lower() or \
        "pre-requisito" in out[0].message.lower()


def test_chk12_ignora_item_sem_prefixo_tst_aud_mesmo_com_ordem_invertida():
    """A ordenacao generica (qualquer ID vs seu pre-requisito) e territorio
    do CHK-07 (core) -- CHK-12 so acusa quando o ID comeca com TST-/AUD-."""
    text = _table([
        _row("Z-1", "W1", "V-1", desc="nao e teste nem auditoria"),
        _row("V-1", "W2", "—", desc="implementa"),
    ])
    assert C.chk12(_ctx(text)) == []


def test_chk12_auto_referencia_conta_como_sem_prerequisito():
    text = _table([_row("TST-1", "W1", "TST-1", desc="cita a si mesma")])
    out = C.chk12(_ctx(text))
    assert len(out) == 1
    assert out[0].severity == "IMPORTANTE"


def test_chk12_sem_coluna_prerequisito_e_silencio(tmp_path):
    text = ("| ID | Descrição | Status |\n"
            "| :- | :- | :- |\n"
            "| TST-1 | testa algo | ⏳ Pendente |\n")
    assert C.chk12(_ctx(text)) == []


def test_chk12_sem_tabela_e_silencio():
    ctx = A.Context(root=".", todo_path=None, text=None, table=None,
                     profile="casa", config=None)
    assert C.chk12(ctx) == []


def test_chk12_lista_com_virgula_todos_ordenados_e_silencio():
    text = _table([
        _row("V-1", "W1", "—", desc="a"),
        _row("V-2", "W1", "—", desc="b"),
        _row("AUD-1", "W2", "V-1, V-2", desc="audita as duas"),
    ])
    assert C.chk12(_ctx(text)) == []


def test_chk12_registrado_no_motor_e_boundary_intacto():
    ids = {c.id: c for c in A.CHECKS}
    assert ids["CHK-12"].run is C.chk12


# ============================================================================
# CHK-13 -- INBOX (formato + ID duplicado)
# ============================================================================

_BASE_TABELA = _table([_row("V-1", "W1", "—", desc="algo")])


def test_chk13_silencio_sem_secao_inbox():
    assert C.chk13(_ctx(_BASE_TABELA)) == []


def test_chk13_silencio_com_inbox_bem_formada():
    text = _BASE_TABELA + (
        "\n## INBOX (descobertas não priorizadas)\n\n"
        "- —: uma descoberta nova, sem ID ainda\n"
        "- Z-9: outra descoberta, ID tentativo que nao existe na tabela\n"
    )
    assert C.chk13(_ctx(text)) == []


def test_chk13_acusa_falta_de_separador_dois_pontos():
    text = _BASE_TABELA + (
        "\n## INBOX (descobertas não priorizadas)\n\n"
        "- uma linha sem separador nenhum\n"
    )
    out = C.chk13(_ctx(text))
    assert len(out) == 1
    assert out[0].check_id == "CHK-13"
    assert out[0].severity == "COSMÉTICO"
    assert out[0].fixable is False


def test_chk13_acusa_descricao_vazia_apos_dois_pontos():
    text = _BASE_TABELA + (
        "\n## INBOX (descobertas não priorizadas)\n\n"
        "- Z-9:   \n"
    )
    out = C.chk13(_ctx(text))
    assert len(out) == 1
    assert out[0].severity == "COSMÉTICO"
    assert "descrição vazia" in out[0].message.lower() or \
        "descricao vazia" in out[0].message.lower()


def test_chk13_acusa_id_duplicado_da_tabela_como_importante():
    text = _BASE_TABELA + (
        "\n## INBOX (descobertas não priorizadas)\n\n"
        "- V-1: essa descoberta reusa um ID que ja esta na tabela\n"
    )
    out = C.chk13(_ctx(text))
    assert len(out) == 1
    assert out[0].check_id == "CHK-13"
    assert out[0].severity == "IMPORTANTE"
    assert "V-1" in out[0].message


def test_chk13_placeholder_travessao_nunca_e_tratado_como_duplicata():
    text = _BASE_TABELA + (
        "\n## INBOX (descobertas não priorizadas)\n\n"
        "- —: descoberta sem ID tentativo\n"
        "- -: outra descoberta, hifen simples\n"
    )
    assert C.chk13(_ctx(text)) == []


def test_chk13_multiplas_linhas_so_acusa_as_defeituosas():
    text = _BASE_TABELA + (
        "\n## INBOX (descobertas não priorizadas)\n\n"
        "- —: linha valida\n"
        "- V-1: linha duplicada\n"
        "- sem separador\n"
    )
    out = C.chk13(_ctx(text))
    assert len(out) == 2
    kinds = {f.severity for f in out}
    assert kinds == {"IMPORTANTE", "COSMÉTICO"}


def test_chk13_sem_tabela_e_silencio():
    ctx = A.Context(root=".", todo_path=None, text=None, table=None,
                     profile="casa", config=None)
    assert C.chk13(ctx) == []


def test_chk13_registrado_no_motor():
    ids = {c.id: c for c in A.CHECKS}
    assert ids["CHK-13"].run is C.chk13


# ============================================================================
# CHK-14 -- item de Wiki + doc iniciante na ultima onda
# ============================================================================

def test_chk14_silencio_quando_ultima_onda_tem_item_de_wiki_pt():
    text = _table([
        _row("V-1", "W1", "—", desc="implementa algo"),
        _row("WIKI-1", "W2", "—", desc="Wiki do repositório e documentação "
             "para iniciante em computação"),
    ])
    assert C.chk14(_ctx(text)) == []


def test_chk14_silencio_reconhece_padrao_em_ingles():
    text = _table([
        _row("V-1", "W1", "—", desc="implementa algo"),
        _row("DOCS-1", "W2", "—", desc="Wiki page and a beginner getting "
             "started guide"),
    ])
    assert C.chk14(_ctx(text)) == []


def test_chk14_acusa_ausencia_como_cosmetico_com_sugestao():
    text = _table([
        _row("V-1", "W1", "—", desc="implementa algo"),
        _row("V-2", "W2", "—", desc="ultimo item, so mais um trabalho comum"),
    ])
    out = C.chk14(_ctx(text))
    assert len(out) == 1
    f = out[0]
    assert f.check_id == "CHK-14"
    assert f.severity == "COSMÉTICO"
    assert f.fixable is False
    assert "sugest" in f.message.lower()


def test_chk14_nunca_e_critico_mesmo_quando_ausente():
    text = _table([_row("V-1", "W1", "—", desc="unico item, sem wiki")])
    out = C.chk14(_ctx(text))
    assert all(f.severity != "CRÍTICO" for f in out)


def test_chk14_so_olha_para_a_ultima_onda_nao_qualquer_item():
    """Um item de wiki numa onda ANTERIOR (nao a ultima) nao conta -- a
    convencao exige que ele esteja na ULTIMA onda, pos-tag."""
    text = _table([
        _row("WIKI-1", "W1", "—", desc="Wiki do repositório e "
             "documentação para iniciante"),
        _row("V-1", "W2", "—", desc="ultimo item, so mais um trabalho comum"),
    ])
    out = C.chk14(_ctx(text))
    assert len(out) == 1
    assert out[0].check_id == "CHK-14"


def test_chk14_config_customizada_soma_ao_default_nao_substitui():
    text = _table([_row("V-1", "W1", "—", desc="Tutorial completo de uso")])
    cfg = configparser.ConfigParser()
    cfg.read_string("[audit.chk14]\npatterns = tutorial\n")
    # sem a config custom, "tutorial" sozinho nao dispara silencio (nao esta
    # no default) -- com ela, dispara.
    assert C.chk14(_ctx(text, config=None)) != []
    assert C.chk14(_ctx(text, config=cfg)) == []


def test_chk14_schema_legado_8_colunas_sem_onda_usa_ultimo_item():
    text = ("| ID | Grupo | Descrição | Prioridade | Pré-requisito | "
            "Dificuldade | Status | Estado Auditado |\n"
            "| :- | :- | :- | :- | :- | :- | :- | :- |\n"
            "| V-1 | G | implementa | Alta | — | Média | ⏳ Pendente | — |\n"
            "| WIKI-1 | G | Wiki e documentação para iniciante | Alta | "
            "— | Média | ⏳ Pendente | — |\n")
    assert C.chk14(_ctx(text)) == []


def test_chk14_sem_tabela_e_silencio():
    ctx = A.Context(root=".", todo_path=None, text=None, table=None,
                     profile="casa", config=None)
    assert C.chk14(ctx) == []


def test_chk14_registrado_no_motor():
    ids = {c.id: c for c in A.CHECKS}
    assert ids["CHK-14"].run is C.chk14


# ============================================================================
# Dogfooding real: --audit --profile casa contra o TODO.md deste repositorio
# ============================================================================

def test_dogfood_perfil_casa_no_proprio_repo_read_only():
    """Este repositorio segue as convencoes da casa (item WIKI-1 na ultima
    onda, INBOX presente, itens TST-T15/AUD-FINAL). Roda --profile casa e
    so documenta o que foi achado -- qualquer achado real e investigado no
    relatorio da fatia, nao silenciado aqui."""
    import hashlib
    todo_path = os.path.join(REPO_ROOT, "TODO.md")

    def _md5(p):
        with open(p, "rb") as fh:
            return hashlib.md5(fh.read()).hexdigest()

    antes = _md5(todo_path)
    res = A.run_audit(REPO_ROOT, checks=A.CHECKS, profile_override="casa")
    depois = _md5(todo_path)
    assert antes == depois  # --audit e sempre read-only, tambem sob "casa"
    casa_findings = [f for f in res.findings if f.check_id in
                     ("CHK-12", "CHK-13", "CHK-14")]
    # nao ha expectativa fixa de zero -- so que a execucao seja valida e
    # deterministica; achados reais sao relatados na mensagem final da
    # fatia (CHK-CASA), nao escondidos por uma asserção vazia aqui.
    assert isinstance(casa_findings, list)
