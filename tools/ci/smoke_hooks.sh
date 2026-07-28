#!/bin/sh
# tools/ci/smoke_hooks.sh -- smoke test dos shims de tools/hooks/ (CI-1)
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
# Prova, rodando os shims de verdade com `sh` (nao so `shellcheck` estatico),
# o contrato de tools/hooks/_chain.sh: um shim de pass-through (1) sai 0
# quando nao ha hook local do repo (.git/hooks/<nome>), (2) delega e
# PROPAGA o exit code de um hook local presente, e (3) preserva argumentos
# e stdin na delegacao. Job so-Linux (D-11/ADR-1(e): os shims dependem de
# shell POSIX -- no Windows, do shell que vem com o Git for Windows; este
# smoke nao roda no job Windows do CI-1, e o README declara essa
# degradacao).
#
# Uso: sh tools/ci/smoke_hooks.sh
# Exit 0 = todas as asserçoes passaram; Exit 1 = pelo menos uma falhou.

set -eu

SCRIPT_DIR=$(cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(cd -- "$SCRIPT_DIR/../.." && pwd)
HOOKS_SRC="$REPO_ROOT/tools/hooks"

TMPDIR_SMOKE=$(mktemp -d)
cleanup() { rm -rf "$TMPDIR_SMOKE"; }
trap cleanup EXIT INT TERM

fail() {
    echo "FALHA: $1" >&2
    exit 1
}

cd "$TMPDIR_SMOKE"
git init -q .

echo "-- asserçao 1: sem hook local, shim sai 0 --"
if ! sh "$HOOKS_SRC/pre-commit"; then
    fail "pre-commit sem hook local deveria sair 0"
fi
echo "OK"

echo "-- asserçao 2: hook local que falha (exit 7) e propagado --"
printf '#!/bin/sh\nexit 7\n' > .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
set +e
sh "$HOOKS_SRC/pre-commit"
rc=$?
set -e
[ "$rc" -eq 7 ] || fail "esperava exit 7 do hook local, recebi $rc"
echo "OK"

echo "-- asserçao 3: args e stdin preservados na delegaçao --"
# shellcheck disable=SC2016
# '$*'/'$line' sao literais: viram o CONTEUDO do hook local gerado abaixo,
# expandidos quando ELE rodar, nao agora.
printf '#!/bin/sh\necho "args=$*"\nread -r line\necho "stdin=$line"\n' > .git/hooks/commit-msg
chmod +x .git/hooks/commit-msg
out=$(printf 'linha-de-teste\n' | sh "$HOOKS_SRC/commit-msg" arg1 arg2)
case "$out" in
    *"args=arg1 arg2"*) : ;;
    *) fail "argumentos nao preservados -- saida: $out" ;;
esac
case "$out" in
    *"stdin=linha-de-teste"*) : ;;
    *) fail "stdin nao preservado -- saida: $out" ;;
esac
echo "OK"

echo "-- asserçao 4: os 7 shims + _chain.sh parseiam sem erro (sh -n) --"
for shim in _chain.sh pre-commit commit-msg post-merge post-checkout prepare-commit-msg pre-push post-commit; do
    sh -n "$HOOKS_SRC/$shim" || fail "sh -n falhou em $shim"
done
echo "OK"

echo "smoke_hooks: todas as asserçoes passaram."
