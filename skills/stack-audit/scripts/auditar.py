#!/usr/bin/env python3
"""Onde os seus próprios projetos se contradizem.

Não é um linter: linter compara o seu código com a regra de outra pessoa. Isto
compara os seus projetos **entre si**, e o padrão é o que a maioria deles já faz.
Com um projeto não há o que dizer; com vinte, a divergência é a informação.

Também varre o que está fora do git atrás de segredo — porque um arquivo não
rastreado com chave dentro é a combinação que vaza sem ninguém notar.
"""

from __future__ import annotations

import collections
import json
import os
import re
import subprocess
import sys

RAIZ = os.environ.get("PROJECTS_ROOT", "/projects")

IGNORAR = {".git", "node_modules", ".venv", "venv", "dist", "build", "__pycache__", ".next", "vendor"}

# Padrões de segredo. Conservadores de propósito: um alarme falso por semana faz
# a pessoa parar de ler os alarmes, e aí o verdadeiro passa junto.
SEGREDOS = {
    "chave AWS": re.compile(r"AKIA[0-9A-Z]{16}"),
    "chave privada": re.compile(r"BEGIN [A-Z ]*PRIVATE KEY"),
    "token/senha": re.compile(
        r"(?i)\b(secret|token|passwd|password|api[_-]?key)\b\s*[=:]\s*[\"']?[A-Za-z0-9_\-]{20,}"),
    "JWT": re.compile(r"eyJ[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]{20,}"),
    "string de conexão": re.compile(r"(?i)(mongodb|postgres(?:ql)?|mysql|redis)://[^\s:@/]+:[^\s@/]+@"),
}

# Arquivo de exemplo não é vazamento: é documentação de qual variável existe.
EXEMPLO = re.compile(r"(?i)(\.example|\.sample|\.template|\.dist)$|(^|/)(example|sample)\.")


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


def nome(caminho: str) -> str:
    return os.path.basename(caminho.rstrip("/\\")) or "projeto"


def dockerfiles(projeto: str) -> list[str]:
    achados = []
    for raiz, dirs, arquivos in os.walk(projeto):
        dirs[:] = [d for d in dirs if d not in IGNORAR]
        if raiz[len(projeto):].count(os.sep) > 2:
            dirs[:] = []
            continue
        achados += [os.path.join(raiz, a) for a in arquivos if a == "Dockerfile" or a.startswith("Dockerfile.")]
    return achados


def auditar_containers(lista: list[str]) -> dict:
    sem_healthcheck, como_root, tag_latest, bases = [], [], [], collections.Counter()
    for projeto in lista:
        for caminho in dockerfiles(projeto):
            try:
                texto = open(caminho, encoding="utf-8", errors="ignore").read()
            except OSError:
                continue
            p = nome(projeto)
            if "HEALTHCHECK" not in texto:
                sem_healthcheck.append(p)
            if not re.search(r"^\s*USER\s+\w", texto, re.M):
                como_root.append(p)
            if re.search(r"^\s*FROM\s+\S+:latest", texto, re.M | re.I):
                tag_latest.append(p)
            for m in re.finditer(r"^\s*FROM\s+([a-z0-9./\-]+):([a-z0-9._\-]+)", texto, re.M | re.I):
                bases[f"{m.group(1)}:{m.group(2)}"] += 1
    return {
        "sem_healthcheck": sorted(set(sem_healthcheck)),
        "rodando_como_root": sorted(set(como_root)),
        "usando_tag_latest": sorted(set(tag_latest)),
        "imagens_base": bases.most_common(8),
    }


def rastreados_e_soltos(projeto: str) -> list[str]:
    """Os arquivos que o git NÃO está versionando ou que estão modificados.

    É onde segredo costuma morar: quem commita um `.env` normalmente já foi
    avisado; quem tem um `credenciais.json` solto ainda não.

    `--ignored` não é detalhe: sem ele, `git status` omite tudo que está no
    `.gitignore` — e `.env` no `.gitignore` é exatamente o lugar mais comum de
    uma chave real. O vigia varria tudo MENOS o caso que ele existe para pegar.
    Só arquivo entra; diretório ignorado o git reporta como uma linha só
    (`node_modules/`), e descer nele traria milhares de arquivos de terceiro.
    """
    try:
        saida = subprocess.run(
            ["git", "-c", "core.autocrlf=true", "-C", projeto,
             "status", "--porcelain", "--ignored=matching"],
            capture_output=True, text=True, timeout=30,
            encoding="utf-8", errors="replace",
        )
    except (OSError, subprocess.SubprocessError):
        return []
    caminhos = []
    for linha in saida.stdout.splitlines():
        if not linha.strip():
            continue
        relativo = linha[3:].strip().strip('"')
        if relativo.endswith("/"):
            continue
        caminhos.append(relativo)
    return caminhos


def varrer_segredos(lista: list[str]) -> list[dict]:
    achados = []
    for projeto in lista:
        for relativo in rastreados_e_soltos(projeto):
            caminho = os.path.join(projeto, relativo)
            if not os.path.isfile(caminho) or EXEMPLO.search(relativo):
                continue
            if any(parte in IGNORAR for parte in caminho.replace("\\", "/").split("/")):
                continue
            try:
                if os.path.getsize(caminho) > 2_000_000:
                    continue
                texto = open(caminho, encoding="utf-8", errors="ignore").read()
            except OSError:
                continue
            tipos = [t for t, rx in SEGREDOS.items() if rx.search(texto)]
            if tipos:
                # O tipo e o caminho, nunca o valor: um segredo repetido numa
                # mensagem de chat é um segredo vazado de novo.
                achados.append({"projeto": nome(projeto), "arquivo": relativo, "tipos": tipos})
    return achados


def main() -> int:
    lista = projetos()
    if not lista:
        print(json.dumps({"erro": f"nenhum repositório git em {RAIZ}",
                          "como_resolver": "aponte CODE_DIR para a pasta que contém seus projetos"},
                         ensure_ascii=False))
        return 1

    containers = auditar_containers(lista)
    segredos = varrer_segredos(lista)
    print(json.dumps({
        "projetos": len(lista),
        "containers": containers,
        "segredos_em_arquivo_solto": segredos,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
