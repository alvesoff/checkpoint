#!/usr/bin/env python3
"""Marca as quedas de conexão já contadas ao dono, para não repetir o aviso.

Existe porque o fechamento deste ciclo era um heredoc dentro do SKILL.md — o
único lugar em todo o repositório que gravava `avisado: true`. Três problemas
com isso: quem escreve é o modelo, não um script, então a gravação dependia de
ele copiar o bloco certo; não havia escrita atômica, então uma interrupção no
meio deixava o arquivo truncado e o histórico de quedas ia junto; e um arquivo
de estado corrompido faz o vigia de rede parar de avisar, em silêncio.
"""

from __future__ import annotations

import json
import os
import sys

CAMINHO = os.path.join(
    os.environ.get("HERMES_HOME", "/var/lib/hermes"), "checkpoint", "quedas.json"
)


def main() -> int:
    try:
        with open(CAMINHO, encoding="utf-8") as f:
            dados = json.load(f)
    except FileNotFoundError:
        print(json.dumps({"marcadas": 0, "motivo": "nenhuma queda registrada"}, ensure_ascii=False))
        return 0
    except (OSError, ValueError) as erro:
        # Falhar aqui em voz alta: silêncio faria o agente repetir o mesmo aviso
        # a cada turno, que é o comportamento que mais rápido leva alguém a
        # silenciar um agente.
        print(json.dumps({"erro": f"{CAMINHO} não pôde ser lido: {erro}"}, ensure_ascii=False))
        return 1

    quedas = dados.get("quedas") or []
    pendentes = [q for q in quedas if not q.get("avisado")]
    if not pendentes:
        print(json.dumps({"marcadas": 0, "motivo": "nada pendente de aviso"}, ensure_ascii=False))
        return 0

    for q in pendentes:
        q["avisado"] = True

    # Escrita atômica: gravar por cima do arquivo bom e ser interrompido no meio
    # perde o histórico inteiro de quedas, que é a única prova de que o agente
    # esteve fora do ar.
    temporario = CAMINHO + ".tmp"
    try:
        with open(temporario, "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporario, CAMINHO)
    except OSError as erro:
        print(json.dumps({"erro": f"não consegui gravar: {erro}"}, ensure_ascii=False))
        return 1

    print(json.dumps({"marcadas": len(pendentes)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
