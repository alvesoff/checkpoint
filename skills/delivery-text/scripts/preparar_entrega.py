#!/usr/bin/env python3
"""Os fatos de uma entrega, para o agente escrever o texto dela.

Uso:
    preparar_entrega.py <projeto> [base]

`<projeto>` é o nome da pasta dentro da raiz montada. `base` é o ponto de
comparação: sem ele, o upstream do branch; sem upstream, o branch principal do
repositório.

Este script não escreve uma linha de texto de entrega — ele devolve o material.
A separação é o desenho: texto bonito e errado vai para o histórico do
repositório e alguém confia nele depois. Toda frase que o agente escrever precisa
apontar para algo daqui.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys

RAIZ = os.environ.get("PROJECTS_ROOT", "/projects")

# Arquivo que muda em toda entrega e não diz nada sobre ela. Contá-los como
# "arquivos alterados" infla o número e esconde o que interessa.
RUIDO = re.compile(r"(package-lock\.json|yarn\.lock|pnpm-lock\.yaml|poetry\.lock|\.min\.(js|css)$)")

# O que mexe na superfície pública — o que o revisor procura primeiro e o que
# quebra quem depende do projeto.
SUPERFICIE = {
    "rota HTTP": re.compile(r"^\+.*(@(app|router)\.(get|post|put|patch|delete)|app\.(get|post|put|patch|delete)\(|router\.(get|post|put|patch|delete)\()", re.M),
    "export público": re.compile(r"^\+\s*export\s+(default\s+)?(async\s+)?(function|class|const)\s+(\w+)", re.M),
    "variável de ambiente": re.compile(r"^\+.*(process\.env\.(\w+)|os\.environ(?:\.get)?[\[(][\"'](\w+))", re.M),
    "migração de banco": re.compile(r"^\+\+\+ b/.*(migrations?|alembic|prisma/migrations)/", re.M),
    "dependência nova": re.compile(r"^\+\s*[\"']([\w@/\-\.]+)[\"']\s*:\s*[\"'][\^~>=<\d]", re.M),
}


def git(repo: str, *args: str) -> str:
    try:
        r = subprocess.run(
            ["git", "-c", "core.autocrlf=true", "-C", repo, *args],
            capture_output=True, text=True, timeout=60,
            # A codificação da plataforma é cp1252 no Windows, e um diff com
            # acento derruba a leitura inteira. O git fala UTF-8.
            encoding="utf-8", errors="replace",
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return r.stdout.strip() if r.returncode == 0 else ""


def achar_projeto(nome: str) -> str | None:
    """Aceita o nome da pasta, o caminho, ou a raiz quando ela é o repositório."""
    if os.path.isdir(os.path.join(nome, ".git")):
        return nome
    direto = os.path.join(RAIZ, nome)
    if os.path.isdir(os.path.join(direto, ".git")):
        return direto
    # Um nível a mais, porque a instalação pode montar várias pastas de código.
    for raiz, dirs, _ in os.walk(RAIZ):
        if raiz.count(os.sep) - RAIZ.count(os.sep) > 2:
            dirs[:] = []
            continue
        if os.path.basename(raiz) == nome and os.path.isdir(os.path.join(raiz, ".git")):
            return raiz
    return None


def base_de_comparacao(repo: str, pedida: str | None) -> str | None:
    if pedida:
        return pedida
    upstream = git(repo, "rev-parse", "--abbrev-ref", "@{upstream}")
    if upstream:
        return upstream
    # Sem upstream, o branch principal do próprio repositório — e não um nome
    # chutado: `main` não existe em todo repositório.
    for palpite in ("origin/main", "origin/master", "main", "master"):
        if git(repo, "rev-parse", "--verify", "--quiet", palpite):
            return palpite
    return None


def superficie(diff: str) -> dict:
    achados: dict[str, list[str]] = {}
    for rotulo, padrao in SUPERFICIE.items():
        vistos = []
        for m in padrao.finditer(diff):
            trecho = next((g for g in m.groups()[::-1] if g), m.group(0)).strip()
            if trecho not in vistos:
                vistos.append(trecho)
        if vistos:
            achados[rotulo] = vistos[:12]
    return achados


def incoerencias(repo: str, arquivos: list[str], diff: str) -> list[str]:
    """O que um revisor humano bom apontaria e um gerador de PR não vê.

    Cada item aqui é uma pergunta que o autor consegue responder em dez segundos
    e que, sem ser feita, vira incidente depois.
    """
    avisos = []

    # Variável de ambiente nova sem entrada no arquivo de exemplo: quem clonar o
    # projeto depois vai descobrir na primeira falha em produção.
    novas_env = set(re.findall(r"^\+.*(?:process\.env\.(\w+)|os\.environ(?:\.get)?[\[(][\"'](\w+))", diff, re.M))
    nomes_env = {a or b for a, b in novas_env}
    if nomes_env:
        exemplos = ""
        for candidato in (".env.example", ".env.sample", ".env.template"):
            caminho = os.path.join(repo, candidato)
            if os.path.isfile(caminho):
                try:
                    exemplos += open(caminho, encoding="utf-8", errors="ignore").read()
                except OSError:
                    pass
        faltando = sorted(n for n in nomes_env if n and n not in exemplos)
        if faltando:
            avisos.append(f"variável de ambiente usada e ausente do arquivo de exemplo: {', '.join(faltando[:6])}")

    # Migração sem rollback: reverter vira trabalho manual às três da manhã.
    migracoes = [a for a in arquivos if re.search(r"(migrations?|alembic|prisma/migrations)/", a)]
    if migracoes and not re.search(r"(down|rollback|revert)", " ".join(migracoes), re.I):
        if not re.search(r"^\+.*(def downgrade|-- *[Dd]own|async function down)", diff, re.M):
            avisos.append("migração de banco sem caminho de rollback visível")

    # Assunto misturado: três áreas do projeto no mesmo diff. Descrição honesta
    # de entrega bagunçada é impossível — melhor sugerir dividir.
    topo = {a.split("/")[0] for a in arquivos if "/" in a and not RUIDO.search(a)}
    if len(topo) >= 4:
        avisos.append(f"a entrega toca {len(topo)} áreas diferentes ({', '.join(sorted(topo)[:5])}) — considere dividir em commits separados")

    # Código novo sem teste algum tocado.
    tem_teste = any(re.search(r"(^|/)(tests?|__tests__|spec)/|\.(test|spec)\.[jt]sx?$|_test\.py$|test_.*\.py$", a) for a in arquivos)
    codigo = [a for a in arquivos if re.search(r"\.(py|[jt]sx?|go|rb|java|cs|php)$", a) and not RUIDO.search(a)]
    if codigo and not tem_teste:
        avisos.append(f"{len(codigo)} arquivos de código alterados e nenhum teste tocado")

    return avisos


def main() -> int:
    if len(sys.argv) < 2:
        print(json.dumps({"erro": "uso: preparar_entrega.py <projeto> [base]"}, ensure_ascii=False))
        return 1

    repo = achar_projeto(sys.argv[1])
    if not repo:
        print(json.dumps({
            "erro": f"projeto '{sys.argv[1]}' não encontrado em {RAIZ}",
            "como_resolver": "use o nome da pasta como ela aparece na lista de projetos",
        }, ensure_ascii=False))
        return 1

    base = base_de_comparacao(repo, sys.argv[2] if len(sys.argv) > 2 else None)
    branch = git(repo, "rev-parse", "--abbrev-ref", "HEAD")

    # Duas entregas possíveis, e a pergunta é diferente em cada uma:
    # o que ainda não foi salvo (vira mensagem de commit), e o que o branch
    # acumulou além da base (vira descrição de PR).
    sujo = [l[3:] for l in git(repo, "status", "--porcelain").splitlines() if l.strip()]
    diff_local = git(repo, "diff", "HEAD")
    commits = []
    diff_branch = ""
    if base:
        for linha in git(repo, "log", f"{base}..HEAD", "--format=%h%x1f%s%x1f%an").splitlines():
            partes = linha.split("\x1f")
            if len(partes) >= 2:
                commits.append({"sha": partes[0], "assunto": partes[1], "autor": partes[2] if len(partes) > 2 else ""})
        diff_branch = git(repo, "diff", f"{base}...HEAD")

    diff = diff_branch or diff_local
    if diff_branch:
        arquivos = [a for a in git(repo, "diff", "--name-only", f"{base}...HEAD").splitlines() if a.strip()]
    else:
        # Arquivo NUNCA rastreado não aparece em `git diff` — e é o caso mais
        # comum de trabalho não salvo: a pessoa criou o arquivo e nunca deu
        # `git add`. Ficar só no diff faria a entrega parecer vazia justamente
        # quando há mais a dizer sobre ela.
        rastreados = [a for a in git(repo, "diff", "--name-only", "HEAD").splitlines() if a.strip()]
        novos = [l[3:].strip().strip('"') for l in git(repo, "status", "--porcelain").splitlines()
                 if l.startswith("??")]
        arquivos = rastreados + [n for n in novos if n not in rastreados]
        # O conteúdo do arquivo novo também não está no diff; sem ele a detecção
        # de superfície pública e de incoerência não enxerga nada.
        for novo in novos[:40]:
            caminho = os.path.join(repo, novo)
            if os.path.isfile(caminho) and os.path.getsize(caminho) < 400_000:
                try:
                    corpo = open(caminho, encoding="utf-8", errors="ignore").read()
                except OSError:
                    continue
                nl = chr(10)
                cabecalho = nl + "+++ b/" + novo + nl
                corpo_diff = "".join("+" + l + nl for l in corpo.splitlines()[:600])
                diff += cabecalho + corpo_diff
    relevantes = [a for a in arquivos if not RUIDO.search(a)]

    print(json.dumps({
        "projeto": os.path.basename(repo.rstrip("/\\")),
        "branch": branch,
        "base": base,
        "tem_base": bool(base),
        "commits_alem_da_base": commits,
        "arquivos": relevantes[:60],
        "arquivos_ignorados_por_ruido": len(arquivos) - len(relevantes),
        "arquivos_nao_salvos": len(sujo),
        "superficie_publica": superficie(diff),
        "pontos_a_confirmar": incoerencias(repo, relevantes, diff),
        "diff_vazio": not diff.strip(),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
