# AUD-CAMPANHA-VERIF — verificação formal campanha v1.2 (🔍 → ✅)

**Data:** 2026-08-16  
**Papel:** QA engineer (bigtech)  
**Repo:** `tab_pendencias` (produto)  
**SHA base da suíte:** `01ec8de4215ffcd69f3447c049211d29dd121efe` (`main`)  
**Escopo:** 65 itens em `🔍 Pendente verificação` da campanha v1.2 (não legados `💡`).

## Comandos executados

```bash
python3 -m pytest tests/ -q --tb=line
python3 tools/ci/guard_stdlib_imports.py
python3 tools/ci/guard_no_real_fixtures.py
python3 tools/todo_health.py | head -20
python3 scripts/dogfood_metrics.py
```

## Resultado da suíte

| Gate | Resultado |
| :--- | :--- |
| `pytest tests/` | **PASS** — 746 passed, 47 skipped, 1 xfailed (~22 s) |
| `guard_stdlib_imports` | **PASS** — 24 arquivos, 0 import fora da stdlib |
| `guard_no_real_fixtures` | **PASS** (após higiene BUS-1; ver nota) |
| `todo_health` (pós-promoção) | 66 ✅, 0 🔍, classifiable=0 |
| `dogfood_metrics` | `classifiable==0 OK` |

### Nota de higiene (guard fixtures)

Na 1ª corrida o `guard_no_real_fixtures` saiu **rc=1** com 4 achados locais (camadas 2/3 via `.guard_forbidden_terms` não versionado): menção a nome real de consumidor na linha `BUS-1` do `TODO.md` e em `docs/auditoria/BUS-1-relay-D1.md`.  
**Ação QA:** neutralização para “consumidor B” / path genérico (sem alterar o SHA de entrega do bus `c284ede…`). Re-execução do guard: **0 achados**.

Nenhum FAIL de teste ou de guard permanece na matriz final.

## Critério de promoção

- ✅ **PASS** = evidência executada (pytest/guard/smoke de script) **ou** artefato canônico + smoke de existência quando o item é doc/release (famílias VAULT/CUT/REL/MDASH/PYFLOOR/SKILL-DESC/HOOKSRC/BUS-1).
- Residual 🔍: **nenhum** — todos os 65 têm evidência suficiente.

## Matriz ID → evidência → veredito

| ID | Evidência (repo-relative) | Veredito |
| :--- | :--- | :--- |
| BUS-1 | `docs/auditoria/BUS-1-relay-D1.md` (entrega bus commit `c284ede…`) | PASS |
| AUD-FUP-1 | `tests/test_todo_fix.py` (`test_provar_invariantes_recusa_divergencia_so_trailing_space`, `…_so_cr_de_crlf`, + aceita/recusa) | PASS |
| AUD-FUP-2 | `tests/test_guard_no_real_fixtures.py` (`check_table_sizes`, `check_forbidden_path_names`, `main`) | PASS |
| AUD-FUP-3 | `TESTES.md` (nota skip cache frio + ruff não-gate) | PASS |
| TAB-SOT-007 | `tests/test_submodule_pin_drift.py` (33 testes) + `tools/submodule_pin_drift.py` | PASS |
| TAB-ADD-001 | `tests/test_todo_intake.py` + `tests/test_fase10_corpus.py` + `tools/todo_intake.py` | PASS |
| TAB-ADD-005 | `tests/test_todo_intake.py` (SCOPED) + F10-24/25 | PASS |
| TAB-ADD-006 | `tests/test_todo_intake.py` (FULL) + F10-04/11/12 | PASS |
| TAB-ADD-007 | `tests/test_todo_intake.py` (strip residual / DUPLICATE) | PASS |
| TAB-ADD-002 | `tests/test_todo_intake.py` + F10-06/07 (dedup descrição) | PASS |
| TAB-INBOX-001 | `tests/test_todo_intake.py` + `tests/test_skill_inbox_semantics.py` | PASS |
| TAB-INBOX-002 | `tests/test_todo_health.py` + `tests/test_session_signals.py` (`TAB_TRIAGE_REQUIRED`) | PASS |
| TAB-INBOX-003 | `tests/test_todo_intake.py` + `tests/test_fase10_properties.py` (`classifiable_zero_after_apply`) | PASS |
| TAB-INBOX-004 | `tests/test_todo_intake.py` (`run_drain` + judgments) + F10-21/23 | PASS |
| TAB-INBOX-005 | `tests/test_todo_intake.py` (intake antes de strip; skip_classifiable) | PASS |
| INTAKE-AGE-1 | `tests/test_session_signals.py` (`residual_is_aged`) + `tools/todo_lib.py` | PASS |
| TAB-HOOK-001 | `tests/test_session_signals.py` + `tests/test_session_hook_adapter.py` | PASS |
| TAB-HOOK-002 | `tests/test_session_signals.py` (machine+human `TAB_*`) | PASS |
| TAB-HOOK-003 | `references/sinais-de-frescor.md` + sinais (triagem ≠ full reorder por relógio) | PASS |
| TAB-HOOK-004 | `tests/test_session_hook_adapter.py` + `tools/hooks/tab_pendencias_reminder.py` | PASS |
| PYFLOOR-2 | `pyproject.toml` `requires-python = ">=3.11"` + `README.md` | PASS |
| MDASH-2 | `.tab_pendencias.allow_emdash` + `README.md` (exceção documentada) | PASS |
| HOOKSRC-1 | `docs/auditoria/HOOKSRC-1-e-TAB-REL-003-bloco-colar.md` + `tools/hooks/`; smoke: githooks publicados apontam skill pinada | PASS |
| VERB-STATUS-2 | `tests/test_pred_fallback_w15.py` (`status_so_verbo` → unknown) + composite | PASS |
| SKILL-DESC-2 | `SKILL.md` frontmatter `description` + `argument-hint` (anuncia audit/fix/add/drain) | PASS |
| FIX-ESCOPO-2 | `README.md` + ADR-0001 (duas classes: `escapar_pipe_cru`, `remover_fragmento_duplicado`) | PASS |
| TAB-WSJF-001 | `tests/test_wsjf.py` (fib scale, normalize reject/snap) | PASS |
| TAB-WSJF-002 | `tests/test_wsjf.py` (early labels / safe ints) | PASS |
| TAB-WSJF-003 | `tests/test_wsjf.py` (`topology_before_wsjf`, `order_levels_then_wsjf`) | PASS |
| TAB-WSJF-004 | `tests/test_wsjf.py` (scoring local / peers) | PASS |
| TAB-WSJF-005 | `tests/test_wsjf.py` (`stable_rank_*`, WIP pin, determinismo) | PASS |
| TAB-WSJF-006 | `tests/test_wsjf.py` (`explain_move_exact_format`) | PASS |
| TAB-WSJF-007 | `tests/test_wsjf.py` + `tests/test_bus_contract.py` (source=bus) | PASS |
| TAB-CONC-001 | `tests/test_intake_agent_bridge.py` + `templates/agents/implementer-discovery-contract.md` | PASS |
| TAB-CONC-002 | `tests/test_concurrent_inbox.py` + `tools/concurrent_inbox.py` | PASS |
| TAB-CONC-003 | `tests/test_todo_health.py` + `tests/test_session_signals.py` (`TAB_CONCURRENT_INBOX_PRESENT`) | PASS |
| TAB-CONC-004 | `tests/test_todo_lock.py` (7) + apply sob lock em intake/fix | PASS |
| FIX-RISCO-A | `tests/test_todo_fix.py` (apply adquire `TodoWriteLock`; timeout) | PASS |
| FIX-RISCO-B | `tests/test_todo_fix.py` (lock + re-check; dry-run sem lock) | PASS |
| FIX-RISCO-C | `tests/test_todo_fix.py` (OSError/PermissionError em `os.replace`) | PASS |
| TAB-VAULT-001 | `templates/vault/CLAUDE.md.fragment.md` + `SKILL.md` (INBOX exception queue) | PASS |
| TAB-VAULT-002 | `templates/vault/tabela-pendencias-frescor.overlay.md` | PASS |
| TAB-VAULT-003 | `templates/agents/implementer-discovery-contract.md` | PASS |
| TAB-VAULT-004 | `templates/vault/settings.sanitized.hook-snippet.json` (path relativo skill; sem path de máquina) | PASS |
| TAB-VAULT-005 | `tests/test_recovery_drill.py` + `scripts/recovery_drill.py` | PASS |
| TAB-BUS-001 | `tests/test_bus_contract.py` + `tools/bus_contract.py` | PASS |
| TAB-BUS-002 | `tests/test_bus_contract.py` (`archive_allowed`) | PASS |
| TAB-BUS-003 | `references/bus-versus-inbox.md` + `tests/corpus/bus/` | PASS |
| TAB-HUB-001 | `tests/test_hub_guard.py` + `references/hub-agregador.md` + F10-26 | PASS |
| TAB-CUT-001 | `tests/test_todo_intake.py` (`legacy_inbox_line`) + compat drain | PASS |
| TAB-CUT-002 | `tests/test_dogfood_metrics.py` + `scripts/dogfood_metrics.py` (dogfood real: classifiable=0) | PASS |
| TAB-CUT-003 | `references/cutover-and-rollback.md` (canaries project-small/large) | PASS |
| TAB-CUT-004 | `tests/test_dogfood_metrics.py` + reference (métricas before/after) | PASS |
| TAB-CUT-005 | `references/cutover-and-rollback.md` (rollback sem apagar candidatos) | PASS |
| TAB-TST-001 | `tests/test_fase10_corpus.py` F10-01..26 | PASS |
| TAB-TST-002 | `tests/test_fase10_properties.py` (5 propriedades) | PASS |
| TAB-TST-003 | `tests/test_contract_real_corpus.py` (+ política CONTR-1/AC-REAL) | PASS |
| TAB-TST-004 | `tests/test_fase10_mutation.py` (mutação em cópia; tools/ intocado) | PASS |
| TAB-TST-005 | `tests/test_fase10_e2e_install.py` | PASS |
| TAB-SEC-001 | `tests/test_fase10_compat_sec.py` (fixtures sintéticas + guards) | PASS |
| TAB-COMPAT-001 | `tests/test_fase10_compat_sec.py` (8/9 cols, offline, INBOX legada) | PASS |
| TAB-REL-001 | `docs/auditoria/RELEASE-1.2.0-CHECKLIST.md` + `CHANGELOG.md` [1.2.0] | PASS |
| TAB-REL-002 | checklist release + tags locais `v1.2.0`/`v1.2.1` (push/tag já autorizados 16/08) | PASS |
| TAB-REL-003 | `docs/auditoria/HOOKSRC-1-e-TAB-REL-003-bloco-colar.md` (pin consumidor) | PASS |
| TAB-REL-004 | checklist + prova clone fresco documentada (autorizada 16/08) | PASS |

## Contagens

| Métrica | Antes | Depois |
| :--- | ---: | ---: |
| Itens 🔍 (campanha) | 65 | 0 |
| Itens ✅ (total tabela) | 1 | 66 |
| Itens 💡 (legados — **não tocados**) | (inalterados) | (inalterados) |
| FAIL na matriz | 0 (final) | 0 |
| Residual 🔍 sem evidência | — | **0** |

## Atualização da tabela

Para os 65 IDs da matriz:

- **Status** → `✅ Concluído`
- **Estado Auditado** → `TST+AUD 2026-08-16 (AUD-CAMPANHA-VERIF)`

Legados `💡` **não** foram alterados.

## Restrições respeitadas

- Sem push.
- Sem PASS inventado: pytest executado; guards re-executados verdes.
- Relatório sem paths absolutos de máquina (exceto nota operacional de githooks como smoke de HOOKSRC-1 no ambiente do autor).
- Higiene BUS-1: designação neutra “consumidor B” no texto versionado.
