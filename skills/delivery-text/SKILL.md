---
name: delivery-text
description: Escreve o texto que falta para um trabalho ser entregue — mensagem de commit, descrição de PR, resumo do que mudou. Lê o diff real e os commits do branch. USE SEMPRE que pedirem: mensagem de commit, descrição de PR, o que escrever no pull request, resumo das mudanças, changelog, o que mudei nesse projeto, como descrevo essa entrega.
---

# Texto de entrega

O código está pronto; o texto que acompanha, não. Esta skill escreve esse texto a partir do que o
repositório diz — não do que a pessoa lembra de ter feito.

## Os fatos

```sh
python3 /opt/hermes/skills/delivery-text/scripts/preparar_entrega.py <projeto> [base]
```

Sem `base`, ele usa o upstream do branch; sem upstream, o branch principal do repositório.

| Campo | Para que serve |
|---|---|
| `commits_alem_da_base` | A narrativa da entrega. **Agrupe por intenção, não por ordem cronológica** — dez commits viram três parágrafos, nunca dez linhas |
| `arquivos` | O escopo. Lockfile e minificado já foram descontados, porque inflam o número e escondem o que interessa |
| `superficie_publica` | Rota, export, variável de ambiente, migração, dependência nova. **É o que o revisor lê primeiro** |
| `pontos_a_confirmar` | O que um revisor humano bom perguntaria |
| `arquivos_nao_salvos` | Trabalho que ainda nem entrou no commit |

## A regra que não se quebra

**Nenhuma frase sem algo no diff que a sustente.** Se você não achou a evidência, escreva a lacuna
em vez de preencher com suposição:

> falta descrever: mudança em `auth/session.ts` sem contexto óbvio no diff

Texto de entrega bonito e errado vai para o histórico do repositório, e alguém confia nele depois.
Uma lacuna explícita custa uma pergunta; uma invenção custa um incidente.

## Mensagem de commit

Quando houver trabalho não salvo e a pessoa pedir a mensagem:

- Conventional Commits quando o repositório já usa (olhe os commits anteriores — o padrão dele ganha
  do seu).
- **Uma alteração lógica por commit.** Se `pontos_a_confirmar` disser que a entrega toca quatro
  áreas, proponha **dividir em commits separados antes de escrever a mensagem** — descrição honesta
  de commit bagunçado é impossível, e é melhor dizer isso que produzir um texto vago.
- O corpo responde **por quê**, não o quê: o `git diff` já conta o quê.

## Descrição de PR

Nesta ordem, porque é a ordem em que se lê:

1. **O que muda para quem usa.** Uma ou duas frases, sem jargão.
2. **O que o revisor precisa olhar com atenção** — vem de `superficie_publica`.
3. **O que precisa ser feito à mão** no deploy: migração, variável nova, ordem de subida.
4. **O que ficou de fora**, se houver — e os `pontos_a_confirmar` entram aqui, como pergunta ao
   autor, nunca como acusação.

## Como entregar pelo chat

Uma descrição de PR não cabe numa mensagem de texto. Mande **as primeiras linhas** e diga que o
texto completo está em `/var/lib/hermes/checkpoint/entregas/<projeto>.md` — grave lá antes de
avisar. Mensagem de quarenta linhas no iMessage ninguém lê e ninguém copia.
