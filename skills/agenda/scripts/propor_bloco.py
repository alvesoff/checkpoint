#!/usr/bin/env python3
"""Acha um buraco livre na agenda e devolve o link de um toque para reservar.

Por que link e não criação direta: gravar no calendário exigiria OAuth ou uma
senha de aplicativo de cada pessoa que instalasse — credencial nova, que derruba
a taxa de instalação. O link abre o evento já preenchido no calendário do dono,
e ele confirma com um toque.

O toque não é limitação disfarçada de virtude: é a confirmação humana no lugar
certo. Um agente que enche a agenda de alguém sozinho é desinstalado na primeira
semana.

Uso:
    propor_bloco.py "<título>" <minutos> [dias_a_frente]
"""

from __future__ import annotations

import datetime
import json
import os
import subprocess
import sys
import urllib.parse

AQUI = os.path.dirname(os.path.realpath(__file__))

# A janela de trabalho. Ninguém quer um bloco proposto às 5 da manhã.
HORA_INICIO, HORA_FIM = 8, 19

# Respiro antes e depois de cada compromisso: encostar um bloco de trabalho no
# fim de uma reunião produz um bloco que nunca acontece.
FOLGA_MIN = 15


def compromissos(dias: int) -> list[tuple[datetime.datetime, datetime.datetime]]:
    try:
        saida = subprocess.run(
            [sys.executable, os.path.join(AQUI, "ler_agenda.py"), str(dias)],
            capture_output=True, text=True, timeout=60,
        )
        dados = json.loads(saida.stdout)
    except (subprocess.SubprocessError, OSError, ValueError):
        return []
    if dados.get("erro"):
        return []
    ocupados = []
    for e in dados.get("eventos", []):
        if e["dia_inteiro"] or not e.get("fim"):
            continue
        try:
            ini = datetime.datetime.fromisoformat(e["inicio"])
            fim = datetime.datetime.fromisoformat(e["fim"])
        except ValueError:
            continue
        ocupados.append((ini - datetime.timedelta(minutes=FOLGA_MIN),
                         fim + datetime.timedelta(minutes=FOLGA_MIN)))
    return sorted(ocupados)


def buracos(ocupados, minutos: int, dias: int) -> list[datetime.datetime]:
    agora = datetime.datetime.now().replace(second=0, microsecond=0)
    livres = []
    for d in range(dias + 1):
        dia = (agora + datetime.timedelta(days=d)).date()
        cursor = datetime.datetime.combine(dia, datetime.time(HORA_INICIO))
        limite = datetime.datetime.combine(dia, datetime.time(HORA_FIM))
        if cursor < agora:
            # Arredonda para a próxima meia hora: propor "daqui a 3 minutos"
            # não é proposta, é atropelo.
            cursor = agora + datetime.timedelta(minutes=(30 - agora.minute % 30) % 30 or 30)
        while cursor + datetime.timedelta(minutes=minutos) <= limite:
            fim = cursor + datetime.timedelta(minutes=minutos)
            if not any(ini < fim and cursor < term for ini, term in ocupados):
                livres.append(cursor)
                break  # um por dia é suficiente para propor
            cursor += datetime.timedelta(minutes=30)
    return livres


def link_google(titulo: str, ini: datetime.datetime, minutos: int, detalhe: str) -> str:
    # O link exige UTC; os horários aqui são locais, então converte de volta na
    # saída. Trocar isso faz o evento nascer no horário errado no calendário.
    ini = ini.astimezone(datetime.timezone.utc).replace(tzinfo=None) if ini.tzinfo else (
        ini - datetime.datetime.now().astimezone().utcoffset())
    fim = ini + datetime.timedelta(minutes=minutos)
    f = "%Y%m%dT%H%M%SZ"
    return "https://calendar.google.com/calendar/render?" + urllib.parse.urlencode({
        "action": "TEMPLATE",
        "text": titulo,
        "dates": f"{ini.strftime(f)}/{fim.strftime(f)}",
        "details": detalhe,
    })


def link_outlook(titulo: str, ini: datetime.datetime, minutos: int, detalhe: str) -> str:
    ini = ini - datetime.datetime.now().astimezone().utcoffset() if not ini.tzinfo else ini
    fim = ini + datetime.timedelta(minutes=minutos)
    return "https://outlook.office.com/calendar/0/deeplink/compose?" + urllib.parse.urlencode({
        "path": "/calendar/action/compose",
        "subject": titulo,
        "startdt": ini.isoformat() + "Z",
        "enddt": fim.isoformat() + "Z",
        "body": detalhe,
    })


def main() -> int:
    if len(sys.argv) < 3:
        print(json.dumps({"erro": 'uso: propor_bloco.py "<título>" <minutos> [dias]'}, ensure_ascii=False))
        return 1
    titulo, minutos = sys.argv[1], int(sys.argv[2])
    dias = int(sys.argv[3]) if len(sys.argv) > 3 else 2
    detalhe = "Bloco proposto pelo Checkpoint."

    ocupados = compromissos(dias)
    livres = buracos(ocupados, minutos, dias)
    if not livres:
        print(json.dumps({
            "erro": "nenhum horário livre encontrado na janela",
            "como_resolver": f"a agenda está cheia entre {HORA_INICIO}h e {HORA_FIM}h nos próximos {dias} dias",
        }, ensure_ascii=False))
        return 1

    propostas = [{
        "inicio_local": q.isoformat(),
        "minutos": minutos,
        "google": link_google(titulo, q, minutos, detalhe),
        "outlook": link_outlook(titulo, q, minutos, detalhe),
    } for q in livres[:3]]
    print(json.dumps({"titulo": titulo, "propostas": propostas,
                      "compromissos_considerados": len(ocupados)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
