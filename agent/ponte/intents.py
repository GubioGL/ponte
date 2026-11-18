"""Interpretador de comandos de voz em português (regras rápidas, sem IA).

Se nenhuma regra casar, o comando vai para o agente de IA (planner.py),
que olha a tela e decide sozinho o que clicar/digitar.
"""
from __future__ import annotations

import re
import unicodedata


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.lower().strip())
    return "".join(c for c in s if not unicodedata.combining(c))


# (regex sobre texto normalizado, ação, função que extrai params)
RULES: list[tuple[str, str, callable]] = [
    (r"^(abr[ae]|abrir|inicia[r]?|executa[r]?) (o |a )?(?P<t>.+)$", "open", lambda m: {"target": m["t"]}),
    (r"^(digita[r]?|escreve[r]?) (?P<t>.+)$", "type", lambda m: {"text": m["t"]}),
    (r"^(pesquisa[r]?|procura[r]?|busca[r]?) (por )?(?P<t>.+)$", "open",
     lambda m: {"target": "https://www.google.com/search?q=" + m["t"].replace(" ", "+")}),
    (r"^(aperta[r]?|pressiona[r]?|tecla) (?P<t>.+)$", "hotkey", lambda m: {"keys": m["t"].replace(" mais ", "+").split("+")}),
    (r"^(copiar|copia)$", "hotkey", lambda m: {"keys": ["ctrl", "c"]}),
    (r"^(colar|cola)$", "hotkey", lambda m: {"keys": ["ctrl", "v"]}),
    (r"^(desfazer|desfaz)$", "hotkey", lambda m: {"keys": ["ctrl", "z"]}),
    (r"^(enter|confirma[r]?)$", "hotkey", lambda m: {"keys": ["enter"]}),
    (r"^(fecha[r]?) (a )?janela$", "hotkey", lambda m: {"keys": ["alt", "f4"]}),
    (r"^(troca[r]?|muda[r]?) (de )?janela$", "hotkey", lambda m: {"keys": ["alt", "tab"]}),
    (r"^(rola[r]?|desce[r]?)( a tela| pagina)?$", "scroll", lambda m: {"amount": -5}),
    (r"^(sobe|subir)( a tela| pagina)?$", "scroll", lambda m: {"amount": 5}),
    (r"^(pausa[r]?|play|toca[r]?|continua[r]?)( musica| video)?$", "media", lambda m: {"action": "play"}),
    (r"^(proxima|pula[r]?)( musica)?$", "media", lambda m: {"action": "next"}),
    (r"^(anterior|volta[r]?)( musica)?$", "media", lambda m: {"action": "prev"}),
    (r"^(aumenta[r]?)( o)? volume$", "media", lambda m: {"action": "vol_up"}),
    (r"^(abaixa[r]?|diminui[r]?)( o)? volume$", "media", lambda m: {"action": "vol_down"}),
    (r"^(muta[r]?|mudo|silencia[r]?)$", "media", lambda m: {"action": "mute"}),
    (r"^(bloque(ia|ar|ie))( o| a)? (pc|computador|tela)$", "lock", lambda m: {}),
    (r"^(fecha[r]?|mata[r]?|encerra[r]?) (o |a )?(programa |processo )?(?P<t>.+)$", "kill", lambda m: {"name_or_pid": m["t"]}),
    (r"^(status|como esta o pc|info(rmacoes)?( do sistema)?)$", "sysinfo", lambda m: {}),
    (r"^(terminal|comando|rodar?) (?P<t>.+)$", "shell", lambda m: {"command": m["t"]}),
]

_COMPILED = [(re.compile(p), a, f) for p, a, f in RULES]


def parse(text: str) -> dict:
    """Retorna {"action": ..., "params": {...}} ou {"action": "agent", ...} como fallback."""
    t = _norm(text)
    # frases compostas ("abre o youtube e coloca lo-fi") são tarefas de vários passos -> IA
    if re.search(r" e (depois |entao )?\w+(a|e|i|ar|er|ir)\b", t) and not t.startswith(("digit", "escrev")):
        return {"action": "agent", "params": {"goal": text}}
    for rx, action, extract in _COMPILED:
        m = rx.match(t)
        if m:
            params = extract(m)
            # mantém o texto original (com acentos) para digitação
            if action == "type":
                params["text"] = re.split(r"\s", text.strip(), maxsplit=1)[1]
            return {"action": action, "params": params}
    return {"action": "agent", "params": {"goal": text}}
