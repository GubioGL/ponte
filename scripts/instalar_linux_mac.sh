#!/usr/bin/env bash
# Instala o Ponte e configura para iniciar com a sessão (systemd --user no Linux, launchd no macOS).
set -euo pipefail
# Linux: dependências de sistema do pyautogui
if command -v apt-get >/dev/null; then sudo apt-get install -y python3-tk python3-dev scrot xclip; fi
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENV="$HOME/.ponte/venv"
python3 -m venv "$VENV"
"$VENV/bin/pip" install -e "$ROOT/agent[ia]"

# Cérebro grátis e local: Ollama + modelo
read -r -p "Instalar o cérebro de IA grátis (Ollama + qwen3, ~3-5 GB)? [S/n] " RESP || RESP=s
if [[ ! "$RESP" =~ ^[nN] ]]; then
  if ! command -v ollama >/dev/null; then
    if [[ "$(uname)" == "Darwin" ]] && command -v brew >/dev/null; then brew install ollama && brew services start ollama
    else curl -fsSL https://ollama.com/install.sh | sh; fi
  fi
  MEM_GB=$("$VENV/bin/python" -c "import psutil; print(round(psutil.virtual_memory().total/2**30))")
  MODEL=$([[ $MEM_GB -ge 14 ]] && echo qwen3:8b || echo qwen3:4b)
  ollama pull "$MODEL"
  "$VENV/bin/python" -c "from ponte import config; c=config.load(); c['llm']['model']='$MODEL'; config.save(c)"
fi

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
echo "Instalado. Para ver o link e o QR code do celular: $VENV/bin/python -m ponte.link"
