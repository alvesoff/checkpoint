#!/usr/bin/env python3
"""A assinatura do que VÁRIAS fontes cobriram, e nada além disso.

É o `--monitor-script` do radar de pauta: roda a cada tique e o agente só é
acordado quando a saída MUDA. Por isso não pode conter nada que ande sozinho --
nem data, nem relógio, nem ordem que dependa do sistema de arquivos.

O que muda a assinatura, e é quando vale interromper alguém:
  - um assunto passa a ser coberto por fontes distintas o bastante (o limiar)
  - um assunto já contado ganha mais fontes
  - uma fonte cadastrada falha três vezes seguidas (radar cego é pior que sem radar)

O que NÃO muda: o tempo passando sobre um assunto que a pessoa já viu ontem.

Nenhuma inferência aqui dentro. O agrupamento é aritmética de palavra rara, e
quem julga -- o que vale, o que é ruído, o que dizer -- é o turno do agente,
com os tokens dele. Um script que chamasse modelo gastaria crédito no escuro,
toda hora, para descobrir que não havia nada a dizer.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import pathlib
import re
import sqlite3
import subprocess
import sys
import unicodedata

HOME = pathlib.Path(os.environ.get("HERMES_HOME", "/var/lib/hermes"))
CONFIG = HOME / "checkpoint" / "pauta.json"
BANCO = HOME / "checkpoint" / "pauta.db"

MAX_ASSUNTOS = 5
MAX_TITULOS = 3
# Palavra que aparece em quase tudo não distingue assunto nenhum, e palavra que
# aparece uma vez só não junta ninguém. O corredor do meio é o que importa -- e
# ele é estreito: com 5% medido sobre 160 títulos reais, "Silent Hill Townfall"
# fica de pé e o par "developer"/"game" para de juntar duas notícias que não têm
# nada a ver uma com a outra.
TETO_FREQUENCIA = 0.05

VAZIAS = {
    "the", "and", "for", "with", "that", "this", "you", "your", "are", "was",
    "com", "para", "que", "dos", "das", "uma", "uns", "por", "como", "mais", "sobre",
    "official", "oficial", "trailer", "video", "vídeo", "novo", "nova", "new", "how",
    "review", "analise", "análise", "gameplay", "live", "ao", "vivo", "hoje", "day",
}


def normalizar(titulo: str) -> list[str]:
    sem_acento = "".join(
        letra
        for letra in unicodedata.normalize("NFD", titulo.lower())
        if unicodedata.category(letra) != "Mn"
    )
    return [
        palavra
        for palavra in re.findall(r"[a-z0-9]{4,}", sem_acento)
        if palavra not in VAZIAS
    ]


class Junta:
    """União-busca: dois itens que dividem duas palavras raras são o mesmo assunto."""

    def __init__(self, tamanho: int) -> None:
        self.pai = list(range(tamanho))

    def raiz(self, no: int) -> int:
        while self.pai[no] != no:
            self.pai[no] = self.pai[self.pai[no]]
            no = self.pai[no]
        return no

    def unir(self, a: int, b: int) -> None:
        ra, rb = self.raiz(a), self.raiz(b)
        if ra != rb:
            self.pai[max(ra, rb)] = min(ra, rb)


def coletar() -> None:
    """O tique do cron é o único momento em que alguém lê os feeds.

    Fica aqui, e não num segundo cron, porque coleta sem digest não avisa
    ninguém e digest sem coleta responde sobre ontem -- dois jobs que só fazem
    sentido juntos são um job. Falha de rede não pode derrubar o monitor: o
    banco continua com o que já tinha, e a assinatura sai do que existe.
    """
    try:
        subprocess.run(
            [sys.executable, str(pathlib.Path(__file__).resolve().parent / "coleta.py")],
            capture_output=True, timeout=180,
        )
    except (subprocess.SubprocessError, OSError):
        pass


def janela(horas: int) -> str:
    corte = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=horas)
    return corte.isoformat(timespec="seconds")


def main() -> int:
    try:
        config = json.loads(CONFIG.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print("Monitor: nenhuma fonte cadastrada")
        return 0

    limiar = int(config.get("limiar_fontes", 3))
    horas = int(config.get("janela_horas", 36))

    coletar()

    if not BANCO.exists():
        print("Monitor: sem coleta ainda")
        return 0

    conexao = sqlite3.connect(f"file:{BANCO}?mode=ro", uri=True)
    itens = conexao.execute(
        "SELECT fonte_id, fonte_nome, titulo, url FROM itens "
        "WHERE publicado_em >= ? ORDER BY item_id",
        (janela(horas),),
    ).fetchall()
    cegas = conexao.execute(
        "SELECT fonte_id FROM falhas WHERE seguidas >= 3 ORDER BY fonte_id"
    ).fetchall()
    conexao.close()

    palavras = [set(normalizar(titulo)) for _, _, titulo, _ in itens]
    frequencia: dict[str, int] = {}
    for conjunto in palavras:
        for palavra in conjunto:
            frequencia[palavra] = frequencia.get(palavra, 0) + 1

    teto = max(2, int(len(itens) * TETO_FREQUENCIA))
    uteis = [
        {palavra for palavra in conjunto if 2 <= frequencia[palavra] <= teto}
        for conjunto in palavras
    ]

    junta = Junta(len(itens))
    for i in range(len(itens)):
        for j in range(i + 1, len(itens)):
            if len(uteis[i] & uteis[j]) >= 2:
                junta.unir(i, j)

    grupos: dict[int, list[int]] = {}
    for indice in range(len(itens)):
        grupos.setdefault(junta.raiz(indice), []).append(indice)

    linhas: list[tuple[int, str]] = []
    for membros in grupos.values():
        fontes = {itens[i][0] for i in membros}
        if len(fontes) < limiar:
            continue
        comuns = set.intersection(*(uteis[i] for i in membros)) or uteis[membros[0]]
        # As três palavras mais raras do grupo, não as três primeiras do
        # alfabeto: a chave é o que o agente vê primeiro, e "hill-silent-townfall"
        # diz do que se trata enquanto "because-disc-doesn" não diz nada.
        chave = "-".join(sorted(sorted(comuns, key=lambda p: (frequencia[p], p))[:3]))
        titulos = " // ".join(itens[i][2][:90] for i in membros[:MAX_TITULOS])
        nomes = ", ".join(sorted({itens[i][1] for i in membros})[:4])
        linhas.append((len(fontes), f"ASSUNTO|{chave}|{len(fontes)}|{nomes}|{titulos}"))

    linhas.sort(key=lambda par: (-par[0], par[1]))
    saida = [linha for _, linha in linhas[:MAX_ASSUNTOS]]
    saida += [f"FONTE_CEGA|{fonte_id}" for (fonte_id,) in cegas]

    print("\n".join(saida) if saida else "Monitor: nada cruzou o limiar")
    return 0


if __name__ == "__main__":
    sys.exit(main())
