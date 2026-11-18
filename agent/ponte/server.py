"""Servidor do Ponte: roda em segundo plano no PC.

- GET  /            -> app web (PWA) para o celular
- WS   /ws?token=   -> canal de comandos (JSON) + stream da tela (frames JPEG binários)

Iniciar:  python -m ponte.server
"""
from __future__ import annotations

import asyncio
import hmac
import json
import socket
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import config, intents, tools

CFG = config.load()
STATIC = Path(__file__).parent / "static"
app = FastAPI(title="Ponte")
app.mount("/static", StaticFiles(directory=STATIC), name="static")


def audit(entry: dict) -> None:
    entry["ts"] = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(config.AUDIT_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/manifest.json")
def manifest():
    return FileResponse(STATIC / "manifest.json")


class Session:
    """Uma conexão do celular."""

    def __init__(self, ws: WebSocket):
        self.ws = ws
        self.streaming = False
        # aberto no próprio PC (atalho "Ponte - Voz"): a janela do Ponte fica com o foco,
        # então antes de digitar/teclar voltamos para a janela que você estava usando
        self.local = bool(ws.client and ws.client.host in ("127.0.0.1", "::1")
                          and "x-forwarded-for" not in ws.headers)  # tailscale serve = celular
        self.pending: dict[str, dict] = {}   # ações aguardando confirmação
        self.waiters: dict[str, asyncio.Future] = {}  # confirmações pedidas pelo LLM
        self.lock = asyncio.Lock()

    async def send(self, msg: dict):
        async with self.lock:
            await self.ws.send_text(json.dumps(msg, ensure_ascii=False, default=str))

    async def send_frame(self, data: bytes):
        async with self.lock:
            await self.ws.send_bytes(data)

    # ------------------------------------------------------------- stream de tela
    async def stream_loop(self):
        interval = 1 / max(1, CFG["screen_fps"])
        while self.streaming:
            t0 = time.monotonic()
            jpeg, _ = await asyncio.to_thread(tools.screenshot_jpeg, CFG["screen_max_width"], CFG["screen_quality"])
            await self.send_frame(jpeg)
            await asyncio.sleep(max(0, interval - (time.monotonic() - t0)))

    # ------------------------------------------------------------- execução
    async def execute(self, action: str, params: dict) -> dict:
        audit({"action": action, "params": params})
        if self.local and action in ("type", "hotkey", "scroll", "click_here", "agent") \
                and CFG.get("local_refocus", True):
            await asyncio.to_thread(tools.hotkey, ["alt", "tab"])
            await asyncio.sleep(0.4)
        a = action
        if a == "open":
            return await asyncio.to_thread(tools.open_target, params["target"], CFG["apps"])
        if a == "type":
            return await asyncio.to_thread(tools.type_text, params["text"])
        if a == "hotkey":
            return await asyncio.to_thread(tools.hotkey, [k.strip() for k in params["keys"]])
        if a == "click":
            return await asyncio.to_thread(tools.click, params["x"], params["y"],
                                           params.get("button", "left"), params.get("double", False))
        if a == "click_here":
            return await asyncio.to_thread(tools.click_here, params.get("button", "left"))
        if a == "move":
            return await asyncio.to_thread(tools.move, params["dx"], params["dy"])
        if a == "scroll":
            return await asyncio.to_thread(tools.scroll, params["amount"])
        if a == "media":
            return await asyncio.to_thread(tools.media, params["action"])
        if a == "lock":
            return await asyncio.to_thread(tools.lock_screen)
        if a == "kill":
            return await asyncio.to_thread(tools.kill, params["name_or_pid"])
        if a == "sysinfo":
            return await asyncio.to_thread(tools.system_info)
        if a == "processes":
            return await asyncio.to_thread(tools.processes)
        if a == "shell":
            return await asyncio.to_thread(tools.shell, params["command"])
        if a == "agent":
            from .planner import run_goal

            async def notify(m):
                await self.send(m)
            text = await run_goal(params["goal"], CFG, notify, self.ask_confirm)
            return {"ok": True, "summary": text}
        raise ValueError(f"ação desconhecida: {a}")

    async def ask_confirm(self, action: str, params: dict, timeout: int = 120) -> bool:
        """Pergunta no celular e espera a resposta (usado pelo LLM antes de rodar comandos)."""
        ref = uuid.uuid4().hex[:8]
        fut = asyncio.get_running_loop().create_future()
        self.waiters[ref] = fut
        await self.send({"type": "confirm_request", "ref": ref, "action": action, "params": params})
        try:
            ok = await asyncio.wait_for(fut, timeout)
        except asyncio.TimeoutError:
            ok = False
        finally:
            self.waiters.pop(ref, None)
        audit({"event": "confirm", "action": action, "params": params, "ok": ok})
        return ok

    async def handle(self, msg: dict):
        kind = msg.get("type")
        rid = msg.get("id")

        if kind == "stream":
            self.streaming = bool(msg.get("on"))
            if self.streaming:
                asyncio.create_task(self.stream_loop())
            return

        if kind == "confirm":
            fut = self.waiters.get(msg.get("ref"))
            if fut and not fut.done():
                fut.set_result(bool(msg.get("ok")))
                return
            pend = self.pending.pop(msg.get("ref"), None)
            if pend and msg.get("ok"):
                await self.run_and_reply(pend["id"], pend["action"], pend["params"])
            elif pend:
                await self.send({"type": "result", "id": pend["id"], "ok": False, "error": "cancelado"})
            return

        if kind == "voice":  # texto vindo do reconhecimento de voz do celular
            parsed = intents.parse(msg["text"]) if CFG.get("fast_rules", True) \
                else {"action": "agent", "params": {"goal": msg["text"]}}
            action, params = parsed["action"], parsed["params"]
            await self.send({"type": "parsed", "id": rid, "action": action, "params": params})
        elif kind == "action":
            action, params = msg["action"], msg.get("params", {})
        else:
            return

        if action in CFG["require_confirm"] and not msg.get("confirmed"):
            ref = uuid.uuid4().hex[:8]
            self.pending[ref] = {"id": rid, "action": action, "params": params}
            await self.send({"type": "confirm_request", "ref": ref, "action": action, "params": params})
            return
        await self.run_and_reply(rid, action, params)

    async def run_and_reply(self, rid, action, params):
        async def job():
            try:
                out = await self.execute(action, params)
                await self.send({"type": "result", "id": rid, "ok": True, "action": action, "data": out})
            except Exception as e:
                await self.send({"type": "result", "id": rid, "ok": False, "action": action, "error": str(e)})
        asyncio.create_task(job())  # não bloqueia: mouse/stream seguem responsivos durante o agente


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    token = ws.query_params.get("token", "")
    if not hmac.compare_digest(token, CFG["token"]):
        await ws.close(code=4401)
        audit({"event": "auth_fail", "ip": ws.client.host if ws.client else None})
        return
    await ws.accept()
    s = Session(ws)
    audit({"event": "connect", "ip": ws.client.host if ws.client else None})
    await s.send({"type": "hello", "info": await asyncio.to_thread(tools.system_info)})
    try:
        while True:
            await s.handle(json.loads(await ws.receive_text()))
    except WebSocketDisconnect:
        pass
    finally:
        s.streaming = False
        audit({"event": "disconnect"})


def _local_ips() -> list[str]:
    ips = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ips.add(info[4][0])
    except OSError:
        pass
    return sorted(i for i in ips if not i.startswith("127."))


def print_link():
    """Mostra o link (com token) e o QR code para abrir no celular."""
    port = CFG["https_port"] if CFG.get("https_port") else CFG["port"]
    scheme = "https" if CFG.get("https_port") else "http"
    urls = [f"{scheme}://{ip}:{port}/#token={CFG['token']}" for ip in _local_ips()] or \
           [f"{scheme}://<IP-DO-PC>:{port}/#token={CFG['token']}"]
    print(f"  No proprio PC (voz pelo microfone do PC): http://localhost:{CFG['port']}/#token={CFG['token']}")
    for u in urls:
        print("  Abra no celular:", u)
    if scheme == "https":
        print("  (1a vez: o navegador avisa 'conexao nao particular' -> Avancado -> Continuar)")
    try:
        import qrcode
        qr = qrcode.QRCode(border=1)
        qr.add_data(urls[0])
        qr.print_ascii(invert=True)
    except Exception:
        pass
    print("Dica: com Tailscale, use o IP 100.x.y.z (ou o endereco https do 'tailscale serve').\n")


def main():
    import sys
    import uvicorn

    if sys.stdout is None or sys.stderr is None:
        # pythonw (segundo plano) não tem console: manda a saída para ~/.ponte/ponte.log
        log = open(config.HOME / "ponte.log", "a", encoding="utf-8", buffering=1)
        sys.stdout = sys.stderr = log
    print("\n=== PONTE rodando ===")
    servers = [uvicorn.Server(uvicorn.Config(app, host=CFG["host"], port=CFG["port"], log_level="warning"))]
    if CFG.get("https_port"):
        # HTTPS para a rede local: o microfone do navegador exige página segura
        from .certs import ensure_cert
        cert, key = ensure_cert(config.HOME, _local_ips())
        servers.append(uvicorn.Server(uvicorn.Config(app, host=CFG["host"], port=CFG["https_port"],
                                                     ssl_certfile=str(cert), ssl_keyfile=str(key),
                                                     log_level="warning")))
    print_link()

    async def run_all():
        await asyncio.gather(*(s.serve() for s in servers))
    asyncio.run(run_all())


if __name__ == "__main__":
    main()
