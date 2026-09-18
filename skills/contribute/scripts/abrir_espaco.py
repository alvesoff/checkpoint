#!/usr/bin/env python3
"""Uma cópia própria do repositório, num branch novo, para propor mudança.

    abrir_espaco.py <dono/repo> [assunto-curto]

O agente NUNCA escreve na pasta do dono: ela entra no container somente
leitura, imposto pelo Docker, e é isso que torna razoável entregá-la. Esta
skill não muda essa regra — ela clona do remoto para uma área que é do agente,
trabalha lá, e o resultado vira um Pull Request que uma pessoa revisa.

A cópia vem do REMOTO, não do bind somente-leitura, e de propósito: a pasta da
máquina do dono pode ter trabalho não commitado, estar num branch antigo ou ter
divergido. Propor mudança em cima de um estado que só existe no laptop dele
gera um PR que não aplica em lugar nenhum.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys

TRABALHO = "/var/lib/checkpoint-work"
# A trava. Escrito pelo boot a partir do .env de quem instalou, root-owned.
# NUNCA lido do ambiente: um turno do agente pode invocar este script com o
# ambiente que quiser, e aí a lista deixaria de ser trava.
LIBERADOS = "/opt/checkpoint/repos-liberados"
AMBIENTE = "/run/s6/container_environment"

REPO_VALIDO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


def token() -> str:
    """O PAT, do ambiente do processo primeiro e do arquivo depois.

    A mesma ordem do `check_mac.py`, e pelo mesmo motivo: dentro de um turno o
    gateway já carrega a variável, enquanto os arquivos em
    /run/s6/container_environment pertencem ao root e o agente não os lê.
    """
    do_ambiente = os.environ.get("CHECKPOINT_GH_TOKEN", "").strip()
    if do_ambiente:
        return do_ambiente
    try:
        with open(f"{AMBIENTE}/CHECKPOINT_GH_TOKEN", encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return ""


def liberados() -> list[str]:
    try:
        with open(LIBERADOS, encoding="utf-8") as f:
            return [L.strip() for L in f if L.strip()]
    except OSError:
        return []


def git(*args: str, cwd: str | None = None) -> tuple[int, str]:
    """git, com o token fora do argv e fora do .git/config.

    O helper gravado na configuração do clone é um trecho de shell que LÊ a
    variável na hora do push; o valor nunca é escrito em disco nem aparece em
    `ps`. Conferir depois com `git config --get credential.helper` e
    `git remote -v`: nenhum dos dois pode conter o token.
    """
    try:
        r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True,
                           timeout=300, encoding="utf-8", errors="replace")
    except (OSError, subprocess.SubprocessError) as erro:
        return 1, f"{type(erro).__name__}"
    return r.returncode, (r.stdout + r.stderr).strip()


HELPER = ('!f() { echo username=x-access-token; '
          'echo "password=$CHECKPOINT_GH_TOKEN"; }; f')


def ramo_padrao(caminho: str) -> str:
    codigo, saida = git("symbolic-ref", "refs/remotes/origin/HEAD", cwd=caminho)
    if codigo == 0 and "/" in saida:
        return saida.rsplit("/", 1)[1]
    for tentativa in ("main", "master"):
        if git("rev-parse", "--verify", f"origin/{tentativa}", cwd=caminho)[0] == 0:
            return tentativa
    return "main"


def slug(texto: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", texto.lower()).strip("-")
    return (s or "melhoria")[:40]


def main() -> int:
    if len(sys.argv) < 2:
        print(json.dumps({"erro": "uso: abrir_espaco.py <dono/repo> [assunto]"},
                         ensure_ascii=False))
        return 1

    repo = sys.argv[1].strip()
    assunto = slug(sys.argv[2]) if len(sys.argv) > 2 else "melhoria"

    if not REPO_VALIDO.match(repo):
        print(json.dumps({"erro": f"'{repo}' não tem a forma dono/repositorio"},
                         ensure_ascii=False))
        return 1

    permitidos = liberados()
    if not permitidos:
        print(json.dumps({
            "disponivel": False,
            "motivo": "esta instalação não liberou nenhum repositório para Pull Request",
            "como_ligar": ("no .env: CONTRIB_REPOS=dono/repo e CHECKPOINT_GH_TOKEN=<PAT>, "
                           "depois docker compose up -d"),
        }, ensure_ascii=False))
        return 1

    if repo not in permitidos:
        print(json.dumps({
            "disponivel": False,
            "motivo": f"'{repo}' não está na lista liberada desta instalação",
            "liberados": permitidos,
        }, ensure_ascii=False))
        return 1

    if not token():
        print(json.dumps({
            "disponivel": False,
            "motivo": "há repositório liberado, mas nenhum CHECKPOINT_GH_TOKEN configurado",
        }, ensure_ascii=False))
        return 1

    os.makedirs(TRABALHO, exist_ok=True)
    caminho = os.path.join(TRABALHO, repo.replace("/", "__"))
    url = f"https://github.com/{repo}.git"

    if not os.path.isdir(os.path.join(caminho, ".git")):
        codigo, saida = git("clone", "--quiet", url, caminho)
        if codigo != 0:
            print(json.dumps({"erro": "não consegui clonar", "detalhe": saida[-400:]},
                             ensure_ascii=False))
            return 1
        git("config", "credential.helper", HELPER, cwd=caminho)
        git("config", "user.name", "Checkpoint", cwd=caminho)
        git("config", "user.email", "checkpoint@users.noreply.github.com", cwd=caminho)
    else:
        git("config", "credential.helper", HELPER, cwd=caminho)
        if git("fetch", "--quiet", "origin", cwd=caminho)[0] != 0:
            print(json.dumps({"erro": "não consegui atualizar a cópia local"},
                             ensure_ascii=False))
            return 1

    base = ramo_padrao(caminho)
    git("checkout", "--quiet", "-B", base, f"origin/{base}", cwd=caminho)

    # Nunca reaproveitar um branch que já existe: pode ser justamente o que a
    # pessoa está revisando num PR aberto, e reescrever por baixo dela é a pior
    # coisa que esta skill poderia fazer.
    n, ramo = 1, f"checkpoint/{assunto}"
    while git("rev-parse", "--verify", ramo, cwd=caminho)[0] == 0 or \
            git("rev-parse", "--verify", f"origin/{ramo}", cwd=caminho)[0] == 0:
        n += 1
        ramo = f"checkpoint/{assunto}-{n}"
    git("checkout", "--quiet", "-b", ramo, cwd=caminho)

    print(json.dumps({
        "disponivel": True,
        "repo": repo,
        "caminho": caminho,
        "base": base,
        "ramo": ramo,
        "proximo_passo": ("edite os arquivos em `caminho` e depois rode "
                          "abrir_pr.py com o título e o corpo do PR"),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
