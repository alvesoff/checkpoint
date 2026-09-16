#!/usr/bin/env python3
"""Registra a vigia de segredo, sem duplicar. Roda dentro do container.

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

NOME = "checkpoint-segredo"

# Documentação apodrece devagar. De 12 em 12 horas o monitor roda; o agente só
# acorda quando a assinatura muda, então o custo de rodar é quase todo zero.
INTERVALO = "every 4h"

INSTRUCAO = (
    "Um segredo apareceu em arquivo solto nos projetos do dono. O achado esta no bloco MONITOR "
    "acima, no formato projeto|segredo|arquivo|tipos. Rode a skill stack-audit para o retrato "
    "completo e componha UMA mensagem curta, so sobre o que apareceu agora. "
    "Se o bloco disser Monitor Baseline, este e o PRIMEIRO retrato: nao ha nada de novo, sao "
    "segredos que ja estavam ali. Diga quantos sao e qual o mais grave, sem alarme de urgencia. "
    "Se o bloco vier VAZIO, nao ha segredo nenhum nos projetos: responda NO_REPLY e nao mande nada. "
    "Regras duras desta mensagem: "
    "NUNCA escreva o valor do segredo, nem parte dele, nem 'comeca com' -- diga o arquivo e o tipo. "
    "Diga o que fazer: tirar do arquivo, por em variavel de ambiente, e rotacionar a chave se o "
    "arquivo ja tiver sido enviado para algum lugar. "
    "Se o arquivo nao esta versionado, diga isso: e a boa noticia, e muda a urgencia. "
    "Uma mensagem so, no maximo 6 linhas, sem markdown. "
    "Se a mudanca nao merecer interromper alguem, responda NO_REPLY."
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
    for nome in ("audit_digest.py", "auditar.py"):
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
        # Editar, nao recriar: `cron remove` + `create` zera o monitor_state, e sem
        # linha de base o proximo tique conta TUDO como mudanca -- um "apareceu
        # agora" sobre o que ja estava la. Num vigia de segredo isso e pior que
        # ficar quieto: recapitula achados conhecidos como se fossem novos.
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
            "--monitor-script", "audit_digest.py",
            "--skill", "stack-audit",
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
