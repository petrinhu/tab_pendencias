#!/bin/sh
# scripts/preci.sh -- pre-CI local (TST-T15)
#
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
#
# Roda LOCALMENTE, na MESMA ORDEM dos jobs de .github/workflows/ci.yml (a
# fonte da verdade deste script -- se o workflow mudar e este script nao
# for atualizado junto, este script fica desatualizado, nao o contrario),
# tudo que da para reproduzir fora do GitHub Actions. Objetivo: o vermelho
# aparecer aqui, na maquina do autor, ANTES do push -- nao so no servidor.
#
# CONTRATO DE EXIT CODE (cuidado explicito do pedido desta fatia):
#   0 = todas as etapas que RODARAM passaram (etapas puladas por ferramenta
#       ausente NAO contam como falha -- ver secao "regra no silent caps"
#       abaixo -- mas ficam bem visiveis no resumo final, nunca misturadas
#       com [PASS]).
#   1 = ERRO DE EXECUCAO deste proprio script (repo nao encontrado, git
#       ausente, python3 ausente, pytest nao instalado -- pre-condicoes que
#       impedem RODAR o pre-CI, nao um resultado de gate).
#   2 = FALHA DE GATE: pelo menos uma etapa que rodou de verdade reprovou
#       (pytest vermelho, guard vermelho, shellcheck/markdownlint/gitleaks
#       com achado). Codigo DIFERENTE de 1 de proposito, para nao confundir
#       "nao rodei" com "rodei e reprovei".
#
# REGRA "NO SILENT CAPS": ferramenta ausente (shellcheck, markdownlint-cli2,
# gitleaks, ruff) nunca vira [PASS] nem fica omitida -- aparece como [SKIP]
# com o motivo, e o resumo final SEMPRE diz quantas etapas foram puladas,
# nunca so "tudo passou" quando na verdade so uma fatia rodou. Este script
# NUNCA instala nada (nem pip, nem npm, nem gerenciador de pacotes de
# sistema) -- so detecta e reporta; instalar e decisao de quem roda.
#
# CROSS-PLATFORM (D-11/ADR-1 secao (e)): este script e `sh` POSIX, mesma
# familia dos shims de tools/hooks/ -- DEGRADACAO DOCUMENTADA no Windows,
# nao suposicao escondida (ver tools/README.md secao "Cross-platform" e
# TESTES.md/TST-T15): roda nativo em Linux/macOS; no Windows requer Git for
# Windows (fornece o `sh`/`bash` usado pelos shims) ou WSL. As etapas de
# A analise estatica dos shims e o smoke deles sao Linux-only mesmo dentro
# do proprio ci.yml (job "shellcheck-and-smoke", comentario "so-Linux,
# declarado") -- este script NAO introduz uma degradacao nova, so herda a
# que ja existe.
#
# Uso:
#   sh scripts/preci.sh
#
# Fixtures reais (opcionais, NUNCA em arquivo versionado -- ver TESTES.md/
# CONTR-1 e AC-REAL/TAB_PENDENCIAS_FIXTURE_A/_B no README):
#   export TAB_PENDENCIAS_FIXTURE_A=/caminho/para/TODO.md-de-consumidor-A
#   export TAB_PENDENCIAS_FIXTURE_B=/caminho/para/TODO.md-de-consumidor-B
#   sh scripts/preci.sh

set -u

# --------------------------------------------------------------------
# Localizacao do repo (mesmo padrao de tools/ci/smoke_hooks.sh: resolve
# via $0, nao assume cwd).
# --------------------------------------------------------------------
SCRIPT_DIR=$(cd -- "$(dirname -- "$0")" && pwd) || {
    echo "ERRO: nao foi possivel resolver o diretorio deste script." >&2
    exit 1
}
REPO_ROOT=$(cd -- "$SCRIPT_DIR/.." && pwd) || {
    echo "ERRO: nao foi possivel resolver a raiz do repo." >&2
    exit 1
}
cd "$REPO_ROOT" || {
    echo "ERRO: nao foi possivel entrar em $REPO_ROOT" >&2
    exit 1
}

if ! command -v git >/dev/null 2>&1; then
    echo "ERRO DE EXECUCAO: git nao encontrado no PATH -- pre-CI nao pode rodar." >&2
    exit 1
fi

PYTHON=""
if command -v python3 >/dev/null 2>&1; then
    PYTHON=python3
elif command -v python >/dev/null 2>&1; then
    PYTHON=python
else
    echo "ERRO DE EXECUCAO: nem python3 nem python encontrados no PATH." >&2
    exit 1
fi

if ! "$PYTHON" -m pytest --version >/dev/null 2>&1; then
    echo "ERRO DE EXECUCAO: pytest nao instalado neste ambiente." >&2
    echo "  Rode: $PYTHON -m pip install -r requirements-dev.txt" >&2
    exit 1
fi

SUMMARY_FILE=$(mktemp) || { echo "ERRO: mktemp falhou." >&2; exit 1; }
NOTES_FILE=$(mktemp) || { echo "ERRO: mktemp falhou." >&2; exit 1; }
# Falso positivo medido nesta versao de shellcheck (0.11.0): so aparece
# quando o script termina com `exit` explicito em TODO ramo do if/elif/else
# final -- shellcheck deixa de creditar `trap cleanup ...` como uso da
# funcao nesse caso especifico (confirmado por bissecao local; o MESMO
# padrao trap+funcao existe, limpo, em tools/ci/smoke_hooks.sh). `cleanup`
# E invocada, via trap, nas 3 saidas (EXIT/INT/TERM).
# shellcheck disable=SC2329
cleanup() { rm -f "$SUMMARY_FILE" "$NOTES_FILE"; }
trap cleanup EXIT INT TERM

GATE_FAILED=0

hr() { printf '%s\n' "------------------------------------------------------------"; }

step_header() {
    printf '\n'
    hr
    printf '%s\n' "$1"
    hr
}

record_pass() { printf '[PASS] %s\n' "$1" >>"$SUMMARY_FILE"; }
record_fail() { printf '[FAIL] %s\n' "$1" >>"$SUMMARY_FILE"; GATE_FAILED=1; }
record_skip() { printf '[SKIP] %s -- %s\n' "$1" "$2" >>"$SUMMARY_FILE"; }
record_info() { printf '[INFO] %s\n' "$1" >>"$SUMMARY_FILE"; }
note() { printf -- '- %s\n' "$1" >>"$NOTES_FILE"; }

printf '%s\n' "pre-CI local (TST-T15) -- espelha .github/workflows/ci.yml"
printf 'Repo: %s\n' "$REPO_ROOT"
printf 'Python: %s (%s)\n' "$PYTHON" "$("$PYTHON" --version 2>&1)"
printf 'SO: %s\n' "$(uname -s 2>/dev/null || echo desconhecido)"

# ======================================================================
# Etapa 1 -- pytest (mirrors o job "test" do ci.yml)
# ======================================================================
step_header "1/6 pytest (tests/)"

if [ -n "${TAB_PENDENCIAS_FIXTURE_A:-}" ] && [ -n "${TAB_PENDENCIAS_FIXTURE_B:-}" ]; then
    printf 'Modo: COM fixtures reais (TAB_PENDENCIAS_FIXTURE_A e _B configuradas)\n'
    printf '  A = %s\n' "$TAB_PENDENCIAS_FIXTURE_A"
    printf '  B = %s\n' "$TAB_PENDENCIAS_FIXTURE_B"
    FIXTURE_MODE="COM fixtures reais (A e B)"
elif [ -n "${TAB_PENDENCIAS_FIXTURE_A:-}" ] || [ -n "${TAB_PENDENCIAS_FIXTURE_B:-}" ]; then
    printf 'Modo: PARCIAL -- so uma das duas fixtures (TAB_PENDENCIAS_FIXTURE_A/_B) esta setada.\n'
    printf '  Os testes que precisam da outra fixture continuam pulando (skip).\n'
    FIXTURE_MODE="PARCIAL (so uma fixture configurada)"
else
    printf 'Modo: SEM fixtures reais (TAB_PENDENCIAS_FIXTURE_A/_B ausentes) -- cobertura\n'
    printf '  REDUZIDA: os testes de contrato com corpus real (TST-T14/CONTR-1) skipam.\n'
    printf '  Ver TESTES.md / TODO.md (AC-REAL) para configurar em maquina de\n'
    printf '  desenvolvedor com acesso aos consumidores reais do lider.\n'
    FIXTURE_MODE="SEM fixtures reais"
fi
printf '\n'

if "$PYTHON" -m pytest tests/ -v; then
    record_pass "pytest tests/ ($FIXTURE_MODE)"
else
    record_fail "pytest tests/ ($FIXTURE_MODE)"
fi
SO_LOCAL=$(uname -s 2>/dev/null || echo desconhecido)
PYVER_LOCAL=$("$PYTHON" --version 2>&1)
note "pytest rodou em 1 ambiente local ($SO_LOCAL/$PYVER_LOCAL), nao nos 5 do ci.yml (job test: ubuntu-latest + windows-latest nativos; job test-distros: debian/fedora/archlinux via container). Reproduzir os 5 requer maquina Windows + runtime de container -- fora do escopo de um script de pre-CI local."

# ======================================================================
# Etapa 2 -- shellcheck + smoke dos shims (mirrors "shellcheck-and-smoke")
# ======================================================================
step_header "2/6 shellcheck + smoke dos shims (so Linux, mesma degradacao do ci.yml)"

SHIM_FILES="tools/hooks/_chain.sh tools/hooks/pre-commit tools/hooks/commit-msg tools/hooks/post-merge tools/hooks/post-checkout tools/hooks/prepare-commit-msg tools/hooks/pre-push tools/hooks/post-commit tools/ci/smoke_hooks.sh"

if command -v shellcheck >/dev/null 2>&1; then
    # $SHIM_FILES e lista de caminhos fixos deste repo, sem espaco/glob a
    # expandir; mesma flag/exclude do ci.yml.
    # shellcheck disable=SC2086
    if shellcheck --exclude=SC1091 $SHIM_FILES; then
        record_pass "shellcheck (_chain.sh + 7 shims + smoke_hooks.sh)"
    else
        record_fail "shellcheck (_chain.sh + 7 shims + smoke_hooks.sh)"
    fi
else
    record_skip "shellcheck" "nao encontrado no PATH -- instale o pacote 'shellcheck' da sua distro (nao instalado automaticamente por este script)"
fi

printf '\n'
if sh tools/ci/smoke_hooks.sh; then
    record_pass "smoke dos shims (sh tools/ci/smoke_hooks.sh)"
else
    record_fail "smoke dos shims (sh tools/ci/smoke_hooks.sh)"
fi

# ======================================================================
# Etapa 3 -- lint de Markdown (mirrors "markdown-lint")
# ======================================================================
step_header "3/6 lint de Markdown (markdownlint-cli2)"

MDLINT_CMD=""
if command -v markdownlint-cli2 >/dev/null 2>&1; then
    MDLINT_CMD="markdownlint-cli2"
elif command -v npx >/dev/null 2>&1 && npx --no-install markdownlint-cli2 --version >/dev/null 2>&1; then
    MDLINT_CMD="npx --no-install markdownlint-cli2"
fi

if [ -n "$MDLINT_CMD" ]; then
    # Mesmo glob do job do ci.yml (globs: "**/*.md"); o ignore de
    # tests/corpus/** vem do .markdownlint-cli2.yaml na raiz (auto-descoberto).
    if $MDLINT_CMD "**/*.md"; then
        record_pass "markdownlint-cli2 (**/*.md)"
    else
        record_fail "markdownlint-cli2 (**/*.md)"
    fi
else
    record_skip "markdownlint-cli2" "nao encontrado (nem binario global, nem cache local de 'npx markdownlint-cli2') -- instale com 'npm i -g markdownlint-cli2', ou rode 'npx markdownlint-cli2 --version' uma vez com rede disponivel para popular o cache"
fi

# ======================================================================
# Etapa 4 -- gitleaks (mirrors "secrets-scan")
# ======================================================================
step_header "4/6 gitleaks (secrets no historico completo)"

if command -v gitleaks >/dev/null 2>&1; then
    if gitleaks detect --source . --no-banner; then
        record_pass "gitleaks detect (historico completo)"
    else
        record_fail "gitleaks detect (historico completo)"
    fi
else
    record_skip "gitleaks" "nao encontrado no PATH -- instale o binario 'gitleaks' (nao instalado automaticamente por este script)"
fi
note "gitleaks nao faz parte da lista original pedida para esta fatia, mas o job secrets-scan existe no ci.yml e a ferramenta estava disponivel nesta maquina -- incluido para nao aproximar a cobertura (cuidado 4 do pedido). Nesta execucao local a acao nao comenta em PR (precisaria de permissao pull-requests:write, que o workflow tambem nao concede); o gate real (falhar se achar segredo) e identico."

# ======================================================================
# Etapa 5 -- guards do produto (mirrors "guards")
# ======================================================================
step_header "5/6 guards (stdlib + anti-vazamento de fixture real)"

if "$PYTHON" tools/ci/guard_stdlib_imports.py tools; then
    record_pass "guard_stdlib_imports.py tools"
else
    record_fail "guard_stdlib_imports.py tools"
fi

printf '\n'
if "$PYTHON" tools/ci/guard_no_real_fixtures.py; then
    record_pass "guard_no_real_fixtures.py"
else
    record_fail "guard_no_real_fixtures.py"
fi

# ======================================================================
# Etapa 6 -- ruff (EXTRA, fora do ci.yml -- NUNCA gate, so informativo)
# ======================================================================
step_header "6/6 ruff -- lint de Python (EXTRA: nao existe job de ruff no ci.yml hoje)"

if command -v ruff >/dev/null 2>&1; then
    if ruff check tools/; then
        record_info "ruff check tools/ (0 achado -- nao bloqueia; nao e gate do ci.yml)"
    else
        record_info "ruff check tools/ (achados acima -- NAO BLOQUEIA; nao ha ruff.toml/pyproject.toml commitado no repo, e o ci.yml nao roda ruff hoje, entao isto e informativo, nao um gate confirmado pelo projeto)"
    fi
else
    record_skip "ruff" "nao encontrado no PATH -- etapa informativa, sem efeito no exit code mesmo se estivesse presente"
fi
note "ruff e citado em TESTES.md (TST-T2 e na propria descricao de TST-T15) mas NAO e um job do ci.yml e NAO ha config (ruff.toml/pyproject.toml) commitada definindo quais regras o projeto de fato adota -- por isso roda aqui so como INFO, nunca como FAIL. Decisao de tornar isto um gate real e do lider (qual config, e se quer abrir TST-T2 como item proprio), nao deste script."
note "TESTES.md (secao TST-T15) tambem menciona um 'check de consistencia README x SKILL.md' que NAO existe hoje como job do ci.yml nem como script em tools/ -- nao foi inventado aqui (seria uma decisao de design nova, fora do escopo de 'espelhar o CI existente'). TESTES.md foi atualizado nesta fatia para descrever o que este script FAZ de fato, nao o que a versao antiga do texto aspirava."

# ======================================================================
# Resumo final
# ======================================================================
printf '\n'
hr
printf '%s\n' "RESUMO"
hr
cat "$SUMMARY_FILE"

# grep -c ja imprime "0" (com exit 1) quando nao ha match -- SEM fallback
# `|| echo 0` aqui: o fallback dispararia JUNTO com a saida do proprio
# grep -c (exit 1 != erro de leitura), duplicando a contagem (achado ao
# rodar o script de verdade, ver relatorio desta fatia).
N_PASS=$(grep -c '^\[PASS\]' "$SUMMARY_FILE")
N_FAIL=$(grep -c '^\[FAIL\]' "$SUMMARY_FILE")
N_SKIP=$(grep -c '^\[SKIP\]' "$SUMMARY_FILE")
N_INFO=$(grep -c '^\[INFO\]' "$SUMMARY_FILE")

printf '\n'
printf 'Contagem: %s passou/passaram, %s falhou/falharam, %s pulada(s), %s informativa(s)\n' \
    "$N_PASS" "$N_FAIL" "$N_SKIP" "$N_INFO"

printf '\n'
hr
printf '%s\n' "DIFERENCAS DECLARADAS vs .github/workflows/ci.yml (nao aproximado, ver cuidado 4)"
hr
cat "$NOTES_FILE"

printf '\n'
hr
if [ "$GATE_FAILED" -eq 1 ]; then
    printf '%s\n' "RESULTADO: FALHA DE GATE -- pelo menos uma etapa reprovou (ver [FAIL] acima)."
    hr
    exit 2
elif [ "$N_SKIP" -gt 0 ]; then
    printf '%s\n' "RESULTADO: CONCLUIDO COM RESSALVAS -- $N_SKIP etapa(s) pulada(s) por ferramenta ausente."
    printf '%s\n' "Isto NAO e 'tudo passou': a cobertura desta execucao e MENOR que a do ci.yml."
    hr
    exit 0
else
    printf '%s\n' "RESULTADO: TUDO PASSOU (nenhuma etapa pulada nesta maquina)."
    hr
    exit 0
fi
