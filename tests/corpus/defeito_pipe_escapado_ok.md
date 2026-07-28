# Backlog: Nebula Pipeline Utilities (escaped variant)

Same scenario as the unescaped-pipe fixture, except the `|` inside the
Description cell of `#01` is correctly GFM-escaped as `\|`. This is a
POSITIVE control: the row MUST parse normally, with the escaped pipe
preserved verbatim inside the Description text.

| ID | Wave | Group | Description | Priority | Blocked By | Effort | Status | Reviewed |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| #01 | W1 | Tooling | Prove `nm libx.a \| grep -c foo` returns zero (escaped) | High | - | Medium | 🔄 Em andamento | - |
| #02 | W1 | Tooling | Document the retry policy | Low | #01 | Low | ⏳ Pendente | - |
