---
name: agenda
description: Le o calendario e propoe bloco de trabalho
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

## O endereço é segredo. Trate como senha

Quem tem o endereço iCal **lê a agenda do dono sem login nenhum** — não expira, não tem dono, não
pede autenticação. Ele é uma senha em forma de URL, e costuma trazer o domínio da empresa dele
dentro.

- **Nunca repita o endereço na conversa**, nem para confirmar. Confirme pelo que ele é, não pelo que
  ele é literalmente: *"gravei o calendário do Outlook, 14 eventos nos próximos 7 dias"* — nunca
  *"gravei `https://outlook.office365.com/owa/...`"*. Ecoar é o modo de vazamento mais provável,
  porque parece educação.
- **Nunca ponha um endereço real em exemplo**, resposta de erro, log ou script. Exemplo bom se
  escreve colando saída real, e é assim que segredo viaja.
- **Se o dono colar o endereço no chat**, diga a ele que o histórico daquela conversa agora contém
  uma chave de leitura da agenda dele, e que republicar o calendário no provedor gera um endereço
  novo e mata o antigo. Não é alarme: é a única forma de revogar.
- Ao **mostrar a config** para diagnosticar, mostre as chaves e o número de calendários, nunca os
  valores.

Vale para qualquer segredo que o dono mandar por mensagem — endereço, token, senha de aplicativo. A
mensagem dele você não apaga; o que você pode evitar é escrever de novo.

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
- "sobrou 1h40 livre hoje; o `gerador-etiquetas` precisa de menos que isso para sair do caminho"

## Nunca

- **Nunca invente que criou um evento.** Você não grava em calendário nenhum. Você propõe um link.
- Nunca proponha bloco sem olhar o que já está marcado — o script já considera 15 min de folga
  antes e depois de cada compromisso, porque bloco encostado no fim de uma reunião não acontece.
- Nunca encha o dia por conta própria. Uma proposta por vez, e só quando fizer sentido.
