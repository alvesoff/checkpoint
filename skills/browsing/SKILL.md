---
name: browsing
description: Abre paginas na web, pela maquina do dono quando existe
---

# Navegar

Você tem dois navegadores possíveis e eles **não** são equivalentes. Escolha antes de agir.

## Primeiro: descubra qual você tem

```sh
python3 /opt/hermes/skills/browsing/scripts/check_mac.py
```

Responde `{"maquina": true, "ferramentas": [...], "plataforma": "...", "skills": [...]}` ou
`{"maquina": false, "motivo": "..."}`. Pode vir também `defeitos_desta_maquina` e
`autoteste_inconclusivo` — leia a seção sobre eles antes de anunciar qualquer coisa ao dono.

Custa uma chamada e evita o erro mais caro que você pode cometer: prometer usar o computador de
alguém que não tem nenhum conectado. A plataforma injeta a descrição do Plow Latch na sua persona
**mesmo quando não há máquina nenhuma do outro lado** — então a sua descrição não é prova de nada.
Este script é.

**A máquina do dono não é necessariamente um Mac.** O Latch tem versão de Windows e de Linux, e o
`plataforma` da resposta diz qual é. Isso decide o que você oferece: `osascript` e AppleScript só
existem no macOS; num Windows o que serve é `powershell`, `where`, `clip` e os builtins do `cmd`.
As próprias descrições das ferramentas já chegam na plataforma certa — se elas disserem Windows,
elas estão certas e qualquer texto seu que diga Mac está errado.

### Se vier `defeitos_desta_maquina`, diga a frase de lá — não invente explicação

Cada item traz `diga_ao_dono` com o texto certo, e `ainda_da` com o que continua funcionando. Use
**essa** frase. Em 21/09, diante de três defeitos do app de Latch, o agente mandou o dono *"reportar
no painel do Plow ou reinstalar o Latch"* nas três vezes — nenhuma das duas resolve nenhum dos três,
e a pessoa fica sem saber o que fazer.

O mais comum, e o mais confuso: **nenhum comando roda** (todo `plow_run_command` volta com *"outside
the approved staged workspace"*). Não é permissão do Windows, não é antivírus, e reinstalar não
muda. Ler e gravar arquivo continuam funcionando — trabalhe por eles.

### Se vier `autoteste_inconclusivo`, NÃO anuncie nada

É o app reportando que o autoteste do sandbox dele falhou por conta própria. Se o sandbox não
conseguisse lançar processo, a mensagem seria *"outside the approved staged workspace"* e teria vindo
como defeito. Qualquer outro erro significa que processo **roda** e a sonda do autoteste é que está
errada — medido em 21/09 numa máquina em que os comandos funcionavam.

Tente o comando. Se ele falhar, aí sim diga o erro que veio. Anunciar que a máquina do dono está
quebrada quando ela não está tem o mesmo efeito de recusar: ele para de pedir.

### Se vier `latch_incompleto: true`, o problema é de montagem, não de permissão

O Latch publica **uma** skill (`plow-folder`) enquanto os plugins e o navegador não são montados na
máquina do dono — e montar é um passo separado, que nada no caminho de instalação lembra de fazer.
Sem as outras, o `plow_browser_*` não tem navegador e não há CLI de Google.

**Diga a ele o que está no `o_que_falta` e nada além disso.** O que **não** se pode fazer é concluir
que o produto não faz aquilo, nem mandá-lo pedir permissão à plataforma: o Gmail e o Google Calendar
saem da skill `google-workspace`, o navegador logado da `camoufox-browsing`, e as duas aparecem
depois de `just stage-plugins` e `just fetch-browser` no diretório do Latch. Já aconteceu em 21/09 —
o agente mandou o dono procurar a plataforma quando faltavam dois comandos na máquina dele.

## Com máquina do dono (`maquina: true`)

Use as ferramentas do Latch. O navegador é o **da pessoa**, com as sessões dela já autenticadas:
alcança portal com login, painel de serviço, conta de banco, sistema interno. É a capacidade mais
poderosa que você tem.

Regras:
- Toda ação passa pela aprovação do dono. Não tente contornar, não insista se for negado.
- Diga o que vai fazer antes de fazer.
- Nunca leia credencial, nem repita na conversa o que aparecer numa tela de senha.

## Sem máquina do dono (`maquina: false`)

Use o navegador do container:

```sh
CHROME=$(find /opt/hermes/.playwright -name chrome-headless-shell -type f | head -1)
"$CHROME" --headless --disable-gpu --no-sandbox --dump-dom "<url>"
```

Ele alcança **qualquer página pública** — changelog, release notes, guia de migração, documentação,
issue de repositório, página de status. Não alcança nada que exija login, porque é um navegador
limpo, sem sessão nenhuma.

Quando a pessoa pedir algo que precise de login e não houver máquina conectada, diga isso direto e
ofereça o que dá: *"isso precisa da sua sessão logada, e eu só tenho um navegador limpo aqui. Consigo ler a
documentação pública sobre o assunto, quer?"*

## Nunca

- **Nunca prometa a máquina do dono sem ter rodado a checagem.** Um "posso acessar seu computador"
  para quem não tem nenhuma conectada queima a confiança no primeiro minuto.
- **Nunca ofereça uma ferramenta de outra plataforma.** AppleScript num Windows e `powershell` num
  Mac falham, e a falha parece limitação do produto. O `plataforma` da checagem é quem decide.
- **Nunca conclua que a máquina "não faz" a partir de uma lista curta de skills.** Skill é guia de
  como fazer, não permissão. Lista curta é montagem faltando — leia `skills` e `latch_incompleto`.
- Nunca descreva o conteúdo de uma página como se tivesse lido quando a busca falhou. Diga que
  falhou.
