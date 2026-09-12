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
  $caminhoPosix = "/$unidade" + ($destino.Substring(2) -replace '\', '/')

  & $bash $caminhoPosix
  $codigo = $LASTEXITCODE

  Remove-Item $destino -ErrorAction SilentlyContinue

  if ($codigo -ne 0) {
    Write-Host ''
    Write-Host (T "The installer stopped with code $codigo." "O instalador parou com código $codigo.")
  }
}

Invoke-CheckpointInstall
