#!/usr/bin/env python3
# tools/todo_audit.py -- motor de checks do `--audit` (AUDIT-ENG)
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
tools/todo_audit.py

Motor do `--audit` (AUDIT-ENG, ADR-0001): registro de checks, ativacao de
perfil core/casa, execucao, relatorio e CLI. NAO contem os checks
concretos do catalogo (CHK-01..14) -- esses sao de outras fatias
(CHK-CORE, CHK-GRAPH, CHK-09, CHK-10, CHK-CASA). O unico check registrado
aqui e `CHK-00`, um EXEMPLO fora do catalogo que prova o mecanismo ponta a
ponta (registro -> execucao -> achado -> relatorio -> exit code); pode ser
removido quando `CHK-CORE` registrar os checks de verdade.

Read-only por contrato (ADR-0001 c): nenhum caminho de codigo deste modulo
abre o TODO.md do usuario em modo de escrita. A unica escrita possivel e a
de `--output`, num arquivo A PARTE que nunca pode resolver para dentro do
repo do usuario.

"No silent caps" (regra da casa, citada no proprio ADR): toda limitacao ou
descarte do proprio motor -- check pulado por perfil, check que lancou
excecao, achados truncados por `--max-per-check` -- e declarado no
relatorio, nunca silencioso.

Uso:
  python3 todo_audit.py                      # roda os checks do perfil ativo
  python3 todo_audit.py --profile casa       # override pontual do perfil
  python3 todo_audit.py --output <arquivo>   # tambem grava o relatorio (fora do repo)
  python3 todo_audit.py --max-per-check 0    # sem limite de achados por check

Exit codes (D-6): 0 = execucao ok e zero achados; 1 = erro de execucao
(excecao nao tratada, TODO.md ilegivel, nao e repositorio git); 2 = execucao
ok e ha 1+ achado, de qualquer severidade -- inclusive so COSMETICO.
"""
from __future__ import annotations

import argparse
import configparser
import inspect
import os
import re
import sys
import traceback
from collections.abc import Callable
from dataclasses import dataclass

import todo_lib as L

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
CASA_DIR = os.path.join(TOOLS_DIR, "casa")

_PROFILES = ("core", "casa")
_SEVERITIES = ("CRÍTICO", "IMPORTANTE", "COSMÉTICO")

DEFAULT_MAX_PER_CHECK = 20
CONFIG_FILENAME = ".tab_pendencias.ini"


# ------------------------------- (a) registro de checks ------------------------

@dataclass(frozen=True)
class Finding:
    """Um achado emitido por um Check.run(). `fixable`/`fix_ref` moram AQUI
    (por-achado, decidido pelo proprio check que o produz), nunca numa
    tabela central -- e a decisao explicita do ADR-0001 (c) contra a classe
    de deriva README x SKILL.md."""
    check_id: str
    severity: str
    message: str
    line_no: int | None = None   # 0-based (indice de `table["lines"]`); o
                                  # relatorio converte p/ 1-based ao exibir
    fixable: bool = False
    fix_ref: str | None = None

    def __post_init__(self):
        if self.severity not in _SEVERITIES:
            raise ValueError(
                f"Finding.severity invalida: {self.severity!r} (esperado um "
                f"de {_SEVERITIES})")


@dataclass(frozen=True)
class Context:
    """O que cada `Check.run` recebe. So leitura: nenhum campo aqui e um
    handle de escrita no TODO.md do usuario (--audit e sempre read-only)."""
    root: str
    todo_path: str | None
    text: str | None
    table: dict | None
    profile: str
    config: configparser.ConfigParser


@dataclass(frozen=True)
class Check:
    """Registro de um check. `profile` e OBRIGATORIO e SEM DEFAULT -- omitir
    e TypeError na construcao (a propria mecanica de dataclass sem default
    ja garante isso; `__post_init__` reforca o VALOR ser um dos dois
    validos, nao so a presenca do campo)."""
    id: str
    title: str
    profile: str
    severity_default: str
    run: Callable[[Context], list[Finding]]

    def __post_init__(self):
        if self.profile not in _PROFILES:
            raise ValueError(
                f"Check {self.id!r}: profile invalido {self.profile!r} "
                f"(esperado um de {_PROFILES}) -- declaracao obrigatoria, "
                "sem default (ADR-0001 a).")
        if self.severity_default not in _SEVERITIES:
            raise ValueError(
                f"Check {self.id!r}: severity_default invalida "
                f"{self.severity_default!r} (esperado um de {_SEVERITIES}).")


def _chk00_id_com_espaco(ctx):
    """[EXEMPLO / placeholder de AUDIT-ENG] Reporta IDs que contem espaco em
    branco -- convencao minima (um ID e um token, ex.: 'V-12', 'F1.4').
    Deliberadamente FORA do catalogo CHK-01..14 (esses sao de CHK-CORE/
    CHK-GRAPH/CHK-09/CHK-10/CHK-CASA): so precisa provar que o motor
    registra, executa, emite Finding com evidencia de linha e aparece no
    relatorio -- nada mais. Remova quando CHK-CORE registrar os checks
    reais."""
    table = ctx.table
    if not table:
        return []
    out = []
    for it in table["items"]:
        if re.search(r"\s", it["id"]):
            out.append(Finding(
                check_id="CHK-00", severity="COSMÉTICO",
                message=f"ID {it['id']!r} contem espaco em branco",
                line_no=it["line_no"], fixable=False))
    return out


import checks.chk_graph as _chk_graph  # noqa: E402 -- import tardio de
# proposito (depois de Check/Finding definidos): `checks.chk_graph` importa
# `Finding` de volta deste modulo dentro do CORPO das suas funcoes de check
# (nao no topo do arquivo), entao nao ha ciclo de importacao de verdade --
# so a ordem de leitura aqui reflete que o registro (CHK-GRAPH) vem DEPOIS
# das classes que ele consome.

CHECKS: list[Check] = [
    Check(id="CHK-00", title="[exemplo] ID com espaco em branco",
          profile="core", severity_default="COSMÉTICO",
          run=_chk00_id_com_espaco),
    Check(id="CHK-05", title="Pré-requisito citando ID inexistente",
          profile="core", severity_default="IMPORTANTE",
          run=_chk_graph.chk05),
    Check(id="CHK-06", title="Ciclo de dependência",
          profile="core", severity_default="CRÍTICO",
          run=_chk_graph.chk06),
    Check(id="CHK-07", title="Onda inconsistente com a dependência",
          profile="core", severity_default="IMPORTANTE",
          run=_chk_graph.chk07),
]


def _check_run_file(check):
    """Caminho absoluto do arquivo-fonte onde `check.run` foi definido."""
    fn = check.run
    path = inspect.getsourcefile(fn) or inspect.getfile(fn)
    return os.path.abspath(path)


def core_boundary_violations(checks):
    """IDs dos checks `profile == "core"` cujo `run` esta fisicamente
    definido dentro de `tools/casa/` -- violacao da fronteira (ADR-0001 a).
    Lista vazia = fronteira intacta (inclusive quando nao ha check 'casa'
    nenhum registrado ainda: o teste que consome isto nasce ANTES do
    primeiro check 'casa' ser codado, por desenho).

    Usa o ARQUIVO-FONTE de `run` (nao o nome do modulo Python) porque
    `tools/` neste projeto nao e um pacote formal (os scripts sao
    importados soltos via sys.path, D-4/monorepo) -- comparar por caminho
    de arquivo e robusto independente de o check ter sido importado como
    `casa.xxx` ou como `xxx` solto."""
    out = []
    for c in checks:
        if c.profile != "core":
            continue
        f = _check_run_file(c)
        try:
            common = os.path.commonpath([f, CASA_DIR])
        except ValueError:          # discos diferentes (Windows): nunca "dentro"
            common = ""
        if common == CASA_DIR:
            out.append(c.id)
    return out


# ------------------------------- (a) perfil ativo -------------------------------

def load_config(root):
    """(`configparser.ConfigParser`, erro_ou_None). D-9: SO configparser da
    stdlib, nunca `tomllib` (exclusivo de 3.11+, o produto e distribuido e
    precisa rodar em 3.9/3.10). D-10: arquivo `.tab_pendencias.ini` na raiz
    do repo do USUARIO. Ausencia do arquivo = perfil core (D-10), silencioso
    (nao e uma limitacao do motor, e o comportamento padrao documentado).
    Arquivo PRESENTE mas malformado NAO trava o motor -- cai no default
    core, mas o erro e devolvido para o motor declarar no relatorio (no
    silent caps: um .ini ilegivel e diferente de auscencia intencional)."""
    cfg = configparser.ConfigParser()
    path = os.path.join(root, CONFIG_FILENAME)
    if not os.path.isfile(path):
        return cfg, None
    try:
        with open(path, encoding="utf-8") as fh:
            cfg.read_string(fh.read(), source=path)
    except (configparser.Error, OSError, UnicodeDecodeError) as exc:
        return configparser.ConfigParser(), (
            f"{CONFIG_FILENAME} ilegivel ({type(exc).__name__}: {exc}) -- "
            "perfil caiu para o default 'core'.")
    return cfg, None


def active_profile(cfg, cli_override):
    """(perfil, origem_legivel). Prioridade (ADR-0001 a): `--profile`
    (override pontual) > `.tab_pendencias.ini` > default 'core'. Sem
    variavel de ambiente (decisao explicita do ADR: estado implicito global
    ao shell, sobrevive entre repos nao-relacionados)."""
    if cli_override:
        return cli_override, f"--profile {cli_override}"
    raw = cfg.get("profile", "name", fallback=None)
    if raw is None:
        return "core", "default (sem .tab_pendencias.ini ou sem [profile] name)"
    val = raw.strip().lower()
    if val not in _PROFILES:
        return "core", (
            f"default (valor invalido {val!r} em {CONFIG_FILENAME} "
            f"[profile] name -- esperado 'core' ou 'casa')")
    return val, f"{CONFIG_FILENAME} [profile] name = {val}"


# --------------------------------- motor ----------------------------------------

class AuditError(Exception):
    """Erro de execucao (D-6): TODO.md ilegivel, etc. -- vira exit 1 em main()."""


@dataclass
class AuditResult:
    findings: list[Finding]
    notices: list[str]
    report_text: str
    profile: str


def _read_todo(todo_path):
    """Leitura explicita de encoding (D-11/ADR-0001 e.3): utf-8 sempre,
    `newline=""` para nao normalizar CRLF/LF -- --audit e read-only, mas os
    numeros de linha reportados tem que corresponder ao arquivo byte-a-byte,
    o mesmo invariante de round-trip que `set_status_cell` exige na escrita."""
    try:
        with open(todo_path, encoding="utf-8", newline="") as fh:
            return fh.read()
    except Exception as exc:
        raise AuditError(
            f"Falha ao ler TODO.md ({type(exc).__name__}): {exc}") from exc


def run_audit(root, checks=None, profile_override=None,
              max_per_check=DEFAULT_MAX_PER_CHECK, verbose=False):
    """Nucleo testavel, sem argparse/sys.exit. Levanta `AuditError` (erro de
    execucao real); nunca escreve no TODO.md (--audit e sempre read-only)."""
    checks = CHECKS if checks is None else list(checks)
    cfg, cfg_error = load_config(root)
    profile, origin = active_profile(cfg, profile_override)

    notices = []
    if cfg_error:
        notices.append(cfg_error)

    todo_path = L.find_todo(root)
    if not todo_path:
        report = _render(root, None, profile, origin, [], notices, checks, [])
        return AuditResult(findings=[], notices=notices, report_text=report,
                           profile=profile)

    text = _read_todo(todo_path)
    table = L.parse_table(text)
    ctx = Context(root=root, todo_path=todo_path, text=text, table=table,
                  profile=profile, config=cfg)

    findings = []
    checks_run = []   # [(check, [Finding,...])] -- so os que rodaram de fato
    for check in checks:
        applicable = check.profile == "core" or (
            check.profile == "casa" and profile == "casa")
        if not applicable:
            notices.append(
                f"{check.id} (convencao da casa) nao executado -- perfil "
                "ativo = core. Habilite com --profile casa ou "
                f"{CONFIG_FILENAME} [profile] name = casa.")
            continue
        try:
            result = list(check.run(ctx))
        except Exception as exc:  # noqa: BLE001 -- isolamento deliberado: um
            # check de terceiro (CHK-09 chama git, futuros podem chamar
            # mais) nunca pode derrubar o motor inteiro; a excecao e sempre
            # capturada COM contexto (tipo+mensagem+id do check) e DECLARADA
            # no relatorio (no silent caps), nunca engolida em silencio.
            notices.append(
                f"{check.id} falhou ao executar ({type(exc).__name__}: "
                f"{exc}) -- achados deste check NAO estao no relatorio "
                "(no silent caps: a falha em si e declarada).")
            if verbose:
                notices.append(traceback.format_exc())
            continue
        checks_run.append((check, result))
        findings.extend(result)

    report = _render(root, todo_path, profile, origin, checks_run, notices,
                     checks, findings, max_per_check)
    return AuditResult(findings=findings, notices=notices, report_text=report,
                       profile=profile)


# ------------------------------- relatorio ---------------------------------------

def _fmt_finding(f):
    loc = f"linha {f.line_no + 1}" if f.line_no is not None else "(sem linha)"
    tag = f"[auto-fixável -> {f.fix_ref}]" if f.fixable else "[julgamento]"
    return f"    {loc}: {f.message}  {tag}"


def _render(root, todo_path, profile, origin, checks_run, notices,
            all_checks, all_findings, max_per_check=DEFAULT_MAX_PER_CHECK):
    lines = []
    lines.append("=== tab_pendencias --audit ===")
    lines.append(f"TODO.md: {todo_path if todo_path else '(nao encontrado em ' + root + ')'}")
    lines.append(f"Perfil ativo: {profile} (origem: {origin})")
    lines.append("")

    if not todo_path:
        lines.append("Sem TODO.md na raiz; nada a auditar.")
    elif not checks_run:
        lines.append("Nenhum check aplicavel produziu achados.")
    else:
        n = 0
        for check, results in checks_run:
            if not results:
                continue
            n += 1
            lines.append(f"[{n}] {check.id} -- {check.title} "
                         f"({check.severity_default}) -- {len(results)} achado(s)")
            shown = results if max_per_check <= 0 else results[:max_per_check]
            for f in shown:
                lines.append(_fmt_finding(f))
            omitidos = len(results) - len(shown)
            if omitidos > 0:
                lines.append(
                    f"    ... (+{omitidos} nao mostrados; rode com "
                    "--max-per-check 0 para ver todos -- no silent caps)")
            lines.append("")
        if n == 0:
            lines.append("Nenhum check aplicavel produziu achados.")

    crit = sum(1 for f in all_findings if f.severity == "CRÍTICO")
    imp = sum(1 for f in all_findings if f.severity == "IMPORTANTE")
    cosm = sum(1 for f in all_findings if f.severity == "COSMÉTICO")
    executados = len(checks_run)
    registrados = len(all_checks)
    lines.append(
        f"Achados: {len(all_findings)} ({crit} CRÍTICO, {imp} IMPORTANTE, "
        f"{cosm} COSMÉTICO) em {executados} check(s) executado(s) de "
        f"{registrados} registrado(s).")
    lines.append("")
    lines.append("Avisos do motor (no silent caps):")
    if notices:
        for nmsg in notices:
            lines.append(f"  - {nmsg}")
    else:
        lines.append("  - nenhum.")
    return "\n".join(lines) + "\n"


# --------------------------------- CLI (D-6) -------------------------------------

class _Parser(argparse.ArgumentParser):
    """Contrato de exit code (D-6): erro de parsing (flag desconhecida, valor
    invalido de --profile/--max-per-check) sai 1, NAO 2 -- 2 e reservado a
    'ha achado(s)'."""

    def error(self, message):
        self.print_usage(sys.stderr)
        self.exit(1, f"{self.prog}: error: {message}\n")


def _build_parser():
    p = _Parser(
        prog="todo_audit.py",
        description=(
            "Motor de auditoria da TODO.md (offline, sem LLM, sem rede): "
            "roda os checks do perfil ativo e relata achados numerados por "
            "check, com evidencia de linha e marcacao [auto-fixavel]/"
            "[julgamento]. --audit e SEMPRE read-only."
        ),
        epilog=(
            "Exit codes: 0 = execucao ok, zero achados; 1 = erro de "
            "execucao (nao e repositorio git, TODO.md ilegivel, flag "
            "invalida); 2 = execucao ok, ha 1+ achado (mesmo so COSMETICO)."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--profile", choices=_PROFILES, default=None,
        help="Override pontual do perfil ativo (default: le "
             f"{CONFIG_FILENAME} na raiz do repo; sem arquivo/chave = core).")
    p.add_argument(
        "--output", metavar="ARQUIVO", default=None,
        help="Tambem grava o relatorio neste arquivo. NUNCA pode resolver "
             "para dentro do repo do usuario (aborta com erro se apontar "
             "para la); use um caminho de scratchpad.")
    p.add_argument(
        "--max-per-check", type=int, default=DEFAULT_MAX_PER_CHECK,
        metavar="N",
        help=f"Acha no maximo N achados por check no relatorio (default "
             f"{DEFAULT_MAX_PER_CHECK}); N<=0 = sem limite. Achados extras "
             "sao sempre contados e declarados (no silent caps), nunca so "
             "descartados.")
    p.add_argument(
        "-v", "--verbose", action="store_true",
        help="Acrescenta traceback completo em stderr/relatorio quando um "
             "check ou a leitura do TODO.md falha (default: so tipo + "
             "mensagem da excecao).")
    return p


def _output_forbidden(path, root):
    """True se `path` (apos abspath) fica DENTRO de `root` -- --output nunca
    pode escrever no repo do usuario (ADR-0001 c: saida em arquivo e sempre
    fora do repo)."""
    ap = os.path.abspath(path)
    rp = os.path.abspath(root)
    try:
        common = os.path.commonpath([ap, rp])
    except ValueError:      # discos diferentes no Windows: nunca "dentro"
        return False
    return common == rp


def main(argv):
    args = _build_parser().parse_args(argv)
    root = L.repo_root()
    if not root:
        print("Nao e um repositorio git.")
        return 1

    if args.output and _output_forbidden(args.output, root):
        print(
            f"--output ({args.output}) resolve para dentro do repo do "
            f"usuario ({root}) -- --audit nunca escreve la. Aponte para "
            "outro lugar (ex.: scratchpad).", file=sys.stderr)
        return 1

    try:
        result = run_audit(root, profile_override=args.profile,
                           max_per_check=args.max_per_check,
                           verbose=args.verbose)
    except AuditError as exc:
        print(str(exc), file=sys.stderr)
        if args.verbose:
            traceback.print_exc(file=sys.stderr)
        return 1

    print(result.report_text)
    if args.output:
        # Relatorio novo (nao e round-trip do TODO.md do usuario): encoding
        # explicito (D-11) sempre; newline default (traduz para os.linesep)
        # e o correto aqui, o invariante byte-exato (ADR-0001 b.1) vale so
        # para o arquivo do usuario, nunca gravado por este modulo.
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(result.report_text)

    return 2 if result.findings else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
