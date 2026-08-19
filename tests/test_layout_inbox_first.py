"""LAYOUT-1 -- ordem canonica do TODO.md: INBOX ANTES da tabela.

Cobre: leitura do formato novo E do legado (o legado continua VALIDO para
leitura, so emite aviso), escrita/criacao sempre no formato novo, e o
utilitario de migracao (`tools/todo_migrate_inbox.py`): idempotencia,
preservacao byte a byte do conteudo da tabela e da INBOX, `--check`,
arquivo sem INBOX, INBOX vazia, e INBOX com texto que PARECE tabela.

Nenhuma fixture real de consumidor e usada: o corpus grande deste arquivo e
GERADO em tempo de execucao (tambem para nao tropecar na CAMADA 1 do
`guard_no_real_fixtures`, que trata tabela grande VERSIONADA como
vazamento).
"""
import os
import subprocess
import sys

import pytest

import todo_lib as L
import todo_intake as I
import todo_migrate_inbox as M

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MIGRADOR = os.path.join(REPO_ROOT, "tools", "todo_migrate_inbox.py")

CAB = "| ID | Onda | Grupo | Status |"
SEP = "| :--- | :--- | :--- | :--- |"
TABELA = [CAB, SEP,
          "| A-1 | W1 | Base | ⏳ Pendente |",
          "| A-2 | W1 | Base | ✅ Concluído |",
          "| A-3 | W2 | Base | 🔍 Pendente verificação |"]
INBOX = ["## INBOX (descobertas não priorizadas)",
         "",
         "- —: [triage since=2026-08-19 reason=missing-info] descoberta X",
         "- B-9: [triage since=2026-08-18 reason=needs-leader-decision] Y"]
PREAMBULO = ["# TODO -- projeto de exemplo", "", "> Prosa de cabecalho.", ""]


def _novo(preambulo=PREAMBULO, inbox=INBOX, tabela=TABELA, extra_pos=None):
    """Arquivo na ordem canonica NOVA."""
    linhas = list(preambulo) + list(inbox) + [""] + list(tabela)
    return "\n".join(linhas) + "\n"


def _legado(preambulo=PREAMBULO, inbox=INBOX, tabela=TABELA, cauda=None):
    """Arquivo no formato LEGADO (INBOX depois da tabela)."""
    linhas = list(preambulo) + list(tabela) + [""] + list(inbox)
    if cauda:
        linhas += [""] + list(cauda)
    return "\n".join(linhas) + "\n"


# --------------------------------------------------------------------------
# leitura: novo E legado sao validos
# --------------------------------------------------------------------------

def test_leitura_formato_novo_parseia_tabela_e_inbox():
    text = _novo()
    tbl = L.parse_table(text)
    assert [it["id"] for it in tbl["items"]] == ["A-1", "A-2", "A-3"]
    assert len(L.inbox_items(text)) == 2


def test_leitura_formato_legado_continua_valida_e_identica():
    """O legado nao e recusado: entrega EXATAMENTE os mesmos itens e a
    mesma INBOX que o formato novo."""
    novo, legado = _novo(), _legado()
    t_novo, t_legado = L.parse_table(novo), L.parse_table(legado)
    assert ([(i["id"], i["status"]) for i in t_novo["items"]]
            == [(i["id"], i["status"]) for i in t_legado["items"]])
    assert L.inbox_items(novo) == L.inbox_items(legado)
    assert L.inbox_entries(novo) == L.inbox_entries(legado)


def test_layout_classifica_as_duas_ordens():
    assert L.layout(_novo())["order"] == L.LAYOUT_INBOX_FIRST
    assert L.layout(_novo())["canonical"] is True
    assert L.layout(_legado())["order"] == L.LAYOUT_INBOX_AFTER_TABLE
    assert L.layout(_legado())["legacy"] is True
    assert L.layout(_legado())["canonical"] is False


def test_legado_emite_AVISO_de_formato_e_o_novo_nao():
    aviso = L.legacy_layout_warning(_legado())
    assert aviso is not None and "LEGADO" in aviso
    assert L.legacy_layout_warning(_novo()) is None


def test_texto_depois_da_tabela_tambem_avisa_mesmo_com_inbox_no_lugar():
    """Nao basta a INBOX estar antes: a tabela tem de ser a ULTIMA coisa."""
    text = _novo()[:-1] + "\n\n## Notas\n\nprosa\n"
    lay = L.layout(text)
    assert lay["order"] == L.LAYOUT_INBOX_FIRST
    assert lay["canonical"] is False
    assert "DEPOIS do fim da tabela" in L.legacy_layout_warning(text)


def test_arquivo_sem_inbox_continua_funcionando():
    text = "\n".join(PREAMBULO + TABELA) + "\n"
    lay = L.layout(text)
    assert lay["order"] == L.LAYOUT_NO_INBOX
    assert lay["canonical"] is True
    assert L.legacy_layout_warning(text) is None
    assert M.plan(text)["needs_migration"] is False


def test_inbox_vazia_nao_quebra_nada():
    vazia = ["## INBOX (descobertas não priorizadas)", "",
             "<!-- 1 linha por descoberta -->", ""]
    novo = _novo(inbox=vazia)
    assert L.inbox_items(novo) == []
    assert L.layout(novo)["order"] == L.LAYOUT_INBOX_FIRST
    legado = _legado(inbox=vazia)
    assert L.layout(legado)["legacy"] is True
    migrado, mudou = M.migrate_text(legado)
    assert mudou and L.layout(migrado)["canonical"]
    assert L.inbox_items(migrado) == []


def test_inbox_com_conteudo_que_parece_tabela_nao_engole_a_canonica():
    """Uma linha com '|' dentro da secao INBOX encerra a regiao: a INBOX
    nunca pode absorver a tabela canonica que vem logo depois."""
    inbox = ["## INBOX (descobertas não priorizadas)",
             "",
             "- —: [triage since=2026-08-19 reason=missing-info] veja abaixo",
             "",
             "| exemplo | de tabela |",
             "| :--- | :--- |",
             "| solta | na prosa |",
             ""]
    text = "\n".join(PREAMBULO + inbox + TABELA) + "\n"
    heading, end = L.inbox_region(text)
    assert heading == len(PREAMBULO)
    # a regiao termina na 1a linha com '|', nao no fim do arquivo
    assert end == len(PREAMBULO) + 4
    assert L.inbox_items(text) == [
        "—: [triage since=2026-08-19 reason=missing-info] veja abaixo"]
    tbl = L.parse_table(text)
    assert [it["id"] for it in tbl["items"]] == ["A-1", "A-2", "A-3"]


def test_table_span_ignora_pipe_perdido_na_prosa_do_fim():
    text = _novo()[:-1] + "\n\nprosa\n\n| linha | solta |\n"
    span = L.table_span(L.parse_table(text))
    linhas = text.split("\n")
    assert linhas[span[1]].startswith("| A-3 ")


# --------------------------------------------------------------------------
# escrita: sempre no formato novo
# --------------------------------------------------------------------------

def _candidato():
    return I.WorkCandidate(
        candidate_id="c1", description="descoberta ambigua",
        item_id="Z-1", source="user")


def test_escrita_cria_secao_INBOX_ANTES_da_tabela():
    """Arquivo sem secao INBOX: o intake cria a secao ANTES da tabela."""
    text = "\n".join(PREAMBULO + TABELA) + "\n"
    novo = I._build_residual_text(text, _candidato(), I.ROUTE_NEEDS_TRIAGE)
    lay = L.layout(novo)
    assert lay["order"] == L.LAYOUT_INBOX_FIRST, novo
    assert lay["canonical"] is True, novo
    assert len(L.inbox_items(novo)) == 1
    # a tabela sobreviveu intacta
    assert [it["id"] for it in L.parse_table(novo)["items"]] == [
        "A-1", "A-2", "A-3"]


def test_escrita_em_arquivo_legado_usa_a_secao_existente_sem_mover_a_tabela():
    """Compat: num arquivo ainda legado o residual entra na secao que ja
    existe (nao inventa uma segunda INBOX)."""
    novo = I._build_residual_text(_legado(), _candidato(),
                                  I.ROUTE_NEEDS_TRIAGE)
    assert novo.count("## INBOX") == 1
    assert len(L.inbox_items(novo)) == 3


def test_escrita_nao_insere_bullet_dentro_da_tabela_quando_inbox_a_precede():
    """Regressao direta do risco do LAYOUT-1: com a INBOX imediatamente
    antes da tabela e SEM heading entre as duas, a regiao da INBOX nao pode
    se estender por cima da tabela."""
    text = "\n".join(PREAMBULO + INBOX + TABELA) + "\n"
    novo = I._build_residual_text(text, _candidato(), I.ROUTE_NEEDS_TRIAGE)
    linhas = novo.split("\n")
    span = L.table_span(L.parse_table(novo))
    for n in range(span[0], span[1] + 1):
        assert not linhas[n].strip().startswith("- "), (
            f"bullet residual foi parar DENTRO da tabela (linha {n + 1})")
    assert len(L.inbox_items(novo)) == 3


# --------------------------------------------------------------------------
# migracao
# --------------------------------------------------------------------------

def test_migracao_move_inbox_para_antes_da_tabela():
    legado = _legado()
    migrado, mudou = M.migrate_text(legado)
    assert mudou is True
    lay = L.layout(migrado)
    assert lay["order"] == L.LAYOUT_INBOX_FIRST
    assert lay["canonical"] is True
    assert lay["inbox_line"] < lay["table_span"][0]


def test_migracao_e_idempotente():
    um, mudou1 = M.migrate_text(_legado())
    dois, mudou2 = M.migrate_text(um)
    assert mudou1 is True and mudou2 is False
    assert dois == um


def test_migracao_preserva_a_tabela_e_a_inbox_byte_a_byte():
    legado = _legado()
    migrado, _ = M.migrate_text(legado)
    for linha in TABELA + [x for x in INBOX if x.strip()]:
        assert migrado.count(linha) == 1, f"linha alterada/perdida: {linha!r}"
    # nenhuma linha de conteudo criada nem destruida
    antes = sorted(x for x in legado.split("\n") if x.strip())
    depois = sorted(x for x in migrado.split("\n") if x.strip())
    assert antes == depois


def test_migracao_move_a_cauda_de_prosa_para_antes_da_tabela():
    """O contrato exige EOF logo apos a tabela: prosa que estava depois
    dela sobe, na mesma ordem relativa, sem perder uma linha."""
    cauda = ["## Notas de montagem", "", "prosa final."]
    legado = _legado(cauda=cauda)
    migrado, _ = M.migrate_text(legado)
    assert L.layout(migrado)["canonical"] is True
    for linha in cauda:
        if linha.strip():
            assert linha in migrado
    pos_cauda = migrado.index("## Notas de montagem")
    assert pos_cauda < migrado.index(CAB)


def test_migracao_preserva_CRLF():
    legado = _legado().replace("\n", "\r\n")
    migrado, mudou = M.migrate_text(legado)
    assert mudou is True
    assert "\r\n" in migrado
    assert "\n" not in migrado.replace("\r\n", "")
    assert L.layout(migrado)["canonical"] is True


def test_migracao_preserva_BOM_no_inicio():
    legado = L.BOM + _legado()
    migrado, _ = M.migrate_text(legado)
    assert migrado.startswith(L.BOM)
    assert migrado.count(L.BOM) == 1
    assert L.layout(migrado)["canonical"] is True


def test_migracao_sem_tabela_recusa_sem_tocar_nada():
    text = "# so prosa\n\n## INBOX (descobertas)\n\n- —: nada\n"
    assert M.plan(text)["order"] == L.LAYOUT_NO_TABLE
    with pytest.raises(M.MigrationError):
        M.migrate_text(text)


def test_migracao_nao_muda_arquivo_ja_canonico():
    novo = _novo()
    saida, mudou = M.migrate_text(novo)
    assert mudou is False and saida == novo


def test_migracao_nao_deixa_linha_em_branco_dupla_no_buraco():
    """MD012: recortar um bloco junta as brancas dos dois lados."""
    migrado, _ = M.migrate_text(_legado())
    assert "\n\n\n" not in migrado


# --------------------------------------------------------------------------
# round-trip real com corpus grande (gerado, nunca versionado)
# --------------------------------------------------------------------------

def _corpus_grande(n_itens=980):
    tabela = [CAB, SEP]
    for i in range(n_itens):
        tabela.append(
            f"| ITEM-{i:04d} | W{i % 12 + 1} | Grupo{i % 7} | "
            f"{'⏳ Pendente' if i % 3 else '✅ Concluído'} |")
    inbox = ["## INBOX (descobertas não priorizadas)", ""]
    for i in range(12):
        inbox.append(f"- N-{i}: [triage since=2026-08-1{i % 9} "
                     f"reason=missing-info] descoberta numero {i}")
    cauda = ["## Notas", "", "rodape com | pipe | solto na prosa.", "",
             "> ultima linha."]
    return tabela, inbox, cauda


def test_round_trip_corpus_grande_preserva_tudo_byte_a_byte():
    tabela, inbox, cauda = _corpus_grande()
    legado = ("\n".join(PREAMBULO + tabela + [""] + inbox + [""] + cauda)
              + "\n")
    assert len(legado.split("\n")) > 1000

    t_antes = L.parse_table(legado)
    inbox_antes = L.inbox_items(legado)
    migrado, mudou = M.migrate_text(legado)
    assert mudou is True

    # (1) ordem canonica
    assert L.layout(migrado)["canonical"] is True
    # (2) a TABELA saiu byte a byte igual, e contigua
    linhas = migrado.split("\n")
    span = L.table_span(L.parse_table(migrado))
    assert linhas[span[0]:span[1] + 1] == tabela
    # (3) a INBOX saiu byte a byte igual (sem a branca de fecho)
    heading, end = L.inbox_region(migrado)
    assert linhas[heading:heading + len(inbox)] == inbox
    # so a branca de costura separa a INBOX da tabela
    assert [x for x in linhas[heading:end] if x.strip()] == [
        x for x in inbox if x.strip()]
    # (4) itens e entradas identicos
    t_depois = L.parse_table(migrado)
    assert ([(i["id"], i["status"]) for i in t_antes["items"]]
            == [(i["id"], i["status"]) for i in t_depois["items"]])
    assert len(t_depois["items"]) == 980
    assert L.inbox_items(migrado) == inbox_antes
    # (5) multiset de linhas nao-brancas identico
    assert (sorted(x for x in legado.split("\n") if x.strip())
            == sorted(x for x in migrado.split("\n") if x.strip()))
    # (6) idempotente tambem no grande
    de_novo, mudou2 = M.migrate_text(migrado)
    assert mudou2 is False and de_novo == migrado


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def _run(*args, cwd=None):
    return subprocess.run([sys.executable, MIGRADOR, *args], cwd=cwd,
                          capture_output=True, text=True, encoding="utf-8")


def _escreve(path, text):
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)


def _le(path):
    with open(path, encoding="utf-8", newline="") as fh:
        return fh.read()


def test_cli_check_detecta_legado_com_exit_2(tmp_path):
    p = tmp_path / "TODO.md"
    _escreve(str(p), _legado())
    r = _run(str(p), "--check")
    assert r.returncode == 2, r.stdout + r.stderr
    assert "inbox-after-table" in r.stdout
    assert _le(str(p)) == _legado(), "dry-run/--check NAO pode escrever"


def test_cli_check_em_arquivo_canonico_sai_0(tmp_path):
    p = tmp_path / "TODO.md"
    _escreve(str(p), _novo())
    r = _run(str(p), "--check")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "ja esta na ordem canonica" in r.stdout


def test_cli_dry_run_e_o_default_e_nao_escreve(tmp_path):
    p = tmp_path / "TODO.md"
    _escreve(str(p), _legado())
    r = _run(str(p))
    assert r.returncode == 2
    assert _le(str(p)) == _legado()


def test_cli_apply_converte_e_e_idempotente_em_disco(tmp_path):
    p = tmp_path / "TODO.md"
    _escreve(str(p), _legado())
    r1 = _run(str(p), "--apply")
    assert r1.returncode == 0, r1.stdout + r1.stderr
    depois = _le(str(p))
    assert L.layout(depois)["canonical"] is True
    r2 = _run(str(p), "--apply")
    assert r2.returncode == 0
    assert _le(str(p)) == depois, "2a passada mudou bytes -- nao e idempotente"


def test_cli_flag_desconhecida_e_erro(tmp_path):
    p = tmp_path / "TODO.md"
    _escreve(str(p), _legado())
    r = _run(str(p), "--aply")
    assert r.returncode == 2 and "unrecognized" in (r.stderr or "").lower()


def test_cli_arquivo_inexistente_sai_1(tmp_path):
    r = _run(str(tmp_path / "nao-existe.md"))
    assert r.returncode == 1


def test_cli_arquivo_sem_tabela_sai_1(tmp_path):
    p = tmp_path / "TODO.md"
    _escreve(str(p), "# so prosa\n\ntexto.\n")
    r = _run(str(p))
    assert r.returncode == 1


# --------------------------------------------------------------------------
# todo_health: avisa o legado, sem falhar nem mudar contagem
# --------------------------------------------------------------------------

def _repo_com_todo(tmp_path, texto):
    from conftest import git_init_isolado, ENV_GIT_TESTE
    _escreve(str(tmp_path / "TODO.md"), texto)
    git_init_isolado(str(tmp_path))
    subprocess.run(["git", "add", "TODO.md"], cwd=str(tmp_path),
                   env=ENV_GIT_TESTE, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-qm", "fixture"], cwd=str(tmp_path),
                   env=ENV_GIT_TESTE, capture_output=True, check=True)
    return str(tmp_path)


def test_health_avisa_layout_legado_sem_mudar_contagem(tmp_path, capsys):
    import todo_health as H
    root = _repo_com_todo(tmp_path, _legado())
    res = H.run(root=root)
    saida = capsys.readouterr().out
    assert "LEGADO" in saida
    assert res["layout"] == L.LAYOUT_INBOX_AFTER_TABLE
    assert res["layout_legacy"] is True
    assert res["itens"] == 3


def test_health_nao_avisa_no_formato_canonico(tmp_path, capsys):
    import todo_health as H
    root = _repo_com_todo(tmp_path, _novo())
    res = H.run(root=root)
    saida = capsys.readouterr().out
    assert "LEGADO" not in saida
    assert res["layout"] == L.LAYOUT_INBOX_FIRST
    assert res["layout_legacy"] is False
    assert res["itens"] == 3
