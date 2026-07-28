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
concretos do catalogo -- esses sao de outras fatias (`checks/chk_core.py`
= CHK-01/02/03/04/08/11; `checks/chk_graph.py` = CHK-05/06/07;
`checks/chk_frescor.py` = CHK-09/10; `casa/chk_casa.py` = CHK-12/13/14,
profile="casa"). Todos os 14 ja registrados em `CHECKS` abaixo.

Read-only por contrato (ADR-0001 c): nenhum caminho de codigo deste modulo
abre o TODO.md do usuario em modo de escrita. A unica escrita possivel e a
de `--output`, num arquivo A PARTE que nunca pode resolver para dentro do
repo do usuario.

"No silent caps" (regra da casa, citada no proprio ADR): toda limitacao ou
descarte do proprio motor -- check pulado por perfil, check que lancou
excecao, achados truncados por `--max-per-check` -- e declarado no
relatorio, nunca silencioso.

Apresentacao do relatorio (achado do team-lead calibrando contra as
fixtures reais, 28/07): secoes ordenadas por SEVERIDADE (CRITICO sempre
primeiro), achados CRITICO nunca truncados pelo `--max-per-check` (so os
de severidade menor sao cortados quando o total excede o limite), e o
cabecalho de cada secao mostra o CONJUNTO REAL de severidades presentes
naquela execucao (nao a `severity_default` estatica do check, que pode
nao bater com achados individuais de severidade propria -- ex. CHK-09).

Uso:
  python3 todo_audit.py                      # roda os checks do perfil ativo
  python3 todo_audit.py --profile casa       # override pontual do perfil
  python3 todo_audit.py --output <arquivo>   # tambem grava o relatorio (fora do repo)
  python3 todo_audit.py --max-per-check 0    # sem limite de achados por check
  python3 todo_audit.py --todo <caminho>     # audita um TODO.md fora do cwd/repo

AUDIT-PATH: `--todo <caminho>` audita um arquivo chamado EXATAMENTE "TODO.md"
(convencao fixa de `todo_lib.find_todo`) que nao precisa estar no cwd atual
nem no mesmo repositorio git de quem invoca -- necessario para auditar as
fixtures de aceitacao de terceiros, que nunca podem ser copiadas para dentro
deste repositorio. Sem a flag, o comportamento e IDENTICO ao anterior
(descoberta automatica a partir do cwd, que precisa ser repositorio git).
Quando o alvo esta fora de qualquer repositorio git resolvivel, os checks
que dependem de `git` (CHK-09, CHK-10) perdem contexto -- eles proprios
declaram isso por achado ("desconhecido"/erro), e o motor ADICIONA um aviso
sistemico unico (no silent caps) em vez de deixar N achados soltos sem
explicacao do porque.

Exit codes (D-6): 0 = execucao ok e zero achados; 1 = erro de execucao
(excecao nao tratada, TODO.md ilegivel, nao e repositorio git); 2 = execucao
ok e ha 1+ achado, de qualquer severidade -- inclusive so COSMETICO.
"""
from __future__ import annotations

import argparse
import configparser
import inspect
import os
import sys
import traceback
from collections.abc import Callable
from dataclasses import dataclass

import todo_lib as L

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
CASA_DIR = os.path.join(TOOLS_DIR, "casa")

_PROFILES = ("core", "casa")
_SEVERITIES = ("CRÍTICO", "IMPORTANTE", "COSMÉTICO")  # ordem = prioridade de leitura
_SEVERITY_RANK = {s: i for i, s in enumerate(_SEVERITIES)}

# DEFAULT_MAX_PER_CHECK reduzido de 20 para 5 (achado do team-lead calibrando
# contra as fixtures reais, 28/07): um check de "padrao repetitivo" (ex.
# CHK-05 com 89 ocorrencias) com 20 linhas de amostra ainda produz um
# relatorio longo demais para escaneamento humano -- 5 e amostra suficiente
# para reconhecer o padrao (o TITULO do check ja diz QUAL e o padrao; a
# amostra so precisa provar que ele e real e mostrar onde). CRITICO nunca e
# cortado por este limite (ver `_shown_findings`) -- so severidades menores
# perdem detalhe quando excedem o limite, nunca o que mais importa.
DEFAULT_MAX_PER_CHECK = 5
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


import checks.chk_graph as _chk_graph  # noqa: E402 -- import tardio de
# proposito (depois de Check/Finding definidos): `checks.chk_graph` importa
# `Finding` de volta deste modulo dentro do CORPO das suas funcoes de check
# (nao no topo do arquivo), entao nao ha ciclo de importacao de verdade --
# so a ordem de leitura aqui reflete que o registro (CHK-GRAPH) vem DEPOIS
# das classes que ele consome.
import checks.chk_frescor as _chk_frescor  # noqa: E402 -- mesmo padrao de
# import tardio acima (CHK-09/CHK-10, `checks/chk_frescor.py`).
import checks.chk_core as _chk_core  # noqa: E402 -- mesmo padrao (CHK-CORE:
# CHK-01/02/03/04/08/11, `checks/chk_core.py`).
import casa.chk_casa as _chk_casa  # noqa: E402 -- mesmo padrao de import
# tardio, agora para o perfil "casa" (CHK-12/13/14, `tools/casa/chk_casa.py`,
# ADR-0001 secao a). E o UNICO ponto do nucleo que sabe da existencia deste
# modulo -- so pela linha de registro abaixo (profile="casa"); nenhuma
# LOGICA do nucleo depende dele (core_boundary_violations garante isso em
# CI para os checks profile=="core").

CHECKS: list[Check] = [
    Check(id="CHK-01", title="ID duplicado", profile="core",
          severity_default="CRÍTICO", run=_chk_core._chk01_id_duplicado),
    Check(id="CHK-02", title="nº de células ≠ cabeçalho (diagnóstico)",
          profile="core", severity_default="CRÍTICO",
          run=_chk_core._chk02_ncols_diverge),
    Check(id="CHK-03", title="Tabela fragmentada + span da canônica",
          profile="core", severity_default="CRÍTICO",
          run=_chk_core._chk03_tabela_fragmentada),
    Check(id="CHK-04", title="ncols divergente entre tabelas ID+Status",
          profile="core", severity_default="CRÍTICO",
          run=_chk_core._chk04_ncols_divergente_entre_tabelas),
    Check(id="CHK-05", title="Pré-requisito citando ID inexistente",
          profile="core", severity_default="IMPORTANTE",
          run=_chk_graph.chk05),
    Check(id="CHK-06", title="Ciclo de dependência",
          profile="core", severity_default="CRÍTICO",
          run=_chk_graph.chk06),
    Check(id="CHK-07", title="Onda inconsistente com a dependência",
          profile="core", severity_default="IMPORTANTE",
          run=_chk_graph.chk07),
    Check(id="CHK-08", title="Status fora do vocabulário canônico",
          profile="core", severity_default="IMPORTANTE",
          run=_chk_core._chk08_status_fora_do_vocabulario),
    Check(id="CHK-09", title="Claims obsoletas na Descrição (contra o git real)",
          profile="core", severity_default="IMPORTANTE",
          run=_chk_frescor.chk09),
    Check(id="CHK-10", title="Proposta do todo_sync.py (sem --apply) anexada",
          profile="core", severity_default="COSMÉTICO",
          run=_chk_frescor.chk10),
    Check(id="CHK-11", title="Reconciliação de contagem (todo_health)",
          profile="core", severity_default="CRÍTICO",
          run=_chk_core._chk11_reconciliacao_contagem),
    Check(id="CHK-12", title="TST-*/AUD-* agendado antes do que cobre "
          "(convenção da casa)",
          profile="casa", severity_default="CRÍTICO", run=_chk_casa.chk12),
    Check(id="CHK-13", title="INBOX: ID duplicado da tabela ou formato "
          "inválido (convenção da casa)",
          profile="casa", severity_default="IMPORTANTE", run=_chk_casa.chk13),
    Check(id="CHK-14", title="Item de Wiki + doc para iniciante ausente na "
          "última onda (convenção da casa)",
          profile="casa", severity_default="COSMÉTICO", run=_chk_casa.chk14),
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
              max_per_check=DEFAULT_MAX_PER_CHECK, verbose=False,
              todo_path=None):
    """Nucleo testavel, sem argparse/sys.exit. Levanta `AuditError` (erro de
    execucao real); nunca escreve no TODO.md (--audit e sempre read-only).

    `todo_path`, quando informado, SOBREPOE a descoberta automatica
    (`L.find_todo(root)`) -- e o que a CLI usa para `--todo <caminho>`
    (AUDIT-PATH). Quando informado, `root` DEVE ser o diretorio que contem
    esse arquivo (a CLI garante isso; ver `main()`) -- e o mesmo diretorio
    de onde `.tab_pendencias.ini` e lido (D-10) e de onde os checks
    dependentes de `git` (CHK-09/CHK-10) partem para deixar o proprio git
    auto-descobrir a arvore (funciona de qualquer subdiretorio dela)."""
    checks = CHECKS if checks is None else list(checks)
    cfg, cfg_error = load_config(root)
    profile, origin = active_profile(cfg, profile_override)

    notices = []
    if cfg_error:
        notices.append(cfg_error)

    todo_path = todo_path or L.find_todo(root)
    if not todo_path:
        report = _render(root, None, profile, origin, [], notices, checks, [])
        return AuditResult(findings=[], notices=notices, report_text=report,
                           profile=profile)

    text = _read_todo(todo_path)
    table = L.parse_table(text)
    ctx = Context(root=root, todo_path=todo_path, text=text, table=table,
                  profile=profile, config=cfg)

    if not L.git_dir(root):
        # AUDIT-PATH: alvo fora de qualquer repositorio git resolvivel.
        # CHK-09/CHK-10 ainda rodam (nao derrubam o motor -- cada um degrada
        # gracilmente por conta propria, "desconhecido"/erro do git), mas
        # sem este aviso sistemico UNICO o leitor veria N achados soltos
        # sem entender que a causa e a MESMA em todos: nao ha contexto git
        # nenhum para verificar (no silent caps).
        notices.append(
            f"Alvo fora de qualquer repositorio git resolvivel (raiz "
            f"assumida: {root}) -- checks que dependem de `git` (CHK-09, "
            "CHK-10) nao terao contexto: eles proprios declararao "
            "'desconhecido'/erro do git por achado, nunca um veredito "
            "real (no silent caps).")

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


def _severity_rank(f):
    return _SEVERITY_RANK.get(f.severity, len(_SEVERITIES))


def _severities_presentes(results):
    """Conjunto REAL de severidades dos achados desta execucao, em ordem de
    prioridade (CRITICO, IMPORTANTE, COSMETICO) -- NUNCA a `severity_default`
    estatica do check, que pode nao bater com o que foi achado de fato (ex.:
    CHK-09 tem achados IMPORTANTE e COSMETICO na MESMA execucao; mostrar so
    o default faria o cabecalho parecer contradizer a contagem abaixo dele,
    o achado original do team-lead que motivou este conserto)."""
    presentes = {f.severity for f in results}
    return tuple(s for s in _SEVERITIES if s in presentes)


def _shown_findings(results, max_per_check):
    """(mostrados, omitidos) -- ordena por severidade (CRITICO primeiro,
    estavel dentro de cada severidade) ANTES de truncar, e garante que
    achados CRITICO NUNCA sao cortados pelo limite: o corte so incide sobre
    severidades menores. Isto nao e supressao automatica (o team-lead pediu
    para nao inventar isso) -- e o oposto, uma garantia de VISIBILIDADE do
    que mais importa; a contagem total e o exit code continuam refletindo
    TUDO que foi achado, so a AMOSTRA impressa muda de composicao."""
    se_ordenados = sorted(results, key=_severity_rank)
    if max_per_check <= 0:
        return se_ordenados, 0
    n_critico = sum(1 for f in se_ordenados if f.severity == "CRÍTICO")
    limite = max(max_per_check, n_critico)
    mostrados = se_ordenados[:limite]
    return mostrados, len(se_ordenados) - len(mostrados)


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
        # Secoes ORDENADAS por severidade (achado do team-lead, 28/07): a
        # ordem de registro (CHK-01, CHK-02, ...) enterrava achados CRITICO
        # raros sob centenas de achados de severidade menor de checks
        # registrados depois. A chave de ordenacao e a PIOR (mais severa)
        # severidade presente nos achados do proprio check -- sort estavel
        # preserva a ordem de registro como desempate entre checks de mesma
        # pior-severidade.
        com_achados = [(c, r) for c, r in checks_run if r]
        com_achados.sort(key=lambda cr: min(_severity_rank(f) for f in cr[1]))

        n = 0
        for check, results in com_achados:
            n += 1
            severidades = _severities_presentes(results)
            rotulo_severidade = ", ".join(severidades)
            lines.append(
                f"[{n}] {check.id} -- {check.title} ({rotulo_severidade}) "
                f"-- {len(results)} ocorrencia(s) deste padrao")
            shown, omitidos = _shown_findings(results, max_per_check)
            for f in shown:
                lines.append(_fmt_finding(f))
            if omitidos > 0:
                lines.append(
                    f"    ... (+{omitidos} nao mostrada(s); rode com "
                    "--max-per-check 0 para ver todas -- no silent caps)")
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
    p.add_argument(
        "--todo", metavar="CAMINHO", default=None,
        help="Audita este arquivo em vez de descobrir automaticamente a "
             "partir do cwd. Nao precisa estar no cwd atual nem no mesmo "
             "repositorio git (AUDIT-PATH) -- mas precisa se chamar "
             "exatamente 'TODO.md'. Sem esta flag, o cwd continua "
             "precisando ser um repositorio git (comportamento anterior, "
             "inalterado).")
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

    if args.todo:
        # AUDIT-PATH: `root` = diretorio que contem o arquivo apontado --
        # NAO exige que o cwd de invocacao seja repositorio git (o alvo
        # pode ser de outro repositorio inteiramente, ou nao ter git
        # nenhum). Restricao deliberada: o basename tem que ser
        # EXATAMENTE "TODO.md" (mesma convencao hardcoded de
        # `L.find_todo`) -- sem isso, CHK-11 (que re-descobre
        # "root/TODO.md" via `todo_health.run(root=...)`, um caminho de
        # codigo INDEPENDENTE do usado aqui) compararia contra um arquivo
        # diferente do auditado (ou nenhum), e o relatorio passaria a
        # impressao de ter verificado algo que nao verificou.
        todo_path = os.path.abspath(args.todo)
        base = os.path.basename(todo_path)
        if base != "TODO.md":
            print(
                f"--todo deve apontar para um arquivo chamado exatamente "
                f"'TODO.md' (convencao fixa do produto, ver "
                f"todo_lib.find_todo) -- recebido {base!r}.",
                file=sys.stderr)
            return 1
        root = os.path.dirname(todo_path)
    else:
        todo_path = None
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
                           verbose=args.verbose, todo_path=todo_path)
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
