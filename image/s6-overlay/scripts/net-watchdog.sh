#!/bin/sh
# Vigia da rede: detecta o canal caído, reage, e deixa registrado para o dono.
#
# Por que existe. Num notebook Windows, o Docker Desktop perde o DNS do
# container quando a máquina suspende: o `resolv.conf` segue apontando para o
# resolvedor antigo e a resolução só volta reiniciando alguma coisa. Medido
# nesta instalação: 33.168 falhas `ClientConnectorDNSError` em três dias, das
# 17h21 de uma sexta às 06h54 da segunda.
#
# O que torna isso grave não é a queda, é o SILÊNCIO dela. O container segue
# `Up`, os crons seguem `completed`, o log de execução mostra o agente decidindo
# normalmente — e nenhuma mensagem do dono chega, porque o websocket de entrada
# está morto. A pessoa conclui que o produto não funciona e desinstala, sem
# nunca saber que foi rede.
#
# Três coisas, nesta ordem:
#   1. detectar (resolução + alcance do relay);
#   2. reagir (reiniciar o gateway, que é o que reabre o websocket);
#   3. contar — a janela da queda vira uma linha no digest do cutucão, então o
#      agente acorda e avisa o dono do que ele perdeu.
set -eu

ESTADO=/var/lib/hermes/checkpoint
QUEDAS="$ESTADO/quedas.json"

# De quanto em quanto tempo olhar. Um minuto é barato (é uma consulta DNS e um
# HEAD) e não deixa a pessoa mais de um minuto sem cobertura.
INTERVALO=60

# Quantas falhas seguidas antes de reiniciar o gateway. Três minutos: menos que
# isso reagiria a oscilação normal de rede, e reiniciar o gateway derruba o turno
# em andamento.
TOLERANCIA=3

# Depois de reiniciar e continuar falhando, esperar bem mais antes de tentar de
# novo — reiniciar em laço não conserta rede e só queima o turno de quem estiver
# conversando.
ESPERA_APOS_REINICIO=600

alcanca_relay() {
  # Resolução E alcance, porque falham por motivos diferentes e o sintoma que
  # nos derrubou foi só o primeiro.
  getent hosts api.plow.co >/dev/null 2>&1 || return 1
  codigo=$(curl -s -o /dev/null -w '%{http_code}' -m 15 https://api.plow.co/v1/usage 2>/dev/null || echo 000)
  # Qualquer código HTTP prova que a rede chegou lá — 401 e 403 inclusive. Só a
  # ausência de resposta (000) conta como queda.
  [ "$codigo" != "000" ]
}


registrar_queda() {
  # Acrescenta a janela ao arquivo que o digest do cutucão lê. Escrito por um
  # Python curto porque montar JSON com shell é como se corrompe arquivo de
  # estado.
  inicio="$1"; fim="$2"
  /opt/hermes/.venv/bin/python3 - "$QUEDAS" "$inicio" "$fim" <<'PY'
import json, os, sys
caminho, inicio, fim = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
try:
    with open(caminho, encoding="utf-8") as f:
        dados = json.load(f)
except (OSError, ValueError):
    dados = {"quedas": []}
dados["quedas"].append({"inicio": inicio, "fim": fim, "minutos": round((fim - inicio) / 60), "avisado": False})
# Só as últimas: o histórico completo não interessa a ninguém e o arquivo é lido
# a cada tique do monitor.
dados["quedas"] = dados["quedas"][-20:]
os.makedirs(os.path.dirname(caminho), exist_ok=True)
tmp = caminho + ".tmp"
with open(tmp, "w", encoding="utf-8") as f:
    json.dump(dados, f, ensure_ascii=False)
os.replace(tmp, caminho)
PY
  chown -R 10000:10000 "$ESTADO" 2>/dev/null || true
}

mkdir -p "$ESTADO"
chown 10000:10000 "$ESTADO" 2>/dev/null || true

# O momento da queda vive em disco, não em memória. Um vigia cujo trabalho é não
# perder informação não pode perdê-la quando o container reinicia — e reiniciar
# durante uma queda é exatamente o que acontece quando a pessoa reinicia o Docker
# para tentar consertar a rede.
EM_QUEDA="$ESTADO/em-queda"

falhas=0
caiu_em=0
[ -f "$EM_QUEDA" ] && caiu_em=$(cat "$EM_QUEDA" 2>/dev/null || echo 0)
case "$caiu_em" in ''|*[!0-9]*) caiu_em=0 ;; esac

while :; do
  if alcanca_relay; then
    if [ "$caiu_em" -ne 0 ]; then
      agora=$(date +%s)
      echo "[net-watchdog] rede voltou apos $(( (agora - caiu_em) / 60 )) min — registrando para avisar o dono"
      registrar_queda "$caiu_em" "$agora"
      rm -f "$EM_QUEDA"
      caiu_em=0
    fi
    falhas=0
  else
    falhas=$((falhas + 1))
    if [ "$caiu_em" -eq 0 ]; then
      caiu_em=$(date +%s)
      printf '%s' "$caiu_em" > "$EM_QUEDA"
    fi
    echo "[net-watchdog] relay inalcancavel ($falhas)"
    if [ "$falhas" -ge "$TOLERANCIA" ]; then
      echo "[net-watchdog] reiniciando o gateway para reabrir o websocket"
      /command/s6-svc -r /run/service/hermes-gateway 2>/dev/null || true
      falhas=0
      sleep "$ESPERA_APOS_REINICIO"
      continue
    fi
  fi
  sleep "$INTERVALO"
done
