#!/usr/bin/env python3
"""Traz um repositorio publico do GitHub para uma area propria, sem credencial.

    clonar_publico.py <dono/repo | URL do GitHub>

Existe por causa da nuvem. Nesta instalacao pode nao haver `/projects`: o
`plow-agents deploy` manda `{name, line_uid, provider}` e nada mais -- sem
volume, sem bind, sem `CODE_DIR`. Um agente que le repositorio do disco nasce la
sem disco para ler, e a unica saida honesta seria dizer que nao faz nada.

O que este script faz e simples de proposito: clona **anonimamente** e devolve o
`PROJECTS_ROOT` para usar. Nenhuma skill precisa mudar -- o `scan_projects.py` e
o `deps_scan.py` ja leem a raiz dessa variavel de ambiente, entao o clone nao e
uma capacidade nova, e sim um passo de preparo que faz as capacidades existentes
funcionarem sobre um repositorio que nao esta montado.

**Nao usa e nao aceita credencial.** Repositorio publico clona sem token; repo
privado falha na hora, com `GIT_TERMINAL_PROMPT=0` para nao travar pedindo
senha. Isso e deliberado: a imagem desta instalacao e publica, entao qualquer
segredo assado nela e segredo publicado, e um token aceito em conversa acabaria
dentro da home que o proprio agente reescreve.

**Nao e a skill `contribute`.** Aqui so se le. Nao ha ramo, nao ha commit, nao ha
Pull Request, e a area e outra.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys

# Fora de $HERMES_HOME de proposito: aqui entra codigo clonado de fora, que
# ninguem executa. Longe de HERMES_HOME/scripts, que e o unico lugar gravavel de
# onde o runtime roda coisa sozinho.
RAIZ = "/var/lib/checkpoint-work/publico"

# Um repositorio do GitHub, e so isso. A URL vem de quem esta conversando, e
# `git clone` aceita coisas que nao sao uma URL http -- `ext::<comando>` executa
# o que vier depois, e um caminho local le o disco do container. Uma expressao
# fechada e mais curta que auditar o que o git aceita.
ENDERECO = re.compile(r"^(?:https://github\.com/)?([A-Za-z0-9._-]+)/([A-Za-z0-9._-]+?)(?:\.git)?/?$")

MINUTOS = 10


def git(*argumentos: str, cwd: str | None = None) -> tuple[int, str]:
    ambiente = dict(os.environ, GIT_TERMINAL_PROMPT="0", GIT_ASKPASS="/bin/true")
    processo = subprocess.run(["git", *argumentos], cwd=cwd, env=ambiente,
                              capture_output=True, text=True, timeout=MINUTOS * 60)
    return processo.returncode, (processo.stdout + processo.stderr).strip()


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(json.dumps({"erro": "uso: clonar_publico.py <dono/repo | URL do GitHub>"},
                         ensure_ascii=False))
        return 2

    casou = ENDERECO.match(argv[1].strip())
    if not casou:
        print(json.dumps({
            "erro": "nao reconheci isso como repositorio do GitHub",
            "esperado": "dono/repo, ou https://github.com/dono/repo",
        }, ensure_ascii=False))
        return 1

    dono, repo = casou.group(1), casou.group(2)
    caminho = os.path.join(RAIZ, f"{dono}__{repo}")
    os.makedirs(RAIZ, exist_ok=True)

    if os.path.isdir(os.path.join(caminho, ".git")):
        codigo, saida = git("fetch", "--quiet", "--prune", "origin", cwd=caminho)
        if codigo != 0:
            print(json.dumps({"erro": "ja tinha uma copia, mas nao consegui atualizar",
                              "detalhe": saida[-400:]}, ensure_ascii=False))
            return 1
        git("reset", "--quiet", "--hard", "@{upstream}", cwd=caminho)
        novo = False
    else:
        codigo, saida = git("clone", "--quiet", f"https://github.com/{dono}/{repo}.git", caminho)
        if codigo != 0:
            # A mensagem do git distingue os dois casos que importam, e a
            # diferenca muda o que dizer: repositorio privado nao vira publico
            # por insistencia, e nome errado vira.
            privado = "Authentication failed" in saida or "could not read Username" in saida
            print(json.dumps({
                "erro": "nao consegui clonar",
                "motivo": ("o repositorio e privado ou nao existe -- daqui so da para ler "
                           "repositorio publico, sem credencial nenhuma") if privado
                          else "o GitHub recusou o clone",
                "detalhe": saida[-400:],
            }, ensure_ascii=False))
            return 1
        novo = True

    print(json.dumps({
        "pronto": True,
        "repo": f"{dono}/{repo}",
        "caminho": caminho,
        "novo": novo,
        "projects_root": RAIZ,
        "como_usar": (f"exporte PROJECTS_ROOT={RAIZ} e rode as skills de sempre "
                      "-- scan_projects.py, deps_scan.py, vulneraveis.py, auditar.py"),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
