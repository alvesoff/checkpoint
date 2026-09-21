#!/usr/bin/env python3
"""Registra o radar de pauta, sem duplicar. Roda dentro do container.

Mesmo desenho do `register_radar.py`: a idempotência lê o `jobs.json`, que é o
estado do próprio hermes, em vez de casar texto da saída de `cron list` --
"não consegui entender o que está registrado" nunca pode virar "não há nada
registrado", porque isso duplica o job.
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

NOME = "checkpoint-pauta"

# De hora em hora. Não é a frequência das mensagens: o agente só acorda quando a
# assinatura muda, ou seja, quando um assunto novo passa a ser coberto por
# fontes distintas o bastante. Feed é barato; o tique que não acorda ninguém não
# gasta token nenhum.
INTERVALO = "every 1h"

INSTRUCAO = (
    "Mudou o que as fontes que o dono acompanha estao cobrindo. A mudanca esta no bloco MONITOR "
    "acima. Duas familias de linha: ASSUNTO|chave|quantas-fontes|nomes|titulos e FONTE_CEGA|id. "
    "O QUE DECIDE E O QUE ENTROU desde a ultima vez, nao o que continua la. "
    "ESCOLHA UM assunto, o coberto por mais fontes distintas, e diga: quantas fontes cobriram, "
    "quais sao, e do que se trata -- pelos titulos, sem opinar sobre o merito e sem tratar o que a "
    "fonte disse como fato seu. Ofereca o resto em UMA linha, sem listar. "
    "NUNCA despeje os cinco assuntos: e o jeito mais rapido de alguem desligar o aviso. "
    "Se so vier FONTE_CEGA, diga qual fonte parou de responder e ofereca remover. "
    "Mande UMA mensagem so, de no maximo 6 linhas. Se nada merecer interromper alguem, responda "
    "NO_REPLY -- um dia sem assunto repetido e informacao, nao motivo para inventar pauta."
)


def destino() -> str:
    """Sem destino explícito o Hermes entrega em `local`, que grava num arquivo
    e não avisa ninguém — falha invisível, porque não há erro nenhum."""
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
    """O runtime só aceita `--monitor-script` relativo a HERMES_HOME/scripts, que
    é gravável pelo agente. Republicar da cópia root-owned em /opt a cada
    registro faz com que alteração feita por um turno não sobreviva a um setup."""
    SCRIPTS.mkdir(parents=True, exist_ok=True)
    for nome in ("pauta_digest.py", "coleta.py", "pauta.py"):
        shutil.copyfile(CANONICO / nome, SCRIPTS / nome)


def main() -> int:
    publicar_scripts()

    for job in jobs_registrados():
        if job.get("name") != NOME:
            continue
        if (job.get("prompt") or "").strip() == INSTRUCAO.strip():
            print(f"já registrado ({job.get('id')}) — nada a fazer")
            return 0
        # Editar, nunca recriar: `remove` + `create` apaga o monitor_state, e sem
        # a linha de base o próximo tique conta TUDO como novidade -- um falso
        # "apareceu agora" sobre assunto de ontem.
        print(f"instrucao mudou — atualizando {NOME} ({job.get('id')})")
        r = subprocess.run([HERMES, "cron", "edit", str(job.get("id")), "--prompt", INSTRUCAO],
                           capture_output=True, text=True)
        if r.returncode == 0:
            print((r.stdout + r.stderr).strip() or "atualizado")
            return 0
        print("nao consegui editar; recriando")
        subprocess.run([HERMES, "cron", "remove", str(job.get("id"))],
                       capture_output=True, text=True)
        break

    resultado = subprocess.run(
        [
            HERMES, "cron", "create", INTERVALO,
            INSTRUCAO,
            "--name", NOME,
            "--deliver", destino(),
            "--monitor-script", "pauta_digest.py",
            "--skill", "radar-de-pauta",
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
