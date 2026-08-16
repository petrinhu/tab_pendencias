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
    fixtures.

CAMADA 3 -- conteudo de arquivo (defesa TERCIARIA, opt-in, mesma fonte de
    termos da CAMADA 2; item LEAK-2). Cobre o vetor que a CAMADA 2 NAO
    cobre: o nome do projeto-fonte real citado dentro do TEXTO de um
    arquivo versionado (comentario, docstring, mensagem de teste) escrito
    por um agente/sessao que tratou o nome como informacao tecnica
    inofensiva -- foi exatamente assim que o incidente LEAK-2 aconteceu
    (5 ocorrencias em comentarios/docstrings de teste, caminho de arquivo
    limpo, conteudo vazando). Nenhuma LINHA de nenhum arquivo versionado
    pode conter, case-insensitive, um dos termos proibidos. A designacao
    correta em texto narrativo (TODO.md, TESTES.md, comentarios) e neutra
    ("consumidor A"/"consumidor B"), nunca o nome real -- por isso esta
    camada nao gera falso positivo com a documentacao legitima do proprio
    guard: a documentacao correta simplesmente nao usa o termo proibido.

IMPORTANTE (o motivo das CAMADAS 2 e 3 serem opt-in por design, nao
    hardcoded): uma lista literal desses nomes DENTRO deste guard seria o
    proprio guard vazando o que deveria proteger -- por isso os termos NUNCA
    sao literais neste arquivo. Eles vem de FORA, por ordem de precedencia:
        1. variavel de ambiente TAB_PENDENCIAS_GUARD_FORBIDDEN_TERMS
           (lista separada por virgula);
        2. arquivo local nao versionado ".guard_forbidden_terms" na raiz do
           repo (um termo por linha, "#" inicia comentario, linhas vazias
           ignoradas) -- ja listado no .gitignore deste repo.
    Se NENHUMA das duas fontes existir (o caso normal em CI/clone publico,
    que nunca tem os nomes reais configurados), as CAMADAS 2 e 3 ficam
    DESLIGADAS e o guard DECLARA isso explicitamente na saida (nunca em
    silencio, e nunca deixando a linha "OK" sozinha sugerir cobertura que
    nao existe) -- a protecao real contra vazamento estrutural continua
    sendo a CAMADA 1, que independe de qualquer configuracao.
    LIMITACAO HONESTA: como os termos so existem na maquina do autor (nunca
    no CI publico, que nao pode conhece-los sem os proprios vazar), as
    CAMADAS 2 e 3 SO protegem localmente, antes do push -- que e justamente
    onde o vazamento e introduzido. Isto e uma escolha correta (a alternativa
    seria commitar os termos, o proprio vazamento que se quer evitar), nao
    uma falha, mas precisa estar escrito para ninguem supor cobertura no CI
    publico que nao ha.
    Auto-referencia: quando a CAMADA 3 acusa um achado, a saida do guard
    reporta apenas arquivo:linha e uma versao MASCARADA do termo (ex.:
    "g*****x"), nunca o termo em claro -- senao o proprio guard, ao relatar
    o problema, seria o vazamento (e pior, em log de CI publico se alguem
    rodar isto la com os termos configurados via env var por engano).

Regra "no silent caps": se uma camada disparar, o guard aponta exatamente
qual (arquivo:linha ou caminho, termo mascarado) e por que; se as CAMADAS
2/3 estiverem desligadas por falta de configuracao, o guard tambem declara
isso de forma inequivoca (nunca falha mudo, nunca deixa "OK" ambiguo).

Uso:
    python3 tools/ci/guard_no_real_fixtures.py

Nao recebe argumentos -- varre TODOS os arquivos rastreados pelo `git`
(`git ls-files`), para garantir que aponta pro estado real do commit, nao
para arquivos untracked/ignorados que o autor ja sabe que nao vao ser
publicados. Exit 0 = limpo; Exit 1 = pelo menos um achado.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

# Ver CAMADA 1 na docstring: 3x a tabela canonica atual (33 linhas de dados),
# ainda 1 ordem de grandeza abaixo das fixtures reais.
LIMITE_LINHAS_DADOS = 100

ENV_TERMOS_PROIBIDOS = "TAB_PENDENCIAS_GUARD_FORBIDDEN_TERMS"
ARQUIVO_TERMOS_LOCAL = ".guard_forbidden_terms"

# CAMADA 4 (Fase 7/8): higiene de path/email em templates e corpus de bus.
# Prefixos POSIX no git ls-files (git normaliza para /).
_HYGIENE_PREFIXES = (
    "templates/",
    "tests/corpus/bus/",
)
_EMAIL_RE = re.compile(r"(?i)\b[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}\b")
_HOME_PATH_RE = re.compile(r"(?i)(?:/home/|\\\\home\\\\|[A-Za-z]:\\\\Users\\\\)")


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
        encoding="utf-8",
        errors="replace",
        check=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def _mask_term(termo: str) -> str:
    """Mascara um termo proibido para relato seguro (nunca reproduz o termo
    em claro na saida do guard -- ver "Auto-referencia" na docstring do
    modulo). Mantem 1o/ultimo caractere como pista de comprimento/formato
    sem reconstituir o termo; termos com 2 caracteres ou menos sao
    mascarados por completo."""
    if len(termo) <= 2:
        return "*" * len(termo)
    return termo[0] + "*" * (len(termo) - 2) + termo[-1]


def _load_forbidden_terms(root: Path) -> tuple[list[str], list[str]]:
    """Carrega os termos proibidos das CAMADAS 2/3 de fora do codigo-fonte.

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
                    f"{rel_path}: caminho contem termo proibido "
                    f"(mascarado) '{_mask_term(termo)}' -- nome de "
                    f"projeto-fonte de fixture real configurado; arquivo "
                    f"nao pode ser versionado com esse nome no caminho."
                )
    return violations


def check_templates_and_bus_hygiene(
    root: Path, tracked: list[str]
) -> list[str]:
    """CAMADA 4: proibe /home/ e emails em templates/ e tests/corpus/bus/.

    Templates de vault e corpus sintetico do bus nao podem carregar path de
    maquina nem endereco de e-mail (vazamento de maquina do autor / PII).
    Barato: so varre prefixos curtos ja versionados.
    """
    violations: list[str] = []
    for rel_path in tracked:
        norm = rel_path.replace("\\", "/")
        if not any(norm.startswith(p) for p in _HYGIENE_PREFIXES):
            continue
        path = root / rel_path
        try:
            text = path.read_text(encoding="utf-8", errors="strict")
        except (UnicodeDecodeError, OSError):
            continue
        for i, line in enumerate(text.split("\n"), start=1):
            if _HOME_PATH_RE.search(line):
                violations.append(
                    f"{rel_path}:{i}: path de maquina (/home/ ou Users) em "
                    f"template/corpus de bus -- use path relativo ao produto "
                    f"(ex.: skills/tab_pendencias/...)."
                )
            if _EMAIL_RE.search(line):
                violations.append(
                    f"{rel_path}:{i}: endereco de e-mail em template/corpus "
                    f"de bus -- remova PII; use designacao neutra."
                )
    return violations


def check_forbidden_content(
    root: Path, tracked: list[str], termos_proibidos: list[str]
) -> list[str]:
    """CAMADA 3 (item LEAK-2): acusa termo proibido dentro do TEXTO de
    qualquer arquivo versionado -- comentario, docstring, mensagem de
    teste. Nunca reproduz o termo em claro na mensagem de achado (so
    arquivo:linha + termo mascarado) para o proprio guard nao virar o
    vazamento que relata. `.guard_forbidden_terms` e sempre excluido do
    escopo (defesa em profundidade -- ele e gitignored e nunca deveria
    aparecer em `tracked`, mas exclui explicitamente mesmo assim)."""
    violations: list[str] = []
    termos_low = [t.lower() for t in termos_proibidos]
    for rel_path in tracked:
        if rel_path == ARQUIVO_TERMOS_LOCAL:
            continue
        path = root / rel_path
        try:
            text = path.read_text(encoding="utf-8", errors="strict")
        except (UnicodeDecodeError, OSError):
            continue  # binario ou ilegivel como texto: fora do escopo
        lines = text.split("\n")
        for i, line in enumerate(lines, start=1):
            line_low = line.lower()
            for termo, termo_low in zip(termos_proibidos, termos_low):
                if termo_low in line_low:
                    violations.append(
                        f"{rel_path}:{i}: linha contem termo proibido "
                        f"(mascarado) '{_mask_term(termo)}' -- nome de "
                        f"projeto-fonte de fixture real configurado; use "
                        f"designacao neutra ('consumidor A'/'consumidor B') "
                        f"em texto narrativo."
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

    termos_proibidos, fontes = _load_forbidden_terms(root)

    violations = check_table_sizes(root, tracked)
    if termos_proibidos:
        violations += check_forbidden_path_names(tracked, termos_proibidos)
        violations += check_forbidden_content(root, tracked, termos_proibidos)
        status_23 = "ATIVA -- fonte(s): " + "; ".join(fontes)
    else:
        status_23 = (
            "DESLIGADA -- nenhum termo configurado (defina "
            f"{ENV_TERMOS_PROIBIDOS} ou crie {ARQUIVO_TERMOS_LOCAL} na raiz "
            "do repo, nunca versionado). A CAMADA 1 (estrutural) continua "
            "ativa independentemente disto."
        )
    camada2_status = status_23
    camada3_status = status_23
    hygiene = check_templates_and_bus_hygiene(root, tracked)
    violations += hygiene
    camada4_status = (
        f"ativa (templates/ + tests/corpus/bus/; "
        f"{len(hygiene)} achado(s) nesta execucao)"
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
        print(f"CAMADA 3 (conteudo): {camada3_status}")
        print(f"CAMADA 4 (templates/bus hygiene): {camada4_status}")
        return 1

    print(
        f"guard_no_real_fixtures: OK -- {len(tracked)} arquivo(s) "
        f"rastreado(s) verificado(s), 0 achado(s)."
    )
    print("CAMADA 1 (tamanho de tabela): ativa (sempre, independe de configuracao).")
    print(f"CAMADA 2 (caminho): {camada2_status}")
    print(f"CAMADA 3 (conteudo): {camada3_status}")
    print(f"CAMADA 4 (templates/bus hygiene): {camada4_status}")
    if not termos_proibidos:
        print(
            "AVISO: CAMADAS 2 e 3 estao DESLIGADAS nesta execucao -- o 'OK' "
            "acima cobre SOMENTE a protecao estrutural (CAMADA 1) e a CAMADA 4 "
            "(templates/bus). Isto e esperado em CI publico/clone fresco "
            "(os termos nunca existem la, de proposito). Na maquina do autor, "
            f"configure {ENV_TERMOS_PROIBIDOS} ou {ARQUIVO_TERMOS_LOCAL} ANTES "
            "de commitar para ativar a protecao completa contra vazamento de "
            "nome de projeto-fonte real, em caminho e em conteudo."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
