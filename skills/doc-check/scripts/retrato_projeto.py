#!/usr/bin/env python3
"""Tudo que é preciso saber de um projeto para documentá-lo sem inventar nada.

    retrato_projeto.py <projeto>

Existe porque documentação escrita de cabeça é pior que documentação ausente:
ela soa verdadeira. O agente não sabe como o projeto sobe — mas o `package.json`
sabe, o `Dockerfile` sabe, o `docker-compose.yml` sabe, e o código diz quais
variáveis ele exige para não morrer na primeira linha.

Este script junta essas evidências. Toda frase que o agente escrever sobre o
projeto tem que apontar para algo daqui.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys

RAIZ = os.environ.get("PROJECTS_ROOT", "/projects")

IGNORAR = {".git", "node_modules", ".venv", "venv", "dist", "build", "__pycache__",
           ".next", "vendor", "target", ".terraform", "coverage"}

ENV_PY = re.compile(r"os\.environ(?:\.get)?[\[(][\"']([A-Z][A-Z0-9_]{2,})[\"']\s*([,)\]])")
ENV_JS = re.compile(r"process\.env\.([A-Z][A-Z0-9_]{2,})\s*(\|\||\?\?)?")
DISPENSADAS = {"NODE_ENV", "PORT", "CI", "HOME", "PATH", "PWD", "USER", "TZ", "LANG",
               "SHELL", "EDITOR", "TERM", "USERPROFILE", "APPDATA", "TMPDIR", "NEXT_RUNTIME"}

ROTA = re.compile(
    r"(?:app|router|api)\.(get|post|put|patch|delete)\s*\(\s*[\"'`]([^\"'`]{1,80})|"
    r"@(?:app|router)\.(get|post|put|patch|delete)\s*\(\s*[\"']([^\"']{1,80})")

# Como o projeto realmente sobe. A ordem é a da confiança: o que está no
# compose vale mais que o que está no README, porque é o que roda.
PISTAS_DE_EXECUCAO = ("docker-compose.yml", "compose.yml", "Dockerfile", "Makefile",
                      "Procfile", "pyproject.toml", "requirements.txt", "package.json")


def git(repo: str, *args: str) -> str:
    try:
        r = subprocess.run(["git", "-c", "core.autocrlf=true", "-C", repo, *args],
                           capture_output=True, text=True, timeout=25,
                           encoding="utf-8", errors="replace")
    except (OSError, subprocess.SubprocessError):
        return ""
    return r.stdout.strip() if r.returncode == 0 else ""


def achar(nome: str) -> str | None:
    direto = os.path.join(RAIZ, nome)
    if os.path.isdir(os.path.join(direto, ".git")):
        return direto
    if os.path.isdir(os.path.join(nome, ".git")):
        return nome
    try:
        for e in os.scandir(RAIZ):
            if e.is_dir() and nome.lower() in e.name.lower() and \
               os.path.isdir(os.path.join(e.path, ".git")):
                return e.path
    except OSError:
        pass
    return None


def ler(caminho: str, teto: int = 400_000) -> str:
    try:
        if os.path.getsize(caminho) > teto:
            return ""
        with open(caminho, encoding="utf-8", errors="ignore") as f:
            return f.read()
    except OSError:
        return ""


def fontes(repo: str, teto: int = 300) -> list[str]:
    achados: list[str] = []
    for raiz, dirs, nomes in os.walk(repo):
        dirs[:] = [d for d in dirs if d not in IGNORAR]
        for n in nomes:
            if n.endswith((".py", ".js", ".ts", ".jsx", ".tsx", ".mjs", ".go", ".rb")):
                achados.append(os.path.join(raiz, n))
                if len(achados) >= teto:
                    return achados
    return achados


def arvore(repo: str, teto: int = 24) -> list[str]:
    """As pastas de primeiro nível que não são ruído — a planta do projeto."""
    try:
        return sorted(e.name + "/" for e in os.scandir(repo)
                      if e.is_dir() and e.name not in IGNORAR and not e.name.startswith("."))[:teto]
    except OSError:
        return []


def main() -> int:
    if len(sys.argv) < 2:
        print(json.dumps({"erro": "uso: retrato_projeto.py <projeto>"}, ensure_ascii=False))
        return 1
    repo = achar(sys.argv[1])
    if not repo:
        print(json.dumps({"erro": f"projeto '{sys.argv[1]}' não encontrado em {RAIZ}"},
                         ensure_ascii=False))
        return 1

    pacote = {}
    if os.path.isfile(os.path.join(repo, "package.json")):
        try:
            pacote = json.loads(ler(os.path.join(repo, "package.json"))) or {}
        except ValueError:
            pacote = {}

    exigidas, rotas = set(), []
    for f in fontes(repo):
        corpo = ler(f)
        for nome, fecha in ENV_PY.findall(corpo):
            if fecha != ",":
                exigidas.add(nome)
        for nome, padrao in ENV_JS.findall(corpo):
            if not padrao:
                exigidas.add(nome)
        rel = os.path.relpath(f, repo).replace("\\", "/")
        for m in ROTA.finditer(corpo):
            metodo = (m.group(1) or m.group(3) or "").upper()
            caminho = m.group(2) or m.group(4) or ""
            if metodo and caminho.startswith("/"):
                rotas.append({"metodo": metodo, "rota": caminho, "arquivo": rel})

    presentes = [n for n in PISTAS_DE_EXECUCAO if os.path.isfile(os.path.join(repo, n))]
    documentos = [n for n in sorted(os.listdir(repo)) if n.lower().endswith(".md")] \
        if os.path.isdir(repo) else []

    # Quem mexeu no projeto, pelo git: é o que diz a quem perguntar em caso de
    # dúvida, e nenhum README adivinha isso sozinho.
    autores = [linha.strip() for linha in
               git(repo, "shortlog", "-sne", "--all", "--no-merges").splitlines()[:5]]

    print(json.dumps({
        "projeto": os.path.basename(repo.rstrip("/\\")),
        "branch": git(repo, "rev-parse", "--abbrev-ref", "HEAD"),
        "ultimo_commit": git(repo, "log", "-1", "--format=%s (%an, %ar)"),
        "commits_total": git(repo, "rev-list", "--count", "HEAD"),
        "quem_mexeu": autores,
        "pastas_de_primeiro_nivel": arvore(repo),
        "documentos_existentes": documentos,
        "arquivos_que_dizem_como_sobe": presentes,
        "nome_no_pacote": pacote.get("name"),
        "descricao_no_pacote": pacote.get("description"),
        "comandos_npm": sorted((pacote.get("scripts") or {}).keys()),
        "dependencias_principais": sorted((pacote.get("dependencies") or {}).keys())[:20],
        "variaveis_exigidas_sem_padrao": sorted(exigidas - DISPENSADAS)[:25],
        "rotas_encontradas": rotas[:25],
        "aviso": ("tudo aqui saiu dos arquivos do projeto; o que não estiver nesta saída, "
                  "pergunte ao dono em vez de supor"),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
