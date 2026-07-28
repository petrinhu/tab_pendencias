# Harbor Lights -- Migration Backlog

Another fictitious project (a data-center migration), used only to prove
that `CHK-07` tells apart its two distinct cases: same-wave dependency
versus row-order violation.

## Cutover table

| ID | Wave | Group | Description | Priority | Blocked By | Effort | Status | Reviewed |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| X-1 | W1 | Delta | First step | High | - | Low | ⏳ Pendente | - |
| X-2 | W1 | Delta | Same wave as its own prerequisite (case a) | High | X-1 | Low | ⏳ Pendente | - |
| X-3 | W3 | Delta | Depends on a row listed further down (case b) | Medium | X-4 | Low | ⏳ Pendente | - |
| X-4 | W2 | Delta | Comes after its dependent in row order | Medium | - | Low | ⏳ Pendente | - |

## Notes

Case (a): `X-2` (Wave `W1`) depends on `X-1` (Wave `W1`) -- same wave as a
real dependency, which contradicts "same wave = can run in parallel".
Case (b), isolated on purpose from case (a): `X-3` (Wave `W3`) depends on
`X-4` (Wave `W2`, a DIFFERENT wave, so case a does not also fire here), but
`X-3` is listed BEFORE `X-4` in row order -- violates "row order is the
recommended execution order". Expected: exactly 2 findings, one of each
case.
