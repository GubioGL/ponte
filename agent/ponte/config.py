"""Configuração persistente: token de pareamento, porta, política de segurança."""
import json, os, secrets
from pathlib import Path

HOME = Path(os.environ.get("PONTE_HOME", Path.home() / ".ponte"))
HOME.mkdir(parents=True, exist_ok=True)
CFG_FILE = HOME / "config.json"
AUDIT_LOG = HOME / "audit.log"

DEFAULTS = {
    "config_version": 2,
    "host": "0.0.0.0",          # use o IP do Tailscale (100.x.y.z) para expor só na VPN
    "port": 8765,               # HTTP (use com 'tailscale serve')
    "https_port": 8766,         # HTTPS com certificado próprio (rede local; libera o microfone)
    "token": None,              # gerado no primeiro start
    "require_confirm": ["shell", "kill"],  # ações diretas que pedem confirmação no celular
    "screen_fps": 4,
    "screen_quality": 50,
    "screen_max_width": 1280,
    # Cérebro (LLM). Provedores:
    #   "ollama"    -> grátis, roda no próprio PC (https://ollama.com). Padrão.
    #   "openai"    -> qualquer API compatível com OpenAI (Groq, Gemini, OpenRouter, LM Studio...)
    #   "anthropic" -> Claude (pago, o mais capaz; precisa de ANTHROPIC_API_KEY)
    "llm": {
        "provider": "ollama",
        "model": "qwen3:8b",
        "base_url": "http://localhost:11434",   # para "openai": ex. https://api.groq.com/openai/v1
        "api_key_env": "",                      # nome da variável com a chave, ex. GROQ_API_KEY
        "vision": False,                        # True se o modelo enxerga imagens (ex. qwen2.5vl)
        "confirm_commands": True,               # pedir confirmação no celular antes de cada comando
        "max_steps": 15,
    },
    "fast_rules": True,         # comandos simples ("abrir chrome") rodam sem passar pelo LLM
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
    saved = json.loads(CFG_FILE.read_text(encoding="utf-8")) if CFG_FILE.exists() else {}
    cfg.update(saved)
    cfg["llm"] = {**DEFAULTS["llm"], **(saved.get("llm") or {})}
    # migração: configs antigas confirmavam o agente inteiro; agora cada comando é confirmado
    if saved and saved.get("config_version", 1) < 2:
        cfg["require_confirm"] = [a for a in cfg.get("require_confirm", []) if a != "agent"]
        cfg.pop("llm_model", None)
        cfg["config_version"] = 2
        save(cfg)
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
