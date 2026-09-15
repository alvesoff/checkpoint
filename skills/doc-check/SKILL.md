---
name: doc-check
description: Onde a documentação do projeto já não bate com o código — README que manda rodar comando que não existe, link que aponta para arquivo apagado, variável que o código exige e nenhum documento menciona. Use quando perguntarem sobre documentação, README, se as instruções estão certas, ou por que o projeto não sobe na máquina de outra pessoa.
---

# Conferência de documentação

```sh
python3 /opt/hermes/skills/doc-check/scripts/conferir_docs.py           # todos os projetos
python3 /opt/hermes/skills/doc-check/scripts/conferir_docs.py <projeto> # um só
```

## O que ele confere, e o que ele se recusa a conferir

**Só o verificável.** Nada de "o README está incompleto" ou "falta uma seção de arquitetura" — isso é
opinião sobre texto alheio, e opinião não se checa contra nada. Três achados, cada um comprovável
abrindo o repositório:

| Campo | O que é, e por que dói |
|---|---|
| `referencias_quebradas` | O documento aponta para um caminho que não existe mais. Alguém renomeou e não voltou no texto |
| `comandos_que_sumiram` | O texto manda rodar `npm run X` e o `package.json` não tem `X`. É o comando que a pessoa copia, cola e vê falhar no primeiro minuto |
| `variaveis_exigidas_sem_documentacao` | O código lê a variável **sem valor padrão** — ou seja, o processo morre sem ela — e nenhum documento nem `.env.example` diz que ela existe. É o que faz o projeto subir na máquina de quem escreveu e em nenhuma outra |

Variável **com** valor padrão não entra: o projeto sobe sem ela, então não documentá-la não quebra
ninguém. Variável que o sistema operacional ou o framework já entregam (`SHELL`, `USERPROFILE`,
`NEXT_RUNTIME`) também não — não é configuração de ninguém.

## Como entregar

Abra pelo que quebra alguém **agora**, que é referência e comando, não pela lista de variáveis:

> O README do `metrics-dashboard` manda o banco ficar em `./data/status.db`, e esse caminho não existe no
> repositório. Quem seguir o passo a passo trava aí.

**Antes de dizer que um comando não existe, confira onde ele poderia estar.** Em monorepo com
`workspaces`, um `npm run X` que não está na raiz costuma estar num sub-pacote — e aí ele existe, só
não roda do diretório que o documento sugere. Dizer "não existe" sobre coisa que existe é o erro que
faz a pessoa parar de conferir tudo o que você diz. Se for esse o caso, diga o que é de verdade:
*"esse script está em `server/package.json`; do diretório onde o documento coloca você, ele falha"*.

Para variáveis, o número primeiro e o nome perigoso depois:

> O `sso-interno` exige 4 variáveis que nenhum documento cita, e uma delas é `GRAPH_CLIENT_SECRET`.
> Em outra máquina o projeto não sobe, e o erro não vai dizer isso.

Nunca despeje os três blocos de doze projetos numa mensagem. Escolha o projeto com o achado mais
grave, diga em duas linhas e ofereça o resto.

## A correção — e o limite que você declara junto

**Você não escreve nos projetos.** A pasta é montada somente leitura, imposta pelo Docker; isso não
é uma regra que você segue por educação, é uma coisa que o sistema não deixa acontecer, e é o que
torna seguro te darem essa pasta.

Então o fluxo de correção é este, e diga-o com todas as letras quando oferecer:

1. Você mostra a divergência e **escreve o texto corrigido** — a linha do README com o comando certo,
   o bloco de `.env.example` com as variáveis que faltam, o link com o caminho novo.
2. O dono cola. Leva dez segundos e a decisão continua dele.

Nunca diga "eu corrijo" nem "já corrigi". Diga "escrevo a correção pra você colar". Prometer
escrita que o container não pode fazer é o pior erro possível aqui: a pessoa confia, não confere, e
o documento continua errado.

Antes de escrever a correção, **leia o arquivo** (você tem leitura) e proponha a menor mudança que
resolve. Reescrever o README inteiro porque um comando mudou é destruir trabalho de alguém para
consertar uma linha.

## O aviso automático

```sh
python3 /opt/hermes/skills/doc-check/scripts/register_docs.py
```

O `docs_digest.py` é o `--monitor-script`: imprime uma assinatura estável das divergências e só
acorda o agente quando ela **muda** — quando uma referência passa a apontar para nada, quando um
comando some do `package.json`, quando uma variável nova entra no código sem entrar na documentação.
O tempo passando sobre uma divergência que o dono já conhece não acorda ninguém.

---

# Escrever a documentação de um projeto

Quando o dono pedir — *"documenta o payroll-api"*, *"escreve o README do X"* — o trabalho é
**um projeto só, do começo ao fim**. Nada de amostra, nada de esboço, nada de "posso continuar?".

## Primeiro o retrato, sempre

```sh
python3 /opt/hermes/skills/doc-check/scripts/retrato_projeto.py <projeto>
```

Devolve o que o projeto diz sobre si mesmo: comandos do `package.json`, arquivos que revelam como
ele sobe, variáveis exigidas sem valor padrão, rotas HTTP encontradas no código, pastas de primeiro
nível, quem mexeu, último commit.

**Documentação escrita de cabeça é pior que documentação ausente, porque soa verdadeira.** Toda
frase que você escrever precisa apontar para algo dessa saída. O que não estiver lá, **pergunte** —
não suponha.

## A estrutura, e ela não é negociável

Quem abre o documento tem que entender o projeto em menos de um minuto:

1. **O que faz** — o problema que resolve, em uma ou duas frases. Não "sistema de gestão": *"controla
   a o ponto da equipe e fecha a folha de horas do mês"*.
2. **Stack** — linguagem, framework, banco. Saem de `dependencias_principais` e dos arquivos de
   execução.
3. **Como rodar** — o caminho completo, do clone ao serviço de pé. Os comandos vêm de
   `comandos_npm` e de `arquivos_que_dizem_como_sobe`; **não invente um `npm start` que não existe**.
4. **Variáveis de ambiente** — uma tabela com nome, para que serve e se é obrigatória. As de
   `variaveis_exigidas_sem_padrao` são obrigatórias: sem elas o processo morre na primeira linha.
   Nunca escreva o valor de nenhuma, só o nome e o formato.
5. **Estrutura** — as pastas de primeiro nível e o que vive em cada uma.
6. **Rotas ou interface pública**, quando houver — de `rotas_encontradas`.
7. **Status** — em desenvolvimento, estável ou em manutenção. Isso você **não sabe**: pergunte.

## Como entregar

A pasta é somente leitura: você **não grava o arquivo**. Entrega o markdown completo, pronto para
colar em `README.md`, e diz onde colar.

É documento longo — não cabe numa mensagem de iMessage e não deve ser picotado em dez. Escreva o
documento inteiro numa resposta só e avise que é para colar de uma vez.

**O que você marca em vez de inventar:** onde faltar informação que nenhum arquivo dá — o porquê de
uma decisão, quem é o dono, o que é status — escreva `<!-- confirmar com o dono: ... -->` no meio do
texto e liste essas dúvidas no fim da mensagem. Um documento com três lacunas honestas é melhor que
um documento com três frases plausíveis e falsas.
