"""tests/test_ac_fix.py -- AC-FIX (W10): aceitacao ADVERSARIAL do `--fix`.

Este arquivo NAO foi escrito por quem implementou `tools/todo_fix.py`
(FIX-ENG) -- e o papel deliberado de QA independente: tentar quebrar o
motor, nao confirmar as suposicoes de quem o construiu. Nao editar
`tools/todo_fix.py` a partir daqui; defeito encontrado e REPORTADO (ver
relatorio da fatia), nunca consertado neste arquivo.

Foco: os cenarios em que um comando que ESCREVE costuma falhar --
round-trip byte-exato (CRLF misto, sem newline final), idempotencia,
escopo estrito (nada alem do prometido muda), heuristica de duplicata sob
ambiguidade (identica, 3+ ocorrencias, prefixo truncado nas DUAS direcoes),
tabela legada de 8 colunas + corpus sintetico em outra lingua (o produto e
agnostico a projeto e idioma por contrato), leitura ilegivel, prova
pos-escrita forcada a falhar, arquivo temporario orfao de uma execucao
anterior interrompida, e o caso perverso em que a PROPRIA correcao cria um
defeito novo (duplicata de ID que nao existia antes do fix).

As fixtures de corpus REAL (dois consumidores vivos) vem so de variavel de
ambiente (`TAB_PENDENCIAS_FIXTURE_A`/`_B`) -- NUNCA hardcoded aqui (guard
CI-1/`guard_no_real_fixtures.py`: repo publico). Os testes que dependem
delas skipam com mensagem clara quando a variavel nao esta configurada.
`--apply` roda SOMENTE contra COPIAS em `tmp_path`, nunca contra o arquivo
apontado pela env var -- o original e so lido (hash conferido antes/depois
onde aplicavel).
"""
import hashlib
import os
import subprocess
import sys

import pytest
import todo_fix as F
import todo_lib as L
from checks import chk_core
from conftest import git_init_isolado as _git_init_isolado

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS_DIR = os.path.join(REPO_ROOT, "tools")
FIX = os.path.join(TOOLS_DIR, "todo_fix.py")

_ENV = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}


def _git(cwd, *a):
    subprocess.run(["git", *a], cwd=cwd, env=_ENV, capture_output=True,
                    check=True)


def _run_cli(args, cwd):
    return subprocess.run([sys.executable, FIX, *args], cwd=cwd,
                          capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


def _repo_bytes(tmp_path, raw_bytes, filename="TODO.md"):
    """Como o `_repo` de test_todo_fix.py, mas grava BYTES crus (nao
    `str.encode("utf-8")` de um literal Python) -- necessario para os casos
    de CRLF misto/sem-newline-final, em que o terminador exato de CADA linha
    importa e nao pode passar por normalizacao nenhuma no caminho ate o
    disco."""
    _git_init_isolado(tmp_path)
    todo = tmp_path / filename
    todo.write_bytes(raw_bytes)
    _git(tmp_path, "add", filename)
    _git(tmp_path, "commit", "-qm", "tabela inicial")
    return tmp_path, todo


def _repo(tmp_path, todo_text, filename="TODO.md"):
    return _repo_bytes(tmp_path, todo_text.encode("utf-8"), filename)


HEADER_9 = (
    "| ID | Onda | Grupo | Descrição | Prioridade | Pré-requisito | "
    "Dificuldade | Status | Estado Auditado |\n"
    "| :- | :- | :- | :- | :- | :- | :- | :- | :- |\n"
)

HEADER_8 = (
    "| ID | Grupo | Descrição | Prioridade | Pré-requisito | Dificuldade | "
    "Status | Estado Auditado |\n"
    "| :- | :- | :- | :- | :- | :- | :- |\n"
)

# Corpus em INGLES -- o contrato e agnostico a idioma: so a palavra "status"
# no cabecalho e ancora fixa do vocabulario (D-1), o resto e livre.
HEADER_9_EN = (
    "| ID | Wave | Group | Description | Priority | Prerequisite | "
    "Difficulty | Status | Audited State |\n"
    "| :- | :- | :- | :- | :- | :- | :- | :- | :- |\n"
)

LINHA_PIPE_CRU = (
    "| P-01 | W1 | Core | Prova `nm x.a | grep -E gl` = 0 | Alta | — | "
    "Média | ⏳ Pendente | — |\n"
)


# =============================================================================
# 1. Round-trip byte-exato sob terminadores hostis
# =============================================================================

def test_crlf_misto_preserva_terminador_por_linha(tmp_path):
    """Cabecalho+separador em LF, uma linha de dado em CRLF (a que sera
    escapada) e outra linha de dado em LF puro -- terminador e por LINHA,
    nao um atributo global do arquivo. Se `_tentar_escapar_pipe_cru` (ou
    quem monta o texto novo) normalizar terminador para o resto do arquivo,
    este teste pega."""
    linha_crlf = LINHA_PIPE_CRU.rstrip("\n").encode("utf-8") + b"\r\n"
    linha_lf_intacta = (
        "| V-2 | W1 | Core | Outro item | Alta | — | Média | "
        "🔄 Em andamento | — |\n").encode("utf-8")
    raw = HEADER_9.encode("utf-8") + linha_crlf + linha_lf_intacta
    root, todo = _repo_bytes(tmp_path, raw)
    result = F.run_fix(str(root), apply_classes=["all"])
    assert result.rc == 2 and result.applied is True
    depois = todo.read_bytes()
    linhas = depois.split(b"\n")
    # a linha corrigida (indice 2, 0-based apos header+separador) continua
    # terminando em CRLF -- o "\r" sobrevive como sufixo do elemento anterior
    # ao split("\n"); testamos via split manual robusto a isso.
    partes = depois.split(b"\n")
    assert partes[2].endswith(b"\r"), (
        "a linha escapada perdeu o terminador CRLF original: "
        f"{partes[2]!r}")
    assert not partes[3].endswith(b"\r"), (
        "a linha LF vizinha ganhou CRLF por engano (contaminacao de "
        f"terminador entre linhas): {partes[3]!r}")
    assert b"\\|" in depois


def test_sem_newline_final_na_linha_corrigida_preserva_ausencia(tmp_path):
    """A linha com pipe cru E a ULTIMA do arquivo, sem newline final nenhum.
    O fix nao pode inventar um '\\n' que nao existia."""
    raw = (HEADER_9 + LINHA_PIPE_CRU).rstrip("\n").encode("utf-8")
    assert not raw.endswith(b"\n")
    root, todo = _repo_bytes(tmp_path, raw)
    result = F.run_fix(str(root), apply_classes=["escapar_pipe_cru"])
    assert result.rc == 2 and result.applied is True
    depois = todo.read_bytes()
    assert not depois.endswith(b"\n"), (
        "o fix ACRESCENTOU um newline final que nao existia no original: "
        f"ultimos bytes = {depois[-5:]!r}")
    assert b"\\|" in depois


def test_bom_mais_crlf_e_sem_newline_final_combinados(tmp_path):
    """Combinacao das tres hostilidades ao mesmo tempo: BOM na 1a linha,
    CRLF em toda a tabela, sem newline final na ultima linha."""
    corpo = (HEADER_9 + LINHA_PIPE_CRU).replace("\n", "\r\n")
    corpo = corpo[:-2]  # tira o \r\n final -- ultima linha sem terminador
    raw = ("﻿" + corpo).encode("utf-8")
    root, todo = _repo_bytes(tmp_path, raw)
    result = F.run_fix(str(root), apply_classes=["all"])
    assert result.rc == 2 and result.applied is True
    depois = todo.read_bytes()
    assert depois.startswith("﻿".encode("utf-8"))
    assert not depois.endswith(b"\r\n") and not depois.endswith(b"\n"), (
        f"newline final foi introduzido: {depois[-6:]!r}")
    assert depois.count(b"\r\n") >= 1
    assert b"\\|" in depois


# =============================================================================
# 2. Idempotencia
# =============================================================================

def test_apply_all_duas_vezes_segunda_nao_acha_nada_e_arquivo_identico(tmp_path):
    root, todo = _repo(tmp_path, HEADER_9 + LINHA_PIPE_CRU + (
        "| V-9 | W1 | Core | Item | Alta | — | Média | ⏳ Pendente | — |\n"
        "| V-9 | W1 | Core | Item | Alta | — | Média | ⏳ Pendente | ✓ |\n"))
    r1 = F.run_fix(str(root), apply_classes=["all"])
    assert r1.rc == 2 and r1.applied is True
    depois_1a = todo.read_bytes()
    _git(root, "add", "TODO.md")
    _git(root, "commit", "-qm", "1a rodada de --fix")

    plan_2a = F.build_plan(str(root))
    assert plan_2a.items == [], (
        "a 2a rodada de build_plan ainda encontra item(ns) apos a 1a "
        f"aplicacao ter dito sucesso: {plan_2a.items}")

    r2 = F.run_fix(str(root), apply_classes=["all"])
    assert r2.rc == 0 and r2.applied is False, (
        "--fix NAO e idempotente: a 2a execucao ainda tem algo a aplicar "
        f"(rc={r2.rc}, applied={r2.applied})")
    depois_2a = todo.read_bytes()
    assert depois_2a == depois_1a, (
        "a 2a execucao (que nao deveria ter achado nada) MUDOU o arquivo")


def test_cli_apply_all_duas_vezes_via_subprocess(tmp_path):
    root, todo = _repo(tmp_path, HEADER_9 + LINHA_PIPE_CRU)
    r1 = _run_cli(["--apply", "all"], cwd=root)
    assert r1.returncode == 2, (r1.stdout, r1.stderr)
    _git(root, "add", "TODO.md")
    _git(root, "commit", "-qm", "1a rodada cli")
    conteudo_1a = todo.read_bytes()
    r2 = _run_cli(["--apply", "all"], cwd=root)
    assert r2.returncode == 0, (
        "CLI nao e idempotente -- 2a chamada ainda relata correcao "
        f"disponivel: rc={r2.returncode}\nstdout={r1.stdout}")
    assert todo.read_bytes() == conteudo_1a


# =============================================================================
# 3. Escopo estrito -- nada alem do prometido muda, ordem preservada
# =============================================================================

def test_escopo_estrito_todas_as_linhas_nao_tocadas_sobrevivem_byte_a_byte(tmp_path):
    texto = HEADER_9 + (
        "| V-1 | W1 | Core | Um | Alta | — | Média | ✅ Concluído | ✓ |\n"
        + LINHA_PIPE_CRU +
        "| V-2 | W2 | Auth | Dois | Média | V-1 | Baixa | 🔄 Em andamento | — |\n"
        "| V-3 | W2 | Auth | Três | Baixa | — | Alta | 💡 Decisão tomada | — |\n"
    )
    linhas_antes = texto.split("\n")
    root, todo = _repo(tmp_path, texto)
    F.run_fix(str(root), apply_classes=["escapar_pipe_cru"])
    linhas_depois = todo.read_text(encoding="utf-8").split("\n")
    # so a linha do P-01 (indice 3: 0=header,1=separador,2=V-1,3=P-01) pode
    # ter mudado; todas as outras, incluindo header/separador/V-1/V-2/V-3,
    # byte-identicas E na MESMA posicao (nenhuma reordenacao).
    assert len(linhas_depois) == len(linhas_antes)
    for i, (antes, depois) in enumerate(zip(linhas_antes, linhas_depois)):
        if i == 3:
            continue
        assert depois == antes, (
            f"linha {i} nao deveria ter mudado (fora do escopo do fix) mas "
            f"mudou:\n  antes:  {antes!r}\n  depois: {depois!r}")
    # e nenhum Status foi tocado (checagem adicional, direta na tabela)
    tbl_antes = L.parse_table(texto)
    tbl_depois = L.parse_table(todo.read_text(encoding="utf-8"))
    status_antes = {it["id"]: it["status"] for it in tbl_antes["items"]}
    status_depois = {it["id"]: it["status"] for it in tbl_depois["items"]
                     if it["id"] in status_antes}
    assert status_depois == status_antes, (
        "Status de item(ns) pre-existente(s) mudou -- --fix so deveria "
        "tocar escape de pipe/remocao de fragmento, nunca Status")


# =============================================================================
# 4. Heuristica de duplicata sob ambiguidade -- nao adivinhar
# =============================================================================

def test_duas_ocorrencias_identicas_em_tudo_nao_e_fixavel(tmp_path):
    """Duplicata "burra" (copy-paste exato, ATE o Status igual): nenhuma
    celula diverge -- a heuristica exige exatamente 1 divergente para
    apontar candidato. Zero divergentes tem que continuar ambiguo (== nao
    fixavel), nunca "escolher a primeira arbitrariamente"."""
    texto = HEADER_9 + (
        "| V-9 | W1 | Core | Item | Alta | — | Média | ⏳ Pendente | — |\n"
        "| V-9 | W1 | Core | Item | Alta | — | Média | ⏳ Pendente | — |\n")
    (tmp_path / "TODO.md").write_text(texto, encoding="utf-8")
    plan = F.build_plan(str(tmp_path))
    assert plan.items == [], (
        "duplicata 100% identica (0 celulas divergentes) foi tratada como "
        f"fixavel pelo motor de --fix: {plan.items}")


def test_tres_ocorrencias_do_mesmo_id_nao_e_fixavel(tmp_path):
    """3+ ocorrencias: a heuristica par-a-par explicitamente nao escala
    (`_candidato_fragmento` recusa quando `len(occs_cells) != 2`) -- prova
    de que o motor de --fix respeita essa recusa e nao aparece no plano."""
    texto = HEADER_9 + (
        "| V-9 | W1 | Core | Item | Alta | — | Média | ⏳ Pendente | — |\n"
        "| V-9 | W1 | Core | Item | Alta | — | Média | ⏳ Pendente | ✓ |\n"
        "| V-9 | W1 | Core | Item | Alta | — | Média | ⏳ Pendente | x |\n")
    (tmp_path / "TODO.md").write_text(texto, encoding="utf-8")
    plan = F.build_plan(str(tmp_path))
    assert plan.items == [], (
        "3 ocorrencias do mesmo ID foram tratadas como fixaveis: "
        f"{plan.items}")
    # nota adversarial: o --audit (CHK-01) AINDA acha e reporta este caso
    # (severidade CRITICO, "julgamento humano necessario") -- so o motor de
    # --fix o omite do proprio plano. Ver relatorio da fatia: assimetria
    # entre CHK-01 e CHK-02 na visibilidade de casos [nao fixaveis].
    tbl = L.parse_table(texto)
    import configparser
    import todo_audit as A
    ctx = A.Context(root=str(tmp_path), todo_path=str(tmp_path / "TODO.md"),
                    text=texto, table=tbl, profile="core",
                    config=configparser.ConfigParser())
    findings = chk_core._chk01_id_duplicado(ctx)
    assert len(findings) == 1 and findings[0].fixable is False


def test_prefixo_truncado_remove_a_ocorrencia_MAIS_CURTA_quando_e_a_primeira(tmp_path):
    texto = HEADER_9 + (
        "| V-9 | W1 | Core | Fazer X | Alta | — | Média | ⏳ Pendente | — |\n"
        "| V-9 | W1 | Core | Fazer X e revisar | Alta | — | Média | "
        "⏳ Pendente | — |\n")
    root, todo = _repo(tmp_path, texto)
    result = F.run_fix(str(root), apply_classes=["remover_fragmento_duplicado"])
    assert result.rc == 2 and result.applied is True
    novo = todo.read_text(encoding="utf-8")
    tbl = L.parse_table(novo)
    ids = [i["id"] for i in tbl["items"]]
    assert ids.count("V-9") == 1
    restante = tbl["items"][ids.index("V-9")]
    linha_restante = tbl["lines"][restante["line_no"]]
    assert "Fazer X e revisar" in linha_restante, (
        "removeu a ocorrencia ERRADA: deveria sobrar a versao completa "
        f"(mais longa), sobrou: {linha_restante!r}")


def test_prefixo_truncado_remove_a_ocorrencia_MAIS_CURTA_quando_e_a_segunda(tmp_path):
    """Mesma heuristica, direcao INVERSA: a ocorrencia completa vem
    PRIMEIRO no arquivo, a truncada vem DEPOIS -- prova de que
    `_candidato_fragmento` nao tem vies de posicao (so de conteudo)."""
    texto = HEADER_9 + (
        "| V-9 | W1 | Core | Fazer X e revisar | Alta | — | Média | "
        "⏳ Pendente | — |\n"
        "| V-9 | W1 | Core | Fazer X | Alta | — | Média | ⏳ Pendente | — |\n")
    root, todo = _repo(tmp_path, texto)
    result = F.run_fix(str(root), apply_classes=["remover_fragmento_duplicado"])
    assert result.rc == 2 and result.applied is True
    novo = todo.read_text(encoding="utf-8")
    tbl = L.parse_table(novo)
    ids = [i["id"] for i in tbl["items"]]
    assert ids.count("V-9") == 1
    restante = tbl["items"][ids.index("V-9")]
    linha_restante = tbl["lines"][restante["line_no"]]
    assert "Fazer X e revisar" in linha_restante, (
        "removeu a ocorrencia ERRADA (a truncada deveria sair, a completa "
        f"deveria ficar), sobrou: {linha_restante!r}")


def test_duas_celulas_divergentes_e_ambiguo_demais_para_fixar(tmp_path):
    """Wave E Descricao divergem ao mesmo tempo (nao so uma celula) --
    ambiguo demais para decidir sozinho, mesmo padrao do corpus real citado
    na docstring de `_candidato_fragmento`."""
    texto = HEADER_9 + (
        "| V-9 | W1 | Core | Item A | Alta | — | Média | ⏳ Pendente | — |\n"
        "| V-9 | W2 | Core | Item B | Alta | — | Média | ⏳ Pendente | — |\n")
    (tmp_path / "TODO.md").write_text(texto, encoding="utf-8")
    plan = F.build_plan(str(tmp_path))
    assert plan.items == [], (
        "duas celulas divergentes ao mesmo tempo foram tratadas como "
        f"fixaveis: {plan.items}")


# =============================================================================
# 5. Tabela legada de 8 colunas -- remover_fragmento_duplicado (nao so escape)
# =============================================================================

def test_tabela_legada_8_colunas_remove_fragmento_duplicado_corretamente(tmp_path):
    texto = HEADER_8 + (
        "| V-9 | Core | Item | Alta | — | Média | ⏳ Pendente | — |\n"
        "| V-9 | Core | Item | Alta | — | Média | ⏳ Pendente | ✓ |\n")
    root, todo = _repo(tmp_path, texto)
    result = F.run_fix(str(root), apply_classes=["remover_fragmento_duplicado"])
    assert result.rc == 2 and result.applied is True
    novo = todo.read_text(encoding="utf-8")
    tbl = L.parse_table(novo)
    assert tbl["ncols"] == 8
    assert tbl["duplicate_ids"] == {}
    assert novo.count("| ✓ |") == 1, (
        "manteve a ocorrencia errada (placeholder) em vez da com conteudo "
        "real, numa tabela de 8 colunas")


# =============================================================================
# 6. Corpus sintetico em OUTRA lingua -- agnostico a idioma por contrato
# =============================================================================

def test_corpus_em_ingles_escapa_pipe_cru_e_remove_fragmento(tmp_path):
    linha_pipe_en = (
        "| P-01 | W1 | Core | Proof `nm x.a | grep -E gl` = 0 | High | — | "
        "Medium | ⏳ Pendente | — |\n")
    texto = HEADER_9_EN + linha_pipe_en + (
        "| V-9 | W1 | Core | Item | High | — | Medium | ⏳ Pendente | — |\n"
        "| V-9 | W1 | Core | Item | High | — | Medium | ⏳ Pendente | ✓ |\n")
    root, todo = _repo(tmp_path, texto)
    result = F.run_fix(str(root), apply_classes=["all"])
    assert result.rc == 2 and result.applied is True
    novo = todo.read_text(encoding="utf-8")
    tbl = L.parse_table(novo)
    assert tbl["malformed"] == [] and tbl["duplicate_ids"] == {}
    ids = [i["id"] for i in tbl["items"]]
    assert ids.count("P-01") == 1 and ids.count("V-9") == 1
    assert "\\|" in novo


# =============================================================================
# 7. O caso perverso: a propria correcao CRIA um defeito novo
# =============================================================================

def test_caso_perverso_escapar_pipe_cru_cria_duplicata_de_id_nova(tmp_path):
    """ANTES do fix: a linha malformada (10 celulas, pipe cru) NAO entra em
    'items' (guarda de ncols) -- entao NAO ha duplicata detectada, mesmo
    com um ID 'P-01' ja existindo numa linha bem formada abaixo. O plano
    desta execucao so ve 1 item: 'escapar_pipe_cru' na linha malformada.

    DEPOIS do fix: a linha deixa de ser malformada e passa a fazer parte de
    'items' com o MESMO id 'P-01' -- uma duplicata de ID que NAO EXISTIA
    antes desta escrita. `_provar_invariantes` so confere CONTAGEM de itens
    (bate: 1 + delta 1 = 2) e round-trip do que nao foi tocado -- nao
    confere UNICIDADE de ID. O motor aplica e escreve mesmo assim.

    Isto e reportado como achado (nao consertado aqui, por instrucao
    explicita do team-lead): '--fix' pode consertar um defeito CRITICO
    (CHK-02) introduzindo silenciosamente outro defeito CRITICO (CHK-01)
    no mesmo golpe, sem avisar nesta mesma execucao."""
    texto = HEADER_9 + LINHA_PIPE_CRU + (
        "| P-01 | W1 | Core | Ja existe, bem formada | Alta | — | Média | "
        "✅ Concluído | — |\n")
    tbl_antes = L.parse_table(texto)
    assert tbl_antes["duplicate_ids"] == {}, (
        "pre-condicao do teste furou: ja havia duplicata ANTES do fix")
    assert [i["id"] for i in tbl_antes["items"]] == ["P-01"]

    root, todo = _repo(tmp_path, texto)
    plan = F.build_plan(str(root))
    assert len(plan.items) == 1 and plan.items[0].fix_ref == "escapar_pipe_cru"

    result = F.run_fix(str(root), apply_classes=["all"])
    assert result.rc == 2 and result.applied is True

    novo = todo.read_text(encoding="utf-8")
    tbl_depois = L.parse_table(novo)
    ids_depois = [i["id"] for i in tbl_depois["items"]]
    assert ids_depois.count("P-01") == 2, (
        "o achado esperado (fix cria duplicata nova) NAO se reproduziu -- "
        f"ids depois: {ids_depois}")
    assert "P-01" in tbl_depois["duplicate_ids"], (
        "confirmado: apos --apply all, existe uma NOVA duplicata de ID "
        "'P-01' que nao existia antes do fix, e o relatorio do --fix nao "
        "menciona isso nesta execucao (so o --audit da proxima rodada "
        "pegaria)")
    # e o relatorio desta execucao NAO alerta sobre a nova duplicata --
    # confirma o carater "silencioso" do achado.
    assert "duplicat" not in result.report_text.lower()


# =============================================================================
# 8. Leitura ilegivel -- encoding invalido
# =============================================================================

def test_todo_com_bytes_invalidos_utf8_falha_limpo_sem_escrever(tmp_path):
    _git_init_isolado(tmp_path)
    todo = tmp_path / "TODO.md"
    # 0xff nao e utf-8 valido em nenhuma posicao
    raw = (HEADER_9 + LINHA_PIPE_CRU).encode("utf-8") + b"\xff\xfe hex lixo"
    todo.write_bytes(raw)
    _git(tmp_path, "add", "TODO.md")
    _git(tmp_path, "commit", "-qm", "init")
    antes = todo.read_bytes()
    result = F.run_fix(str(tmp_path), apply_classes=["all"])
    assert result.rc == 1, (
        f"TODO.md ilegivel deveria dar rc=1, deu rc={result.rc}")
    assert result.applied is False
    assert todo.read_bytes() == antes
    assert result.report_text.strip() != ""


# =============================================================================
# 9. Prova pos-escrita forcada a falhar -- aborta ANTES de qualquer escrita
# =============================================================================

def test_invariantes_falham_por_bug_hipotetico_em_montar_novo_texto_aborta_limpo(
        tmp_path, monkeypatch):
    """Simula um bug FUTURO em `_montar_novo_texto` que produzisse
    invariantes incoerentes com o texto realmente montado (ex.: contagem
    de itens esperada errada). `_provar_invariantes` tem que RECUSAR --
    e nenhuma escrita em disco (nem arquivo temporario orfao) pode
    acontecer depois disso."""
    root, todo = _repo(tmp_path, HEADER_9 + LINHA_PIPE_CRU)
    antes = todo.read_bytes()

    original = F._montar_novo_texto

    def _montar_com_contagem_errada(table, selecionados):
        texto, invariantes = original(table, selecionados)
        invariantes = dict(invariantes)
        invariantes["n_items_esperado"] += 99  # deliberadamente incoerente
        return texto, invariantes

    monkeypatch.setattr(F, "_montar_novo_texto", _montar_com_contagem_errada)
    result = F.run_fix(str(root), apply_classes=["all"])
    assert result.rc == 1 and result.applied is False
    assert todo.read_bytes() == antes, (
        "TODO.md foi tocado mesmo com a prova de invariantes reprovando")
    sobras = [f for f in os.listdir(root)
              if "todo_fix" in f or f.endswith(".tmp")]
    assert sobras == [], f"arquivo temporario orfao apos falha de prova: {sobras}"


# =============================================================================
# 10. Arquivo temporario orfao PRE-EXISTENTE (crash de uma execucao anterior)
# =============================================================================

def test_tmp_orfao_preexistente_nao_atrapalha_e_nao_e_removido(tmp_path):
    """Um `.todo_fix.*.tmp` ja presente no diretorio (sobra de um crash
    anterior, nunca limpo) nao pode ser confundido com o arquivo desta
    execucao nem ser apagado por ela -- `tempfile.mkstemp` gera nome
    proprio, e a limpeza so mexe no `tmp_path` que ELA mesma criou."""
    root, todo = _repo(tmp_path, HEADER_9 + LINHA_PIPE_CRU)
    orfao = root / ".todo_fix.orfao-de-crash-anterior.tmp"
    orfao.write_text("lixo de uma execucao interrompida antes", encoding="utf-8")
    result = F.run_fix(str(root), apply_classes=["all"])
    assert result.rc == 2 and result.applied is True
    assert orfao.exists(), "o fix removeu um tmp orfao que NAO era dele"
    assert orfao.read_text(encoding="utf-8") == (
        "lixo de uma execucao interrompida antes")
    tmps_novos = [f for f in os.listdir(root)
                  if f.startswith(".todo_fix.") and f != orfao.name]
    assert tmps_novos == [], (
        f"sobrou tmp NOVO desta execucao sem limpar: {tmps_novos}")


# =============================================================================
# 11. Working tree: arquivo NUNCA commitado (untracked) tambem bloqueia apply
# =============================================================================

def test_todo_untracked_nunca_commitado_tambem_bloqueia_apply(tmp_path):
    """TODO.md existe mas nunca foi commitado (so `git init`, sem add nem
    commit) -- `git status --porcelain` marca como '??' (untracked), que
    `_working_tree_status` trata como sujo (nao ha prova de estado
    limpo). Confirma que a precondicao tambem cobre 'nunca versionado',
    nao so 'versionado e depois editado'."""
    _git_init_isolado(tmp_path)
    todo = tmp_path / "TODO.md"
    todo.write_text(HEADER_9 + LINHA_PIPE_CRU, encoding="utf-8")
    antes = todo.read_bytes()
    result = F.run_fix(str(tmp_path), apply_classes=["all"])
    assert result.rc == 1, (
        "TODO.md untracked (nunca commitado) deveria bloquear --apply "
        f"(rc=1), deu rc={result.rc}")
    assert result.applied is False
    assert todo.read_bytes() == antes


# =============================================================================
# 12. Fixture real (corpus dos dois consumidores vivos) -- AC-4
# =============================================================================

FIXTURE_A = os.environ.get("TAB_PENDENCIAS_FIXTURE_A")
FIXTURE_B = os.environ.get("TAB_PENDENCIAS_FIXTURE_B")


def _preparar_copia_isolada(env_path, tmp_path):
    """Le o arquivo apontado pela env var (SO LEITURA) e grava uma COPIA
    isolada em `tmp_path`, com o MESMO conteudo byte-a-byte (newline=""
    preserva CRLF/LF/BOM exatos). Retorna (root, todo_path, hash_original).
    O arquivo original NUNCA e aberto para escrita a partir daqui."""
    with open(env_path, "rb") as fh:
        raw = fh.read()
    hash_original = hashlib.sha256(raw).hexdigest()
    root = tmp_path
    _git_init_isolado(root)
    todo = root / "TODO.md"
    todo.write_bytes(raw)
    _git(root, "add", "TODO.md")
    _git(root, "commit", "-qm", "copia isolada do corpus real")
    return root, todo, hash_original


@pytest.mark.parametrize("env_path,rotulo", [
    (FIXTURE_A, "consumidor A"),
    (FIXTURE_B, "consumidor B"),
])
def test_ac4_apply_all_em_copia_do_corpus_real_fecha_defeitos_e_preserva_resto(
        env_path, rotulo, tmp_path):
    if not env_path or not os.path.isfile(env_path):
        pytest.skip(f"fixture nao configurada ({rotulo})")

    root, todo, hash_antes_copia = _preparar_copia_isolada(env_path, tmp_path)

    with open(env_path, "rb") as fh:
        hash_original_pre = hashlib.sha256(fh.read()).hexdigest()

    texto_antes = todo.read_text(encoding="utf-8", newline="")
    tbl_antes = L.parse_table(texto_antes)
    assert tbl_antes is not None

    plan_antes = F.build_plan(str(root))
    linhas_tocadas = {it.line_no for it in plan_antes.items if it.aplicavel}
    linhas_preservadas_esperadas = {
        i: l for i, l in enumerate(tbl_antes["lines"]) if i not in linhas_tocadas}
    n_itens_antes = len(tbl_antes["items"])
    delta_total = sum(it.delta_itens for it in plan_antes.items if it.aplicavel)

    result = F.run_fix(str(root), apply_classes=["all"])

    with open(env_path, "rb") as fh:
        hash_original_pos = hashlib.sha256(fh.read()).hexdigest()
    assert hash_original_pos == hash_original_pre == hash_antes_copia, (
        f"O ARQUIVO REAL ({rotulo}) foi tocado -- isto e uma falha "
        "GRAVISSIMA, --apply so deveria rodar contra a copia isolada")

    if not plan_antes.items or not any(it.aplicavel for it in plan_antes.items):
        pytest.skip(f"nenhum item aplicavel no corpus real ({rotulo}) -- "
                    "nada para o AC-4 exercitar nesta execucao")

    assert result.rc == 2 and result.applied is True, (
        f"--apply all nao aplicou nada no corpus real ({rotulo}) apesar de "
        f"{len(plan_antes.items)} item(ns) no plano: {result.report_text[:2000]}")

    texto_depois = todo.read_text(encoding="utf-8", newline="")
    tbl_depois = L.parse_table(texto_depois)
    assert tbl_depois is not None

    remocoes_ordenadas = sorted(
        it.line_no for it in plan_antes.items
        if it.aplicavel and it.fix_ref == "remover_fragmento_duplicado")
    divergencias = []
    for i_original, texto_original in linhas_preservadas_esperadas.items():
        deslocamento = sum(1 for r in remocoes_ordenadas if r < i_original)
        i_novo = i_original - deslocamento
        if (i_novo >= len(tbl_depois["lines"])
                or tbl_depois["lines"][i_novo] != texto_original):
            divergencias.append((i_original, i_novo))
    assert divergencias == [], (
        f"round-trip quebrado ({rotulo}): {len(divergencias)} linha(s) "
        f"nao tocada(s) pelo fix divergiram no resultado -- primeiras: "
        f"{divergencias[:5]}")

    assert len(tbl_depois["items"]) == n_itens_antes + delta_total, (
        f"contagem de itens ({rotulo}) diverge do esperado apos --apply all: "
        f"antes={n_itens_antes} delta={delta_total} "
        f"depois={len(tbl_depois['items'])}")

    plan_depois = F.build_plan(str(root))
    itens_chk01_chk02_restantes = [
        it for it in plan_depois.items if it.check_id in ("CHK-01", "CHK-02")]
    assert itens_chk01_chk02_restantes == [], (
        f"apos --apply all, o --audit (via build_plan) AINDA encontra "
        f"achado(s) CHK-01/CHK-02 no corpus real ({rotulo}): "
        f"{itens_chk01_chk02_restantes}")


@pytest.mark.parametrize("env_path,rotulo", [
    (FIXTURE_A, "consumidor A"),
    (FIXTURE_B, "consumidor B"),
])
def test_ac4_idempotencia_no_corpus_real_apos_commit(env_path, rotulo, tmp_path):
    """Depois de aplicar e COMMITAR a correcao (working tree limpa de
    novo), uma 2a chamada de --fix no mesmo corpus real (copia) nao pode
    achar mais nada CHK-01/CHK-02 nem escrever de novo. Se achar, e o
    caso perverso (secao 7 acima) se manifestando de verdade num corpus
    real -- reportar, nao consertar."""
    if not env_path or not os.path.isfile(env_path):
        pytest.skip(f"fixture nao configurada ({rotulo})")
    root, todo, _ = _preparar_copia_isolada(env_path, tmp_path)
    plan_antes = F.build_plan(str(root))
    if not any(it.aplicavel for it in plan_antes.items):
        pytest.skip(f"nenhum item aplicavel no corpus real ({rotulo})")

    r1 = F.run_fix(str(root), apply_classes=["all"])
    assert r1.rc == 2 and r1.applied is True
    _git(root, "add", "TODO.md")
    _git(root, "commit", "-qm", "1a rodada de --fix no corpus real")

    plan_depois = F.build_plan(str(root))
    achados_novos = [it for it in plan_depois.items
                     if it.check_id in ("CHK-01", "CHK-02")]
    assert achados_novos == [], (
        f"NAO idempotente no corpus real ({rotulo}): apos aplicar e "
        f"commitar, uma 2a rodada de --fix acha {len(achados_novos)} "
        f"achado(s) novo(s) que nao existiam antes -- possivel "
        f"manifestacao real do caso perverso (fix cria defeito novo): "
        f"{achados_novos}")
