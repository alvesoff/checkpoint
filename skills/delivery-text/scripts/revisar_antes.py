#!/usr/bin/env python3
"""O que está prestes a entrar no git e não deveria.

    revisar_antes.py <projeto>

Roda contra o que ainda NÃO foi commitado — working tree e índice. É o único
momento em que o estrago ainda é grátis: depois do push, um segredo commitado
continua no histórico mesmo apagado no commit seguinte, e a chave tem que ser
rotacionada de verdade.

Não é linter e não opina sobre estilo. Três perguntas, todas com resposta
binária e verificável no diff:

  1. tem segredo aí dentro?
  2. tem arquivo que nunca deveria ser versionado?
  3. tem sobra de depuração que ninguém quis mandar?

Nunca imprime o valor do segredo. Um segredo repetido numa mensagem de chat é um
segredo vazado outra vez, e o iMessage guarda aquilo para sempre.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys

RAIZ = os.environ.get("PROJECTS_ROOT", "/projects")

# Arquivo cujo nome já é o problema, independente do conteúdo. `.env.example` e
# amigos ficam fora: são documentação de quais variáveis existem.
NOME_PROIBIDO = re.compile(
    r"(^|/)(\.env(\.local|\.production|\.development)?|"
    r"credentials?\.json|service-account.*\.json|"
    r"id_rsa|id_ed25519|.*\.pem|.*\.p12|.*\.pfx|.*\.keystore|"
    r".*\.sql(\.gz)?|.*\.dump)$", re.I)
# Duas listas, porque sao duas perguntas diferentes e uma constante so
# respondia as duas. NOME_LIBERADO diz "este arquivo PODE entrar no commit":
# schema.sql e migrations/ sao codigo legitimo, ainda que casem com a regra de
# nome arriscado. CONTEUDO_LIBERADO diz "nao vale varrer o conteudo", e ai so
# entra arquivo de exemplo, que existe para mostrar o formato da variavel.
NOME_LIBERADO = re.compile(r"\.(example|sample|template|dist)$|schema\.sql$|migrations?/", re.I)
# Uma migration com `CREATE USER ... PASSWORD` e o unico achado do produto que
# vaza credencial de producao, e era exatamente o que ficava de fora.
CONTEUDO_LIBERADO = re.compile(r"\.(example|sample|template|dist)$", re.I)

# Segredo no conteúdo das linhas ADICIONADAS. Só linha `+`: o que já estava lá
# não é decisão deste commit, e acusá-lo transforma toda revisão em ruído.
SEGREDO = [
    ("chave da AWS", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("token do GitHub", re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}")),
    ("chave da OpenAI/Anthropic", re.compile(r"sk-(ant-)?[A-Za-z0-9_\-]{20,}")),
    ("chave privada", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("token do Slack", re.compile(r"xox[baprs]-[A-Za-z0-9\-]{10,}")),
    ("string de conexão com senha", re.compile(
        r"(postgres|postgresql|mysql|mongodb(\+srv)?|redis|amqp)://[^\s:@/]+:[^\s:@/]+@")),
    ("senha ou segredo literal", re.compile(
        r"(?i)\b(password|passwd|secret|api[_-]?key|token)\b\s*[:=]\s*[\"'][^\"'\s$<{]{8,}[\"']")),
    # SQL nao usa `=` para isto: `CREATE USER app WITH PASSWORD 'x'` e
    # `IDENTIFIED BY 'x'` escapam do padrao acima, e migration e justamente
    # onde credencial de producao aparece escrita por extenso. Placeholder
    # obvio fica de fora -- alarme falso ensina a ignorar o alarme verdadeiro.
    ("credencial em SQL", re.compile(
        r"""(?i)\b(?:password|identified\s+by)\s+['"]"""
        r"""(?!(?:password|changeme|senha|placeholder|your[_-]?\w+|x{3,})['"])"""
        r"""[^'"\s$<{]{8,}['"]""")),
]

# Sobra de depuração. Cada uma some sozinha até o dia em que vai para produção.
DEPURACAO = [
    ("console.log", re.compile(r"^\+\s*console\.(log|debug|dir)\s*\(", re.M)),
    ("debugger", re.compile(r"^\+\s*debugger\s*;?\s*$", re.M)),
    ("breakpoint do Python", re.compile(r"^\+\s*(breakpoint\(\)|import\s+pdb|pdb\.set_trace)", re.M)),
    ("teste isolado (.only)", re.compile(r"^\+\s*(describe|it|test)\.only\s*\(", re.M)),
    ("print de depuração", re.compile(r"^\+\s*print\s*\(\s*[\"']?(debug|aqui|teste|xxx|\d)", re.I | re.M)),
]

# Falso positivo clássico: a linha que o próprio código usa para dizer que NÃO
# tem segredo — placeholder, exemplo, variável interpolada.
PLACEHOLDER = re.compile(
    r"(?i)(xxx+|your[_-]?|placeholder|example|changeme|<[^>]+>|\$\{|process\.env|os\.environ|"
    r"\*{4,}|dummy|fake|sample)")


def git(repo: str, *args: str) -> str:
    try:
        r = subprocess.run(
            ["git", "-c", "core.autocrlf=true", "-C", repo, *args],
            capture_output=True, text=True, timeout=40,
            encoding="utf-8", errors="replace",
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return r.stdout if r.returncode == 0 else ""


def achar_projeto(nome: str) -> str | None:
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


def por_arquivo(diff: str) -> dict[str, list[str]]:
    """O diff fatiado por arquivo, guardando só as linhas adicionadas.

    Guardar o arquivo junto é o que permite dizer "linha nova em `config.py`" em
    vez de "linha nova em algum lugar" — e sem isso o dono não tem o que abrir.
    """
    blocos: dict[str, list[str]] = {}
    atual = None
    for linha in diff.splitlines():
        if linha.startswith("+++ b/"):
            atual = linha[6:].strip()
            blocos.setdefault(atual, [])
        elif atual and linha.startswith("+") and not linha.startswith("+++"):
            blocos[atual].append(linha)
    return blocos


def main() -> int:
    if len(sys.argv) < 2:
        print(json.dumps({"erro": "uso: revisar_antes.py <projeto>"}, ensure_ascii=False))
        return 1

    repo = achar_projeto(sys.argv[1])
    if not repo:
        print(json.dumps({"erro": f"projeto '{sys.argv[1]}' não encontrado em {RAIZ}"},
                         ensure_ascii=False))
        return 1

    # Tudo que ainda não está no HEAD: índice e working tree, mais o que o git
    # ainda não conhece. O não rastreado é o mais perigoso dos três — é onde
    # mora o `credenciais.json` que ninguém pretendia mandar.
    diff = git(repo, "diff", "HEAD") or git(repo, "diff")
    novos = [a for a in git(repo, "ls-files", "--others", "--exclude-standard").splitlines() if a]
    adicionadas = por_arquivo(diff)
    for arquivo in novos[:60]:
        caminho = os.path.join(repo, arquivo)
        try:
            if os.path.getsize(caminho) > 400_000:
                continue
            with open(caminho, encoding="utf-8", errors="ignore") as f:
                adicionadas.setdefault(arquivo, []).extend("+" + L for L in f.read().splitlines())
        except OSError:
            continue

    if not adicionadas:
        print(json.dumps({
            "projeto": os.path.basename(repo.rstrip("/\\")),
            "nada_para_revisar": True,
            "observacao": "não há alteração fora do último commit",
        }, ensure_ascii=False, indent=2))
        return 0

    segredos, proibidos, sobras = [], [], []

    for arquivo, linhas in adicionadas.items():
        if NOME_PROIBIDO.search(arquivo) and not NOME_LIBERADO.search(arquivo):
            proibidos.append({
                "arquivo": arquivo,
                "motivo": "o nome já diz que não é para versionar",
                "rastreado": arquivo not in novos,
            })

        # Arquivo de exemplo é documentação de quais variáveis existem, não
        # vazamento: `.env.example` sempre traz `postgres://user:password@host`,
        # e acusá-lo ensina o dono a ignorar o aviso verdadeiro. Mesma regra que
        # o `stack-audit` já aplica no vigia de segredo.
        if CONTEUDO_LIBERADO.search(arquivo):
            continue

        corpo = "\n".join(linhas)
        for rotulo, padrao in SEGREDO:
            for linha in linhas:
                if not padrao.search(linha):
                    continue
                if PLACEHOLDER.search(linha):
                    continue
                # Arquivo e tipo, e nada mais. Número de linha foi tentado e
                # removido: dentro de um diff, a posição na lista de linhas
                # adicionadas não é a linha do arquivo, e mandar o dono abrir
                # uma linha onde não há nada é pior que não dizer linha nenhuma.
                # O valor do segredo nunca sai daqui.
                segredos.append({"arquivo": arquivo, "tipo": rotulo})
                break

        for rotulo, padrao in DEPURACAO:
            achados = len(padrao.findall(corpo))
            if achados:
                sobras.append({"arquivo": arquivo, "tipo": rotulo, "vezes": achados})

    # Segredo primeiro, sempre: é o único achado aqui que custa mais que tempo,
    # e o único que fica caro DEPOIS do push.
    print(json.dumps({
        "projeto": os.path.basename(repo.rstrip("/\\")),
        "arquivos_a_entrar": len(adicionadas),
        "segredo_no_conteudo": segredos[:10],
        "arquivo_que_nao_deveria_ir": proibidos[:10],
        "sobra_de_depuracao": sobras[:15],
        "aviso": ("revisa o que ainda NAO foi commitado; depois do push um segredo continua no "
                  "historico mesmo apagado no commit seguinte"),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
