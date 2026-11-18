"""Cérebro do Ponte: um LLM recebe o pedido (texto da sua voz) e decide o que fazer.

Fluxo:
  1. Se existir uma ferramenta direta (abrir app, digitar, atalho...), o LLM a usa.
  2. Se não existir, o LLM ESCREVE um comando (PowerShell no Windows, bash no Linux/macOS)
     que resolve a tarefa, e você confirma no celular antes de ele rodar.
  3. O LLM lê o resultado e repete até terminar; então responde com um resumo.

Provedores (config.json -> "llm.provider"):
  - "ollama"    grátis e local (https://ollama.com). Ex.: qwen3:8b, llama3.1:8b, qwen2.5vl:7b (visão)
  - "openai"    qualquer API compatível com OpenAI: Groq, Google Gemini, OpenRouter, LM Studio...
  - "anthropic" Claude (precisa de ANTHROPIC_API_KEY)
"""
from __future__ import annotations

import asyncio
import json
import os
import platform
import urllib.error
import urllib.request
from typing import Awaitable, Callable

from . import tools

Notify = Callable[[dict], Awaitable[None]]
Confirm = Callable[[str, dict], Awaitable[bool]]

SHELL_NAME = {"win": "PowerShell", "mac": "zsh", "linux": "bash"}[tools.OS]


def system_prompt(cfg: dict) -> str:
    apps = ", ".join(cfg.get("apps", {}).keys())
    vision = cfg["llm"].get("vision")
    return f"""Você é o Ponte, um assistente que controla o computador do usuário.
O usuário fala pelo celular; você executa as tarefas NESTE computador.
Sistema: {platform.platform()}. Terminal: {SHELL_NAME}. Usuário do sistema: {os.environ.get("USERNAME") or os.environ.get("USER")}.
Pasta pessoal: {os.path.expanduser("~")}.

Como trabalhar:
- Use a ferramenta direta quando houver: open_target (apps conhecidos: {apps}; também abre URLs, arquivos e pastas),
  type_text, hotkey, scroll, media, processes.
- Quando não houver ferramenta pronta, escreva um comando {SHELL_NAME} com run_command que resolva a tarefa
  (ex.: criar/mover/listar arquivos, ajustar o sistema, baixar algo, abrir um programa pelo caminho, consultar informações).
- Um comando por vez. Leia a saída antes de seguir. Se der erro, corrija e tente de outro jeito.
- {"Use screenshot para ver a tela antes de clicar. click usa frações 0..1 da tela." if vision else "Você não enxerga a tela: prefira comandos e atalhos de teclado em vez de cliques."}
- Nunca apague arquivos, formate discos, faça compras, envie mensagens ou mude senhas sem que o pedido diga isso claramente.
- Ao terminar, responda em português, em uma ou duas frases, dizendo o que foi feito (ou o resultado pedido)."""


def tool_specs(cfg: dict) -> list[dict]:
    """Ferramentas em JSON Schema (formato comum aos três provedores)."""
    obj = lambda props, req: {"type": "object", "properties": props, "required": req, "additionalProperties": False}
    specs = [
        ("run_command", f"Executa um comando {SHELL_NAME} neste PC e devolve stdout/stderr. "
                        "Use para qualquer tarefa que não tenha ferramenta própria.",
         obj({"command": {"type": "string", "description": f"comando {SHELL_NAME}"},
              "explanation": {"type": "string", "description": "em português, o que o comando faz (mostrado ao usuário)"}},
             ["command", "explanation"])),
        ("open_target", "Abre um app conhecido, uma URL, um arquivo ou uma pasta.",
         obj({"target": {"type": "string"}}, ["target"])),
        ("type_text", "Digita um texto no campo que está com o foco.",
         obj({"text": {"type": "string"}}, ["text"])),
        ("hotkey", 'Pressiona tecla ou atalho, ex.: ["ctrl","l"], ["enter"], ["win","d"].',
         obj({"keys": {"type": "array", "items": {"type": "string"}}}, ["keys"])),
        ("scroll", "Rola a tela. Positivo sobe, negativo desce.",
         obj({"amount": {"type": "integer"}}, ["amount"])),
        ("media", "Controle de mídia/volume.",
         obj({"action": {"type": "string", "enum": ["play", "next", "prev", "vol_up", "vol_down", "mute"]}}, ["action"])),
        ("processes", "Lista os programas que mais usam memória.", obj({}, [])),
    ]
    if cfg["llm"].get("vision"):
        specs += [
            ("screenshot", "Captura a tela atual.", obj({}, [])),
            ("click", "Clica num ponto da tela; x,y são frações 0..1.",
             obj({"x": {"type": "number"}, "y": {"type": "number"},
                  "button": {"type": "string", "enum": ["left", "right"]}}, ["x", "y"])),
        ]
    return [{"name": n, "description": d, "parameters": p} for n, d, p in specs]


async def call_tool(name: str, args: dict, cfg: dict, confirm: Confirm) -> tuple[str, str | None]:
    """Executa a ferramenta. Retorna (texto_do_resultado, imagem_b64_ou_None)."""
    if name == "screenshot":
        shot = await asyncio.to_thread(tools.screenshot_b64, 1280)
        return "Captura da tela anexada.", shot["image_b64"]
    if name == "run_command":
        if cfg["llm"].get("confirm_commands", True):
            ok = await confirm("run_command", {"comando": args.get("command"), "o_que_faz": args.get("explanation", "")})
            if not ok:
                return "O usuário NÃO autorizou este comando. Pergunte de outra forma ou encerre.", None
        out = await asyncio.to_thread(tools.shell, args["command"])
    elif name == "open_target":
        out = await asyncio.to_thread(tools.open_target, args["target"], cfg["apps"])
    elif name in ("type_text", "hotkey", "scroll", "media", "processes", "click"):
        out = await asyncio.to_thread(getattr(tools, name), **args)
    else:
        return f"Ferramenta desconhecida: {name}", None
    return json.dumps(out, ensure_ascii=False)[:6000], None


# ------------------------------------------------------------------ HTTP simples (sem dependências)
def _post(url: str, body: dict, headers: dict | None = None, timeout: int = 300) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"LLM respondeu {e.code}: {e.read().decode(errors='replace')[:500]}") from None
    except urllib.error.URLError as e:
        raise RuntimeError(f"Não consegui falar com o LLM em {url}: {e.reason}. "
                           "O Ollama está aberto? (ollama serve)") from None


# ------------------------------------------------------------------ provedores
async def _loop_ollama(goal: str, cfg: dict, notify: Notify, confirm: Confirm) -> str:
    llm = cfg["llm"]
    url = llm.get("base_url", "http://localhost:11434").rstrip("/") + "/api/chat"
    tools_json = [{"type": "function", "function": t} for t in tool_specs(cfg)]
    msgs = [{"role": "system", "content": system_prompt(cfg)}, {"role": "user", "content": goal}]
    for step in range(llm.get("max_steps", 15)):
        r = await asyncio.to_thread(_post, url, {"model": llm["model"], "messages": msgs, "tools": tools_json,
                                                 "stream": False, "options": {"temperature": 0.2}})
        m = r.get("message", {})
        msgs.append({k: v for k, v in m.items() if k in ("role", "content", "tool_calls")})
        calls = m.get("tool_calls") or []
        if not calls:
            return (m.get("content") or "").split("</think>")[-1].strip() or "Concluído."
        for c in calls:
            fn = c["function"]
            args = fn.get("arguments") or {}
            if isinstance(args, str):
                args = json.loads(args or "{}")
            await notify({"type": "agent_step", "step": step + 1, "tool": fn["name"], "input": args})
            try:
                text, img = await call_tool(fn["name"], args, cfg, confirm)
            except Exception as e:
                text, img = f"Erro: {e}", None
            tool_msg = {"role": "tool", "content": text, "tool_name": fn["name"]}
            msgs.append(tool_msg)
            if img:
                msgs.append({"role": "user", "content": "Tela atual:", "images": [img]})
    return "Parei por limite de passos sem concluir."


async def _loop_openai(goal: str, cfg: dict, notify: Notify, confirm: Confirm) -> str:
    llm = cfg["llm"]
    url = llm["base_url"].rstrip("/") + "/chat/completions"
    key = os.environ.get(llm.get("api_key_env") or "", "")
    headers = {"Authorization": f"Bearer {key}"} if key else {}
    tools_json = [{"type": "function", "function": t} for t in tool_specs(cfg)]
    msgs: list[dict] = [{"role": "system", "content": system_prompt(cfg)}, {"role": "user", "content": goal}]
    for step in range(llm.get("max_steps", 15)):
        r = await asyncio.to_thread(_post, url, {"model": llm["model"], "messages": msgs, "tools": tools_json,
                                                 "temperature": 0.2}, headers)
        m = r["choices"][0]["message"]
        msgs.append({k: v for k, v in m.items() if k in ("role", "content", "tool_calls") and v is not None})
        calls = m.get("tool_calls") or []
        if not calls:
            return (m.get("content") or "Concluído.").strip()
        images = []
        for c in calls:
            fn = c["function"]
            args = json.loads(fn.get("arguments") or "{}")
            await notify({"type": "agent_step", "step": step + 1, "tool": fn["name"], "input": args})
            try:
                text, img = await call_tool(fn["name"], args, cfg, confirm)
            except Exception as e:
                text, img = f"Erro: {e}", None
            msgs.append({"role": "tool", "tool_call_id": c["id"], "content": text})
            if img:
                images.append(img)
        if images:
            msgs.append({"role": "user", "content": [{"type": "text", "text": "Tela atual:"}] +
                         [{"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{i}"}} for i in images]})
    return "Parei por limite de passos sem concluir."


async def _loop_anthropic(goal: str, cfg: dict, notify: Notify, confirm: Confirm) -> str:
    import anthropic  # pip install anthropic; defina ANTHROPIC_API_KEY

    llm = cfg["llm"]
    client = anthropic.AsyncAnthropic()
    tools_json = [{"name": t["name"], "description": t["description"], "input_schema": t["parameters"],
                   "strict": True} for t in tool_specs(cfg)]
    msgs: list[dict] = [{"role": "user", "content": goal}]
    for step in range(llm.get("max_steps", 15)):
        resp = await client.beta.messages.create(
            model=llm.get("model") if str(llm.get("model", "")).startswith("claude") else "claude-opus-5-5",
            max_tokens=16000, system=system_prompt(cfg), tools=tools_json,
            thinking={"type": "adaptive"}, output_config={"effort": "medium"},
            betas=["server-side-fallback-2026-07-01"], fallbacks="default", messages=msgs)
        if resp.stop_reason == "refusal":
            return "O modelo recusou este pedido."
        msgs.append({"role": "assistant", "content": resp.content})  # inalterado (thinking preservado)
        if resp.stop_reason != "tool_use":
            return "".join(b.text for b in resp.content if b.type == "text") or "Concluído."
        results = []
        for b in resp.content:
            if b.type != "tool_use":
                continue
            await notify({"type": "agent_step", "step": step + 1, "tool": b.name, "input": b.input})
            try:
                text, img = await call_tool(b.name, b.input, cfg, confirm)
                content = [{"type": "text", "text": text}]
                if img:
                    content.append({"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": img}})
                results.append({"type": "tool_result", "tool_use_id": b.id, "content": content})
            except Exception as e:
                results.append({"type": "tool_result", "tool_use_id": b.id, "content": f"Erro: {e}", "is_error": True})
        msgs.append({"role": "user", "content": results})
    return "Parei por limite de passos sem concluir."


PROVIDERS = {"ollama": _loop_ollama, "openai": _loop_openai, "anthropic": _loop_anthropic}


async def run_goal(goal: str, cfg: dict, notify: Notify, confirm: Confirm) -> str:
    provider = cfg["llm"].get("provider", "ollama")
    if provider not in PROVIDERS:
        raise ValueError(f"provedor de LLM desconhecido: {provider}")
    await notify({"type": "agent_step", "step": 0, "tool": "pensando", "input": {"llm": f"{provider}/{cfg['llm'].get('model')}"}})
    return await PROVIDERS[provider](goal, cfg, notify, confirm)
