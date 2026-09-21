---
name: radar-de-pauta
description: Acompanha as fontes publicas que o dono cadastrou e avisa quando varias cobrem o mesmo assunto
---

# Radar de pauta

Responde "sobre o que todo mundo está falando hoje?" com as fontes que **o dono** cadastrou — nunca
com uma lista escolhida por você.

## As fontes

```sh
python3 /opt/hermes/skills/radar-de-pauta/scripts/pauta.py fonte list
python3 /opt/hermes/skills/radar-de-pauta/scripts/pauta.py fonte add "@canal"
python3 /opt/hermes/skills/radar-de-pauta/scripts/pauta.py fonte add "https://site/feed"
python3 /opt/hermes/skills/radar-de-pauta/scripts/pauta.py fonte remove <id>
```

A lista nasce **vazia**. Sem fonte não há radar: se ele perguntar e não houver nenhuma, ofereça
cadastrar e peça o canal ou o site. **Nunca sugira uma fonte por conta própria** — o que ele
acompanha é escolha dele.

`add` aceita `@handle`, URL de canal do YouTube ou qualquer RSS/Atom, e resolve o resto sozinho.

## O retrato

```sh
python3 /opt/hermes/skills/radar-de-pauta/scripts/coleta.py
```

Lê todos os feeds e guarda o que ainda não tinha visto. Devolve quantos itens entraram e quais
fontes estão quebradas. Roda sozinho no tique do cron — chame à mão só quando ele pedir "olha agora".

## O que decide um assunto

```sh
python3 /opt/hermes/skills/radar-de-pauta/scripts/pauta_digest.py
```

Uma linha por assunto que **várias fontes distintas** cobriram:

```
ASSUNTO|chave|quantas-fontes|nomes das fontes|titulo // titulo // titulo
FONTE_CEGA|id        # falhou 3 vezes seguidas
```

O agrupamento é aritmética de palavra rara, sem nenhuma inferência. **O julgamento é seu, no turno.**

## O que fazer com isso

**Nunca despeje a lista.** Cinco assuntos numa mensagem é a forma mais rápida de alguém desligar o
aviso.

1. **Escolha um.** O critério é quantas fontes distintas cobriram — é o único sinal objetivo de que
   o assunto saiu da bolha de uma redação só.
2. **Diga quantas cobriram e quais**, porque é isso que separa "está todo mundo falando disso" de
   "um site publicou".
3. **Ofereça o resto**, em uma linha. Não liste.

Se nada cruzou o limiar, **não invente pauta**: um dia sem assunto repetido é informação, e o certo
é `NO_REPLY` no cron.

`FONTE_CEGA` é o único caso em que você fala de manutenção: diga qual fonte parou e ofereça remover.

## Nunca

- Nunca opine sobre o mérito do conteúdo. Você diz que várias fontes cobriram, não se a notícia é
  boa, verdadeira ou importante para o público dele.
- Nunca publique nada em lugar nenhum. Este radar **lê**.
- Nunca trate o que a fonte disse como fato seu. É o título dela, com o link dela.
