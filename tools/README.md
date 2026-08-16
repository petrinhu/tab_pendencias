# tools/ -- frescor da TODO.md (Camada 2 local)

Git hook **local, cross-platform e warn-only** que ajuda a manter a tabela de
pendências (`TODO.md`) sincronizada durante o sprint, **sem CI nem servidor**,
o gêmeo local da Camada 2. Detalhe canônico da convenção em
[`../references/`](../references/) (regras de frescor internalizadas, D-2).

Layout monorepo (D-4): os scripts Python ficam aqui em `tools/`; os shims
POSIX + `_chain.sh` ficam em [`hooks/`](hooks/); a suíte pytest fica em
[`../tests/`](../tests/).

## O que faz

No `post-commit` (já depois do commit, então **nunca bloqueia**), avisa em dois
casos, e só quando há lacuna acionável (silencioso caso contrário):

1. O commit **tocou código mas não citou nenhum ID** do `TODO.md`: sugere citar
   o ID (ex.: `V-12`) na mensagem, para rastrear o status. Bootstrapa o hábito.
2. O commit **cita um ID cujo Status ainda é "Pendente" / "Em andamento"**:
   lembra de atualizar o Status (implementação entregue, "Pendente
   verificação"; "Concluído" só após a onda de teste/auditoria).

Nunca edita o `TODO.md`, nunca aborta o commit. Registra uma linha em
`.git/todo-freshness.log` (local, não versionado) para **medir adesão** antes de
qualquer automação, a Camada 2 só escala com evidência, nunca de prontidão.

## Sincronização e saúde (scripts offline, sem LLM)

Dois scripts locais e **determinísticos** (Python stdlib; nem precisam de sessão Claude) complementam o hook. São a "metade mecânica" do frescor; o `--reorder` (julgamento) continua na skill:

- **`python3 tools/todo_sync.py`**: lê os commits desde o último sync (`.git/todo-sync-ref`), acha os IDs citados e propõe avançar itens `⏳ Pendente`/`🔄 Em andamento` para `🔍 Pendente verificação` (NUNCA `✅`; nunca reordena). Por padrão **só propõe**; `--apply` escreve. Preserva o resto da linha e o EOL (CRLF/LF), e ignora linha malformada. `--since <ref>` força uma janela.
- **`python3 tools/todo_health.py`**: relatório de itens presos em `🔍` (falso-done residual), tamanho da INBOX, e a % de adesão a citar ID (do `todo-freshness.log`). Dá o dado para "medir antes de escalar".

Podem ser rodados à mão, por um alias, pelo git hook, ou por um agendador local (systemd/launchd/Task Scheduler). Robustez verificada por `qa-engineer` + `code-reviewer` (CRLF, BOM, múltiplas tabelas, célula deslocada).

## Drift do pin de submódulo (`submodule_pin_drift.py`)

Detector **read-only, offline-first e warn-only** (TAB-SOT-007): quando este
toolkit é distribuído como submódulo git dentro de outro repositório, o
gitlink gravado na árvore do superprojeto pode ficar preso num commit antigo
sem que ninguém perceba -- foi exatamente o que aconteceu num consumidor real
(gitlink 67 commits atrás da tag publicada mais recente; `git clone
--recursive` numa máquina nova restaurava a skill sem o toolkit inteiro).

```sh
python3 tools/submodule_pin_drift.py --path caminho/do/submodulo [--url <remoto>] [--branch <nome>]
```

- **Agnóstico a projeto** (AGN-1): `--path` e `--url` são sempre parâmetros
  -- nenhum nome de projeto/submódulo vem embutido no código. Sem `--url`, o
  único fallback é o `.gitmodules` do próprio superprojeto (mecanismo padrão
  do git, não convenção deste projeto).
- **Nunca muta nada**: sem `git submodule update --remote`, sem
  commit/push, sem `git fetch` (mesma política de `checks/chk_frescor.py`
  para CHK-09 -- `git ls-remote` consulta o remoto sem gravar nada local).
  Exit code é sinal, não bloqueio: quem decide se isso falha um pipeline é o
  job de CI que consome a ferramenta.
- **Sem rede nunca vira "OK"**: se `git ls-remote` falhar/expirar, ou se o
  remoto não tiver nenhuma tag `vX.Y.Z`, o relatório sai com
  `status: nao_verificavel` -- nunca `atualizado`. `commits_behind` e
  `commits_ahead` só são calculáveis quando os objetos do submódulo já
  estão localmente disponíveis (checkout prévio); do contrário ficam
  `nao calculavel offline`, com o motivo explícito.
- **`status` enumera a posição relativa inteira, não só "bate ou não bate"**
  (TAB-SOT-007-BIS, 16/08/26 -- um pin *à frente* da última release, o
  estado normal de um consumidor que segue a `main` entre releases, chegou
  a sair como `desatualizado` mesmo com `commits_behind: 0` no próprio
  relatório contradizendo o veredito):
  - `atualizado` -- pin == última release (e == branch pedido, se houver);
  - `a_frente` -- pin é descendente da última release (comum entre
    releases, **não** é drift pra trás);
  - `desatualizado` -- pin é ancestral da última release (ou, sem checkout
    local pra confirmar a direção, sha diferente presume `atras` -- a
    mesma política conservadora do incidente histórico de 67 commits);
  - `divergente` -- pin e última release estão em linhas de história
    diferentes (nem ancestral nem descendente) -- a situação genuinamente
    perigosa, nunca conflada com `desatualizado`;
  - `nao_verificavel` -- sem rede, sem tag semver no remoto, ou branch
    pedido não resolvido.
- Contrato de exit code (D-6/CLI-1): `0` = `status` em `atualizado` **ou**
  `a_frente` (nenhum dos dois é drift -- `a_frente` sai silencioso de
  propósito, pra não virar alarme permanente entre releases, mesmo
  raciocínio anti-fadiga-de-alerta do ADR-0002); `1` = erro de execução
  (path inválido, `.gitmodules` sem URL resolvível, flag desconhecida);
  `2` = `status` em `desatualizado`, `divergente` ou `nao_verificavel`.

## Como ativar

Os arquivos são `hooks/post-commit` (shim POSIX) + `todo_freshness.py`
(lógica, só stdlib). Escolha um modo:

### Por projeto (recomendado)

Versiona o hook junto do repo e vale também nos worktrees dos agents. O shim
(`post-commit`) procura `todo_freshness.py` **um nível acima** de onde ele
mesmo está (mesmo layout monorepo de `tools/hooks/` + `tools/` descrito
acima), e `todo_freshness.py` por sua vez precisa de `todo_lib.py` na
**mesma pasta** que ele -- por isso os scripts Python vão em `.githooks/` e
só os shims em `.githooks/hooks/` (não os dois juntos na mesma pasta):

```sh
mkdir -p .githooks/hooks
cp tools/hooks/post-commit tools/hooks/_chain.sh .githooks/hooks/
cp tools/todo_freshness.py tools/todo_lib.py .githooks/
chmod +x .githooks/hooks/post-commit    # Unix; no Windows o exec bit e irrelevante
git config core.hooksPath .githooks/hooks
```

### Global (todos os repositórios da máquina)

Aplica a todos os repos; faz **no-op silencioso** onde não há `TODO.md`:

```sh
git config --global core.hooksPath /caminho/para/este/clone/tools/hooks
```

(Nesta máquina, a migração para este modo é acompanhada por passo de
verificação explícito; ver `MIG-1` no `TODO.md` deste projeto.)

## Coexistência com hooks locais (encadeamento)

Um `core.hooksPath` global normalmente **sombrearia** o `.git/hooks/` próprio de
cada repo, desativando silenciosamente git-lfs, o framework pre-commit, husky
etc. Para evitar isso, `hooks/` traz **shims de pass-through** (`pre-commit`,
`prepare-commit-msg`, `commit-msg`, `post-checkout`, `post-merge`, `pre-push`)
que **delegam ao hook local** do repo (`.git/hooks/<nome>`, resolvido por
`git rev-parse --git-common-dir`, via `_chain.sh`). O `post-commit` roda o aviso
de frescor **e depois** encadeia o local.

Resultado: o aviso de frescor vale em todos os repos **e** os hooks locais
continuam funcionando. Hooks que **bloqueiam** (ex.: um `pre-commit` que falha)
continuam bloqueando: `exec` preserva args, stdin e exit code. Repos que já
definem o próprio `core.hooksPath` (ex.: husky) ignoram o global e seguem como
estão.

## Cross-platform

- **Linux / macOS:** `sh` nativo executa o shim; `python3` faz o trabalho.
- **Windows:** requer o Git for Windows (traz o `bash` que roda hooks `#!/bin/sh`)
  e `python`/`python3` no PATH. O shim tenta `python3` e depois `python`.
- O output é texto puro (sem emoji) e o stderr é reconfigurado para UTF-8 com
  `errors="replace"`, então não quebra em console com encoding legado.
- Sem dependências externas (só stdlib). Onde não houver Python, o shim sai com
  código 0 e não atrapalha o commit.

## Equivalentes locais das outras camadas (referência)

- **Camada 3 local** (faxina periódica desassistida): agendador nativo do OS
  com payload Python portável: `systemd --user` timer (Linux), `launchd`
  (macOS), Task Scheduler (Windows), ou `cron`. Só necessária no caso raro
  "rodar mesmo sem commit nem sessão"; faz só higiene mecânica, **não** reordena.
- **Camada 4 local** (fonte-da-verdade offline): `git-bug` (issues em refs git,
  sem servidor) em vez de Issues do GitHub.

## Testes

```sh
cd /caminho/para/este/clone && python3 -m pytest tests/ -q
```

## Pre-CI local (TST-T15)

`scripts/preci.sh`, na raiz do repo, roda localmente -- na mesma ordem dos jobs de
`.github/workflows/ci.yml` -- tudo que dá para reproduzir fora do GitHub Actions
(pytest, `shellcheck` + smoke dos shims, `markdownlint-cli2`, `gitleaks`, os guards
de `tools/ci/`), para o vermelho não aparecer só no servidor. Detalhe completo,
diferenças declaradas vs. o CI, e contrato de exit code em `TESTES.md` (TST-T15).

**Cross-platform:** é `sh` POSIX, mesma família dos shims acima (degradação
documentada, não suposição escondida, D-11/ADR-1 seção (e)) -- roda nativo em
Linux/macOS; no Windows requer Git for Windows ou WSL (o mesmo shell que os shims
já exigem). As etapas de `shellcheck` e do smoke dos shims já são Linux-only dentro
do próprio `ci.yml` (job `shellcheck-and-smoke`); este script não introduz
degradação nova, só herda a que já existe.

```sh
cd /caminho/para/este/clone && sh scripts/preci.sh
```

## Licença

GPL-3.0-or-later (ver `../LICENSE`).
