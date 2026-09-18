# A imagem deste agente: a base do Plow, mais a nossa persona, as nossas skills
# e o reporter do Agent Index.
#
# A tag é um `base-<sha>` imutável nomeando um commit de plow-pbc/plow-hermes-agent,
# fixada também por digest: um agente que segura credencial viva não pode ter
# código trocado por baixo dele por uma tag que se move.
#
# Atualizada em 18/09 para a mais recente do registro (base-0eba9f29, de
# 18/09 13:05Z), porque o Daniel Delattre pediu a base mais nova como condicao
# do deploy de um clique. Ela substitui a base-51f83158 que o PR #1 dele tinha
# indicado de manha -- a instrucao nova e dele e vale sobre a antiga.
#
# O que essa base traz e que importa aqui: ela bumpa o pin do cliente do Agent
# Index para 87901f8, que ENTRA COMO INSTALADOR no 409 em vez de desistir. O pin
# antigo fazia toda instalacao de terceiro nunca reportar nada. Nos bumpamos o
# nosso `vendor/client.pin` junto, que e o que a nossa imagem realmente busca.
#
# O custo: ela semeia `z-ai/glm-5.2` como modelo padrao -- metade do preco por
# token e, pela medicao da propria Plow, 34 contra 38 do Sonnet no Artificial
# Analysis. O modelo passa a ser FIXADO pelo `05-checkpoint-config`, para que a
# base nao decida sozinha o que o agente roda enquanto os hosts o testam.
FROM public.ecr.aws/e1h7x4a2/plow-cloud-agents:base-0eba9f29edbcffeb846064bbc718b54d3d3e0e47@sha256:14a8307bee7d40c926be4ff7c599d9e973c3d0213099072f0015dd21b61f4594

# Identidade. O plow-init compõe o SOUL.md a cada boot como "persona da base +
# este arquivo", então nada é copiado direto para /var/lib/hermes/SOUL.md.
# `COPY --chmod` exigiria BuildKit, e o Docker Engine instalado pelo gerenciador
# de pacotes vem sem ele: no Docker Desktop o BuildKit e o padrao, num Arch com
# `pacman -S docker` nao e, e a construcao morre em
# "the --chmod option requires BuildKit". Um COPY seguido de chmod funciona nos
# dois, e o custo e uma camada.
COPY runtime/persona.md /opt/hermes/plow-seed/persona.md
RUN chmod 0644 /opt/hermes/plow-seed/persona.md

# Em que commit esta imagem foi construida. Serve para o agente saber se esta
# atrasado em relacao ao repositorio publico -- ele nao tem git nem acesso ao
# Docker do host, entao a unica forma de saber a propria versao e esta.
# Ausente (build manual sem o .env do instalador) vira "desconhecido", e o
# verificador diz isso em vez de inventar uma resposta.
ARG CHECKPOINT_REV=desconhecido
RUN mkdir -p /opt/checkpoint  && printf '%s' "$CHECKPOINT_REV" > /opt/checkpoint/rev  && chmod 0644 /opt/checkpoint/rev

# Quem este agente e para o Agent Index, assado na imagem como PADRAO.
#
# Ate aqui isto vinha so do ambiente (`AGENT_ID` no compose), e vazio o reporter
# fica parado de proposito. Duas coisas quebram nesse arranjo:
#
# 1. O deploy na nuvem do Plow NAO passa ambiente nenhum. O `plow-agents deploy`
#    manda `{name, line_uid, provider}` e mais nada -- sem AGENT_ID assado, um
#    agente rodando na nuvem nunca reporta uso, e uso reportado e a metrica
#    publica de ranking.
# 2. Quem instala este agente esta instalando ESTE agente. O id nao e segredo
#    nem escolha de quem instala: o cliente do indice entra como INSTALADOR na
#    listagem (409 -> join), que e exatamente o caminho certo.
#
# Continua sobrescrevivel pelo ambiente, para quem fizer um fork e quiser a
# propria listagem.
ENV AGENT_ID=checkpoint

# A area onde o agente clona repositorio publico para ler.
#
# Criada AQUI, e nao so pelo compose, porque na nuvem do Plow nao ha compose: o
# `deploy` manda `{name, line_uid, provider}` e nada mais, entao nenhum volume
# nomeado existe la. Sem esta pasta o unico caminho que a nuvem tem para ver
# codigo tambem nao existiria.
#
# Fora de $HERMES_HOME de proposito: aqui entra codigo clonado de fora, que o
# agente le e ninguem executa. Longe de HERMES_HOME/scripts, que e o unico lugar
# gravavel de onde o runtime roda coisa sozinho. O dono vira `hermes` no boot
# (05-checkpoint-config), que ja trata o caso do volume montado por cima.
RUN mkdir -p /var/lib/checkpoint-work/publico  && chown -R hermes:hermes /var/lib/checkpoint-work  && chmod 0750 /var/lib/checkpoint-work

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

# O serviço supervisionado que chama o reporter a cada 5 minutos.
COPY image/s6-overlay/ /etc/s6-overlay/
RUN chmod 0755 /etc/s6-overlay/scripts/latch-probe.sh /etc/s6-overlay/s6-rc.d/latch-probe/up /etc/s6-overlay/scripts/checkpoint-crons.sh /etc/s6-overlay/s6-rc.d/checkpoint-crons/up /etc/s6-overlay/scripts/net-watchdog.sh /etc/s6-overlay/s6-rc.d/net-watchdog/run
RUN chmod 0755 /etc/s6-overlay/s6-rc.d/agent-index/run

# O pin do modelo. Servico, e nao cont-init, porque o `plow-init` reescreve o
# config.yaml a partir do seed DEPOIS do legacy-cont-init -- a primeira versao
# disto rodou cedo demais, nao mudou nada e nao imprimiu nada, e o agente subiu
# no modelo da base assim mesmo. O `hermes-gateway` depende dele.
RUN chmod 0755 /etc/s6-overlay/scripts/checkpoint-model.sh /etc/s6-overlay/s6-rc.d/checkpoint-model/up

# As skills deste agente. Ficam em /opt/hermes/skills, fora de toda home, para
# que uma home montada por bind ainda as receba e uma atualização de imagem
# alcance a skill que o agente não customizou.
COPY skills/ /opt/hermes/skills/
RUN find /opt/hermes/skills -mindepth 1 -type d -exec chmod 0755 {} + \
 && find /opt/hermes/skills -mindepth 1 -type f -exec chmod 0644 {} +

# Quais skills sao NOSSAS. O diretorio de destino mistura as nossas com as que a
# imagem base ja traz, entao a lista sai de uma copia separada do contexto de
# build -- e nao de uma enumeracao escrita a mao em algum script, que esquece a
# skill nova em silencio. Foi o que aconteceu com a prior-art e a self-update:
# o COPY acima as levou para a imagem sozinhas, e so o cont-init que reimpoe as
# skills precisava saber o nome delas.
COPY skills/ /tmp/nossas-skills/
RUN mkdir -p /opt/checkpoint  && ls -1 /tmp/nossas-skills > /opt/checkpoint/skills-do-agente  && chmod 0644 /opt/checkpoint/skills-do-agente  && rm -rf /tmp/nossas-skills

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
# Reimpoe as nossas skills por cima da home a cada boot. Sem isto, um turno que
# edite um arquivo em $HERMES_HOME/skills congela aquela skill para sempre: o
# sync do runtime passa a pular o diretorio inteiro e nenhuma correcao deste
# repositorio chega mais nesta instalacao.
# A promocao da credencial. Antes da 04 de proposito: o plow-init desiste
# sessenta segundos depois do boot, e um cont-init que corre tarde chega tarde.
COPY image/cont-init.d/03-plow-credential /etc/cont-init.d/03-plow-credential
COPY image/cont-init.d/04-checkpoint-skills /etc/cont-init.d/04-checkpoint-skills
COPY image/cont-init.d/05-checkpoint-config /etc/cont-init.d/05-checkpoint-config

# Solta o prompt de sistema preso na sessao. Sem isto, toda persona nova so
# alcanca quem instalar DEPOIS dela: quem ja estava conversando carrega para
# sempre o texto do dia em que abriu a conversa. Ver o proprio script.
COPY image/cont-init.d/06-refresh-persona /etc/cont-init.d/06-refresh-persona
# Os tres juntos, numa camada so. cont-init nao executa o que nao e executavel,
# e a falha seria silenciosa: o boot segue e a etapa simplesmente nao acontece.
RUN chmod 0755 /etc/cont-init.d/03-plow-credential \
               /etc/cont-init.d/04-checkpoint-skills \
               /etc/cont-init.d/05-checkpoint-config \
               /etc/cont-init.d/06-refresh-persona
