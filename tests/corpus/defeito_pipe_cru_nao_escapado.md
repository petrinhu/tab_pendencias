# Backlog: Nebula Pipeline Utilities

Ticket `#02` below has a raw, unescaped `|` inside its Description cell --
a copy-pasted shell one-liner that forgot to escape the pipe. The row ends
up with one cell too many for the header, which is exactly the class of
defect that made a real ticket invisible in production.

| ID | Wave | Group | Description | Priority | Blocked By | Effort | Status | Reviewed |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| #01 | W1 | Tooling | Fix the log rotation cron job | High | - | Low | ⏳ Pendente | - |
| #02 | W1 | Tooling | Prove `nm libx.a | grep -c foo` returns zero (pipe not escaped!) | High | #01 | Medium | 🔄 Em andamento | - |
| #03 | W2 | Tooling | Document the retry policy | Low | #02 | Low | ⏳ Pendente | - |
