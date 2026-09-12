#Requires -Version 5.1
<#
  Instalador do Checkpoint para PowerShell.

      irm https://raw.githubusercontent.com/alvesoff/checkpoint/main/install.ps1 | iex

  Existe porque no Windows o terminal que a pessoa abre é o PowerShell, e o
  comando do README falha ali: `curl` é alias de Invoke-WebRequest e `sh` não
  existe. Quem copia, cola e vê um erro desiste — e desistência conta como
  instalação falha no índice.

  Não há duas versões do instalador. Este script encontra o bash que o Git for
  Windows já trouxe e entrega o install.sh para ele: a lógica de instalar mora
  em um lugar só, e uma correção feita lá vale para os dois caminhos.

  Tudo vive dentro de uma função porque com `irm | iex` um `exit` fecharia a
  janela do usuário no meio de uma mensagem de erro.
#>

function Invoke-CheckpointInstall {
  $ErrorActionPreference = 'Stop'
  # No PowerShell 7 um comando nativo que sai com codigo diferente de zero
  # pode virar erro terminante, dependendo da versao. Aqui isso trocaria a
  # mensagem escrita para a pessoa por um stack trace: o codigo de saida do
  # winget, do docker e do proprio install.sh e lido a mao, logo abaixo.
  $PSNativeCommandUseErrorActionPreference = $false

  $pt = (Get-Culture).Name -like 'pt-*'
  function T([string]$en, [string]$ptBr) { if ($pt) { $ptBr } else { $en } }

  Write-Host (T 'Checkpoint - installer' 'Checkpoint - instalador')
  Write-Host ''

  # ----------------------------------------------------------- achar o bash
  #
  # `bash.exe` no PATH não serve como primeira escolha: no Windows esse nome
  # costuma ser o do WSL, que enxerga outro sistema de arquivos e nem sempre
  # alcança o Docker Desktop. O bash certo é o que veio junto com o git, então
  # ele é procurado a partir do próprio git.exe.
  $bash = $null

  $git = Get-Command git.exe -ErrorAction SilentlyContinue
  if ($git) {
    $raizGit = Split-Path (Split-Path $git.Source -Parent) -Parent
    $candidato = Join-Path $raizGit 'bin\bash.exe'
    if (Test-Path $candidato) { $bash = $candidato }
  }

  if (-not $bash) {
    foreach ($caminho in @(
        "$env:ProgramFiles\Git\bin\bash.exe",
        "${env:ProgramFiles(x86)}\Git\bin\bash.exe",
        "$env:LOCALAPPDATA\Programs\Git\bin\bash.exe")) {
      if ($caminho -and (Test-Path $caminho)) { $bash = $caminho; break }
    }
  }

  if (-not $bash) {
    $doPath = Get-Command bash.exe -ErrorAction SilentlyContinue
    if ($doPath -and $doPath.Source -notlike "$env:WINDIR*") { $bash = $doPath.Source }
  }

  # ----------------------------------------------------------- instalar o git
  #
  # O install.sh exige git de qualquer forma. Instalar aqui resolve o git e o
  # bash de uma vez — mas pergunta antes, como todo passo que muda a máquina.
  if (-not $bash) {
    Write-Host (T 'Git for Windows was not found, and the installer needs it (it also provides bash).' `
                  'O Git for Windows não foi encontrado, e o instalador precisa dele (é ele que traz o bash).')

    if (Get-Command winget.exe -ErrorAction SilentlyContinue) {
      $r = Read-Host (T 'Install it now with winget? [Y/n]' 'Instalar agora pelo winget? [S/n]')
      if ($r -match '^(n|no|nao|não)$') {
        Write-Host (T 'Install it from https://git-scm.com/download/win and run this again.' `
                      'Instale por https://git-scm.com/download/win e rode de novo.')
        return
      }
      winget.exe install --id Git.Git -e --source winget --accept-package-agreements --accept-source-agreements
      foreach ($caminho in @(
          "$env:ProgramFiles\Git\bin\bash.exe",
          "${env:ProgramFiles(x86)}\Git\bin\bash.exe",
          "$env:LOCALAPPDATA\Programs\Git\bin\bash.exe")) {
        if ($caminho -and (Test-Path $caminho)) { $bash = $caminho; break }
      }
    }

    if (-not $bash) {
      Write-Host (T 'Still no bash. Install Git for Windows from https://git-scm.com/download/win and run this again.' `
                    'Ainda sem bash. Instale o Git for Windows por https://git-scm.com/download/win e rode de novo.')
      return
    }
  }

  # ----------------------------------------------------------- o docker
  #
  # O install.sh sabe checar o Docker, mas no Windows ele só pode reclamar: quem
  # abre o Docker Desktop é o Windows. Parar a instalação para mandar a pessoa
  # abrir um programa e começar de novo aqui é atrito puro, e atrito no meio da
  # instalação é desistência.
  #
  # Abrir o Docker não muda nada na máquina e é o que a pessoa faria em seguida,
  # então acontece sozinho. Instalar o Docker muda, então pergunta antes.

  function Find-DockerCli {
    $c = Get-Command docker.exe -ErrorAction SilentlyContinue
    if ($c) { return $c.Source }
    foreach ($base in @($env:ProgramFiles, ${env:ProgramFiles(x86)}) | Where-Object { $_ }) {
      $p = Join-Path $base 'Docker\Docker\resources\bin\docker.exe'
      if (Test-Path $p) { return $p }
    }
    return $null
  }

  function Test-DockerUp([string]$cli) {
    if (-not $cli) { return $false }
    # `docker info` com o motor parado escreve em stderr e sai diferente de
    # zero. As duas coisas sao a resposta esperada aqui, nao uma falha, e a
    # atribuicao local mantem isso dentro desta funcao.
    $ErrorActionPreference = 'Continue'
    & $cli info 2>&1 | Out-Null
    return ($LASTEXITCODE -eq 0)
  }

  $docker = Find-DockerCli

  # -------- não instalado: oferece o winget
  if (-not $docker) {
    Write-Host (T 'Docker Desktop was not found, and the agent runs in a container.' `
                  'O Docker Desktop não foi encontrado, e o agente roda em container.')

    if (-not (Get-Command winget.exe -ErrorAction SilentlyContinue)) {
      Write-Host (T 'Install it from https://docs.docker.com/desktop/install/windows-install/ and run this again.' `
                    'Instale por https://docs.docker.com/desktop/install/windows-install/ e rode de novo.')
      return
    }

    $r = Read-Host (T 'Install it now with winget? Large download, and Windows will ask for permission. [Y/n]' `
                      'Instalar agora pelo winget? É um download grande e o Windows vai pedir permissão. [S/n]')
    if ($r -match '^(n|no|nao)$') {
      Write-Host (T 'Nothing was installed.' 'Nada foi instalado.')
      return
    }

    winget.exe install --id Docker.DockerDesktop -e --source winget --accept-package-agreements --accept-source-agreements
    $docker = Find-DockerCli

    if (-not $docker) {
      Write-Host ''
      Write-Host (T 'Docker was installed but is not visible yet. Windows usually needs a restart here, for WSL2. Restart and run this again.' `
                    'O Docker foi instalado mas ainda não aparece. Normalmente o Windows precisa reiniciar aqui, por causa do WSL2. Reinicie e rode de novo.')
      return
    }
  }

  # -------- instalado mas parado: abre e espera
  if (-not (Test-DockerUp $docker)) {
    $app = $null
    foreach ($base in @($env:ProgramFiles, ${env:ProgramFiles(x86)}) | Where-Object { $_ }) {
      $p = Join-Path $base 'Docker\Docker\Docker Desktop.exe'
      if (Test-Path $p) { $app = $p; break }
    }

    if (-not $app) {
      Write-Host (T 'Docker is installed but not running, and I could not find Docker Desktop to open. Start it and run this again.' `
                    'O Docker está instalado mas parado, e não achei o Docker Desktop para abrir. Abra ele e rode de novo.')
      return
    }

    Write-Host (T 'Docker is not running. Opening Docker Desktop and waiting for it.' `
                  'O Docker não está rodando. Abrindo o Docker Desktop e esperando.')
    # A primeira abertura pede aceite dos termos, e aí a espera depende de um
    # clique. Sem este aviso, a fila de pontos parece travamento.
    Write-Host (T 'If a window asks you to accept terms, accept it - the wait ends right after.' `
                  'Se abrir uma janela pedindo aceite dos termos, aceite - a espera termina logo depois.')

    Start-Process -FilePath $app | Out-Null

    # Quatro minutos: um Docker Desktop subindo pela primeira vez, com o WSL2
    # frio, passa de um minuto sem dificuldade. Desistir antes manda a pessoa
    # reinstalar o que já estava funcionando.
    $limite = (Get-Date).AddMinutes(4)
    while ((Get-Date) -lt $limite) {
      Start-Sleep -Seconds 3
      if (Test-DockerUp $docker) { break }
      Write-Host '.' -NoNewline
    }
    Write-Host ''

    if (-not (Test-DockerUp $docker)) {
      Write-Host (T 'Docker did not come up in four minutes. Check the Docker Desktop window and run this again.' `
                    'O Docker não subiu em quatro minutos. Veja a janela do Docker Desktop e rode de novo.')
      return
    }

    Write-Host (T 'Docker is up.' 'Docker no ar.')
    Write-Host ''
  }

  # ----------------------------------------------------------- baixar e rodar
  #
  # Gravado em arquivo, e não entregue por pipe: o install.sh é interativo e
  # precisa que a entrada padrão continue sendo o terminal.
  $destino = Join-Path $env:TEMP 'checkpoint-install.sh'
  $url = 'https://raw.githubusercontent.com/alvesoff/checkpoint/main/install.sh'

  try {
    # TLS 1.2 explícito: o Windows PowerShell 5.1 ainda sobe com o padrão
    # antigo em instalação limpa, e o GitHub recusa a conexão.
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    Invoke-WebRequest -UseBasicParsing -Uri $url -OutFile $destino
  } catch {
    Write-Host (T "Could not download the installer: $($_.Exception.Message)" `
                  "Não consegui baixar o instalador: $($_.Exception.Message)")
    return
  }

  # O bash do MSYS entende o caminho em formato POSIX sem reconversão.
  $unidade = $destino.Substring(0, 1).ToLower()
  $caminhoPosix = "/$unidade" + $destino.Substring(2).Replace([char]92, [char]47)

  & $bash $caminhoPosix
  $codigo = $LASTEXITCODE

  Remove-Item $destino -ErrorAction SilentlyContinue

  if ($codigo -ne 0) {
    Write-Host ''
    Write-Host (T "The installer stopped with code $codigo." "O instalador parou com código $codigo.")
  }
}

Invoke-CheckpointInstall
