#!/usr/bin/env python3
# tools/hooks/tab_pendencias_reminder.py -- adapter Claude-Code (TAB-HOOK-004)
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
Adapter de hook Claude Code para o motor de sinais de frescor.

Contrato (TAB-HOOK-001..004):
  - stdin JSON -> stdout JSON `{continue: true, additionalContext?: str}`
  - JSON invalido/vazio: cwd = getcwd(), fail-open
  - exit SEMPRE 0 (nunca bloqueia a sessao)
  - zero regra de negocio propria: so chama `session_signals.collect_signals`
  - offline, sem LLM, sem rede, sem escrever TODO.md

Roteamento por evento (TAB-HOOK-005): o mesmo adapter e ligado a
`SessionStart` e a `UserPromptSubmit`. Cada sinal so e emitido no evento a
que pertence (`session_signals.SIGNALS_BY_EVENT`), nunca nos dois -- antes
disto a mesma mensagem de defasagem saia nos dois eventos, repetida ao
usuario. Alem do roteamento, o evento por-turno passa por deduplicacao
por sessao: um sinal com as mesmas `reasons` nao se repete no mesmo
`session_id`; se o fato mudar (ex.: mais um arquivo em inbox/), o sinal
volta a ser emitido.

A logica vive em `tools/session_signals.py`. Este arquivo e wiring.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import time

# tools/ e o pai de tools/hooks/ -- garante import flat do monorepo.
# realpath: quando o hook e invocado via symlink (ex.: ~/.grok/hooks/scripts/),
# abspath aponta para o link e o parent deixa de ser tools/ -- o import quebra.
_HOOKS_DIR = os.path.dirname(os.path.realpath(__file__))
_TOOLS_DIR = os.path.dirname(_HOOKS_DIR)
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

import session_signals as SS  # noqa: E402


def parse_hook_stdin(raw):
    """Parse do stdin do Claude Code. Fail-open.

    Devolve dict com pelo menos `cwd` (string). JSON invalido, vazio ou
    nao-dict -> cwd = os.getcwd().
    """
    cwd_fallback = os.getcwd()
    if raw is None:
        return {"cwd": cwd_fallback}
    if isinstance(raw, (bytes, bytearray)):
        try:
            raw = raw.decode("utf-8")
        except Exception:
            return {"cwd": cwd_fallback}
    text = raw if isinstance(raw, str) else str(raw)
    text = text.strip()
    if not text:
        return {"cwd": cwd_fallback}
    try:
        data = json.loads(text)
    except (TypeError, ValueError, json.JSONDecodeError):
        return {"cwd": cwd_fallback}
    if not isinstance(data, dict):
        return {"cwd": cwd_fallback}
    cwd = (data.get("cwd") or cwd_fallback or "").strip()
    if not cwd or not os.path.isdir(cwd):
        cwd = cwd_fallback
    data = dict(data)
    data["cwd"] = cwd
    return data


# --- Deduplicacao por sessao (TAB-HOOK-005) ---------------------------------
#
# `UserPromptSubmit` dispara a CADA turno. Sem memoria, um `inbox/x.md` nao
# drenado emitiria o mesmo aviso 20 vezes numa conversa de 20 turnos. O
# estado e um arquivo por sessao no diretorio temporario do SO (nunca dentro
# do repositorio do usuario -- o produto nao escreve na arvore dele).
#
# `SessionStart` NAO passa por dedup de proposito: ele dispara poucas vezes
# por sessao e cada disparo (startup/resume/clear/compact) segue um reset de
# contexto -- suprimir ali apagaria a injecao justamente quando ela e mais
# necessaria.
_STATE_DIRNAME = "tab_pendencias_hook_state"
_STATE_TTL_SECONDS = 7 * 24 * 3600
_STATE_MAX_FILES = 200


def default_state_dir():
    """Diretorio de estado de sessao. `tempfile.gettempdir()` e portavel
    (POSIX e Windows) e nao presume separador nem permissao Unix."""
    return os.path.join(tempfile.gettempdir(), _STATE_DIRNAME)


def session_state_path(session_id, state_dir=None):
    """Caminho do arquivo de estado de uma sessao, ou None sem session_id.

    O `session_id` vem do harness (texto arbitrario): vira digest hex, o que
    elimina travessia de caminho e caractere invalido em qualquer SO.
    """
    if session_id is None:
        return None
    # o harness manda texto, mas payload corrompido pode mandar qualquer
    # tipo JSON -- normaliza sem levantar.
    sid = session_id if isinstance(session_id, str) else str(session_id)
    sid = sid.strip()
    if not sid:
        return None
    base = state_dir or default_state_dir()
    digest = hashlib.sha256(sid.encode("utf-8")).hexdigest()[:32]
    return os.path.join(base, digest + ".json")


def prune_state_dir(state_dir=None, now_ts=None):
    """Remove estado velho: por idade (TTL) e por teto de arquivos.

    Mantem o diretorio limitado sem crescer sem fim. Nunca levanta.
    """
    base = state_dir or default_state_dir()
    if now_ts is None:
        now_ts = time.time()
    try:
        nomes = [n for n in os.listdir(base) if n.endswith(".json")]
    except OSError:
        return
    vivos = []
    for nome in nomes:
        caminho = os.path.join(base, nome)
        try:
            m = os.path.getmtime(caminho)
        except OSError:
            continue
        if (now_ts - m) > _STATE_TTL_SECONDS:
            try:
                os.remove(caminho)
            except OSError:
                pass
            continue
        vivos.append((m, caminho))
    if len(vivos) > _STATE_MAX_FILES:
        vivos.sort()
        for _, caminho in vivos[: len(vivos) - _STATE_MAX_FILES]:
            try:
                os.remove(caminho)
            except OSError:
                pass


def _signal_fingerprint(signal):
    """Identidade do FATO, nao so do sinal: id + reasons.

    Se as reasons mudarem (inbox_files=1 -> inbox_files=2), o sinal volta a
    ser emitido -- informacao nova nao pode ser silenciada pelo dedup.
    """
    return "{}|{}".format(signal.id, ",".join(signal.reasons))


def _load_emitted(path):
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return set()
    if isinstance(data, dict):
        vistos = data.get("emitted")
        if isinstance(vistos, list):
            return {v for v in vistos if isinstance(v, str)}
    return set()


def _save_emitted(path, vistos, now_ts=None):
    """Escrita atomica (tmp + os.replace, atomico em POSIX e Windows)."""
    base = os.path.dirname(path)
    try:
        os.makedirs(base, exist_ok=True)
    except OSError:
        return
    payload = {"emitted": sorted(vistos), "updated_ts": now_ts or time.time()}
    tmp = path + ".{}.tmp".format(os.getpid())
    try:
        with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(payload, fh, ensure_ascii=False)
        os.replace(tmp, path)
    except OSError:
        try:
            os.remove(tmp)
        except OSError:
            pass


def dedupe_for_session(report, event, session_id, state_dir=None, now_ts=None):
    """Suprime sinal ja emitido nesta sessao, so no evento por-turno.

    Fail-open: qualquer falha de IO devolve o relatorio intacto (emitir de
    novo e melhor que engolir um sinal por causa de disco).
    """
    if SS.normalize_event(event) != SS.EVENT_USER_PROMPT_SUBMIT:
        return report
    path = session_state_path(session_id, state_dir=state_dir)
    if not path:
        return report
    try:
        vistos = _load_emitted(path)
        ativos = [s for s in report.signals if s.active]
        novos = [s for s in ativos if _signal_fingerprint(s) not in vistos]
        if ativos:
            _save_emitted(
                path,
                vistos | {_signal_fingerprint(s) for s in ativos},
                now_ts=now_ts,
            )
            prune_state_dir(state_dir=state_dir, now_ts=now_ts)
        # identidade (`is`), nao igualdade: dois Signal com mesmo conteudo
        # nao podem se confundir na filtragem.
        mantidos = [s for s in report.signals if any(s is n for n in novos)]
        return SS.SignalReport(
            signals=mantidos,
            metrics=dict(report.metrics),
            root=report.root,
            now=report.now,
        )
    except Exception:
        return report


def build_hook_output(report):
    """Monta o JSON de resposta. Sempre continue=true."""
    out = {"continue": True}
    human = SS.format_human(report)
    machine = SS.format_machine(report)
    if human or machine:
        # machine (IDs) primeiro para a thread parsear; prosa em seguida.
        ctx_parts = []
        if machine:
            ctx_parts.append(machine)
        if human:
            ctx_parts.append(human)
        out["additionalContext"] = "\n".join(ctx_parts)
    return out


def run_hook(stdin_text=None, now=None, now_ts=None, cfg=None, state_dir=None):
    """Nucleo testavel. Nunca levanta; devolve o dict de saida.

    Ordem: coleta (motor) -> roteia por `hook_event_name` (motor) ->
    dedup por sessao (so no evento por-turno) -> formata.
    """
    try:
        data = parse_hook_stdin(stdin_text)
        root = data.get("cwd") or os.getcwd()
        event = data.get("hook_event_name")
        session_id = data.get("session_id")
        report = SS.collect_signals(root, now=now, cfg=cfg, now_ts=now_ts)
        report = SS.signals_for_event(report, event)
        report = dedupe_for_session(
            report, event, session_id, state_dir=state_dir, now_ts=now_ts
        )
        return build_hook_output(report)
    except Exception:
        return {"continue": True}


def main(argv=None):
    try:
        raw = sys.stdin.read()
    except Exception:
        raw = ""
    out = run_hook(raw)
    try:
        sys.stdout.write(json.dumps(out, ensure_ascii=False))
        sys.stdout.write("\n")
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
