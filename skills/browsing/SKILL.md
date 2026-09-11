---
name: browsing
description: Abrir páginas da web — changelog, documentação, guia de migração, status de serviço. Escolhe sozinho entre o Mac do dono (Plow Latch, com as sessões já logadas) e o navegador do próprio container. Use sempre que precisar ler algo que está na internet.
---

# Navegar

Você tem dois navegadores possíveis e eles **não** são equivalentes. Escolha antes de agir.

## Primeiro: descubra qual você tem

```sh
python3 /opt/hermes/skills/browsing/scripts/check_mac.py
```

Responde `{"mac": true, "ferramentas": [...]}` ou `{"mac": false, "motivo": "..."}`.

Custa uma chamada e evita o erro mais caro que você pode cometer: prometer usar o computador de
alguém que não tem Mac. A plataforma injeta a descrição do Plow Latch na sua persona **mesmo quando
não há Mac nenhum do outro lado** — então a sua descrição não é prova de nada. Este script é.

## Com Mac (`mac: true`)

Use as ferramentas do Latch. O navegador é o **da pessoa**, com as sessões dela já autenticadas:
alcança portal com login, painel de serviço, conta de banco, sistema interno. É a capacidade mais
poderosa que você tem.

Regras:
- Toda ação passa pela aprovação do dono. Não tente contornar, não insista se for negado.
- Diga o que vai fazer antes de fazer.
- Nunca leia credencial, nem repita na conversa o que aparecer numa tela de senha.

## Sem Mac (`mac: false`)

Use o navegador do container:

```sh
CHROME=$(find /opt/hermes/.playwright -name chrome-headless-shell -type f | head -1)
"$CHROME" --headless --disable-gpu --no-sandbox --dump-dom "<url>"
```

Ele alcança **qualquer página pública** — changelog, release notes, guia de migração, documentação,
issue de repositório, página de status. Não alcança nada que exija login, porque é um navegador
limpo, sem sessão nenhuma.

Quando a pessoa pedir algo que precise de login e não houver Mac, diga isso direto e ofereça o que
dá: *"isso precisa da sua sessão logada, e eu só tenho um navegador limpo aqui. Consigo ler a
documentação pública sobre o assunto, quer?"*

## Nunca

- **Nunca prometa o Mac sem ter rodado a checagem.** Um "posso acessar seu computador" para quem
  não tem Mac queima a confiança no primeiro minuto.
- Nunca descreva o conteúdo de uma página como se tivesse lido quando a busca falhou. Diga que
  falhou.
