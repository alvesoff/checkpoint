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

import concurrent.futures
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


def _manifesto_proprio(pasta: str) -> bool:
    """Manifesto NA pasta, não em alguma subpasta dela.

    `manifestos()` desce dois níveis de propósito, para cobrir monorepo. Usar
    ela aqui faria a pasta-mãe entrar por causa do manifesto de um repositório
    lá dentro — e o mesmo pacote seria contado duas vezes, inflando o "em
    quantos projetos" que é a informação central desta skill.
    """
    try:
        return any(e.is_file() and (e.name == "package.json"
                                    or re.match(r"^requirements.*\.txt$", e.name))
                   for e in os.scandir(pasta))
    except OSError:
        return False


def projetos(raiz: str) -> list[str]:
    """Repositório git em qualquer nível, MAIS pasta que carrega manifesto.

    As duas metades importam, e trocar uma pela outra troca um ponto cego por
    outro. Só `os.scandir` no primeiro nível perdia tudo numa instalação com
    duas pastas de código, onde o repositório fica em `/projects/<pasta>/<repo>`
    — e como o `vulneraveis.py` lê os manifestos daqui, aquele projeto ficava
    invisível também para a consulta de vulnerabilidade. Falso negativo, não
    rótulo errado.

    Só a descoberta por `.git` perderia o caso oposto: a pasta que tem
    `package.json` e nunca virou repositório. Ela é exatamente o tipo de projeto
    sobre o qual vale avisar.
    """
    if os.path.isdir(os.path.join(raiz, ".git")):
        return [raiz]

    achados: list[str] = []
    vistos: set[str] = set()

    def registrar(caminho: str) -> None:
        real = os.path.normpath(caminho)
        if real not in vistos:
            vistos.add(real)
            achados.append(caminho)

    def descer(pasta: str, nivel: int) -> None:
        if nivel > 3:
            return
        try:
            entradas = sorted(os.scandir(pasta), key=lambda e: e.name)
        except OSError:
            return
        for e in entradas:
            if not e.is_dir(follow_symlinks=False) or e.name in IGNORAR:
                continue
            if os.path.isdir(os.path.join(e.path, ".git")):
                registrar(e.path)          # repositório encerra o ramo
            else:
                if nivel == 1 and _manifesto_proprio(e.path):
                    registrar(e.path)      # pasta com manifesto, sem git
                descer(e.path, nivel + 1)

    descer(raiz, 1)
    return achados


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
    # `/latest` em vez do pacote inteiro. O documento completo do npm traz TODAS
    # as versões já publicadas: o `next` sozinho são 31 MB, contra 3 KB do
    # `/latest` — dez mil vezes menos, pelos mesmos dois campos que lemos. Era
    # daí que vinham os 106 segundos da varredura.
    url = (
        f"https://registry.npmjs.org/{urllib.parse.quote(pacote, safe='@/')}/latest"
        if eco == "npm"
        else f"https://pypi.org/pypi/{urllib.parse.quote(pacote)}/json"
    )
    registro = {"em": time.time(), "ultima": "", "abandonado": ""}
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            dados = json.load(r)
        if eco == "npm":
            # `/latest` já É o manifesto da última versão: `version` e
            # `deprecated` vêm na raiz, com a mesma semântica de antes.
            registro["ultima"] = dados.get("version", "")
            registro["abandonado"] = str(dados.get("deprecated") or "")[:200]
        else:
            info = dados.get("info", {})
            registro["ultima"] = info.get("version", "")
            if (info.get("yanked") or "").strip() if isinstance(info.get("yanked"), str) else info.get("yanked"):
                registro["abandonado"] = "versão retirada do PyPI"
    except (urllib.error.URLError, urllib.error.HTTPError, ValueError, OSError):
        # Pacote privado, nome interno ou rede fora: não é erro nosso, é um
        # pacote sobre o qual não temos o que dizer.
        #
        # E NÃO vai para o cache. Guardar a falha por 24h faz o pacote sumir da
        # assinatura do monitor durante um dia inteiro e voltar depois — duas
        # interrupções do dono por um soluço de rede de 15 segundos. Aconteceu
        # em 15/09 às 02:09: o radar acordou de madrugada e repetiu um alerta de
        # vulnerabilidade que o dono já tinha recebido às 20:06.
        registro["erro"] = True
        return registro
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

    # Aquece o cache em paralelo antes do laço. São ~150 consultas de rede, e em
    # fila indiana elas custavam 106 segundos — dentro de um `demandas.py` que
    # levava 222 no total. Um assistente de conversa que demora quatro minutos
    # para responder "o que eu tenho pra fazer" não é usado duas vezes.
    #
    # O laço abaixo continua idêntico e sequencial: ele lê do cache já quente,
    # então a ORDEM do resultado não depende de quem respondeu primeiro. Ordem
    # instável aqui viraria assinatura instável no monitor, que é o defeito que
    # acordou o dono às 2h da manhã.
    pendentes = [(eco, pacote) for (eco, pacote) in usos
                 if f"{eco}:{pacote}" not in cache]
    if pendentes:
        with concurrent.futures.ThreadPoolExecutor(max_workers=12) as piscina:
            futuros = {piscina.submit(consultar, eco, pacote, {}): (eco, pacote)
                       for eco, pacote in pendentes}
            for futuro in concurrent.futures.as_completed(futuros):
                eco, pacote = futuros[futuro]
                try:
                    registro = futuro.result()
                except Exception:
                    continue
                # Falha continua fora do cache, pelo mesmo motivo de sempre:
                # guardá-la faz o pacote sumir da assinatura por 24 horas.
                if not registro.get("erro"):
                    cache[f"{eco}:{pacote}"] = registro

    achados = []
    # Quem a rede não deixou consultar. Some da lista de achados, e por isso
    # quem monta a assinatura precisa saber que ele é DESCONHECIDO, não
    # RESOLVIDO — as duas coisas se parecem por fora e significam o oposto.
    nao_consultados = []
    # Do mais espalhado para o menos: é a ordem da urgência real, e também a
    # ordem em que vale gastar rede se a varredura for interrompida.
    for (eco, pacote), onde in sorted(usos.items(), key=lambda kv: -len(kv[1])):
        registro = consultar(eco, pacote, cache)
        if registro.get("erro") or not registro["ultima"]:
            nao_consultados.append(pacote)
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
    # Sem teto apertado: com 55 achados e teto 40, o corte caía no meio dos
    # empates de `quantos`, e qualquer mudança na ordem de entrada trocava QUEM
    # ficava de fora. Assinatura instável acorda o dono sem nada ter mudado.
    print(json.dumps({
        "projetos_lidos": resumo["projetos"],
        "pacotes_distintos": len(usos),
        "com_problema": len(achados),
        "nao_consultados": sorted(nao_consultados),
        "achados": achados[:200],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
