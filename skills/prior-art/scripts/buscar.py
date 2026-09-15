#!/usr/bin/env python3
"""Como o dono já resolveu isso antes, nos projetos dele.

A pergunta que esta skill responde é "como eu fiz isso da última vez?" — e a
resposta não está na memória de ninguém, está no código que ele mesmo escreveu.
Vinte e cinco repositórios são grandes demais para lembrar e pequenos demais
para procurar no Google.

Por que é diferente de um `grep`: o resultado vem agrupado por projeto e
ordenado pelo que foi tocado mais recentemente, porque num conjunto de projetos
a versão mais nova de um padrão costuma ser a que já corrigiu os problemas das
anteriores. Um `grep` devolve trinta ocorrências em ordem alfabética; isto
devolve "três projetos fazem isso, o mais recente é este".
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

RAIZ = os.environ.get("PROJECTS_ROOT", "/projects")

# Pastas que nunca contêm código do dono. Sem isto a busca devolve a
# implementação de um pacote de terceiro como se fosse precedente dele.
EXCLUIR = ["node_modules", ".venv", "venv", "dist", "build", "__pycache__",
           ".next", "vendor", ".cache", ".git", "target", "coverage"]

MAX_POR_PROJETO = 4
MAX_PROJETOS = 8


def repos() -> list[str]:
    achados = []
    for atual, pastas, _ in os.walk(RAIZ):
        pastas[:] = [p for p in pastas if p not in EXCLUIR]
        if ".git" in os.listdir(atual) if os.path.isdir(atual) else False:
            achados.append(atual)
            pastas[:] = []
        if atual.count(os.sep) - RAIZ.count(os.sep) > 3:
            pastas[:] = []
    return achados


def _repo_de(caminho: str) -> str:
    """O repositorio git que contem este arquivo, subindo ate a raiz montada."""
    atual = os.path.dirname(os.path.abspath(caminho))
    limite = os.path.abspath(RAIZ)
    while atual.startswith(limite) and len(atual) >= len(limite):
        if os.path.isdir(os.path.join(atual, ".git")):
            return atual
        pai = os.path.dirname(atual)
        if pai == atual:
            break
        atual = pai
    return ""


def tocado_em(repo: str) -> float:
    """Quando o projeto teve o último commit. Ordena o que é precedente bom."""
    try:
        r = subprocess.run(["git", "-C", repo, "log", "-1", "--format=%ct"],
                           capture_output=True, text=True, timeout=15)
        return float(r.stdout.strip() or 0)
    except (OSError, subprocess.SubprocessError, ValueError):
        return 0.0


def main() -> int:
    if len(sys.argv) < 2:
        print(json.dumps({"erro": "uso: buscar.py <o que procurar> [extensao]"}, ensure_ascii=False))
        return 1

    alvo = sys.argv[1]
    extensao = sys.argv[2] if len(sys.argv) > 2 else ""

    if not os.path.isdir(RAIZ):
        print(json.dumps({"erro": f"{RAIZ} não existe dentro do container"}, ensure_ascii=False))
        return 1

    comando = ["rg", "--json", "-i", "--max-count", str(MAX_POR_PROJETO), "-C", "2"]
    for e in EXCLUIR:
        comando += ["--glob", f"!**/{e}/**"]
    if extensao:
        comando += ["--glob", f"*.{extensao.lstrip('.')}"]
    comando += ["--", alvo, RAIZ]

    try:
        r = subprocess.run(comando, capture_output=True, text=True, timeout=120,
                           encoding="utf-8", errors="replace")
    except FileNotFoundError:
        print(json.dumps({"erro": "ripgrep (rg) não está disponível nesta imagem"}, ensure_ascii=False))
        return 1
    except (OSError, subprocess.SubprocessError) as e:
        print(json.dumps({"erro": f"a busca falhou: {type(e).__name__}"}, ensure_ascii=False))
        return 1

    por_projeto: dict[str, list[dict]] = {}
    raiz_do_projeto: dict[str, str] = {}
    for linha in r.stdout.splitlines():
        try:
            evento = json.loads(linha)
        except ValueError:
            continue
        if evento.get("type") != "match":
            continue
        dados = evento["data"]
        caminho = dados["path"]["text"]
        relativo = os.path.relpath(caminho, RAIZ)
        # O repositorio que contem o arquivo, nao o primeiro segmento do
        # caminho: com mais de uma pasta de codigo montada o primeiro segmento
        # e a PASTA, e ai todos os achados caem num balde so e a ordenacao por
        # recencia consulta o git log de um diretorio que nao e repositorio.
        repo = _repo_de(caminho)
        projeto = os.path.basename(repo) if repo else relativo.replace("\\", "/").split("/")[0]
        raiz_do_projeto[projeto] = repo or os.path.join(RAIZ, projeto)
        texto = (dados["lines"]["text"] or "").strip()
        por_projeto.setdefault(projeto, []).append({
            "arquivo": relativo,
            "linha": dados["line_number"],
            # Cortado: o valor de uma linha inteira de minificado não ajuda
            # ninguém e enche a mensagem.
            "trecho": texto[:200],
        })

    # `--max-count` do rg corta por ARQUIVO. Sem este corte, um projeto com
    # cinquenta arquivos devolvia cinquenta trechos e a saida declarava um teto
    # que nao existia -- o agente confiava no numero e mandava parede de texto.
    por_projeto = {p: o[:MAX_POR_PROJETO] for p, o in por_projeto.items()}

    ordenados = sorted(
        por_projeto.items(),
        key=lambda kv: -tocado_em(raiz_do_projeto.get(kv[0], os.path.join(RAIZ, kv[0]))),
    )[:MAX_PROJETOS]

    print(json.dumps({
        "procurado": alvo,
        "projetos_com_precedente": len(por_projeto),
        "achados": [{"projeto": p, "ocorrencias": o} for p, o in ordenados],
        # Honestidade sobre o alcance: sem isto o agente afirma "não existe
        # precedente" quando na verdade a busca não olhou tudo.
        "limites": f"até {MAX_POR_PROJETO} trechos por projeto e {MAX_PROJETOS} projetos, "
                   f"do mais recentemente commitado para o mais antigo",
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
