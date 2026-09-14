#!/usr/bin/env python3
"""O resumo do dia — de manhã, o que é realista; à noite, o que ficou.

    resumo.py manha
    resumo.py noite

A diferença entre isto e um digest de tarefas: **o calendário entra na conta**.
Calendário guarda intenção, git guarda realidade, e ninguém junta os dois — a
pessoa marca seis horas de trabalho num dia que já tem quatro de reunião, e
descobre às cinco da tarde.

De manhã responde "o que dá para fazer hoje", com as horas livres calculadas — e
abre pelo **importante que não é urgente**, que é a coisa que nenhuma lista de
tarefas mostra, porque todas ordenam por gravidade e gravidade é urgência
disfarçada.
À noite responde "o que eu fiz e o que ficou solto", e olha a primeira reunião
de amanhã para dizer em que estado está o projeto que ela cita.
"""

from __future__ import annotations

import datetime
import json
import os
import re
import subprocess
import sys
import unicodedata

RAIZ = os.environ.get("PROJECTS_ROOT", "/projects")
SKILLS = os.environ.get("SKILLS_DIR", "/opt/hermes/skills")

# Um dia de trabalho, para a conta de horas livres. Não é promessa de jornada:
# é a régua contra a qual o tempo de reunião é descontado.
JORNADA_MIN = 8 * 60


def sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto.lower())
                   if unicodedata.category(c) != "Mn")


def git(repo: str, *args: str) -> str:
    try:
        r = subprocess.run(
            ["git", "-c", "core.autocrlf=true", "-C", repo, *args],
            capture_output=True, text=True, timeout=25,
            encoding="utf-8", errors="replace",
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return r.stdout.strip() if r.returncode == 0 else ""


def projetos() -> list[str]:
    if os.path.isdir(os.path.join(RAIZ, ".git")):
        return [RAIZ]
    try:
        return [e.path for e in sorted(os.scandir(RAIZ), key=lambda x: x.name)
                if e.is_dir() and os.path.isdir(os.path.join(e.path, ".git"))]
    except OSError:
        return []


def rodar(caminho: str, *args: str) -> dict:
    """Chama um script irmão. Falha dele não derruba o resumo — um resumo
    incompleto ainda serve; um resumo que não chega, não."""
    try:
        r = subprocess.run(
            [sys.executable, caminho, *args],
            capture_output=True, text=True, timeout=300,
            encoding="utf-8", errors="replace",
        )
        return json.loads(r.stdout)
    except (OSError, subprocess.SubprocessError, ValueError):
        return {}


def commits_de_hoje() -> list[dict]:
    """O que entrou no git hoje, por projeto.

    `--since=midnight` e não "últimas 24h": a pessoa quer saber do dia dela, e
    um commit de ontem às 23h não é trabalho de hoje.
    """
    feitos = []
    for repo in projetos():
        linhas = git(repo, "log", "--since=midnight", "--format=%s", "--all").splitlines()
        if linhas:
            feitos.append({
                "projeto": os.path.basename(repo.rstrip("/\\")),
                "commits": len(linhas),
                "assuntos": [s[:80] for s in linhas[:3]],
            })
    feitos.sort(key=lambda f: -f["commits"])
    return feitos


def agenda(dias: int) -> dict:
    return rodar(f"{SKILLS}/agenda/scripts/ler_agenda.py", str(dias))


def do_dia(eventos: list[dict], dia: datetime.date) -> list[dict]:
    marcados = []
    for e in eventos:
        try:
            comeco = datetime.datetime.fromisoformat(e["inicio"])
        except (ValueError, KeyError):
            continue
        if comeco.date() == dia:
            marcados.append({**e, "_quando": comeco})
    marcados.sort(key=lambda e: e["_quando"])
    for e in marcados:
        e.pop("_quando", None)
    return marcados


def projeto_do_evento(titulo: str, nomes: list[str]) -> str | None:
    """Qual projeto esta reunião cita, se algum.

    Casa por pedaço do nome, não pelo nome inteiro: ninguém escreve
    "deploy do payroll-api" no calendário — escreve "deploy faltas". Pedaços
    curtos ficam de fora porque `bsj` e `app` casam com qualquer coisa.
    """
    alvo = sem_acento(titulo)
    melhor, tamanho = None, 0
    for nome in nomes:
        for pedaco in re.split(r"[-_]", sem_acento(nome)):
            if len(pedaco) >= 5 and pedaco in alvo and len(pedaco) > tamanho:
                melhor, tamanho = nome, len(pedaco)
    return melhor


def estado_dos_projetos() -> list[dict]:
    dados = rodar(f"{SKILLS}/where-i-left-off/scripts/scan_projects.py")
    return dados.get("projetos", [])


def resumir(p: dict) -> str:
    n = p.get("arquivos_alterados") or 0
    plural = "arquivos" if n != 1 else "arquivo"
    if p.get("nunca_versionado"):
        return f"{n} {plural} nunca versionados" if n != 1 else f"{n} arquivo nunca versionado"
    if n:
        return f"{n} {plural} alterados e não salvos" if n != 1 else f"{n} arquivo alterado e não salvo"
    if p.get("branch_sem_upstream"):
        return f"o branch {p.get('branch')} nunca foi enviado"
    return "limpo"


def manha() -> dict:
    hoje = datetime.date.today()
    cal = agenda(1)
    eventos = do_dia(cal.get("eventos", []), hoje)
    ocupado = sum(e.get("minutos") or 0 for e in eventos)

    estado = estado_dos_projetos()
    parados = [p for p in estado
               if p.get("arquivos_alterados") or p.get("nunca_versionado")
               or p.get("branch_sem_upstream")]
    parados.sort(key=lambda p: (-int(bool(p.get("nunca_versionado"))),
                                -(p.get("arquivos_alterados") or 0)))

    # A pergunta que ninguém se faz sozinho, e que o resumo existe para responder.
    # Vem da lista de demandas porque é lá que os dois eixos são cruzados.
    lista = rodar(f"{SKILLS}/todo/scripts/demandas.py", "listar")

    return {
        "momento": "manha",
        "data": hoje.isoformat(),
        "o_que_ninguem_vai_cobrar_hoje": lista.get("o_que_ninguem_vai_cobrar_hoje"),
        "quadrantes": lista.get("por_quadrante"),
        "reunioes": [{"titulo": e["titulo"], "inicio": e["inicio"], "minutos": e.get("minutos")}
                     for e in eventos],
        "minutos_de_reuniao": ocupado,
        # A conta que muda a conversa: sobra tempo para quantas frentes, não
        # para quantas tarefas. Duas frentes num dia de quatro horas de reunião
        # já é otimismo.
        "horas_livres_estimadas": round(max(JORNADA_MIN - ocupado, 0) / 60, 1),
        "projetos_com_pendencia": [
            {"projeto": p["projeto"], "pendencia": resumir(p),
             "dias": p.get("ultimo_toque_ha_dias")} for p in parados[:6]
        ],
        "projetos_limpos": len(estado) - len(parados),
    }


def noite() -> dict:
    hoje = datetime.date.today()
    amanha = hoje + datetime.timedelta(days=1)

    feitos = commits_de_hoje()
    estado = estado_dos_projetos()
    nomes = [p["projeto"] for p in estado]
    por_nome = {p["projeto"]: p for p in estado}

    soltos = [{"projeto": p["projeto"], "pendencia": resumir(p),
               "dias": p.get("ultimo_toque_ha_dias")}
              for p in estado
              if p.get("arquivos_alterados") or p.get("nunca_versionado")]
    soltos.sort(key=lambda s: -(s.get("dias") or 0))

    cal = agenda(2)
    de_amanha = do_dia(cal.get("eventos", []), amanha)
    primeira = de_amanha[0] if de_amanha else None

    # O cruzamento que justifica o produto: a primeira reunião de amanhã e o
    # estado real do projeto que ela cita. O calendário diz o que ele prometeu;
    # o git diz o que existe.
    ligacao = None
    if primeira:
        nome = projeto_do_evento(primeira["titulo"], nomes)
        if nome:
            ligacao = {"reuniao": primeira["titulo"], "projeto": nome,
                       "estado": resumir(por_nome[nome]),
                       "dias": por_nome[nome].get("ultimo_toque_ha_dias")}

    return {
        "momento": "noite",
        "data": hoje.isoformat(),
        "commits_hoje": sum(f["commits"] for f in feitos),
        "onde": feitos[:5],
        "ainda_nao_salvo": soltos[:5],
        "amanha_primeira_reuniao": ({"titulo": primeira["titulo"], "inicio": primeira["inicio"]}
                                    if primeira else None),
        "amanha_reunioes": len(de_amanha),
        "reuniao_cruzada_com_projeto": ligacao,
    }


def main() -> int:
    modo = sys.argv[1] if len(sys.argv) > 1 else "manha"
    if modo not in ("manha", "noite"):
        print(json.dumps({"erro": "uso: resumo.py manha|noite"}, ensure_ascii=False))
        return 1
    print(json.dumps(manha() if modo == "manha" else noite(),
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
