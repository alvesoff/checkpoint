---
name: daily
description: O resumo do dia — de manhã, quanto tempo sobra depois das reuniões e o que dá para atacar; à noite, o que foi commitado, o que continua fora do git e em que estado está o projeto da primeira reunião de amanhã. Use quando perguntarem sobre o dia, o que fazer hoje, como foi o dia, ou o que tem amanhã.
---

# O resumo do dia

```sh
python3 /opt/hermes/skills/daily/scripts/resumo.py manha
python3 /opt/hermes/skills/daily/scripts/resumo.py noite
```

## Por que este resumo não é mais um digest

Digest de tarefas lista o que existe. Este responde **o que cabe**, porque o calendário entra na
conta. Calendário guarda intenção, git guarda realidade, e essa junção é a única coisa aqui que
nenhuma outra ferramenta faz.

### De manhã — o que é realista

`horas_livres_estimadas` é a jornada menos o tempo já comprometido. Use esse número para falar de
**frentes, não de tarefas**:

> 3h de reunião hoje, das 9h às 10h30 e das 14h às 15h30. Sobram 5h.
>
> qrcode-labels · 4 arquivos não salvos · 14 dias
> payroll-api · 3 arquivos não salvos · 3 dias
>
> Com 5h dá para fechar um desses, não os dois. Qual?

Dia sem reunião e sem projeto parado não merece mensagem. Responda `NO_REPLY`.

### À noite — o que ficou, e o que amanhã vai cobrar

A ordem importa e a última linha é a que vale:

| Campo | O que fazer com ele |
|---|---|
| `onde` | O que ele commitou hoje. Uma linha, curta — é reconhecimento, não relatório |
| `ainda_nao_salvo` | O mais antigo primeiro. Isto some se a máquina morrer, e ninguém além dele sabe que existe |
| `reuniao_cruzada_com_projeto` | **A frase mais valiosa da mensagem.** Vai por último |

O cruzamento é assim:

> Amanhã sua primeira reunião é 15h, sobre os projetos NetSuite. Esse projeto tem 2 arquivos
> alterados e não salvos desde quarta.

Repare no que aconteceu: ninguém disse ao agente que aquela reunião era sobre aquele projeto. O
nome saiu do título do evento e o estado saiu do `git status`. É o momento em que o produto se
explica sozinho.

Quando `reuniao_cruzada_com_projeto` vier vazio, **não invente ligação**. Diga a reunião e pare — a
maioria das reuniões não é sobre um repositório, e forçar a conexão é o jeito mais rápido de perder
a confiança na que é verdadeira.

## Os horários

```sh
python3 /opt/hermes/skills/daily/scripts/register_daily.py
```

Registra `checkpoint-manha` (8h) e `checkpoint-noite` (18h), em dias úteis. São os **únicos** dois
cronjobs do Checkpoint que falam por horário; todos os outros só acordam quando alguma coisa muda.
A exceção é consciente: aqui o valor é o ritmo, e um resumo que só chega quando muda algo não é um
resumo, é mais um alerta.

Se o dono quiser desligar um deles, é `hermes cron delete <id>` — e vale oferecer isso antes de ele
começar a ignorar as mensagens, porque quem ignora não volta.
