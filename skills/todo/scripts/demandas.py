#!/usr/bin/env python3
"""A lista de demandas que se preenche sozinha a partir do estado dos projetos.

    demandas.py listar [--todas]
    demandas.py adicionar "<texto>" [projeto]
    demandas.py concluir <id>
    demandas.py adiar <id> <dias>
    demandas.py ignorar <id>

O que a separa de um aplicativo de tarefas: **a maior parte dela não é digitada
por ninguém**. Ela nasce do que os scripts já detectam — trabalho não salvo,
dependência que vai quebrar, segredo solto, container como root — e **fecha
sozinha** quando a condição some do estado real.

Isso resolve algo que faltava no agente: hoje ele avisa da mesma coisa a cada
faixa cruzada e não sabe se a pessoa decidiu não fazer. Com a lista, "adiar" e
"não vou fazer" viram estados, e ele para de repetir.

A demanda digitada à mão convive com as derivadas, e é a única que o dono fecha
manualmente — nada no repositório diz quando ela acabou.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time

HOME = os.environ.get("HERMES_HOME", "/var/lib/hermes")
ARQUIVO = os.path.join(HOME, "checkpoint", "demandas.json")
SKILLS = os.environ.get("SKILLS_DIR", "/opt/hermes/skills")

# Onde cada demanda derivada nasce. O id precisa ser **estável**: é ele que liga
# a demanda de hoje à mesma demanda de amanhã, e é o que permite lembrar que a
# pessoa mandou adiar. Um id que muda a cada varredura ressuscita o que já foi
# dispensado.
AGORA = time.time()


def carregar() -> dict:
    try:
        with open(ARQUIVO, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {"demandas": {}}


def salvar(dados: dict) -> None:
    os.makedirs(os.path.dirname(ARQUIVO), exist_ok=True)
    tmp = ARQUIVO + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)
    os.replace(tmp, ARQUIVO)


def rodar(caminho: str, *args: str) -> dict:
    """Chama um script irmão e devolve o JSON dele, ou {} se falhar.

    Falha de um detector não pode derrubar a lista inteira: uma lista que some
    quando a rede cai é pior que uma lista incompleta.
    """
    try:
        r = subprocess.run(
            [sys.executable, caminho, *args],
            capture_output=True, text=True, timeout=600,
            encoding="utf-8", errors="replace",
        )
        return json.loads(r.stdout)
    except (OSError, subprocess.SubprocessError, ValueError):
        return {}


def derivadas() -> dict[str, dict]:
    """As demandas que o estado dos projetos justifica agora."""
    achadas: dict[str, dict] = {}

    projetos = rodar(f"{SKILLS}/where-i-left-off/scripts/scan_projects.py")
    for p in projetos.get("projetos", []):
        nome = p["projeto"]
        if p.get("nunca_versionado"):
            achadas[f"git:nunca-versionado:{nome}"] = {
                "texto": f"{nome} nunca entrou no git de verdade: {p['arquivos_alterados']} arquivos fora do controle de versão",
                "projeto": nome, "origem": "git", "peso": 3,
            }
        elif p.get("arquivos_alterados"):
            achadas[f"git:nao-salvo:{nome}"] = {
                "texto": f"{nome} tem {p['arquivos_alterados']} arquivos alterados e não salvos",
                "projeto": nome, "origem": "git", "peso": 2,
            }
        if p.get("branch_sem_upstream"):
            achadas[f"git:sem-upstream:{nome}:{p['branch']}"] = {
                "texto": f"{nome}: o branch {p['branch']} nunca foi enviado, ninguém além de você o tem",
                "projeto": nome, "origem": "git", "peso": 2,
            }

    deps = rodar(f"{SKILLS}/dependency-radar/scripts/deps_scan.py")
    for a in deps.get("achados", [])[:15]:
        pacote = a["pacote"]
        if a["tipo"] == "abandonado":
            achadas[f"dep:abandonado:{pacote}"] = {
                "texto": f"{pacote} foi descontinuado e está em {a['quantos']} projetos: {a['detalhe'][:110]}",
                "projeto": ", ".join(a["projetos"][:3]), "origem": "dependencia", "peso": 3,
            }
        else:
            achadas[f"dep:atras:{pacote}"] = {
                "texto": f"{pacote} está em {a['voce_usa']} e o atual é {a['atual']}, afetando {a['quantos']} projetos",
                "projeto": ", ".join(a["projetos"][:3]), "origem": "dependencia", "peso": 1,
            }

    # Vulnerabilidade grave vira demanda de peso máximo: é a única coisa aqui
    # que pode custar mais que tempo.
    vulns = rodar(f"{SKILLS}/dependency-radar/scripts/vulneraveis.py")
    for v in vulns.get("achados", []):
        if v.get("pior") not in ("CRITICAL", "HIGH"):
            continue
        achadas[f"vuln:{v['pacote']}:{v['versao_declarada']}"] = {
            "texto": (f"{v['pacote']} {v['versao_declarada']} tem vulnerabilidade "
                      f"{v['pior']} ({v['vulnerabilidades']} conhecidas) em {v['quantos']} projetos"),
            "projeto": ", ".join(v["projetos"][:3]), "origem": "seguranca", "peso": 5,
        }

    auditoria = rodar(f"{SKILLS}/stack-audit/scripts/auditar.py")
    for s in auditoria.get("segredos_em_arquivo_solto", []):
        achadas[f"segredo:{s['projeto']}:{s['arquivo']}"] = {
            "texto": f"{s['projeto']}: possível {', '.join(s['tipos'])} em {s['arquivo']}, que o git não versiona",
            "projeto": s["projeto"], "origem": "seguranca", "peso": 4,
        }
    for nome in (auditoria.get("containers") or {}).get("rodando_como_root", [])[:10]:
        achadas[f"container:root:{nome}"] = {
            "texto": f"{nome}: o container roda como root, sem USER no Dockerfile",
            "projeto": nome, "origem": "seguranca", "peso": 2,
        }

    # Branch esquecida: tem commit que nao existe em mais lugar nenhum. Entra
    # na lista; branch ja mesclada NAO entra - e limpeza, e uma lista com treze
    # "apague isto" some debaixo do proprio peso e esconde o que importa.
    branches = rodar(f"{SKILLS}/stack-audit/scripts/branches.py")
    for b in branches.get("esquecidas_nao_mescladas", [])[:10]:
        achadas[f"branch:esquecida:{b['projeto']}:{b['branch']}"] = {
            "texto": (f"{b['projeto']}: a branch {b['branch']} esta parada ha {int(b['dias'])} dias "
                      f"com {b['commits_so_dela']} commits que nao estao no principal"),
            "projeto": b["projeto"], "origem": "git", "peso": 3,
        }

    # Documentacao que deixou de bater com o codigo. Duas demandas por projeto no
    # maximo: uma para o que quebra quem segue o documento agora (comando que
    # sumiu, caminho que nao existe) e outra para a configuracao que falta.
    docs = rodar(f"{SKILLS}/doc-check/scripts/conferir_docs.py")
    for r in docs.get("relatorios", [])[:10]:
        nome = r["projeto"]
        erradas = len(r.get("referencias_quebradas", [])) + len(r.get("comandos_que_sumiram", []))
        if erradas:
            primeiro = (r["comandos_que_sumiram"] or
                        [q["aponta_para"] for q in r["referencias_quebradas"]])[0]
            achadas[f"doc:quebrado:{nome}"] = {
                "texto": (f"{nome}: a documentacao manda usar {primeiro}, que nao existe mais"
                          if erradas == 1 else
                          f"{nome}: a documentacao aponta para {erradas} coisas que nao existem "
                          f"mais, comecando por {primeiro}"),
                "projeto": nome, "origem": "documentacao", "peso": 2,
            }
        faltando = r.get("variaveis_exigidas_sem_documentacao") or []
        if faltando:
            achadas[f"doc:env:{nome}"] = {
                "texto": (f"{nome} exige {len(faltando)} variaveis que nenhum documento cita "
                          f"({', '.join(faltando[:3])}): noutra maquina o projeto nao sobe"),
                "projeto": nome, "origem": "documentacao", "peso": 2,
            }

    return achadas


def sincronizar(dados: dict) -> dict:
    """Casa a lista guardada com o estado de agora.

    Três movimentos, e o do meio é o que faz a lista valer:
      - demanda derivada nova entra como aberta;
      - **demanda derivada que sumiu do estado fecha sozinha** — a pessoa
        resolveu, e ninguém precisou avisar a lista;
      - demanda digitada à mão nunca fecha sozinha: nada no repositório sabe
        quando ela acabou.
    """
    vivas = derivadas()
    guardadas = dados.setdefault("demandas", {})

    for ident, nova in vivas.items():
        if ident in guardadas:
            guardadas[ident].update({"texto": nova["texto"], "peso": nova["peso"]})
            guardadas[ident]["visto_em"] = AGORA
            # Reapareceu depois de ter sido resolvida: é uma demanda nova de
            # novo, não a antiga — o arquivo voltou a ficar sujo, a dependência
            # saiu de dia outra vez.
            if guardadas[ident].get("estado") == "feita":
                guardadas[ident]["estado"] = "aberta"
        else:
            guardadas[ident] = {**nova, "estado": "aberta",
                                "criada_em": AGORA, "visto_em": AGORA}

    for ident, d in guardadas.items():
        if d.get("origem") == "manual":
            continue
        if ident not in vivas and d.get("estado") in ("aberta", "adiada"):
            d["estado"] = "feita"
            d["fechada_em"] = AGORA
            d["fechada_por"] = "o estado mudou sozinho"

    return dados


def visivel(d: dict) -> bool:
    if d.get("estado") == "adiada":
        return AGORA >= d.get("adiada_ate", 0)
    return d.get("estado") == "aberta"


def listar(todas: bool) -> None:
    dados = sincronizar(carregar())
    salvar(dados)
    itens = [(i, d) for i, d in dados["demandas"].items() if todas or visivel(d)]
    # Peso primeiro (segredo antes de versão atrasada), e dentro do peso a mais
    # antiga: o que está aberto há mais tempo é o que mais incomoda.
    itens.sort(key=lambda kv: (-kv[1].get("peso", 1), kv[1].get("criada_em", 0)))
    print(json.dumps({
        "abertas": sum(1 for _, d in dados["demandas"].items() if visivel(d)),
        "fechadas_sozinhas": sum(1 for _, d in dados["demandas"].items()
                                 if d.get("fechada_por") == "o estado mudou sozinho"),
        "demandas": [{
            "id": i,
            "texto": d["texto"],
            "projeto": d.get("projeto"),
            "origem": d.get("origem"),
            "estado": d.get("estado"),
            "dias_aberta": round((AGORA - d.get("criada_em", AGORA)) / 86400, 1),
        } for i, d in itens[:40]],
    }, ensure_ascii=False, indent=2))


def mudar(ident: str, **campos) -> None:
    dados = carregar()
    if ident not in dados.get("demandas", {}):
        print(json.dumps({"erro": f"demanda '{ident}' não existe",
                          "como_resolver": "use o id exato que aparece no listar"}, ensure_ascii=False))
        sys.exit(1)
    dados["demandas"][ident].update(campos)
    salvar(dados)
    print(json.dumps({"ok": True, "id": ident, **campos}, ensure_ascii=False))


def main() -> int:
    if len(sys.argv) < 2:
        print(json.dumps({"erro": "uso: demandas.py listar|adicionar|concluir|adiar|ignorar"},
                         ensure_ascii=False))
        return 1
    cmd = sys.argv[1]

    if cmd == "listar":
        listar("--todas" in sys.argv)
    elif cmd == "adicionar":
        if len(sys.argv) < 3:
            print(json.dumps({"erro": 'uso: demandas.py adicionar "<texto>" [projeto]'}, ensure_ascii=False))
            return 1
        dados = carregar()
        ident = f"manual:{int(AGORA)}"
        dados.setdefault("demandas", {})[ident] = {
            "texto": sys.argv[2],
            "projeto": sys.argv[3] if len(sys.argv) > 3 else None,
            "origem": "manual", "peso": 2, "estado": "aberta",
            "criada_em": AGORA, "visto_em": AGORA,
        }
        salvar(dados)
        print(json.dumps({"ok": True, "id": ident, "texto": sys.argv[2]}, ensure_ascii=False))
    elif cmd == "concluir":
        mudar(sys.argv[2], estado="feita", fechada_em=AGORA, fechada_por="o dono marcou")
    elif cmd == "adiar":
        dias = float(sys.argv[3]) if len(sys.argv) > 3 else 7
        mudar(sys.argv[2], estado="adiada", adiada_ate=AGORA + dias * 86400)
    elif cmd == "ignorar":
        mudar(sys.argv[2], estado="ignorada", fechada_em=AGORA, fechada_por="o dono dispensou")
    else:
        print(json.dumps({"erro": f"comando '{cmd}' não existe"}, ensure_ascii=False))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
