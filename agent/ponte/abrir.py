"""python -m ponte.abrir  -> abre o Ponte numa janelinha no próprio PC, para dar comandos de voz
usando o microfone do computador (o Chrome/Edge libera o microfone em localhost)."""
import os
import shutil
import subprocess
import webbrowser

from . import config

cfg = config.load()
url = f"http://localhost:{cfg['port']}/#token={cfg['token']}"

candidatos = [
    shutil.which("chrome"), shutil.which("msedge"), shutil.which("google-chrome"), shutil.which("chromium"),
    os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
    os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
    os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"),
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
]
for exe in candidatos:
    if exe and os.path.exists(exe):
        # modo "app": janela pequena, sem barra de endereço
        subprocess.Popen([exe, f"--app={url}", "--window-size=420,720"])
        break
else:
    webbrowser.open(url)
