---
name: stack-audit
description: Onde os próprios projetos do dono se contradizem — Dockerfile sem healthcheck, container rodando como root, tag latest, imagens base divergentes — e segredo em arquivo que o git não está versionando. Use quando perguntarem sobre padrão, consistência, segurança dos containers, ou o que está errado nos projetos.
---

# Auditoria do seu padrão

```sh
python3 /opt/hermes/skills/stack-audit/scripts/auditar.py
```

Duas coisas num retrato só.

## Consistência entre os projetos

**Não é linter.** Linter compara o código da pessoa com a regra de outra. Isto compara os projetos
dela **entre si** — e o padrão é o que a maioria deles já faz. Com um projeto não há nada a dizer;
com vinte, a divergência é a informação.

| Campo | Como falar disso |
|---|---|
| `rodando_como_root` | O mais sério. Container sem `USER` roda como root; se alguém escapar do processo, escapa como root |
| `sem_healthcheck` | O orquestrador não sabe que o container morreu por dentro e continua mandando tráfego |
| `usando_tag_latest` | O build de amanhã não é o de hoje. Quebra sem ninguém ter mexido |
| `imagens_base` | Quando aparecem cinco variantes da mesma linguagem, é decisão repetida, não decisão tomada |

Abra pelo número, não pela lista: *"16 dos seus 24 containers rodam como root"* é uma frase que a
pessoa entende; a lista de 16 nomes ela não lê.

## Segredo em arquivo solto

Varre o que o git **não** está versionando ou o que está modificado — é onde segredo mora. Quem
commitou um `.env` normalmente já foi avisado; quem tem um `credenciais.json` solto ainda não.

**Diga o arquivo e o tipo. Nunca o valor.** Um segredo repetido numa mensagem de chat é um segredo
vazado de novo — e essa mensagem fica no histórico do iMessage para sempre.

Arquivos de exemplo (`.env.example`, `.sample`) são ignorados de propósito: são documentação de
quais variáveis existem, não vazamento.

## Como entregar

Isto não é uma lista de tarefas para despejar. Escolha **o mais grave** e diga em uma frase, com o
número, oferecendo o resto:

> 16 dos seus 24 containers rodam como root, e um está preso em `:latest`. Quer a lista?

Nada disso é urgente no sentido de interromper o dia. É informação que a pessoa usa quando for mexer
no projeto — então entregue quando perguntarem, ou junto de algo que ela já esteja fazendo naquele
projeto.
