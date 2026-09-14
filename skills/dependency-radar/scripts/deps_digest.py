#!/usr/bin/env python3
"""A assinatura estável do que está para trás e do que está vulnerável.

É o `--monitor-script` do radar: roda a cada tique e o agente só acorda quando a
saída MUDA. Por isso não pode conter nada que ande sozinho — nem data, nem
contagem que oscile, nem ordem dependente do sistema de arquivos.

O que muda a assinatura, e é quando vale interromper alguém:
  - **uma vulnerabilidade grave passa a existir num pacote que a pessoa usa**
  - um pacote PASSA a estar um major atrás (saiu versão nova)
  - um pacote PASSA a ser abandonado pelo mantenedor
  - o salto aumenta (de um major para dois)
  - o problema passa a atingir mais projetos

O que NÃO muda: o tempo passando sobre um problema que a pessoa já conhece.

A vulnerabilidade entrou aqui depois de uma constatação incômoda: ela era o
achado mais grave do produto inteiro e **não tinha caminho de aviso nenhum** —
só aparecia se o dono pedisse a lista de demandas. Um agente que sabe de uma
falha CRITICAL e espera ser perguntado não está cuidando de ninguém.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

AQUI = os.path.dirname(os.path.realpath(__file__))
HOME = os.environ.get("HERMES_HOME", "/var/lib/hermes")
# A última assinatura de vulnerabilidade que deu certo. Existe por um motivo
# específico, explicado em `linhas_de_vulnerabilidade`.
CACHE = os.path.join(HOME, "checkpoint", "assinatura_vulneravel.txt")

# Só o que interrompe alguém. MODERATE e abaixo vivem na lista de demandas: um
# aviso por vulnerabilidade média, com vinte projetos, é ruído diário garantido
# — e ruído diário é como se ensina alguém a ignorar o aviso que importa.
GRAVES = ("CRITICAL", "HIGH")


def rodar(script: str, segundos: int) -> dict | None:
    try:
        saida = subprocess.run(
            [sys.executable, os.path.join(AQUI, script)],
            capture_output=True, text=True, timeout=segundos,
            encoding="utf-8", errors="replace",
        )
        return json.loads(saida.stdout)
    except (subprocess.SubprocessError, OSError, ValueError):
        return None


def linhas_de_vulnerabilidade() -> list[str]:
    """As vulnerabilidades graves, com o último resultado bom como rede.

    A consulta depende da rede e da OSV. Se ela falhar e nós simplesmente
    omitíssemos as linhas, a assinatura **encolheria** — e o agente acordaria
    para anunciar que as vulnerabilidades sumiram, que é a pior mensagem falsa
    que este produto poderia mandar. Então: falhou, repete a última boa.
    """
    dados = rodar("vulneraveis.py", 900)
    if dados is None or dados.get("erro"):
        try:
            with open(CACHE, encoding="utf-8") as f:
                return [linha for linha in f.read().splitlines() if linha]
        except OSError:
            return []

    linhas = [
        f"VULN|{a['pacote']}|{a['versao_declarada']}|{a['pior']}|{a['quantos']}"
        for a in dados.get("achados", []) if a.get("pior") in GRAVES
    ]
    try:
        os.makedirs(os.path.dirname(CACHE), exist_ok=True)
        with open(CACHE, "w", encoding="utf-8") as f:
            f.write("\n".join(sorted(linhas)))
    except OSError:
        pass
    return linhas


def linhas_de_atraso() -> list[str]:
    dados = rodar("deps_scan.py", 600)
    if dados is None or dados.get("erro"):
        # Silêncio, não erro: rede fora é temporário, e um erro repetido também
        # é assinatura estável — acordaria o agente uma vez para reclamar de
        # algo que se resolve sozinho.
        return []

    linhas = []
    for a in dados.get("achados", []):
        if a["tipo"] == "abandonado":
            linhas.append(f"ATRAS|{a['pacote']}|abandonado|{a['quantos']}")
        else:
            # O salto em majors, não a versão exata: um patch novo do mesmo
            # major não é notícia e não deve acordar ninguém.
            try:
                salto = int(a["atual"].split(".")[0]) - int(a["voce_usa"].split(".")[0])
            except (ValueError, IndexError):
                salto = 1
            linhas.append(f"ATRAS|{a['pacote']}|major:{salto}|{a['quantos']}")
    return linhas


def main() -> int:
    # Vulnerabilidade primeiro na saída: o bloco de mudança chega ao agente
    # nesta ordem, e a primeira linha é a que ele lê com mais atenção.
    for linha in sorted(linhas_de_vulnerabilidade()) + sorted(linhas_de_atraso()):
        print(linha)
    return 0


if __name__ == "__main__":
    sys.exit(main())
