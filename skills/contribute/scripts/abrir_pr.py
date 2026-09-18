#!/usr/bin/env python3
"""Commita o que está na cópia do agente e abre um Pull Request em rascunho.

    abrir_pr.py <dono/repo> <arquivo-com-o-texto.md>

O arquivo traz o título na primeira linha e o corpo no resto. Vai por arquivo,
e não por argumento, porque descrição de PR tem parágrafo, crase e quebra de
linha — coisas que não sobrevivem inteiras a uma linha de comando.

Três coisas que este script se recusa a fazer, e é por elas que ele existe:

  * empurrar para o ramo base. Toda mudança vira PR, sempre, mesmo trivial.
  * empurrar com segredo dentro. A varredura é a MESMA do `delivery-text`,
    importada e não copiada: duas cópias divergem, e a que para o push é a que
    não pode estar desatualizada.
  * `--force`, em qualquer ramo, por qualquer motivo.

O PR nasce em RASCUNHO. Quem revisa é uma pessoa, e rascunho é o que diz isso
sem depender de ninguém lembrar.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request

TRABALHO = "/var/lib/checkpoint-work"
LIBERADOS = "/opt/checkpoint/repos-liberados"
AMBIENTE = "/run/s6/container_environment"
REVISOR = "/opt/hermes/skills/delivery-text/scripts/revisar_antes.py"

REPO_VALIDO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
# Um PR gigante não é revisável, e "eu avalio o que ele fez" era o ponto.
MAX_ARQUIVOS = 40


def token() -> str:
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


def git(*args: str, cwd: str) -> tuple[int, str]:
    try:
        r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True,
                           timeout=300, encoding="utf-8", errors="replace")
    except (OSError, subprocess.SubprocessError) as erro:
        return 1, type(erro).__name__
    return r.returncode, (r.stdout + r.stderr).strip()


def carregar_revisor():
    """O módulo do `delivery-text`, carregado pelo caminho.

    Importado em vez de copiado de propósito. Se os padrões forem duplicados
    aqui, a cópia que decide se um segredo vai para um repositório público é
    justamente a que ninguém lembra de atualizar.
    """
    spec = importlib.util.spec_from_file_location("revisar_antes", REVISOR)
    if spec is None or spec.loader is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception:
        return None
    return mod


def varrer(rev, diff: str) -> list[dict]:
    """Os segredos nas linhas ADICIONADAS de um diff qualquer."""
    achados = []
    for arquivo, linhas in rev.por_arquivo(diff).items():
        if rev.NOME_PROIBIDO.search(arquivo) and not rev.NOME_LIBERADO.search(arquivo):
            achados.append({"arquivo": arquivo, "tipo": "arquivo que não deveria ser versionado"})
        if rev.CONTEUDO_LIBERADO.search(arquivo):
            continue
        for rotulo, padrao in rev.SEGREDO:
            for linha in linhas:
                if padrao.search(linha) and not rev.PLACEHOLDER.search(linha):
                    achados.append({"arquivo": arquivo, "tipo": rotulo})
                    break
    return achados


def segredos(caminho: str, base: str, so_o_indice: bool) -> list[dict] | None:
    """Segredo no que vai subir. `None` = não deu para varrer, e isso interrompe.

    `None` e `[]` são coisas diferentes, e o chamador trata diferente: lista
    vazia libera, "não deu para saber" barra. Trava que falha aberta não é trava.

    Duas passadas, e a segunda é a que importa:

      * antes de commitar, o índice — para o segredo nem entrar num commit;
      * antes de empurrar, **o patch de CADA commit** do ramo, e não o diff
        líquido contra a base. Um segredo adicionado num commit e apagado no
        seguinte **some do diff líquido e continua no histórico** — que é
        exatamente o que fica caro depois do push. Descoberto testando: a
        primeira versão olhava só o líquido e teria empurrado.
    """
    rev = carregar_revisor()
    if rev is None:
        return None
    if so_o_indice:
        codigo, diff = git("diff", "--cached", cwd=caminho)
    else:
        # -p com --no-merges: o patch de cada commit, um atrás do outro.
        codigo, diff = git("log", "-p", "--no-merges", f"origin/{base}..HEAD", cwd=caminho)
    if codigo != 0:
        return None
    return varrer(rev, diff)


def api(caminho_api: str, corpo: dict, tok: str) -> tuple[int, dict]:
    pedido = urllib.request.Request(
        f"https://api.github.com{caminho_api}",
        data=json.dumps(corpo).encode(),
        method="POST",
        headers={
            "Authorization": f"Bearer {tok}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "checkpoint-agent",
        },
    )
    try:
        with urllib.request.urlopen(pedido, timeout=45) as r:
            return r.status, json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as erro:
        try:
            return erro.code, json.loads(erro.read().decode("utf-8", "replace"))
        except Exception:
            return erro.code, {}
    except Exception as erro:
        return 0, {"message": type(erro).__name__}


def main() -> int:
    if len(sys.argv) < 3:
        print(json.dumps({"erro": "uso: abrir_pr.py <dono/repo> <arquivo-com-o-texto.md>"},
                         ensure_ascii=False))
        return 1

    repo, texto = sys.argv[1].strip(), sys.argv[2]

    if not REPO_VALIDO.match(repo) or repo not in liberados():
        print(json.dumps({"erro": f"'{repo}' não está liberado nesta instalação"},
                         ensure_ascii=False))
        return 1

    tok = token()
    if not tok:
        print(json.dumps({"erro": "sem CHECKPOINT_GH_TOKEN"}, ensure_ascii=False))
        return 1

    try:
        with open(texto, encoding="utf-8") as f:
            linhas = f.read().splitlines()
    except OSError as erro:
        print(json.dumps({"erro": f"não consegui ler {texto}: {type(erro).__name__}"},
                         ensure_ascii=False))
        return 1
    titulo = (linhas[0] if linhas else "").strip().lstrip("# ").strip()
    corpo_pr = "\n".join(linhas[1:]).strip()
    if not titulo:
        print(json.dumps({"erro": "a primeira linha do arquivo é o título, e está vazia"},
                         ensure_ascii=False))
        return 1

    caminho = os.path.join(TRABALHO, repo.replace("/", "__"))
    if not os.path.isdir(os.path.join(caminho, ".git")):
        print(json.dumps({"erro": "não há cópia preparada; rode abrir_espaco.py antes"},
                         ensure_ascii=False))
        return 1

    codigo, ramo = git("rev-parse", "--abbrev-ref", "HEAD", cwd=caminho)
    if codigo != 0 or not ramo.startswith("checkpoint/"):
        print(json.dumps({
            "erro": f"o ramo atual é '{ramo}', e esta skill só empurra ramo checkpoint/*",
            "por_que": "mudança vira PR; nada vai direto para o ramo base",
        }, ensure_ascii=False))
        return 1

    base_ref = git("symbolic-ref", "refs/remotes/origin/HEAD", cwd=caminho)[1]
    base = base_ref.rsplit("/", 1)[1] if "/" in base_ref else "main"

    git("add", "-A", cwd=caminho)
    if not git("diff", "--cached", "--name-only", cwd=caminho)[1].strip() and \
            not git("log", f"origin/{base}..HEAD", "--oneline", cwd=caminho)[1].strip():
        print(json.dumps({"erro": "nada mudou nesta cópia — não há PR para abrir"},
                         ensure_ascii=False))
        return 1

    # Antes de commitar, não depois: um segredo que entra num commit fica no
    # ramo mesmo se o arquivo for apagado em seguida, e aí a cópia inteira tem
    # que ser jogada fora. Barato agora, caro daqui a um commit.
    if git("diff", "--cached", "--name-only", cwd=caminho)[1].strip():
        achados = segredos(caminho, base, so_o_indice=True)
        if achados is None:
            print(json.dumps({"erro": "não consegui varrer o que ia para o commit"},
                             ensure_ascii=False))
            return 1
        if achados:
            print(json.dumps({
                "erro": "há segredo no que ia para o commit; nada foi commitado nem empurrado",
                "achados": achados[:10],
            }, ensure_ascii=False, indent=2))
            return 1
        if git("commit", "--quiet", "-m", titulo, cwd=caminho)[0] != 0:
            print(json.dumps({"erro": "o commit falhou"}, ensure_ascii=False))
            return 1

    arquivos = [a for a in git("diff", "--name-only", f"origin/{base}...HEAD",
                               cwd=caminho)[1].splitlines() if a.strip()]
    if len(arquivos) > MAX_ARQUIVOS:
        print(json.dumps({
            "erro": f"{len(arquivos)} arquivos mudaram, e o limite é {MAX_ARQUIVOS}",
            "por_que": "PR que ninguém consegue revisar não é revisão, é carimbo",
        }, ensure_ascii=False))
        return 1

    # Segunda passada, contra o patch de CADA commit do ramo. É a que pega o
    # segredo que entrou num commit e saiu no seguinte — invisível no diff
    # líquido, e presente para sempre no histórico que o push publica.
    achados = segredos(caminho, base, so_o_indice=False)
    if achados is None:
        print(json.dumps({
            "erro": "não consegui varrer o histórico atrás de segredo, então não empurro",
            "por_que": "depois do push o segredo fica no histórico mesmo apagado depois",
        }, ensure_ascii=False))
        return 1
    if achados:
        # Nunca o valor. Arquivo e tipo, que é o que a pessoa precisa para abrir
        # e resolver — repetir o segredo numa mensagem é vazá-lo de novo.
        print(json.dumps({
            "erro": "há segredo no que ia subir; nada foi empurrado",
            "achados": achados[:10],
        }, ensure_ascii=False, indent=2))
        return 1

    codigo, saida = git("push", "--quiet", "--set-upstream", "origin", ramo, cwd=caminho)
    if codigo != 0:
        print(json.dumps({"erro": "o push falhou", "detalhe": saida[-400:]},
                         ensure_ascii=False))
        return 1

    status, resposta = api(f"/repos/{repo}/pulls", {
        "title": titulo, "body": corpo_pr, "head": ramo, "base": base, "draft": True,
    }, tok)
    if status not in (200, 201):
        print(json.dumps({
            "erro": f"o ramo subiu, mas a API do GitHub respondeu {status}",
            "detalhe": str(resposta.get("message", ""))[:200],
            "abrir_a_mao": f"https://github.com/{repo}/compare/{base}...{ramo}",
        }, ensure_ascii=False))
        return 1

    print(json.dumps({
        "ok": True,
        "pr": resposta.get("html_url"),
        "rascunho": True,
        "repo": repo, "ramo": ramo, "base": base,
        "arquivos": len(arquivos),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
