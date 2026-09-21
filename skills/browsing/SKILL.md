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

Responde `{"maquina": true, "ferramentas": [...], "plataforma": "..."}` ou
`{"maquina": false, "motivo": "..."}`.

Custa uma chamada e evita o erro mais caro que você pode cometer: prometer usar o computador de
alguém que não tem nenhum conectado. A plataforma injeta a descrição do Plow Latch na sua persona
**mesmo quando não há máquina nenhuma do outro lado** — então a sua descrição não é prova de nada.
Este script é.

**A máquina do dono não é necessariamente um Mac.** O Latch tem versão de Windows e de Linux, e o
`plataforma` da resposta diz qual é. Isso decide o que você oferece: `osascript` e AppleScript só
existem no macOS; num Windows o que serve é `powershell`, `where`, `clip` e os builtins do `cmd`.
As próprias descrições das ferramentas já chegam na plataforma certa — se elas disserem Windows,
elas estão certas e qualquer texto seu que diga Mac está errado.

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
- Nunca descreva o conteúdo de uma página como se tivesse lido quando a busca falhou. Diga que
  falhou.
