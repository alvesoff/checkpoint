---
name: prior-art
description: Como o dono ja resolveu isso antes, nos projetos dele
---

# Como eu fiz isso da última vez?

A resposta não está na memória de ninguém: está no código que o próprio dono escreveu. Vinte e
cinco repositórios são grandes demais para lembrar e pequenos demais para procurar no Google.

```sh
python3 /opt/hermes/skills/prior-art/scripts/buscar.py "<o que procurar>" [extensao]
```

Exemplos:

```sh
python3 /opt/hermes/skills/prior-art/scripts/buscar.py "healthcheck" yml
python3 /opt/hermes/skills/prior-art/scripts/buscar.py "refresh token"
python3 /opt/hermes/skills/prior-art/scripts/buscar.py "retry" py
```

O segundo argumento é uma extensão e é opcional; sem ele a busca cobre tudo.

## Por que não é um grep

O resultado vem **agrupado por projeto** e ordenado pelo commit mais recente. Num conjunto de
projetos, a versão mais nova de um padrão costuma ser a que já corrigiu os problemas das anteriores
— então a ordem é a informação, não enfeite. Um `grep` devolve trinta ocorrências em ordem
alfabética; isto devolve *"três projetos fazem isso, e o mais recente é este"*.

`node_modules`, `.venv`, `dist` e companhia ficam de fora: a implementação de um pacote de terceiro
não é precedente do dono.

## Como responder

Diga **em quantos projetos** existe precedente antes de mostrar qualquer código — é o número que
diz se aquilo é um padrão dele ou uma tentativa isolada. Depois mostre o trecho do mais recente,
com projeto, arquivo e linha, para ele poder abrir.

Exemplo do tom:

```
Você já fez isso em 3 projetos.

O mais recente é o portal-cliente, em docker-compose.yml linha 14:
  healthcheck: curl -f http://localhost:3000/health || exit 1

Os outros dois usam a mesma forma. Abro algum?
```

Quando não houver nada, diga isso e **diga o alcance da busca** — o campo `limites` vem na saída.
"Não encontrei" sem dizer onde procurou faz o dono concluir que ele nunca resolveu aquilo, quando
talvez a busca só não tenha chegado lá.

Nunca invente precedente que a busca não devolveu, e nunca cole o valor de um segredo que apareça
num trecho: diga o arquivo e a linha.
