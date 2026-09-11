---
name: agenda
description: Lê os compromissos do dono pelo endereço iCal do calendário (Google, Outlook/M365 ou Apple) e propõe blocos de trabalho em horários livres, entregues como link de um toque. Use quando falarem de agenda, reunião, horário, tempo disponível, ou ao dizer se um plano cabe no dia.
---

# Agenda

Você **lê** o calendário e **propõe**. Quem grava é o dono, com um toque.

Isto não é gerenciar a agenda de ninguém — existe agente demais fazendo isso. É usar a agenda para
responder a pergunta que só você consegue: **o que é realista hoje, dado o que está pendente no
código e o tempo que sobra.**

## Ler

```sh
python3 /opt/hermes/skills/agenda/scripts/ler_agenda.py [dias]
```

Devolve os eventos da janela, `minutos_ocupados` e quais calendários falharam. Calendário fora do ar
**é dito**, nunca tratado como dia livre.

Se não houver calendário configurado, o script devolve `como_resolver` com o caminho exato no Google
e no Outlook. Repasse isso em vez de adivinhar — e grave o endereço que a pessoa mandar em
`$HERMES_HOME/checkpoint/config.json`, na lista `calendarios`.

## Propor um bloco

```sh
python3 /opt/hermes/skills/agenda/scripts/propor_bloco.py "Fechar o erp-cutover" 90
```

Devolve até três horários livres, cada um com link para Google e para Outlook. O link abre o evento
já preenchido; o dono confirma tocando.

Manda **um** horário por mensagem, com o link, e pergunta. Três links de uma vez viram parede.

## Onde isto ganha valor

Cruze a agenda com o estado dos projetos — é a única coisa aqui que ninguém mais faz. Calendário
guarda intenção; git guarda realidade.

- "amanhã 9h você tem reunião sobre o deploy do `payroll-api`, e esse projeto tem 3 arquivos não
  commitados desde ontem"
- "você tem 3h de reunião hoje e 4 projetos parados; dá para atacar um, não quatro"
- "sobrou 1h40 livre hoje; o `qrcode-labels` precisa de menos que isso para sair do caminho"

## Nunca

- **Nunca invente que criou um evento.** Você não grava em calendário nenhum. Você propõe um link.
- Nunca proponha bloco sem olhar o que já está marcado — o script já considera 15 min de folga
  antes e depois de cada compromisso, porque bloco encostado no fim de uma reunião não acontece.
- Nunca encha o dia por conta própria. Uma proposta por vez, e só quando fizer sentido.
