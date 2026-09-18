#!/usr/bin/env python3
"""Esta instalação tem código para ler, e se não tem, por quê.

    onde_estou.py

Existe porque "nenhum projeto encontrado" tem duas causas opostas, e o conselho
certo para uma é inútil para a outra:

  * **Numa instalação local**, a pasta está montada e vazia, ou apontada um
    nível acima. Aí "confira o CODE_DIR" é exatamente o que resolve.
  * **Na nuvem da Plow**, não existe disco do dono para montar, e mandar alguém
    conferir o CODE_DIR é mandar mexer numa coisa que não existe. Quem recebe
    esse conselho conclui que o agente está quebrado.

O sinal é limpo: `/projects` **não existe** na imagem. Ele só aparece quando o
compose monta a pasta, então diretório ausente e diretório vazio são estados
diferentes e querem respostas diferentes.
"""

from __future__ import annotations

import json
import os
import sys

RAIZ = os.environ.get("PROJECTS_ROOT", "/projects")


def repositorios(raiz: str) -> int:
    """Quantos repositórios git existem até dois níveis abaixo da raiz."""
    total = 0
    for base, pastas, _ in os.walk(raiz):
        profundidade = base[len(raiz):].count(os.sep)
        if profundidade >= 2:
            pastas[:] = []
            continue
        if ".git" in pastas:
            total += 1
            pastas[:] = [p for p in pastas if p != ".git"]
    return total


def main() -> int:
    existe = os.path.isdir(RAIZ)
    quantos = repositorios(RAIZ) if existe else 0

    if not existe:
        saida = {
            "modo": "sem pasta de código",
            "tem_codigo": False,
            "por_que": (f"{RAIZ} não existe nesta instalação — nada foi montado. "
                        "É o que acontece quando o agente roda na nuvem da Plow, "
                        "onde não há disco do dono."),
            "o_que_funciona": ["conversar", "lista de demandas", "navegador",
                               "checar a própria versão"],
            "o_que_nao_funciona": ["onde parei", "radar de dependências",
                                   "auditoria entre projetos", "documentação vs código",
                                   "como fiz da última vez", "resumo de manhã e de noite"],
            "como_dar_codigo": [
                "mandar a URL de um repositório PÚBLICO do GitHub: o `clonar_publico.py` "
                "traz uma cópia sem credencial nenhuma, e as skills de sempre funcionam "
                "sobre ela — é o caminho que serve aqui mesmo, agora",
                "para o código privado da própria máquina, rodar na própria máquina com "
                "`docker compose up -d`, que monta a pasta somente leitura",
            ],
        }
    elif quantos == 0:
        saida = {
            "modo": "pasta montada e vazia",
            "tem_codigo": False,
            "por_que": f"{RAIZ} existe mas não tem nenhum repositório git até dois níveis abaixo",
            "como_resolver": ("CODE_DIR provavelmente aponta um nível acima ou abaixo do lugar "
                              "certo. Ele deve apontar para a pasta que CONTÉM os projetos, "
                              "não para um projeto e não para a raiz do disco."),
        }
    else:
        saida = {"modo": "local", "tem_codigo": True, "repositorios": quantos, "raiz": RAIZ}

    print(json.dumps(saida, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
