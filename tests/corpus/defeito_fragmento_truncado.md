# Backlog: Halcyon Export Artifact

Ticket `#02` simulates a file that got cut off mid-write (a crashed editor,
a truncated `scp`, or similar): the row has far fewer cells than the header
promises. `#01` and `#03` around it are well-formed and must stay visible.

| ID | Wave | Group | Description | Priority | Blocked By | Effort | Status | Reviewed |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| #01 | W1 | Tooling | Ship the first candidate | High | - | Low | ✅ Concluído | yes |
| #02 | W1 | Tooling | Truncated row, file got cut off mid-write | High | #01
| #03 | W2 | Tooling | Row after the truncation, still well-formed | Low | #01 | Low | ⏳ Pendente | - |
