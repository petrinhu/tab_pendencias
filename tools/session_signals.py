#!/usr/bin/env python3
# tools/session_signals.py -- motor de sinais de frescor (Fase 6 / TAB-HOOK-*)
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
tools/session_signals.py

Motor de sinais de frescor da TODO.md (Fase 6). Read-only, offline, sem LLM,
sem rede, sem escrever no TODO. Predicados deterministicos com relogio
injetavel (`now=datetime.date`).

Consumidores: `todo_health.py` (CLI humano) e o adapter de hook
`tools/hooks/tab_pendencias_reminder.py` (SessionStart). A regra de negocio
mora aqui -- o adapter so formata e emite.
"""
from __future__ import annotations

import datetime
import os
import time
from dataclasses import dataclass, field

import todo_lib as L

try:
    import concurrent_inbox as CI
except ImportError:  # pragma: no cover
    CI = None

try:
    import intake_journal as J
except ImportError:  # pragma: no cover
    J = None


SIGNAL_IDS = (
    "TAB_TODO_CREATE_REQUIRED",
    "TAB_STATUS_SYNC_RECOMMENDED",
    "TAB_TRIAGE_REQUIRED",
    "TAB_CONCURRENT_INBOX_PRESENT",
    "TAB_LEADER_DECISION_AGED",
    "TAB_VERIFICATION_AGING",
    "TAB_INTAKE_RECOVERY_REQUIRED",
)

# Mensagens humanas curtas (pt-br). Sem reordenar por relogio (TAB-HOOK-003).
_HUMAN = {
    "TAB_TODO_CREATE_REQUIRED": (
        "Repositorio git sem TODO.md na raiz. Considere "
        "/tab_pendencias --create."
    ),
    "TAB_STATUS_SYNC_RECOMMENDED": (
        "Ha itens ⏳/🔄 e a tabela nao e tocada ha varios commits/dias. "
        "Acao barata: python3 tools/todo_sync.py (nunca reordena)."
    ),
    "TAB_TRIAGE_REQUIRED": (
        "INBOX exige triagem: classifiable, residual envelhecido e/ou "
        "inbox/ concorrente. Rode --drain no proximo ponto seguro "
        "(nao e full reorder por relogio)."
    ),
    "TAB_CONCURRENT_INBOX_PRESENT": (
        "Ha descobertas em inbox/ (fallback entre sessoes). A sessao "
        "principal deve drenar."
    ),
    "TAB_LEADER_DECISION_AGED": (
        "Decisao do lider na INBOX residual envelheceu (cycles ou idade). "
        "Apresentar 2-3 opcoes com trade-offs."
    ),
    "TAB_VERIFICATION_AGING": (
        "Itens em 🔍 Pendente verificacao acumulam sem a tabela ser "
        "tocada -- planeje a onda TST-*/AUD-*."
    ),
    "TAB_INTAKE_RECOVERY_REQUIRED": (
        "Journal de intake tem orfaos (state != DONE). Rode recuperacao "
        "idempotente antes de novo intake."
    ),
}


@dataclass
class Signal:
    id: str
    active: bool
    reasons: list = field(default_factory=list)

    def to_dict(self):
        return {"id": self.id, "active": self.active, "reasons": list(self.reasons)}


@dataclass
class SignalReport:
    """Resultado de collect_signals. `signals` na ordem de SIGNAL_IDS."""
    signals: list = field(default_factory=list)
    metrics: dict = field(default_factory=dict)
    root: str = ""
    now: object = None

    def active(self):
        return [s for s in self.signals if s.active]

    def by_id(self, signal_id):
        for s in self.signals:
            if s.id == signal_id:
                return s
        return None

    def is_active(self, signal_id):
        s = self.by_id(signal_id)
        return bool(s and s.active)

    def to_flags(self):
        """Flags aditivas para o dict de retorno do todo_health."""
        out = {}
        for s in self.signals:
            key = s.id.lower()
            out[key] = s.active
        return out


def _is_todo_work_pending(status):
    """⏳ ou 🔄 apenas (TAB_STATUS_SYNC_RECOMMENDED; 🎨 nao conta)."""
    s = (status or "").strip()
    return s.startswith("⏳") or s.startswith("🔄")


def todo_touch_stats(root, now_ts=None):
    """(commits_since_touch, days_since_touch) do ultimo commit em TODO.md.

    TODO.md untracked ou sem baseline: commits=None; dias via mtime se
    o arquivo existir. Fora de repo git: (None, None) se sem arquivo.
    """
    if now_ts is None:
        now_ts = time.time()
    todo = L.find_todo(root)
    if not todo:
        return None, None

    if L.repo_root(root) is None:
        try:
            m = os.path.getmtime(todo)
        except OSError:
            return None, None
        return None, max(0.0, (now_ts - m) / 86400.0)

    h = L.git(["log", "-1", "--format=%H", "--", "TODO.md"], cwd=root).strip()
    if not h:
        try:
            m = os.path.getmtime(todo)
        except OSError:
            return None, None
        return None, max(0.0, (now_ts - m) / 86400.0)

    commits = None
    c = L.git(["rev-list", "--count", f"{h}..HEAD"], cwd=root).strip()
    if c.isdigit():
        commits = int(c)

    days = None
    ct = L.git(["log", "-1", "--format=%ct", "--", "TODO.md"], cwd=root).strip()
    if ct.isdigit():
        days = max(0.0, (now_ts - int(ct)) / 86400.0)
    else:
        try:
            m = os.path.getmtime(todo)
            days = max(0.0, (now_ts - m) / 86400.0)
        except OSError:
            days = None
    return commits, days


def collect_signals(root, now=None, cfg=None, now_ts=None):
    """Avalia todos os SIGNAL_IDS no repositorio `root`.

    `now`: datetime.date injetavel (aging). `now_ts`: epoch float para
    commits/dias desde toque no TODO.md. `cfg`: dict de limiares (defaults
    via load_signals_config). Nunca levanta para o hook (falhas parciais
    degradam o sinal afetado).
    """
    if now is None:
        now = datetime.date.today()
    if now_ts is None:
        now_ts = time.time()
    root = os.path.abspath(root) if root else ""
    todo = L.find_todo(root) if root else None
    if cfg is None:
        cfg = L.load_signals_config(todo)

    max_cycles = int(cfg.get("triage_max_cycles", 2))
    max_age_days = int(cfg.get("triage_max_age_days", 1))
    verif_min_count = int(cfg.get("verification_aging_min_count", 5))
    verif_min_days = int(cfg.get("verification_aging_min_days", 7))
    sync_min_commits = int(cfg.get("status_sync_min_commits", 5))
    sync_min_days = int(cfg.get("status_sync_min_days", 3))

    metrics = {
        "has_todo": bool(todo),
        "is_git": bool(root and L.repo_root(root)),
        "n_items": 0,
        "n_pending_work": 0,  # ⏳/🔄
        "n_verif": 0,
        "inbox_count": 0,
        "classifiable_count": 0,
        "residual_count": 0,
        "aged_residual_count": 0,
        "needs_leader_count": 0,
        "needs_leader_aged_count": 0,
        "concurrent_inbox_count": 0,
        "journal_orphan_count": 0,
        "commits_since_todo_touch": None,
        "days_since_todo_touch": None,
    }

    signals_map = {sid: Signal(id=sid, active=False, reasons=[])
                   for sid in SIGNAL_IDS}

    # --- CREATE: git sem TODO.md ---
    if metrics["is_git"] and not todo:
        signals_map["TAB_TODO_CREATE_REQUIRED"].active = True
        signals_map["TAB_TODO_CREATE_REQUIRED"].reasons.append("git_sem_todo")

    commits, days = (None, None)
    if todo:
        commits, days = todo_touch_stats(root, now_ts=now_ts)
    metrics["commits_since_todo_touch"] = commits
    metrics["days_since_todo_touch"] = days

    text = ""
    items = []
    if todo:
        try:
            with open(todo, encoding="utf-8") as fh:
                text = fh.read()
        except OSError:
            text = ""
        tbl = L.parse_table(text) if text else None
        if tbl:
            items = tbl["items"]
            metrics["n_items"] = len(items)

    n_pending_work = sum(1 for it in items if _is_todo_work_pending(it["status"]))
    n_verif = sum(1 for it in items if L.is_awaiting_verification(it["status"]))
    metrics["n_pending_work"] = n_pending_work
    metrics["n_verif"] = n_verif

    entries = L.inbox_entries(text) if text else []
    classifiable = [e for e in entries if e["classifiable"]]
    residual = [e for e in entries if not e["classifiable"]]
    metrics["inbox_count"] = len(entries)
    metrics["classifiable_count"] = len(classifiable)
    metrics["residual_count"] = len(residual)

    aged_residual = []
    leader_aged = []
    needs_leader = []
    for e in residual:
        reason = (e.get("triage") or {}).get("fields", {}).get("reason")
        if reason == "needs-leader-decision":
            needs_leader.append(e)
        if L.residual_is_aged(
            e, now=now, max_cycles=max_cycles, max_age_days=max_age_days
        ):
            aged_residual.append(e)
            if reason == "needs-leader-decision":
                leader_aged.append(e)
    metrics["aged_residual_count"] = len(aged_residual)
    metrics["needs_leader_count"] = len(needs_leader)
    metrics["needs_leader_aged_count"] = len(leader_aged)

    concurrent_count = 0
    if CI is not None and root:
        try:
            concurrent_count = CI.count_pending(root)
        except Exception:
            concurrent_count = 0
    metrics["concurrent_inbox_count"] = concurrent_count

    orphan_count = 0
    if J is not None and root:
        try:
            jd = J.journal_dir_for(cwd=root)
            if jd:
                orphan_count = len(J.list_orphans(jd))
        except Exception:
            orphan_count = 0
    metrics["journal_orphan_count"] = orphan_count

    # --- STATUS_SYNC: ⏳/🔄 E (commits>=N OU days>=D) ---
    if n_pending_work > 0 and todo:
        bate_c = commits is not None and commits >= sync_min_commits
        bate_d = days is not None and days >= sync_min_days
        if bate_c or bate_d:
            sig = signals_map["TAB_STATUS_SYNC_RECOMMENDED"]
            sig.active = True
            if bate_c:
                sig.reasons.append(f"commits_since_todo_touch={commits}")
            if bate_d:
                sig.reasons.append(
                    f"days_since_todo_touch={int(days) if days is not None else days}"
                )
            sig.reasons.append(f"pending_work={n_pending_work}")

    # --- CONCURRENT ---
    if concurrent_count > 0:
        signals_map["TAB_CONCURRENT_INBOX_PRESENT"].active = True
        signals_map["TAB_CONCURRENT_INBOX_PRESENT"].reasons.append(
            f"inbox_files={concurrent_count}"
        )

    # --- TRIAGE: classifiable OU residual aged OU concurrent
    # (NAO inbox_count>=3 so de leader novos -- ADR-0002 F9 refinado) ---
    triage_reasons = []
    if classifiable:
        triage_reasons.append(f"classifiable={len(classifiable)}")
    if aged_residual:
        triage_reasons.append(f"aged_residual={len(aged_residual)}")
    if concurrent_count > 0:
        triage_reasons.append(f"concurrent_inbox={concurrent_count}")
    if triage_reasons:
        signals_map["TAB_TRIAGE_REQUIRED"].active = True
        signals_map["TAB_TRIAGE_REQUIRED"].reasons.extend(triage_reasons)

    # --- LEADER_AGED ---
    if leader_aged:
        signals_map["TAB_LEADER_DECISION_AGED"].active = True
        signals_map["TAB_LEADER_DECISION_AGED"].reasons.append(
            f"aged_leader={len(leader_aged)}"
        )

    # --- VERIFICATION_AGING: n_verif>=5 OU (n_verif>=1 e days>=7) ---
    if n_verif >= verif_min_count or (
        n_verif >= 1 and days is not None and days >= verif_min_days
    ):
        sig = signals_map["TAB_VERIFICATION_AGING"]
        sig.active = True
        sig.reasons.append(f"n_verif={n_verif}")
        if days is not None and days >= verif_min_days:
            sig.reasons.append(f"days_since_todo_touch={int(days)}")

    # --- RECOVERY: journal orphans ---
    if orphan_count > 0:
        signals_map["TAB_INTAKE_RECOVERY_REQUIRED"].active = True
        signals_map["TAB_INTAKE_RECOVERY_REQUIRED"].reasons.append(
            f"orphans={orphan_count}"
        )

    ordered = [signals_map[sid] for sid in SIGNAL_IDS]
    return SignalReport(
        signals=ordered, metrics=metrics, root=root, now=now
    )


def format_machine(report):
    """Uma linha por sinal ativo: `TAB_ID reason1,reason2`."""
    lines = []
    for s in report.signals:
        if not s.active:
            continue
        if s.reasons:
            lines.append(f"{s.id} {','.join(s.reasons)}")
        else:
            lines.append(s.id)
    return "\n".join(lines)


def format_human(report):
    """Prosa curta para additionalContext do hook / stdout do health."""
    parts = []
    for s in report.signals:
        if not s.active:
            continue
        body = _HUMAN.get(s.id, s.id)
        if s.reasons:
            parts.append(f"{s.id}: {body} ({', '.join(s.reasons)})")
        else:
            parts.append(f"{s.id}: {body}")
    return "\n".join(parts)
