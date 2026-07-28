# Solstice Rollout -- Program Backlog

Another fictitious project (a multi-team program rollout), used only to
prove that `CHK-06` finds every independent dependency cycle, not just the
first one it stumbles on.

## Workstream table

| ID | Wave | Group | Description | Priority | Blocked By | Effort | Status | Reviewed |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| A-1 | W1 | Alpha | Alpha step one | High | A-3 | Low | ⏳ Pendente | - |
| A-2 | W1 | Alpha | Alpha step two | High | A-1 | Low | ⏳ Pendente | - |
| A-3 | W2 | Alpha | Alpha step three | High | A-2 | Low | ⏳ Pendente | - |
| B-1 | W1 | Beta | Beta step one | Medium | B-2 | Low | ⏳ Pendente | - |
| B-2 | W1 | Beta | Beta step two | Medium | B-1 | Low | ⏳ Pendente | - |
| C-1 | W1 | Gamma | Standalone item, no cycle | Low | - | Low | ⏳ Pendente | - |

## Notes

Two independent, unrelated cycles, on purpose: `A-1 -> A-3 -> A-2 -> A-1`
(3-node cycle, team Alpha) and `B-1 -> B-2 -> B-1` (2-node cycle, team
Beta). `C-1` has no prerequisite at all and must not appear in either
cycle. `CHK-06` must report BOTH cycles, never just the first one found.
