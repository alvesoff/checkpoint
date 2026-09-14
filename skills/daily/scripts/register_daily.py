#!/usr/bin/env python3
"""Registra os dois resumos do dia, sem duplicar. Roda dentro do container.

Estes dois são os ÚNICOS cronjobs do Checkpoint que falam por horário em vez de
falarem por mudança. É uma exceção consciente à regra "só interrompe quando algo
muda": o valor aqui é justamente o ritmo — de manhã antes de decidir o dia, à
noite antes de fechar o notebook. Um resumo que só chega quando muda alguma
coisa não é um resumo, é outro alerta.

Por isso usam `--script` e não `--monitor-script`: o monitor existe para
suprimir; aqui a entrega é o ponto.
"""

from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess
import sys

HERMES = "/opt/hermes/bin/hermes"
HOME = pathlib.Path(os.environ.get("HERMES_HOME", "/var/lib/hermes"))
JOBS = HOME / "cron" / "jobs.json"
SCRIPTS = HOME / "scripts"
CANONICO = pathlib.Path(__file__).resolve().parent

# Horários em expressão cron, no fuso do container (TZ vem do compose). Cedo o
# bastante para mudar o que a pessoa vai fazer, tarde o bastante para o dia já
# ter acontecido.
ROTINAS = [
    {
        "nome": "checkpoint-manha",
        "quando": "0 8 * * 1-5",
        "script": "resumo_manha.py",
        "instrucao": (
            "Este e o resumo da manha do dono, ja calculado no bloco acima. Maximo 6 linhas. "
            "ABRA pelo campo o_que_ninguem_vai_cobrar_hoje: e a coisa mais importante que ninguem "
            "esta cobrando e que ele nao vai fazer se voce nao lembrar. Diga o que e, e diga ha "
            "quanto tempo esta parada, porque o tempo parado E o argumento. "
            "Depois: quantas horas de reuniao ele tem hoje e quanto sobra. A conta que importa e "
            "quantas FRENTES cabem no tempo que sobra, nao quantas tarefas - se sobram 4 horas e ha "
            "6 projetos parados, diga que da para atacar um. "
            "Se o campo quadrantes mostrar itens em 'agora', cite o numero deles numa linha e "
            "ofereca - sao vulnerabilidade ou segredo exposto, e nao podem sumir da mensagem. "
            "Nao liste tudo: uma coisa importante bem dita vale mais que sete linhas de inventario. "
            "Se nao ha reuniao nenhuma, nenhum projeto parado e nada em 'agora', responda NO_REPLY - "
            "dia limpo nao merece mensagem."
        ),
    },
    {
        "nome": "checkpoint-noite",
        "quando": "0 18 * * 1-5",
        "script": "resumo_noite.py",
        "instrucao": (
            "Este e o fechamento do dia do dono, ja calculado no bloco acima. "
            "Diga em no maximo 6 linhas: o que ele commitou hoje e onde, o que continua fora do git "
            "(o mais antigo primeiro, porque some se a maquina morrer), e a primeira reuniao de "
            "amanha. "
            "Se o campo reuniao_cruzada_com_projeto vier preenchido, ESSA e a frase mais valiosa da "
            "mensagem e vai por ultimo: a reuniao de amanha e sobre um projeto que esta num certo "
            "estado agora. Diga o nome da reuniao, o projeto e o que esta pendente nele. "
            "Se ele nao commitou nada e nao ha nada solto nem reuniao amanha, responda NO_REPLY."
        ),
    },
]


def destino() -> str:
    canal = os.environ.get("PLOW_HOME_CHANNEL", "").strip()
    if not canal:
        try:
            with open("/run/s6/container_environment/PLOW_HOME_CHANNEL", encoding="utf-8") as f:
                canal = f.read().strip()
        except OSError:
            canal = ""
    return f"plow_chat:{canal}" if canal else "origin"


def jobs_registrados() -> list[dict]:
    try:
        return json.loads(JOBS.read_text()).get("jobs", [])
    except FileNotFoundError:
        return []


def publicar_scripts() -> None:
    SCRIPTS.mkdir(parents=True, exist_ok=True)
    for nome in ("resumo.py", "resumo_manha.py", "resumo_noite.py"):
        shutil.copyfile(CANONICO / nome, SCRIPTS / nome)


def main() -> int:
    publicar_scripts()
    existentes = {j.get("name") for j in jobs_registrados()}
    alvo = destino()
    falhou = False

    for rotina in ROTINAS:
        if rotina["nome"] in existentes:
            print(f"{rotina['nome']}: já registrado — nada a fazer")
            continue
        r = subprocess.run(
            [HERMES, "cron", "create", rotina["quando"], rotina["instrucao"],
             "--name", rotina["nome"],
             "--deliver", alvo,
             "--script", rotina["script"],
             "--skill", "daily"],
            capture_output=True, text=True,
        )
        saida = (r.stdout + r.stderr).strip()
        if r.returncode != 0:
            print(f"{rotina['nome']}: falhou — {saida}", file=sys.stderr)
            falhou = True
        else:
            print(f"{rotina['nome']}: {saida.splitlines()[0] if saida else 'registrado'}")

    return 1 if falhou else 0


if __name__ == "__main__":
    sys.exit(main())
