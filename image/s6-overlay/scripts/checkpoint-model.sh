#!/bin/sh
# Fixa o modelo que o agente roda, DEPOIS do plow-init.
#
# A base semeia o modelo padrao, e ela troca esse padrao sem ninguem escolher: a
# base de 18/09 semeia `z-ai/glm-5.2` onde a de 17/09 semeia
# `anthropic/claude-sonnet-5`. Metade do preco por token e, pela medicao da
# propria Plow no commit dela, 34 contra 38 do Sonnet no Artificial Analysis.
# Subir a base e obrigacao -- o verificador pediu a mais recente. Deixar a base
# escolher o modelo nao e.
#
# POR QUE AQUI E NAO NO cont-init: isto ja foi escrito no 05-checkpoint-config e
# NAO funcionou, e o modo de falha foi silencioso. O `plow-init` roda DEPOIS do
# legacy-cont-init e reescreve o config.yaml a partir do seed; o passo de
# cont-init via o config velho, nao mudava nada, nao imprimia nada, e o agente
# subia em GLM assim mesmo. As outras chaves que o 05 escreve (wrap_response,
# gateway_restart_notification, context_file_max_chars) sobrevivem porque o
# plow-init preserva o que ele nao gerencia -- `model` ele gerencia.
#
# O `hermes-gateway` depende deste servico, entao o gateway so sobe depois que o
# modelo esta fixado. Sem isso a corrida e real: o gateway leria o config no
# mesmo instante em que ele esta sendo trocado.
#
# Sao TRES chaves, e fixar so a primeira sai pela culatra:
#   model.default               o modelo da conversa
#   providers.plow.models.<id>  sem a entrada, o prompt caching do modelo que
#                               roda de verdade fica de fora e cada turno paga
#                               o prefixo inteiro
#   auxiliary.vision.model      a foto recebida pelo iMessage; um modelo de
#                               texto barato nao ve imagem
#
# Como o usuario do agente, nunca como root: o runtime endurece a home com o uid
# de quem o chama, e `/var/lib/hermes` viraria root:hermes 0700 -- o agente
# perde acesso a propria pasta e para de responder, sem nada no chat dizendo por
# que. Ja custou um dia em 14/09.
#
# Nunca falha o boot: um agente em GLM e pior que um agente em Sonnet, e os dois
# sao muito melhores que um agente que nao sobe.
/command/s6-setuidgid hermes /opt/hermes/.venv/bin/python3 - <<'PY' || \
  echo "[checkpoint] nao consegui fixar o modelo -- vale o que a base semeou"
import yaml

MODELO = "anthropic/claude-sonnet-5"
CAMINHO = "/var/lib/hermes/config.yaml"

with open(CAMINHO, encoding="utf-8") as arquivo:
    config = yaml.safe_load(arquivo) or {}

antes = yaml.safe_dump(config, sort_keys=False, allow_unicode=True)

config.setdefault("model", {})["default"] = MODELO
modelos = config.setdefault("providers", {}).setdefault("plow", {}).setdefault("models", {})
modelos.setdefault(MODELO, {})["prompt_caching"] = True
config.setdefault("auxiliary", {}).setdefault("vision", {})["model"] = MODELO

depois = yaml.safe_dump(config, sort_keys=False, allow_unicode=True)
if depois == antes:
    print("[checkpoint] modelo ja estava em " + MODELO)
else:
    # Irmao e rename, como o proprio plow-init escreve o config: um boot
    # interrompido no meio de um write direto deixaria o agente com um
    # config.yaml pela metade, que e pior que o config anterior.
    temporario = CAMINHO + ".checkpoint-novo"
    with open(temporario, "w", encoding="utf-8") as arquivo:
        arquivo.write(depois)
    import os
    os.replace(temporario, CAMINHO)
    print("[checkpoint] modelo fixado em " + MODELO)
PY
