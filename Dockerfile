# A imagem deste agente: a base do Plow, mais a nossa persona, as nossas skills
# e o reporter do Agent Index.
#
# A tag é um `base-<sha>` imutável nomeando um commit de plow-pbc/plow-hermes-agent,
# fixada também por digest: um agente que segura credencial viva não pode ter
# código trocado por baixo dele por uma tag que se move.
FROM public.ecr.aws/e1h7x4a2/plow-cloud-agents:base-4747960eaa8a44ac24424bf0cc6c22559af61f43@sha256:fe9b0f428f9ed2da1698ecf0b504c79eceb9e016e770291ff6b3418b9f65449d

# Identidade. O plow-init compõe o SOUL.md a cada boot como "persona da base +
# este arquivo", então nada é copiado direto para /var/lib/hermes/SOUL.md.
COPY --chmod=0644 runtime/persona.md /opt/hermes/plow-seed/persona.md

# O reporter do Agent Index — o ÚNICO requisito obrigatório do hackathon.
#
# Buscado no build em vez de commitado porque plow-pbc/agent-index-client é dono
# do arquivo; pinado por sha em vez de `main` porque isto roda dentro de um
# agente que segura credencial viva, e uma referência móvel substituiria código
# não revisado embaixo dele. O sha256 é a segunda metade da garantia: um sha na
# URL só vale o quanto vale o host que serve a URL.
#
# Root-owned sob /opt/plow, fora da home: o que o supervisor roda sozinho não
# pode ser um arquivo que um turno do agente consegue reescrever.
COPY vendor/client.pin /opt/plow/agent-index-client.pin
RUN set -eu; \
    sha="$(sed -n 's/^sha=//p' /opt/plow/agent-index-client.pin)"; \
    want="$(sed -n 's/^sha256=//p' /opt/plow/agent-index-client.pin)"; \
    path="$(sed -n 's/^path=//p' /opt/plow/agent-index-client.pin)"; \
    curl -fsS --max-time 60 -o /opt/plow/agent-index-client.py \
      "https://raw.githubusercontent.com/plow-pbc/agent-index-client/${sha}/${path}"; \
    got="$(sha256sum /opt/plow/agent-index-client.py | cut -d' ' -f1)"; \
    [ "$got" = "$want" ] || { echo "agent-index client is $got, pin says $want" >&2; exit 1; }; \
    chmod 0644 /opt/plow/agent-index-client.py

# O serviço supervisionado que chama o reporter de hora em hora.
COPY image/s6-overlay/ /etc/s6-overlay/
RUN chmod 0755 /etc/s6-overlay/scripts/latch-probe.sh /etc/s6-overlay/s6-rc.d/latch-probe/up /etc/s6-overlay/scripts/checkpoint-crons.sh /etc/s6-overlay/s6-rc.d/checkpoint-crons/up /etc/s6-overlay/scripts/net-watchdog.sh /etc/s6-overlay/s6-rc.d/net-watchdog/run
RUN chmod 0755 /etc/s6-overlay/s6-rc.d/agent-index/run

# As skills deste agente. Ficam em /opt/hermes/skills, fora de toda home, para
# que uma home montada por bind ainda as receba e uma atualização de imagem
# alcance a skill que o agente não customizou.
COPY skills/ /opt/hermes/skills/
RUN find /opt/hermes/skills -mindepth 1 -type d -exec chmod 0755 {} + \
 && find /opt/hermes/skills -mindepth 1 -type f -exec chmod 0644 {} +

# O git recusa ler repositório cujo dono não é o usuário que o invoca
# ("detected dubious ownership"). Arquivo montado do host nunca pertence ao uid
# do agente — em NENHUMA máquina, seja Windows, Linux ou Mac. Sem esta linha a
# skill principal falha na instalação de todo mundo, com uma mensagem que fala
# de propriedade quando o problema é montagem.
#
# Só leitura é permitida de qualquer forma: a montagem é :ro.
# Vai em /etc/gitconfig, NAO na home do agente: /var/lib/hermes e um volume
# nomeado, e um volume mascara o que a imagem escreveu no ponto de montagem —
# o arquivo existe na imagem e some no container. Custou um diagnostico: 25
# repositorios montados apareciam como "nenhum projeto ativo".
RUN printf '[safe]\n\tdirectory = *\n' > /etc/gitconfig && chmod 0644 /etc/gitconfig

# Desliga o embrulho do cron na resposta entregue. Ver o proprio script: sem isso
# todo aviso proativo chega com "Cronjob Response", id do job e instrucoes de
# gerenciamento no meio da mensagem.
COPY --chmod=0755 image/cont-init.d/05-checkpoint-config /etc/cont-init.d/05-checkpoint-config

# Solta o prompt de sistema preso na sessao. Sem isto, toda persona nova so
# alcanca quem instalar DEPOIS dela: quem ja estava conversando carrega para
# sempre o texto do dia em que abriu a conversa. Ver o proprio script.
COPY --chmod=0755 image/cont-init.d/06-refresh-persona /etc/cont-init.d/06-refresh-persona
