#!/usr/bin/env python3
"""Lê os feeds das fontes cadastradas e guarda o que ainda não tinha visto.

Sem chave e sem cota: feed de canal do YouTube e RSS/Atom de site são páginas
públicas. O que grava é o mínimo para agrupar depois -- título, link e data.

Uma fonte que falha não derruba a varredura. Falha some quando volta a
funcionar; falha que se repete vira aviso, porque fonte morta em silêncio é
como um radar deixa de radar sem ninguém perceber.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import pathlib
import sqlite3
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

HOME = pathlib.Path(os.environ.get("HERMES_HOME", "/var/lib/hermes"))
CONFIG = HOME / "checkpoint" / "pauta.json"
BANCO = HOME / "checkpoint" / "pauta.db"

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
ATOM = "{http://www.w3.org/2005/Atom}"
FALHAS_ATE_AVISAR = 3


def conectar() -> sqlite3.Connection:
    BANCO.parent.mkdir(parents=True, exist_ok=True)
    conexao = sqlite3.connect(BANCO)
    conexao.executescript(
        """
        CREATE TABLE IF NOT EXISTS itens (
            item_id      TEXT PRIMARY KEY,
            fonte_id     TEXT NOT NULL,
            fonte_nome   TEXT NOT NULL,
            titulo       TEXT NOT NULL,
            url          TEXT,
            publicado_em TEXT,
            visto_em     TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS itens_por_data ON itens (publicado_em);
        CREATE TABLE IF NOT EXISTS falhas (
            fonte_id TEXT PRIMARY KEY,
            seguidas INTEGER NOT NULL,
            erro     TEXT
        );
        """
    )
    return conexao


def buscar(url: str) -> bytes:
    pedido = urllib.request.Request(
        url, headers={"User-Agent": UA, "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8"}
    )
    with urllib.request.urlopen(pedido, timeout=25) as resposta:
        return resposta.read()


def texto(no, *caminhos: str) -> str:
    for caminho in caminhos:
        achado = no.find(caminho)
        if achado is not None:
            valor = (achado.text or achado.get("href") or "").strip()
            if valor:
                return valor
    return ""


def itens_do_feed(corpo: bytes) -> list[dict]:
    """Atom e RSS no mesmo formato. Feed quebrado devolve lista vazia, nunca
    exceção: uma fonte mal formada não pode calar as outras."""
    try:
        raiz = ET.fromstring(corpo)
    except ET.ParseError:
        return []

    achados: list[dict] = []
    for entrada in raiz.iter():
        marca = entrada.tag.replace(ATOM, "")
        if marca not in ("entry", "item"):
            continue
        titulo = texto(entrada, f"{ATOM}title", "title")
        if not titulo:
            continue
        achados.append(
            {
                "id": texto(entrada, f"{ATOM}id", "guid", "link", f"{ATOM}link") or titulo,
                "titulo": " ".join(titulo.split()),
                "url": texto(entrada, "link", f"{ATOM}link"),
                "publicado": texto(
                    entrada, f"{ATOM}published", "pubDate", f"{ATOM}updated", "updated"
                ),
            }
        )
    return achados


def main() -> int:
    try:
        config = json.loads(CONFIG.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(json.dumps({"fontes": 0, "novos": 0, "aviso": "nenhuma fonte cadastrada"}))
        return 0

    agora = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    conexao = conectar()
    novos = 0
    quebradas: list[str] = []

    for fonte in config.get("fontes", []):
        try:
            entradas = itens_do_feed(buscar(fonte["url"]))
            if not entradas:
                raise ValueError("feed sem itens legíveis")
        except (urllib.error.URLError, OSError, ValueError) as erro:
            linha = conexao.execute(
                "SELECT seguidas FROM falhas WHERE fonte_id = ?", (fonte["id"],)
            ).fetchone()
            seguidas = (linha[0] if linha else 0) + 1
            conexao.execute(
                "INSERT INTO falhas (fonte_id, seguidas, erro) VALUES (?, ?, ?) "
                "ON CONFLICT(fonte_id) DO UPDATE SET seguidas = ?, erro = ?",
                (fonte["id"], seguidas, str(erro)[:200], seguidas, str(erro)[:200]),
            )
            if seguidas >= FALHAS_ATE_AVISAR:
                quebradas.append(fonte["nome"])
            continue

        conexao.execute("DELETE FROM falhas WHERE fonte_id = ?", (fonte["id"],))
        for entrada in entradas:
            cursor = conexao.execute(
                "INSERT OR IGNORE INTO itens "
                "(item_id, fonte_id, fonte_nome, titulo, url, publicado_em, visto_em) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    f"{fonte['id']}|{entrada['id']}",
                    fonte["id"],
                    fonte["nome"],
                    entrada["titulo"],
                    entrada["url"],
                    entrada["publicado"] or agora,
                    agora,
                ),
            )
            novos += cursor.rowcount

    conexao.commit()
    total = conexao.execute("SELECT COUNT(*) FROM itens").fetchone()[0]
    conexao.close()
    print(
        json.dumps(
            {
                "fontes": len(config.get("fontes", [])),
                "novos": novos,
                "no_banco": total,
                "quebradas": quebradas,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
