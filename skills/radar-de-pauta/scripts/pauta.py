#!/usr/bin/env python3
"""As fontes que o dono mandou acompanhar, e mais nenhuma.

A lista nasce vazia e vive no volume, nunca na imagem: fonte é escolha de quem
instala, e uma lista embutida seria a nossa escolha rodando na máquina dele.

Resolve `@handle` e URL de canal para o `channel_id`, porque o feed do YouTube
só aceita o id -- e ninguém guarda o id de um canal de cabeça.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import re
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

HOME = pathlib.Path(os.environ.get("HERMES_HOME", "/var/lib/hermes"))
CONFIG = HOME / "checkpoint" / "pauta.json"

# Identidade de navegador real. A lição custou uma medição: o mesmo GET sem isto
# volta com página vazia em boa parte dos sites, e a conclusão fácil -- "o
# container não alcança" -- está errada. O que decide é a fonte, não o cliente.
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
FEED_YOUTUBE = "https://www.youtube.com/feeds/videos.xml?channel_id="
CANAL_ID = re.compile(r'"externalId"\s*:\s*"(UC[A-Za-z0-9_-]{22})"')

PADRAO = {"fontes": [], "limiar_fontes": 3, "janela_horas": 36}


def buscar(url: str, timeout: int = 20) -> bytes:
    pedido = urllib.request.Request(
        url, headers={"User-Agent": UA, "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8"}
    )
    with urllib.request.urlopen(pedido, timeout=timeout) as resposta:
        return resposta.read()


def ler() -> dict:
    try:
        dados = json.loads(CONFIG.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return dict(PADRAO)
    for chave, valor in PADRAO.items():
        dados.setdefault(chave, valor)
    return dados


def gravar(dados: dict) -> None:
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    CONFIG.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")


def resolver_youtube(alvo: str) -> tuple[str, str]:
    """(channel_id, nome) a partir de handle, URL de canal ou do próprio id."""
    direto = re.search(r"(UC[A-Za-z0-9_-]{22})", alvo)
    if direto:
        return direto.group(1), ""
    if alvo.startswith("@"):
        alvo = "https://www.youtube.com/" + alvo
    pagina = buscar(alvo).decode("utf-8", "replace")
    achado = CANAL_ID.search(pagina)
    if not achado:
        raise SystemExit(f"não achei o channel_id em {alvo}")
    nome = re.search(r'"channelMetadataRenderer"\s*:\s*{\s*"title"\s*:\s*"([^"]{1,120})"', pagina)
    return achado.group(1), (nome.group(1) if nome else "")


def titulo_do_feed(url: str) -> str:
    try:
        raiz = ET.fromstring(buscar(url))
    except (ET.ParseError, urllib.error.URLError, OSError) as erro:
        raise SystemExit(f"não consegui ler o feed: {erro}")
    for caminho in ("./channel/title", "./title", "./{http://www.w3.org/2005/Atom}title"):
        achado = raiz.find(caminho)
        if achado is not None and (achado.text or "").strip():
            return achado.text.strip()
    return url


def cmd_add(args: argparse.Namespace) -> int:
    dados = ler()
    alvo = args.alvo.strip()
    ehyoutube = "youtube.com" in alvo or "youtu.be" in alvo or alvo.startswith("@")
    if ehyoutube and "feeds/videos.xml" not in alvo:
        canal, nome = resolver_youtube(alvo)
        fonte = {"id": f"yt:{canal}", "tipo": "youtube", "url": FEED_YOUTUBE + canal}
        fonte["nome"] = args.nome or nome or titulo_do_feed(fonte["url"])
    else:
        fonte = {
            "id": "rss:" + hashlib.sha1(alvo.encode("utf-8")).hexdigest()[:10],
            "tipo": "rss",
            "url": alvo,
        }
        fonte["nome"] = args.nome or titulo_do_feed(alvo)

    if any(f["id"] == fonte["id"] for f in dados["fontes"]):
        print(f"já acompanhava {fonte['nome']} ({fonte['id']}) — nada a fazer")
        return 0
    dados["fontes"].append(fonte)
    gravar(dados)
    print(f"acompanhando {fonte['nome']} ({fonte['id']})")
    return 0


def cmd_list(_: argparse.Namespace) -> int:
    dados = ler()
    if not dados["fontes"]:
        print("nenhuma fonte ainda — nada é acompanhado até o dono pedir")
        return 0
    for fonte in dados["fontes"]:
        print(f"{fonte['id']}\t{fonte['tipo']}\t{fonte['nome']}")
    print(f"\nlimiar: {dados['limiar_fontes']} fontes · janela: {dados['janela_horas']}h")
    return 0


def cmd_remove(args: argparse.Namespace) -> int:
    dados = ler()
    antes = len(dados["fontes"])
    dados["fontes"] = [f for f in dados["fontes"] if f["id"] != args.id]
    if len(dados["fontes"]) == antes:
        print(f"não acompanhava {args.id}")
        return 1
    gravar(dados)
    print(f"parei de acompanhar {args.id}")
    return 0


def cmd_config(args: argparse.Namespace) -> int:
    dados = ler()
    if args.limiar is not None:
        dados["limiar_fontes"] = max(2, args.limiar)
    if args.janela is not None:
        dados["janela_horas"] = max(1, args.janela)
    gravar(dados)
    print(json.dumps({k: v for k, v in dados.items() if k != "fontes"}, ensure_ascii=False))
    return 0


def main() -> int:
    analisador = argparse.ArgumentParser(description=__doc__)
    sub = analisador.add_subparsers(dest="comando", required=True)

    fonte = sub.add_parser("fonte").add_subparsers(dest="acao", required=True)
    adicionar = fonte.add_parser("add")
    adicionar.add_argument("alvo", help="@handle, URL do canal, ou URL de um feed RSS/Atom")
    adicionar.add_argument("--nome")
    adicionar.set_defaults(func=cmd_add)
    fonte.add_parser("list").set_defaults(func=cmd_list)
    remover = fonte.add_parser("remove")
    remover.add_argument("id")
    remover.set_defaults(func=cmd_remove)

    configurar = sub.add_parser("config")
    configurar.add_argument("--limiar", type=int, help="quantas fontes distintas fazem um assunto")
    configurar.add_argument("--janela", type=int, help="horas de material considerado novo")
    configurar.set_defaults(func=cmd_config)

    args = analisador.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
