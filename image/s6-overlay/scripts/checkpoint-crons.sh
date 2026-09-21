#!/bin/sh
# Registra as rotinas do Checkpoint no primeiro boot.
#
# Sem isto, quem instala recebe um agente PASSIVO: ele responde quando
# perguntado e nunca age sozinho — que é metade do produto. Os dois crons
# existiam só porque foram registrados à mão na máquina de desenvolvimento, e
# isso não acompanha a instalação de ninguém.
#
# Os scripts de registro são idempotentes: leem o jobs.json e não criam um
# segundo job com o mesmo nome. Por isso roda a cada boot em vez de marcar
# "já rodei" num arquivo — marcador mente depois de um `down -v`, o estado real
# não.
set -eu

PY=/opt/hermes/.venv/bin/python3
HOME_AGENTE=/var/lib/hermes

# Sem credencial não há agente para agendar nada, e o plow-init já terá parado o
# boot de qualquer forma.
#
# A credencial deixou de ser um ARQUIVO: a base entrega o token pelo ambiente do
# s6 (`/run/s6/container_environment/PLOW_AGENT_TOKEN`), e `/var/lib/plow` não
# existe mais. Enquanto este guarda olhava só para o arquivo, ele saía **em todo
# boot, em silêncio** -- nenhuma rotina se registrava, o container subia inteiro,
# o agente respondia quando perguntado e simplesmente nunca falava primeiro.
# Numa instalação nova isso significa zero rotina, sem um erro sequer. Medido em
# 21/09, com os seis jobs sobreviventes de um boot antigo escondendo o problema.
#
# Os dois caminhos ficam aceitos: o arquivo, para uma base que volte a usá-lo, e
# o ambiente, que é como funciona hoje.
[ -f /var/lib/plow/credentials ] || [ -s /run/s6/container_environment/PLOW_AGENT_TOKEN ] || exit 0

for registro in \
  /opt/hermes/skills/where-i-left-off/scripts/register_nudge.py \
  /opt/hermes/skills/dependency-radar/scripts/register_radar.py \
  /opt/hermes/skills/doc-check/scripts/register_docs.py \
  /opt/hermes/skills/stack-audit/scripts/register_audit.py \
  /opt/hermes/skills/self-update/scripts/register_update.py \
  /opt/hermes/skills/daily/scripts/register_daily.py \
  /opt/hermes/skills/radar-de-pauta/scripts/register_pauta.py
do
  [ -f "$registro" ] || continue
  # Nunca fatal: uma rotina que não registrou não pode impedir o agente de subir
  # e responder. O erro fica no log do boot.
  /command/s6-setuidgid hermes \
    env HOME="$HOME_AGENTE" HERMES_HOME="$HOME_AGENTE" \
    "$PY" "$registro" 2>&1 | sed 's/^/[checkpoint-crons] /' || \
    echo "[checkpoint-crons] falhou ao registrar $(basename "$registro") — o agente sobe mesmo assim"
done
