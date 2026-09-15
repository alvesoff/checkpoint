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

---

# Branches que sobraram

```sh
python3 /opt/hermes/skills/stack-audit/scripts/branches.py
```

Duas perguntas que parecem uma só, e confundi-las é como se apaga trabalho:

| Campo | O que é | O que dizer |
|---|---|---|
| `ja_mescladas` | Todo commit dela já está no branch principal. É entulho | A única coisa aqui que se pode dizer que é seguro apagar |
| `esquecidas_nao_mescladas` | Parada há mais de 30 dias **e** com commit que não existe em nenhum outro lugar | Isto não é entulho, é trabalho esquecido. `commits_so_dela` diz quanto se perderia |

A diferença sai de `git merge-base --is-ancestor`, não de nome nem de data: uma branch chamada
`feature/velha` de seis meses atrás pode estar inteira na `main`, e uma de ontem pode ter trabalho
que só existe ali.

**Comece sempre pelas esquecidas**, mesmo sendo menos. Uma branch com 8 commits parada há 90 dias é
alguém que resolveu um problema, foi interrompido, e esqueceu que resolveu:

> `gerador-etiquetas` tem uma branch parada há 97 dias com 8 commits que não estão na develop.
> O último assunto é "valida leitura offline do QR". Isso não está em lugar nenhum além da sua
> máquina.

Das mescladas, fale pelo número e só se perguntarem, ou junto de outra coisa naquele projeto:

> Você tem 13 branches já mescladas encostadas. Nenhuma tem trabalho único — é limpeza, quando der.

**Nunca ofereça apagar.** A pasta é somente leitura e você não roda `git branch -d` de ninguém; e
mesmo que rodasse, decidir o que fazer com branch é de quem escreveu o código. Você diz o que há;
ele decide.

## O vigia de segredo, que acorda sozinho

`audit_digest.py` é o `--monitor-script` desta skill: imprime uma assinatura estável dos segredos em
arquivo solto — `projeto|segredo|arquivo|tipos`, **nunca o valor** — e só acorda o agente quando ela
muda. De 4 em 4 horas, não de 12 como o vigia de documentação: documento desatualizado espera,
credencial exposta não.

Só segredo entra na assinatura. Dockerfile como root, imagem base velha e falta de healthcheck são
verdadeiros e importantes, e **não mudam sozinhos** — viram demanda na lista, não interrupção. Um
monitor que acorda o agente para repetir o que disse ontem é um monitor que a pessoa desliga.

Registre uma vez, quando o dono pedir para ser avisado:

```sh
python3 /opt/hermes/skills/stack-audit/scripts/register_audit.py
```

No boot ele já é registrado sozinho, junto dos outros quatro.
