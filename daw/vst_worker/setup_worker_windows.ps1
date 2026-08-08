# daw/vst_worker/setup_worker_windows.ps1
#
# Automatiza TODO o setup do worker de VST:
#   1. Baixa o Python 3.12 embeddable (64-bit) direto do python.org
#   2. Extrai em daw/vendor/py312_embed_win_amd64/
#   3. Habilita o "import site" (necessário pro pip funcionar num
#      embeddable, que vem desabilitado por padrão)
#   4. Baixa e roda o get-pip.py
#   5. Instala dawdreamer + numpy DENTRO desse Python (não no do Blender)
#
# Uso: abra o PowerShell nesta pasta (daw/vst_worker/) e rode:
#     .\setup_worker_windows.ps1
#
# Não precisa rodar como administrador -- tudo fica dentro da pasta do
# addon.

$ErrorActionPreference = "Stop"

$PythonVersions = @("3.12.12", "3.12.11", "3.12.10")
$ScriptDir     = Split-Path -Parent $MyInvocation.MyCommand.Path
$VendorDir     = Join-Path (Split-Path -Parent $ScriptDir) "vendor"
$TargetDir     = Join-Path $VendorDir "py312_embed_win_amd64"
$TmpDir        = Join-Path $env:TEMP "daw_worker_setup"

Write-Host "=== Setup do worker de VST (Python embutido) ===" -ForegroundColor Cyan

if (Test-Path (Join-Path $TargetDir "python.exe")) {
    Write-Host "Ja existe um Python embutido em: $TargetDir"
    $resp = Read-Host "Reinstalar do zero? (s/N)"
    if ($resp -ne "s" -and $resp -ne "S") {
        Write-Host "Mantendo instalacao existente. Pulando para a instalacao de pacotes..."
    } else {
        Remove-Item -Recurse -Force $TargetDir
    }
}

New-Item -ItemType Directory -Force -Path $TmpDir | Out-Null
New-Item -ItemType Directory -Force -Path $VendorDir | Out-Null

if (-not (Test-Path (Join-Path $TargetDir "python.exe"))) {
    # 1. Baixa o Python embeddable oficial, tentando cada versão da
    #    lista até uma que exista (releases mais novas do 3.12 às vezes
    #    saem só como source, sem build pra Windows) ------------------
    $embedZip = Join-Path $TmpDir "python-embed.zip"
    $downloaded = $false
    $usedVersion = $null

    foreach ($ver in $PythonVersions) {
        $embedUrl = "https://www.python.org/ftp/python/$ver/python-$ver-embed-amd64.zip"
        Write-Host "`n[1/5] Tentando Python $ver embeddable..." -ForegroundColor Yellow
        Write-Host "      $embedUrl"
        try {
            Invoke-WebRequest -Uri $embedUrl -OutFile $embedZip -ErrorAction Stop
            $downloaded = $true
            $usedVersion = $ver
            break
        } catch {
            Write-Host "      Nao encontrado (provavelmente release source-only). Tentando a proxima..." -ForegroundColor DarkYellow
        }
    }

    if (-not $downloaded) {
        throw "Nenhuma das versoes $($PythonVersions -join ', ') tem build embeddable pra Windows. Verifique https://www.python.org/downloads/windows/ manualmente e ajuste `$PythonVersions no topo deste script."
    }
    Write-Host "      OK -- usando Python $usedVersion" -ForegroundColor Green

    # 2. Extrai ----------------------------------------------------------
    Write-Host "[2/5] Extraindo para $TargetDir ..." -ForegroundColor Yellow
    Expand-Archive -Path $embedZip -DestinationPath $TargetDir -Force

    # 3. Habilita "import site" (obrigatorio pro pip funcionar) ----------
    Write-Host "[3/5] Habilitando 'import site' no ._pth ..." -ForegroundColor Yellow
    $pthFile = Get-ChildItem -Path $TargetDir -Filter "python*._pth" | Select-Object -First 1
    if ($null -eq $pthFile) {
        throw "Nao encontrei o arquivo python*._pth dentro de $TargetDir -- build do embeddable mudou?"
    }
    (Get-Content $pthFile.FullName) -replace '^#import site', 'import site' | Set-Content $pthFile.FullName

    # 4. Baixa e roda o get-pip.py ---------------------------------------
    Write-Host "[4/5] Instalando pip ..." -ForegroundColor Yellow
    $getPipPath = Join-Path $TmpDir "get-pip.py"
    Invoke-WebRequest -Uri "https://bootstrap.pypa.io/get-pip.py" -OutFile $getPipPath
    & (Join-Path $TargetDir "python.exe") $getPipPath --no-warn-script-location
}

# 5. Instala dawdreamer + numpy dentro do Python embutido ----------------
Write-Host "[5/5] Instalando dawdreamer + numpy (isso demora um pouco, ~30-60MB)..." -ForegroundColor Yellow
& (Join-Path $TargetDir "python.exe") -m pip install --no-warn-script-location dawdreamer numpy

Write-Host "`n=== Testando se o worker sobe corretamente ===" -ForegroundColor Cyan
$workerScript = Join-Path $ScriptDir "worker.py"
$stdoutFile = Join-Path $TmpDir "test_stdout.txt"
$stderrFile = Join-Path $TmpDir "test_stderr.txt"
Remove-Item $stdoutFile, $stderrFile -ErrorAction SilentlyContinue

$testProc = Start-Process -FilePath (Join-Path $TargetDir "python.exe") `
    -ArgumentList @($workerScript, "--port", "0") `
    -NoNewWindow -PassThru `
    -RedirectStandardOutput $stdoutFile `
    -RedirectStandardError $stderrFile

# Poll ate 20s (primeira carga do dawdreamer.pyd, ~46MB, pode demorar
# mais que os 3s fixos que a gente esperava antes).
$handshakeFound = $false
for ($i = 0; $i -lt 40; $i++) {
    Start-Sleep -Milliseconds 500

    if ($testProc.HasExited) {
        Write-Host "O processo encerrou sozinho antes do handshake (codigo $($testProc.ExitCode))." -ForegroundColor Red
        break
    }

    $stdout = Get-Content $stdoutFile -ErrorAction SilentlyContinue -Raw
    if ($stdout -match "DAW-VST-WORKER PORT=") {
        $handshakeFound = $true
        break
    }
}

if ($handshakeFound) {
    Write-Host "OK -- worker subiu e abriu a porta de escuta corretamente." -ForegroundColor Green
    Stop-Process -Id $testProc.Id -Force -ErrorAction SilentlyContinue
} else {
    Write-Host "ATENCAO -- o worker nao deu o handshake esperado." -ForegroundColor Red
    Write-Host "`n--- stdout ---"
    Get-Content $stdoutFile -ErrorAction SilentlyContinue
    Write-Host "--- stderr ---"
    Get-Content $stderrFile -ErrorAction SilentlyContinue
    Write-Host "--------------"
    if (-not $testProc.HasExited) {
        Stop-Process -Id $testProc.Id -Force -ErrorAction SilentlyContinue
    }
    exit 1
}

Write-Host "`n=== Setup concluido ===" -ForegroundColor Cyan
Write-Host "Reinicie o Blender e tente carregar um VST."