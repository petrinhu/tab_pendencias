#!/usr/bin/env python3
"""
~/.claude/githooks/selftest_no_mdash_staged.py

PROVA que o portao no_mdash_staged.py fica VERMELHO contra o que deve
barrar (L-36: portao so conta depois de provado vermelho). Monta um
repositorio git descartavel em /var/tmp (nunca /tmp, que e tmpfs nesta
maquina; nunca dentro de um repo real), stageia arquivos e confere o
codigo de saida do verificador e o texto que ele imprime.

Casos cobertos:
  1. arquivo user-facing (README.md) com em-dash staged -> exit 1
  2. o mesmo arquivo limpo (sem em-dash/en-dash) staged  -> exit 0
  3. arquivo NAO user-facing (TODO.md) com em-dash staged -> exit 0
  4. arquivo user-facing (README.md) com en-dash staged  -> exit 1
  5. arquivo user-facing (README.md) com en-dash removido -> exit 0
  6. caminhos RELATIVOS (como o git entrega): public/guia.md, docs/narrative/
     cap1.md e site/x.md com dash -> exit 1; DECISOES_AUTONOMAS.md e
     tests/x.md com dash -> exit 0 (defeito 2: fragmentos com barra inicial)
  7. so arquivo interno staged -> stdout declara "0 user-facing file(s)
     among 1 staged file(s)" (defeito 1: zero sem declaracao)
  8. arquivo user-facing staged -> stdout NAO traz a declaracao de zero
  9. verificador copiado para uma arvore sem o no_mdash.py canonico ao lado
     -> rc diferente de 0 e stderr cita o caminho procurado (fail-closed)

Uso: python3 ~/.claude/githooks/selftest_no_mdash_staged.py
(rode pelo caminho ~/.claude/githooks/, que e o que o pre-commit usa: o
verificador acha o no_mdash.py canonico relativo ao caminho em que foi
chamado, e a copia dentro de tools/hooks/ nao o enxerga.)
"""
import os
import shutil
import subprocess
import sys
import tempfile

_AQUI = os.path.dirname(os.path.abspath(__file__))
_VERIFICADOR = os.path.join(_AQUI, "no_mdash_staged.py")

EM_DASH = "—"
EN_DASH = "–"


def _git(repo, *args):
    p = subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, timeout=30,
    )
    return p.returncode, p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")


def _novo_repo() -> str:
    repo = tempfile.mkdtemp(prefix="selftest-no-mdash-staged-", dir="/var/tmp")
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "selftest@example.com")
    _git(repo, "config", "user.name", "selftest")
    return repo


def _escrever_e_stagear(repo: str, nome: str, conteudo: str):
    caminho = os.path.join(repo, nome)
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    with open(caminho, "w", encoding="utf-8") as f:
        f.write(conteudo)
    rc, _, err = _git(repo, "add", nome)
    if rc != 0:
        raise RuntimeError(f"git add {nome} falhou: {err}")


def _rodar_verificador(repo: str):
    p = subprocess.run(
        [sys.executable, _VERIFICADOR], cwd=repo, capture_output=True, timeout=30,
    )
    return p.returncode, p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")


# Cada caso: (descricao, arquivo, conteudo, rc_esperado[, trechos que DEVEM
# aparecer no stdout[, trechos que NAO podem aparecer no stdout]]).
CASOS = (
    (
        "README.md com em-dash staged deve reprovar",
        "README.md",
        f"Este texto tem em-dash{EM_DASH} no meio.",
        1,
    ),
    (
        "README.md limpo staged deve passar",
        "README.md",
        "Este texto nao tem pontuacao suspeita, so virgula, e ponto final.",
        0,
    ),
    (
        "TODO.md (nao user-facing) com em-dash staged deve passar",
        "TODO.md",
        f"Pendencia interna com em-dash{EM_DASH} no meio.",
        0,
    ),
    (
        "README.md com en-dash staged deve reprovar",
        "README.md",
        f"Periodo de 1990{EN_DASH}2000 no texto.",
        1,
    ),
    (
        "README.md com hifen simples staged deve passar",
        "README.md",
        "Periodo de 1990-2000 no texto.",
        0,
    ),
)

# Caminhos relativos, como o git entrega no staged (defeito 2).
CASOS_CAMINHO = (
    (
        "public/guia.md com em-dash staged deve reprovar (relativo)",
        "public/guia.md",
        f"Texto{EM_DASH} no guia publico.",
        1,
    ),
    (
        "docs/narrative/cap1.md com em-dash staged deve reprovar (relativo)",
        "docs/narrative/cap1.md",
        f"Capitulo{EM_DASH} um.",
        1,
    ),
    (
        "site/x.md com en-dash staged deve reprovar (relativo)",
        "site/x.md",
        f"Periodo 1990{EN_DASH}2000.",
        1,
    ),
    (
        "DECISOES_AUTONOMAS.md com em-dash staged deve passar (interno)",
        "DECISOES_AUTONOMAS.md",
        f"Decisao{EM_DASH} interna.",
        0,
    ),
    (
        "tests/x.md com em-dash staged deve passar (interno, relativo)",
        "tests/x.md",
        f"Caso{EM_DASH} interno.",
        0,
    ),
)

# Declaracao de zero (defeito 1): quando nada e user-facing, o verificador
# diz por que, em vez de imprimir so a linha de contagem.
CASOS_DECLARACAO = (
    (
        "so arquivo interno staged: declara zero user-facing among 1",
        "DECISOES_AUTONOMAS.md",
        f"Decisao{EM_DASH} interna.",
        0,
        (
            "encontrados=0 analisados=0 falharam=0",
            "0 user-facing file(s) among 1 staged file(s)",
        ),
        (),
    ),
    (
        "arquivo user-facing staged: nao declara zero",
        "README.md",
        "Texto limpo, so virgula.",
        0,
        (),
        ("0 user-facing file(s)",),
    ),
)


def _checar(caso) -> tuple[bool, str]:
    descricao, nome_arquivo, conteudo, esperado = caso[:4]
    deve_conter = caso[4] if len(caso) > 4 else ()
    nao_deve_conter = caso[5] if len(caso) > 5 else ()
    repo = _novo_repo()
    try:
        _escrever_e_stagear(repo, nome_arquivo, conteudo)
        rc, out, err = _rodar_verificador(repo)
    finally:
        shutil.rmtree(repo, ignore_errors=True)
    problemas = []
    if rc != esperado:
        problemas.append(f"rc={rc} (esperado {esperado})")
    for trecho in deve_conter:
        if trecho not in out:
            problemas.append(f"stdout sem '{trecho}'")
    for trecho in nao_deve_conter:
        if trecho in out:
            problemas.append(f"stdout traz '{trecho}'")
    if problemas:
        detalhe = (
            f"     {'; '.join(problemas)}\n"
            f"     stdout: {out.strip()}\n"
            f"     stderr: {err.strip()}"
        )
        return False, f"FAIL {descricao}\n{detalhe}"
    return True, f"ok   {descricao} (rc={rc})"


def _checar_canon_ausente() -> tuple[bool, str]:
    """Caso 9 (fail-closed, L-36): o verificador copiado para uma arvore SEM
    o no_mdash.py canonico ao lado (tools/hooks/ sem ../hooks/) deve
    REPROVAR (rc diferente de 0) e dizer qual caminho procurou. Antes
    passava calado (rc 0, so um aviso em stderr)."""
    descricao = "verificador sem no_mdash.py canonico deve reprovar e dizer onde procurou"
    base = tempfile.mkdtemp(prefix="selftest-canon-ausente-", dir="/var/tmp")
    try:
        pasta = os.path.join(base, "tools", "hooks")
        os.makedirs(pasta)
        copia = os.path.join(pasta, "no_mdash_staged.py")
        shutil.copyfile(_VERIFICADOR, copia)
        procurado = os.path.normpath(os.path.join(pasta, "..", "hooks", "no_mdash.py"))
        repo = _novo_repo()
        try:
            _escrever_e_stagear(repo, "README.md", f"Texto{EM_DASH} no meio.")
            p = subprocess.run(
                [sys.executable, copia], cwd=repo, capture_output=True, timeout=30,
            )
            rc = p.returncode
            err = p.stderr.decode("utf-8", "replace")
        finally:
            shutil.rmtree(repo, ignore_errors=True)
    finally:
        shutil.rmtree(base, ignore_errors=True)
    problemas = []
    if rc == 0:
        problemas.append("rc=0 (esperado diferente de 0, fail-closed)")
    if procurado not in err:
        problemas.append(f"stderr nao cita o caminho procurado '{procurado}'")
    if problemas:
        return False, f"FAIL {descricao}\n     {'; '.join(problemas)}\n     stderr: {err.strip()}"
    return True, f"ok   {descricao} (rc={rc})"


# Casos S10 a S15 (F3c, HUM-08): excecao de origem do portao de staged.
# A base e a versao no HEAD. Cada caso monta um repositorio com um commit de
# base (hooksPath vazio so nesse commit de montagem) e depois stageia o teste.
_EM = "\u2014"
ORIGEM_BASE = (
    "Inicio do texto.\n"
    + _EM + " um personagem fala.\n"
    + "O narrador " + _EM + " comenta algo.\n"
)
ORIGEM_REESCRITA = (
    "Inicio reescrito.\n"
    + _EM + " um personagem fala, reescrito.\n"
    + "O narrador " + _EM + " comenta algo, de outro modo.\n"
)
ORIGEM_UM_MEIO_A_MAIS = ORIGEM_REESCRITA + "Mais um " + _EM + " aqui.\n"

# (descricao, arquivos do commit de base {caminho: texto}, arquivo staged,
#  texto staged, rc_esperado)
CASOS_ORIGEM = (
    (
        "S10 site/cap.md no HEAD com 2 travessoes; staged com as mesmas contagens: deve passar",
        {"site/cap.md": ORIGEM_BASE},
        "site/cap.md",
        ORIGEM_REESCRITA,
        0,
    ),
    (
        "S11 igual a S10 com um travessao a mais: deve reprovar",
        {"site/cap.md": ORIGEM_BASE},
        "site/cap.md",
        ORIGEM_UM_MEIO_A_MAIS,
        1,
    ),
    (
        "S12 site/cap_humanizado.md novo com contagens <= HEAD site/cap.md: deve passar",
        {"site/cap.md": ORIGEM_BASE},
        "site/cap_humanizado.md",
        ORIGEM_REESCRITA,
        0,
    ),
    (
        "S13 site/x_humanizado.md novo sem site/x.md no HEAD: deve reprovar",
        {"outro.txt": "x\n"},
        "site/x_humanizado.md",
        _EM + " frase.\n",
        1,
    ),
    (
        "S14 site/cap_original.md novo, identico ao site/cap.md do HEAD: deve passar",
        {"site/cap.md": ORIGEM_BASE},
        "site/cap_original.md",
        ORIGEM_BASE,
        0,
    ),
    (
        "S15 troca de classe (inicio da linha para meio) no humanizado: deve reprovar",
        {"site/cap.md": _EM + " um personagem fala.\n"},
        "site/cap_humanizado.md",
        "Frase com " + _EM + " no meio.\n",
        1,
    ),
)


def _checar_origem(caso) -> tuple[bool, str]:
    descricao, base, arquivo, conteudo, esperado = caso
    repo = _novo_repo()
    try:
        for nome, texto in base.items():
            _escrever_e_stagear(repo, nome, texto)
        rc, _, err = _git(
            repo, "-c", "core.hooksPath=/dev/null", "commit", "-q", "-m", "base"
        )
        if rc != 0:
            return False, f"FAIL {descricao}\n     commit de base falhou: {err.strip()}"
        _escrever_e_stagear(repo, arquivo, conteudo)
        rc, out, err = _rodar_verificador(repo)
    finally:
        shutil.rmtree(repo, ignore_errors=True)
    if rc != esperado:
        return False, (
            f"FAIL {descricao}\n     rc={rc} (esperado {esperado})\n"
            f"     stdout: {out.strip()}\n     stderr: {err.strip()}"
        )
    return True, f"ok   {descricao} (rc={rc})"


def main() -> int:
    passou = falhou = 0
    for caso in (*CASOS, *CASOS_CAMINHO, *CASOS_DECLARACAO):
        ok, linha = _checar(caso)
        print(linha)
        if ok:
            passou += 1
        else:
            falhou += 1
    ok, linha = _checar_canon_ausente()
    print(linha)
    if ok:
        passou += 1
    else:
        falhou += 1

    for caso in CASOS_ORIGEM:
        ok, linha = _checar_origem(caso)
        print(linha)
        if ok:
            passou += 1
        else:
            falhou += 1

    print(f"\n{passou} passed / {falhou} failed")
    return 1 if falhou else 0


if __name__ == "__main__":
    sys.exit(main())
