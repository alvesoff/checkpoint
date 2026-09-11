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

perguntar() { # perguntar <rotulo en> <rotulo pt> ; ecoa a resposta
  rotulo=$([ "$IDIOMA" = pt ] && printf '%s' "$2" || printf '%s' "$1")
  printf '%s ' "$rotulo"
  read -r valor <&3 || valor=""
  printf '%s' "$valor"
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
  confirmar "Directory $DESTINO already exists. Use it anyway?" \
            "A pasta $DESTINO já existe. Usar assim mesmo?" n \
    || DESTINO=$(perguntar "Install into which directory?" "Instalar em qual pasta?")
fi
[ -n "$DESTINO" ] || erro "No directory given." "Nenhuma pasta informada."

# -c core.autocrlf=false não é necessário para este repo (o .gitattributes fixa
# LF), mas é para o plow-agents, que não tem um.
if [ ! -d "$DESTINO/.git" ]; then
  git clone -q https://github.com/alvesoff/checkpoint.git "$DESTINO"
fi
cd "$DESTINO"

[ -d tools/plow-agents ] || git clone -q -c core.autocrlf=false https://github.com/plow-pbc/plow-agents.git tools/plow-agents
PLOW="$PY tools/plow-agents/bin/plow-agents"

# ---------------------------------------------------------------- pastas de código

# Procura todo lugar onde a pessoa possa guardar projeto e conta os repositórios
# git de cada um. Monta TODOS os que tiverem repositório, não só o maior: quem
# separa trabalho de pessoal em duas pastas quer as duas acompanhadas.
#
# A sugestão é sempre confirmada. Montar a pasta de código de alguém sem
# perguntar seria abuso, mesmo sendo somente leitura.
CANDIDATAS=""
for candidata in "$HOME/code" "$HOME/projects" "$HOME/Projetos" "$HOME/dev" "$HOME/src"                  "$HOME/repos" "$HOME/git" "$HOME/workspace"                  "$HOME/Desktop/Projetos" "$HOME/Desktop/projects" "$HOME/Desktop/code"                  "$HOME/Documents/GitHub" "$HOME/Documents/Projetos"; do
  [ -d "$candidata" ] || continue
  n=$(find "$candidata" -maxdepth 2 -name .git -type d 2>/dev/null | wc -l | tr -d " ")
  [ "$n" -gt 0 ] && CANDIDATAS="$CANDIDATAS$candidata|$n
"
done

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
    for linha in $(printf '%s' "$CANDIDATAS" | cut -d"|" -f1); do
      confirmar "  $linha ?" "  $linha ?" s && ESCOLHIDAS="$ESCOLHIDAS$linha
"
    done
  fi
fi

while [ -z "$(printf '%s' "$ESCOLHIDAS" | tr -d '[:space:]')" ]; do
  entrada=$(perguntar "Full path of a folder that CONTAINS your projects:"                       "Caminho completo de uma pasta que CONTÉM seus projetos:")
  if [ -d "$entrada" ]; then
    ESCOLHIDAS="$entrada
"
  else
    msg "That path does not exist." "Esse caminho não existe."
  fi
done

# A primeira vai no CODE_DIR (o compose.yml já a monta em /projects); as demais
# entram por um override, cada uma em /projects/<nome>. Repositório novo dentro
# de qualquer uma delas é encontrado na próxima varredura, sem reinstalar nada —
# só uma pasta-raiz nova exige rodar isto de novo.
CODE_DIR=$(printf '%s' "$ESCOLHIDAS" | head -1)
EXTRAS=$(printf '%s' "$ESCOLHIDAS" | tail -n +2)

rm -f compose.override.yml
if [ -n "$(printf '%s' "$EXTRAS" | tr -d '[:space:]')" ]; then
  {
    echo "# Gerado pelo install.sh: as demais pastas de código, somente leitura."
    echo "services:"
    echo "  agent:"
    echo "    volumes:"
    printf '%s
' "$EXTRAS" | while read -r extra; do
      [ -n "$extra" ] || continue
      echo "      - $extra:/projects/$(basename "$extra"):ro"
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

if [ ! -f plow-credentials ]; then
  echo
  msg "Now the phone line. Plow will print a phrase — text that WHOLE phrase from your phone." \
      "Agora a linha telefônica. O Plow vai imprimir uma frase — mande a frase INTEIRA do seu celular."
  echo
  if $PLOW lines 2>/dev/null | grep -q free; then
    $PLOW login || erro "Login failed." "Login falhou."
  else
    # --new-line aloca um número na conta e não tem como desfazer, então só é
    # usado quando não existe nenhuma linha livre.
    confirmar "You have no free line. Ask Plow for one? (cannot be undone)" \
              "Você não tem linha livre. Pedir uma ao Plow? (não dá para desfazer)" s \
      || erro "Cannot continue without a line." "Não dá para continuar sem uma linha."
    $PLOW login --new-line || erro "Login failed." "Login falhou."
  fi

  LINHA=$($PLOW lines 2>/dev/null | awk '$NF=="free"{print $1; exit}')
  [ -n "$LINHA" ] || erro "No free line on this account." "Nenhuma linha livre nesta conta."
  msg "Using line $LINHA." "Usando a linha $LINHA."
  $PLOW mint "$LINHA" || erro "Could not mint the credential." "Não consegui gerar a credencial."
fi

# ---------------------------------------------------------------- configurar e subir

cat > .env <<EOF
CODE_DIR=$CODE_DIR
TZ=$FUSO
AGENT_ID=
PANEL_USER=dev
PANEL_PASS=$(head -c 12 /dev/urandom 2>/dev/null | od -An -tx1 | tr -d ' \n' || echo checkpoint)
EOF

echo
msg "Building the image (first time takes a few minutes)..." \
    "Construindo a imagem (a primeira vez demora alguns minutos)..."
"$DOCKER" compose up --build -d || erro "Build failed." "A construção falhou."

NUMERO=$($PLOW lines 2>/dev/null | awk -v l="$LINHA" '$1==l{print $3}')
echo
msg "Done. Text this number and ask: where did I leave off?" \
    "Pronto. Mande uma mensagem para este número e pergunte: onde eu parei?"
[ -n "${NUMERO:-}" ] && printf '\n    %s\n\n' "$NUMERO"
msg "Logs:   $DOCKER compose logs -f agent" "Logs:   $DOCKER compose logs -f agent"
msg "Folder: $DESTINO" "Pasta:  $DESTINO"
