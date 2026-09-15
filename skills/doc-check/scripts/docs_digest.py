#!/usr/bin/env python3
"""A assinatura estável das divergências entre documento e código.

É o `--monitor-script` do `doc-check`: roda a cada tique e o agente só acorda
quando a saída MUDA. Por isso não pode conter nada que ande sozinho — nem data,
nem contagem que oscile, nem ordem dependente do sistema de arquivos.

O que muda a assinatura, e é quando vale interromper alguém:
  - uma referência PASSA a apontar para nada (alguém renomeou e não avisou o texto)
  - um comando some do `package.json` e continua no README
  - uma variável nova entra no código sem entrar em documento nenhum

O que NÃO muda: o tempo passando sobre uma divergência que o dono já viu e
decidiu não consertar hoje.
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
            [sys.executable, os.path.join(AQUI, "conferir_docs.py")],
            capture_output=True, text=True, timeout=600,
            encoding="utf-8", errors="replace",
        )
        dados = json.loads(saida.stdout)
    except (subprocess.SubprocessError, OSError, ValueError):
        # Silêncio, não erro: uma falha repetida também é assinatura estável, e
        # acordaria o agente uma vez para reclamar do que se resolve sozinho.
        return 0

    if dados.get("erro"):
        return 0

    linhas = []
    for r in dados.get("relatorios", []):
        projeto = r["projeto"]
        for q in r.get("referencias_quebradas", []):
            linhas.append(f"{projeto}|ref|{q['aponta_para']}")
        for c in r.get("comandos_que_sumiram", []):
            linhas.append(f"{projeto}|cmd|{c}")
        for v in r.get("variaveis_exigidas_sem_documentacao", []):
            linhas.append(f"{projeto}|env|{v}")
        # O quarto achado que o conferir_docs emite. Sem esta linha ele existia,
        # era medido e nunca acordava ninguem: documento mandando rodar um
        # comando que so existe em outro workspace nao entrava na assinatura, e
        # o monitor so compara assinaturas.
        for c in r.get("comandos_fora_do_lugar", []):
            linhas.append(f"{projeto}|fora|{c}")

    for linha in sorted(linhas):
        print(linha)
    return 0


if __name__ == "__main__":
    sys.exit(main())
