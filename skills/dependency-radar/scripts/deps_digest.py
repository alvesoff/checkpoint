#!/usr/bin/env python3
"""A assinatura estável do que está para trás. Sem isto, nada.

É o `--monitor-script` do radar: roda a cada tique e o agente só acorda quando a
saída MUDA. Por isso não pode conter nada que ande sozinho — nem data, nem
contagem que oscile, nem ordem dependente do sistema de arquivos.

O que muda a assinatura, e é quando vale interromper alguém:
  - um pacote PASSA a estar um major atrás (saiu versão nova)
  - um pacote PASSA a ser abandonado pelo mantenedor
  - o salto aumenta (de um major para dois)
  - o problema passa a atingir mais projetos

O que NÃO muda: o tempo passando sobre um problema que a pessoa já conhece.
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
            [sys.executable, os.path.join(AQUI, "deps_scan.py")],
            capture_output=True, text=True, timeout=600,
        )
        dados = json.loads(saida.stdout)
    except (subprocess.SubprocessError, OSError, ValueError):
        # Silêncio, não erro: rede fora é temporário, e um erro repetido também
        # é uma assinatura estável — acordaria o agente uma vez para reclamar de
        # algo que se resolve sozinho.
        return 0

    if dados.get("erro"):
        return 0

    linhas = []
    for a in dados.get("achados", []):
        if a["tipo"] == "abandonado":
            linhas.append(f"{a['pacote']}|abandonado|{a['quantos']}")
        else:
            # O salto em majors, não a versão exata: um patch novo do mesmo
            # major não é notícia e não deve acordar ninguém.
            try:
                salto = int(a["atual"].split(".")[0]) - int(a["voce_usa"].split(".")[0])
            except (ValueError, IndexError):
                salto = 1
            linhas.append(f"{a['pacote']}|atras:{salto}|{a['quantos']}")

    for linha in sorted(linhas):
        print(linha)
    return 0


if __name__ == "__main__":
    sys.exit(main())
