# Catalogo de Testes e Auditorias (embutido)

> Catalogo GENERICO usado pela skill tab_pendencias para injetar itens de teste e
> auditoria na tabela. Derivado de guias de teste/auditoria multi-stack. NAO contem
> nada especifico de um sistema pessoal. Quando o projeto tem ./TESTES.md ou
> ./AUDITORIAS.md proprios, eles tem precedencia; este catalogo e a base/fallback e
> a fonte dos manuais que a skill cria quando faltam.

## Deteccao de stack

Por arquivos na raiz (via Glob):

| Stack | Sinais |
|---|---|
| C/C++/Qt | `CMakeLists.txt`, `*.cpp`, `*.h`, `*.hpp`, `*.pro` |
| Python | `pyproject.toml`, `setup.py`, `requirements.txt`, `*.py` |
| Rust | `Cargo.toml` |
| Node/TS | `package.json`, `tsconfig.json`, `*.ts`, `*.js` |
| Web/PHP | `*.php`, `composer.json`, `public_html/`, `index.html` |

Caracteristicas (habilitam tipos condicionais):

| Caracteristica | Sinais | Habilita |
|---|---|---|
| DB SQL | `*.sql`, `migrations/`, libs sqlite/mysql/psycopg/PDO | T10, AUD-DB |
| Rede/API | servidor HTTP, endpoints, sockets, rotas | T6, T9, T11, AUD-API |
| Binario compilado | C/C++/Rust | T4, T7 |
| UI | QML, widgets, HTML, componentes front | AUD-UI |

## Testes (T1-T15)

`Aplica`: `sempre` | condicao (caracteristica). T1 e SEMPRE EXCLUIDO (coberto pelo
hook de TDD; nunca vira item na tabela).

| ID | Tipo | Objetivo (1 linha) | Aplica | Ferramentas tipicas |
|---|---|---|---|---|
| (T1) | Testes Unitarios | modulo isolado conforme spec | EXCLUIDO (hook TDD) | QtTest, gtest, pytest, vitest, cargo test |
| TST-T2 | Analise Estatica | bugs/ma pratica sem executar | sempre | cppcheck+clang-tidy, ruff+mypy, eslint+tsc, clippy, phpstan |
| TST-T3 | Fuzzing de Inputs | parsing de input nao-confiavel | binario compilado OU parser de formato | libFuzzer/AFL, atheris |
| TST-T4 | Analise Dinamica de Memoria | leaks/UB em runtime | binario compilado | ASan + UBSan |
| TST-T5 | Scanning de Dependencias | deps vulneraveis/desatualizadas | sempre | trivy/grype, pip-audit, npm audit, cargo audit, composer audit |
| TST-T6 | Teste de APIs | contratos de endpoints | rede/API | schemathesis, postman/newman, REST client |
| TST-T7 | Scanning de Binario | flags de hardening do binario | binario compilado | checksec, hardening-check |
| TST-T8 | Verificacao de Secrets | credencial commitada | sempre | gitleaks, trufflehog |
| TST-T9 | Teste de Rede | comportamento de rede | rede/API | nmap, ferramentas de socket |
| TST-T10 | SQL Injection | queries seguras | DB SQL | sqlmap + revisao de prepared statements |
| TST-T11 | Fuzzing de Protocolos | protocolo de rede custom | rede com protocolo proprio | boofuzz |
| TST-T12 | Busca de CVEs | CVE nas deps | sempre | trivy, grype, OSV/NVD |
| TST-T14 | Integracao (fim-a-fim) | sistema integrado contra fontes de verdade | sempre (quase) | harness de integracao por stack |
| TST-T15 | Pre-CI (espelhar CI local) | rodar a suite do CI antes do push | sempre | scripts/preci.sh por stack |

## Auditorias (consolidadas)

Funde os blocos de auditoria genericos (A1-A10) com os temas por stack, deduplicando
por tema. ID semantico e estavel. `Aplica` igual ao das tabelas de teste.

| ID | Tema | Objetivo (1 linha) | Aplica |
|---|---|---|---|
| AUD-DISC | Descoberta e Modelagem | mapear superficie, ativos, modelo de ameaca | sempre |
| AUD-ARCH | Arquitetura e Camadas | 4 camadas, SOLID, DRY, sem violacao de dependencia | sempre |
| AUD-SEC | Seguranca | memory safety, secrets, SQLi, binario, LGPD/privacidade | sempre |
| AUD-DB | Banco de Dados | schema, queries, EXPLAIN, migrations, indices, LGPD | DB SQL |
| AUD-API | API e Contratos | verbos REST, status codes, auth, OpenAPI | rede/API |
| AUD-UI | UI/UX e Acessibilidade | contraste, navegacao por teclado, WCAG | UI |
| AUD-QUALITY | Qualidade de Codigo | god classes, complexidade, dead code, duplicacao | sempre |
| AUD-COV | Cobertura de Testes | cobertura significativa nos modulos criticos | sempre |
| AUD-DEPS | Dependencias e Acoplamento | grafo de deps, acoplamento, ciclos | sempre |
| AUD-LANG | Idiomas Modernos da Linguagem | tipos/concorrencia/idioms do stack | por stack (Baixa) |
| AUD-FRAMEWORK | Framework Especifico | padroes do framework (ex.: Qt signals/slots, model/view, i18n) | quando usa framework relevante |
| AUD-REPORT | Relatorio Final de Auditoria | score 0-100, sumario de problemas, patches | sempre (consolida) |
