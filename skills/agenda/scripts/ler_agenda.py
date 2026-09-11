#!/usr/bin/env python3
"""Os compromissos do dono, lidos do endereço iCal do calendário dele.

Por que iCal e não a API do provedor: todo calendário — Google, Outlook/M365,
Apple — publica um endereço secreto em formato iCal, e ele é um GET de texto.
Sem OAuth, sem app registrado, sem credencial que o instalador precise criar, e
funciona igual nos três. A API de cada um exigiria um caminho diferente por
provedor e uma credencial por instalador, e credencial nova derruba a taxa de
instalação.

É somente leitura por natureza, o que combina com o resto deste agente: ele lê o
estado do mundo e propõe; quem grava é o dono, com um toque.
"""

from __future__ import annotations

import datetime
import json
import os
import re
import sys
import urllib.error
import urllib.request

CONFIG = os.path.join(os.environ.get("HERMES_HOME", "/var/lib/hermes"), "checkpoint", "config.json")


def urls() -> list[str]:
    try:
        with open(CONFIG, encoding="utf-8") as f:
            return [u for u in (json.load(f).get("calendarios") or []) if u.startswith("http")]
    except (OSError, ValueError):
        return []


def desdobrar(texto: str) -> str:
    """O iCal quebra linha longa continuando com espaço. Junta antes de parsear."""
    return texto.replace("\r\n", "\n").replace("\n ", "").replace("\n\t", "")


def quando(valor: str) -> datetime.datetime | None:
    """A data do iCal convertida para a hora LOCAL do container.

    O sufixo Z marca UTC, e um calendário quase sempre publica assim. Devolver
    isso cru faria o agente dizer "sua reunião é às 12h" para quem a tem às 9h —
    errado por três horas no Brasil, e errado em qualquer lugar fora do UTC.
    O fuso vem da variável TZ; sem ela o container é UTC e a conversão é neutra.
    """
    valor = valor.strip()
    if valor.endswith("Z"):
        try:
            em_utc = datetime.datetime.strptime(valor, "%Y%m%dT%H%M%SZ").replace(
                tzinfo=datetime.timezone.utc)
            return em_utc.astimezone().replace(tzinfo=None)
        except ValueError:
            pass
    for formato in ("%Y%m%dT%H%M%S", "%Y%m%d"):
        try:
            return datetime.datetime.strptime(valor, formato)
        except ValueError:
            continue
    return None


def eventos(texto: str, inicio: datetime.datetime, fim: datetime.datetime) -> list[dict]:
    achados = []
    for bloco in re.findall(r"BEGIN:VEVENT(.*?)END:VEVENT", desdobrar(texto), re.S):
        def campo(nome: str) -> str:
            m = re.search(rf"^{nome}[^:\n]*:(.*)$", bloco, re.M)
            return (m.group(1).strip() if m else "")

        comeco = quando(campo("DTSTART"))
        if not comeco or not (inicio <= comeco <= fim):
            continue
        termino = quando(campo("DTEND"))
        # Evento de dia inteiro não tem hora: o DTSTART vem só com a data.
        dia_inteiro = "T" not in campo("DTSTART")
        achados.append({
            "inicio": comeco.isoformat(),
            "fim": termino.isoformat() if termino else None,
            "dia_inteiro": dia_inteiro,
            "titulo": campo("SUMMARY") or "(sem título)",
            "local": campo("LOCATION") or None,
            "minutos": int((termino - comeco).total_seconds() // 60) if termino and not dia_inteiro else None,
        })
    return achados


def main() -> int:
    dias = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 2
    enderecos = urls()
    if not enderecos:
        print(json.dumps({
            "erro": "nenhum calendário configurado",
            "como_resolver": (
                "peça ao dono o endereço secreto em formato iCal do calendário dele "
                "(no Google: Configurações do calendário > Endereço secreto no formato iCal; "
                "no Outlook/M365: Calendário > Compartilhar > Publicar > ICS) e grave em "
                f"{CONFIG} como {{\"calendarios\": [\"https://...\"]}}"
            ),
        }, ensure_ascii=False))
        return 1

    agora = datetime.datetime.now()
    janela_fim = agora + datetime.timedelta(days=dias)
    todos, falhas = [], []
    for endereco in enderecos:
        try:
            with urllib.request.urlopen(endereco, timeout=25) as r:
                todos.extend(eventos(r.read().decode("utf-8", "ignore"), agora - datetime.timedelta(hours=12), janela_fim))
        except (urllib.error.URLError, urllib.error.HTTPError, OSError) as e:
            # Um calendário fora do ar não pode esconder os outros, mas também
            # não pode passar por "dia livre" — a falha é dita.
            falhas.append(type(e).__name__)

    todos.sort(key=lambda e: e["inicio"])
    ocupado = sum(e["minutos"] or 0 for e in todos if not e["dia_inteiro"])
    print(json.dumps({
        "janela_dias": dias,
        "eventos": todos,
        "minutos_ocupados": ocupado,
        "calendarios_que_falharam": falhas,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
