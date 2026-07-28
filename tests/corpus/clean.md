# Aurora Widgets -- Engineering Backlog

This file tracks outstanding engineering work for the packaging automation
line at a fictitious company. It does not resemble any real project: the
section names, the prose around the table, and the ID scheme are all
invented for the sole purpose of proving that `tab_pendencias` does not
assume anything about a specific codebase.

Update the Status cell whenever a ticket changes state. Do not reorder rows
by hand -- that is a separate, deliberate operation.

## Ticket table

| ID | Wave | Group | Description | Priority | Blocked By | Effort | Status | Reviewed |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| #01 | W1 | Core | Bootstrap the packaging line simulator | High | - | Medium | ✅ Concluído | yes |
| #02 | W1 | Core | Wire the conveyor belt sensor driver | High | #01 | Medium | 🔄 Em andamento | - |
| #03 | W2 | Safety | Add emergency stop debounce logic | High | #02 | Low | ⏳ Pendente | - |
| #04 | W2 | Reporting | Draft the shift handover report template | Medium | - | Low | 🔍 Pendente verificação | - |
| #05 | W3 | Safety | Spec the guard rail interlock | Medium | #03 | Medium | 🎨 Pendente design | - |
| #06 | W3 | Core | Decide on the retry backoff strategy | Low | - | Low | 💡 Decisão tomada | - |
| #07 | W4 | Reporting | Reconcile the weekly defect counters | Low | #04 | Low | 🟡 Parcial | - |

## Notes

This table is clean by design: it is the negative control used to prove the
absence of false positives. Every one of the seven canonical statuses
appears exactly once, on purpose.
