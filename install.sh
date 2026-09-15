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

erro() { msg "$1" "$2" >&2; exit 1; }

# ---------------------------------------------------------------- pré-requisitos

msg "Checkpoint — installer" "Checkpoint — instalador"
echo

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
"$DOCKER" --version >/dev/null 2>&1 || erro \
  "Docker not found. Install Docker Desktop (or the docker engine) and run this again." \
  "Docker não encontrado. Instale o Docker Desktop (ou o engine) e rode de novo."

"$DOCKER" info >/dev/null 2>&1 || erro \
  "Docker is installed but not running. Start it and run this again." \
  "O Docker está instalado mas não está rodando. Abra ele e rode de novo."

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

# ---------------------------------------------------------------- onde instalar

DESTINO="${CHECKPOINT_DIR:-$HOME/checkpoint}"
if [ -e "$DESTINO" ]; then
  # Uma pasta que ja tem o repo clonado dentro nao e uma pasta ocupada por
  # engano: e uma tentativa anterior que parou no meio, e a instalacao demora
  # o bastante para isso ser comum. Ai o padrao e continuar. Qualquer outra
  # pasta que ja exista continua com o padrao seguro, que e nao mexer.
  if [ -d "$DESTINO/.git" ] && [ -f "$DESTINO/compose.yml" ]; then
    confirmar "Found an earlier install in $DESTINO. Continue from it?" \
              "Encontrei uma instalação anterior em $DESTINO. Continuar dela?" s \
      || DESTINO=$(normalizar_caminho "$(perguntar "Install into which directory?" "Instalar em qual pasta?")")
  else
    confirmar "Directory $DESTINO already exists. Use it anyway?" \
              "A pasta $DESTINO já existe. Usar assim mesmo?" n \
      || DESTINO=$(normalizar_caminho "$(perguntar "Install into which directory?" "Instalar em qual pasta?")")
  fi
fi
[ -n "$DESTINO" ] || erro "No directory given." "Nenhuma pasta informada."

# -c core.autocrlf=false não é necessário para este repo (o .gitattributes fixa
# LF), mas é para o plow-agents, que não tem um.
if [ ! -d "$DESTINO/.git" ]; then
  git clone -q https://github.com/alvesoff/checkpoint.git "$DESTINO"
else
  # Retomando uma tentativa anterior: o clone que esta ali pode ser de antes da
  # correcao que a pessoa esta tentando usar agora. --ff-only nunca reescreve
  # trabalho local; se nao der, segue com o que ja existe.
  git -C "$DESTINO" pull -q --ff-only 2>/dev/null || msg     "Could not update the local copy. Continuing with what is there."     "Não consegui atualizar a cópia local. Seguindo com a que está aqui."
fi
cd "$DESTINO"

[ -d tools/plow-agents ] || git clone -q -c core.autocrlf=false https://github.com/plow-pbc/plow-agents.git tools/plow-agents

# Sem isto a CLI do Plow nao consegue gravar o token no Windows, e a instalacao
# morre depois da ativacao por iMessage -- com a mensagem ja mandada e o codigo
# ja gasto. Roda toda vez porque o clone pode ser de agora e um git pull na CLI
# desfaz a edicao; aplicar duas vezes nao faz nada.
if [ -f tools/patch-plow-windows.py ]; then
  $PY tools/patch-plow-windows.py tools/plow-agents/bin/plow-agents
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

FUSO=""
if [ -L /etc/localtime ]; then
  FUSO=$(readlink /etc/localtime | sed 's|.*/zoneinfo/||')
fi
[ -n "$FUSO" ] || FUSO=$([ "$IDIOMA" = pt ] && echo "America/Sao_Paulo" || echo "UTC")
confirmar "Timezone $FUSO — is that right?" "Fuso horário $FUSO — está certo?" s \
  || FUSO=$(perguntar "Timezone (e.g. America/Sao_Paulo):" "Fuso horário (ex.: America/Sao_Paulo):")

# ---------------------------------------------------------------- linha e credencial

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
