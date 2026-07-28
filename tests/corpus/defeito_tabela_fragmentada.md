# Backlog: Split Across Two Tables (legacy export artifact)

This fixture reproduces a genuinely fragmented canonical table: two
separate ID+Status tables in sequence, as if two half-exports were pasted
one after the other and never merged.

## First half

| ID | Wave | Group | Description | Priority | Blocked By | Effort | Status | Reviewed |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| #01 | W1 | Core | First half item A | High | - | Low | ✅ Concluído | yes |
| #02 | W1 | Core | First half item B | High | #01 | Low | ⏳ Pendente | - |

## Second half (exported separately, never merged)

| ID | Wave | Group | Description | Priority | Blocked By | Effort | Status | Reviewed |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| #03 | W2 | Core | Second half item C | Medium | #02 | Low | ⏳ Pendente | - |
| #04 | W2 | Core | Second half item D | Low | #03 | Low | ⏳ Pendente | - |
