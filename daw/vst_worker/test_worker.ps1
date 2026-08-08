# daw/vst_worker/test_worker.ps1
#
# Testa o worker ja instalado (nao baixa nem reinstala nada).
# Uso: dentro de daw/vst_worker/, rode:
#     powershell -ExecutionPolicy Bypass -File .\test_worker.ps1

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$VendorDir = Join-Path (Split-Path -Parent $ScriptDir) "vendor"
$TargetDir = Join-Path $VendorDir "py312_embed_win_amd64"
$PythonExe = Join-Path $TargetDir "python.exe"
$WorkerScript = Join-Path $ScriptDir "worker.py"
$TmpDir = Join-Path $env:TEMP "daw_worker_test"

New-Item -ItemType Directory -Force -Path $TmpDir | Out-Null

if (-not (Test-Path $PythonExe)) {
    Write-Host "ERRO: nao achei $PythonExe -- rode setup_worker_windows.ps1 primeiro." -ForegroundColor Red
    exit 1
}

Write-Host "Python: $PythonExe"
Write-Host "Worker: $WorkerScript`n"

# 1) Confere se dawdreamer importa isoladamente (sem worker.py no meio) --
Write-Host "=== [1/2] Testando 'import dawdreamer' isoladamente ===" -ForegroundColor Cyan
& $PythonExe -c "import dawdreamer; print('dawdreamer OK, versao:', getattr(dawdreamer, '__version__', '?')); print('tem RenderEngine:', hasattr(dawdreamer, 'RenderEngine'))"
if ($LASTEXITCODE -ne 0) {
    Write-Host "`nFALHOU: dawdreamer nao importa nem isolado. O problema esta na instalacao do pacote, nao no worker.py." -ForegroundColor Red
    exit 1
}
Write-Host "OK`n" -ForegroundColor Green

# 2) Sobe o worker.py de verdade e espera o handshake -----------------
Write-Host "=== [2/2] Subindo worker.py e esperando handshake ===" -ForegroundColor Cyan
$stdoutFile = Join-Path $TmpDir "stdout.txt"
$stderrFile = Join-Path $TmpDir "stderr.txt"
Remove-Item $stdoutFile, $stderrFile -ErrorAction SilentlyContinue

$proc = Start-Process -FilePath $PythonExe `
    -ArgumentList @($WorkerScript, "--port", "0") `
    -NoNewWindow -PassThru `
    -RedirectStandardOutput $stdoutFile `
    -RedirectStandardError $stderrFile

$found = $false
for ($i = 0; $i -lt 40; $i++) {
    Start-Sleep -Milliseconds 500
    if ($proc.HasExited) {
        $exitCode = $proc.ExitCode
        Write-Host "Processo encerrou sozinho (codigo $exitCode) antes do handshake." -ForegroundColor Red
        break
    }
    $out = Get-Content $stdoutFile -ErrorAction SilentlyContinue -Raw
    if ($out -match "DAW-VST-WORKER PORT=") {
        $found = $true
        break
    }
}

if ($found) {
    Write-Host "OK -- handshake recebido: $($out.Trim())" -ForegroundColor Green
    Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
} else {
    Write-Host "FALHOU -- sem handshake." -ForegroundColor Red
    Write-Host "`n--- stdout ---"; Get-Content $stdoutFile -ErrorAction SilentlyContinue
    Write-Host "--- stderr ---"; Get-Content $stderrFile -ErrorAction SilentlyContinue
    if (-not $proc.HasExited) { Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue }
    exit 1
}