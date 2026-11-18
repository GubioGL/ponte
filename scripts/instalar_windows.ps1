# Instala o Ponte e configura para iniciar com o Windows (em segundo plano).
# Execute no PowerShell:  powershell -ExecutionPolicy Bypass -File scripts\instalar_windows.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
python -m venv "$env:USERPROFILE\.ponte\venv"
& "$env:USERPROFILE\.ponte\venv\Scripts\pip.exe" install -e "$root\agent[ia]"
$pyw = "$env:USERPROFILE\.ponte\venv\Scripts\pythonw.exe"
# Tarefa agendada: inicia no logon, sem janela
$action  = New-ScheduledTaskAction -Execute $pyw -Argument "-m ponte.server"
$trigger = New-ScheduledTaskTrigger -AtLogOn
Register-ScheduledTask -TaskName "Ponte" -Action $action -Trigger $trigger -RunLevel Highest -Force
Start-ScheduledTask -TaskName "Ponte"
Write-Host "Ponte instalado. Para ver o QR code rode uma vez:  $env:USERPROFILE\.ponte\venv\Scripts\ponte.exe"
Write-Host "Token salvo em $env:USERPROFILE\.ponte\config.json"
