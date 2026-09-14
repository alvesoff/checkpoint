---
name: todo
description: A lista de demandas do dono — o que está pendente nos projetos dele. Nasce sozinha do estado real (trabalho não salvo, dependência que vai quebrar, segredo solto, container como root) e aceita demandas digitadas por ele. USE SEMPRE que a pergunta envolver: pendências, tarefas, demandas, to-do, lista, o que tenho para fazer, o que falta, no que devo mexer, prioridade, anota isso, me lembra de, já fiz, deixa pra depois, adia, esquece isso.
---

# Demandas

A lista do que está pendente. **A maior parte dela ninguém digitou** — ela nasce do estado dos
projetos e fecha sozinha quando a condição some.

## Onde ela mora, e por que isso precisa estar escrito aqui

Em `$HERMES_HOME/checkpoint/demandas.json` — **na sua pasta, não na do dono.** Você escreve nela
sem restrição nenhuma.

Isto está dito porque a regra "a pasta de projetos é somente leitura" já foi generalizada para
"eu não registro nada", e o agente respondeu *"não tenho To-Do próprio"* a um dono que pedia para
anotar uma tarefa — e ainda sugeriu que ele anotasse em outro sistema. As duas coisas não têm
relação: o `:ro` protege os arquivos **dele**; a lista é **sua**.

Quando ele disser "anota isso", "me lembra de", "põe na lista" ou "registra aí": rode
`adicionar` e confirme. Nunca mande ele anotar em outro lugar.

## Ver

```sh
python3 /opt/hermes/skills/todo/scripts/demandas.py listar
```

Devolve as abertas, ordenadas por peso e depois por idade. Segredo solto vem antes de versão
atrasada; dentro do mesmo peso, o que está aberto há mais tempo vem primeiro.

`fechadas_sozinhas` conta o que se resolveu sem ninguém avisar a lista — vale mencionar quando for
notícia boa: *"e três coisas saíram da lista sozinhas desde ontem"*.

## Mudar

```sh
demandas.py adicionar "<texto>" [projeto]   # o que o dono pedir para anotar
demandas.py concluir <id>                   # ele disse que fez
demandas.py adiar <id> <dias>               # "deixa pra semana que vem"
demandas.py ignorar <id>                    # "não vou fazer isso"
```

Use o `id` exato que apareceu no `listar`. Quando o dono disser "já fiz o do people-portal", **case pelo
texto e confirme o id antes**: fechar a demanda errada apaga algo que ele ainda precisa.

## O que isto resolve, e por que importa para o seu comportamento

Antes desta lista você repetia o mesmo aviso a cada faixa de dias cruzada, sem saber se a pessoa
tinha decidido não fazer. Agora **adiar e dispensar são estados**.

Então: antes de cutucar alguém sobre algo, olhe se aquilo está `adiada` ou `ignorada`. Se estiver,
**fique quieto** — insistir no que já foi dispensado é o comportamento que faz silenciar um agente.

## Como falar dela

- **Nunca despeje as 32.** Diga quantas são e leia as três primeiras.
- Demanda derivada explica a si mesma; a manual não. Ao listar uma manual, ela é do dono e você não
  sabe o contexto — só repita o que ele escreveu.
- Quando algo fechou sozinho, diga **por quê**: "o `qrcode-labels` saiu da lista, você commitou
  as imagens".
- Nunca invente prazo. A lista não tem data de entrega, tem idade — e idade é o que você informa.
