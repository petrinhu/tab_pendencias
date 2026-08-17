# Auditorias do Projeto

> Auditorias aplicáveis a este projeto (stack: **Python 3 stdlib + pytest, shell POSIX,
> Markdown, CI GitHub Actions**). Cada uma vira um item `AUD-*` no `TODO.md`, nas ondas
> finais -- sempre **downstream de código + teste** (nunca auditar o que ainda não foi
> implementado e testado).

## AUD-DISC Descoberta e Modelagem
Mapear a superfície do produto, os ativos e o modelo de ameaça.
**Ferramentas:** revisão manual de superfície (o que o toolkit lê e escreve na máquina de
terceiros), DFD simples. Superfície central deste produto: **git hooks executam código na
máquina de quem instala** e o parser processa arquivo não-confiável.

## AUD-ARCH Arquitetura e Camadas
Verificar separação de camadas, SOLID, DRY e ausência de violação de dependência.
**Ferramentas:** `import-linter` (ou revisão do grafo). Invariante deste repo: a fronteira
**núcleo genérico × convenções da casa** -- nenhum check do núcleo pode depender do perfil
"casa" (constelação, wikilinks do vault, CHK-14).

## AUD-SEC Segurança
Secrets, entrada não-confiável, e o que o código executa por conta própria.
**Ferramentas:** `bandit`/`semgrep` (SAST), `gitleaks` (secrets), OSV (CVE). Focos deste repo:
(a) nada de `shell=True` nem interpolação de path em subprocess git; (b) `--fix` / `--add` /
`--drain` escrevem no `TODO.md` do usuário -- working tree limpa, lock, round-trip e journal
com `redact_secrets` no intake; (c) os shims `sh` rodam como hook e devem apontar para a
**instalação publicada** (HOOKSRC-1), não para checkout de dev; (d) corpus e bus sem payload
privado versionado.

## AUD-QUALITY Qualidade de Código
God functions, complexidade, dead code, duplicação.
**Ferramentas:** `ruff`, `radon`/`lizard` (complexidade), `vulture` (dead code).

## AUD-COV Cobertura de Testes
Cobertura significativa nos módulos críticos -- não cobertura de vaidade.
**Ferramentas:** `pytest-cov`. Alvo prioritário: `todo_lib.py` (parser e predicados) e os
motores `todo_audit.py`/`todo_fix.py`. **Mutation testing** é o critério que vale acima do
percentual: cobertura alta sem mutante morto não prova nada.

## AUD-DEPS Dependências, Acoplamento e Licenças
Grafo de dependências, ciclos, e conformidade de licença.
**Ferramentas:** `pydeps`/`import-linter`; verificação de licença após a relicença
**GPL-3.0-or-later** (D-3): cabeçalhos coerentes, `LICENSE` correto, README sem menção residual
à licença anterior, e nenhuma dependência com licença incompatível.

## AUD-LANG Idiomas Modernos da Linguagem
Idioms atuais de Python e portabilidade real.
**Ferramentas:** `pyupgrade` + `mypy`. Restrição de projeto: **stdlib puro** (nenhuma dependência
de runtime) e **cross-platform** -- sem suposição de separador de path nem de POSIX-only.

## AUD-REPORT Relatório Final de Auditoria
Consolidar os achados num relatório único com score e patches propostos.
**Ferramentas:** consolidação manual em `docs/auditoria/` pelo `internal-auditor`, agregando os
achados das auditorias acima, classificados em CRÍTICO / IMPORTANTE / COSMÉTICO.

---

## Fora de escopo (podados do catálogo, com motivo)

| Auditoria | Motivo |
|---|---|
| AUD-DB | não há banco de dados nem SQL |
| AUD-API | não há endpoint nem contrato de rede |
| AUD-UI | não há interface gráfica (a saída é texto no terminal e Markdown) |
| AUD-FRAMEWORK | não há framework de app/UI; o runtime é stdlib puro |
