#!/usr/bin/env python3
"""O que você usa, onde usa, e o que já está desatualizado ou abandonado.

Lê os manifestos dos projetos montados e cruza com os registros públicos (npm e
PyPI). Só stdlib.

O que separa isto de um `npm outdated`: o `npm outdated` responde por projeto, e
a pergunta que importa quando se tem vinte repositórios é **em quantos deles
isso me atinge**. Um pacote atrasado em nove projetos e um atrasado em um não
são o mesmo problema, e a ordem de urgência sai daí.

Rede: uma consulta por pacote distinto, com cache em disco. Sem cache, uma
varredura de 133 pacotes a cada tique do monitor seria abuso do registro e
demoraria o suficiente para estourar o turno do agente.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

RAIZ = os.environ.get("PROJECTS_ROOT", "/projects")
CACHE = os.path.join(os.environ.get("HERMES_HOME", "/var/lib/hermes"), "deps-cache.json")

# Quanto tempo a resposta do registro vale. Um dia: versão nova não sai de hora
# em hora, e o monitor roda a cada hora.
CACHE_HORAS = 24

# Pastas que nunca contêm manifesto do projeto — só dependências de terceiros,
# que fariam a varredura encontrar milhares de pacotes que não são seus.
IGNORAR = {".git", "node_modules", ".venv", "venv", "dist", "build", "__pycache__", ".next", "vendor"}


def carregar_cache() -> dict:
    try:
        with open(CACHE, encoding="utf-8") as f:
            dados = json.load(f)
    except (OSError, ValueError):
        return {}
    limite = time.time() - CACHE_HORAS * 3600
    return {k: v for k, v in dados.items() if v.get("em", 0) > limite}


def salvar_cache(cache: dict) -> None:
    try:
        tmp = CACHE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cache, f)
        os.replace(tmp, CACHE)
    except OSError:
        # Cache é otimização, não requisito: uma home somente-leitura não pode
        # derrubar a varredura.
        pass


def projetos(raiz: str) -> list[str]:
    if os.path.isdir(os.path.join(raiz, ".git")):
        return [raiz]
    try:
        return [e.path for e in sorted(os.scandir(raiz), key=lambda x: x.name) if e.is_dir()]
    except OSError:
        return []


def manifestos(projeto: str) -> list[str]:
    """Os manifestos deste projeto, no máximo dois níveis abaixo da raiz dele.

    Dois níveis porque monorepo com `backend/` e `frontend/` é comum; mais que
    isso começa a varrer dependência de dependência.
    """
    achados = []
    for raiz, dirs, arquivos in os.walk(projeto):
        dirs[:] = [d for d in dirs if d not in IGNORAR]
        if raiz[len(projeto):].count(os.sep) > 2:
            dirs[:] = []
            continue
        for nome in arquivos:
            if nome == "package.json" or re.match(r"^requirements.*\.txt$", nome):
                achados.append(os.path.join(raiz, nome))
    return achados


def versao_limpa(spec: str) -> str:
    """A versão dentro de um spec do tipo `^5.0.0` ou `>=2.4,<3`."""
    m = re.search(r"(\d+(?:\.\d+)*)", spec or "")
    return m.group(1) if m else ""


def ler_manifestos(raiz: str) -> tuple[dict, dict]:
    """{ (ecossistema, pacote): {projeto: versao} } e a contagem de projetos."""
    usos: dict[tuple[str, str], dict[str, str]] = {}
    vistos = set()
    for projeto in projetos(raiz):
        nome_proj = os.path.basename(projeto.rstrip("/\\")) or "projeto"
        for caminho in manifestos(projeto):
            try:
                texto = open(caminho, encoding="utf-8", errors="ignore").read()
            except OSError:
                continue
            if caminho.endswith("package.json"):
                try:
                    dados = json.loads(texto)
                except ValueError:
                    continue
                for secao in ("dependencies", "devDependencies"):
                    for pacote, spec in (dados.get(secao) or {}).items():
                        if isinstance(spec, str) and not spec.startswith(("file:", "link:", "workspace:")):
                            usos.setdefault(("npm", pacote), {}).setdefault(nome_proj, versao_limpa(spec))
            else:
                for linha in texto.splitlines():
                    linha = linha.strip()
                    if not linha or linha.startswith(("#", "-")):
                        continue
                    m = re.match(r"^([A-Za-z0-9_.\-]+)\s*([=<>~!]=?.*)?$", linha)
                    if m:
                        usos.setdefault(("pypi", m.group(1).lower()), {}).setdefault(
                            nome_proj, versao_limpa(m.group(2) or "")
                        )
            vistos.add(nome_proj)
    return usos, {"projetos": len(vistos)}


def consultar(eco: str, pacote: str, cache: dict) -> dict:
    chave = f"{eco}:{pacote}"
    if chave in cache:
        return cache[chave]
    url = (
        f"https://registry.npmjs.org/{urllib.parse.quote(pacote, safe='@/')}"
        if eco == "npm"
        else f"https://pypi.org/pypi/{urllib.parse.quote(pacote)}/json"
    )
    registro = {"em": time.time(), "ultima": "", "abandonado": ""}
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            dados = json.load(r)
        if eco == "npm":
            registro["ultima"] = dados.get("dist-tags", {}).get("latest", "")
            versao = dados.get("versions", {}).get(registro["ultima"], {})
            registro["abandonado"] = str(versao.get("deprecated") or "")[:200]
        else:
            info = dados.get("info", {})
            registro["ultima"] = info.get("version", "")
            if (info.get("yanked") or "").strip() if isinstance(info.get("yanked"), str) else info.get("yanked"):
                registro["abandonado"] = "versão retirada do PyPI"
    except (urllib.error.URLError, urllib.error.HTTPError, ValueError, OSError):
        # Pacote privado, nome interno ou rede fora: não é erro nosso, é um
        # pacote sobre o qual não temos o que dizer.
        registro["erro"] = True
    cache[chave] = registro
    return registro


def major(v: str) -> int | None:
    try:
        return int(v.split(".")[0])
    except (ValueError, AttributeError, IndexError):
        return None


def main() -> int:
    if not os.path.isdir(RAIZ):
        print(json.dumps({"erro": f"{RAIZ} não existe dentro do container",
                          "como_resolver": "monte sua pasta de código em /projects"}, ensure_ascii=False))
        return 1

    usos, resumo = ler_manifestos(RAIZ)
    if not usos:
        print(json.dumps({"erro": "nenhum manifesto encontrado (package.json ou requirements.txt)",
                          "como_resolver": "confira se CODE_DIR aponta para a pasta que contém seus projetos"},
                         ensure_ascii=False))
        return 1

    cache = carregar_cache()
    achados = []
    # Do mais espalhado para o menos: é a ordem da urgência real, e também a
    # ordem em que vale gastar rede se a varredura for interrompida.
    for (eco, pacote), onde in sorted(usos.items(), key=lambda kv: -len(kv[1])):
        registro = consultar(eco, pacote, cache)
        if registro.get("erro") or not registro["ultima"]:
            continue
        m_atual = major(registro["ultima"])
        atrasados = {
            proj: v for proj, v in onde.items()
            if v and m_atual is not None and (major(v) or m_atual) < m_atual
        }
        if registro["abandonado"]:
            achados.append({"ecossistema": eco, "pacote": pacote, "tipo": "abandonado",
                            "detalhe": registro["abandonado"], "projetos": sorted(onde),
                            "quantos": len(onde)})
        elif atrasados:
            achados.append({"ecossistema": eco, "pacote": pacote, "tipo": "majors_atras",
                            "voce_usa": sorted(set(atrasados.values()))[0], "atual": registro["ultima"],
                            "projetos": sorted(atrasados), "quantos": len(atrasados)})
    salvar_cache(cache)

    achados.sort(key=lambda a: -a["quantos"])
    print(json.dumps({
        "projetos_lidos": resumo["projetos"],
        "pacotes_distintos": len(usos),
        "com_problema": len(achados),
        "achados": achados[:40],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
