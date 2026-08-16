# Fragmento para `CLAUDE.md` global (TAB-VAULT-001)

> Cole sob a secao de pendencias / frescor da tabela. Substitui a regra
> historica "trabalho novo vai para a INBOX". Este arquivo e **template de
> produto** -- sem caminhos de maquina, sem nomes de projetos privados.

## Descoberta e intake (6 passos)

1. **Descoberta de worker** -- o subagente/worker devolve o bloco
   `DISCOVERED_WORK` (ou equivalente); **nao** edita `TODO.md` nem a secao
   INBOX por conta propria.
2. **Main chama intake** -- a thread principal (unico escritor logico por
   orquestracao) normaliza o achado e invoca o pipeline de intake
   (`tools/todo_intake.py` / `/tab_pendencias --add`).
3. **Local -> TODO imediato** -- se o julgamento for L0 (escopo local, sem
   reordenar o grafo), o item entra na tabela na hora.
4. **Estrutural -> reorder proporcional** -- fundacao / escopo largo / nova
   dependencia material dispara `SCOPED_REORDER` ou `FULL_REORDER` (nunca
   reorder por relogio).
5. **Ambiguo -> INBOX residual** -- so quando faltam campos, autoridade ou
   julgamento: a INBOX e **exception queue**, nao a fila normal de
   descobertas.
6. **`TAB_TRIAGE_REQUIRED` e acao da thread principal** -- drenar
   (`--drain`) no proximo ponto seguro; nao e lembrete passivo ao humano.

Contrato de retorno de agents: ver
`templates/agents/implementer-discovery-contract.md` no produto
`tab_pendencias`.
