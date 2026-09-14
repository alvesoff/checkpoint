#!/usr/bin/env python3
"""Onde a documentação do projeto já não bate com o código.

    conferir_docs.py [projeto]

Não avalia estilo nem completude — isso é opinião, e opinião sobre texto alheio
vira ruído. Confere só o que é **verificável**: referência que aponta para nada,
comando que não existe mais, variável que o código exige e nenhum documento
menciona.

Documentação errada é pior que documentação ausente: a ausente faz a pessoa
perguntar; a errada faz ela seguir o caminho que não existe mais e concluir que
o projeto está quebrado.

A regra que governa cada filtro aqui: **na dúvida, cale**. A primeira versão
acusava `.env`, `.py` e `.115` de serem arquivos sumidos, porque começavam com
ponto. Um relatório assim ensina o dono a ignorar o relatório inteiro, e aí o
achado verdadeiro morre junto. Melhor achar menos.
"""

from __future__ import annotations

import json
import os
import re
import sys

RAIZ = os.environ.get("PROJECTS_ROOT", "/projects")

IGNORAR = {".git", "node_modules", ".venv", "venv", "dist", "build", "__pycache__",
           ".next", "vendor", "target", ".terraform"}

# Caminho entre crases. Exige `./` ou `../` no começo **e** pelo menos um
# segmento depois: sem isso, `.env` e `.length` entram como "arquivo que sumiu".
CRASE = re.compile(r"`(\.{1,2}/[\w.\-]+(?:/[\w.\-]+)*)`")

# Alvo de link markdown. É evidência mais forte que a crase — ninguém escreve
# `[texto](algo)` sem querer apontar para algo — então aceita caminho sem `./`,
# desde que tenha barra ou extensão de arquivo.
LINK = re.compile(r"\]\((?!https?:|mailto:|#)([\w./\-]{3,80})\)")

EXTENSAO = re.compile(r"\.[A-Za-z0-9]{1,5}$")

NPM_RUN = re.compile(r"npm run ([\w:-]+)")

# Variável de ambiente lida pelo código, com o que vem logo depois: é o que
# distingue exigência de preferência.
ENV_PY = re.compile(r"os\.environ(?:\.get)?[\[(][\"']([A-Z][A-Z0-9_]{2,})[\"']\s*([,)\]])")
ENV_JS = re.compile(r"process\.env\.([A-Z][A-Z0-9_]{2,})\s*(\|\||\?\?)?")

# Nao sao configuracao do projeto: o sistema operacional, o terminal ou o
# framework ja as entregam prontas. Cobrar documentacao delas foi o segundo
# alarme falso do teste - um projeto aparecia com nove "variaveis faltando"
# que eram TMUX, SHELL e USERPROFILE.
DISPENSADAS = {
    "NODE_ENV", "PORT", "CI", "HOME", "PATH", "PWD", "USER", "TZ", "LANG",
    "SHELL", "EDITOR", "VISUAL", "TERM", "TERM_PROGRAM", "COMSPEC", "USERPROFILE",
    "APPDATA", "LOCALAPPDATA", "TMPDIR", "TEMP", "TMP", "TMUX", "ZELLIJ",
    "NODE_OPTIONS", "NEXT_RUNTIME", "VERCEL", "HOSTNAME", "LOGNAME", "SSH_TTY",
}


def projetos(alvo: str | None) -> list[str]:
    if alvo:
        direto = alvo if os.path.isdir(os.path.join(alvo, ".git")) else os.path.join(RAIZ, alvo)
        return [direto] if os.path.isdir(direto) else []
    if os.path.isdir(os.path.join(RAIZ, ".git")):
        return [RAIZ]
    try:
        return [e.path for e in sorted(os.scandir(RAIZ), key=lambda x: x.name)
                if e.is_dir() and os.path.isdir(os.path.join(e.path, ".git"))]
    except OSError:
        return []


def arquivos(repo: str, sufixos: tuple[str, ...], teto: int) -> list[str]:
    achados: list[str] = []
    for raiz, dirs, nomes in os.walk(repo):
        dirs[:] = [d for d in dirs if d not in IGNORAR]
        for n in nomes:
            if n.endswith(sufixos):
                achados.append(os.path.join(raiz, n))
                if len(achados) >= teto:
                    return achados
    return achados


def ler(caminho: str) -> str:
    try:
        if os.path.getsize(caminho) > 1_000_000:
            return ""
        with open(caminho, encoding="utf-8", errors="ignore") as f:
            return f.read()
    except OSError:
        return ""


def citacoes(corpo: str) -> list[str]:
    """Os caminhos que o texto aponta, já filtrados do que só parece caminho."""
    achados = [m.group(1) for m in CRASE.finditer(corpo)]
    for m in LINK.finditer(corpo):
        alvo = m.group(1)
        if "/" in alvo or EXTENSAO.search(alvo):
            achados.append(alvo)
    return achados


def referencias_quebradas(repo: str, texto_docs: dict[str, str]) -> list[dict]:
    absoluto = os.path.abspath(repo)
    quebrados, ja_visto = [], set()
    for doc, corpo in texto_docs.items():
        for citado in citacoes(corpo):
            alvo = citado.split("#")[0].rstrip("/")
            if not alvo or alvo in ja_visto:
                continue
            # Relativo ao documento e relativo à raiz: os dois jeitos são
            # escritos por aí. O normpath é o que faz `../` funcionar — sem ele,
            # um link que sobe um nível vira acusação falsa.
            perto = os.path.normpath(os.path.join(os.path.dirname(doc), alvo))
            daraiz = os.path.normpath(os.path.join(repo, alvo))
            if os.path.exists(perto) or os.path.exists(daraiz):
                continue
            # Apontar para fora do repositório não é documentação podre: é
            # referência a outro projeto, e não sabemos nada sobre ele.
            if not perto.startswith(absoluto) and not daraiz.startswith(absoluto):
                continue
            # O mesmo caminho errado citado em oito documentos é um problema, não
            # oito — e contá-lo oito vezes distorce a ordem do relatório.
            ja_visto.add(alvo)
            quebrados.append({"documento": os.path.relpath(doc, repo).replace("\\", "/"),
                              "aponta_para": citado})
    return quebrados


def variaveis_exigidas(repo: str) -> set[str]:
    """As variáveis que o código exige **sem valor padrão**.

    A distinção é o que separa alarme de ruído: `os.environ.get("X", "algo")`
    tem resposta pronta quando ninguém configurou nada, então não documentá-la
    não impede o projeto de subir. Já `os.environ["X"]` derruba o processo na
    primeira linha, na máquina de quem não escreveu o código.
    """
    exigidas: set[str] = set()
    for fonte in arquivos(repo, (".py", ".js", ".ts", ".jsx", ".tsx", ".mjs"), 300):
        corpo = ler(fonte)
        for nome, fecha in ENV_PY.findall(corpo):
            if fecha != ",":
                exigidas.add(nome)
        for nome, padrao in ENV_JS.findall(corpo):
            if not padrao:
                exigidas.add(nome)
    return exigidas - DISPENSADAS


def conferir(repo: str) -> dict:
    docs = arquivos(repo, (".md",), 60)
    if not docs:
        return {}

    texto_docs = {d: ler(d) for d in docs}
    tudo = "\n".join(texto_docs.values())

    quebrados = referencias_quebradas(repo, texto_docs)

    # `npm run X` citado e ausente do package.json. É o comando que a pessoa
    # copia, cola e vê falhar no primeiro minuto de contato com o projeto.
    sumidos: list[str] = []
    pacote = os.path.join(repo, "package.json")
    if os.path.isfile(pacote):
        try:
            scripts = set((json.loads(ler(pacote)) or {}).get("scripts", {}))
        except ValueError:
            scripts = set()
        if scripts:
            sumidos = sorted({a for a in NPM_RUN.findall(tudo) if a not in scripts})

    # Variável exigida que nenhum documento nem arquivo de exemplo menciona. É o
    # que faz o projeto subir na máquina de quem escreveu e em nenhuma outra.
    documentado = tudo
    for exemplo in (".env.example", ".env.sample", ".env.template", ".env.local.example",
                    "docker-compose.yml", "compose.yml", "Dockerfile"):
        documentado += ler(os.path.join(repo, exemplo))
    sem_doc = sorted(v for v in variaveis_exigidas(repo) if v not in documentado)

    if not (quebrados or sumidos or sem_doc):
        return {}
    return {
        "projeto": os.path.basename(repo.rstrip("/\\")),
        "documentos": len(docs),
        "referencias_quebradas": quebrados[:10],
        "comandos_que_sumiram": sumidos[:10],
        "variaveis_exigidas_sem_documentacao": sem_doc[:15],
    }


def main() -> int:
    lista = projetos(sys.argv[1] if len(sys.argv) > 1 else None)
    if not lista:
        print(json.dumps({"erro": f"nenhum repositório em {RAIZ}"}, ensure_ascii=False))
        return 1

    relatorios = [r for r in (conferir(p) for p in lista) if r]
    # Referência quebrada e comando inexistente valem o dobro: quebram alguém
    # que está seguindo o documento agora. Variável sem menção quebra depois.
    relatorios.sort(key=lambda r: -(len(r["referencias_quebradas"]) * 2
                                    + len(r["comandos_que_sumiram"]) * 2
                                    + len(r["variaveis_exigidas_sem_documentacao"])))
    print(json.dumps({
        "projetos_conferidos": len(lista),
        "com_divergencia": len(relatorios),
        "aviso": ("só o que é verificável: referência que aponta para nada, comando que não "
                  "existe no package.json, variável exigida sem valor padrão e sem menção"),
        "relatorios": relatorios[:15],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
