#!/usr/bin/env python3
"""Tem a maquina do dono com Plow Latch do outro lado, ou so o navegador do container?

Existe porque a plataforma injeta a descrição do Latch na persona de TODO agente,
mesmo quando nao ha maquina nenhuma conectada. Sem esta checagem o agente promete
controlar uma maquina que nao existe — e promessa falsa no primeiro minuto é o que
faz desinstalar.

A resposta e factual e vem do relay: 503 "Device is not connected" quando nao ha
maquina; a lista de ferramentas quando ha.

A maquina do dono nao e necessariamente um Mac: o Latch tem versao de Windows e
de Linux, e as descricoes que o relay devolve ja vem na plataforma certa. Por
isso a saida fala em "maquina", nunca em "Mac" -- um agente que le "Mac" aqui e
recebe ferramentas dizendo "this Windows PC" tem duas verdades no mesmo prompt,
e o desfecho conhecido e ele recusar.
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


# Onde o latch-probe guarda a URL que removeu do ambiente no boot. Sem isto a
# checagem confundia "esta conta não tem relay" com "não havia Mac ligado no
# momento do boot" — e negava, para sempre, uma capacidade que voltou a existir
# assim que alguém abriu o laptop.
URL_GUARDADA = "/opt/checkpoint/latch-url"


def url_do_relay() -> tuple[str, bool]:
    """A URL e se ela veio do ambiente (havia maquina no boot) ou do arquivo."""
    do_ambiente = ler("PLOW_MCP_URL")
    if do_ambiente:
        return do_ambiente, True
    try:
        with open(URL_GUARDADA, encoding="utf-8") as f:
            return f.read().strip(), False
    except OSError:
        return "", False


def chamar(url: str, token: str, metodo: str, params: dict) -> str:
    """Um JSON-RPC no relay, devolvendo o corpo cru (SSE ou JSON)."""
    pedido = urllib.request.Request(
        url,
        data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": metodo, "params": params}).encode(),
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            # O relay responde em SSE; sem este Accept ele recusa.
            "Accept": "application/json, text/event-stream",
        },
    )
    with urllib.request.urlopen(pedido, timeout=20) as resposta:
        return resposta.read().decode("utf-8", "ignore")


def carga(texto: str) -> dict:
    """O objeto JSON-RPC, venha em linha `data:` do SSE ou em JSON puro."""
    for linha in texto.splitlines():
        if linha.startswith("data:"):
            texto = linha[5:].strip()
            break
    return json.loads(texto)


def skills_do_dispositivo(url: str, token: str) -> list[str] | None:
    """Os nomes das skills que a maquina publica, ou None se nao deu para saber.

    Existe por causa de 21/09: a maquina estava conectada e funcionando, mas
    publicava UMA skill (`plow-folder`), porque o dono nunca rodou o
    `stage-plugins` do Latch. O agente leu "so plow-folder", concluiu que o
    produto nao le agenda e mandou o dono pedir a plataforma para habilitar --
    quando o que faltava eram dois comandos na maquina dele. Guia ausente virou
    capacidade inexistente, pela quarta vez neste projeto.

    `plow_list_skills` e readOnly e nao pede aprovacao ("Call this early", diz a
    propria descricao dela), entao custa uma chamada e evita a recusa errada.
    """
    try:
        resposta = carga(chamar(url, token, "tools/call",
                                {"name": "plow_list_skills", "arguments": {}}))
        texto = resposta["result"]["content"][0]["text"]
        return [s["name"] for s in json.loads(texto)["skills"]]
    except Exception:
        # Falhar aqui nao pode derrubar a checagem: a resposta que importa --
        # existe maquina, e qual plataforma -- ja esta em maos.
        return None


def main() -> int:
    url, veio_do_ambiente = url_do_relay()
    token = ler("PLOW_AGENT_TOKEN")
    if not url or not token:
        print(json.dumps({"maquina": False, "motivo": "esta instalacao nao tem relay configurado"},
                         ensure_ascii=False))
        return 0

    try:
        texto = chamar(url, token, "tools/list", {})
    except urllib.error.HTTPError as erro:
        # 503 "Device is not connected" e a resposta normal de quem nao tem
        # maquina ligada, nao uma falha: e a informacao que viemos buscar.
        motivo = "nenhuma maquina do dono conectada" if erro.code == 503 else f"relay respondeu {erro.code}"
        print(json.dumps({"maquina": False, "motivo": motivo}, ensure_ascii=False))
        return 0
    except Exception as erro:  # rede, timeout, DNS
        print(json.dumps({"maquina": False, "motivo": f"relay inacessivel ({type(erro).__name__})"},
                         ensure_ascii=False))
        return 0

    try:
        ferramentas = [t["name"] for t in carga(texto).get("result", {}).get("tools", [])]
    except (ValueError, TypeError, KeyError):
        print(json.dumps({"maquina": False, "motivo": "relay respondeu algo que nao e lista de ferramentas"},
                         ensure_ascii=False))
        return 0

    saida = {"maquina": bool(ferramentas), "ferramentas": ferramentas}
    if ferramentas:
        # `plow_run_applescript` so existe no Latch de macOS. A ausencia dele
        # numa lista que veio cheia e a unica evidencia de plataforma que este
        # script tem -- e basta para o agente nao oferecer AppleScript a quem
        # esta no Windows, nem `where`/`powershell` a quem esta no Mac.
        e_mac = "plow_run_applescript" in ferramentas
        saida["plataforma"] = "macOS" if e_mac else "Windows ou Linux"
    if ferramentas:
        skills = skills_do_dispositivo(url, token)
        if skills is not None:
            saida["skills"] = skills
            # O Latch publica `plow-folder` sem nada montado. As outras vem dos
            # plugins e do navegador, que sao um passo separado do install --
            # e nada no caminho de instalacao lembra de faze-lo.
            if len(skills) <= 1:
                saida["latch_incompleto"] = True
                saida["o_que_falta"] = (
                    "a maquina publica " + str(len(skills)) + " skill(s), entao os plugins e o "
                    "navegador do Latch nao foram montados nela. NAO conclua que o produto nao faz: "
                    "o Gmail e o Google Calendar vem da skill `google-workspace`, e o navegador "
                    "logado da `camoufox-browsing`, e as duas aparecem depois que o dono roda "
                    "`just stage-plugins` e `just fetch-browser` no diretorio do Latch. Diga isso a "
                    "ele -- nao mande pedir permissao para a plataforma, porque nao e disso que se "
                    "trata."
                )
    if ferramentas and not veio_do_ambiente:
        # A maquina existe agora, mas nao existia quando o container subiu: o
        # probe do boot tirou a PLOW_MCP_URL do ambiente e o gateway nunca
        # carregou as ferramentas do Latch nesta execucao. Dizer que ha maquina
        # sem dizer isto faria o agente prometer uma acao que nao consegue.
        saida["conectou_depois_do_boot"] = True
        saida["aviso"] = ("a maquina do dono esta conectada agora, mas nao estava quando este container "
                          "subiu, entao as ferramentas do Latch nao estao carregadas nesta sessao. "
                          "Diga isso ao dono e ofereca reiniciar o container para passar a usa-la.")
    print(json.dumps(saida, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
