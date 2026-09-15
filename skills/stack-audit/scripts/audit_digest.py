#!/usr/bin/env python3
"""A assinatura estável do que está exposto nos projetos do dono.

O `stack-audit` era a única skill detectora sem monitor: ele encontra segredo
em arquivo solto e container rodando como root, e nada disso acordava ninguém.
Quem colasse uma chave num `.env` não versionado ficava com ela ali até pensar
em perguntar — e ninguém pergunta sobre o que não sabe que existe.

O que entra na assinatura: só o **segredo em arquivo solto**, pelo caminho e
pelo tipo, nunca pelo valor. É o único achado do auditor que é urgente por
natureza e que aparece do nada, entre uma auditoria e outra.

O que NÃO entra, de propósito: Dockerfile como root, imagem base velha, falta
de healthcheck. São verdadeiros, são importantes, e não mudam sozinhos — viram
demanda na lista, não interrupção. Um monitor que acorda o agente para dizer o
que ele já disse ontem é um monitor que a pessoa desliga.
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
            [sys.executable, os.path.join(AQUI, "auditar.py")],
            capture_output=True, text=True, timeout=240,
            encoding="utf-8", errors="replace",
        )
        dados = json.loads(saida.stdout)
    except (subprocess.SubprocessError, OSError, ValueError):
        # Silêncio, não erro: uma falha repetida também é assinatura estável e
        # acordaria o agente uma vez para reclamar do que se resolve sozinho.
        return 0

    if dados.get("erro"):
        return 0

    linhas = []
    for s in dados.get("segredos_em_arquivo_solto", []):
        tipos = ",".join(sorted(s.get("tipos") or []))
        # Caminho e tipo. NUNCA o valor: esta linha vai para o estado do monitor
        # e para o prompt do agente, e um segredo que vaza para o log do
        # container é pior que o segredo parado no arquivo.
        linhas.append(f"{s.get('projeto')}|segredo|{s.get('arquivo')}|{tipos}")

    for linha in sorted(linhas):
        print(linha)
    return 0


if __name__ == "__main__":
    sys.exit(main())
