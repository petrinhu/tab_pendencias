#!/usr/bin/env python3
# tools/submodule_pin_drift.py -- detector de drift do pin de submodulo git
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
tools/submodule_pin_drift.py

Detector READ-ONLY, offline-first e warn-only de drift entre o SHA de um
submodulo git PINADO na arvore do superprojeto (o gitlink gravado no commit,
NAO o que porventura esteja em checkout) e a ultima release/tag conhecida no
remoto (e, opcionalmente, a ponta de um branch).

Nasceu de um incidente medido (TAB-SOT-007, 16/08/26): o gitlink de um
submodulo consumidor apontava para um commit 67 commits atras da tag
publicada mais recente -- ninguem percebeu ate alguem medir a mao. Um
`git clone --recursive` nesse estado restaura um consumidor com o pin velho,
em silencio.

--- AGN-1: agnostico a projeto (CLAUDE.md do projeto, requisito canonico) ---

Nenhum nome de projeto, caminho de maquina ou suposicao de esquema esta
embutido aqui. O caminho do submodulo (`--path`) e a URL do remoto (`--url`)
sao SEMPRE parametros; quando `--url` nao e dado, a UNICA fonte de fallback e
o proprio `.gitmodules` do superprojeto (mecanismo padrao do git, nao
convencao de nenhum projeto especifico).

--- Por que "read-only" aqui tambem exclui `git fetch` -----------------------

Mesma politica de `checks/chk_frescor.py` (CHK-09): consultar o remoto via
`git ls-remote` NUNCA grava nada local (nem refs remote-tracking); `git
fetch` grava, e por isso nunca e usado. Consequencia direta: a contagem
EXATA de commits de atraso (`commits_behind`) so e calculavel quando os
objetos do submodulo JA estao disponiveis localmente (checkout previo) --
caso contrario o campo fica `None` com o motivo explicito, nunca um numero
adivinhado. `git submodule update --remote`, auto-commit e auto-push sao
proibidos em qualquer caminho deste modulo; a unica saida com efeito e a
leitura (stdout) e o exit code -- este ultimo e SINAL, quem decide se
bloqueia um pipeline e o job de CI que consome esta ferramenta.

--- Por que "sem rede" nunca vira "OK" ---------------------------------------

Quando `git ls-remote` falha (sem rede, remoto inalcancavel, timeout) ou
quando o remoto nao tem nenhuma tag no formato `vX.Y.Z` (nada para comparar),
o `status` do relatorio e sempre `nao_verificavel` -- NUNCA `atualizado`. Um
detector que declara frescor sem ter conseguido consultar nada e pior que
nenhum detector (ver docstring do modulo/prompt da fatia).

--- Contrato de exit code (D-6/CLI-1, mesma familia dos irmaos do toolkit) ---

0 = `status == atualizado` (pin confirmado contra o remoto); 1 = erro de
execucao (path invalido, `.gitmodules` sem URL resolvivel, flag desconhecida
etc.); 2 = `status in (desatualizado, nao_verificavel)` -- o campo `status`
no relatorio distingue drift confirmado de incapacidade de verificar.
"""
import argparse
import os
import re
import subprocess
import sys

import todo_lib as L

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


class _Parser(argparse.ArgumentParser):
    """Contrato de exit code (D-6/CLI-1): erro de parsing (flag desconhecida,
    `--path` obrigatorio ausente) sai 1 ('erro de execucao'), nunca o exit
    code default do argparse."""

    def error(self, message):
        self.print_usage(sys.stderr)
        self.exit(1, f"{self.prog}: error: {message}\n")


def _build_parser():
    p = _Parser(
        prog="submodule_pin_drift.py",
        description=(
            "Detector read-only, offline-first e warn-only de drift entre o "
            "SHA de submodulo PINADO na arvore do superprojeto (o gitlink, "
            "nao o que esta no checkout) e a ultima release/tag conhecida no "
            "remoto. Nunca muta nada (sem 'submodule update --remote', sem "
            "commit/push, sem 'git fetch'); sem rede, declara capacidade "
            "limitada em vez de fingir frescor."
        ),
        epilog=(
            "Exit codes: 0 = pin em dia (confirmado contra o remoto); "
            "1 = erro de execucao (path invalido / .gitmodules sem URL "
            "resolvivel / flag desconhecida); 2 = drift detectado OU nao "
            "verificavel (sem rede, ou sem tag semver no remoto) -- o campo "
            "'status' no relatorio distingue os dois casos. Sinal, nao "
            "bloqueio: quem decide se isto falha um pipeline e o job de CI "
            "que consome esta ferramenta."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--path", required=True,
        help="Caminho do submodulo dentro do superprojeto, relativo a raiz "
             "do repo (ex.: skills/tab_pendencias). Sempre um parametro -- "
             "nenhum caminho vem embutido no codigo (AGN-1).")
    p.add_argument(
        "--root", default=None,
        help="Raiz do superprojeto. Default: descoberta via "
             "'git rev-parse --show-toplevel' a partir do cwd.")
    p.add_argument(
        "--url", default=None,
        help="URL do remoto do submodulo. Default: resolvida em "
             ".gitmodules na raiz do superprojeto (chave "
             "submodule.<nome>.url da secao cujo 'path' bate com --path).")
    p.add_argument(
        "--branch", default=None,
        help="Nome de branch do remoto a comparar tambem contra o pin, alem "
             "da ultima tag semver (opcional).")
    p.add_argument(
        "--timeout", type=int, default=10,
        help="Timeout em segundos para cada chamada git (default: 10).")
    p.add_argument(
        "-v", "--verbose", action="store_true",
        help="Imprime as notas de diagnostico completas mesmo quando o "
             "status e 'atualizado' (default: notas so aparecem quando ha "
             "algo a explicar).")
    return p


# ------------------------------- git helpers (read-only) --------------------

def _git(cwd, args, timeout):
    """(ok, saida_ou_erro) -- nunca lanca excecao; nunca chama subcomando que
    muta estado local (sem commit/checkout/branch/reset/submodule
    update/fetch -- mesma politica de checks/chk_frescor.py)."""
    try:
        r = subprocess.run(["git", *args], cwd=cwd, capture_output=True,
                           text=True, timeout=timeout)
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"
    if r.returncode != 0:
        msg = (r.stderr or r.stdout or "").strip()
        return False, msg or f"git {' '.join(args)} falhou (rc={r.returncode})"
    return True, r.stdout


def _to_pathspec(path):
    """Normaliza separador para '/' -- git sempre quer pathspec com barra,
    independente do SO que informou --path (Windows pode chegar com '\\')."""
    return path.replace("\\", "/").strip().strip("/")


# ------------------------------- pinned_sha (arvore, nao checkout) ----------

def get_pinned_sha(root, submodule_path, ref="HEAD", timeout=10):
    """(sha_ou_None, motivo_ou_None). Le o gitlink (mode 160000) gravado na
    ARVORE de `ref` -- funciona mesmo se o submodulo nunca foi inicializado
    (sem checkout local), que e exatamente o caso do incidente medido: um
    `git clone` sem `--recursive` nao tem `submodule_path/` no disco, mas o
    pin ja esta la na arvore do commit."""
    pathspec = _to_pathspec(submodule_path)
    ok, out = _git(root, ["ls-tree", ref, "--", pathspec], timeout)
    if not ok:
        return None, f"'git ls-tree {ref} -- {pathspec}' falhou: {out}"
    line = out.strip()
    if not line:
        return None, (f"'{pathspec}' nao encontrado na arvore de {ref} "
                      "(caminho errado, ou nao e um submodulo)")
    parts = line.split(None, 3)
    if len(parts) < 3:
        return None, f"saida inesperada de 'git ls-tree': {line!r}"
    mode, otype, sha = parts[0], parts[1], parts[2]
    if mode != "160000" or otype != "commit":
        return None, (f"'{pathspec}' nao e um gitlink de submodulo "
                      f"(mode={mode}, type={otype})")
    return sha, None


# ------------------------------- URL via .gitmodules ------------------------

def resolve_url_from_gitmodules(root, submodule_path, timeout=10):
    """(url_ou_None, motivo_ou_None). Unico fallback quando --url nao e
    passado -- le a secao do `.gitmodules` cujo 'path' bate com
    `submodule_path` e devolve a chave 'url' dessa MESMA secao (o nome da
    secao e arbitrario por design do git; nunca assumimos que 'nome da
    secao' == 'path')."""
    gm = os.path.join(root, ".gitmodules")
    if not os.path.isfile(gm):
        return None, f"'.gitmodules' nao encontrado em {root!r}"
    ok, out = _git(root, ["config", "-f", ".gitmodules", "--get-regexp",
                          r"^submodule\..*\.path$"], timeout)
    if not ok or not out.strip():
        return None, ("nao foi possivel ler secoes de submodulo em "
                      ".gitmodules ('git config --get-regexp' falhou ou "
                      "nao encontrou nenhuma)")
    target = _to_pathspec(submodule_path)
    name = None
    for line in out.strip().splitlines():
        key, _, value = line.partition(" ")
        if _to_pathspec(value.strip()) == target:
            # key = "submodule.<nome>.path" -- tira prefixo/sufixo por
            # TAMANHO fixo (nao por split em "."), pois <nome> pode ter
            # pontos.
            name = key[len("submodule."):-len(".path")]
            break
    if not name:
        return None, (f"nenhuma secao em .gitmodules aponta para o path "
                      f"'{target}'")
    ok2, url_out = _git(root, ["config", "-f", ".gitmodules", "--get",
                               f"submodule.{name}.url"], timeout)
    if not ok2 or not url_out.strip():
        return None, f"secao submodule.{name} nao tem chave 'url' em .gitmodules"
    return url_out.strip(), None


# ------------------------------- tags remotas (ls-remote, nunca fetch) -----

def list_remote_tags(root, url, timeout=10):
    """(dict_nome_tag->sha_ou_None, motivo_ou_None). `git ls-remote --tags`
    consulta o remoto DIRETAMENTE sem gravar nada local. Para tag anotada, a
    linha `refs/tags/<nome>^{}` (peeled) traz o sha do COMMIT -- sem tratar
    isso, uma tag anotada seria comparada pelo sha do OBJETO tag (errado:
    nunca bate com um commit pinado nem entra num 'rev-list')."""
    ok, out = _git(root, ["ls-remote", "--tags", url], timeout)
    if not ok:
        return None, out
    tags = {}
    for raw_line in out.splitlines():
        if "\t" not in raw_line:
            continue
        sha, ref = raw_line.split("\t", 1)
        sha, ref = sha.strip(), ref.strip()
        if not ref.startswith("refs/tags/"):
            continue
        name = ref[len("refs/tags/"):]
        peeled = name.endswith("^{}")
        if peeled:
            name = name[:-3]
        if peeled or name not in tags:
            tags[name] = sha
    return tags, None


def remote_branch_tip(root, url, branch, timeout=10):
    """(sha_ou_None, motivo_ou_None) da ponta de `branch` no remoto."""
    ok, out = _git(root, ["ls-remote", "--heads", url, branch], timeout)
    if not ok:
        return None, out
    line = next((l for l in out.splitlines() if l.strip()), "")
    if not line:
        return None, f"branch '{branch}' nao encontrada no remoto"
    return line.split("\t", 1)[0].strip(), None


# ------------------------------- semver: ordenar, nao adivinhar -------------

_SEMVER_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)(?:[-.]([0-9A-Za-z.\-]+))?$")


def _semver_key(name):
    """None quando `name` nao segue vX.Y.Z (tag ignorada como 'release' --
    nao adivinha ordem de tag arbitraria, ex. 'nightly', 'latest')."""
    m = _SEMVER_RE.match(name)
    if not m:
        return None
    major, minor, patch, pre = m.groups()
    # release final (sem sufixo) rankeia ACIMA de qualquer pre-release do
    # mesmo numero (v1.0.0 > v1.0.0-rc1).
    pre_rank = (1,) if pre is None else (0, pre)
    return (int(major), int(minor), int(patch), pre_rank)


def latest_release(tags):
    """(nome, sha) da maior tag semver, ou None se nenhuma tag seguir
    vX.Y.Z. Ordenacao NUMERICA (nao lexicografica -- 'v1.0.10' > 'v1.0.9',
    que uma comparacao de string erraria)."""
    candidatos = [(name, sha, _semver_key(name)) for name, sha in tags.items()]
    candidatos = [c for c in candidatos if c[2] is not None]
    if not candidatos:
        return None
    candidatos.sort(key=lambda c: c[2])
    name, sha, _key = candidatos[-1]
    return name, sha


def releases_behind(tags, pinned_sha):
    """(N_ou_None, motivo_ou_None). SO calculavel quando `pinned_sha` bate
    EXATAMENTE com o sha de alguma tag conhecida -- o pin pode estar em
    qualquer commit ENTRE duas tags, e sem o grafo de commits
    (commits_behind_local) nao ha como saber quantas tags ficaram para
    tras nesse caso."""
    pinned_tag = next((n for n, s in tags.items() if s == pinned_sha), None)
    if pinned_tag is None:
        return None, ("pinned_sha nao corresponde a nenhuma tag conhecida "
                      "no remoto -- releases_behind so e calculavel quando "
                      "o pin aponta exatamente para uma tag")
    pinned_key = _semver_key(pinned_tag)
    if pinned_key is None:
        return None, f"tag do pinned_sha ('{pinned_tag}') nao segue vX.Y.Z"
    newer = [n for n in tags if _semver_key(n) is not None
            and _semver_key(n) > pinned_key]
    return len(newer), None


# ------------------------------- commits_behind: so com objetos locais -----

def commits_behind_local(root, submodule_path, pinned_sha, target_sha, timeout=10):
    """(N_ou_None, motivo_ou_None). Contagem EXATA via
    `git -C <submodulo> rev-list --count`, SO quando os objetos de AMBOS os
    shas ja estao disponiveis no repositorio local do submodulo (checkout
    previo com o historico necessario). Nunca dispara `git fetch` para
    obter o que falta (ver docstring do modulo)."""
    sub_dir = os.path.join(root, *_to_pathspec(submodule_path).split("/"))
    if not os.path.isdir(sub_dir):
        return None, (f"'{submodule_path}' nao esta inicializado localmente "
                      "(sem checkout) -- commits_behind nao e calculavel "
                      "offline sem os objetos do submodulo")
    ok, _out = _git(sub_dir, ["rev-parse", "--git-dir"], timeout)
    if not ok:
        return None, f"'{submodule_path}' nao e um repositorio git valido localmente"
    for sha in (pinned_sha, target_sha):
        ok, _out = _git(sub_dir, ["cat-file", "-e", sha], timeout)
        if not ok:
            return None, (f"objeto {sha[:8]} nao disponivel localmente no "
                          "submodulo -- seria necessario 'git fetch', que "
                          "este detector nunca faz silenciosamente")
    ok, out = _git(sub_dir, ["rev-list", "--count", f"{pinned_sha}..{target_sha}"],
                   timeout)
    if not ok:
        return None, f"'git rev-list --count' falhou: {out}"
    try:
        return int(out.strip()), None
    except ValueError:
        return None, f"saida inesperada de 'git rev-list --count': {out!r}"


# ------------------------------- orquestracao --------------------------------

def _novo_resultado(submodule_path, url, branch):
    return {
        "submodule_path": submodule_path,
        "pinned_sha": None,
        "remote_url": url,
        "network_ok": None,
        "latest_release_tag": None,
        "latest_release_sha": None,
        "releases_behind": None,
        "commits_behind": None,
        "branch": branch,
        "branch_tip_sha": None,
        "status": "erro",
        "notes": [],
    }


def check_drift(root, submodule_path, url=None, branch=None, timeout=10):
    """Nucleo testavel, nunca lanca excecao. Devolve o dict de resultado
    descrito na docstring do modulo. `status` em
    {"erro", "atualizado", "desatualizado", "nao_verificavel"}."""
    result = _novo_resultado(submodule_path, url, branch)

    pinned, err = get_pinned_sha(root, submodule_path, timeout=timeout)
    if pinned is None:
        result["notes"].append(f"pinned_sha: {err}")
        return result
    result["pinned_sha"] = pinned

    if not url:
        url, err = resolve_url_from_gitmodules(root, submodule_path, timeout=timeout)
        if not url:
            result["notes"].append(f"remote_url: {err}")
            return result
    result["remote_url"] = url

    tags, err = list_remote_tags(root, url, timeout=timeout)
    if tags is None:
        result["network_ok"] = False
        result["status"] = "nao_verificavel"
        result["notes"].append(
            f"remoto inalcancavel ('git ls-remote --tags' falhou ou "
            f"expirou): {err}. Capacidade limitada -- nao e possivel "
            "confirmar frescor; NAO tratar como atualizado.")
        return result
    result["network_ok"] = True

    # sinais independentes de comparacao; None = indeterminado, True/False =
    # comparacao definitiva. Qualquer False vira 'desatualizado' mesmo que
    # outro sinal seja None (drift confirmado nao pode ser mascarado por
    # incerteza em OUTRO campo); so vira 'atualizado' quando TODOS os
    # sinais coletados forem True.
    sinais = []

    latest = latest_release(tags)
    if latest is None:
        result["notes"].append(
            "nenhuma tag no padrao vX.Y.Z encontrada no remoto -- "
            "releases_behind nao e calculavel; considere --branch se o "
            "consumidor segue a ponta em vez de tags.")
        sinais.append(None)
    else:
        latest_name, latest_sha = latest
        result["latest_release_tag"] = latest_name
        result["latest_release_sha"] = latest_sha
        sinais.append(pinned == latest_sha)

        n, err = releases_behind(tags, pinned)
        result["releases_behind"] = n
        if n is None:
            result["notes"].append(f"releases_behind: {err}")

        cb, err = commits_behind_local(root, submodule_path, pinned,
                                       latest_sha, timeout=timeout)
        result["commits_behind"] = cb
        if cb is None:
            result["notes"].append(f"commits_behind: {err}")

    if branch:
        tip, err = remote_branch_tip(root, url, branch, timeout=timeout)
        result["branch_tip_sha"] = tip
        if tip is None:
            result["notes"].append(f"branch '{branch}': {err}")
            sinais.append(None)
        else:
            sinais.append(tip == pinned)

    if any(s is False for s in sinais):
        result["status"] = "desatualizado"
    elif any(s is None for s in sinais):
        result["status"] = "nao_verificavel"
    else:
        result["status"] = "atualizado"
    return result


# ------------------------------- relatorio + CLI -----------------------------

def format_report(result, verbose=False):
    linhas = [
        f"submodulo:          {result['submodule_path']}",
        f"pinned_sha:         {result['pinned_sha'] or 'desconhecido'}",
        f"remote_url:         {result['remote_url'] or 'desconhecido'}",
        f"network_ok:         {result['network_ok']}",
        f"latest_release_tag: {result['latest_release_tag'] or 'desconhecida'}",
        f"latest_release_sha: {result['latest_release_sha'] or 'desconhecido'}",
        "releases_behind:    " + (
            str(result["releases_behind"]) if result["releases_behind"] is not None
            else "desconhecido"),
        "commits_behind:     " + (
            str(result["commits_behind"]) if result["commits_behind"] is not None
            else "nao calculavel offline"),
    ]
    if result["branch"]:
        linhas.append(f"branch:             {result['branch']}")
        linhas.append(f"branch_tip_sha:     {result['branch_tip_sha'] or 'desconhecido'}")
    linhas.append(f"status:             {result['status']}")
    if result["notes"] and (verbose or result["status"] != "atualizado"):
        linhas.append("notas:")
        linhas.extend(f"  - {n}" for n in result["notes"])
    return "\n".join(linhas)


def main(argv):
    args = _build_parser().parse_args(argv)
    root = args.root or L.repo_root()
    if not root:
        print("submodule_pin_drift.py: nao e um repositorio git (nem --root "
              "foi informado).", file=sys.stderr)
        return 1

    result = check_drift(root, args.path, url=args.url, branch=args.branch,
                         timeout=args.timeout)
    print(format_report(result, verbose=args.verbose))

    if result["status"] == "erro":
        for n in result["notes"]:
            print(f"[erro] {n}", file=sys.stderr)
        return 1
    return 0 if result["status"] == "atualizado" else 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
