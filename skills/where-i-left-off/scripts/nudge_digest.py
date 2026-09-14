#!/usr/bin/env python3
"""A assinatura estável do que está travado. Sem isto, nada.

Este script é o `--monitor-script` do cron do Hermes: ele roda a cada tique, e o
agente só é acordado quando a saída MUDA. Estado parado imprime a mesma coisa e
custa zero token.

Por isso a saída não pode conter nada que ande sozinho — nem data, nem hora, nem
"há 2.7 dias". Se contivesse, mudaria a cada tique e o agente seria acordado
para dizer que nada mudou, que é exatamente o ruído que faz desinstalar.

A idade entra como FAIXA. A consequência é o desenho todo: a assinatura muda no
instante em que um projeto **cruza** para uma faixa pior, e é aí que vale avisar.
Um projeto parado há três dias continua parado amanhã sem gerar mensagem
nenhuma; quando vira uma semana, gera.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))

from scan_projects import RAIZ, estado, repositorios  # noqa: E402

# Dias completos antes de algo contar como travado. Abaixo disto é só trabalho
# em andamento: ninguém quer ser cutucado sobre o que mexeu hoje de manhã.
DIAS_ATE_TRAVADO = 2

# As fronteiras que valem um aviso. Escolhidas para serem poucas: cada faixa a
# mais é uma mensagem a mais na vida de quem instalou.
FAIXAS = (2, 4, 7, 14, 30, 60)


def faixa(dias: float) -> str:
    """A maior fronteira que estes dias já cruzaram."""
    marca = FAIXAS[0]
    for limite in FAIXAS:
        if dias >= limite:
            marca = limite
    return f"{marca}d+"


def sinal(projeto: dict) -> str | None:
    """Uma linha estável para um projeto travado, ou None se ele não está.

    Trabalho não salvo e trabalho não enviado são coisas diferentes e a pessoa
    reage diferente a cada uma, então a assinatura distingue — e muda quando o
    projeto passa de um para o outro.
    """
    # O relógio é o último TOQUE em arquivo, não a data do commit. Alguém que
    # mexeu no projeto hoje está trabalhando nele — cutucar seria ruído, mesmo
    # que o último commit seja de dois meses atrás. E o caso inverso é o que
    # torna isso obrigatório: um projeto que nunca foi versionado tem commit
    # antigo e trabalho recente, e seria cutucado todo dia pelo motivo errado.
    dias = projeto.get("ultimo_toque_ha_dias")
    if dias is None:
        dias = projeto["ultimo_commit"]["ha_dias"]
    if dias < DIAS_ATE_TRAVADO:
        return None

    if projeto["arquivos_alterados"]:
        estado_txt = f"nao-salvo:{projeto['arquivos_alterados']}"
    elif projeto["commits_nao_enviados"]:
        estado_txt = f"nao-enviado:{projeto['commits_nao_enviados']}"
    elif projeto["branch_sem_upstream"]:
        estado_txt = "branch-nunca-enviado"
    else:
        # Parado, mas nada pendente: o trabalho está salvo e entregue. Isso não
        # é uma ponta solta, é um projeto em repouso. Não avisa.
        return None

    return f"{projeto['projeto']}|{projeto['branch']}|{estado_txt}|{faixa(dias)}"


def quedas_nao_avisadas() -> list[str]:
    """As janelas em que o canal ficou fora do ar e o dono ainda não soube.

    Entram na assinatura de propósito: uma queda muda a saída do monitor, o
    agente acorda e conta. Sem isto a falha permanece invisível — foi assim que
    esta instalação passou três dias muda sem ninguém notar.

    A janela vai arredondada em minutos, e não com horário exato, para a
    assinatura não mudar sozinha a cada tique.
    """
    caminho = os.path.join(
        os.environ.get("HERMES_HOME", "/var/lib/hermes"), "checkpoint", "quedas.json")
    try:
        with open(caminho, encoding="utf-8") as f:
            dados = json.load(f)
    except (OSError, ValueError):
        return []
    return [f"canal-fora|{q['minutos']}min|{q['inicio']}"
            for q in dados.get("quedas", []) if not q.get("avisado")]


def main() -> int:
    if not os.path.isdir(RAIZ):
        # Silêncio, não erro: um erro repetido a cada tique é uma assinatura
        # estável também, mas acordaria o agente uma vez para reclamar de algo
        # que a pessoa resolve na instalação, não por mensagem.
        return 0

    linhas = []
    for repo in repositorios(RAIZ):
        projeto = estado(repo)
        if projeto.get("vazio") or projeto.get("arquivado"):
            continue
        marca = sinal(projeto)
        if marca:
            linhas.append(marca)

    # Ordenado para que a assinatura não dependa da ordem em que o sistema de
    # arquivos devolveu as pastas.
    # A queda do canal vem primeiro: é a única linha que explica por que o dono
    # pode ter ficado sem resposta, e isso vale mais que qualquer ponta solta.
    for linha in quedas_nao_avisadas():
        print(linha)

    for linha in sorted(linhas):
        print(linha)
    return 0


if __name__ == "__main__":
    sys.exit(main())
