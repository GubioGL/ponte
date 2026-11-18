"""Ferramentas de baixo nível: tela, mouse, teclado, shell, apps, processos.

Tudo o que o celular (ou a IA) pode fazer no PC passa por aqui.
Cada função recebe parâmetros simples e devolve um dict serializável.
"""
from __future__ import annotations

import base64
import io
import platform
import subprocess
import webbrowser

import mss
import psutil
from PIL import Image

try:  # pyautogui precisa de um display; falha em servidores sem tela
    import pyautogui

    pyautogui.FAILSAFE = True  # mover o mouse para o canto superior esquerdo aborta
    pyautogui.PAUSE = 0.05
except (Exception, SystemExit):  # pragma: no cover  (no Linux, falta python3-tk -> SystemExit)
    pyautogui = None

try:
    import pyperclip
except Exception:  # pragma: no cover
    pyperclip = None

OS = {"Windows": "win", "Darwin": "mac"}.get(platform.system(), "linux")


# ---------------------------------------------------------------- tela
def screen_size() -> tuple[int, int]:
    with mss.mss() as s:
        m = s.monitors[1]
        return m["width"], m["height"]


def screenshot_jpeg(max_width: int = 1280, quality: int = 50) -> tuple[bytes, float]:
    """Captura o monitor principal. Retorna (jpeg, fator_de_escala)."""
    with mss.mss() as s:
        raw = s.grab(s.monitors[1])
        img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
    scale = 1.0
    if img.width > max_width:
        scale = max_width / img.width
        img = img.resize((max_width, int(img.height * scale)))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=quality)
    return buf.getvalue(), scale


def screenshot_b64(max_width: int = 1280) -> dict:
    data, scale = screenshot_jpeg(max_width, 70)
    return {"image_b64": base64.b64encode(data).decode(), "scale": scale}


# ---------------------------------------------------------------- mouse/teclado
def _need_gui():
    if pyautogui is None:
        raise RuntimeError("pyautogui indisponível (sem display?)")


def click(x: float, y: float, button: str = "left", double: bool = False, relative: bool = True) -> dict:
    """x,y em 0..1 (relative=True, vindo do toque no celular) ou em pixels reais."""
    _need_gui()
    if relative:
        w, h = screen_size()
        x, y = x * w, y * h
    pyautogui.click(int(x), int(y), clicks=2 if double else 1, button=button)
    return {"ok": True, "x": int(x), "y": int(y)}


def click_here(button: str = "left") -> dict:
    """Clica onde o cursor está (toque no modo touchpad)."""
    _need_gui()
    pyautogui.click(button=button)
    return {"ok": True}


def move(dx: float, dy: float) -> dict:
    """Movimento relativo (modo touchpad)."""
    _need_gui()
    pyautogui.moveRel(int(dx), int(dy))
    return {"ok": True}


def scroll(amount: int) -> dict:
    _need_gui()
    pyautogui.scroll(int(amount))
    return {"ok": True}


def type_text(text: str) -> dict:
    """Digita texto. Usa a área de transferência para acentos (pyautogui não digita 'ç', 'ã')."""
    _need_gui()
    if pyperclip and not text.isascii():
        pyperclip.copy(text)
        pyautogui.hotkey("command" if OS == "mac" else "ctrl", "v")
    else:
        pyautogui.write(text, interval=0.01)
    return {"ok": True, "chars": len(text)}


def hotkey(keys: list[str]) -> dict:
    """Ex.: ["ctrl","c"], ["alt","tab"], ["enter"]."""
    _need_gui()
    if len(keys) == 1:
        pyautogui.press(keys[0])
    else:
        pyautogui.hotkey(*keys)
    return {"ok": True, "keys": keys}


# ---------------------------------------------------------------- sistema
def shell(command: str, timeout: int = 120) -> dict:
    """Executa um comando (PowerShell no Windows, bash/zsh no Linux/macOS) e devolve a saída."""
    if OS == "win":
        args = ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command",
                "[Console]::OutputEncoding=[Text.Encoding]::UTF8; " + command]
        p = subprocess.run(args, capture_output=True, text=True, timeout=timeout,
                           encoding="utf-8", errors="replace", creationflags=0x08000000)  # sem janela
    else:
        p = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=timeout,
                           encoding="utf-8", errors="replace")
    return {"code": p.returncode, "stdout": p.stdout[-8000:], "stderr": p.stderr[-4000:]}


def open_target(target: str, apps: dict) -> dict:
    """Abre um app conhecido, uma URL ou um arquivo/pasta."""
    key = target.lower().strip()
    if key in apps:
        cmd = apps[key][OS]
        subprocess.Popen(cmd, shell=True)
        return {"ok": True, "opened": key, "cmd": cmd}
    if key.startswith(("http://", "https://", "www.")) or "." in key and " " not in key:
        url = key if key.startswith("http") else "https://" + key
        webbrowser.open(url)
        return {"ok": True, "opened": url}
    opener = {"win": f'start "" "{target}"', "mac": f'open "{target}"', "linux": f'xdg-open "{target}"'}[OS]
    subprocess.Popen(opener, shell=True)
    return {"ok": True, "opened": target}


def processes(top: int = 15) -> dict:
    procs = sorted(psutil.process_iter(["pid", "name", "memory_percent"]),
                   key=lambda p: p.info["memory_percent"] or 0, reverse=True)[:top]
    return {"processes": [p.info for p in procs]}


def kill(name_or_pid: str) -> dict:
    killed = []
    for p in psutil.process_iter(["pid", "name"]):
        if str(p.info["pid"]) == name_or_pid or (p.info["name"] or "").lower().startswith(name_or_pid.lower()):
            try:
                p.terminate()
                killed.append(p.info)
            except psutil.Error:
                pass
    return {"killed": killed}


def system_info() -> dict:
    return {
        "os": platform.platform(),
        "cpu_percent": psutil.cpu_percent(interval=0.3),
        "ram_percent": psutil.virtual_memory().percent,
        "battery": getattr(psutil.sensors_battery(), "percent", None) if hasattr(psutil, "sensors_battery") else None,
        "screen": screen_size(),
    }


def media(action: str) -> dict:
    """play/pause, próxima, anterior, volume."""
    keymap = {"play": "playpause", "pause": "playpause", "next": "nexttrack", "prev": "prevtrack",
              "vol_up": "volumeup", "vol_down": "volumedown", "mute": "volumemute"}
    return hotkey([keymap[action]])


def lock_screen() -> dict:
    cmd = {"win": "rundll32.exe user32.dll,LockWorkStation",
           "mac": "pmset displaysleepnow",
           "linux": "loginctl lock-session"}[OS]
    return shell(cmd)
