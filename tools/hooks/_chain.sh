#!/bin/sh
# tools/hooks/_chain.sh
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
# Delega ao hook LOCAL do repo (.git/hooks/<nome>) que um core.hooksPath GLOBAL
# sombreia. Sem isto, definir core.hooksPath global desativaria silenciosamente
# os hooks proprios de cada repo (git-lfs, framework pre-commit, husky, etc.).
#
# E "sourced" pelos shims de pass-through (pre-commit, pre-push, ...). Usa o
# basename do hook chamador, acha o hook local pelo --git-common-dir (correto
# tambem em worktrees; NUNCA usa --git-path hooks, que devolveria o proprio dir
# global e causaria loop). Preserva args, stdin e exit code via exec, entao um
# hook local que BLOQUEIA (ex: pre-commit que falha) continua bloqueando.
__name=$(basename "$0")
__gd=$(git rev-parse --git-common-dir 2>/dev/null) || exit 0
__local="$__gd/hooks/$__name"
[ -x "$__local" ] && exec "$__local" "$@"
exit 0
