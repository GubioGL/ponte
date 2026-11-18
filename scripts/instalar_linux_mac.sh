#!/usr/bin/env bash
# Instala o Ponte e configura para iniciar com a sessão (systemd --user no Linux, launchd no macOS).
set -euo pipefail
# Linux: dependências de sistema do pyautogui
if command -v apt-get >/dev/null; then sudo apt-get install -y python3-tk python3-dev scrot xclip; fi
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENV="$HOME/.ponte/venv"
python3 -m venv "$VENV"
"$VENV/bin/pip" install -e "$ROOT/agent[ia]"

if [[ "$(uname)" == "Darwin" ]]; then
  PLIST="$HOME/Library/LaunchAgents/com.ponte.agent.plist"
  cat > "$PLIST" <<PL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.ponte.agent</string>
  <key>ProgramArguments</key><array><string>$VENV/bin/python</string><string>-m</string><string>ponte.server</string></array>
  <key>RunAtLoad</key><true/><key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>$HOME/.ponte/ponte.log</string>
  <key>StandardErrorPath</key><string>$HOME/.ponte/ponte.log</string>
</dict></plist>
PL
  launchctl unload "$PLIST" 2>/dev/null || true
  launchctl load "$PLIST"
  echo "macOS: conceda 'Gravação de Tela' e 'Acessibilidade' ao Python em Ajustes > Privacidade e Segurança."
else
  mkdir -p "$HOME/.config/systemd/user"
  cat > "$HOME/.config/systemd/user/ponte.service" <<SV
[Unit]
Description=Ponte - controle do PC pelo celular
After=graphical-session.target

[Service]
ExecStart=$VENV/bin/python -m ponte.server
Restart=always
Environment=DISPLAY=:0

[Install]
WantedBy=default.target
SV
  systemctl --user daemon-reload
  systemctl --user enable --now ponte.service
  echo "Linux: em Wayland o controle de mouse/tela é limitado; use uma sessão X11 (Xorg)."
fi
echo "Instalado. QR code / link: rode '$VENV/bin/ponte' uma vez, ou veja o token em ~/.ponte/config.json"
