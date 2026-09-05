#!/usr/bin/env python3
"""
~/.claude/githooks/selftest_no_mdash_staged.py

PROVA que o portao no_mdash_staged.py fica VERMELHO contra o que deve
barrar (L-36: portao so conta depois de provado vermelho). Monta um
repositorio git descartavel em /var/tmp (nunca /tmp, que e tmpfs nesta
maquina; nunca dentro de um repo real), stageia arquivos e confere o
codigo de saida do verificador.

Casos cobertos:
  1. arquivo user-facing (README.md) com em-dash staged -> exit 1
  2. o mesmo arquivo limpo (sem em-dash/en-dash) staged  -> exit 0
  3. arquivo NAO user-facing (TODO.md) com em-dash staged -> exit 0
  4. arquivo user-facing (README.md) com en-dash staged  -> exit 1
  5. arquivo user-facing (README.md) com en-dash removido -> exit 0

Uso: python3 ~/.claude/githooks/selftest_no_mdash_staged.py
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


def main() -> int:
    passou = falhou = 0
    for descricao, nome_arquivo, conteudo, esperado in CASOS:
        repo = _novo_repo()
        try:
            _escrever_e_stagear(repo, nome_arquivo, conteudo)
            rc, out, err = _rodar_verificador(repo)
            if rc != esperado:
                falhou += 1
                print(f"FAIL {descricao}: rc={rc} (esperado {esperado})")
                print(f"     stdout: {out.strip()}")
                print(f"     stderr: {err.strip()}")
            else:
                passou += 1
                print(f"ok   {descricao} (rc={rc})")
        finally:
            shutil.rmtree(repo, ignore_errors=True)

    print(f"\n{passou} passed / {falhou} failed")
    return 1 if falhou else 0


if __name__ == "__main__":
    sys.exit(main())
