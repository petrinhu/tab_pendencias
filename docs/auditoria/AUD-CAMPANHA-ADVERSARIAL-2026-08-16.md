# AUD-CAMPANHA-ADVERSARIAL -- revisao com dente (campanha v1.2)

<!-- markdownlint-disable MD029 -->

**Auditor:** feature-dev:code-reviewer (nao implementou as fatias; nao e o QA)
**Data medida:** 2026-08-16 22:10:40 (`date '+%d/%m/%y - %H:%M:%S'` = `16/08/26 - 22:10:40`)
**HEAD auditado (blobs):** `01ec8de4215ffcd69f3447c049211d29dd121efe` (`v1.2.1`, `origin/main`)
**Arvore do produto:** mutacao **nao** aplicada in-place. Mutantes so em `/var/tmp/tab_aud_adv_229683*`.
**TODO.md / status:** **nao alterados por este auditor.** O QA promoveu `🔍` → `✅` em paralelo (n_verif 65 → 0 durante esta sessao). Relatorio de QA nao e prova -- medi o motor e os bindings de novo.

> Papel: assumir que a equipe esta errada. So aceitar NAO com evidencia reproduzivel. Relatorio de agente anterior nao e prova.

---

## Veredito

**APROVA COM RESSALVAS.**

Nenhum P0 de motor que impeça `✅`. **Nenhum ID deve ser revertido de `✅` por esta auditoria.**

Ressalvas (nao bloqueiam a campanha; nao sao P0):

1. **IMPORTANTE (prosa da skill, residual AUD-EXTREME Q3):** `SKILL.md:85-87` e `:182-186` ainda dizem que `--drain` / `--create` / `--reorder` **esvaziam o `inbox/`**. O motor de `--drain` **nao le nem apaga** `inbox/*.md` (`concurrent_inbox.py` so tem `write_discovery` / `list_pending` / `read_discovery` / `count_pending`). Um agente que "esvaziar" apagando arquivos apos drain verde **perderia** descoberta. A secao TAB-CONC (`SKILL.md:369-378`) contradiz e esta correta (uniao; dreno via bridge+intake por arquivo). Nao e perda no Python.
2. **COSMETICO (arquivo morto na maquina):** `~/.claude/hooks/tab_pendencias_reminder.py` (44 linhas, md5 `839d1a4e…`) ainda existe. **Nao esta wired.** `settings.json` SessionStart e UserPromptSubmit apontam para `$HOME/.claude/skills/tab_pendencias/tools/hooks/tab_pendencias_reminder.py` (md5 `033448a7…` = produto HEAD). Residual do Q11 de AUD-EXTREME; o binding vivo fechou.
3. **COSMETICO (prosa do item HOOKSRC-1):** a descricao no `TODO.md` ainda cita pin `5d42412`. O pin **vivo** e `01ec8de` / `v1.2.1`. O estado real e mais novo que o texto.

---

## 0. Estado medido (nao declarado)

| Superficie | SHA / fato |
|---|---|
| `HEAD` local `main` | `01ec8de4215ffcd69f3447c049211d29dd121efe` |
| tag peeled `v1.2.1` | **mesmo SHA** |
| `origin/main` (`git ls-remote`) | **mesmo SHA** |
| checkout `~/.claude/skills/tab_pendencias` | `01ec8de` (`v1.2.1`) |
| gitlink `claude-memory` `HEAD` `skills/tab_pendencias` | `160000 commit 01ec8de…` |
| commit do pin no consumidor | `37a118f` `chore(submodule): pin tab_pendencias v1.2.1 (01ec8de)` -- **esta em `github/main`** |
| `~/.claude/githooks` | symlink → `~/.claude/skills/tab_pendencias/tools/hooks` (**publicado**, nao `Projects/…/dev`) |
| `core.hooksPath` (local deste repo e global) | `~/.claude/githooks` |
| md5 shims produto vs publicados | **identicos** (`_chain.sh` `eb714e07…`, `post-commit` `ccd8e646…`, pass-through `0d0181fe…`, reminder `033448a7…`) |
| `~/.grok/skills/tab_pendencias` | symlink para o checkout de **dev** -- **por desenho** da casa Grok; fora do escopo HOOKSRC |
| dogfood (antes e depois do flip do QA) | `classifiable==0` OK; `inbox_total=0`; `residual=0` |
| status da tabela (pos-QA, 22:09) | 112 linhas; **66 ✅**, **46 💡**, **0 ⏳**, **0 🔄**, **0 🔍** |
| sinal ativo pos-QA | nenhum (`TAB_VERIFICATION_AGING` apagou quando n_verif foi a 0) |

`scripts/dogfood_metrics.py` exit 0. `todo_intake.classifiable_inbox_count(TODO.md) == 0`. `todo_lib.inbox_entries` vazio.

---

## 1. Mutation spot (`/var/tmp`, arvore do repo intocada)

Extracao: `git archive HEAD` → `/var/tmp/tab_aud_adv_229683`. Tres copias independentes. `grep MUTANT tools/{todo_intake,wsjf,session_signals}.py` no produto = vazio **antes e depois**.

Baseline (copia sem mutante, mesmos testes-alvo): **4 passed**.

### M1 -- `todo_intake.decide_route`: fundacao forca L0

- Arquivo: `/var/tmp/tab_aud_adv_229683-m1-intake-foundation-l0/tools/todo_intake.py:439`
- Mutacao: `is_foundation` → `return ROUTE_LOCAL_INTEGRATION` (em vez de `ROUTE_FULL_REORDER`)
- Suíte: `1 failed, 4 passed` em 0,18 s
- Morto por: `tests/test_todo_intake.py::test_decide_route_full_reorder_por_fundacao:189`
  (`LOCAL_INTEGRATION` != `FULL_REORDER`)
- Nao morto por: `test_decide_route_local_integration`, `test_decide_route_default_full_reorder`, `test_cascata_dup_vence_fields_incomplete`, `test_prop_apply_2_full_topology_and_wip` (nenhum deles e fundacao)

### M2 -- `wsjf.stable_rank_within_level`: ignora pins WIP

- Arquivo: `/var/tmp/tab_aud_adv_229683-m2-wsjf-ignore-pins/tools/wsjf.py` (`pin = set()`)
- Mutacao: barreiras de segmento some; item livre de WSJF alto atravessa WIP
- Suíte: `3 failed, 1 passed` em 0,24 s
- Morto por:
  - `tests/test_wsjf.py::test_stable_rank_pinned_wip_not_overtaken:205` (`['X','Y']` != `['Y','X']`)
  - `tests/test_todo_intake.py::test_full_wip_pin_not_preempted_by_higher_wsjf:1115`
  - `tests/test_fase10_properties.py::test_prop_apply_2_full_topology_and_wip:222`
    (ordem mutante `#04,#05,#01,#02` -- peer WSJF alto passou o pin `#02`)
- Nao morto por: `test_stable_rank_material_delta_swaps` (sem pin)

### M3 -- `session_signals.collect_signals`: classifiable nao dispara TRIAGE

- Arquivo: `/var/tmp/tab_aud_adv_229683-m3-signals-no-classifiable-triage/tools/session_signals.py` (`if False and classifiable`)
- Suíte: `1 failed, 3 passed` em 0,10 s
- Morto por: `tests/test_session_signals.py::test_classifiable_fires_triage:218`
  (`is_active('TAB_TRIAGE_REQUIRED')` ficou `False`)
- Nao morto por: leader-aged / residual-aged / cinco leaders frescos (outros gatilhos)

### Suíte de mutacao ja commitada

`python3 -m pytest tests/test_fase10_mutation.py`: **5 passed** (0,21 s). Cobre identity de `topology_before_wsjf`, L0-em-fundacao, `residual_is_aged` sempre False, `BUS_SOURCES` vazio, e isolamento em `/var/tmp`. Independente dos tres mutantes novos acima.

**Conclusao mutation:** a suíte **pega** os dois eixos pedidos (intake/wsjf/signals). Nao e cobertura de vaidade: M2 morre em tres camadas (unidade + apply FULL + propriedade F10).

---

## 2. HOOKSRC -- githooks nao apontam para `Projects/dev`

**NAO apontam.** Medido:

```text
readlink ~/.claude/githooks
  -> /home/petrus/.claude/skills/tab_pendencias/tools/hooks
realpath ~/.claude/githooks
  -> .../.claude/skills/tab_pendencias/tools/hooks
contains Projects/tab_pendencias: False
contains IDrive: False
shims -> Projects/dev: NONE
_chain.sh nao menciona Projects/ nem IDrive
```

`core.hooksPath` (global e deste repo) = `~/.claude/githooks`, que resolve para o **submodulo pinado**, nao para `/home/petrus/IDrive/.../Projects/tab_pendencias/tools/hooks`.

SessionStart/UserPromptSubmit vivos usam o **mesmo** adapter publicado (`skills/tab_pendencias/tools/hooks/tab_pendencias_reminder.py`). Q11 de AUD-EXTREME (settings no reminder antigo de 313 linhas) **fechou** no binding.

O arquivo orfao `~/.claude/hooks/tab_pendencias_reminder.py` e um adapter fino (44 linhas) que *se* fosse chamado cairia no skill publicado primeiro e so depois no symlink Grok (dev). Nao esta no `settings.json`. Nao viola HOOKSRC.

---

## 3. Pin Claude skill == produto HEAD

**SIM, byte a byte no gitlink e no checkout.**

| Ponta | SHA |
|---|---|
| produto `HEAD` | `01ec8de4215ffcd69f3447c049211d29dd121efe` |
| produto `origin/main` | `01ec8de…` |
| tag `v1.2.1^{}` | `01ec8de…` |
| `git -C ~/.claude/skills/tab_pendencias rev-parse HEAD` | `01ec8de…` |
| `git -C ~/.claude ls-tree HEAD skills/tab_pendencias` | `160000 commit 01ec8de…` |
| `git -C ~/.claude submodule status` | `01ec8de… (v1.2.1)` |
| pin commit no consumidor | `37a118f` **contido em `github/main`** |

AUD-EXTREME Q9 (GitHub atrasado) e Q10 (pin v1.1.0 / 15 commits atras, sem `session_signals.py`) **nao se reproduzem** neste HEAD. `session_signals.py` existe no pin.

`TAB-SOT-007` continua warning-only e o gemeo CI do consumidor **nao esta ligado** -- residual de processo, nao drift atual.

---

## 4. `classifiable==0` e `⏳` campanha == 0

**SIM nos dois eixos, medido duas vezes** (antes do flip do QA e depois).

| Metrica | Antes (22:07) | Depois (22:09) |
|---|---|---|
| `inbox_total` | 0 | 0 |
| `classifiable` | 0 | 0 |
| `residual` | 0 | 0 |
| `⏳` (status) | 0 | 0 |
| `🔍` | 65 (onda de verificacao) | 0 (QA promoveu) |
| `n_verif` | 65 | 0 |
| `TAB_VERIFICATION_AGING` | ativo (`n_verif=65`) | inativo |

Nenhuma linha de campanha (`TAB-*`, `INTAKE-*`, `HOOKSRC-1`, `PYFLOOR-2`, `MDASH-2`, …) esta `⏳`. Os 46 `💡` sao backlog **legado cancelado** (anti-OE pos-v1.2), nao campanha aberta.

Este auditor **nao** tocou `Status`. O flip `🔍`→`✅` e do QA (`docs/auditoria/AUD-CAMPANHA-VERIF-2026-08-16.md`).

---

## 5. Dominos do AUD-EXTREME-01 (so o que esta campanha prometeu fechar)

| Q | AUD-EXTREME (HEAD `db3ee8a`) | Agora (`01ec8de`) |
|---|---|---|
| Q3 overclaim `inbox/` | prosa da skill | **ainda la** (ressalva 1) |
| Q9 GitHub atrasado | SIM / `TAB-REL-004` | **NAO** -- `origin/main` == HEAD |
| Q10 pin velho | SIM / pin `319dd5e` | **NAO** -- pin == HEAD == `v1.2.1` |
| Q11 SessionStart antigo | SIM | **NAO** no binding vivo; arquivo orfao residual |
| Q14 drain apaga linha antes do intake | SIM / sem item | **NAO** -- `todo_intake.py:2266-2346` intake **antes** do strip; `tests/test_todo_intake.py::test_drain_intake_fail_preserva_inbox_e_todo_byte_igual` |

Q14 fechado no codigo (TAB-INBOX-005). Nao reabri.

---

## 6. IDs e `✅`

**Nenhum ID deve deixar de virar (ou deve voltar de) `✅` por P0 desta auditoria.**

O overclaim do `inbox/` e documentacao, nao falha do motor. Nao rebaixa TAB-INBOX-* / TAB-CONC-* / TAB-HOOK-*. Se o orquestrador quiser higiene da prosa, e item **novo** (nao reabrir legado `💡`).

---

## 7. O que esta auditoria nao fez

- Nao rodou a suíte pytest completa (746) -- isso e do QA; aqui so mutacao + alvos que matam mutante + `test_fase10_mutation.py`.
- Nao push. Nao tag. Nao alterou `TODO.md`.
- Nao reescreveu `SKILL.md` (auditor != implementer).
- Copias em `/var/tmp/tab_aud_adv_229683*` podem ser apagadas pelo orquestrador (`gio trash` / pedido ao lider). Nao estao no tracking.

---

## 8. Prova de isolamento

```text
grep MUTANT tools/todo_intake.py tools/wsjf.py tools/session_signals.py
  -> (vazio)
git status --short   # neste auditor, so o presente relatorio (TODO.md
                     # e BUS-1-relay foram tocados pelo QA em paralelo)
```
