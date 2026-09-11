---
name: where-i-left-off
description: Reconstrói onde o trabalho parou em cada projeto lendo os artefatos do repositório — branch, último commit, alterações não salvas, commits não enviados. Use quando perguntarem onde pararam, o que está travado, o que está em voo, ou ao preparar um cutucão sobre trabalho parado.
---

# Onde eu parei

Responde "onde eu parei?" a partir do que os repositórios dizem, não do que a
pessoa lembra de ter contado. É a razão de existir deste agente.

## Quando usar

- "onde eu parei no <projeto>?"
- "o que eu tenho em voo?", "o que está travado?"
- "no que eu estava mexendo ontem / sexta?"
- Ao montar um aviso sobre trabalho parado (o serviço de cutucão chama este mesmo script).

## Como usar

```sh
python3 /opt/hermes/skills/where-i-left-off/scripts/scan_projects.py
```

Devolve JSON com um objeto por projeto ativo, **ordenado do mais parado para o
mais recente**. Sem argumentos: ele lê a raiz montada (`/projects` por padrão,
ou `PROJECTS_ROOT`).

Campos que importam para a resposta:

| Campo | O que significa de verdade |
|---|---|
| `arquivos_alterados` | Trabalho feito e **não salvo em lugar nenhum**. O sinal mais forte de "parei no meio" — some se a máquina morrer, e ninguém além da pessoa vê |
| `commits_nao_enviados` | Trabalho salvo localmente que **ninguém mais recebeu** |
| `branch_sem_upstream` | Branch criado e nunca enviado — trabalho invisível para o time |
| `ultimo_toque_ha_dias` | Há quanto tempo o projeto foi **realmente** tocado (arquivo modificado). É este o relógio de "parado", não a data do commit |
| `ultimo_commit.ha_dias` | Há quanto tempo foi salvo no git. Pode ser muito maior que o toque — e aí a diferença **é** a notícia |
| `nunca_versionado` | Um commit só e vários arquivos fora do git: não está parado, nunca entrou no git |
| `ultimo_commit.assunto` | A pista mais direta do que a pessoa estava fazendo |

## Como responder

Reconstrua a cena, não recite o JSON. A pessoa quer voltar a trabalhar, não ler
um relatório.

- Diga **o que ela estava fazendo** (assunto do último commit) e **o que ficou
  pela metade** (os arquivos alterados), nessa ordem.
- Quando houver alteração não salva, nomeie os arquivos: é o que faz a memória voltar.
- Um projeto parado há 4 dias com alteração não salva é a coisa mais urgente da
  lista, mesmo que outro tenha prazo mais próximo. Trabalho não salvo se perde.
- **Diga há quanto tempo foi tocado, não há quanto tempo foi commitado**, e
  quando os dois divergem muito, essa divergência é a informação principal:
  "você mexeu nisso há 14 dias, mas o último commit é de 88" quer dizer que há
  duas semanas de trabalho sem histórico nenhum. Dizer "parado há 88 dias" para
  quem mexeu no projeto há duas semanas queima a confiança na resposta inteira.
- Se perguntarem de um projeto específico, responda só dele. A lista inteira
  quando a pergunta é "o que eu tenho em voo".
- Não invente próximo passo que o repositório não sustenta. Se o último commit
  diz "wip: validação de CPF pela metade", o próximo passo é esse. Se não diz
  nada útil, diga o que ficou aberto e pergunte.

## Limites que você deve declarar

- Só enxerga o que está montado em `/projects`, e **somente leitura**. Nunca
  ofereça commitar, enviar ou alterar arquivo: a montagem é `:ro` e a tentativa
  vai falhar.
- `arquivado` (sem commit há mais de 90 dias) sai da lista de propósito. Se
  perguntarem por um projeto que sumiu, é provavelmente isso — diga.
- Se `/projects` não existir ou não tiver repositório, o script devolve `erro` e
  `como_resolver`. Repasse o `como_resolver` em vez de adivinhar.

## O cutucão (aviso na hora certa)

Registre uma vez, quando o dono pedir para ser avisado sozinho:

```sh
python3 /opt/hermes/skills/where-i-left-off/scripts/register_nudge.py
```

É idempotente — rodar de novo não cria um segundo aviso.

Como funciona, e por que não vira spam: o cron roda `nudge_digest.py` de hora em
hora, e esse script imprime uma **assinatura estável** do que está travado, sem
nenhuma data dentro. Saída igual à do tique anterior não acorda você e não
consome token. A assinatura só muda quando um projeto **cruza** para uma faixa
pior de dias parados, ou quando o tipo de pendência muda — e é aí que vale
interromper alguém.

Quando você for acordado por isso, o bloco MONITOR traz o que mudou no formato
`projeto|branch|estado|faixa`. Fale **só do que mudou**, nunca da lista inteira,
e mande uma mensagem só. Se a mudança não merecer interromper ninguém, responda
`NO_REPLY`.
