"""Agente de IA: recebe um objetivo em linguagem natural ("abre o YouTube e coloca
lo-fi"), olha a tela, e usa as ferramentas de mouse/teclado/shell em loop até concluir.

Usa a API do Claude (pip install anthropic; defina ANTHROPIC_API_KEY).
Cada passo é enviado ao celular via callback `notify`, para você acompanhar ao vivo.
"""
from __future__ import annotations

import json
from typing import Awaitable, Callable

from . import tools

SYSTEM = """Você controla o computador do usuário para cumprir o objetivo pedido.
Você recebe capturas de tela (redimensionadas) e pode clicar, digitar, usar atalhos e rodar comandos.
Coordenadas de clique são frações 0..1 da largura/altura da tela (x=0.5,y=0.5 é o centro).
Depois de cada ação que muda a tela, tire um novo screenshot para confirmar o resultado.
Prefira atalhos de teclado e comandos de shell quando forem mais confiáveis que cliques.
Nunca apague arquivos, faça compras, envie mensagens ou altere senhas sem que o objetivo peça isso explicitamente.
Ao terminar, responda em português com um resumo curto do que foi feito."""

TOOLS = [
    {"name": "screenshot", "description": "Captura a tela atual.",
     "input_schema": {"type": "object", "properties": {}, "additionalProperties": False}},
    {"name": "click", "description": "Clica num ponto. x,y são frações 0..1 da tela.",
     "input_schema": {"type": "object", "properties": {
         "x": {"type": "number"}, "y": {"type": "number"},
         "button": {"type": "string", "enum": ["left", "right", "middle"]},
         "double": {"type": "boolean"}},
         "required": ["x", "y"], "additionalProperties": False}},
    {"name": "type_text", "description": "Digita um texto no campo focado.",
     "input_schema": {"type": "object", "properties": {"text": {"type": "string"}},
                      "required": ["text"], "additionalProperties": False}},
    {"name": "hotkey", "description": "Pressiona teclas/atalho, ex.: [\"ctrl\",\"l\"] ou [\"enter\"].",
     "input_schema": {"type": "object", "properties": {"keys": {"type": "array", "items": {"type": "string"}}},
                      "required": ["keys"], "additionalProperties": False}},
    {"name": "scroll", "description": "Rola a tela. Positivo sobe, negativo desce.",
     "input_schema": {"type": "object", "properties": {"amount": {"type": "integer"}},
                      "required": ["amount"], "additionalProperties": False}},
    {"name": "open_target", "description": "Abre app conhecido, URL ou arquivo.",
     "input_schema": {"type": "object", "properties": {"target": {"type": "string"}},
                      "required": ["target"], "additionalProperties": False}},
    {"name": "shell", "description": "Executa um comando de terminal e retorna stdout/stderr.",
     "input_schema": {"type": "object", "properties": {"command": {"type": "string"}},
                      "required": ["command"], "additionalProperties": False}},
]
for _t in TOOLS:
    _t["strict"] = True


def _run_tool(name: str, args: dict, cfg: dict) -> list[dict]:
    """Executa a ferramenta e devolve o conteúdo do tool_result (texto e/ou imagem)."""
    if name == "screenshot":
        shot = tools.screenshot_b64(1280)
        return [{"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                             "data": shot["image_b64"]}}]
    if name == "open_target":
        out = tools.open_target(args["target"], cfg["apps"])
    else:
        out = getattr(tools, name)(**args)
    return [{"type": "text", "text": json.dumps(out, ensure_ascii=False)[:8000]}]


async def run_goal(goal: str, cfg: dict, notify: Callable[[dict], Awaitable[None]],
                   max_steps: int = 30) -> str:
    import anthropic  # import tardio: o resto do Ponte funciona sem a SDK

    client = anthropic.AsyncAnthropic()
    messages: list[dict] = [{"role": "user", "content": f"Objetivo: {goal}"}]

    for step in range(max_steps):
        resp = await client.beta.messages.create(
            model=cfg.get("llm_model", "claude-opus-5-5"),
            max_tokens=16000,
            system=SYSTEM,
            tools=TOOLS,
            thinking={"type": "adaptive"},
            output_config={"effort": "medium"},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            messages=messages,
        )
        if resp.stop_reason == "refusal":
            return "O modelo recusou este pedido."
        # devolve o conteúdo da resposta inalterado (necessário para o thinking preservado)
        messages.append({"role": "assistant", "content": resp.content})

        if resp.stop_reason != "tool_use":
            text = "".join(b.text for b in resp.content if b.type == "text")
            return text or "Concluído."

        results = []
        for block in resp.content:
            if block.type != "tool_use":
                continue
            await notify({"type": "agent_step", "step": step + 1, "tool": block.name, "input": block.input})
            try:
                content = _run_tool(block.name, block.input, cfg)
                results.append({"type": "tool_result", "tool_use_id": block.id, "content": content})
            except Exception as e:  # erro vira resultado para a IA tentar outra abordagem
                results.append({"type": "tool_result", "tool_use_id": block.id,
                                "content": f"Erro: {e}", "is_error": True})
        messages.append({"role": "user", "content": results})

    return f"Parei após {max_steps} passos sem concluir."
