#!/bin/sh
# Instalador de um comando do Checkpoint.
#
#   curl -fsSL https://raw.githubusercontent.com/alvesoff/checkpoint/main/install.sh | sh
#
# Existe porque a instalação manual são nove comandos, incluindo textar uma frase
# de ativação e copiar o uid de uma linha. No índice do hackathon, a taxa média de
# instalação bem-sucedida é ~18% — um agente teve 9 tentativas e 1 sucesso. O
# gargalo não é a ideia, é isto aqui.
#
# Nada é feito às escondidas: todo passo que muda algo pergunta antes, e a
# resposta padrão é sempre a segura.
set -eu

# Quando o script chega por `curl | sh`, a entrada padrão é o próprio script —
# ler dela devoraria o resto do código. Toda pergunta vai para o terminal real.
# `[ -r /dev/tty ]` não basta: o teste passa e a abertura falha quando não há
# terminal controlador (CI, container sem tty). Só a abertura de verdade prova.
if (exec 3</dev/tty) 2>/dev/null; then
  exec 3</dev/tty
else
  exec 3<&0
fi

# ---------------------------------------------------------------- idioma

# Detecta pelo locale do sistema. No Git Bash do Windows o LANG costuma vir
# vazio, então cai para o PowerShell, que sabe a cultura do usuário. Sem os dois,
# inglês: é o que mais gente entende.
detectar_idioma() {
  # Locale explícito do shell ganha: quem definiu LANG escolheu, e uma cultura de
  # sistema não pode desfazer essa escolha.
  locale_shell="${LC_ALL:-}${LC_MESSAGES:-}${LANG:-}"
  if [ -n "$locale_shell" ]; then
    case "$locale_shell" in
      pt_*|pt) echo pt ;;
      *) echo en ;;
    esac
    return
  fi
  # Sem locale nenhum — o caso do Git Bash no Windows — pergunta ao sistema.
  if command -v powershell.exe >/dev/null 2>&1; then
    case "$(powershell.exe -NoProfile -Command '(Get-Culture).Name' 2>/dev/null | tr -d '\r')" in
      pt-*) echo pt; return ;;
    esac
  fi
  echo en
}
IDIOMA=$(detectar_idioma)

# Cada mensagem em duas línguas, escolhidas por uma função só. Duplicar o texto
# no ponto de uso espalharia a tradução por trinta lugares.
msg() { # msg <texto en> <texto pt>
  if [ "$IDIOMA" = pt ]; then printf '%s\n' "$2"; else printf '%s\n' "$1"; fi
}

# Em que passo o script estava quando morreu.
#
# São 800 linhas sob `set -eu` rodando na máquina de outra pessoa: qualquer
# comando que devolva não-zero encerra tudo sem dizer nada, e o que chega para
# quem instalou é "parou com código 1". Aconteceu num Windows em 16/09 e custou
# três execuções para localizar a linha — com o instalador dizendo onde parou,
# teria custado uma.
#
# EXIT em vez de ERR porque ERR não existe em `sh` POSIX: no Linux o script
# chega por `curl | sh`, que na Debian e na Ubuntu é o dash. Testado nos três.
ETAPA=""
onde_parou() {
  codigo=$?
  [ "$codigo" -eq 0 ] && return 0
  # `erro` já explicou o motivo em português claro; não repetir por cima dele.
  [ -n "$ETAPA" ] || return 0
  msg "Stopped while: $ETAPA (exit $codigo)" \
      "Parou em: $ETAPA (código $codigo)" >&2
}
trap onde_parou EXIT

# Pergunta sim/não. O padrão vai em maiúscula e é o que acontece se a pessoa
# só apertar Enter.
confirmar() { # confirmar <pergunta en> <pergunta pt> <padrao s|n>
  pergunta=$([ "$IDIOMA" = pt ] && printf '%s' "$2" || printf '%s' "$1")
  if [ "${3:-s}" = s ]; then dica="[S/n]"; [ "$IDIOMA" = en ] && dica="[Y/n]"; else dica="[s/N]"; [ "$IDIOMA" = en ] && dica="[y/N]"; fi
  printf '%s %s ' "$pergunta" "$dica"
  read -r resposta <&3 || resposta=""
  case "$(printf '%s' "$resposta" | tr '[:upper:]' '[:lower:]')" in
    s|sim|y|yes) return 0 ;;
    n|nao|não|no) return 1 ;;
    "") [ "${3:-s}" = s ] && return 0 || return 1 ;;
    *) [ "${3:-s}" = s ] && return 0 || return 1 ;;
  esac
}

# Quem chama esta funcao captura a saida dela com $(...), entao tudo que for
# escrito em stdout vira a resposta em vez de aparecer na tela. O rotulo vai
# para stderr: e o unico jeito de a pergunta ser vista e nao ser lida de volta
# como se fosse o que a pessoa digitou.
perguntar() { # perguntar <rotulo en> <rotulo pt> ; ecoa a resposta
  rotulo=$([ "$IDIOMA" = pt ] && printf '%s' "$2" || printf '%s' "$1")
  printf '%s ' "$rotulo" >&2
  read -r valor <&3 || valor=""
  printf '%s' "$valor"
}

# No Windows a pessoa copia o caminho do Explorer e cola do jeito que veio:
# C:\Users\alguem\projetos. O bash do MSYS quer /c/Users/alguem/projetos.
# Recusar o formato que ela tem na mao seria implicancia, nao validacao.
normalizar_caminho() {
  bruto=$(printf '%s' "$1" | tr '\\' '/')
  case "$bruto" in
    "~/"*) printf '%s/%s' "$HOME" "${bruto#~/}" ; return ;;
  esac
  case "$bruto" in
    [A-Za-z]:/*)
      unidade=$(printf '%s' "$bruto" | cut -c1 | tr '[:upper:]' '[:lower:]')
      printf '/%s%s' "$unidade" "$(printf '%s' "$bruto" | cut -c3-)"
      ;;
    *) printf '%s' "$bruto" ;;
  esac
}

erro() { ETAPA=""; msg "$1" "$2" >&2; exit 1; }

# ---------------------------------------------------------------- pré-requisitos

ETAPA="conferindo Docker, git e Python"

msg "Checkpoint — installer" "Checkpoint — instalador"
echo

# Qual sistema, porque daqui para baixo cada um falha de um jeito e a mesma
# mensagem para os tres manda a pessoa fazer a coisa errada. WSL se declara
# Linux, que e o certo: o docker dele e o do Linux.
case "$(uname -s 2>/dev/null || echo desconhecido)" in
  Darwin)                SO=mac;;
  Linux)                 SO=linux;;
  MINGW*|MSYS*|CYGWIN*)  SO=windows;;
  *)                     SO=outro;;
esac


DOCKER=docker
command -v docker >/dev/null 2>&1 || {
  # Docker Desktop no Windows nem sempre exporta o docker para o PATH do Git Bash.
  # No Git Bash o binario e docker.exe; no WSL, sem extensao. Procurar so um
  # dos dois derruba a instalacao em metade das maquinas Windows.
  for tentativa in "/c/Program Files/Docker/Docker/resources/bin/docker.exe" \
                   "/c/Program Files/Docker/Docker/resources/bin/docker" \
                   "/mnt/c/Program Files/Docker/Docker/resources/bin/docker.exe" \
                   "/mnt/c/Program Files/Docker/Docker/resources/bin/docker"; do
    [ -x "$tentativa" ] && DOCKER="$tentativa" && break
  done
}
if ! "$DOCKER" --version >/dev/null 2>&1; then
  # O Windows ja oferecia instalar pelo winget e o Mac ja abre o Docker Desktop.
  # No Linux o script so reclamava e morria: quem seguiu o link de instalacao
  # batia numa parede e tinha que ir procurar como instalar Docker sozinho.
  # Existe caminho oficial e de uma linha, entao nao ha motivo para nao oferecer.
  if [ "$SO" = linux ]; then
    msg "Docker is not installed, and the agent runs in a container." \
        "O Docker nao esta instalado, e o agente roda em container."
    SUDO=""
    if [ "$(id -u)" != "0" ]; then
      if command -v sudo >/dev/null 2>&1; then
        SUDO="sudo"
      else
        erro "Docker is missing and there is no sudo here. Install docker as root, then run this again." \
             "Falta o Docker e nao ha sudo aqui. Instale o docker como root e rode de novo."
      fi
    fi
    if confirmar "Install Docker Engine now? (your package manager may update other packages; asks for your password)" \
                 "Instalar o Docker Engine agora? (o gerenciador de pacotes pode atualizar outros pacotes; vai pedir sua senha)" s; then
      command -v curl >/dev/null 2>&1 || erro \
        "curl is needed to fetch the Docker installer." \
        "Preciso do curl para baixar o instalador do Docker."
      # O get.docker.com NAO cobre Arch: ele responde
      # "ERROR: Unsupported distribution 'cachyos'" e sai. No Arch e derivados
      # (CachyOS, Manjaro, EndeavourOS) o docker esta no repositorio oficial, e
      # tentar o script da Docker primeiro so faz a pessoa ver um erro em ingles
      # antes de chegar no caminho que funciona.
      if command -v pacman >/dev/null 2>&1; then
        msg "Arch-based system: installing docker from the official repository." \
            "Sistema baseado em Arch: instalando o docker pelo repositorio oficial."
        # -Syu, e nao -S: sem sincronizar a base o pacman responde "target not
        # found", e sincronizar sem atualizar (-Sy) deixa o sistema em partial
        # upgrade, que o Arch desaconselha e que quebra de formas dificeis de
        # diagnosticar depois.
        $SUDO pacman -Syu --needed --noconfirm docker docker-compose docker-buildx || erro \
          "pacman could not install docker. See the output above." \
          "O pacman nao conseguiu instalar o docker. Veja a saida acima."
      else
        # get.docker.com e publicado e mantido pela propria Docker, e cobre
        # Debian, Ubuntu, Fedora, CentOS e derivados. Baixado para arquivo antes
        # de rodar: `curl | sh` como root esconde o que esta sendo executado.
        curl -fsSL https://get.docker.com -o /tmp/get-docker.sh || erro \
          "Could not download the Docker installer." \
          "Nao consegui baixar o instalador do Docker."
        $SUDO sh /tmp/get-docker.sh || erro \
          "The Docker install failed. See the output above." \
          "A instalacao do Docker falhou. Veja a saida acima."
        rm -f /tmp/get-docker.sh
      fi
      # Recem-instalado, o servico costuma ficar parado e o usuario fora do grupo.
      $SUDO systemctl enable --now docker >/dev/null 2>&1 || true
      if [ "$(id -u)" != "0" ]; then
        $SUDO usermod -aG docker "$(id -un)" >/dev/null 2>&1 || true
        msg "Added you to the docker group. This shell does not have it yet." \
            "Adicionei voce ao grupo docker. Este shell ainda nao tem o grupo."
      fi
      "$DOCKER" --version >/dev/null 2>&1 || erro \
        "Docker installed. This shell cannot see it yet: run  newgrp docker  (or log out and back in), then run this again." \
        "Docker instalado. Este shell ainda nao enxerga: rode  newgrp docker  (ou faca logout/login) e rode isto de novo."
    else
      erro "Nothing was installed. Install docker and run this again." \
           "Nada foi instalado. Instale o docker e rode de novo."
    fi
  else
    erro "Docker not found. Install Docker Desktop (or the docker engine) and run this again." \
         "Docker não encontrado. Instale o Docker Desktop (ou o engine) e rode de novo."
  fi
fi

# `docker info` falha por dois motivos muito diferentes, e ate aqui os dois
# recebiam "abra o Docker": no Linux, quem esta fora do grupo docker leva
# "permission denied" com o daemon rodando perfeitamente, e abrir coisa
# nenhuma resolve. WSL se declara Linux, que e o certo.
if ! INFO_ERRO=$("$DOCKER" info 2>&1 >/dev/null); then
  case "$INFO_ERRO" in
    # So "permission denied". O padrao "dial unix" tambem casava, e a CLI 29
    # -- a que o pacman, o get.docker.com e o Docker Desktop entregam hoje --
    # poe "dial unix" na mensagem de DAEMON PARADO. Resultado: a pessoa era
    # mandada entrar no grupo docker, o que nao liga daemon nenhum, e rodar
    # de novo devolvia a mesma frase para sempre. O caso real de permissao
    # continua coberto: com socket 0660 e usuario fora do grupo, a CLI 29
    # emite "permission denied" sem "dial unix".
    *"permission denied"*)
      erro "Docker is running, but your user cannot reach it. Run:  sudo usermod -aG docker \$USER  then log out and back in (or run: newgrp docker)." \
           "O Docker esta rodando, mas seu usuario nao alcanca ele. Rode:  sudo usermod -aG docker \$USER  e faca logout/login (ou rode: newgrp docker)."
      ;;
  esac
  if [ "$SO" = mac ] && [ -d /Applications/Docker.app ]; then
    # No Windows o instalador ja abria e esperava o Docker sozinho; no Mac ele
    # so reclamava e morria. Mesma cortesia nos dois.
    msg "Docker Desktop is installed but not running. Starting it..." \
        "O Docker Desktop esta instalado mas nao esta rodando. Abrindo..."
    open -a Docker >/dev/null 2>&1 || true
    i=0
    while [ "$i" -lt 120 ]; do
      "$DOCKER" info >/dev/null 2>&1 && break
      i=$((i + 1))
      sleep 1
    done
  fi
  "$DOCKER" info >/dev/null 2>&1 || {
    case "$SO" in
      mac)   erro "Docker is installed but not running. Open Docker Desktop and run this again." \
                  "O Docker esta instalado mas nao esta rodando. Abra o Docker Desktop e rode de novo.";;
      linux) erro "The Docker daemon is not running. Start it:  sudo systemctl start docker" \
                  "O daemon do Docker nao esta rodando. Ligue com:  sudo systemctl start docker";;
      *)     erro "Docker is installed but not running. Start it and run this again." \
                  "O Docker esta instalado mas nao esta rodando. Abra ele e rode de novo.";;
    esac
  }
fi

command -v git >/dev/null 2>&1 || erro "git not found." "git não encontrado."

# A CLI do Plow é Python puro, mas o shebang dela é python3 — e no Windows esse
# nome cai no alias da Microsoft Store, que não é um Python. Por isso o
# interpretador é resolvido aqui e a CLI é sempre chamada através dele.
PY=""
for tentativa in python3 python; do
  if command -v "$tentativa" >/dev/null 2>&1 && "$tentativa" -c 'import sys; sys.exit(0 if sys.version_info>=(3,9) else 1)' 2>/dev/null; then
    PY="$tentativa"; break
  fi
done
[ -n "$PY" ] || erro "Python 3.9+ not found." "Python 3.9+ não encontrado."

msg "Docker, git and Python: found." "Docker, git e Python: encontrados."

# ------------------------------------------------- iniciar junto com a maquina

ETAPA="configurando o Docker para iniciar sozinho"
#
# O container tem `restart: unless-stopped`, entao ele volta sozinho assim que o
# Docker sobe. Mas se o Docker nao sobe com a maquina, o agente fica morto e em
# silencio depois do primeiro reboot -- e quem instalou conclui que o produto
# parou de funcionar, sem nada no celular dizendo o contrario. E o caminho mais
# curto para uma desinstalacao.
#
# Mexer na configuracao do Docker de outra pessoa exige perguntar.
docker_sobe_sozinho() {
  case "$SO" in
    linux)
      systemctl is-enabled docker >/dev/null 2>&1 && return 0 || return 1
      ;;
    mac|windows)
      cfg=$(ls "$HOME/Library/Group Containers/group.com.docker/settings-store.json" \
               "${APPDATA:-}/Docker/settings-store.json" \
               "$HOME/AppData/Roaming/Docker/settings-store.json" 2>/dev/null | head -1)
      [ -n "$cfg" ] || return 0   # sem config legivel, nao afirmar nada
      grep -q '"AutoStart"[[:space:]]*:[[:space:]]*true' "$cfg" && return 0 || return 1
      ;;
  esac
  return 0
}

ligar_docker_no_boot() {
  case "$SO" in
    linux)
      sudo systemctl enable docker >/dev/null 2>&1 && return 0 || return 1
      ;;
    mac|windows)
      cfg=$(ls "$HOME/Library/Group Containers/group.com.docker/settings-store.json" \
               "${APPDATA:-}/Docker/settings-store.json" \
               "$HOME/AppData/Roaming/Docker/settings-store.json" 2>/dev/null | head -1)
      [ -n "$cfg" ] || return 1
      "$PY" - "$cfg" <<'PYEOF' || return 1
import json, sys
caminho = sys.argv[1]
try:
    with open(caminho, encoding="utf-8") as f:
        dados = json.load(f)
except (OSError, ValueError):
    sys.exit(1)
dados["AutoStart"] = True
try:
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(dados, f, indent=2)
except OSError:
    sys.exit(1)
PYEOF
      return 0
      ;;
  esac
  return 1
}

if ! docker_sobe_sozinho; then
  echo
  msg "Docker does not start with your machine. After a reboot the agent stays down, silently." \
      "O Docker nao inicia junto com a maquina. Depois de um reboot o agente fica parado, em silencio."
  if confirmar "Make Docker start automatically? (changes a Docker Desktop setting)" \
               "Fazer o Docker iniciar sozinho? (muda uma configuracao do Docker Desktop)" s; then
    if ligar_docker_no_boot; then
      msg "Done. It takes effect on the next restart of Docker." \
          "Pronto. Vale a partir do proximo restart do Docker."
    else
      msg "Could not change it here. Turn on 'Start Docker Desktop when you sign in' in Docker settings." \
          "Nao consegui mudar aqui. Ligue 'Start Docker Desktop when you sign in' nas configuracoes do Docker."
    fi
  else
    msg "Fine. Remember to open Docker after each reboot, or the agent will not answer." \
        "Certo. Lembre de abrir o Docker depois de cada reboot, ou o agente nao responde."
  fi
fi

# ---------------------------------------------------------------- onde instalar

# Quem recusa a pasta sugerida quase nunca tem outra na cabeça — recusou porque
# a de lá parecia quebrada. O prompt antigo não dava exemplo nem padrão, e um
# Enter vazio encerrava a instalação com "Nenhuma pasta informada". Num Windows
# em 16/09 foi exatamente assim que a terceira tentativa morreu. Agora o Enter
# tem resposta.
outra_pasta() {
  # A sugestão precisa ser uma pasta que não existe: oferecer uma ocupada faria
  # o Enter cair na atualização de uma cópia que a pessoa nunca confirmou — que
  # é o caminho do qual ela está justamente saindo.
  alternativa="$1-novo"
  n=2
  while [ -e "$alternativa" ] && [ "$n" -lt 20 ]; do
    alternativa="$1-novo$n"
    n=$((n + 1))
  done
  escolha=$(normalizar_caminho "$(perguntar \
    "Install into which directory? (Enter for $alternativa)" \
    "Instalar em qual pasta? (Enter para $alternativa)")")
  [ -n "$escolha" ] || escolha="$alternativa"
  printf '%s' "$escolha"
}

DESTINO="${CHECKPOINT_DIR:-$HOME/checkpoint}"
if [ -e "$DESTINO" ]; then
  # Uma pasta que ja tem o repo clonado dentro nao e uma pasta ocupada por
  # engano: e uma tentativa anterior que parou no meio, e a instalacao demora
  # o bastante para isso ser comum. Ai o padrao e continuar. Qualquer outra
  # pasta que ja exista continua com o padrao seguro, que e nao mexer.
  if [ -d "$DESTINO/.git" ] && [ -f "$DESTINO/compose.yml" ]; then
    confirmar "Found an earlier install in $DESTINO. Continue from it?" \
              "Encontrei uma instalação anterior em $DESTINO. Continuar dela?" s \
      || DESTINO=$(outra_pasta "$DESTINO")
  else
    confirmar "Directory $DESTINO already exists. Use it anyway?" \
              "A pasta $DESTINO já existe. Usar assim mesmo?" n \
      || DESTINO=$(outra_pasta "$DESTINO")
  fi
fi
[ -n "$DESTINO" ] || erro "No directory given." "Nenhuma pasta informada."

# -c core.autocrlf=false não é necessário para este repo (o .gitattributes fixa
# LF), mas é para o plow-agents, que não tem um.
ETAPA="baixando o Checkpoint"
if [ ! -d "$DESTINO/.git" ]; then
  # O git já disse o motivo logo acima — não repetir um palpite por cima dele.
  # A mensagem antiga chutava "confira a conexão" para uma falha que costuma ser
  # pasta ocupada.
  git clone -q https://github.com/alvesoff/checkpoint.git "$DESTINO" \
    || erro "Could not clone Checkpoint into $DESTINO — the reason is right above." \
            "Não consegui clonar o Checkpoint em $DESTINO — o motivo está logo acima."
else
  # Retomando uma tentativa anterior. A pasta PRECISA virar a ponta do
  # origin/main — não "o que der".
  #
  # Este script veio do repositório de agora; a pasta pode ser de semanas atrás.
  # As duas metades discordam em silêncio: o pin da CLI do Plow, o
  # CHECKPOINT_REV, a lista de skills, e o AGENT_ID que as cópias anteriores a
  # 14/09 escreviam vazio. O fim disso é um agente que sobe, funciona e nunca
  # aparece no índice — e ninguém tem como perceber. "Seguindo com a que está
  # aqui" era o pior desfecho possível, disfarçado de aviso leve.
  #
  # O erro do git é mostrado. Ia para /dev/null, e aí nem quem instalou nem eu
  # conseguíamos saber por que a atualização falhou.
  ETAPA="atualizando a cópia local"
  if ! SAIDA_GIT=$(git -C "$DESTINO" fetch -q origin 2>&1); then
    msg "Could not update the copy in $DESTINO:" \
        "Não consegui atualizar a cópia em $DESTINO:"
    printf '%s\n' "$SAIDA_GIT" >&2
    # Não chutar "confira a conexão": um fetch falha tanto por rede quanto por
    # .git corrompido, origin renomeado ou index.lock de uma tentativa que foi
    # interrompida — e nesses três a rede está ótima. Apagar a pasta é o
    # caminho que resolve todos eles, e é o único testado do zero.
    erro "If it is not the network, remove the folder and run this again: rm -rf $DESTINO" \
         "Se não for a rede, apague a pasta e rode isto de novo: rm -rf $DESTINO"
  fi

  # `pull --ff-only` recusa cópia com HEAD destacado, com commit local ou com
  # arquivo alterado, e as três acontecem numa tentativa que parou no meio.
  # `checkout -B` resolve as duas primeiras sem descartar nada.
  if ! SAIDA_GIT=$(git -C "$DESTINO" checkout -B main origin/main 2>&1); then
    msg "The copy in $DESTINO has local changes to Checkpoint's own files." \
        "A cópia em $DESTINO tem alterações locais nos arquivos do próprio Checkpoint."
    # Descartar arquivo alterado é a única coisa aqui que apaga trabalho de
    # alguém, então pergunta. O que é da pessoa não está em jogo: .env,
    # plow-credentials e compose.override.yml estão no .gitignore e nenhum
    # comando daqui roda `git clean`. Medido antes de escrever esta linha.
    if confirmar "Discard them and use the published version? (.env, your credentials and your chosen folders are kept)" \
                 "Descartar essas alterações e usar a versão publicada? (o .env, suas credenciais e suas pastas escolhidas ficam)" s; then
      if ! SAIDA_GIT=$(git -C "$DESTINO" checkout -f -B main origin/main 2>&1); then
        printf '%s\n' "$SAIDA_GIT" >&2
        erro "Could not update it. Remove the folder and run this again: rm -rf $DESTINO" \
             "Não consegui atualizar. Apague a pasta e rode isto de novo: rm -rf $DESTINO"
      fi
    else
      erro "Then install into another folder, or remove this one: rm -rf $DESTINO" \
           "Então instale em outra pasta, ou apague esta: rm -rf $DESTINO"
    fi
  fi
fi
cd "$DESTINO"

# A CLI do Plow e executada aqui e e ela que faz o `mint` -- clonar o HEAD de
# um repositorio de terceiro e rodar o que vier e substituir codigo nao revisado
# debaixo de quem segura a credencial. Mesmo padrao do vendor/client.pin.
# Esta era a linha que encerrava a instalação com "código 1" e mais nada, logo
# depois de dizer que não conseguiu atualizar a cópia local.
#
# `X=$(cmd)` sozinho numa linha, sob `set -eu`, derruba o script inteiro quando
# cmd devolve não-zero — e `[ -f ausente ] && ...` devolve 1. Toda cópia
# anterior a 15/09 15:20 chega aqui sem o arquivo de pin, então a combinação
# "cópia velha + atualização que falhou" era morte certa e muda. Agora o teste
# é um `if`, cujo resultado o `set -e` não olha.
PLOW_SHA=""
if [ -f vendor/plow-agents.pin ]; then
  PLOW_SHA=$(sed -n 's/^sha=//p' vendor/plow-agents.pin | head -1)
fi
PLOW_REF="${PLOW_AGENTS_REF:-$PLOW_SHA}"
# Sem pin nenhum, o passo seguinte clonaria o HEAD da CLI que cria a credencial
# deste agente. Parar é a resposta certa, não seguir: é código de terceiro
# rodando com a chave na mão, e a regra do projeto é pinar por SHA.
[ -n "$PLOW_REF" ] || erro \
  "vendor/plow-agents.pin is missing, so the Plow CLI would be cloned unpinned. Remove $DESTINO and run this again." \
  "O arquivo vendor/plow-agents.pin não está aqui, e a CLI do Plow não vai ser clonada sem pin. Apague $DESTINO e rode isto de novo."
if [ ! -d tools/plow-agents ]; then
  git clone -q -c core.autocrlf=false https://github.com/plow-pbc/plow-agents.git tools/plow-agents \
    || erro "Could not clone the Plow CLI." "Nao consegui clonar a CLI do Plow."
fi
if [ -n "$PLOW_REF" ]; then
  git -C tools/plow-agents fetch -q origin "$PLOW_REF" 2>/dev/null || git -C tools/plow-agents fetch -q origin 2>/dev/null || true
  if ! git -C tools/plow-agents checkout -q "$PLOW_REF" 2>/dev/null; then
    # Pin velho nao pode virar falha obscura na maquina de quem instala: diga o
    # que houve e siga no que veio, que e melhor do que parar aqui.
    msg "Pinned Plow CLI revision not found; using whatever the clone has. Update vendor/plow-agents.pin." \
        "A revisao pinada da CLI do Plow nao existe mais; seguindo com a do clone. Atualize vendor/plow-agents.pin."
  fi
fi

# Sem isto a CLI do Plow nao consegue gravar o token no Windows, e a instalacao
# morre depois da ativacao por iMessage -- com a mensagem ja mandada e o codigo
# ja gasto. Roda toda vez porque o clone pode ser de agora e um git pull na CLI
# desfaz a edicao; aplicar duas vezes nao faz nada.
if [ -f tools/patch-plow-windows.py ]; then
  # So no Windows, e so ai a falha importa: em Mac e Linux a CLI grava o token
  # sem ajuda. Falhar calado aqui fazia a instalacao morrer depois da ativacao
  # por iMessage, com o codigo ja gasto -- o pior momento possivel.
  if ! $PY tools/patch-plow-windows.py tools/plow-agents/bin/plow-agents; then
    [ "$SO" = windows ] && erro       "Could not patch the Plow CLI for Windows; it would fail to save the token after you already spent the activation code."       "Nao consegui ajustar a CLI do Plow para Windows; ela falharia ao salvar o token depois de voce ja ter gasto o codigo de ativacao."
  fi
else
  msg "Local copy is older than this installer; the Plow CLI may fail to save the token on Windows."       "A cópia local é mais antiga que este instalador; no Windows a CLI do Plow pode falhar ao salvar o token."
fi

PLOW="$PY tools/plow-agents/bin/plow-agents"

# A CLI do Plow separa colunas por TAB, e um numero de telefone tem espaco
# dentro. Lido por posicao no separador padrao, "+1 555 0100" vira tres campos
# e o numero sai truncado. Cada leitura tenta TAB primeiro e so entao cai para
# espaco, para nao quebrar de novo se o formato mudar.
linha_livre() {
  L=$($PLOW lines 2>/dev/null | awk -F'\t' '$NF=="free"{print $1; exit}')
  [ -n "$L" ] || L=$($PLOW lines 2>/dev/null | awk '$NF=="free"{print $1; exit}')
  printf '%s' "$L"
}

# Numa reinstalacao a conta ja gastou a linha: nenhuma esta "free", e ainda
# assim e dela que sai o numero para textar.
linha_em_uso() {
  L=$($PLOW lines 2>/dev/null | awk -F'\t' 'NR>1 && $1!=""{print $1; exit}')
  [ -n "$L" ] || L=$($PLOW lines 2>/dev/null | awk 'NR>1 && $1!=""{print $1; exit}')
  printf '%s' "$L"
}

numero_da_linha() {
  [ -n "$1" ] || return 0
  N=$($PLOW lines 2>/dev/null | awk -F'\t' -v l="$1" '$1==l{print $3; exit}')
  [ -n "$N" ] || N=$($PLOW lines 2>/dev/null | awk -v l="$1" '$1==l{print $3; exit}')
  printf '%s' "$N"
}

# ---------------------------------------------------------------- pastas de código

ETAPA="escolhendo as pastas de projeto"

# Procura todo lugar onde a pessoa possa guardar projeto e conta os repositórios
# git de cada um. Monta TODOS os que tiverem repositório, não só o maior: quem
# separa trabalho de pessoal em duas pastas quer as duas acompanhadas.
#
# A sugestão é sempre confirmada. Montar a pasta de código de alguém sem
# perguntar seria abuso, mesmo sendo somente leitura.
CANDIDATAS=""
# Uma por linha, relativas ao HOME, para a lista poder crescer sem virar uma
# linha de duzentas colunas. As do OneDrive nao sao luxo: no Windows atual o
# Desktop e o Documentos costumam estar redirecionados para la, e entao os
# caminhos sem OneDrive simplesmente nao existem.
while IFS= read -r relativo; do
  [ -n "$relativo" ] || continue
  candidata="$HOME/$relativo"
  [ -d "$candidata" ] || continue
  n=$(find "$candidata" -maxdepth 2 -name .git -type d 2>/dev/null | wc -l | tr -d " ")
  [ "$n" -gt 0 ] && CANDIDATAS="$CANDIDATAS$candidata|$n
"
done <<'LUGARES'
code
projects
Projetos
dev
src
repos
git
workspace
Desktop/Projetos
Desktop/projects
Desktop/code
Documents/GitHub
Documents/Projetos
OneDrive/Desktop/Projetos
OneDrive/Desktop/projects
OneDrive/Desktop/code
OneDrive/Documents/GitHub
OneDrive/Documentos/GitHub
OneDrive/Projetos
OneDrive/code
LUGARES

ESCOLHIDAS=""
if [ -n "$CANDIDATAS" ]; then
  msg "Folders with git repositories found here:" "Pastas com repositórios git encontradas:"
  printf '%s' "$CANDIDATAS" | while IFS="|" read -r pasta n; do
    [ -n "$pasta" ] && printf '    %-45s %s
' "$pasta" "$(msg "$n repositories" "$n repositórios")"
  done
  echo
  if confirmar "Watch all of them?" "Acompanhar todas?" s; then
    ESCOLHIDAS=$(printf '%s' "$CANDIDATAS" | cut -d"|" -f1)
  else
    # Uma a uma, para quem quer deixar a pasta pessoal de fora.
    ESCOLHIDAS=""
    # `for` sobre $(...) quebra no espaco: um perfil do Windows chamado
    # "Ana Paula" viraria duas perguntas, nenhuma das duas uma pasta real.
    while IFS= read -r linha; do
      [ -n "$linha" ] || continue
      confirmar "  $linha ?" "  $linha ?" s && ESCOLHIDAS="$ESCOLHIDAS$linha
"
    done <<CANDIDATAS_ESCOLHA
$(printf '%s' "$CANDIDATAS" | cut -d"|" -f1)
CANDIDATAS_ESCOLHA
  fi
fi

# Sem saida, este laco e infinito numa maquina sem projeto nenhum — a recem
# formatada, e a de quem so quer testar a instalacao. Entao Enter vazio tem
# resposta: cria uma pasta e segue, ou para com um motivo dito em voz alta.
while [ -z "$(printf '%s' "$ESCOLHIDAS" | tr -d '[:space:]')" ]; do
  msg "Paste the folder that CONTAINS your projects. A Windows path works." \
      "Cole a pasta que CONTÉM seus projetos. Caminho do Windows serve."
  entrada=$(normalizar_caminho "$(perguntar "Folder (Enter to skip):" "Pasta (Enter para pular):")")
  if [ -z "$entrada" ]; then
    if confirmar "No folder given. Create $HOME/projects and use that?" \
                 "Nenhuma pasta informada. Criar $HOME/projects e usar essa?" s; then
      mkdir -p "$HOME/projects"
      ESCOLHIDAS="$HOME/projects
"
    else
      erro "The agent needs at least one folder to watch." \
           "O agente precisa de pelo menos uma pasta para acompanhar."
    fi
  elif [ -d "$entrada" ]; then
    ESCOLHIDAS="$entrada
"
  else
    msg "That path does not exist: $entrada" "Esse caminho não existe: $entrada"
  fi
done

# A primeira vai no CODE_DIR (o compose.yml já a monta em /projects); as demais
# entram por um override, cada uma em /projects/<nome>. Repositório novo dentro
# de qualquer uma delas é encontrado na próxima varredura, sem reinstalar nada —
# só uma pasta-raiz nova exige rodar isto de novo.
# Se todas as escolhidas dividem o mesmo pai, oferecer o pai: assim uma pasta
# nova criada ali dentro passa a ser acompanhada sozinha, sem reinstalar. O
# HOME nunca entra nessa conta -- ali moram .ssh, .aws e .docker, e este agente
# tem uma skill que procura segredo em arquivo solto e conta para o dono.
PAI=""
if [ "$(printf '%s' "$ESCOLHIDAS" | sed '/^$/d' | wc -l | tr -d ' ')" -gt 1 ]; then
  PAIS=$(printf '%s' "$ESCOLHIDAS" | sed '/^$/d' | while IFS= read -r e; do dirname "$e"; done | sort -u)
  if [ "$(printf '%s
' "$PAIS" | sed '/^$/d' | wc -l | tr -d ' ')" -eq 1 ]; then
    case "$PAIS" in
      "$HOME"|"$HOME"/|/|//*|?:/|?:) ;;
      *) [ -d "$PAIS" ] && PAI="$PAIS";;
    esac
  fi
fi
if [ -n "$PAI" ]; then
  echo
  msg "All of them live in $PAI." "Todas elas estão em $PAI."
  if confirmar "Watch $PAI itself? A new folder there is then picked up on its own."                "Acompanhar $PAI inteiro? Aí uma pasta nova ali já entra sozinha." s; then
    ESCOLHIDAS="$PAI
"
  fi
fi

# A pasta com MAIS repositorios vira a raiz. Escolher pela ordem do heredoc
# elegia a primeira que existisse: numa maquina com uma pasta de 1 repo e outra
# de 25, a de 1 virava a principal e a de 25 ia para o override.
CODE_DIR=""
MAIOR=-1
while IFS= read -r escolhida; do
  [ -n "$escolhida" ] || continue
  n=$(printf '%s' "$CANDIDATAS" | awk -F'|' -v p="$escolhida" '$1==p{print $2; exit}')
  [ -n "$n" ] || n=$(find "$escolhida" -maxdepth 2 -name .git -type d 2>/dev/null | wc -l | tr -d " ")
  if [ "$n" -gt "$MAIOR" ]; then MAIOR=$n; CODE_DIR=$escolhida; fi
done <<ESCOLHA_RAIZ
$ESCOLHIDAS
ESCOLHA_RAIZ
EXTRAS=$(printf '%s' "$ESCOLHIDAS" | grep -vxF "$CODE_DIR" | sed '/^$/d')

# Havendo mais de uma pasta, NENHUMA pode ir para /projects: esse caminho vira
# um bind somente leitura e o Docker nao consegue criar /projects/<nome> dentro
# dele. O daemon recusa com "read-only file system", exit 125, e o instalador
# traduzia isso como "Build failed" — no caminho PADRAO (Enter = sim). Entao,
# havendo extras, todas descem um nivel: /projects passa a ser diretorio do
# proprio container e cada pasta monta em /projects/<nome>. O scan ja procura
# ate dois niveis abaixo da raiz, que era o desenho pretendido desde o inicio.
CODE_TARGET=""
rm -f compose.override.yml
if [ -n "$(printf '%s' "$EXTRAS" | tr -d '[:space:]')" ]; then
  CODE_TARGET="/projects/$(basename "$CODE_DIR")"
  {
    echo "# Gerado pelo install.sh: as demais pastas de código, somente leitura."
    echo "services:"
    echo "  agent:"
    echo "    volumes:"
    USADOS=" $(basename "$CODE_DIR") "
    printf '%s
' "$EXTRAS" | while read -r extra; do
      [ -n "$extra" ] || continue
      nome=$(basename "$extra")
      # Duas pastas "code" em lugares diferentes montariam no mesmo alvo e uma
      # delas sumiria sem nenhum aviso.
      case "$USADOS" in *" $nome "*) nome="$nome-$(printf '%s' "$extra" | cksum | cut -d' ' -f1)";; esac
      USADOS="$USADOS$nome "
      # Sintaxe longa de proposito: na curta o compose separa por ":", e um
      # caminho do Windows ja traz um (C:/Users/...) enquanto um nome de perfil
      # com espaco traz outro problema. Assim source e target sao campos.
      echo "      - type: bind"
      echo "        source: \"$extra\""
      echo "        target: \"/projects/$nome\""
      echo "        read_only: true"
    done
  } > compose.override.yml
  msg "Extra folders written to compose.override.yml" "Pastas extras gravadas em compose.override.yml"
fi

# ---------------------------------------------------------------- fuso

ETAPA="descobrindo o fuso horário"

# No Windows nao existe /etc/localtime, entao ate aqui o fuso caia direto no
# chute por idioma -- e quem instalasse em ingles recebia UTC com SIM como
# resposta padrao. Um agente que fala "sua reuniao e as 12h" com o fuso errado
# erra todo horario, inclusive o do cutucao automatico.
FUSO=""
if [ -L /etc/localtime ]; then
  FUSO=$(readlink /etc/localtime | sed 's|.*/zoneinfo/||')
fi
[ -n "$FUSO" ] || FUSO="${TZ:-}"
if [ -z "$FUSO" ] && [ "$SO" = windows ]; then
  # .NET 6+ converte o nome do fuso do Windows ("E. South America Standard
  # Time") para o nome IANA que o container entende.
  for PS in pwsh powershell.exe powershell; do
    command -v "$PS" >/dev/null 2>&1 || continue
    FUSO=$("$PS" -NoProfile -Command '
      $i = $null
      if ([System.TimeZoneInfo]::TryConvertWindowsIdToIanaId([System.TimeZoneInfo]::Local.Id, [ref]$i)) { $i }
    ' 2>/dev/null | tr -d '\r' | head -1)
    [ -n "$FUSO" ] && break
  done
fi
if [ -z "$FUSO" ]; then
  # Ultimo recurso antes do chute: o deslocamento de agora. Perde horario de
  # verao, mas erra por uma hora em vez de errar por tres.
  OFF=$(date +%z 2>/dev/null)
  case "$OFF" in
    [+-][0-9][0-9]00)
      H=$(printf '%s' "$OFF" | cut -c2-3 | sed 's/^0//')
      # Etc/GMT tem o sinal invertido de proposito: Etc/GMT+3 e UTC-3.
      [ "$(printf '%s' "$OFF" | cut -c1)" = "-" ] && FUSO="Etc/GMT+${H:-0}" || FUSO="Etc/GMT-${H:-0}"
      ;;
  esac
fi
[ -n "$FUSO" ] || FUSO=$([ "$IDIOMA" = pt ] && echo "America/Sao_Paulo" || echo "UTC")
confirmar "Timezone $FUSO — is that right?" "Fuso horário $FUSO — está certo?" s \
  || FUSO=$(perguntar "Timezone (e.g. America/Sao_Paulo):" "Fuso horário (ex.: America/Sao_Paulo):")

# ---------------------------------------------------------------- linha e credencial

ETAPA="criando a linha e a credencial do Plow"

# Este e o passo com mais desistencia do instalador, por dois motivos que nao
# sao culpa de quem instala: ele e manual no meio de um processo automatico, e a
# saida vem da CLI do Plow, em ingles, dizendo o que digitar mas nao o que fazer.
# Traduzir a saida dela nao da -- e processo de terceiro, esperando em tempo
# real. O que da e dizer antes o que vai aparecer e o que fazer com aquilo.
tutorial_da_linha() {
  if [ "$IDIOMA" = pt ]; then
    cat <<'PT'
Agora a linha telefônica. Este passo é manual, e a saída abaixo vem em inglês,
assim:

    Text  Plow Activate: XXXXX  to  +1 650 ...
    Waiting for that text ...

O que fazer, na ordem:

  1. Abra o app Mensagens (iMessage) no seu iPhone ou Mac.
  2. Comece uma mensagem para o número que aparecer depois de "to".
  3. Mande exatamente o texto que aparecer entre "Text" e "to", com o código.
  4. Volte aqui e espere. O terminal segue sozinho quando a mensagem chegar —
     "Waiting for that text ..." é justamente ele esperando.

Três coisas que costumam derrubar este passo:

  - O código vale 15 minutos e serve uma vez só. Se expirar, rode de novo.
  - Quem manda a mensagem vira o dono do agente. Mande do seu próprio telefone.
  - É iMessage. Sem iPhone nem Mac, este passo não tem como ser concluído.
PT
  else
    cat <<'EN'
Now the phone line. This step is manual, and the output below comes from Plow,
like this:

    Text  Plow Activate: XXXXX  to  +1 650 ...
    Waiting for that text ...

What to do, in order:

  1. Open Messages (iMessage) on your iPhone or Mac.
  2. Start a message to the number shown after "to".
  3. Send exactly the text shown between "Text" and "to", code included.
  4. Come back here and wait. The terminal moves on by itself once the message
     lands -- "Waiting for that text ..." is it waiting.

Three things that usually break this step:

  - The code lasts 15 minutes and works once. If it expires, run this again.
  - Whoever sends the message becomes the owner. Send it from your own phone.
  - It is iMessage. Without an iPhone or a Mac, this step cannot be completed.
EN
  fi
}

if [ ! -f plow-credentials ]; then
  echo
  tutorial_da_linha
  echo
  # Sem token de conta salvo, `lines` falha por falta de login, e não por
  # falta de linha. Confundir as duas coisas faz o instalador oferecer uma
  # linha nova -- que não tem como desfazer -- a quem já tem uma parada na
  # conta. Então: primeiro entrar, depois olhar o que existe.
  if ! $PLOW lines >/dev/null 2>&1; then
    $PLOW login || {
      msg "That login did not go through. That happens when the account does not exist yet." \
          "Esse login não foi concluído. Acontece quando a conta ainda não existe."
      confirmar "Ask Plow for a new account and line? (cannot be undone)" \
                "Pedir ao Plow uma conta e uma linha novas? (não dá para desfazer)" s \
        || erro "Cannot continue without a line." "Não dá para continuar sem uma linha."
      $PLOW login --new-line || erro "Login failed." "Login falhou."
    }
  fi

  # --new-line aloca um número na conta e não tem como desfazer, então só
  # entra em cena depois de olhar as linhas que a conta já tem.
  LINHA=$(linha_livre)
  if [ -z "$LINHA" ]; then
    confirmar "No free line on this account. Ask Plow for one? (cannot be undone)" \
              "Nenhuma linha livre nesta conta. Pedir uma ao Plow? (não dá para desfazer)" s \
      || erro "Cannot continue without a line." "Não dá para continuar sem uma linha."
    $PLOW login --new-line || erro "Login failed." "Login falhou."
    LINHA=$(linha_livre)
    [ -n "$LINHA" ] || erro "Still no free line on this account." "Continua sem linha livre nesta conta."
  fi
  msg "Using line $LINHA." "Usando a linha $LINHA."
  $PLOW mint "$LINHA" || erro "Could not mint the credential." "Não consegui gerar a credencial."
fi

# ---------------------------------------------------------------- configurar e subir

ETAPA="construindo e subindo o container"

# O AGENT_ID diz ao reporter PARA QUAL agente do indice ele reporta. Vazio, o
# servico `agent-index` fica parado de proposito ("standing down") e a
# instalacao inteira nunca aparece no placar publico.
#
# Ficou vazio aqui e passou despercebido porque a maquina de desenvolvimento
# tinha o valor preenchido a mao no .env: funcionava para nos e falhava em
# silencio para todo mundo que instalasse. O reporter e o UNICO requisito
# obrigatorio do hackathon, e `install_success` conta quem REPORTOU uso.
cat > .env <<EOF
CODE_DIR=$CODE_DIR
CODE_TARGET=${CODE_TARGET:-/projects}
TZ=$FUSO
AGENT_ID=checkpoint
EOF

echo
msg "Building the image (first time takes a few minutes)..." \
    "Construindo a imagem (a primeira vez demora alguns minutos)..."
# O rev vai na INVOCACAO, nao no .env: gravado, ele envelheceria no primeiro
# `git pull` e o agente passaria a jurar que esta atrasado para sempre --
# inclusive logo depois de a pessoa ter atualizado. Ausente vira
# "desconhecido", e o verificador responde que nao sabe, que e honesto.
CHECKPOINT_REV="$(git -C "$DESTINO" rev-parse HEAD 2>/dev/null || echo desconhecido)" \
  "$DOCKER" compose up --build -d || erro "Build failed." "A construção falhou."

# O pior modo de falha medido neste projeto: a imagem constroi, o container
# sobe, e o runtime "estaciona" por credencial recusada sem nunca abrir o
# gateway. Ate aqui o script dizia "Pronto" por cima de um agente mudo.
msg "Checking that the agent actually came up..." \
    "Conferindo se o agente subiu de verdade..."
ESTACIONADO=""
i=0
while [ "$i" -lt 25 ]; do
  LOGS=$("$DOCKER" compose logs --no-color agent 2>/dev/null || true)
  case "$LOGS" in
    *"parking; no gateway will start"*) ESTACIONADO="sim"; break;;
    *"Gateway started"*|*gateway*istening*) break;;
  esac
  i=$((i + 1))
  sleep 1
done
if [ -n "$ESTACIONADO" ]; then
  msg "The agent started but PARKED: the credential was refused." \
      "O agente subiu mas ESTACIONOU: a credencial foi recusada."
  msg "Delete plow-credentials and run this again to mint a new one." \
      "Apague plow-credentials e rode isto de novo para gerar outra."
  erro "Agent parked; it will not answer." "Agente estacionado; ele nao vai responder."
fi

# LINHA so existe quando ESTE run passou pelo mint. Numa reinstalacao sobre uma
# credencial que ja existe o bloco e pulado, e `awk -v l="$LINHA"` sob `set -eu`
# matava o script com "LINHA: unbound variable" DEPOIS do build dar certo e
# ANTES de imprimir o numero — justamente na segunda tentativa, que e onde a
# taxa de instalacao se recupera.
[ -n "${LINHA:-}" ] || LINHA=$(linha_em_uso)
NUMERO=$(numero_da_linha "${LINHA:-}")
echo
msg "Done. Text this number and ask: where did I leave off?" \
    "Pronto. Mande uma mensagem para este número e pergunte: onde eu parei?"
if [ -n "${NUMERO:-}" ]; then
  printf '\n    %s\n\n' "$NUMERO"
else
  msg "Could not read the number here. Run: $PLOW lines" \
      "Nao consegui ler o numero aqui. Rode: $PLOW lines"
fi
msg "Logs:   $DOCKER compose logs -f agent" "Logs:   $DOCKER compose logs -f agent"
msg "Folder: $DESTINO" "Pasta:  $DESTINO"
