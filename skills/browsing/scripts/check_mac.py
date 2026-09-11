#!/usr/bin/env python3
"""Tem um Mac com Plow Latch do outro lado, ou só o navegador do container?

Existe porque a plataforma injeta a descrição do Latch na persona de TODO agente,
mesmo quando não há Mac nenhum conectado. Sem esta checagem o agente promete
controlar um Mac que não existe — e promessa falsa no primeiro minuto é o que
faz desinstalar.

A resposta é factual e vem do relay: 503 "Device is not connected" quando não há
Mac; a lista de ferramentas quando há.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

AMBIENTE = "/run/s6/container_environment"


def ler(nome: str) -> str:
    """O valor, do ambiente do processo primeiro e do arquivo depois.

    A ordem importa: dentro de um turno o gateway já carrega essas variáveis,
    enquanto os arquivos em /run/s6/container_environment pertencem ao root e
    o agente não os lê. Tentar só o arquivo faz a checagem responder "sem
    relay" numa instalação que tem relay — que é pior que não checar, porque
    o agente passa a negar uma capacidade que existe.
    """
    do_ambiente = os.environ.get(nome, "").strip()
    if do_ambiente:
        return do_ambiente
    try:
        with open(f"{AMBIENTE}/{nome}", encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return ""


def main() -> int:
    url, token = ler("PLOW_MCP_URL"), ler("PLOW_AGENT_TOKEN")
    if not url or not token:
        print(json.dumps({"mac": False, "motivo": "esta instalação não tem relay configurado"},
                         ensure_ascii=False))
        return 0

    pedido = urllib.request.Request(
        url,
        data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}).encode(),
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            # O relay responde em SSE; sem este Accept ele recusa.
            "Accept": "application/json, text/event-stream",
        },
    )
    try:
        with urllib.request.urlopen(pedido, timeout=20) as resposta:
            texto = resposta.read().decode("utf-8", "ignore")
    except urllib.error.HTTPError as erro:
        # 503 "Device is not connected" é a resposta normal de quem não tem Mac,
        # não uma falha: é a informação que viemos buscar.
        motivo = "nenhum Mac conectado" if erro.code == 503 else f"relay respondeu {erro.code}"
        print(json.dumps({"mac": False, "motivo": motivo}, ensure_ascii=False))
        return 0
    except Exception as erro:  # rede, timeout, DNS
        print(json.dumps({"mac": False, "motivo": f"relay inacessível ({type(erro).__name__})"},
                         ensure_ascii=False))
        return 0

    # Resposta em SSE: a carga vem numa linha `data:`.
    for linha in texto.splitlines():
        if linha.startswith("data:"):
            texto = linha[5:].strip()
            break
    try:
        ferramentas = [t["name"] for t in json.loads(texto).get("result", {}).get("tools", [])]
    except (ValueError, TypeError, KeyError):
        print(json.dumps({"mac": False, "motivo": "relay respondeu algo que não é lista de ferramentas"},
                         ensure_ascii=False))
        return 0

    print(json.dumps({"mac": bool(ferramentas), "ferramentas": ferramentas}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
