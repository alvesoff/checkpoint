#!/bin/sh
# Remove PLOW_MCP_URL quando não há máquina do dono conectada do outro lado.
#
# O plugin do Plow injeta o LATCH_PROMPT em todo turno de chat sempre que essa
# variável existe — e o plow-init a publica sempre, tenha máquina ou não. Esse
# texto manda o agente tratar qualquer pedido com "meu" (meus arquivos, meu
# calendário, meus projetos) como sendo sobre o Mac do dono, e diz que o próprio
# shell dele serve só para o trabalho dele.
#
# O texto da plataforma diz "Mac"; a máquina do outro lado não precisa ser um.
# O Latch tem versão de Windows e de Linux, e em 21/09 quem respondeu 200 aqui
# foi um Windows 11. Por isso este script fala em "máquina", nunca em "Mac":
# quem lê este log é quem está diagnosticando, e um log que afirma Mac manda
# essa pessoa procurar o problema na plataforma errada.
#
# Sem ela, isso faz o agente RECUSAR perguntas que ele sabe responder: "não
# tenho acesso à sua agenda" com a agenda carregada na própria máquina. Tentar
# sobrepor pela persona não venceu o texto da plataforma.
#
# A variável só é verdade quando há um device conectado. Apagá-la quando não há
# faz o LATCH_PROMPT inteiro desaparecer — que é o comportamento correto, não um
# contorno: o agente para de prometer e de recusar em nome de uma máquina
# inexistente.
#
# Roda depois do plow-init, que a publica, e antes do gateway, que a lê.
#
# O probe roda UMA vez, no boot. Uma maquina que conecte depois nao seria percebida,
# e ate aqui a skill `browsing` passava a responder "esta instalacao nao tem
# relay configurado" -- que e falso: o relay existe, so nao havia device ligado
# naquele instante. Por isso a URL removida fica guardada num arquivo legivel
# pelo agente: a skill reavalia o relay na hora em que alguem pergunta, e volta
# a dizer a verdade sem depender de reboot nem de reiniciar o gateway.
set -eu

VAR=/run/s6/container_environment/PLOW_MCP_URL
GUARDADA=/opt/checkpoint/latch-url
[ -f "$VAR" ] || exit 0

URL=$(cat "$VAR" 2>/dev/null || true)
TOKEN=$(cat /run/s6/container_environment/PLOW_AGENT_TOKEN 2>/dev/null || true)

guardar() {
  mkdir -p /opt/checkpoint
  printf '%s' "$1" > "$GUARDADA"
  chmod 0644 "$GUARDADA"
}

if [ -z "$URL" ] || [ -z "$TOKEN" ]; then
  rm -f "$VAR"
  echo "[checkpoint] sem relay utilizável — PLOW_MCP_URL removida"
  exit 0
fi

CODE=$(curl -s -o /dev/null -w '%{http_code}' -m 20 -X POST "$URL" \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' 2>/dev/null || echo 000)

if [ "$CODE" = "200" ]; then
  echo "[checkpoint] máquina do dono conectada pelo Latch — mantendo PLOW_MCP_URL"
else
  guardar "$URL"
  rm -f "$VAR"
  echo "[checkpoint] nenhuma máquina conectada (relay respondeu $CODE) — PLOW_MCP_URL removida para o agente nao recusar em nome de uma maquina inexistente"
fi
