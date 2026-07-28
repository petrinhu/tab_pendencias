# Backlog: Sprawl Repro (mirrors the SPRAWL-1 incident)

## Tickets

| ID | Wave | Group | Description | Priority | Blocked By | Effort | Status | Reviewed |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| #01 | W1 | Core | Canonical item one | High | - | Low | ✅ Concluído | yes |
| #02 | W1 | Core | Canonical item two | High | #01 | Low | ⏳ Pendente | - |
| #03 | W2 | Core | Canonical item three | Medium | #02 | Low | ⏳ Pendente | - |

## Appendix: unrelated reference table (same column count, no ID/Status columns)

In the real-world incident that inspired this fixture, a table like this one
lived hundreds of lines below the canonical table, across a whole extra
section, and got silently swallowed into the canonical item list anyway.

| Metric | Baseline | Target | Owner | Source | Confidence | Window | Note | Date |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| Throughput | 100 | 150 | Team A | Sensor | High | 30d | n/a | 2026-01-01 |
| Latency | 80 | 60 | Team B | Sensor | Medium | 30d | n/a | 2026-01-02 |
