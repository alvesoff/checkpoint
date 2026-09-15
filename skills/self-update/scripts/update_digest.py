#!/usr/bin/env python3
"""A assinatura estável de "há versão nova publicada".

Imprime uma linha com a revisão publicada quando esta instalação está atrasada,
e NADA quando está em dia. Como o monitor só acorda o agente quando a assinatura
muda, o efeito é: um aviso por versão nova, não um por dia.

Sem isso o cron diário avisaria todo dia a mesma coisa enquanto o dono não
atualizasse — e aviso repetido é o que faz alguém silenciar um agente.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

AQUI = os.path.dirname(os.path.realpath(__file__))


def main() -> int:
    try:
        saida = subprocess.run(
            [sys.executable, os.path.join(AQUI, "checar_atualizacao.py")],
            capture_output=True, text=True, timeout=60,
            encoding="utf-8", errors="replace",
        )
        dados = json.loads(saida.stdout)
    except (subprocess.SubprocessError, OSError, ValueError):
        # Silêncio, não erro: GitHub fora do ar ou rede caída é coisa que passa
        # sozinha, e uma falha repetida também é assinatura estável — acordaria
        # o agente uma vez para reclamar do que se resolve só.
        return 0

    if not dados.get("sabe") or dados.get("atualizado"):
        return 0

    # A revisão publicada É a assinatura: ela só muda quando sai versão nova.
    print(f"ATUALIZACAO|{dados.get('rev_publicada')}|{dados.get('commits_atras')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
