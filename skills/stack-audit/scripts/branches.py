#!/usr/bin/env python3
"""Branches que sobraram: já entregues, ou abandonadas.

Duas perguntas diferentes, e confundi-las é o que faz alguém apagar trabalho:

- **Já mesclada** no branch principal: o conteúdo está lá, a branch é só entulho.
  Apagar é seguro, e é a única coisa aqui que se pode sugerir apagar.
- **Parada há muito tempo e NÃO mesclada**: tem commit que não existe em lugar
  nenhum. Isso não é entulho, é trabalho esquecido — e some junto se alguém
  limpar sem olhar.

Só leitura. Nenhum comando aqui apaga nada, e a skill não oferece apagar: quem
decide o que fazer com branch é quem escreveu o código.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time

RAIZ = os.environ.get("PROJECTS_ROOT", "/projects")

# Dias sem commit para uma branch não mesclada contar como esquecida. Trinta é
# depois de qualquer férias e antes de a pessoa ter esquecido o que era.
DIAS_ESQUECIDA = 30


def git(repo: str, *args: str) -> str:
    try:
        r = subprocess.run(
            ["git", "-c", "core.autocrlf=true", "-C", repo, *args],
            capture_output=True, text=True, timeout=30,
            encoding="utf-8", errors="replace",
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return r.stdout.strip() if r.returncode == 0 else ""


def principal(repo: str) -> str | None:
    for palpite in ("origin/main", "origin/master", "main", "master"):
        if git(repo, "rev-parse", "--verify", "--quiet", palpite):
            return palpite
    return None


def _repositorios(raiz: str) -> list[str]:
    """A descoberta recursiva do scan_projects, importada em vez de recopiada.

    Quatro scripts tinham cada um a sua cópia rasa, que só olhava UM nível
    abaixo da raiz. Numa instalação com duas ou mais pastas de código — o
    caminho padrão do instalador — tudo é montado em `/projects/<pasta>/<repo>`,
    e aí os quatro ficavam cegos. Pior que cegos: o de branches devolvia lista
    vazia sem erro nenhum, e o agente respondia com confiança que não havia
    branch esquecida, sem ter olhado. O vigia de segredo fazia o mesmo com uma
    chave de verdade.
    """
    aqui = os.path.dirname(os.path.realpath(__file__))
    irma = os.path.join(aqui, os.pardir, os.pardir, "where-i-left-off", "scripts")
    if irma not in sys.path:
        sys.path.insert(0, irma)
    try:
        from scan_projects import repositorios
    except ImportError:
        # Um nível é melhor que nenhum, se a skill irmã não estiver instalada.
        if os.path.isdir(os.path.join(raiz, ".git")):
            return [raiz]
        try:
            return [e.path for e in sorted(os.scandir(raiz), key=lambda x: x.name)
                    if e.is_dir() and os.path.isdir(os.path.join(e.path, ".git"))]
        except OSError:
            return []
    return repositorios(raiz)

def projetos() -> list[str]:
    return _repositorios(RAIZ)


def main() -> int:
    mescladas, esquecidas = [], []
    agora = time.time()

    for repo in projetos():
        nome = os.path.basename(repo.rstrip("/\\"))
        base = principal(repo)
        if not base:
            continue
        atual = git(repo, "rev-parse", "--abbrev-ref", "HEAD")

        for linha in git(repo, "for-each-ref", "--format=%(refname:short)%09%(committerdate:unix)",
                         "refs/heads/").splitlines():
            partes = linha.split("\t")
            if len(partes) != 2:
                continue
            branch, quando = partes[0], partes[1]
            # Nunca falar do branch principal nem daquele em que a pessoa está:
            # sugerir apagar o que ela tem aberto agora é o conselho mais burro
            # possível.
            if branch in (atual, base.split("/")[-1]):
                continue
            try:
                dias = round((agora - int(quando)) / 86400, 1)
            except ValueError:
                continue

            # `merge-base --is-ancestor` responde a pergunta certa: todo commit
            # desta branch já está na base? Comparar nome ou data não responde.
            ja_esta = subprocess.run(
                ["git", "-C", repo, "merge-base", "--is-ancestor", branch, base],
                capture_output=True, timeout=20,
            ).returncode == 0

            if ja_esta:
                mescladas.append({"projeto": nome, "branch": branch, "dias": dias})
            elif dias >= DIAS_ESQUECIDA:
                adiante = git(repo, "rev-list", "--count", f"{base}..{branch}")
                esquecidas.append({
                    "projeto": nome, "branch": branch, "dias": dias,
                    "commits_so_dela": int(adiante) if adiante.isdigit() else 0,
                    "ultimo_assunto": git(repo, "log", "-1", "--format=%s", branch)[:90],
                })

    mescladas.sort(key=lambda b: -b["dias"])
    esquecidas.sort(key=lambda b: -b["dias"])
    print(json.dumps({
        "ja_mescladas": mescladas[:30],
        "esquecidas_nao_mescladas": esquecidas[:30],
        "aviso": ("as mescladas podem ser apagadas com segurança; as esquecidas têm commit que "
                  "não existe em mais lugar nenhum e sumiriam junto"),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
