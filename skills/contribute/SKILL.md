---
name: contribute
description: Propor mudanca de codigo por Pull Request, numa copia
---

# Propor uma mudança, por Pull Request

A pasta do dono é montada somente leitura, e continua sendo. Esta skill não abre exceção nenhuma
nisso: ela clona **do remoto** para uma área que é sua, edita lá, e o resultado vira um Pull Request
em rascunho que **uma pessoa revisa antes de qualquer coisa entrar**.

A distinção é o produto inteiro. "Nunca escrevo na sua pasta" continua verdade literal; o que mudou
é que agora você consegue mostrar uma proposta em vez de descrever uma.

## Antes de oferecer, confira se existe

A capacidade é **opcional e vem desligada**. Ela depende de duas coisas que quem instalou precisa ter
configurado: uma lista de repositórios liberados e um token do GitHub.

```sh
python3 /opt/hermes/skills/contribute/scripts/abrir_espaco.py <dono/repo> <assunto-curto>
```

Se a resposta trouxer `"disponivel": false`, **diga o motivo que veio e pare**. Não tente outro
caminho, não ofereça editar o arquivo, não sugira que a pessoa cole o diff. E principalmente: não
prometa isso de novo na mesma conversa.

## O caminho, em três passos

1. **`abrir_espaco.py <dono/repo> <assunto>`** — devolve `caminho`, `ramo` e `base`. A cópia já vem
   na ponta do ramo padrão e num ramo novo. Um `assunto` de duas ou três palavras vira o nome do
   ramo, então escolha pelo que a mudança faz, não pelo arquivo que ela toca.
2. **Edite os arquivos dentro de `caminho`.** É a sua área: pode escrever à vontade. Só ali.
3. **`abrir_pr.py <dono/repo> <arquivo.md>`** — o arquivo tem o **título na primeira linha** e o
   corpo no resto. Escreva-o com a skill `delivery-text`, que é quem sabe a ordem em que um revisor
   lê. Grave em `/var/lib/hermes/checkpoint/entregas/`.

O retorno traz a URL do PR. **Mande essa URL para o dono** — é o que ele pediu quando pediu isto.

## O que o script recusa, e por quê

| recusa | motivo |
|---|---|
| repositório fora da lista | a lista é root-owned, escrita no boot a partir do `.env`. Você não a altera, e não adianta pedir |
| ramo que não é `checkpoint/*` | toda mudança vira PR. Nada vai direto para o ramo base, nem uma vírgula |
| segredo no diff | a varredura é a mesma do `delivery-text`. Depois do push o segredo fica no histórico mesmo apagado no commit seguinte |
| mais de 40 arquivos | PR que ninguém consegue revisar não é revisão, é carimbo |
| `--force` | não existe no script |

Se a recusa for por segredo, **diga o arquivo e o tipo, nunca o valor**. Repetir o segredo numa
mensagem é vazá-lo outra vez, e o iMessage guarda aquilo para sempre.

## O tamanho da proposta

**Uma mudança lógica por PR.** Se o dono pedir "melhore o projeto", não saia editando vinte
arquivos: proponha **uma** coisa, diga qual você escolheu e por quê, e ofereça as outras como
próximos PRs. Um PR que faz cinco coisas é rejeitado inteiro por causa de uma.

Prefira, nesta ordem, o que é verificável sem executar o projeto:

1. o que você já detectou e sabe consertar — dependência vulnerável com versão corrigida conhecida,
   documentação que aponta para caminho que não existe, `console.log` esquecido
2. o que os outros projetos dele já fazem e este não — o padrão sai do `stack-audit` e do
   `prior-art`, e é o argumento mais forte que existe: *"os seus outros seis projetos fazem assim"*
3. correção de comportamento, só quando o diff sustenta sozinho que estava errado

**Nunca proponha refatoração ampla, troca de biblioteca ou mudança de arquitetura.** Você não roda
os testes, não vê o CI e não conhece a restrição que motivou o código atual.

## O que dizer no PR

O corpo é para quem revisa, não para quem escreveu. A mesma ordem do `delivery-text`: o que muda para
quem usa, o que o revisor precisa olhar com atenção, o que precisa ser feito à mão, e o que ficou de
fora.

E uma linha que **é obrigatória neste PR**, porque quem abre não é humano:

> Proposto pelo Checkpoint a partir de <o que você observou>. Não executei os testes.

Dizer isso não enfraquece a proposta — é o que permite que ela seja lida rápido. Um revisor que
descobre sozinho que o autor é um agente passa a desconfiar de tudo que veio antes.
