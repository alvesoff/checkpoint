---
name: dependency-radar
description: O que vai quebrar antes de quebrar. Mapeia todo pacote usado em todos os projetos, cruza com os registros npm e PyPI, e diz em quantos projetos cada problema atinge. Use quando perguntarem sobre dependências, atualização, versão, o que está desatualizado ou o que pode quebrar.
---

# Radar de dependências

Responde "o que vai me quebrar?" com o que está instalado nos projetos da pessoa, não com conselho
genérico.

## O retrato

```sh
python3 /opt/hermes/skills/dependency-radar/scripts/deps_scan.py
```

Devolve JSON com os achados **ordenados por quantos projetos cada um atinge** — que é a ordem da
urgência real. Um pacote atrasado em nove projetos e um atrasado em um não são o mesmo problema.

Tipos de achado:

| `tipo` | O que significa |
|---|---|
| `abandonado` | O mantenedor marcou como deprecated. O `detalhe` traz o recado dele, que quase sempre diz o substituto |
| `majors_atras` | A pessoa está em um major anterior ao atual. `voce_usa` e `atual` mostram o salto |

A primeira varredura demora (uma consulta por pacote distinto); as seguintes leem cache de 24h.

## O que fazer com isso — e é aqui que você se diferencia

**Nunca entregue a lista crua.** Uma lista de "saia da versão X para a Y" é exatamente o que o
Dependabot manda e o que todo mundo ignora. O que ninguém faz — e você faz — é responder **se aquilo
quebra o código que a pessoa realmente escreveu**.

Para o achado mais espalhado, faça os três passos:

1. **Leia o que muda.** Use a skill `browsing` para abrir o changelog ou o guia de migração da
   versão nova. Procure a seção de *breaking changes*.

2. **Procure o uso real.** Para cada símbolo removido ou alterado, busque nos projetos afetados:

   ```sh
   rg -n --no-ignore "req\.param\(" /projects/portal-atendimento /projects/portal-cliente
   ```

3. **Responda com o cruzamento**, não com a versão:

   > O Express 5 remove `req.param()`. Você usa em 3 arquivos, no `portal-atendimento` e no
   > `portal-cliente`. Atualizar sem mexer quebra o login dos dois. A troca é direta: `req.params`.

   Se a busca não achar uso nenhum do que foi removido, diga isso — é a melhor notícia possível:
   *"o salto do Vite 5 para o 8 não toca em nada que você usa; dá para atualizar sem medo"*.

## Limites que você declara

- Lê `package.json` e `requirements*.txt`. Não lê lockfile, então fala de **versão declarada**, não
  da resolvida.
- Pacote privado ou interno não existe no registro público: some da lista em silêncio, porque não há
  o que dizer sobre ele.
- Major atrás **não é** sinônimo de quebrado. É sinal de onde olhar. Quem decide se quebra é o passo
  2, no código da pessoa.

## O aviso automático

O `deps_digest.py` é o `--monitor-script` deste radar: imprime uma assinatura estável e só acorda o
agente quando ela muda. São **três** gatilhos, e o terceiro é o que mais importa:

- um pacote **passa** a ficar para trás;
- um pacote passa a ser abandonado;
- **uma vulnerabilidade grave passa a existir num pacote que a pessoa usa** — este não depende de
  ninguém publicar versão nova, e é o único que pode aparecer sem que nada no projeto tenha mudado.

Enquanto nada muda, silêncio e zero token.

Registre uma vez, quando o dono pedir para ser avisado:

```sh
python3 /opt/hermes/skills/dependency-radar/scripts/register_radar.py
```

## Vulnerabilidade conhecida

```sh
python3 /opt/hermes/skills/dependency-radar/scripts/vulneraveis.py
```

Consulta a base pública da OSV com as versões que os manifestos declaram. Devolve os achados
ordenados por gravidade e, dentro dela, por **quantos projetos cada um atinge** — que é a ordem em
que se conserta quando se tem vinte repositórios.

| Campo | Como ler |
|---|---|
| `pior` | `CRITICAL` e `HIGH` merecem interromper alguém. `MODERATE` e abaixo vão para a lista, não para o chat |
| `nao-consultada` | A gravidade **não foi buscada** para esse pacote, porque só os 12 mais espalhados são detalhados. Não é "sem problema" — é ausência de dado, e diga assim |
| `quantos` | Em quantos projetos aparece. É o que `npm audit` não responde, porque ele olha um projeto de cada vez |

**Sempre declare o limite ao falar disso:** são as versões **declaradas no manifesto**, não as
resolvidas pelo lockfile. Um alarme sobre versão que o lockfile já corrigiu ensina a pessoa a
ignorar os alarmes verdadeiros — então diga "declarada no package.json" e sugira conferir o
lockfile antes de mexer.
