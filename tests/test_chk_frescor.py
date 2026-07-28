"""Suite de CHK-09 (claims obsoletas na Descricao, contra o git real) e
CHK-10 (proposta do todo_sync.py sem --apply, anexada ao relatorio).

Ambos sao `profile == "core"` (ADR-0001 secao a), registrados em
`tools/todo_audit.py` via `checks.chk_frescor.chk09`/`chk10`.
"""
import hashlib
import os
import subprocess
import sys

import pytest

import todo_audit as A
import todo_lib as L
from checks import chk_frescor as F

from conftest import git_init_isolado

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS_DIR = os.path.join(REPO_ROOT, "tools")

ENV = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
       "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}


def _git(cwd, *args, check=True):
    return subprocess.run(["git", *args], cwd=cwd, env=ENV,
                          capture_output=True, text=True, check=check)


def _md5(path):
    with open(path, "rb") as fh:
        return hashlib.md5(fh.read()).hexdigest()


HEADER = ("| ID | Onda | Grupo | Descrição | Prioridade | Pré-requisito | "
          "Dificuldade | Status | Estado Auditado |")
SEP = "| :- | :- | :- | :- | :- | :- | :- | :- | :- |"


def _row(iid, desc, status="⏳ Pendente"):
    return (f"| {iid} | W1 | Grupo | {desc} | Alta | — | Média | {status} "
            "| — |")


def _todo(rows):
    return "\n".join([HEADER, SEP, *rows]) + "\n"


def _repo(tmp_path, todo_text):
    git_init_isolado(tmp_path)
    (tmp_path / "TODO.md").write_text(todo_text, encoding="utf-8")
    _git(tmp_path, "add", "TODO.md")
    _git(tmp_path, "commit", "-qm", "tabela")
    return tmp_path


def _bare_remote(tmp_path_factory):
    bare = tmp_path_factory.mktemp("bare") / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", str(bare)], env=ENV,
                  check=True, capture_output=True)
    return bare


# ---------------------------- registro / motor -----------------------------

def test_chk09_e_chk10_registrados_como_core():
    ids = {c.id: c for c in A.CHECKS}
    assert ids["CHK-09"].profile == "core"
    assert ids["CHK-10"].profile == "core"


def test_chk09_severity_default_nao_e_critico():
    ids = {c.id: c for c in A.CHECKS}
    assert ids["CHK-09"].severity_default in ("IMPORTANTE", "COSMÉTICO")
    assert ids["CHK-10"].severity_default == "COSMÉTICO"


# ---------------------------- CHK-09: agnostico a idioma -------------------

def test_chk09_dispara_em_corpus_ingles(tmp_path, tmp_path_factory):
    """AC-0/ADR-0001(d): nenhum check pode assumir portugues no conteudo
    livre. Corpus so em ingles, remoto local (bare) ja com HEAD -- prova
    que o padrao default 'not pushed' dispara mesmo fora do idioma do
    autor."""
    bare = _bare_remote(tmp_path_factory)
    root = _repo(tmp_path, _todo([
        _row("EN-1", "Work done, but still not pushed to the server."),
    ]))
    _git(root, "remote", "add", "origin", str(bare))
    _git(root, "push", "-q", "origin", "HEAD:refs/heads/main")

    res = A.run_audit(str(root))
    achados = [f for f in res.findings if f.check_id == "CHK-09"]
    assert achados, "CHK-09 nao disparou em descricao 100% em ingles"
    assert achados[0].severity == "IMPORTANTE"
    assert "not pushed" in achados[0].message


def test_chk09_dispara_em_corpus_pt(tmp_path, tmp_path_factory):
    bare = _bare_remote(tmp_path_factory)
    root = _repo(tmp_path, _todo([
        _row("PT-1", "Trabalho pronto, mas ainda é commit local não pushado."),
    ]))
    _git(root, "remote", "add", "origin", str(bare))
    _git(root, "push", "-q", "origin", "HEAD:refs/heads/main")

    res = A.run_audit(str(root))
    achados = [f for f in res.findings if f.check_id == "CHK-09"]
    assert achados


# ---------------------------- CHK-09: motivador real ------------------------

def test_chk09_acha_claim_obsoleta_quando_ja_esta_no_remoto(tmp_path, tmp_path_factory):
    """Caso real que motivou o check: item diz 'commit local, nao pushado'
    mas o trabalho ja esta em origin ha dias (aqui: mesmo HEAD)."""
    bare = _bare_remote(tmp_path_factory)
    root = _repo(tmp_path, _todo([
        _row("V-1", "Fix pronto: commit local, ainda não pushado."),
    ]))
    _git(root, "remote", "add", "origin", str(bare))
    _git(root, "push", "-q", "origin", "HEAD:refs/heads/main")

    res = A.run_audit(str(root))
    achados = [f for f in res.findings if f.check_id == "CHK-09"]
    assert len(achados) == 1
    f = achados[0]
    assert f.severity == "IMPORTANTE"
    assert f.fixable is False
    assert "V-1" in f.message
    assert "já está no remoto" in f.message or "ja esta no remoto" in f.message.lower()
    assert f.line_no == 2  # 0-based: 3a linha do arquivo


def test_chk09_nao_acha_nada_quando_claim_ainda_e_verdadeira(tmp_path, tmp_path_factory):
    """Commit local genuino, nunca pushado -- claim se sustenta, sem achado."""
    bare = _bare_remote(tmp_path_factory)
    root = _repo(tmp_path, _todo([
        _row("V-2", "placeholder"),
    ]))
    _git(root, "remote", "add", "origin", str(bare))
    _git(root, "push", "-q", "origin", "HEAD:refs/heads/main")

    # commit novo, NUNCA pushado -- reescreve a descricao do item citando a claim
    root_todo = root / "TODO.md"
    root_todo.write_text(_todo([
        _row("V-2", "Ainda é commit local, não pushado -- aguardando review."),
    ]), encoding="utf-8")
    _git(root, "add", "TODO.md")
    _git(root, "commit", "-qm", "atualiza V-2")

    res = A.run_audit(str(root))
    achados = [f for f in res.findings if f.check_id == "CHK-09"]
    assert achados == [], (
        f"claim genuinamente valida nao deveria gerar achado: {achados}")


def test_chk09_sem_remote_vira_achado_cosmetico_nao_verificavel(tmp_path):
    """Sem remoto configurado: nunca silencioso -- vira achado COSMETICO
    'nao verificavel', nunca um veredito afirmativo."""
    root = _repo(tmp_path, _todo([
        _row("NR-1", "Ainda é commit local, não pushado."),
    ]))
    res = A.run_audit(str(root))
    achados = [f for f in res.findings if f.check_id == "CHK-09"]
    assert len(achados) == 1
    assert achados[0].severity == "COSMÉTICO"
    assert "sem remoto" in achados[0].message.lower()


def test_chk09_branch_ausente_no_remoto_e_obsoleta(tmp_path, tmp_path_factory):
    bare = _bare_remote(tmp_path_factory)
    root = _repo(tmp_path, _todo([
        _row("BR-1", "Está na branch `feature-x`, aguardando merge."),
    ]))
    _git(root, "remote", "add", "origin", str(bare))
    _git(root, "push", "-q", "origin", "HEAD:refs/heads/main")
    # 'feature-x' nunca existiu no remoto -- claim (implicitamente) obsoleta
    # (ou nunca existiu, mas o sinal e o mesmo do ponto de vista do check:
    # a branch citada NAO esta la para ser conferida).
    res = A.run_audit(str(root))
    achados = [f for f in res.findings if f.check_id == "CHK-09"]
    assert achados
    assert any("feature-x" in f.message for f in achados)
    assert achados[0].severity == "IMPORTANTE"


def test_chk09_branch_presente_no_remoto_nao_acha_nada(tmp_path, tmp_path_factory):
    bare = _bare_remote(tmp_path_factory)
    root = _repo(tmp_path, _todo([
        _row("BR-2", "Está na branch `feature-y`, aguardando merge."),
    ]))
    _git(root, "remote", "add", "origin", str(bare))
    _git(root, "push", "-q", "origin", "HEAD:refs/heads/main")
    _git(root, "branch", "feature-y")
    _git(root, "push", "-q", "origin", "feature-y")

    res = A.run_audit(str(root))
    achados = [f for f in res.findings if f.check_id == "CHK-09"]
    assert achados == []


# ---------------------------- CHK-09: falsos-positivos medidos ao vivo -----
#
# As tres proximas fixtures reproduzem, com dado sintetico, casos REAIS
# encontrados rodando CHK-09 contra TAB_PENDENCIAS_FIXTURE_A
# (consumidor A/TODO.md): a palavra "branch" em portugues NEM SEMPRE
# significa branch git ("branch de codigo"/if-else, "branch" como
# adjetivo posposto -- "branch novo"), e teria virado uma afirmacao
# categorica FALSA ("branch 'novo' nao existe no remoto") sem a guarda de
# exigir crase na extracao (`_extract_branch_name`).

def test_chk09_branch_sem_crase_nao_extrai_nome_fica_desconhecido(tmp_path, tmp_path_factory):
    """'branch em runtime'/'branch novo'/'branch Win32' (sem crase) sao
    portugues comum, nao uma branch git citada -- o check tem que degradar
    para COSMETICO 'nao verificavel' (ou nao extrair nada), NUNCA afirmar
    categoricamente que uma branch chamada 'em'/'novo'/'Win32' nao existe."""
    bare = _bare_remote(tmp_path_factory)
    root = _repo(tmp_path, _todo([
        _row("FP-1", "Fallback via um 2º branch em runtime, sem reordenar."),
        _row("FP-2", "Versão MÍNIMA possível (branch novo, zero linha tocada)."),
        _row("FP-3", "Inspeção do branch Win32 (sentinelas/WINAPI/ordem)."),
    ]))
    _git(root, "remote", "add", "origin", str(bare))
    _git(root, "push", "-q", "origin", "HEAD:refs/heads/main")

    res = A.run_audit(str(root))
    achados = [f for f in res.findings if f.check_id == "CHK-09"]
    for f in achados:
        assert "'em'" not in f.message
        assert "'novo'" not in f.message
        assert "'win32'" not in f.message.lower()
        # se disparou, so pode ser como INCONCLUSIVO -- nunca afirmando
        # categoricamente que uma branch com esse nome nao existe.
        assert f.severity == "COSMÉTICO"


def test_chk09_branch_de_outro_repositorio_git_nao_verifica_contra_remoto_errado(
        tmp_path, tmp_path_factory):
    """'outro-projeto.wiki.git, branch `master`' cita a branch de OUTRO
    repositorio (a wiki), nao do repo que este --audit esta rodando --
    verificar 'master' contra o remoto do repo principal e comparar coisas
    diferentes. O check tem que recusar a extracao (fica 'desconhecido'),
    nunca afirmar 'master nao existe' com base no remoto errado."""
    bare = _bare_remote(tmp_path_factory)
    root = _repo(tmp_path, _todo([
        _row("WIKI-1",
             "Publicar em `projeto.wiki.git`, branch `master` (wiki nativa)."),
    ]))
    _git(root, "remote", "add", "origin", str(bare))
    _git(root, "push", "-q", "origin", "HEAD:refs/heads/main")

    res = A.run_audit(str(root))
    achados = [f for f in res.findings if f.check_id == "CHK-09"]
    assert not any("'master' não existe" in f.message
                  or "'master' nao existe" in f.message.lower()
                  for f in achados)


def test_extrai_branch_so_com_crase_recusa_texto_cru():
    assert F._extract_branch_name("um 2º branch em runtime") is None
    assert F._extract_branch_name("branch novo, zero linha tocada") is None
    assert F._extract_branch_name("inspeção do branch Win32 (x)") is None
    assert F._extract_branch_name("entregue na branch `feat/x`") == "feat/x"
    assert F._extract_branch_name(
        "branch descartável `ci/heavy-runner-smoke`, já apagada"
    ) == "ci/heavy-runner-smoke"


def test_extrai_branch_recusa_quando_contexto_cita_outro_repo_git():
    assert F._extract_branch_name(
        "`projeto.wiki.git`, branch `master`") is None


# ------------------- CHK-09: citacao vs. afirmacao (achado auto-referencial) -
#
# Achado real, reportado pelo team-lead: a PROPRIA linha do CHK-09 na
# TODO.md deste repositorio ("Claims obsoletas na Descrição (\"não
# pushado\", \"commit local\", \"branch X\") verificadas...") disparava os
# proprios padroes -- o texto MENCIONA os padroes como exemplo de catalogo
# (entre aspas, numa enumeracao), nao esta fazendo nenhuma claim sobre o
# proprio item. Mesma familia do defeito fundador do projeto (o item que
# DESCREVIA o bug do pipe cru era ele mesmo invisivel por causa do pipe).

def test_chk09_nao_acusa_padrao_citado_entre_aspas_como_exemplo(tmp_path, tmp_path_factory):
    """Reproducao exata do caso real: reescreve a propria linha de CHK-09
    (texto identico ao que esta na TODO.md deste repo) e confirma que os 3
    padroes citados entre aspas NAO disparam achado."""
    bare = _bare_remote(tmp_path_factory)
    root = _repo(tmp_path, _todo([
        _row("CHK-09", 'Claims obsoletas na Descrição ("não pushado", '
                       '"commit local", "branch X") verificadas contra o '
                       'git real.'),
    ]))
    _git(root, "remote", "add", "origin", str(bare))
    _git(root, "push", "-q", "origin", "HEAD:refs/heads/main")

    res = A.run_audit(str(root))
    achados = [f for f in res.findings if f.check_id == "CHK-09"]
    assert achados == [], (
        f"citacao de padrao como EXEMPLO nao deveria virar achado: {achados}")


def test_chk09_ainda_acusa_quando_pattern_esta_fora_de_aspas(tmp_path):
    """Contraprova: o MESMO padrao, fora de aspas, na mesma descricao,
    continua contando como possivel afirmacao (a supressao e so para o
    padrao entre aspas adjacentes, nao um apagao geral do pattern)."""
    root = _repo(tmp_path, _todo([
        _row("Q-1", 'Exemplos de claim ("branch X") à parte: este item '
                    'ainda é commit local, não pushado de verdade.'),
    ]))
    res = A.run_audit(str(root))
    achados = [f for f in res.findings if f.check_id == "CHK-09"]
    assert achados, "claim genuina fora de aspas nao deveria ser suprimida"


def test_pattern_ocorrencia_fora_de_citacao_unidade():
    citado = ('Claims obsoletas na Descrição ("não pushado", "commit local", '
             '"branch X") verificadas contra o git real.')
    assert not F._pattern_tem_ocorrencia_fora_de_citacao(citado, "não pushado")
    assert not F._pattern_tem_ocorrencia_fora_de_citacao(citado, "commit local")
    assert not F._pattern_tem_ocorrencia_fora_de_citacao(citado, "branch ")

    afirmacao = "Ainda é commit local, não pushado."
    assert F._pattern_tem_ocorrencia_fora_de_citacao(afirmacao, "commit local")
    assert F._pattern_tem_ocorrencia_fora_de_citacao(afirmacao, "não pushado")


def test_dogfood_proprio_repo_chk09_zero_achados():
    """Regressao direta do achado real do team-lead: rodar CHK-09 contra a
    TODO.md deste proprio repositorio (que cita os padroes como exemplo na
    linha do proprio CHK-09) da ZERO achados de CHK-09."""
    res = A.run_audit(REPO_ROOT)
    achados = [f for f in res.findings if f.check_id == "CHK-09"]
    assert achados == [], (
        f"CHK-09 disparou achado(s) auto-referencial(is) na TODO.md do "
        f"proprio repo: {achados}")


# ---------------------------- CHK-09: config extensivel ---------------------

def test_chk09_config_estende_patterns_sem_substituir(tmp_path):
    root = _repo(tmp_path, _todo([
        _row("CFG-1", "Aguardando push manual do responsável."),
        _row("CFG-2", "Ainda é commit local."),
    ]))
    (root / ".tab_pendencias.ini").write_text(
        "[audit.chk09]\npatterns = aguardando push manual\n", encoding="utf-8")
    res = A.run_audit(str(root))
    achados = {f.line_no for f in res.findings if f.check_id == "CHK-09"}
    # os DOIS disparam: o pattern novo (CFG-1) E o default (CFG-2) --
    # extensao, nao substituicao.
    assert 2 in achados and 3 in achados


def test_chk09_config_override_substitui_defaults(tmp_path):
    root = _repo(tmp_path, _todo([
        _row("OVR-1", "Aguardando push manual do responsável."),
        _row("OVR-2", "Ainda é commit local."),
    ]))
    (root / ".tab_pendencias.ini").write_text(
        "[audit.chk09]\npatterns = aguardando push manual\n"
        "patterns_override = true\n", encoding="utf-8")
    res = A.run_audit(str(root))
    achados = [f for f in res.findings if f.check_id == "CHK-09"]
    # so o pattern configurado dispara (linha 2); 'commit local' (linha 3,
    # default) NAO dispara mais -- override substituiu, nao estendeu.
    assert any(f.line_no == 2 for f in achados)
    assert not any(f.line_no == 3 for f in achados)


def test_patterns_default_tem_pt_e_en():
    low = [p.lower() for p in F.DEFAULT_PATTERNS]
    assert any("push" in p and ("nao" in p or "não" in p) for p in low)
    assert any(p == "not pushed" for p in low)


# ---------------------------- CHK-09: read-only -----------------------------

def test_chk09_e_read_only(tmp_path, tmp_path_factory):
    bare = _bare_remote(tmp_path_factory)
    root = _repo(tmp_path, _todo([
        _row("RO-1", "Ainda é commit local, não pushado."),
    ]))
    _git(root, "remote", "add", "origin", str(bare))
    _git(root, "push", "-q", "origin", "HEAD:refs/heads/main")
    todo = root / "TODO.md"
    antes = _md5(todo)
    A.run_audit(str(root))
    assert _md5(todo) == antes


# ---------------------------- CHK-10 ----------------------------------------

def test_chk10_nada_a_propor_nao_gera_achado(tmp_path):
    """Repo limpo, sem nenhum commit citando ID -- rc=0 do proprio
    `todo_sync.py` (D-6): "informacao anexa" so faz sentido quando ha algo
    a anexar (proposta real ou falha de execucao); do contrario CHK-10 fica
    em SILENCIO DE PROPOSITO (lista vazia), preservando o invariante do
    motor "tabela limpa -> 0 achados totais" que `test_todo_audit.py`
    (fatia AUDIT-ENG, anterior a este check) ja depende."""
    root = _repo(tmp_path, _todo([_row("S-1", "placeholder")]))
    res = A.run_audit(str(root))
    achados = [f for f in res.findings if f.check_id == "CHK-10"]
    assert achados == []


def test_chk10_com_proposta_real_emite_exatamente_um_finding(tmp_path):
    root = _repo(tmp_path, _todo([_row("F-1", "algo a fazer")]))
    sync = os.path.join(TOOLS_DIR, "todo_sync.py")
    # 1a execucao so estabelece o baseline (linha de base = HEAD, D-2/ADR):
    # sem isso, o commit que cita F-1 logo abaixo cairia na semantica de
    # '1a execucao' do proprio todo_sync e nao proporia nada (rc=0).
    subprocess.run([sys.executable, sync, "--apply"], cwd=root,
                  capture_output=True, text=True)
    (root / "codigo.py").write_text("x = 1\n", encoding="utf-8")
    _git(root, "add", "codigo.py")
    _git(root, "commit", "-qm", "feat: entrega F-1")

    res = A.run_audit(str(root))
    achados = [f for f in res.findings if f.check_id == "CHK-10"]
    assert len(achados) == 1
    assert achados[0].severity == "COSMÉTICO"
    assert achados[0].fixable is False


def test_chk10_nao_infla_contagem_mesmo_com_varios_ids_citados(tmp_path):
    """N itens citados e entregues no MESMO intervalo -> ainda assim CHK-10
    emite 1 unico achado (nao e defeito, e informacao anexa; nao inflar a
    contagem com N achados por item proposto)."""
    root = _repo(tmp_path, _todo([
        _row("N-1", "primeiro"), _row("N-2", "segundo"), _row("N-3", "terceiro"),
    ]))
    sync = os.path.join(TOOLS_DIR, "todo_sync.py")
    subprocess.run([sys.executable, sync, "--apply"], cwd=root,
                  capture_output=True, text=True)
    for i in ("N-1", "N-2", "N-3"):
        (root / f"src_{i}.py").write_text("x = 1\n", encoding="utf-8")
        _git(root, "add", f"src_{i}.py")
        _git(root, "commit", "-qm", f"feat: entrega {i}")
    res = A.run_audit(str(root))
    achados = [f for f in res.findings if f.check_id == "CHK-10"]
    assert len(achados) == 1
    assert all(i in achados[0].message for i in ("N-1", "N-2", "N-3"))


def test_chk10_menciona_aviso_canonico_e_baseline_quando_ha_achado(tmp_path):
    root = _repo(tmp_path, _todo([_row("S-2", "placeholder")]))
    sync = os.path.join(TOOLS_DIR, "todo_sync.py")
    subprocess.run([sys.executable, sync, "--apply"], cwd=root,
                  capture_output=True, text=True)
    (root / "codigo.py").write_text("x = 1\n", encoding="utf-8")
    _git(root, "add", "codigo.py")
    _git(root, "commit", "-qm", "feat: entrega S-2")

    res = A.run_audit(str(root))
    f = next(f for f in res.findings if f.check_id == "CHK-10")
    assert "desconfiança" in f.message or "desconfianca" in f.message.lower()
    assert "baseline" in f.message.lower()
    assert "todo-sync-ref" in f.message
    assert "presente" in f.message.lower()  # baseline foi estabelecido acima


def test_baseline_message_ausente_por_padrao_e_presente_apos_apply(tmp_path):
    """Testa `_baseline_message` diretamente (unidade), independente de
    CHK-10 emitir achado ou nao -- ver docstring de `chk10` sobre por que a
    presenca do achado e condicional."""
    root = _repo(tmp_path, _todo([_row("BM-1", "placeholder")]))
    existe, msg = F._baseline_message(str(root))
    assert existe is False
    assert "sem baseline" in msg.lower()

    sync = os.path.join(TOOLS_DIR, "todo_sync.py")
    subprocess.run([sys.executable, sync, "--apply"], cwd=root,
                  capture_output=True, text=True)
    existe, msg = F._baseline_message(str(root))
    assert existe is True
    assert "presente" in msg.lower()
    assert "todo-sync-ref" in msg


def test_chk10_mostra_proposta_de_flip_quando_ha_id_citado_e_entregue(tmp_path):
    root = _repo(tmp_path, _todo([_row("F-1", "algo a fazer")]))
    sync = os.path.join(TOOLS_DIR, "todo_sync.py")
    # 1a execucao so estabelece o baseline (linha de base = HEAD, D-2/ADR):
    # sem isso, o commit que cita F-1 logo abaixo cairia na semantica de
    # '1a execucao' do proprio todo_sync e nao proporia nada.
    subprocess.run([sys.executable, sync, "--apply"], cwd=root,
                  capture_output=True, text=True)

    (root / "codigo.py").write_text("x = 1\n", encoding="utf-8")
    _git(root, "add", "codigo.py")
    _git(root, "commit", "-qm", "feat: entrega F-1")
    res = A.run_audit(str(root))
    f = next(f for f in res.findings if f.check_id == "CHK-10")
    assert "F-1" in f.message
    assert "Pendente verificação" in f.message


def test_chk10_e_read_only_nunca_toca_todo_md_nem_ref(tmp_path):
    root = _repo(tmp_path, _todo([_row("F-2", "algo a fazer")]))
    (root / "codigo.py").write_text("x = 1\n", encoding="utf-8")
    _git(root, "add", "codigo.py")
    _git(root, "commit", "-qm", "feat: entrega F-2")

    todo = root / "TODO.md"
    antes = _md5(todo)
    gd = L.git_dir(str(root))
    ref_path = os.path.join(gd, "todo-sync-ref")
    A.run_audit(str(root))
    assert _md5(todo) == antes
    assert not os.path.isfile(ref_path), (
        "CHK-10 gravou o ref de sync -- --audit tem que ser SEMPRE "
        "read-only, mesmo rodando todo_sync.py internamente (sem --apply)")


def test_chk10_nunca_passa_apply_no_subprocess(monkeypatch, tmp_path):
    """Prova estrutural (nao so comportamental): intercepta subprocess.run
    dentro do modulo do check e afirma que '--apply' nunca aparece nos
    argumentos passados."""
    root = _repo(tmp_path, _todo([_row("F-3", "algo")]))
    chamadas = []
    real_run = subprocess.run

    def _fake_run(args, *a, **kw):
        chamadas.append(list(args))
        return real_run(args, *a, **kw)

    monkeypatch.setattr(F.subprocess, "run", _fake_run)
    A.run_audit(str(root))
    todo_sync_calls = [c for c in chamadas if any("todo_sync.py" in str(a) for a in c)]
    assert todo_sync_calls, "todo_sync.py nao foi chamado pelo CHK-10"
    for call in todo_sync_calls:
        assert "--apply" not in call


# ---------------------------- integração CHK-09 + CHK-10 no relatorio ------

def test_relatorio_mostra_chk09_e_chk10(tmp_path, tmp_path_factory):
    bare = _bare_remote(tmp_path_factory)
    root = _repo(tmp_path, _todo([
        _row("RPT-1", "Ainda é commit local, não pushado."),
    ]))
    _git(root, "remote", "add", "origin", str(bare))
    sync = os.path.join(TOOLS_DIR, "todo_sync.py")
    # baseline ANTES do commit que entrega RPT-1 (senao o proprio todo_sync
    # cai na semantica de '1a execucao' e nao propoe nada).
    subprocess.run([sys.executable, sync, "--apply"], cwd=root,
                  capture_output=True, text=True)
    (root / "codigo.py").write_text("x = 1\n", encoding="utf-8")
    _git(root, "add", "codigo.py")
    _git(root, "commit", "-qm", "feat: entrega RPT-1")
    # push por ULTIMO, com o HEAD ja incluindo o commit que entrega RPT-1 --
    # senao esse commit ficaria genuinamente nao-pushado, e a claim de
    # CHK-09 ('commit local, nao pushado') estaria correta (sem achado).
    _git(root, "push", "-q", "origin", "HEAD:refs/heads/main")

    res = A.run_audit(str(root))
    assert "CHK-09" in res.report_text
    assert "CHK-10" in res.report_text
    assert "[julgamento]" in res.report_text


# ---------------------------- fixtures reais (opcionais, locais) -----------

@pytest.mark.parametrize("env_var", ["TAB_PENDENCIAS_FIXTURE_A",
                                      "TAB_PENDENCIAS_FIXTURE_B"])
def test_chk09_chk10_contra_fixture_real_read_only(env_var):
    path = os.environ.get(env_var)
    if not path or not os.path.isfile(path):
        pytest.skip(f"{env_var} não configurada (fixture local, nunca commitada)")
    root = os.path.dirname(path)
    antes = _md5(path)
    res = A.run_audit(root)
    depois = _md5(path)
    assert antes == depois
    chk09 = [f for f in res.findings if f.check_id == "CHK-09"]
    chk10 = [f for f in res.findings if f.check_id == "CHK-10"]
    # CHK-10 emite NO MAXIMO 1 achado (0 quando nao ha nada a propor, ver
    # docstring de `chk10`/`chk_frescor.py`) -- nunca mais que 1.
    assert len(chk10) in (0, 1)
    resumo_chk10 = (chk10[0].message.splitlines()[0][:200] if chk10
                   else "(sem achado -- nada a propor nesta fixture agora)")
    print(f"[{env_var}] CHK-09: {len(chk09)} achado(s); CHK-10: {resumo_chk10}")
