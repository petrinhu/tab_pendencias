# Cutover e rollback (TAB-CUT-001..005)

> Reference do produto. Agnostica a projeto. Descreve a janela de
> compatibilidade da INBOX legada, o criterio de dogfood, canaries
> sinteticos, metricas before/after e o modo de rollback sem perda.

## Janela de compat (TAB-CUT-001)

Durante a migracao, o motor **aceita** linhas da secao INBOX no formato
antigo (sem bloco ``[triage ...]``):

- **Sem metadado** (`present=False`): `classifiable=True` por definicao
  (ADR-0002 secao f). O dry-run de ``--drain`` emite o aviso
  ``legacy_inbox_line: <id> (sem [triage ...] -- janela cutover TAB-CUT-001)``.
- **Metadado malformado** (`present=True`, `valid=False`): tambem
  classifiable; drena no proximo ``--drain`` com judgment.
- **Residual valido** (`valid=True`): permanece na exception queue; so
  incrementa ``cycles`` no drain; ``needs-leader-decision`` nao auto-integra.

Nao e necessario editar manualmente todos os ``TODO.md`` existentes.
``--drain`` com ``--judgments-json`` migra as linhas classifiable; apos
apply ok, ``classifiable_inbox_count == 0``.

## Criterio dogfood (TAB-CUT-002)

Primeiro no **proprio** repositorio do produto:

1. Rodar ``python3 scripts/dogfood_metrics.py`` na raiz do repo.
2. Criterio verde: **``classifiable == 0``** (exit 0).
3. Neste repo, o residual legado ``FIX-RISCO`` ja foi drenado
   (``FIX-RISCO-A/B/C`` na tabela; secao INBOX vazia ou so residual com
   triage valido).
4. Novo achado durante o dogfood entra pelo pipeline novo
   (``DISCOVERED_WORK`` / ``--add`` / residual com triage), nunca como
   bullet solto sem metadado.

Exit 2 de ``dogfood_metrics.py`` e **metrica**, nao hard fail de CI
generico: serve de canary de cutover.

## Canary (TAB-CUT-003)

Nao migrar todos os projetos de uma vez. Escolher perfis diferentes com
nomes **sinteticos** (sem nome de projeto real no produto):

| Canary | Perfil |
|---|---|
| `project-small` | TODO curto, poucas ondas, sem bus |
| `project-large` | TODO grande (dezenas/centenas de linhas), multiplas ondas |
| (opcional) `project-bus` | consumidor de bus com mensagens `source=bus` |
| (opcional) `project-multi-session` | `inbox/` concorrente / multiplas worktrees |

Por canary:

1. Baseline com ``dogfood_metrics.py --json`` (gravar fora do repo se
   quiser comparar depois).
2. Rodar ``--drain`` dry-run; se houver ``legacy_inbox_line``, planejar
   judgments e apply com arvore limpa.
3. Repetir metricas; ``classifiable`` deve ir a 0; ``itens perdidos`` = 0.

## Metricas before/after (TAB-CUT-004)

Medir por projeto (script cobre o nucleo mecanico; o resto e checklist
operacional):

| Metrica | Fonte |
|---|---|
| `inbox_total` | `dogfood_metrics` / `inbox_entries` |
| `classifiable` (`inbox_classificable`) | idem |
| `oldest_age_days` (`oldest_inbox_age`) | residual com `since` mais antigo |
| `n_items` / `n_verif` / `n_pending` | tabela canônica |
| sinais `TAB_*` | `session_signals.collect_signals` |
| `discoveries_integrated_same_cycle_pct` | journal / contagem operacional |
| `full_reorders_per_10_discoveries` | journal / logs de intake FULL |
| `scoped_reorders_per_10_discoveries` | idem SCOPED |
| conflitos de merge em TODO | historico git do canary |
| tempo medio descoberta -> item priorizado | operacional |
| duplicatas criadas | journal DUPLICATE + tabela |
| **itens perdidos** | **deve ser 0** (n_antes = integrados + remanescentes + dups) |

Falha de cutover (ADR-0002 F7): `duplicatas criadas > 0` sustentado, ou
conflitos de merge materialmente piores que o baseline pre-migracao.

## Rollback (TAB-CUT-005)

Se o novo intake corromper ordem ou perder trabalho:

1. **Parar escrita automatica** -- nao rodar ``--add`` / ``--drain`` /
   ``--reorder`` com ``--apply``; desligar hooks de escrita se houver.
2. **Preservar** ``.tab_pendencias/journal/`` (ou caminho do journal) e
   arquivos em ``inbox/`` -- nunca limpar para "consertar".
3. **Captura conservadora**: so append de descoberta residual / arquivo
   em ``inbox/``, sem integracao automatica na tabela.
4. **Nunca apagar candidatos** ja coletados (linha INBOX, journal entry,
   arquivo em ``inbox/``).
5. Corrigir a causa no produto, repetir canary em ``project-small`` antes
   de voltar a escrita automatica.

Rollback e **modo de contencao**, nao restauracao permanente da
dependencia de memoria humana para priorizar a fila.

## Gate CUT-11 (checklist)

- [ ] dogfood verde (``classifiable==0`` no produto)
- [ ] canaries verdes (``project-small``, ``project-large``, ...)
- [ ] 0 work lost
- [ ] merge conflicts nao pioraram de forma material
- [ ] same-cycle integration aumentou vs baseline
- [ ] full reorder nao virou rotina para pedido trivial

## Comandos uteis

```text
python3 scripts/dogfood_metrics.py
python3 scripts/dogfood_metrics.py --todo path/to/TODO.md --json
python3 tools/todo_intake.py --drain
python3 tools/todo_intake.py --drain --apply --judgments-json judgments.json
python3 tools/todo_health.py
```
