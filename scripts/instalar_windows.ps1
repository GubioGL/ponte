# Instala o Ponte e configura para iniciar com o Windows (em segundo plano).
# Execute dentro da pasta do projeto, no PowerShell:
#   powershell -ExecutionPolicy Bypass -File scripts\instalar_windows.ps1
# Nao precisa ser administrador.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$venv = "$env:USERPROFILE\.ponte\venv"

# 1. Escolhe o Python: prefere 3.13/3.12 (todas as bibliotecas tem versao pronta)
$pyExe = "python"; $pyArgs = @()
foreach ($v in @("3.13", "3.12", "3.11")) {
    try { & py "-$v" -c "import sys" 2>$null; if ($LASTEXITCODE -eq 0) { $pyExe = "py"; $pyArgs = @("-$v"); break } } catch {}
}
Write-Host "Usando Python: $pyExe $pyArgs"

# 2. Ambiente virtual + dependencias
if (-not (Test-Path "$venv\Scripts\python.exe")) {
    & $pyExe @pyArgs -m venv $venv
    if ($LASTEXITCODE -ne 0) { throw "Falha ao criar o ambiente virtual." }
}
& "$venv\Scripts\python.exe" -m pip install --upgrade pip --quiet
& "$venv\Scripts\python.exe" -m pip install -e "$root\agent[ia]"
if ($LASTEXITCODE -ne 0) { throw "Falha ao instalar as dependencias (veja o erro acima)." }

# 3. Inicio automatico: atalho na pasta Inicializar do usuario (sem admin)
$startup = [Environment]::GetFolderPath("Startup")
$lnk = Join-Path $startup "Ponte.lnk"
$sh = New-Object -ComObject WScript.Shell
$s = $sh.CreateShortcut($lnk)
$s.TargetPath = "$venv\Scripts\pythonw.exe"
$s.Arguments = "-m ponte.server"
$s.WorkingDirectory = "$env:USERPROFILE\.ponte"
$s.Save()

# 4. Inicia agora em segundo plano (se ja nao estiver rodando)
$running = Get-CimInstance Win32_Process -Filter "Name='pythonw.exe'" | Where-Object { $_.CommandLine -like "*ponte.server*" }
if (-not $running) { Start-Process "$venv\Scripts\pythonw.exe" -ArgumentList "-m ponte.server" -WindowStyle Hidden }

Write-Host ""
Write-Host "Ponte instalado e rodando em segundo plano. Ele inicia sozinho quando voce liga o PC."
Write-Host "Para ver o link e o QR code do celular, rode:"
Write-Host "  $venv\Scripts\python.exe -m ponte.link"
Write-Host "Para desinstalar o inicio automatico, apague: $lnk"
