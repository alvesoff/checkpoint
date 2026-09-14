#!/usr/bin/env python3
"""A lista de demandas que se preenche sozinha a partir do estado dos projetos.

    demandas.py listar [--todas]
    demandas.py adicionar "<texto>" [projeto] [AAAA-MM-DD]
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

## Importante não é urgente, e confundir os dois é o defeito padrão

Toda lista de tarefas ordena por gravidade e chama isso de prioridade. O efeito
é que ela só mostra incêndio, e o trabalho que **ninguém está cobrando hoje e
custa caro depois** nunca chega ao topo — que é exatamente onde mora o valor
deste agente: o projeto de três semanas que nunca entrou no git, a branch com
oito commits que só existem numa máquina.

Por isso os dois eixos são medidos separado, e de fontes diferentes:

  - **importância** — o que se perde se isto nunca for feito. Sai da natureza do
    achado e não muda com o tempo.
  - **urgência** — o que força uma data. Sai **de fora**: uma reunião no
    calendário que toca aquele projeto, um prazo que o dono declarou, ou um dano
    que já está acontecendo agora. Gravidade **não** cria urgência.

O quadrante sai do cruzamento, e o resumo da manhã abre pelo **importante e não
urgente** — a pergunta que ninguém responde: *o que é mais importante hoje e que
eu não faria se ninguém me lembrasse?*
"""

from __future__ import annotations

import datetime
import json
import os
import re
import subprocess
import sys
import time
import unicodedata

HOME = os.environ.get("HERMES_HOME", "/var/lib/hermes")
ARQUIVO = os.path.join(HOME, "checkpoint", "demandas.json")
SKILLS = os.environ.get("SKILLS_DIR", "/opt/hermes/skills")

# Onde cada demanda derivada nasce. O id precisa ser **estável**: é ele que liga
# a demanda de hoje à mesma demanda de amanhã, e é o que permite lembrar que a
# pessoa mandou adiar. Um id que muda a cada varredura ressuscita o que já foi
# dispensado.
#
# O `peso` de cada achado é a IMPORTÂNCIA — o que se perde se aquilo nunca for
# feito — e não a gravidade técnica. A diferença apareceu no primeiro teste do
# eixo: com os pesos antigos, "28 arquivos que nunca entraram no git" caía em
# "quando sobrar" e um pacote de tipos depreciado subia para o topo do
# importante. Escala: 5 = trabalho ou dinheiro que se perde; 4 = trabalho que só
# existe numa máquina; 3 = trava outra pessoa; 2 = custa tempo.
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


# A única urgência que nasce do próprio achado é o dano que **já está
# acontecendo**: um segredo num arquivo solto já está exposto agora, uma
# vulnerabilidade CRITICAL já é explorável agora.
#
# Isso é marcado por achado, nunca pela origem. Marcar a origem `seguranca`
# inteira punha "container roda como root" no mesmo balde — e aquilo é fraqueza
# latente, não incêndio. O teste mostrou 18 itens em "faça agora", que é a
# mangueira de incêndio que este produto existe para não ser.


def sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto.lower())
                   if unicodedata.category(c) != "Mn")


def projetos_com_reuniao(dias: int = 3) -> dict[str, str]:
    """Projetos que aparecem no título de algum compromisso dos próximos dias.

    É daqui que vem quase toda a urgência honesta desta lista: uma reunião
    marcada é um prazo real que alguém combinou com outra pessoa. Gravidade de
    vulnerabilidade não marca hora com ninguém.
    """
    agenda = rodar(f"{SKILLS}/agenda/scripts/ler_agenda.py", str(dias))
    eventos = agenda.get("eventos") or []
    if not eventos:
        return {}

    nomes = set()
    for p in (rodar(f"{SKILLS}/where-i-left-off/scripts/scan_projects.py").get("projetos") or []):
        nomes.add(p["projeto"])

    encontrados: dict[str, str] = {}
    for e in eventos:
        titulo = sem_acento(e.get("titulo") or "")
        for nome in nomes:
            for pedaco in re.split(r"[-_]", sem_acento(nome)):
                # Pedaço curto casa com qualquer coisa: `bsj` e `app` viram
                # urgência falsa em meia dúzia de projetos.
                if len(pedaco) >= 5 and pedaco in titulo:
                    encontrados.setdefault(nome, e.get("titulo") or "")
    return encontrados


def urgencia_de(demanda: dict, com_reuniao: dict[str, str]) -> tuple[int, str]:
    """De 0 a 3, e o motivo — sempre um fato externo, nunca a gravidade.

    Uma demanda sem nada forçando a data é urgência 0, por mais grave que seja.
    Isso é deliberado: é o que impede a lista de virar só uma fila de incêndios.
    """
    prazo = demanda.get("prazo")
    if prazo:
        try:
            faltam = (datetime.date.fromisoformat(prazo) - datetime.date.today()).days
            if faltam <= 1:
                return 3, f"prazo declarado: {prazo}"
            if faltam <= 3:
                return 2, f"prazo declarado: {prazo}"
            if faltam <= 7:
                return 1, f"prazo declarado: {prazo}"
        except ValueError:
            pass

    if demanda.get("em_curso"):
        return 3, "o dano já está acontecendo"

    for nome in (demanda.get("projeto") or "").split(", "):
        if nome and nome in com_reuniao:
            return 2, f"reunião marcada: {com_reuniao[nome][:60]}"

    return 0, "nada força uma data"


def quadrante(importancia: int, urgencia: int) -> str:
    """O quadrante de Eisenhower, nomeado pelo que a pessoa deve fazer.

    O corte da importância é 3: abaixo disso o trabalho custa tempo, acima ele
    custa trabalho perdido, dinheiro ou confiança.
    """
    grande = importancia >= 3
    corre = urgencia >= 2
    if grande and corre:
        return "agora"
    if grande:
        return "importante-sem-pressa"
    if corre:
        return "corre-mas-nao-importa"
    return "quando-sobrar"


def derivadas() -> dict[str, dict]:
    """As demandas que o estado dos projetos justifica agora."""
    achadas: dict[str, dict] = {}

    projetos = rodar(f"{SKILLS}/where-i-left-off/scripts/scan_projects.py")
    for p in projetos.get("projetos", []):
        nome = p["projeto"]
        if p.get("nunca_versionado"):
            achadas[f"git:nunca-versionado:{nome}"] = {
                "texto": f"{nome} nunca entrou no git de verdade: {p['arquivos_alterados']} arquivos fora do controle de versão",
                # Importância máxima, e nunca urgente: ninguém está cobrando, e
                # some inteiro se o disco morrer. É o caso que define este eixo.
                "projeto": nome, "origem": "git", "peso": 5,
            }
        elif p.get("arquivos_alterados"):
            # Quanto mais tempo parado, mais o trabalho vale e menos alguém
            # lembra dele. Um dia é rascunho; dois meses é coisa que se perde.
            parado = p.get("ultimo_toque_ha_dias") or 0
            quantos = p["arquivos_alterados"]
            achadas[f"git:nao-salvo:{nome}"] = {
                "texto": (f"{nome} tem {quantos} "
                          + ("arquivos alterados e não salvos"
                             if quantos != 1 else "arquivo alterado e não salvo")
                          + (f", parado há {int(parado)} dias" if parado >= 7 else "")),
                "projeto": nome, "origem": "git",
                "peso": 5 if parado >= 30 else 4 if parado >= 7 else 3,
                "parado_ha_dias": round(parado, 1),
            }
        if p.get("branch_sem_upstream"):
            achadas[f"git:sem-upstream:{nome}:{p['branch']}"] = {
                "texto": f"{nome}: o branch {p['branch']} nunca foi enviado, ninguém além de você o tem",
                "projeto": nome, "origem": "git", "peso": 4,
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
            "em_curso": True,
        }

    auditoria = rodar(f"{SKILLS}/stack-audit/scripts/auditar.py")
    for s in auditoria.get("segredos_em_arquivo_solto", []):
        achadas[f"segredo:{s['projeto']}:{s['arquivo']}"] = {
            "texto": f"{s['projeto']}: possível {', '.join(s['tipos'])} em {s['arquivo']}, que o git não versiona",
            "projeto": s["projeto"], "origem": "seguranca", "peso": 5,
            "em_curso": True,
        }
    for nome in (auditoria.get("containers") or {}).get("rodando_como_root", [])[:10]:
        achadas[f"container:root:{nome}"] = {
            "texto": f"{nome}: o container roda como root, sem USER no Dockerfile",
            "projeto": nome, "origem": "seguranca", "peso": 3,
        }

    # Branch esquecida: tem commit que nao existe em mais lugar nenhum. Entra
    # na lista; branch ja mesclada NAO entra - e limpeza, e uma lista com treze
    # "apague isto" some debaixo do proprio peso e esconde o que importa.
    branches = rodar(f"{SKILLS}/stack-audit/scripts/branches.py")
    for b in branches.get("esquecidas_nao_mescladas", [])[:10]:
        achadas[f"branch:esquecida:{b['projeto']}:{b['branch']}"] = {
            "texto": (f"{b['projeto']}: a branch {b['branch']} esta parada ha {int(b['dias'])} dias "
                      f"com {b['commits_so_dela']} commits que nao estao no principal"),
            "projeto": b["projeto"], "origem": "git", "peso": 4,
            "parado_ha_dias": b.get("dias", 0),
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
                "projeto": nome, "origem": "documentacao", "peso": 3,
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
    com_reuniao = projetos_com_reuniao()

    for ident, nova in vivas.items():
        if ident in guardadas:
            guardadas[ident].update({"texto": nova["texto"], "peso": nova["peso"],
                                     "em_curso": nova.get("em_curso", False),
                                     "parado_ha_dias": nova.get("parado_ha_dias", 0)})
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

    # Os eixos são recalculados a cada leitura, nunca guardados como verdade: a
    # urgência muda quando o calendário muda, e uma urgência congelada em disco
    # seria falsa no dia seguinte.
    for d in guardadas.values():
        d["importancia"] = d.get("peso", 1)
        d["urgencia"], d["por_que_corre"] = urgencia_de(d, com_reuniao)
        d["quadrante"] = quadrante(d["importancia"], d["urgencia"])

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
    itens.sort(key=lambda kv: (-kv[1].get("urgencia", 0), -kv[1].get("importancia", 1),
                               kv[1].get("criada_em", 0)))

    def em_json(par):
        i, d = par
        return {
            "id": i,
            "texto": d["texto"],
            "projeto": d.get("projeto"),
            "origem": d.get("origem"),
            "estado": d.get("estado"),
            "importancia": d.get("importancia", 1),
            "urgencia": d.get("urgencia", 0),
            "quadrante": d.get("quadrante"),
            "por_que_corre": d.get("por_que_corre"),
            "prazo": d.get("prazo"),
            "parado_ha_dias": d.get("parado_ha_dias") or None,
            "dias_aberta": round((AGORA - d.get("criada_em", AGORA)) / 86400, 1),
        }

    # A resposta da pergunta que ninguém faz sozinho: o que é mais importante
    # hoje e não vai acontecer se ninguém lembrar. Entre iguais, a mais antiga —
    # é a que está sendo adiada há mais tempo.
    sem_pressa = [kv for kv in itens if kv[1].get("quadrante") == "importante-sem-pressa"]
    # Entre importâncias iguais, o que está parado há mais tempo. Data de criação
    # não serve de desempate: todas as derivadas nascem na mesma varredura, e o
    # que distingue duas iguais é há quanto tempo ninguém toca nelas.
    sem_pressa.sort(key=lambda kv: (-kv[1].get("importancia", 1),
                                    -(kv[1].get("parado_ha_dias") or 0),
                                    kv[1].get("criada_em", 0)))

    print(json.dumps({
        "abertas": sum(1 for _, d in dados["demandas"].items() if visivel(d)),
        "fechadas_sozinhas": sum(1 for _, d in dados["demandas"].items()
                                 if d.get("fechada_por") == "o estado mudou sozinho"),
        "por_quadrante": {
            q: sum(1 for _, d in itens if d.get("quadrante") == q)
            for q in ("agora", "importante-sem-pressa", "corre-mas-nao-importa", "quando-sobrar")
        },
        "o_que_ninguem_vai_cobrar_hoje": em_json(sem_pressa[0]) if sem_pressa else None,
        "demandas": [em_json(kv) for kv in itens[:40]],
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
            print(json.dumps({"erro": 'uso: demandas.py adicionar "<texto>" [projeto] [AAAA-MM-DD]'},
                             ensure_ascii=False))
            return 1
        dados = carregar()
        ident = f"manual:{int(AGORA)}"
        # O último argumento, se for uma data ISO, é prazo — e prazo declarado é
        # a única urgência que o dono cria por conta própria.
        extras = sys.argv[3:]
        prazo = None
        if extras:
            try:
                datetime.date.fromisoformat(extras[-1])
                prazo = extras.pop()
            except ValueError:
                prazo = None
        dados.setdefault("demandas", {})[ident] = {
            "texto": sys.argv[2],
            "projeto": extras[0] if extras else None,
            "prazo": prazo,
            # Ele pediu para anotar: presume-se que custa algo se não for feito.
            "origem": "manual", "peso": 3, "estado": "aberta",
            "criada_em": AGORA, "visto_em": AGORA,
        }
        salvar(dados)
        print(json.dumps({"ok": True, "id": ident, "texto": sys.argv[2], "prazo": prazo},
                         ensure_ascii=False))
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
