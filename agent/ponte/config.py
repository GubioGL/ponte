"""Configuração persistente: token de pareamento, porta, política de segurança."""
import json, os, secrets
from pathlib import Path

HOME = Path(os.environ.get("PONTE_HOME", Path.home() / ".ponte"))
HOME.mkdir(parents=True, exist_ok=True)
CFG_FILE = HOME / "config.json"
AUDIT_LOG = HOME / "audit.log"

DEFAULTS = {
    "host": "0.0.0.0",          # use o IP do Tailscale (100.x.y.z) para expor só na VPN
    "port": 8765,
    "token": None,              # gerado no primeiro start
    "require_confirm": ["shell", "kill", "agent"],  # ações que pedem confirmação no celular
    "screen_fps": 4,
    "screen_quality": 50,
    "screen_max_width": 1280,
    "llm_model": "claude-opus-5-5",
    "apps": {                   # atalhos de voz: "abrir chrome" -> comando
        "chrome": {"win": "start chrome", "mac": "open -a 'Google Chrome'", "linux": "google-chrome"},
        "navegador": {"win": "start msedge", "mac": "open -a Safari", "linux": "xdg-open https://google.com"},
        "bloco de notas": {"win": "notepad", "mac": "open -a TextEdit", "linux": "gedit"},
        "calculadora": {"win": "calc", "mac": "open -a Calculator", "linux": "gnome-calculator"},
        "explorador": {"win": "explorer", "mac": "open ~", "linux": "xdg-open ~"},
        "vscode": {"win": "code", "mac": "code", "linux": "code"},
        "spotify": {"win": "start spotify:", "mac": "open -a Spotify", "linux": "spotify"},
    },
}


def load() -> dict:
    cfg = dict(DEFAULTS)
    if CFG_FILE.exists():
        cfg.update(json.loads(CFG_FILE.read_text(encoding="utf-8")))
    if not cfg.get("token"):
        cfg["token"] = secrets.token_urlsafe(24)
        save(cfg)
    return cfg


def save(cfg: dict) -> None:
    CFG_FILE.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    try:
        os.chmod(CFG_FILE, 0o600)
    except OSError:
        pass
