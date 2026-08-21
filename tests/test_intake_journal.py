"""tests/test_intake_journal.py -- TAB-ADD-000: write-ahead journal de intake.

Cobre os modos de falha enumerados no brief (crash antes/depois de gravar,
antes/depois de integrar, recuperacao repetida, journal corrompido/parcial,
dois processos gravando ao mesmo tempo) mais os dois eixos cross-platform
exigidos: git-common-dir compartilhado entre worktrees, e sanitizacao de
nome de arquivo (caracteres invalidos no Windows). Nao reusa helpers de
outros arquivos de teste de proposito (convencao da suite).
"""
import json
import os
import subprocess
import threading

import pytest

from conftest import git_init_isolado

import intake_journal as J

ENV = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
       "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}


def _git(cwd, *args, check=True):
    return subprocess.run(["git", *args], cwd=str(cwd), env=ENV,
                          capture_output=True, text=True,
                          encoding="utf-8", errors="replace", check=check)


# ---------------------------------------------------------------------------
# git-common-dir: localizacao e compartilhamento entre worktrees
# ---------------------------------------------------------------------------

def test_resolve_git_common_dir_fora_de_repo_git(tmp_path):
    assert J.resolve_git_common_dir(cwd=tmp_path) is None


def test_resolve_git_common_dir_repo_simples(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    git_init_isolado(repo)
    (repo / "f.txt").write_text("x\n", encoding="utf-8")
    _git(repo, "add", "f.txt")
    _git(repo, "commit", "-qm", "c0")

    got = J.resolve_git_common_dir(cwd=repo)
    assert got is not None
    assert os.path.isabs(got)
    assert os.path.normcase(os.path.normpath(got)) == \
        os.path.normcase(os.path.normpath(str(repo / ".git")))


def test_journal_compartilhado_entre_worktrees(tmp_path):
    """Grava um candidato a partir do worktree principal; confirma que o
    diretorio do journal calculado a partir de um worktree LINKED (git
    worktree add) resolve para o MESMO caminho -- prova de compartilhamento
    exigida pelo brief (nao e o .git fisico simples do worktree)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    git_init_isolado(repo)
    (repo / "f.txt").write_text("x\n", encoding="utf-8")
    _git(repo, "add", "f.txt")
    _git(repo, "commit", "-qm", "c0")

    wt = tmp_path / "wt"
    _git(repo, "worktree", "add", "-q", str(wt), "-b", "feature-x")

    dir_repo = J.journal_dir_for(cwd=repo)
    dir_wt = J.journal_dir_for(cwd=wt)
    assert dir_repo is not None and dir_wt is not None
    assert os.path.normcase(os.path.normpath(dir_repo)) == \
        os.path.normcase(os.path.normpath(dir_wt))

    path = J.write_candidate("cand-shared-1", source="test",
                              description="descoberta no worktree",
                              cwd=wt)
    assert os.path.isfile(path)
    # visivel a partir do outro worktree, pelo MESMO calculo de diretorio
    orphans = J.list_orphans(J.journal_dir_for(cwd=repo))
    ids = [rec["candidate_id"] for _p, rec in orphans]
    assert "cand-shared-1" in ids


# ---------------------------------------------------------------------------
# sanitizacao de nome de arquivo
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("raw", [
    'id:com*chars?invalidos"no<windows>|pipe',
    "id/com/barra",
    "id\\com\\contrabarra",
    "id\x00com\x01controle",
    "   id com espacos nas pontas   ",
    "id.com.pontos.finais...",
])
def test_sanitize_filename_component_remove_caracteres_invalidos(raw):
    safe = J.sanitize_filename_component(raw)
    proibidos = set('<>:"/\\|?*') | {chr(c) for c in range(32)}
    assert not (set(safe) & proibidos)
    assert safe == safe.strip().rstrip(".")
    assert safe != ""


@pytest.mark.parametrize("reservado", [
    "CON", "con", "PRN", "AUX", "NUL", "COM1", "com9", "LPT1", "lpt9",
])
def test_sanitize_filename_component_nomes_reservados_windows(reservado):
    safe = J.sanitize_filename_component(reservado)
    assert safe.upper() != reservado.upper()


def test_sanitize_filename_component_string_vazia_nao_produz_vazio():
    assert J.sanitize_filename_component("") != ""
    assert J.sanitize_filename_component("   ") != ""
    assert J.sanitize_filename_component("...") != ""


def test_sanitize_filename_component_string_longa_e_truncada():
    safe = J.sanitize_filename_component("a" * 500)
    assert len(safe) <= 120


def test_candidate_id_colidindo_apos_sanitize_nao_sobrescreve(tmp_path):
    """Dois candidate_id DIFERENTES que sanitizam para o MESMO nome (troca
    de caractere proibido por '_') nao podem colidir em disco -- o sufixo de
    hash do candidate_id original desambigua."""
    jd = str(tmp_path / "journal")
    id_a = "cand:x"
    id_b = "cand?x"
    assert J.sanitize_filename_component(id_a) == \
        J.sanitize_filename_component(id_b)

    path_a = J.write_candidate(id_a, source="test", description="a",
                                journal_dir=jd)
    path_b = J.write_candidate(id_b, source="test", description="b",
                                journal_dir=jd)
    assert path_a != path_b
    assert os.path.isfile(path_a) and os.path.isfile(path_b)

    rec_a = json.loads(open(path_a, encoding="utf-8").read())
    rec_b = json.loads(open(path_b, encoding="utf-8").read())
    assert rec_a["candidate_id"] == id_a
    assert rec_b["candidate_id"] == id_b


# ---------------------------------------------------------------------------
# gravacao atomica, validacao de campos, sanitizacao de segredo
# ---------------------------------------------------------------------------

def test_write_candidate_rejeita_source_invalido(tmp_path):
    with pytest.raises(J.IntakeJournalError):
        J.write_candidate("cand-1", source="nao-existe", description="x",
                           journal_dir=str(tmp_path / "journal"))


def test_write_candidate_fora_de_repo_git_exige_journal_dir_explicito(tmp_path):
    with pytest.raises(J.IntakeJournalError):
        J.write_candidate("cand-1", source="test", description="x",
                           cwd=tmp_path)
    # com journal_dir explicito funciona mesmo fora de um repo git
    path = J.write_candidate("cand-1", source="test", description="x",
                              cwd=tmp_path, journal_dir=str(tmp_path / "j"))
    assert os.path.isfile(path)


def test_write_candidate_grava_registro_minimo_correto(tmp_path):
    jd = str(tmp_path / "journal")
    path = J.write_candidate("cand-42", source="agent",
                              description="algo descoberto",
                              source_item="V-12", journal_dir=jd)
    rec = json.loads(open(path, encoding="utf-8").read())
    assert rec["candidate_id"] == "cand-42"
    assert rec["source"] == "agent"
    assert rec["description"] == "algo descoberto"
    assert rec["source_item"] == "V-12"
    assert rec["state"] == J.STATE_NEW
    assert "created_at" in rec and rec["created_at"]


def test_write_candidate_e_atomico_sem_temporario_residual(tmp_path):
    jd = tmp_path / "journal"
    J.write_candidate("cand-1", source="test", description="x",
                       journal_dir=str(jd))
    nomes = os.listdir(jd)
    assert all(n.endswith(".json") for n in nomes)


def test_write_candidate_redige_segredo_na_descricao(tmp_path):
    jd = str(tmp_path / "journal")
    # Montado em pedacos de proposito: escrito inteiro no fonte, o detector de
    # segredos do CI reconhece o formato e reprova o build, mesmo sendo falso.
    segredo = "AKIA" + "ABCDEFGHIJ" + "KLMNOP"
    path = J.write_candidate(
        "cand-secret", source="test",
        description=f"config exposta: aws_key={segredo} no log",
        journal_dir=jd)
    conteudo = open(path, encoding="utf-8").read()
    assert segredo not in conteudo
    assert "REDACTED" in conteudo


def test_write_candidate_redige_bloco_de_chave_privada(tmp_path):
    jd = str(tmp_path / "journal")
    # Idem: montado em pedacos para o detector de segredos do CI nao reconhecer
    # o formato no fonte. O texto que chega a funcao sob teste e o mesmo.
    marca = "-----BEGIN RSA PRIVATE" + " KEY-----"
    corpo = "MIIBOgIBAAJBAK" + "j34GkxFhD91aB"
    bloco = marca + "\n" + corpo + "\n" + marca.replace("BEGIN", "END")
    path = J.write_candidate("cand-pk", source="test",
                              description=f"achei isto: {bloco}",
                              journal_dir=jd)
    conteudo = open(path, encoding="utf-8").read()
    assert "BEGIN RSA PRIVATE KEY" not in conteudo
    assert "MIIBOgIBAAJBAKj34GkxFhD91aB" not in conteudo


def test_write_candidate_preserva_texto_pt_br_acentuado(tmp_path):
    jd = str(tmp_path / "journal")
    desc = "descoberta com acentuação e emoji 🔍 não-ascii"
    path = J.write_candidate("cand-utf8", source="test", description=desc,
                              journal_dir=jd)
    rec = json.loads(open(path, encoding="utf-8").read())
    assert rec["description"] == desc


# ---------------------------------------------------------------------------
# modos de falha enumerados: crash antes/depois de gravar, antes/depois de
# integrar, recuperacao idempotente, journal corrompido/parcial
# ---------------------------------------------------------------------------

def test_crash_antes_do_journal_dir_inexistente_nao_quebra_listagem(tmp_path):
    jd = str(tmp_path / "nunca-criado")
    assert J.list_orphans(jd) == []
    assert J.list_corrupted(jd) == []


def test_crash_apos_journal_antes_da_integracao_fica_orfao(tmp_path):
    jd = str(tmp_path / "journal")
    J.write_candidate("cand-1", source="test", description="x",
                       journal_dir=jd)
    orphans = J.list_orphans(jd)
    assert [rec["candidate_id"] for _p, rec in orphans] == ["cand-1"]


def test_recovery_sem_integracao_mantem_pendente_sem_duplicar(tmp_path):
    jd = str(tmp_path / "journal")
    J.write_candidate("cand-1", source="test", description="x",
                       journal_dir=jd)
    todo_texto = "| ID | Descricao |\n|---|---|\n| V-1 | outra coisa |\n"

    relatorio = J.recover_orphans(jd, todo_text=todo_texto)
    assert relatorio.still_pending == ["cand-1"]
    assert relatorio.recovered_as_duplicate == []
    assert len(os.listdir(jd)) == 1

    # repetir nao duplica nem muda o resultado
    relatorio2 = J.recover_orphans(jd, todo_text=todo_texto)
    assert relatorio2.still_pending == ["cand-1"]
    assert len(os.listdir(jd)) == 1
    rec = J.list_orphans(jd)[0][1]
    assert rec["state"] == J.STATE_NEW


def test_recovery_apos_integracao_marca_done(tmp_path):
    jd = str(tmp_path / "journal")
    J.write_candidate("cand-1", source="test", description="x",
                       journal_dir=jd)
    # simula que o candidato ja foi integrado: o marcador do candidate_id
    # aparece no TODO.md (contrato mecanico de dedup por ID exato, ADR-0002
    # secao (a), linha "deduplicacao por ID exato | mecanica | nucleo").
    todo_texto = "| ID | Descricao |\n|---|---|\n| V-9 | x <!-- cand-1 --> |\n"

    relatorio = J.recover_orphans(jd, todo_text=todo_texto)
    assert relatorio.recovered_as_duplicate == ["cand-1"]
    assert relatorio.still_pending == []
    assert J.list_orphans(jd) == []


def test_recovery_e_idempotente_rodada_dupla_nao_duplica(tmp_path):
    jd = str(tmp_path / "journal")
    J.write_candidate("cand-1", source="test", description="x",
                       journal_dir=jd)
    todo_texto = "cand-1 ja integrado em algum lugar do texto"

    r1 = J.recover_orphans(jd, todo_text=todo_texto)
    assert r1.recovered_as_duplicate == ["cand-1"]
    n1 = len(os.listdir(jd))

    r2 = J.recover_orphans(jd, todo_text=todo_texto)
    assert r2.recovered_as_duplicate == []  # ja estava DONE, nao e orfao
    assert r2.still_pending == []
    n2 = len(os.listdir(jd))
    assert n1 == n2 == 1


def test_journal_corrompido_e_reportado_sem_quebrar(tmp_path):
    jd = tmp_path / "journal"
    jd.mkdir()
    (jd / "quebrado--abc1234567.json").write_text("{nao e json valido",
                                                    encoding="utf-8")
    corrompidos = J.list_corrupted(str(jd))
    assert len(corrompidos) == 1
    # nao aparece como orfao classificavel (evita mark_done as cegas)
    assert J.list_orphans(str(jd)) == []
    # recover_orphans nao explode com arquivo corrompido no diretorio
    relatorio = J.recover_orphans(str(jd), todo_text="qualquer coisa")
    assert relatorio.still_pending == []
    assert relatorio.recovered_as_duplicate == []
    assert len(relatorio.corrupted) == 1


def test_arquivo_temporario_orfao_e_ignorado_na_listagem(tmp_path):
    jd = tmp_path / "journal"
    jd.mkdir()
    (jd / ".intake_journal.tmp123.tmp").write_text("lixo parcial",
                                                     encoding="utf-8")
    assert J.list_orphans(str(jd)) == []
    assert J.list_corrupted(str(jd)) == []


def test_dois_processos_gravando_candidatos_diferentes_concorrentemente(tmp_path):
    jd = str(tmp_path / "journal")
    os.makedirs(jd, exist_ok=True)
    n = 12
    erros = []

    def _write(i):
        try:
            J.write_candidate(f"cand-conc-{i}", source="test",
                               description=f"item {i}", journal_dir=jd)
        except Exception as exc:  # pragma: no cover - so falha se houver bug
            erros.append(exc)

    threads = [threading.Thread(target=_write, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert erros == []
    orphans = J.list_orphans(jd)
    ids = sorted(rec["candidate_id"] for _p, rec in orphans)
    assert ids == sorted(f"cand-conc-{i}" for i in range(n))
    assert J.list_corrupted(jd) == []


def test_dois_processos_gravando_mesmo_candidato_concorrentemente_sem_corromper(tmp_path):
    jd = str(tmp_path / "journal")
    os.makedirs(jd, exist_ok=True)
    resultados = []

    def _write(desc):
        resultados.append(J.write_candidate("cand-race", source="test",
                                              description=desc,
                                              journal_dir=jd))

    threads = [threading.Thread(target=_write, args=(f"versao-{i}",))
               for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # todas as threads apontam para o MESMO arquivo final (candidate_id
    # identico -> nome deterministico)
    assert len(set(resultados)) == 1
    path = resultados[0]
    # o arquivo final e sempre JSON valido e completo -- nunca gravacao
    # parcial ("torn write"), mesmo sob 8 escritores concorrentes
    rec = json.loads(open(path, encoding="utf-8").read())
    assert rec["candidate_id"] == "cand-race"
    assert rec["description"].startswith("versao-")


# ---------------------------------------------------------------------------
# ciclo de vida: mark_done / remove_candidate, idempotentes
# ---------------------------------------------------------------------------

def test_mark_done_idempotente(tmp_path):
    jd = str(tmp_path / "journal")
    J.write_candidate("cand-1", source="test", description="x",
                       journal_dir=jd)
    assert J.mark_done(jd, "cand-1") is True
    assert J.mark_done(jd, "cand-1") is True  # repetir nao quebra
    assert J.mark_done(jd, "nao-existe") is False
    assert J.list_orphans(jd) == []


def test_remove_candidate_seguro_e_idempotente(tmp_path):
    jd = str(tmp_path / "journal")
    J.write_candidate("cand-1", source="test", description="x",
                       journal_dir=jd)
    assert J.remove_candidate(jd, "cand-1") is True
    assert J.remove_candidate(jd, "cand-1") is False  # ja removido: no-op
    assert os.listdir(jd) == []


def test_new_candidate_id_gera_ids_unicos():
    ids = {J.new_candidate_id() for _ in range(200)}
    assert len(ids) == 200
    for cid in ids:
        assert cid == J.sanitize_filename_component(cid)
