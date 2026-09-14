#!/usr/bin/env python3
"""Vulnerabilidade conhecida nas versões que os projetos realmente usam.

Consulta a base pública da OSV (`api.osv.dev`), que não exige credencial nem
conta — importante, porque toda credencial exigida derruba a instalação.

A diferença para `npm audit`: o audit responde por projeto e sobre a árvore
resolvida do lockfile. Isto responde **em quantos dos seus projetos a mesma
vulnerabilidade aparece**, que é a ordem em que se conserta quando se tem vinte
repositórios — e é a pergunta que nenhuma ferramenta por projeto consegue fazer.

Fala de **versão declarada**, não resolvida: lemos manifesto, não lockfile. Isso
é dito na saída, porque um alarme sobre versão que o lockfile já corrigiu é um
alarme falso, e alarme falso ensina a pessoa a ignorar os verdadeiros.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

AQUI = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, AQUI)

from deps_scan import ler_manifestos, RAIZ, versao_limpa  # noqa: E402

OSV = "https://api.osv.dev/v1/querybatch"

# A OSV aceita lote, e um lote grande é uma chamada em vez de duzentas. Cem por
# vez é o que responde em tempo razoável sem estourar o turno do agente.
LOTE = 100

# Severidade que vale interromper alguém. `MODERATE` e abaixo entram na lista de
# demandas, mas não viram aviso: um aviso por vulnerabilidade média, num universo
# de vinte projetos, é ruído diário garantido.
GRAVES = {"CRITICAL", "HIGH"}


def severidade(ident: str, cache: dict) -> str:
    """A severidade de uma vulnerabilidade, buscada por id.

    O `querybatch` devolve **apenas `id` e `modified`** — descobrir isso custou
    um relatório inteiro em que tudo saía como "DESCONHECIDA", que é pior que
    não relatar: uma lista sem gravidade não prioriza nada.

    O rótulo de verdade está em `database_specific.severity`. O CVSS numérico é
    a segunda opção, com as faixas da própria convenção.
    """
    if ident in cache:
        return cache[ident]
    nivel = "DESCONHECIDA"
    try:
        with urllib.request.urlopen(f"https://api.osv.dev/v1/vulns/{ident}", timeout=25) as r:
            d = json.load(r)
        nivel = ((d.get("database_specific") or {}).get("severity") or "").upper() or "DESCONHECIDA"
        if nivel == "DESCONHECIDA":
            for s_ in d.get("severity") or []:
                pontos = str(s_.get("score", ""))
                if pontos.startswith("CVSS"):
                    continue
                try:
                    valor = float(pontos)
                except ValueError:
                    continue
                nivel = ("CRITICAL" if valor >= 9 else "HIGH" if valor >= 7
                         else "MODERATE" if valor >= 4 else "LOW")
                break
    except (urllib.error.URLError, urllib.error.HTTPError, ValueError, OSError):
        pass
    cache[ident] = nivel
    return nivel


def consultar(consultas: list[dict]) -> list[dict]:
    resultados: list[dict] = []
    for i in range(0, len(consultas), LOTE):
        corpo = json.dumps({"queries": consultas[i:i + LOTE]}).encode()
        pedido = urllib.request.Request(
            OSV, data=corpo, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(pedido, timeout=40) as r:
                resultados += json.load(r).get("results", [])
        except (urllib.error.URLError, urllib.error.HTTPError, ValueError, OSError):
            # Um lote que falhou não pode zerar os outros: relatório incompleto
            # é melhor que relatório ausente, desde que se saiba que faltou.
            resultados += [{"erro": True}] * len(consultas[i:i + LOTE])
    return resultados


def main() -> int:
    if not os.path.isdir(RAIZ):
        print(json.dumps({"erro": f"{RAIZ} não existe dentro do container"}, ensure_ascii=False))
        return 1

    usos, _ = ler_manifestos(RAIZ)

    # Uma consulta por (pacote, versão) distinta — não por projeto. Dois projetos
    # na mesma versão são a mesma pergunta.
    chaves: dict[tuple, list[str]] = {}
    for (eco, pacote), onde in usos.items():
        for projeto, versao in onde.items():
            limpa = versao_limpa(versao)
            if not limpa:
                continue
            chaves.setdefault((eco, pacote, limpa), []).append(projeto)

    consultas = [{"package": {"name": p, "ecosystem": "npm" if e == "npm" else "PyPI"},
                  "version": v} for (e, p, v) in chaves]
    if not consultas:
        print(json.dumps({"erro": "nenhuma dependência com versão declarada"}, ensure_ascii=False))
        return 1

    achados = []
    falhas = 0
    for (chave, resultado) in zip(chaves, consultar(consultas)):
        if resultado.get("erro"):
            falhas += 1
            continue
        vulns = resultado.get("vulns") or []
        if not vulns:
            continue
        eco, pacote, versao = chave
        achados.append({
            "pacote": pacote,
            "ecossistema": eco,
            "versao_declarada": versao,
            "projetos": sorted(set(chaves[chave])),
            "quantos": len(set(chaves[chave])),
            "vulnerabilidades": len(vulns),
            "ids": [v["id"] for v in vulns[:6]],
        })

    # A gravidade custa uma consulta por vulnerabilidade, então só vale buscá-la
    # para os pacotes mais espalhados — que são os que a pessoa vai consertar
    # primeiro de qualquer forma. O resto fica com a contagem, sem rótulo.
    achados.sort(key=lambda a: -a["quantos"])
    cache: dict[str, str] = {}
    ordem_nivel = {"CRITICAL": 0, "HIGH": 1, "MODERATE": 2, "LOW": 3, "DESCONHECIDA": 4}
    for a in achados[:12]:
        niveis = [severidade(i, cache) for i in a["ids"][:5]]
        a["pior"] = min(niveis, key=lambda n: ordem_nivel.get(n, 9)) if niveis else "DESCONHECIDA"
    for a in achados[12:]:
        a["pior"] = "nao-consultada"

    # Grave primeiro, e dentro da gravidade o que atinge mais projetos: é a ordem
    # em que se conserta.
    achados.sort(key=lambda a: (ordem_nivel.get(a["pior"], 9), -a["quantos"]))

    print(json.dumps({
        "consultadas": len(consultas),
        "com_vulnerabilidade": len(achados),
        "graves": sum(1 for a in achados if a["pior"] in GRAVES),
        "consultas_que_falharam": falhas,
        "aviso": "versões declaradas nos manifestos, não as resolvidas pelo lockfile",
        "achados": achados[:30],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
