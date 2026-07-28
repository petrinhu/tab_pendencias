#!/usr/bin/env python3
# tools/ci/guard_no_real_fixtures.py -- guard anti-vazamento de fixture real (CI-1)
# Copyright (C) 2026 Petrus Silva Costa
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.
"""
tools/ci/guard_no_real_fixtures.py

Guard de CI (item CI-1 do TODO.md): este repo e PUBLICO e as fixtures de
aceitacao vindas de projetos reais do lider (dois consumidores vivos --
ver TODO.md/CONTR-1/AC-REAL, TESTES.md) tem que permanecer SOMENTE LOCAIS.
Nunca commitadas, nem anonimizadas.

Criterio declarado (duas camadas independentes, cada uma verificavel sem
depender de vocabulario/idioma do conteudo livre):

CAMADA 1 -- estrutural, por TAMANHO de tabela GFM (defesa PRIMARIA, sempre
    ativa, nao depende de nenhum dado externo). Uma fixture real tem centenas
    de linhas de dados (ordem de grandeza medida: dezenas a centenas -- ver
    TODO.md/CONTR-1); a tabela canonica deste proprio repo (TODO.md) tem hoje
    33; exemplos sinteticos usados em teste (ex.: tests/test_todo_fixes.py,
    corpus de CORP-0) sao de poucas linhas por desenho (existem para
    exercitar um caso, nao para serem um TODO.md inteiro). Qualquer bloco
    contiguo de tabela GFM (linhas que comecam com `|` e terminam com `|`)
    com mais de LIMITE_LINHAS_DADOS linhas de dados (excluindo cabecalho e
    separador `:---`) e tratado como fixture real vazada, em QUALQUER
    arquivo versionado, sem allowlist por nome de arquivo -- deliberado: um
    allowlist por caminho e a mesma classe de excecao friavel que este
    projeto ja rejeitou em outros guards (ADR-1). Threshold com folga grande
    (o triplo da tabela canonica atual) para nao gerar falso positivo com o
    crescimento organico do proprio TODO.md, e ainda assim uma ordem de
    grandeza abaixo das fixtures reais.

CAMADA 2 -- caminho de arquivo (defesa SECUNDARIA, opt-in, cobre o vetor
    mais comum de acidente: alguem larga o arquivo com o nome original do
    projeto-fonte). Nenhum CAMINHO versionado pode conter, case-insensitive,
    um dos termos proibidos -- os nomes dos projetos-fonte reais das
    fixtures. IMPORTANTE (o motivo desta camada ser opt-in por design, nao
    hardcoded): uma lista literal desses nomes DENTRO deste guard seria o
    proprio guard vazando o que deveria proteger -- por isso os termos NUNCA
    sao literais neste arquivo. Eles vem de FORA, por ordem de precedencia:
        1. variavel de ambiente TAB_PENDENCIAS_GUARD_FORBIDDEN_PATH_TERMS
           (lista separada por virgula);
        2. arquivo local nao versionado ".guard_forbidden_terms" na raiz do
           repo (um termo por linha, "#" inicia comentario, linhas vazias
           ignoradas) -- ja listado no .gitignore deste repo.
    Se NENHUMA das duas fontes existir (o caso normal em CI/clone publico,
    que nunca tem os nomes reais configurados), a CAMADA 2 fica DESLIGADA e
    o guard DECLARA isso explicitamente na saida (nunca em silencio) -- a
    protecao real contra vazamento estrutural continua sendo a CAMADA 1,
    que independe de qualquer configuracao.
    Esta camada e checada no CAMINHO, nunca no CONTEUDO: o conteudo (docs
    narrativos como TODO.md, TESTES.md) MENCIONA os projetos-fonte por
    designacao neutra ("consumidor A"/"consumidor B") -- e a documentacao
    correta do porque este guard existe, nao vazamento. Um grep de conteudo
    daria falso positivo inclusive dentro deste projeto (comentario citando
    um nome de arquivo de exemplo com pipe escapado, por exemplo -- nao e
    fixture, e narrativa). Checar o CAMINHO em vez do conteudo evita essa
    classe de falso positivo por construcao.

Regra "no silent caps": se uma camada disparar, o guard aponta exatamente
qual (arquivo:linha ou caminho) e por que; se a CAMADA 2 estiver desligada
por falta de configuracao, o guard tambem declara isso, nunca falha mudo.

Uso:
    python3 tools/ci/guard_no_real_fixtures.py

Nao recebe argumentos -- varre TODOS os arquivos rastreados pelo `git`
(`git ls-files`), para garantir que aponta pro estado real do commit, nao
para arquivos untracked/ignorados que o autor ja sabe que nao vao ser
publicados. Exit 0 = limpo; Exit 1 = pelo menos um achado.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

# Ver CAMADA 1 na docstring: 3x a tabela canonica atual (33 linhas de dados),
# ainda 1 ordem de grandeza abaixo das fixtures reais.
LIMITE_LINHAS_DADOS = 100

ENV_TERMOS_PROIBIDOS = "TAB_PENDENCIAS_GUARD_FORBIDDEN_PATH_TERMS"
ARQUIVO_TERMOS_LOCAL = ".guard_forbidden_terms"


def _is_table_row(line: str) -> bool:
    s = line.strip()
    return s.startswith("|") and s.endswith("|") and len(s) >= 2


def _is_separator_row(line: str) -> bool:
    """Linha tipo `| :--- | :--- |` -- separador de cabecalho GFM, nao dado."""
    s = line.strip().strip("|")
    cells = [c.strip() for c in s.split("|")]
    if not cells:
        return False
    return all(c and set(c) <= set(":- ") for c in cells)


def _git_ls_files(root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def _load_forbidden_path_terms(root: Path) -> tuple[list[str], list[str]]:
    """Carrega os termos proibidos de CAMADA 2 de fora do codigo-fonte.

    Devolve (termos, fontes_usadas) -- fontes_usadas e uma lista de strings
    descrevendo de onde cada termo veio, para o guard declarar explicitamente
    (nunca em silencio) o que estava ativo nesta execucao.
    """
    termos: list[str] = []
    fontes: list[str] = []

    env_val = os.environ.get(ENV_TERMOS_PROIBIDOS, "").strip()
    if env_val:
        env_termos = [t.strip() for t in env_val.split(",") if t.strip()]
        termos.extend(env_termos)
        fontes.append(f"variavel de ambiente {ENV_TERMOS_PROIBIDOS} ({len(env_termos)} termo(s))")

    arquivo_local = root / ARQUIVO_TERMOS_LOCAL
    if arquivo_local.is_file():
        linhas = arquivo_local.read_text(encoding="utf-8").splitlines()
        arquivo_termos = []
        for linha in linhas:
            s = linha.strip()
            if not s or s.startswith("#"):
                continue
            arquivo_termos.append(s)
        termos.extend(arquivo_termos)
        fontes.append(f"arquivo local {ARQUIVO_TERMOS_LOCAL} ({len(arquivo_termos)} termo(s))")

    # dedup preservando ordem
    vistos = set()
    unicos = []
    for t in termos:
        low = t.lower()
        if low not in vistos:
            vistos.add(low)
            unicos.append(t)
    return unicos, fontes


def check_table_sizes(root: Path, tracked: list[str]) -> list[str]:
    violations: list[str] = []
    for rel_path in tracked:
        path = root / rel_path
        try:
            text = path.read_text(encoding="utf-8", errors="strict")
        except (UnicodeDecodeError, OSError):
            continue  # binario ou ilegivel como texto: fora do escopo deste guard
        lines = text.split("\n")
        block_start = None
        data_rows = 0
        header_seen_in_block = False

        def _flush(end_idx: int):
            nonlocal block_start, data_rows, header_seen_in_block
            if block_start is not None and data_rows > LIMITE_LINHAS_DADOS:
                violations.append(
                    f"{rel_path}:{block_start}-{end_idx}: bloco de tabela GFM com "
                    f"{data_rows} linha(s) de dados (limite {LIMITE_LINHAS_DADOS}) -- "
                    f"tamanho compativel com fixture real de consumidor vivo do "
                    f"lider, nao com corpus sintetico ou com a tabela canonica "
                    f"deste repo."
                )
            block_start = None
            data_rows = 0
            header_seen_in_block = False

        for i, line in enumerate(lines, start=1):
            if _is_table_row(line):
                if block_start is None:
                    block_start = i
                if _is_separator_row(line):
                    header_seen_in_block = True
                    continue
                if header_seen_in_block or block_start != i:
                    # linha de dados (ja passou do cabecalho, ou e a 2a+ linha
                    # do bloco sem separador reconhecido -- conta como dado)
                    data_rows += 1
                # senao: e a 1a linha do bloco (provavel cabecalho), nao conta
            else:
                _flush(i - 1)
        _flush(len(lines))
    return violations


def check_forbidden_path_names(tracked: list[str], termos_proibidos: list[str]) -> list[str]:
    violations = []
    for rel_path in tracked:
        low = rel_path.lower()
        for termo in termos_proibidos:
            if termo.lower() in low:
                violations.append(
                    f"{rel_path}: caminho contem '{termo}' -- termo proibido "
                    f"configurado (nome de projeto-fonte de fixture real); "
                    f"arquivo nao pode ser versionado com esse nome."
                )
    return violations


def main(argv: list[str]) -> int:
    if argv:
        print("ERRO: este guard nao aceita argumentos (varre git ls-files).", file=sys.stderr)
        return 1

    root = Path.cwd()
    try:
        tracked = _git_ls_files(root)
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        print(f"ERRO: nao foi possivel rodar 'git ls-files' em {root}: {exc}", file=sys.stderr)
        return 1

    termos_proibidos, fontes = _load_forbidden_path_terms(root)

    violations = check_table_sizes(root, tracked)
    if termos_proibidos:
        violations += check_forbidden_path_names(tracked, termos_proibidos)
        camada2_status = "ATIVA -- fonte(s): " + "; ".join(fontes)
    else:
        camada2_status = (
            "DESLIGADA -- nenhum termo configurado (defina "
            f"{ENV_TERMOS_PROIBIDOS} ou crie {ARQUIVO_TERMOS_LOCAL} na raiz "
            "do repo, nunca versionado). A CAMADA 1 (estrutural) continua "
            "ativa independentemente disto."
        )

    if violations:
        print(f"guard_no_real_fixtures: {len(violations)} achado(s):\n")
        for v in violations:
            print(f"  {v}")
        print(
            "\nFixtures reais (consumidores vivos do lider) sao SOMENTE LOCAIS -- "
            "ver TODO.md (CONTR-1/AC-REAL) e TESTES.md. Se isto e um falso "
            "positivo (ex.: a propria tabela canonica cresceu organicamente "
            "alem do limite), ajuste LIMITE_LINHAS_DADOS neste guard e declare "
            "o motivo no commit; nao adicione allowlist por nome de arquivo."
        )
        print(f"\nCAMADA 2 (caminho): {camada2_status}")
        return 1

    print(f"guard_no_real_fixtures: OK -- {len(tracked)} arquivo(s) rastreado(s) verificado(s).")
    print(f"CAMADA 2 (caminho): {camada2_status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
