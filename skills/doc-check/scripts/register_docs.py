#!/usr/bin/env python3
"""Registra a conferência de documentação, sem duplicar. Roda dentro do container.

Mesmo padrão do `register_radar.py`: idempotência lida do `jobs.json` — o estado
do próprio hermes, onde nome é campo — e nunca da saída legível de
`hermes cron list`. "Não consegui entender o que está registrado" jamais pode
virar "não há nada registrado": é assim que se cria o segundo job cutucando a
pessoa em dobro.
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

NOME = "checkpoint-docs"

# Documentação apodrece devagar. De 12 em 12 horas o monitor roda; o agente só
# acorda quando a assinatura muda, então o custo de rodar é quase todo zero.
INTERVALO = "every 12h"

INSTRUCAO = (
    "A documentacao de um projeto deixou de bater com o codigo. A mudanca esta no bloco MONITOR "
    "acima, no formato projeto|tipo|detalhe, onde tipo e ref (o documento aponta para caminho que "
    "nao existe), cmd (o texto manda rodar um npm run que sumiu do package.json) ou env (o codigo "
    "exige uma variavel sem valor padrao e nenhum documento a menciona). "
    "Escolha o achado que quebra alguem AGORA - cmd e ref antes de env - abra o arquivo citado para "
    "ver o trecho errado, e componha UMA mensagem curta dizendo onde esta a divergencia e qual e o "
    "texto correto. "
    "Voce NAO escreve nos projetos: a pasta e somente leitura. Ofereca o texto corrigido para o dono "
    "colar, nunca diga que corrigiu. "
    "Se o bloco acima disser Monitor Baseline, este e o PRIMEIRO retrato e traz dezenas de linhas de "
    "uma vez, todas novidade para voce e nenhuma novidade para ele. Nao liste: diga em quantos "
    "projetos ha divergencia, escolha UM achado - o que quebra quem segue o documento agora - e "
    "ofereca o resto. "
    "Mande UMA mensagem so, de no maximo 6 linhas. Se a divergencia nao merecer interromper alguem, "
    "responda NO_REPLY."
)


def destino() -> str:
    """Para onde a mensagem vai.

    Sem destino explícito o Hermes entrega em `local`, que grava num arquivo
    dentro do container e não avisa ninguém — falha silenciosa que já custou
    três dias de agente mudo.
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
    try:
        dados = json.loads(JOBS.read_text())
    except FileNotFoundError:
        return []
    return dados.get("jobs", [])


def publicar_scripts() -> None:
    """Republica os scripts da cópia root-owned em /opt para a pasta que o
    runtime exige (`HERMES_HOME/scripts`, gravável pelo agente).

    É imposição do `--monitor-script`, não escolha: ele só aceita caminho
    relativo àquela pasta. Republicar a cada registro é a mitigação — alteração
    feita por um turno do agente não sobrevive a um novo setup.
    """
    SCRIPTS.mkdir(parents=True, exist_ok=True)
    for nome in ("docs_digest.py", "conferir_docs.py"):
        shutil.copyfile(CANONICO / nome, SCRIPTS / nome)


def main() -> int:
    publicar_scripts()

    # Registrado uma vez, congelado para sempre: ate aqui bastava o nome existir
    # para o registrador sair, sem olhar o que estava registrado. Entao toda
    # melhoria de instrucao, horario ou destino publicada neste repositorio
    # nunca alcancava quem ja tinha o job -- a base instalada parava no dia da
    # instalacao e ninguem percebia, porque o cron continuava rodando.
    for job in jobs_registrados():
        if job.get("name") != NOME:
            continue
        # So a instrucao: o intervalo praticamente nao muda, e comparar o
        # formato que o runtime usa para exibi-lo ("every 60m") seria acoplar
        # este script a um detalhe de apresentacao dele.
        if (job.get("prompt") or "").strip() == INSTRUCAO.strip():
            print(f"já registrado ({job.get('id')}) — nada a fazer")
            return 0
        # Recriar, e nao editar: `cron edit` nao alcanca todos os campos, e um job
        # meio atualizado e pior que um desatualizado.
        print(f"definicao mudou — recriando {NOME} ({job.get('id')})")
        subprocess.run([HERMES, "cron", "remove", str(job.get("id"))],
                       capture_output=True, text=True)
        break

    resultado = subprocess.run(
        [
            HERMES, "cron", "create", INTERVALO,
            INSTRUCAO,
            "--name", NOME,
            "--deliver", destino(),
            "--monitor-script", "docs_digest.py",
            "--skill", "doc-check",
        ],
        capture_output=True, text=True,
    )
    saida = (resultado.stdout + resultado.stderr).strip()
    if resultado.returncode != 0:
        print(f"falhou ao registrar: {saida}", file=sys.stderr)
        return 1
    print(saida.splitlines()[0] if saida else "registrado")
    return 0


if __name__ == "__main__":
    sys.exit(main())
