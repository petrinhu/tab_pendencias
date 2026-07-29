# Guia para quem está começando agora em computação

> **Tipo de documento:** tutorial + explicação (misturados de propósito -- este é
> o único documento do projeto pensado para quem nunca programou).
> **Para quem é:** qualquer pessoa que não sabe o que é um terminal, um commit,
> uma tabela em Markdown ou um "exit code", mas quer entender e usar o
> `tab_pendencias`.
> **Não duplica:** o [`README.md`](../README.md) e o [`SKILL.md`](../SKILL.md)
> são as fontes de verdade sobre o que o produto faz. Este guia explica os
> mesmos comandos, mas parte do zero e explica cada termo técnico na primeira
> vez que ele aparece.
> **Versão do produto:** v1.0.0. **Última revisão:** 2026-07-28.

Se alguma frase deste guia usar uma palavra técnica sem explicar, isso é uma
falha do texto, não sua -- procure a palavra no [glossário](#8-glossário) no
final.

## Sumário

1. [A história que motiva este projeto](#1-a-história-que-motiva-este-projeto)
2. [O que é uma tabela em Markdown](#2-o-que-é-uma-tabela-em-markdown-e-por-que-o-caractere-pipe-é-perigoso)
3. [git, commit e hook: só o necessário](#3-git-commit-e-hook-só-o-necessário-para-entender-a-ferramenta)
4. [Instalando e rodando do zero](#4-instalando-e-rodando-do-zero)
5. [Os comandos, um a um, com entrada e saída reais](#5-os-comandos-um-a-um-com-entrada-e-saída-reais)
6. [Como ler o relatório do `--audit`](#6-como-ler-o-relatório-do---audit)
7. [Problemas comuns](#7-problemas-comuns)
8. [Glossário](#8-glossário)

---

## 1. A história que motiva este projeto

Imagine uma pessoa que organiza o trabalho da sua equipe numa tabela de texto
simples chamada `TODO.md` (mais sobre esse formato na próxima seção). Cada
linha da tabela é uma tarefa, com um identificador curto (o **ID**, por
exemplo `T-2`) e uma coluna de status (pendente, em andamento, concluído).

Um dia, alguém copia a linha da tarefa `T-2` ("Enviar e-mail de confirmação do
pedido") para criar uma tarefa nova e parecida ("Enviar SMS de confirmação do
pedido") -- e esquece de trocar o ID da cópia. Agora a tabela tem **duas
linhas diferentes com o mesmo ID `T-2`**:

```markdown
| ID | Onda | Grupo | Descrição Técnica | Prioridade | Pré-requisito | Dificuldade | Status | Estado Auditado |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| T-2 | W1 | Loja | Enviar e-mail de confirmacao do pedido. | Alta | -- | Baixa | Em andamento | -- |
| T-2 | W1 | Loja | Enviar SMS de confirmacao do pedido. | Alta | -- | Baixa | Pendente | -- |
```

Visualmente, nada parece quebrado: as duas linhas aparecem normalmente para
quem olha a tabela. O problema é invisível justamente porque **nenhum erro é
mostrado na tela**. Ele só aparece quando um programa (ou uma pessoa)
pergunta "qual é o status da tarefa `T-2`?" -- e para responder isso, o
programa precisa escolher UMA das duas linhas. Testamos isso de verdade neste
projeto: o script que sincroniza status a partir de commits (`todo_sync.py`,
seção [5.3](#53-todo_syncpy-e-todo_healthpy-o-gêmeo-mecânico)) sempre resolve
o ID para a **última ocorrência** da tabela. No exemplo acima, isso significa
que a tarefa "Enviar e-mail" fica **permanentemente esquecida**: todo
mecanismo automático que procura `T-2` só enxerga a tarefa do SMS a partir
daí. A tarefa do e-mail continua escrita na tela, mas nenhum robô e
dificilmente uma pessoa lendo uma tabela de 40 linhas vai perceber que há
duas tarefas competindo pelo mesmo nome.

**Por que isso é pior que um erro barulhento?** Porque um erro barulhento
(uma mensagem vermelha, um programa que trava) força alguém a olhar e
resolver na hora. Um item que "some" silenciosamente não força nada: o
trabalho simplesmente deixa de ser rastreado, e ninguém descobre até o dia em
que perguntam "e aquele e-mail de confirmação, quem estava cuidando disso?" e
a resposta é "a tabela dizia que estava em andamento, há semanas".

O `tab_pendencias` existe para prevenir exatamente esta classe de defeito
**antes** que ela vire um problema de produção: rodando `--audit` (seção
[5.1](#51---audit-achar-defeitos-sem-alterar-nada)) na tabela acima, a
ferramenta aponta o ID duplicado como achado **CRÍTICO**, mostra as duas
linhas em conflito, e explica por que ela se recusa a decidir sozinha qual
das duas está certa (a decisão exige julgamento humano -- ver seção
[6.2](#62-auto-fixável-contra-julgamento)). É o mesmo princípio por trás do
defeito mais comum que a ferramenta encontra na prática: um caractere `|`
digitado sem querer dentro de uma célula, explicado na próxima seção.

## 2. O que é uma tabela em Markdown (e por que o caractere pipe é perigoso)

**Markdown** é um jeito de escrever texto formatado (títulos, listas, tabelas,
texto em negrito) usando só caracteres comuns de teclado, sem nenhum programa
especial -- qualquer editor de texto simples serve. Um arquivo Markdown tem a
extensão `.md`, como o próprio `TODO.md`. O motivo de usar Markdown em vez de
uma planilha (Excel, Google Sheets) é que o arquivo é **texto puro**: pode ser
lido por qualquer programa, comparado linha a linha por ferramentas de
controle de versão (seção 3), e não depende de nenhum software proprietário
para abrir.

Uma tabela em Markdown se escreve assim:

```markdown
| ID | Descrição | Status |
| :--- | :--- | :--- |
| T-1 | Fechar o carrinho de compras. | Concluído |
| T-2 | Enviar e-mail de confirmação. | Pendente |
```

Cada linha do texto vira uma **linha** (row) da tabela. Dentro de uma linha,
o caractere `|` (chamado **pipe**, em inglês; a tecla geralmente fica perto do
Enter ou do Z, combinada com Shift ou AltGr dependendo do teclado) separa uma
**célula** (cell) da outra -- é o pipe que diz onde termina uma coluna e
começa a próxima. A segunda linha do exemplo (`| :--- | :--- | :--- |`) é
obrigatória e só serve para dizer "isto é mesmo uma tabela, não um parágrafo
com barras verticais": cada `:---` marca uma coluna e seu alinhamento.

### O problema: o pipe é ambíguo

Como o pipe **separa** colunas, qualquer programa que leia a tabela (inclusive
o `tab_pendencias`) conta quantos pipes existem numa linha para saber quantas
células ela tem. Se alguém escrever uma descrição de tarefa que **contenha**
um pipe de verdade -- por exemplo, para descrever uma condição matemática ou
um comando -- sem avisar que aquele pipe não é separador, o programa acha uma
célula a mais do que deveria e a linha inteira fica malformada:

```markdown
| T-2 | Aceitar cupom, valido se preco < 50 | free | Alta | -- | Baixa | Pendente | -- |
```

Aqui, a pessoa quis escrever uma única célula de descrição ("válido se preço
< 50 | free", talvez copiando de uma calculadora ou de um chat), mas o pipe do
meio quebrou a célula em duas, e a linha passou a ter uma coluna a mais do que
o cabeçalho. Isso é exatamente o achado mais comum do `--audit` deste
projeto (o check chamado `CHK-02`, ver seção
[6.1](#61-as-três-severidades-crítico-importante-cosmético)) -- rodamos ao
vivo para este guia e a ferramenta reportou:

```text
[1] CHK-02 -- nº de células ≠ cabeçalho (diagnóstico) (CRÍTICO) -- 1 ocorrencia(s) deste padrao
    linha 6: 1 celula(s) a mais (10 obtidas, 9 esperadas) -- SUPOSICAO: algum '|' literal na linha nao foi escapado; troque por '\|' no ponto que nao deveria separar coluna.  [auto-fixável -> escapar_pipe_cru]
```

A solução é **escapar** o pipe (avisar "este aqui não é separador"),
escrevendo `\|` no lugar de `|`. A barra invertida (`\`) antes de um caractere
é a convenção universal de Markdown para "trate o próximo caractere como
texto normal, não como formatação". A seção
[5.2](#52---fix-corrigir-só-o-que-é-seguro-corrigir) mostra a ferramenta
`--fix` fazendo essa correção sozinha, de forma segura, num caso em que a
posição do pipe é inequívoca.

## 3. git, commit e hook: só o necessário para entender a ferramenta

Você não precisa saber tudo sobre controle de versão para usar o
`tab_pendencias` -- só o suficiente para entender por que a ferramenta
consegue perceber, sozinha, que um trabalho foi entregue.

### O que é um repositório e um commit

**git** é um programa que guarda o **histórico completo** de um conjunto de
arquivos: cada vez que alguém salva uma mudança de propósito, isso vira um
**commit** -- uma "fotografia" datada e assinada do estado dos arquivos
naquele momento, com uma mensagem curta explicando o que mudou. Uma pasta
cujos arquivos são acompanhados dessa forma se chama **repositório**
(em inglês, *repository*, por isso a abreviação comum "repo"). O
`tab_pendencias` em si é um repositório: cada conserto, cada nova
funcionalidade, virou um commit ao longo do desenvolvimento.

Diferente de simplesmente salvar um arquivo, um commit registra **quem**
mudou, **quando**, e **por quê** (a mensagem) -- e nunca apaga o histórico
anterior: é sempre possível voltar e ver como um arquivo estava há semanas.

### Por que citar o ID no commit importa

Cada linha da tabela `TODO.md` representa uma tarefa com um ID (`T-2`, por
exemplo). Quando alguém termina o trabalho daquela tarefa e faz um commit
entregando o código, o `tab_pendencias` pede que a mensagem do commit **cite
o ID** da tarefa -- por exemplo: `"T-2: implementar envio de SMS de
confirmação"`. Isso é só texto dentro da mensagem, não exige nenhuma sintaxe
especial.

Citar o ID é o que permite a um script determinístico (sem inteligência
artificial nenhuma, seção [5.3](#53-todo_syncpy-e-todo_healthpy-o-gêmeo-mecânico))
olhar o histórico de commits, encontrar a menção a `T-2`, e propor
automaticamente avançar o status daquela linha na tabela -- sem que ninguém
precise editar o `TODO.md` à mão para isso.

### O que é um hook

Um **hook** ("gancho", em inglês) é um script que o git executa
automaticamente em certos momentos -- por exemplo, logo depois que um commit
é criado (`post-commit`). O `tab_pendencias` usa um hook `post-commit` que
roda um aviso (nunca bloqueia o commit): se o commit tocou código de verdade
mas não citou nenhum ID conhecido, ou se citou um ID cujo status na tabela
ainda está "Pendente"/"Em andamento", ele lembra a pessoa de atualizar a
coluna Status. Testamos isso ao vivo: depois de instalar o hook (passo
detalhado na seção [4.4](#44-duas-formas-de-usar-dentro-do-claude-code-ou-por-conta-própria))
e commitar código citando um ID ainda pendente, o terminal mostrou:

```text
[todo-fresh] o commit cita T-1, mas no TODO.md o Status segue '⏳ Pendente'. Se entregou, atualize o Status (implementacao -> 'Pendente verificacao'; 'Concluido' so apos a onda de teste/auditoria).
[main 8449586] T-1: implementar fechamento do carrinho
 1 file changed, 1 insertion(+)
```

Note que o commit **aconteceu normalmente** (a segunda linha, `[main
8449586] ...`) -- o aviso apareceu antes, mas não impediu nada. É por isso
que o texto do produto chama este hook de "warn-only" (só avisa).

## 4. Instalando e rodando do zero

### 4.1 Abrindo um terminal

Um **terminal** (ou "linha de comando", "console", "prompt") é um programa
onde você digita comandos de texto em vez de clicar em ícones. No Linux, o
atalho costuma ser `Ctrl+Alt+T` ou procurar por "Terminal" no menu de
aplicativos. No macOS, o aplicativo se chama "Terminal" (em Aplicativos >
Utilitários). No Windows, use o "Git Bash" (instalado junto com o Git para
Windows, próxima seção) ou o "PowerShell".

Depois de abrir, você verá uma linha piscando esperando você digitar --
chamada de **prompt**. Cada comando que você digitar e confirmar com Enter é
executado, e o resultado (a **saída**, em inglês *output*) aparece logo
abaixo, como texto.

### 4.2 Conferindo se você tem git e python3

O `tab_pendencias` precisa de dois programas instalados: **git** (a
ferramenta de controle de versão da seção 3) e **Python 3** (a linguagem em
que os scripts do projeto são escritos). Para conferir se já estão
instalados, digite no terminal:

```bash
git --version
python3 --version
```

Se aparecer um número de versão (por exemplo `git version 2.43.0` e `Python
3.13.9`), está tudo certo. Se aparecer uma mensagem de "comando não
encontrado", você precisa instalar: procure "instalar git" e "instalar
python3" para o seu sistema operacional -- ambos são gratuitos e têm
instaladores oficiais para Windows, macOS e Linux. No Windows, o instalador
do "Git for Windows" já traz o Git Bash mencionado no passo anterior.

### 4.3 Baixando o projeto (clone)

**Clonar** um repositório é baixar uma cópia completa dele, incluindo todo o
histórico de commits, para o seu computador. No terminal:

```bash
git clone https://github.com/petrinhu/tab_pendencias.git
cd tab_pendencias
```

O segundo comando (`cd`, de "change directory") entra na pasta que acabou de
ser criada. A partir daqui, todos os comandos deste guia assumem que você
está dentro dessa pasta.

### 4.4 Duas formas de usar: dentro do Claude Code ou por conta própria

O projeto tem duas camadas, explicadas em detalhe no
[`README.md`](../README.md#duas-camadas-nucleo-genérico-e-convenções-da-casa):

- **Como skill do Claude Code**: se você usa o
  [Claude Code](https://claude.com/claude-code) (um assistente de
  programação em linha de comando), pode instalar este projeto como uma
  "skill" -- um pacote de instruções que o assistente carrega automaticamente.
  Isso dá acesso aos comandos `--create`, `--reorder`, `--show`, `--main` e
  `--add_tests_audit` (seção
  [5.4](#54-os-comandos-que-rodam-dentro-do-claude-code)), que dependem de um
  assistente de IA para funcionar. Instalação:

  ```bash
  mkdir -p ~/.claude/skills
  cd ~/.claude/skills
  git clone https://github.com/petrinhu/tab_pendencias.git
  ```

- **Por conta própria, sem nenhum assistente de IA**: os scripts em `tools/`
  (`todo_audit.py`, `todo_fix.py`, `todo_sync.py`, `todo_health.py`) são
  Python puro -- rodam com só `git` e `python3` instalados, sem precisar do
  Claude Code nem de internet. É o caminho deste guia a partir daqui, porque
  cada comando pode ser executado e conferido por qualquer pessoa, sem
  depender de mais nada.

Instalar o hook de aviso automático da seção 3 (opcional, mas recomendado
para projeto próprio) exige um passo a mais; veja o alerta na seção
[7](#7-problemas-comuns) antes de segui-lo, porque a receita mais curta tem
um detalhe que só funciona com um ajuste.

## 5. Os comandos, um a um, com entrada e saída reais

Todos os comandos abaixo foram executados de verdade para escrever este guia
-- a saída mostrada é a saída real, não uma reconstrução.

### 5.1 `--audit`: achar defeitos sem alterar nada

`tools/todo_audit.py` lê um arquivo `TODO.md` e aponta defeitos estruturais,
**sem nunca escrever nada** (nem no arquivo, nem em nenhum outro lugar do seu
computador, a menos que você peça explicitamente com `--output`). Rode:

```bash
python3 tools/todo_audit.py --todo /caminho/para/o/TODO.md/do/seu/projeto
```

Se você não passar `--todo`, o comando procura um `TODO.md` na pasta atual (e
essa pasta precisa ser um repositório git). Testamos com uma tabela pequena
de exemplo contendo o defeito da seção 2 (um pipe cru dentro de uma célula) e
a saída real foi:

```text
=== tab_pendencias --audit ===
TODO.md: /caminho/para/o/TODO.md/do/seu/projeto
Perfil ativo: core (origem: default (sem .tab_pendencias.ini ou sem [profile] name))

[1] CHK-02 -- nº de células ≠ cabeçalho (diagnóstico) (CRÍTICO) -- 1 ocorrencia(s) deste padrao
    linha 6: 1 celula(s) a mais (10 obtidas, 9 esperadas) -- SUPOSICAO: algum '|' literal na linha nao foi escapado; troque por '\|' no ponto que nao deveria separar coluna.  [auto-fixável -> escapar_pipe_cru]

[2] CHK-05 -- Pré-requisito citando ID inexistente (IMPORTANTE) -- 1 ocorrencia(s) deste padrao
    linha 7: 'T-3' cita pre-requisito 'T-2', que nao existe na tabela  [julgamento]

Achados: 2 (1 CRÍTICO, 1 IMPORTANTE, 0 COSMÉTICO) em 11 check(s) executado(s) de 14 registrado(s).

Avisos do motor (no silent caps):
  - CHK-12 (convencao da casa) nao executado -- perfil ativo = core. Habilite com --profile casa ou .tab_pendencias.ini [profile] name = casa.
  - CHK-13 (convencao da casa) nao executado -- perfil ativo = core. Habilite com --profile casa ou .tab_pendencias.ini [profile] name = casa.
  - CHK-14 (convencao da casa) nao executado -- perfil ativo = core. Habilite com --profile casa ou .tab_pendencias.ini [profile] name = casa.
```

Note o segundo achado (`CHK-05`): a linha 7 citava `T-2` como pré-requisito,
mas como o pipe cru bagunçou a linha de `T-2`, o programa deixou de reconhecer
aquele ID como válido -- outra ilustração da mesma história da seção 1: um
defeito estrutural faz um ID "desaparecer" do ponto de vista de qualquer
verificação automática, mesmo que ele continue visível a olho nu.

Depois de rodar, confira o **código de saída** (também chamado *exit code*):
é um número que o próprio terminal guarda dizendo se o comando terminou bem
ou mal. Digite logo em seguida:

```bash
echo $?
```

Para `--audit`: `0` significa "rodou certo, zero achados"; `1` significa
"erro de execução" (por exemplo, o arquivo não existe, ou não se chama
exatamente `TODO.md`); `2` significa "rodou certo, mas há pelo menos um
achado" -- **mesmo que só um achado cosmético**, sem gravidade nenhuma. É por
isso que o número sozinho nunca diz a gravidade: é preciso ler o relatório
(seção 6).

### 5.2 `--fix`: corrigir só o que é seguro corrigir

`tools/todo_fix.py` lê os achados que o `--audit` já marcou como
`[auto-fixável]` (seção [6.2](#62-auto-fixável-contra-julgamento)) e aplica
**só** essas correções -- ele nunca decide sozinho o que é seguro consertar;
essa decisão já foi tomada pelo `--audit`. Por padrão, `--fix` não escreve
nada (modo *dry-run*, "simulação"): só mostra o que faria.

Testamos com uma tabela onde o pipe cru estava dentro de um trecho de código
(entre crases, por exemplo `` `preco|desconto` ``), o que torna a posição do
pipe **inequívoca**:

```bash
python3 tools/todo_fix.py -v
```

Saída real (modo simulação, nada escrito ainda):

```text
=== tab_pendencias --fix ===
TODO.md: /caminho/para/o/TODO.md/do/seu/projeto

- CHK-02 (escapar_pipe_cru) [proposto]: linha 6: escapar pipe cru dentro de code span (célula a mais)
    - | T-2 | W1 | Loja | Aceitar regex `preco|desconto` no filtro de busca. | Alta | — | Baixa | 🔍 Pendente verificação | — |
    + | T-2 | W1 | Loja | Aceitar regex `preco\|desconto` no filtro de busca. | Alta | — | Baixa | 🔍 Pendente verificação | — |

Nada foi escrito (dry-run). Rode com --apply <classe...> para aplicar (ou --apply all para todas as classes detectadas nesta execução).
```

As linhas com `-` e `+` são um **diff** ("diferença"): `-` mostra a linha como
ela está hoje, `+` mostra como ficaria depois da correção. Para aplicar de
verdade:

```bash
python3 tools/todo_fix.py --apply escapar_pipe_cru
```

Saída real:

```text
- CHK-02 (escapar_pipe_cru) [APLICADO]: linha 6: escapar pipe cru dentro de code span (célula a mais)
    - | T-2 | W1 | Loja | Aceitar regex `preco|desconto` no filtro de busca. | Alta | — | Baixa | 🔍 Pendente verificação | — |
    + | T-2 | W1 | Loja | Aceitar regex `preco\|desconto` no filtro de busca. | Alta | — | Baixa | 🔍 Pendente verificação | — |

1 correção(ões) aplicada(s) e escrita(s) no TODO.md.
```

E rodando `--audit` de novo na mesma tabela, o resultado veio limpo:

```text
Nenhum check aplicavel produziu achados.
Achados: 0 (0 CRÍTICO, 0 IMPORTANTE, 0 COSMÉTICO) em 11 check(s) executado(s) de 14 registrado(s).
```

**Nem todo achado `[auto-fixável]` consegue de fato ser corrigido.** No
exemplo da seção 5.1 (pipe cru **fora** de qualquer trecho de código), o
`--fix` se recusou:

```text
- CHK-02 (escapar_pipe_cru) [NÃO APLICÁVEL -- recusado pelo motor de fix]: linha 6: CHK-02 marcou [auto-fixável], mas o motor de fix RECUSA aplicar automaticamente
    motivo da recusa: 0 pipe(s) cru(s) localizado(s) dentro de code span (crase), mas o excesso de célula(s) é 1 -- posição ambígua fora de code span; o motor de fix RECUSA adivinhar (nunca escreve no lugar errado).
```

Isto é intencional: o `--fix` prefere dizer "não sei corrigir isto com
segurança" a arriscar um palpite errado no seu arquivo.

### 5.3 `todo_sync.py` e `todo_health.py`: o "gêmeo mecânico"

Estes dois scripts complementam o hook da seção 3, sem depender dele:

- `python3 tools/todo_sync.py` lê os commits e propõe avançar itens
  "Pendente"/"Em andamento" para "Pendente verificação", só para IDs citados
  num commit que também tocou código de verdade (não conta um commit que só
  mexeu no próprio `TODO.md`). Por padrão só mostra a proposta; `--apply`
  escreve de fato.
- `python3 tools/todo_health.py` mostra um raio-x da tabela. Saída real,
  rodada na tabela deste próprio projeto:

  ```text
  Saude da TODO.md (46 itens):
    ✅ concluidos: 1
    ⏳/🔄 pendentes (nao entregues): 6
    🔍 aguardando verificacao (entregue, falta teste/auditoria): 39
         presos em 🔍 -> ADR-1
         presos em 🔍 -> SCAF-1
         (...)
    INBOX (descobertas nao priorizadas): 6
    adesao a citar ID: 49/50 commits de codigo citaram ID (98%)
  ```

  "Presos em 🔍" lista itens que já foram implementados, mas ainda esperam o
  teste ou a auditoria que os leva a "Concluído" -- não é um erro, é o estado
  esperado enquanto o trabalho de verificação não termina.

### 5.4 Os comandos que rodam dentro do Claude Code

Os comandos `--create`, `--reorder`, `--show`, `--main` e `--add_tests_audit`
não são scripts Python que você roda direto no terminal: eles são
instruções que um assistente de IA (o Claude Code) interpreta e executa,
descritas em detalhe no [`SKILL.md`](../SKILL.md). Resumo do que cada um
faz (sem repetir o `README.md`, que já documenta o comportamento verificado):

| Comando | O que faz |
|---|---|
| `--create` | Cria uma tabela nova, já ordenada |
| `--reorder` | Recalcula a ordem de uma tabela existente |
| `--show` | Mostra a tabela inteira, inclusive o que já terminou |
| `--main` | Mostra só o que ainda falta |
| `--add_tests_audit` | Acrescenta itens de teste/auditoria faltantes |

Estes comandos não puderam ser demonstrados com entrada/saída real neste
guia porque dependem de uma sessão ativa do Claude Code, não de um comando de
terminal isolado.

## 6. Como ler o relatório do `--audit`

### 6.1 As três severidades: CRÍTICO, IMPORTANTE, COSMÉTICO

Cada achado do `--audit` vem etiquetado com uma destas três gravidades:

- **CRÍTICO**: um defeito que compromete a confiabilidade da tabela (ID
  duplicado, tabela fragmentada, ciclo de dependência). Vale a pena resolver
  antes de confiar na tabela para planejar qualquer coisa.
- **IMPORTANTE**: um problema real, mas que não invalida a tabela inteira
  (um pré-requisito que cita um ID que não existe, uma claim que parece
  desatualizada).
- **COSMÉTICO**: sem impacto funcional -- por exemplo, uma proposta de
  sincronização de status ainda não aplicada.

O código de saída do `--audit` (seção 5.1) sobe para `2` mesmo com **um único
achado cosmético**: o número por si só nunca diz a gravidade, só "há algo a
olhar" -- por isso este guia recomenda sempre ler o relatório, nunca decidir
só pelo número.

### 6.2 `[auto-fixável]` contra `[julgamento]`

Cada achado também vem marcado com uma destas duas etiquetas, no final da
linha:

- **`[auto-fixável -> nome_da_classe]`**: existe uma correção mecânica
  conhecida para este achado, que o `--fix` (seção 5.2) sabe aplicar **quando
  a posição é inequívoca**. Nem todo achado assim marcado consegue ser
  corrigido de fato -- o `--fix` pode ainda recusar, como mostrado na seção
  5.2.
- **`[julgamento]`**: a correção exige uma decisão que só uma pessoa pode
  tomar -- por exemplo, duas linhas com o mesmo ID que divergem em mais de
  uma célula (qual das duas está certa?). O `--fix` nunca tenta adivinhar
  nestes casos.

### 6.3 Quando o relatório diz que é uma suposição

Alguns achados trazem a palavra **"SUPOSIÇÃO"** dentro da própria mensagem
(veja o exemplo da seção 5.1: *"SUPOSICAO: algum '|' literal na linha nao foi
escapado"*). Isso é deliberado: o `--audit` só tem acesso ao texto da tabela,
não à intenção de quem escreveu -- então, quando o diagnóstico mais provável
não é o único possível, o relatório avisa explicitamente que está
suposição, nunca apresenta um palpite como se fosse fato confirmado. A mesma
honestidade aparece nos avisos "não executado" (por exemplo, `CHK-12` sob o
perfil padrão): o motor nunca finge que rodou uma verificação que na verdade
pulou.

## 7. Problemas comuns

- **"Não é um repositório git"** (erro ao rodar `--audit` sem `--todo`): o
  comando precisa ser executado de dentro de uma pasta que já é um
  repositório git (tem uma subpasta oculta `.git`), ou você precisa passar
  `--todo /caminho/completo/para/TODO.md` apontando para o arquivo.
- **O arquivo precisa se chamar exatamente `TODO.md`**: `--todo` recusa
  qualquer outro nome (por exemplo `todo.md` em minúsculas, ou `TAREFAS.md`),
  com uma mensagem explicando a restrição.
- **`--fix --apply` recusa rodar com a árvore de trabalho "suja"**: se você
  tem mudanças no `TODO.md` que ainda não foram commitadas (seção 3), o
  `--fix` se recusa a escrever, para nunca misturar sua edição em andamento
  com a correção automática. Faça o commit (ou descarte a mudança) antes de
  rodar `--apply`.
- **Instalando o hook "por projeto": um detalhe que a receita mais curta do
  [`tools/README.md`](../tools/README.md) não deixa óbvio.** Testamos ao vivo
  a receita exatamente como está escrita lá (copiar `post-commit`,
  `_chain.sh` e `todo_freshness.py` para dentro de uma pasta `.githooks/`) e
  o aviso do hook não apareceu -- o terminal mostrou um erro de arquivo não
  encontrado. A causa: o script `post-commit` procura `todo_freshness.py` um
  nível **acima** da pasta onde ele mesmo está, e `todo_freshness.py` por sua
  vez precisa de outro arquivo do projeto (`todo_lib.py`) na **mesma pasta**
  que ele. Para a instalação "por projeto" funcionar hoje, coloque
  `todo_freshness.py` **e** `todo_lib.py` na raiz do seu projeto (não dentro
  de `.githooks/`), e só os shims (`post-commit`, `_chain.sh`) dentro de
  `.githooks/`:

  ```bash
  mkdir -p .githooks
  cp /caminho/do/clone/tools/hooks/post-commit /caminho/do/clone/tools/hooks/_chain.sh .githooks/
  chmod +x .githooks/post-commit
  cp /caminho/do/clone/tools/todo_freshness.py /caminho/do/clone/tools/todo_lib.py .
  git config core.hooksPath .githooks
  ```

  Reportamos esta divergência para quem mantém o projeto corrigir a receita
  documentada; até lá, use os passos acima, verificados ao vivo para este
  guia.

## 8. Glossário

| Termo | Significado |
|---|---|
| Terminal | Programa onde se digitam comandos de texto em vez de clicar em ícones |
| Prompt | A linha onde você digita um comando dentro do terminal |
| Shell | O programa que interpreta os comandos digitados no terminal (`bash`, `sh`, PowerShell) |
| git | Programa que guarda o histórico completo de mudanças de um conjunto de arquivos |
| Repositório (repo) | Uma pasta cujos arquivos são acompanhados pelo git |
| Commit | Uma "fotografia" datada de como os arquivos estavam num momento, com uma mensagem explicando o que mudou |
| Clonar | Baixar uma cópia completa de um repositório, com todo o histórico |
| Hook | Script que o git executa automaticamente em certos momentos (por exemplo, depois de um commit) |
| Markdown | Formato de texto simples que vira formatação (títulos, listas, tabelas) sem programa especial |
| Tabela GFM | Tabela em Markdown no formato do GitHub (linhas separadas pelo caractere pipe) |
| Célula | Cada posição de uma tabela, na interseção de uma linha com uma coluna |
| Pipe | O caractere `\|`, usado para separar colunas numa tabela Markdown |
| Escapar | Preceder um caractere especial com `\` para que ele seja tratado como texto comum, não como formatação |
| ID | Identificador curto e único de uma tarefa na tabela (ex.: `T-2`) |
| Exit code (código de saída) | Número que um comando devolve ao terminar, indicando se rodou bem (`0`) ou mal (diferente de `0`) |
| Dry-run | Modo de simulação: o programa mostra o que faria, sem escrever nada de fato |
| Diff | Representação de uma diferença entre duas versões de um texto, com `-` para o que sai e `+` para o que entra |
| Flag | Uma opção de linha de comando, geralmente começando com `--` (ex.: `--apply`) |
| stdlib | Biblioteca padrão de uma linguagem de programação -- código que já vem pronto, sem precisar instalar nada a mais |
| CI (integração contínua) | Um serviço que roda automaticamente os testes e verificações do projeto a cada mudança, sem depender do computador de ninguém |
| Skill (do Claude Code) | Um pacote de instruções que um assistente de IA carrega para saber executar uma tarefa específica |

---

Para material de referência mais direto (uma página por comando, sem o
contexto didático deste guia), veja a
[Wiki do repositório](https://github.com/petrinhu/tab_pendencias/wiki).
