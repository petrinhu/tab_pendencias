# Testes do Projeto

> Tipos de teste aplicáveis a este projeto (stack: **Python 3 stdlib + pytest, shell POSIX,
> Markdown, CI GitHub Actions**; sem DB, sem rede/API, sem binário compilado, sem UI).
> T1 unitário fica sob TDD e ride COM a implementação -- não é listado aqui nem vira item
> na tabela. Cada tipo abaixo vira um item `TST-*` no `TODO.md`, em onda posterior à
> implementação que ele cobre.

## TST-T2 Análise Estática
Encontrar bugs e má prática sem executar o código.
**Ferramentas:** `ruff` (lint) + `mypy` (tipos) nos módulos de `tools/`; `shellcheck` nos shims
POSIX (`tools/hooks/*.sh` e os shims sem extensão); lint de Markdown nos docs.

## TST-T5 Scanning de Dependências
Detectar dependência vulnerável ou desatualizada.
**Ferramentas:** `pip-audit` sobre o ambiente de teste (o runtime é stdlib puro -- a superfície
real é `pytest` e as *actions* do CI). Inclui **pinagem das GitHub Actions por SHA**, não por tag
móvel: é a única dependência de terceiro que executa código neste repo.

## TST-T8 Verificação de Secrets
Garantir que nenhuma credencial foi commitada.
**Ferramentas:** `gitleaks` ou `trufflehog` sobre o histórico completo. Atenção específica deste
repo: as **fixtures de aceitação vindas de projetos reais** (consumidor A/consumidor B) nunca entram no
repo sem anonimização -- o corpus distribuído é sintético.

## TST-T12 Busca de CVEs
Verificar CVE conhecida nas dependências.
**Ferramentas:** OSV/NVD via `pip-audit` ou consulta OSV; escopo mínimo por desenho (stdlib puro).
Roda junto de TST-T5.

## TST-T14 Integração (fim-a-fim)
Exercitar o sistema integrado contra fontes de verdade, não só unidades isoladas.
**Ferramentas:** pytest chamando as CLIs de verdade (`todo_sync.py`, `todo_health.py`,
`todo_audit.py`, `todo_fix.py`) por subprocess em repositórios git temporários de fixture;
e2e do `todo_freshness.main` com `diff-tree` real; execução dos shims `sh` via subprocess.
Inclui os testes de contrato com o corpus real (LOCAIS, nunca commitados) e o corpus sintético.

## TST-T15 Pre-CI (espelhar o CI local)
Rodar a mesma suíte do CI antes do push, para o vermelho não aparecer só no servidor.
**Ferramentas:** `scripts/preci.sh` executando pytest + ruff + shellcheck + o check de
consistência README×SKILL.md, na mesma ordem do workflow do GitHub Actions.

---

## Fora de escopo (podados do catálogo, com motivo)

| Tipo | Motivo |
|---|---|
| T1 Unitário | coberto por TDD; ride com a implementação, nunca vira item |
| T3 Fuzzing de inputs / T4 Análise dinâmica de memória / T7 Scanning de binário | não há binário compilado (Python stdlib + sh) |
| T6 Teste de APIs / T9 Teste de rede / T11 Fuzzing de protocolo | o produto é offline por desenho; nenhum socket, nenhum endpoint |
| T10 SQL Injection | não há banco de dados nem SQL |

> Nota: embora não haja *fuzzing* formal (T3), o parser processa entrada não-confiável
> (TODO.md de terceiros). A cobertura equivalente vem do **corpus sintético property-based**
> e do **mutation testing** obrigatório de cada guard, ambos em TST-T14 e nos itens de
> implementação -- não da ausência de risco.
