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
# Mesma rede, mesmo motivo, outra metade da assinatura: 40 das 48 linhas são de
# atraso, e era justamente aí que a queda de rede passava sem proteção.
CACHE_ATRASO = os.path.join(HOME, "checkpoint", "assinatura_atrasada.txt")

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
    def do_cache() -> list[str]:
        try:
            with open(CACHE, encoding="utf-8") as f:
                return [linha for linha in f.read().splitlines() if linha]
        except OSError:
            return []

    dados = rodar("vulneraveis.py", 900)
    if dados is None or dados.get("erro"):
        return do_cache()

    # Falha PARCIAL e o caso perigoso, e era o que faltava. Quando um lote da
    # OSV cai, o script devolve sucesso com menos achados: nada indica erro, a
    # assinatura encolhe, e o agente acorda para dizer que a vulnerabilidade
    # sumiu. Enquanto houver consulta falhada, o ultimo resultado bom manda e o
    # cache NAO e reescrito -- sobrescrever com um retrato incompleto apaga a
    # rede de protecao exatamente no momento em que ela e necessaria.
    if dados.get("consultas_que_falharam"):
        return do_cache()

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


def cache_de_atraso() -> dict:
    """Última linha boa por pacote."""
    try:
        with open(CACHE_ATRASO, encoding="utf-8") as f:
            return {linha.split("|")[1]: linha for linha in f.read().splitlines()
                    if linha.count("|") >= 3}
    except (OSError, IndexError):
        return {}


def linhas_de_atraso() -> list[str]:
    """O que está para trás, com o último resultado bom cobrindo o que a rede
    não deixou consultar.

    Um pacote que não pôde ser consultado é DESCONHECIDO, não resolvido. Se ele
    simplesmente sumir da assinatura, o monitor entende "mudou" e acorda o dono
    — e acorda de novo quando a rede voltar. Em 15/09 isso tirou o dono da cama
    às 02:09 para repetir um alerta que ele já tinha às 20:06.
    """
    dados = rodar("deps_scan.py", 600)
    if dados is None or dados.get("erro"):
        # Silêncio, não erro: rede fora é temporário, e um erro repetido também
        # é assinatura estável — acordaria o agente uma vez para reclamar de
        # algo que se resolve sozinho.
        return sorted(cache_de_atraso().values())

    linhas = {}
    for a in dados.get("achados", []):
        if a["tipo"] == "abandonado":
            linhas[a["pacote"]] = f"ATRAS|{a['pacote']}|abandonado|{a['quantos']}"
        else:
            # O salto em majors, não a versão exata: um patch novo do mesmo
            # major não é notícia e não deve acordar ninguém.
            try:
                salto = int(a["atual"].split(".")[0]) - int(a["voce_usa"].split(".")[0])
            except (ValueError, IndexError):
                salto = 1
            linhas[a["pacote"]] = f"ATRAS|{a['pacote']}|major:{salto}|{a['quantos']}"

    # Só para quem a rede engoliu. Pacote consultado com sucesso e sem achado
    # está resolvido de verdade, e sumir da assinatura é a notícia boa que o
    # dono merece receber.
    antigas = cache_de_atraso()
    for pacote in dados.get("nao_consultados", []):
        if pacote not in linhas and pacote in antigas:
            linhas[pacote] = antigas[pacote]

    try:
        os.makedirs(os.path.dirname(CACHE_ATRASO), exist_ok=True)
        with open(CACHE_ATRASO, "w", encoding="utf-8") as f:
            f.write("\n".join(sorted(linhas.values())))
    except OSError:
        pass
    return list(linhas.values())


def main() -> int:
    # Vulnerabilidade primeiro na saída: o bloco de mudança chega ao agente
    # nesta ordem, e a primeira linha é a que ele lê com mais atenção.
    for linha in sorted(linhas_de_vulnerabilidade()) + sorted(linhas_de_atraso()):
        print(linha)
    return 0


if __name__ == "__main__":
    sys.exit(main())
