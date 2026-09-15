#!/usr/bin/env python3
"""Esta instalação está atrasada em relação ao repositório público?

Existe porque o agente não pode se atualizar sozinho, e isso é de propósito:
reconstruir a própria imagem exigiria o socket do Docker do host montado aqui
dentro, e aí um turno com prompt injetado teria controle total da máquina de
quem instalou. O preço dessa escolha é que uma instalação fica parada na versão
do dia em que foi feita, para sempre, sem ninguém perceber — e é esse preço que
este script paga: ele não atualiza nada, só sabe dizer que há o que atualizar.

Compara o commit gravado na imagem no build com o HEAD do repositório público.
Sem rede, sem git e sem Docker: uma requisição HTTP à API pública do GitHub.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

REPO = os.environ.get("CHECKPOINT_REPO", "alvesoff/checkpoint")
RAMO = os.environ.get("CHECKPOINT_BRANCH", "main")
REV_LOCAL = "/opt/checkpoint/rev"


def rev_instalada() -> str:
    try:
        with open(REV_LOCAL, encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return ""


def pedir(url: str) -> dict | list | None:
    pedido = urllib.request.Request(
        url, headers={"accept": "application/vnd.github+json",
                      "user-agent": "checkpoint-self-update"})
    try:
        with urllib.request.urlopen(pedido, timeout=20) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except (urllib.error.URLError, urllib.error.HTTPError, OSError, ValueError):
        return None


def main() -> int:
    local = rev_instalada()
    if not local or local == "desconhecido":
        # Não mentir: sem a revisão não dá para comparar, e dizer "está
        # atualizado" seria pior do que dizer que não sabe.
        print(json.dumps({
            "sabe": False,
            "motivo": "esta imagem não registrou em que commit foi construída",
            "como_resolver": "reinstale pelo install.sh, ou rode o build com "
                             "CHECKPOINT_REV=$(git rev-parse HEAD) no .env",
        }, ensure_ascii=False))
        return 0

    topo = pedir(f"https://api.github.com/repos/{REPO}/commits/{RAMO}")
    if not isinstance(topo, dict) or not topo.get("sha"):
        print(json.dumps({"sabe": False, "motivo": "não consegui falar com o GitHub agora"},
                         ensure_ascii=False))
        return 0

    remoto = topo["sha"]
    if remoto.startswith(local) or local.startswith(remoto):
        print(json.dumps({"sabe": True, "atualizado": True, "rev": local[:9]},
                         ensure_ascii=False))
        return 0

    # Quantos commits, e o que dizem. O dono decide se aplica, então ele precisa
    # saber o que mudaria — uma contagem sozinha não ajuda a decidir nada.
    comp = pedir(f"https://api.github.com/repos/{REPO}/compare/{local}...{remoto}")
    atras, mudancas = None, []
    if isinstance(comp, dict):
        atras = comp.get("ahead_by")
        for c in (comp.get("commits") or [])[-12:]:
            msg = ((c.get("commit") or {}).get("message") or "").splitlines()
            if msg:
                mudancas.append(msg[0][:110])

    print(json.dumps({
        "sabe": True,
        "atualizado": False,
        "rev_instalada": local[:9],
        "rev_publicada": remoto[:9],
        "commits_atras": atras,
        "o_que_mudou": list(reversed(mudancas)),
        "como_atualizar": "cd ~/checkpoint && git pull && docker compose up --build -d",
        "aviso": "o rebuild derruba o agente por alguns minutos e a plataforma "
                 "manda um aviso de gateway reiniciando",
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
