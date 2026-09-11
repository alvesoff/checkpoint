#!/usr/bin/env python3
"""Lê o estado real de cada projeto montado e devolve JSON.

Só stdlib e o `git` do sistema. Nada aqui decide o que é importante — isso é do
agente. Este script responde uma pergunta factual: para cada repositório, onde o
trabalho parou e há quanto tempo.

A montagem é read-only de propósito, e nenhum comando aqui escreve: todo `git`
invocado é de leitura. Quem instala precisa poder verificar isso lendo o arquivo.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time

RAIZ = os.environ.get("PROJECTS_ROOT", "/projects")

# Um repositório sem commit nos últimos N dias não é "parado", é arquivado. A
# diferença importa: cutucar alguém sobre um projeto que ele abandonou de
# propósito é ruído, e ruído é o que faz desinstalar.
DIAS_ATE_ARQUIVADO = 90


def git(repo: str, *args: str) -> str:
    """Um comando git de leitura, ou string vazia se ele falhar.

    Falha silenciosa é deliberada aqui: um repositório sem commit nenhum, com
    HEAD solto ou corrompido não pode derrubar a varredura dos outros.
    """
    try:
        saida = subprocess.run(
            # core.autocrlf=true na LEITURA, e isto não é detalhe: um repo
            # clonado no Windows fica com CRLF no disco e LF no index, e aí
            # `git status` acusa TODOS os arquivos como modificados. Sem esta
            # linha, todo usuário de Windows receberia "trabalho não salvo" em
            # todos os projetos — o agente viraria ruído puro para metade dos
            # instaladores. Medido: 96 arquivos falsos viram 0, enquanto um
            # repositório com pendência real continua acusando as 28 dele.
            #
            # Só normaliza a comparação; nada aqui escreve, e a montagem é :ro.
            ["git", "-c", "core.autocrlf=true", "-C", repo, *args],
            capture_output=True,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return saida.stdout.strip() if saida.returncode == 0 else ""


def repositorios(raiz: str) -> list[str]:
    """Os repositórios sob a raiz: os filhos diretos, e a própria raiz se for um.

    Não desce recursivamente. Quem monta uma pasta de código quer os projetos
    dela, não cada submódulo e cada `node_modules` com .git dentro — e uma
    varredura profunda numa árvore grande demora o suficiente para estourar o
    turno do agente.
    """
    achados = []
    if os.path.isdir(os.path.join(raiz, ".git")):
        achados.append(raiz)
        return achados
    try:
        entradas = sorted(os.scandir(raiz), key=lambda e: e.name)
    except OSError:
        return achados
    for entrada in entradas:
        if entrada.is_dir() and os.path.isdir(os.path.join(entrada.path, ".git")):
            achados.append(entrada.path)
    return achados


def nome_do_projeto(repo: str) -> str:
    """O nome que a pessoa reconhece.

    Normalmente é o nome da pasta. Mas quando alguém aponta CODE_DIR para um
    projeto só — o que funciona e é legítimo — a pasta dentro do container se
    chama "projects", que é o ponto de montagem e não diz nada. Nesse caso o
    nome sai da URL do remote, que é como o projeto se chama de verdade.
    """
    base = os.path.basename(repo.rstrip("/\\"))
    if base != os.path.basename(RAIZ.rstrip("/\\")):
        return base
    origem = git(repo, "remote", "get-url", "origin")
    if origem:
        return os.path.basename(origem.rstrip("/")).removesuffix(".git")
    return base


def estado(repo: str) -> dict:
    """O retrato de um repositório: onde parou, e o que ficou pela metade."""
    ultimo = git(repo, "log", "-1", "--format=%H%x1f%ct%x1f%s%x1f%an")
    if not ultimo:
        # Duas coisas muito diferentes chegam aqui, e confundi-las esconde uma
        # instalação quebrada: um repositório legitimamente sem commit, e um
        # `git` que não conseguiu ler o repositório (dono divergente, permissão,
        # binário ausente). O segundo caso, silenciado, faz 25 repositórios
        # virarem "nenhum projeto ativo" em vez de um erro que se conserta.
        if git(repo, "rev-parse", "--git-dir"):
            return {"projeto": nome_do_projeto(repo), "vazio": True}
        return {
            "projeto": nome_do_projeto(repo),
            "ilegivel": True,
            "erro": "git não conseguiu ler este repositório",
        }

    sha, epoch, assunto, autor = (ultimo.split("\x1f") + ["", "", "", ""])[:4]
    try:
        idade_dias = (time.time() - int(epoch)) / 86400
    except ValueError:
        idade_dias = 0.0

    # `status --porcelain` lista uma linha por caminho alterado. É o sinal mais
    # forte de "parei no meio": o trabalho existe e não foi salvo em lugar
    # nenhum, então some se a máquina morrer e ninguém além do dono o vê.
    sujo = [linha for linha in git(repo, "status", "--porcelain").splitlines() if linha]

    # Commits à frente do upstream: trabalho salvo localmente que ninguém mais
    # recebeu. Vazio quando o branch não tem upstream, que é o caso comum de um
    # branch criado e nunca empurrado — tratado logo abaixo.
    adiante = git(repo, "rev-list", "--count", "@{upstream}..HEAD")
    tem_upstream = bool(git(repo, "rev-parse", "--abbrev-ref", "@{upstream}"))

    # Um repositório sem remote nenhum não tem para onde enviar, então "branch
    # nunca enviado" não é ponta solta nele — é a condição normal. Sem esta
    # distinção, todo repositório puramente local ficaria travado para sempre,
    # e quem tem uma pasta de projetos locais receberia ruído até desinstalar.
    tem_remote = bool(git(repo, "remote"))

    # Um repositório com um único commit e vários arquivos nunca versionados não
    # é trabalho parado no meio: é um projeto que nunca entrou no git de verdade.
    # Os dois estados pedem ações opostas — um pede retomar, o outro pede
    # começar a versionar — então o agente precisa conseguir distinguir sem
    # adivinhar.
    total = git(repo, "rev-list", "--count", "HEAD")
    commits_total = int(total) if total.isdigit() else 0

    return {
        "projeto": nome_do_projeto(repo),
        "caminho": repo,
        "branch": git(repo, "rev-parse", "--abbrev-ref", "HEAD") or "(desconhecido)",
        "ultimo_commit": {
            "sha": sha[:8],
            "assunto": assunto,
            "autor": autor,
            "ha_dias": round(idade_dias, 1),
        },
        "arquivos_alterados": len(sujo),
        "arquivos": [linha[3:] for linha in sujo[:10]],
        "commits_nao_enviados": int(adiante) if adiante.isdigit() else 0,
        "tem_remote": tem_remote,
        "commits_total": commits_total,
        "nunca_versionado": commits_total <= 1 and len(sujo) >= 5,
        "branch_sem_upstream": tem_remote and not tem_upstream,
        "arquivado": idade_dias > DIAS_ATE_ARQUIVADO,
    }


def main() -> int:
    if not os.path.isdir(RAIZ):
        print(
            json.dumps(
                {
                    "erro": f"{RAIZ} não existe dentro do container",
                    "como_resolver": (
                        "monte sua pasta de código: em compose.yml, "
                        "volumes: - ${CODE_DIR}:/projects:ro"
                    ),
                },
                ensure_ascii=False,
            )
        )
        return 1

    repos = repositorios(RAIZ)
    if not repos:
        print(
            json.dumps(
                {
                    "erro": f"nenhum repositório git encontrado em {RAIZ}",
                    "como_resolver": (
                        "aponte CODE_DIR para a pasta que contém seus projetos, "
                        "não para um projeto só"
                    ),
                },
                ensure_ascii=False,
            )
        )
        return 1

    projetos = [estado(r) for r in repos]
    ilegiveis = [p for p in projetos if p.get("ilegivel")]
    ativos = [
        p for p in projetos
        if not p.get("arquivado") and not p.get("vazio") and not p.get("ilegivel")
    ]

    # Todos ilegíveis não é "nada para relatar": é instalação quebrada, e quem
    # instalou precisa ver isso em vez de uma lista vazia.
    if ilegiveis and not ativos:
        print(
            json.dumps(
                {
                    "erro": f"nenhum dos {len(ilegiveis)} repositórios pôde ser lido pelo git",
                    "como_resolver": (
                        "normalmente é dono divergente entre host e container: "
                        "confirme que a imagem traz /etc/gitconfig com "
                        "safe.directory = *"
                    ),
                    "repositorios": [p["projeto"] for p in ilegiveis[:10]],
                },
                ensure_ascii=False,
            )
        )
        return 1

    print(
        json.dumps(
            {
                "raiz": RAIZ,
                "total": len(projetos),
                "ativos": len(ativos),
                "ilegiveis": len(ilegiveis),
                "projetos": sorted(
                    ativos,
                    key=lambda p: p["ultimo_commit"]["ha_dias"],
                    reverse=True,
                ),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
