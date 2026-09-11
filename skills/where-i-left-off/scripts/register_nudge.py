#!/usr/bin/env python3
"""Registra o cutucão, sem duplicar. Roda dentro do container.

Por que existe: `hermes cron` guarda os jobs em jobs.json, e nada replaya esse
arquivo num rebuild. Sem isto, "configura o aviso" vira improvisar um horário
por conversa toda vez, e duas conversas viram dois jobs cutucando a pessoa em
dobro.

A idempotência lê jobs.json — o estado do próprio hermes, onde nome é campo —
em vez de casar texto da saída de `hermes cron list`. Listagem legível não é
estrutura de dados, e "não consegui entender o que está registrado" nunca pode
ser lido como "não há nada registrado": isso duplica o job.
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

NOME = "checkpoint-nudge"

# De quanto em quanto tempo o monitor roda. Note que isto NÃO é a frequência das
# mensagens: o agente só é acordado quando a assinatura do nudge_digest muda, ou
# seja, quando um projeto cruza para uma faixa pior. Rodar de hora em hora é
# barato porque a maioria dos tiques não acorda ninguém.
INTERVALO = "every 1h"

INSTRUCAO = (
    "Uma ou mais pontas soltas mudaram de estado. A mudança detectada está no "
    "bloco MONITOR acima, no formato projeto|branch|estado|faixa-de-dias. "
    "Rode a skill where-i-left-off para o retrato completo e mande UMA mensagem "
    "curta ao dono sobre o que mudou — só sobre o que mudou, não a lista toda. "
    "Diga o que ele estava fazendo (assunto do último commit) e o que ficou "
    "pela metade (os arquivos não salvos). Se nada na mudança merecer "
    "interromper alguém, responda NO_REPLY e não mande nada."
)


def destino() -> str:
    """Para onde a mensagem vai.

    O canal de origem do agente é publicado pelo boot em PLOW_HOME_CHANNEL. Sem
    destino explícito o Hermes entrega em `local`, que grava num arquivo e não
    avisa ninguém.
    """
    canal = os.environ.get("PLOW_HOME_CHANNEL", "").strip()
    if not canal:
        try:
            with open("/run/s6/container_environment/PLOW_HOME_CHANNEL", encoding="utf-8") as f:
                canal = f.read().strip()
        except OSError:
            canal = ""
    return f"plow_chat:{canal}" if canal else "origin"


def jobs_registrados() -> list[dict]:
    """Os jobs que o hermes conhece. Arquivo ausente é agenda vazia; arquivo
    ilegível é erro, nunca 'vazio' — registrar por cima de estado que não
    conseguimos ler é como se duplica job."""
    try:
        dados = json.loads(JOBS.read_text())
    except FileNotFoundError:
        return []
    return dados.get("jobs", [])


def publicar_scripts() -> None:
    """Copia os scripts da cópia canônica, root-owned, para a pasta que o
    hermes exige.

    O runtime só aceita `--monitor-script` relativo a HERMES_HOME/scripts, que
    fica dentro da home — e a home pertence ao agente, que pode reescrevê-la.
    Isso contraria a regra de manter fora da home o que roda sem supervisão, e
    é imposição do runtime, não escolha nossa. A mitigação é esta função:
    republicar a partir da cópia root-owned em /opt sempre que o registro roda,
    para que uma alteração feita por um turno não sobreviva a um novo setup.
    """
    SCRIPTS.mkdir(parents=True, exist_ok=True)
    for nome in ("nudge_digest.py", "scan_projects.py"):
        shutil.copyfile(CANONICO / nome, SCRIPTS / nome)


def main() -> int:
    publicar_scripts()

    for job in jobs_registrados():
        if job.get("name") == NOME:
            print(f"já registrado ({job.get('id')}) — nada a fazer")
            return 0

    resultado = subprocess.run(
        [
            HERMES, "cron", "create", INTERVALO, INSTRUCAO,
            "--name", NOME,
            # Sem isto o Hermes usa `local`: o agente compõe a mensagem e a grava
            # num arquivo dentro do container em vez de entregar. O aviso
            # proativo é metade deste produto, e sem destino ele simplesmente
            # nunca chega — sem erro nenhum, o que torna a falha invisível.
            "--deliver", destino(),
            "--monitor-script", "nudge_digest.py",
            "--skill", "where-i-left-off",
        ],
        capture_output=True,
        text=True,
    )
    saida = (resultado.stdout + resultado.stderr).strip()
    if resultado.returncode != 0:
        print(f"falhou ao registrar: {saida}", file=sys.stderr)
        return 1
    print(saida.splitlines()[0] if saida else "registrado")
    return 0


if __name__ == "__main__":
    sys.exit(main())
