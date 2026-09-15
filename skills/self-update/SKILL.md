---
name: self-update
description: Se esta instalacao esta atrasada, e o que mudou
---

# Esta instalação está atualizada?

```sh
python3 /opt/hermes/skills/self-update/scripts/checar_atualizacao.py
```

Compara o commit em que **esta imagem** foi construída com o topo do repositório público. Uma
requisição à API do GitHub, sem git e sem Docker.

Respostas possíveis:

- `{"sabe": true, "atualizado": true}` — em dia. Diga só isso.
- `{"sabe": true, "atualizado": false, ...}` — traz `commits_atras`, `o_que_mudou` (as mensagens de
  commit) e `como_atualizar`.
- `{"sabe": false, ...}` — ou a imagem não registrou a própria versão, ou o GitHub não respondeu.
  **Diga que não sabe.** Não chute "está atualizado": é a resposta que faz alguém deixar de
  atualizar.

## O agente não atualiza, e isso é de propósito

Reconstruir a própria imagem exigiria o socket do Docker do host montado dentro do container — e aí
um turno com prompt injetado teria controle total da máquina de quem instalou. A escolha é
deliberada e o preço dela é este: a instalação fica parada até o dono agir.

Então **nunca ofereça atualizar, nunca diga que vai atualizar**. Entregue o comando e o que muda:

```
cd ~/checkpoint && git pull && docker compose up --build -d
```

E avise que o rebuild derruba o agente por alguns minutos — quem estiver conversando vai receber um
aviso da plataforma dizendo que o gateway está reiniciando.

## Como falar disso

Cite no máximo três mudanças, escolhendo as que afetam quem usa. Commit de documentação interna não
entra: para quem instalou, "docs: registra a decisão X" não é motivo para derrubar o agente.
