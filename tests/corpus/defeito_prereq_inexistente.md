# Nimbus Fleet -- Maintenance Backlog

Another fictitious project (aircraft fleet maintenance scheduling), used
only to prove that `CHK-05` does not assume anything about the author's own
ID scheme or language.

## Work order table

| ID | Wave | Group | Description | Priority | Blocked By | Effort | Status | Reviewed |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| #01 | W1 | Airframe | Ship the loader firmware | High | - | Low | ✅ Concluído | yes |
| #02 | W1 | Airframe | Ship the parser firmware | High | #99 | Medium | ⏳ Pendente | - |
| #03 | W2 | Avionics | Ship the exporter firmware | Low | #01, #99 | Low | ⏳ Pendente | - |

## Notes

`#02` claims to be blocked by `#99`, which was never created (1 invalid
reference). `#03` cites a list of two prerequisites, `#01, #99`: `#01`
exists, `#99` does not (1 more invalid reference). Total: 2 invalid
references expected from `CHK-05`.
