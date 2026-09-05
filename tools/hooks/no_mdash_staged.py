#!/usr/bin/env python3
"""
~/.claude/githooks/no_mdash_staged.py

Portao de pre-commit GLOBAL (core.hooksPath) contra em-dash (U+2014) e
en-dash (U+2013) em conteudo staged user-facing. Fecha o buraco que o
hook PreToolUse ~/.claude/hooks/no_mdash.py nao cobre: escrita feita por
Bash (sed -i, python -c, heredoc) nao passa pelas tools Write/Edit/
MultiEdit, entao chega ao commit sem revisao.

Fonte de verdade UNICA da definicao de "user-facing": a funcao
is_user_facing() de ~/.claude/hooks/no_mdash.py, importada aqui (nunca
copiada). O escopo dessa funcao nao e alterado por este arquivo.

Le o CONTEUDO STAGED (git show :<arquivo>), nao a working tree, porque
so o staged e o que vai de fato para o commit.

Contrato de saida:
  - exit 0: nada encontrado, ou nenhum candidato user-facing staged.
  - exit 1: em-dash/en-dash encontrado em algum candidato, OU a analise
    de algum candidato falhou (git show quebrou) -- ambos contam como
    reprovacao, nunca sucesso silencioso.
  - exit 0 com aviso em stderr: SO quando o ambiente nao tem git, ou o
    no_mdash.py de referencia nao existe no disco. Fail-open documentado,
    nunca fail-open em silencio.

Uso: chamado pelo shim ~/.claude/githooks/pre-commit ANTES do source de
_chain.sh (que usa exec e substitui o processo, entao nada depois dele
roda).
"""
import importlib.util
import os
import subprocess
import sys

_AQUI = os.path.dirname(os.path.abspath(__file__))
_NO_MDASH_PATH = os.path.normpath(
    os.path.join(_AQUI, "..", "hooks", "no_mdash.py")
)


def _carregar_no_mdash():
    """Importa a funcao is_user_facing (e os pedacos que a acompanham) do
    modulo canonico no_mdash.py, por caminho absoluto explicito -- nao
    depende do cwd de onde o commit foi disparado."""
    if not os.path.isfile(_NO_MDASH_PATH):
        return None
    spec = importlib.util.spec_from_file_location(
        "no_mdash_canonico", _NO_MDASH_PATH
    )
    if spec is None or spec.loader is None:
        return None
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _arquivos_staged(repo_root: str) -> list[str]:
    """Lista arquivos staged do commit (Added/Copied/Modified/Renamed),
    -z para tolerar nome com espaco ou caractere especial."""
    p = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z"],
        cwd=repo_root, capture_output=True, timeout=30,
    )
    saida = p.stdout
    if not saida:
        return []
    return [os.fsdecode(b) for b in saida.split(b"\x00") if b]


def _conteudo_staged(repo_root: str, caminho: str) -> str:
    """Le o conteudo STAGED (index), nao a working tree."""
    p = subprocess.run(
        ["git", "show", f":{caminho}"],
        cwd=repo_root, capture_output=True, timeout=30,
    )
    if p.returncode != 0:
        raise RuntimeError(
            f"git show :{caminho} saiu {p.returncode}: "
            f"{p.stderr.decode('utf-8', 'replace').strip()}"
        )
    return p.stdout.decode("utf-8", "replace")


def main() -> int:
    if not any(
        os.access(os.path.join(d, "git"), os.X_OK)
        for d in os.environ.get("PATH", "").split(os.pathsep)
        if d
    ):
        print(
            "no_mdash_staged: git nao encontrado no PATH; portao "
            "desativado (fail-open documentado).",
            file=sys.stderr,
        )
        return 0

    modulo = _carregar_no_mdash()
    if modulo is None:
        print(
            f"no_mdash_staged: nao encontrei o modulo canonico em "
            f"{_NO_MDASH_PATH}; portao desativado (fail-open documentado).",
            file=sys.stderr,
        )
        return 0

    p = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True, timeout=30,
    )
    if p.returncode != 0:
        print(
            "no_mdash_staged: nao estou dentro de um repositorio git; "
            "portao desativado (fail-open documentado).",
            file=sys.stderr,
        )
        return 0
    repo_root = p.stdout.decode("utf-8", "replace").strip()

    candidatos = [
        f for f in _arquivos_staged(repo_root) if modulo.is_user_facing(f)
    ]
    encontrados = len(candidatos)
    analisados = 0
    falharam = 0
    violacoes = []

    for caminho in candidatos:
        try:
            conteudo = _conteudo_staged(repo_root, caminho)
        except Exception as e:
            falharam += 1
            print(f"no_mdash_staged: falha ao analisar {caminho}: {e}", file=sys.stderr)
            continue
        analisados += 1

        limpo = modulo.strip_urls(conteudo)
        n_em = limpo.count(modulo.EM_DASH)
        n_en = limpo.count(modulo.EN_DASH)
        if n_em or n_en:
            violacoes.append((caminho, n_em, n_en))

    print(f"encontrados={encontrados} analisados={analisados} falharam={falharam}")

    if analisados + falharam != encontrados:
        print(
            "no_mdash_staged: divergencia de contagem (analisados+falharam != "
            "encontrados) -- varredura quebrada, tratando como reprovacao.",
            file=sys.stderr,
        )
        return 1

    if not violacoes and falharam == 0:
        return 0

    if violacoes:
        linhas = ["Commit bloqueado: texto user-facing staged contem pontuacao"]
        linhas.append(
            "tipica de IA generativa (em-dash/en-dash). Reescreva substituindo por:"
        )
        linhas.append("  - virgula em pausas curtas (ex.: 'Texto, explicacao')")
        linhas.append(
            "  - ponto-e-virgula entre clausulas independentes (ex.: 'A; B')"
        )
        linhas.append("  - dois pontos antes de explicacao (ex.: 'Texto: explicacao')")
        linhas.append("  - parenteses para apartes (ex.: 'Texto (aparte)')")
        linhas.append("  - hifen simples (-) para compostos e ranges (ex.: '1990-2000')")
        linhas.append("")
        for caminho, n_em, n_en in violacoes:
            partes = []
            if n_em:
                partes.append(f"em-dash (U+2014): {n_em} ocorrencia(s)")
            if n_en:
                partes.append(f"en-dash (U+2013): {n_en} ocorrencia(s)")
            linhas.append(f"  {caminho}: " + " | ".join(partes))
        print("\n".join(linhas), file=sys.stderr)

    return 1


if __name__ == "__main__":
    sys.exit(main())
