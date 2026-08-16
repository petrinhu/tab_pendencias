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
Rodar localmente, na mesma ordem dos jobs de `.github/workflows/ci.yml` (a fonte da
verdade), tudo que dá para reproduzir fora do GitHub Actions -- para o vermelho não
aparecer só no servidor.
**Ferramenta:** `scripts/preci.sh` (POSIX `sh`, mesma família dos shims de
`tools/hooks/` -- degradação cross-platform documentada abaixo). Roda, nesta ordem:
pytest (`tests/`); `shellcheck` + o smoke dos shims (`tools/ci/smoke_hooks.sh`);
`markdownlint-cli2`; `gitleaks` (histórico completo); os dois guards do produto
(`guard_stdlib_imports.py`, `guard_no_real_fixtures.py`); e, como camada **extra**
não-bloqueante fora do `ci.yml`, `ruff` sobre `tools/` (informativo -- não há
`ruff.toml`/`pyproject.toml` commitado definindo as regras que o projeto de fato
adota, então um achado de `ruff` nunca reprova o gate).

**Diferenças declaradas vs. `ci.yml`** (o script imprime as mesmas ao rodar, nunca
aproxima em silêncio): (1) pytest roda em **1** ambiente local, não nos 5 do CI
(`ubuntu-latest`/`windows-latest` nativos + `debian`/`fedora`/`archlinux` via
container -- job `test-distros`); reproduzir os 5 requer máquina Windows + runtime
de container, fora do escopo de um script local; (2) `gitleaks` foi incluído além
do pedido original desta fatia porque o job `secrets-scan` existe no `ci.yml` e a
ferramenta estava disponível -- omiti-lo seria aproximar a cobertura; (3) ferramenta
ausente nesta máquina (`shellcheck`, `markdownlint-cli2`, `gitleaks`, `ruff`) vira
`[SKIP]` explícito no resumo final, nunca `[PASS]` silencioso -- o script não
instala nada.

**Nota histórica:** esta seção descrevia antes um "check de consistência
README×SKILL.md" -- ele **nunca existiu** como job do `ci.yml` nem como script em
`tools/`; era aspiracional. Não foi implementado agora (seria uma decisão de design
nova -- o que conta como "consistência" entre os dois arquivos -- fora do escopo de
"espelhar o CI existente"); se o líder quiser esse check, vira item próprio no
`TODO.md`.

**Contagem de `skipped` com cache frio (AUD-FUP-3):** a 1ª execução local após
apagar `.pytest_cache` (ou em clone fresco) pode reportar **mais** `skipped` que
as rodadas seguintes com cache quente. Isto é comportamento esperado do pytest
(fixtures/coleta dependentes de estado de cache), não flakiness do produto: a
suíte estabiliza na 2ª rodada. Não tratar a diferença 1ª×2ª como regressão sem
reexecutar com cache quente.

**`ruff`:** permanece **informativo** em `scripts/preci.sh` (não é job do
`ci.yml`). Não há gate de ruff; por isso não há `ruff.toml`/`pyproject.toml`
que torne achado de lint bloqueante. Tornar ruff gate é decisão de design à
parte (item próprio se o líder quiser).

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
