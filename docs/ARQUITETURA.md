# Ponte — Arquitetura e plano

## 1. O que já existe no GitHub (pesquisa de nov/2026)

Não vale reescrever o que já está pronto. Cada camada do Ponte tem um projeto maduro para copiar ou integrar:

| Camada | Repositório | ⭐ | Para que serve no Ponte |
|---|---|---|---|
| Mouse/teclado | [asweigart/pyautogui](https://github.com/asweigart/pyautogui) | 12,7k | Base do MVP (Win/Mac/Linux) |
| Mouse/teclado (nativo) | [go-vgo/robotgo](https://github.com/go-vgo/robotgo) | 10,9k | Alternativa em Go se quiser um binário único |
| Acessibilidade (clicar por nome do botão) | [vercel-labs/agent-desktop](https://github.com/vercel-labs/agent-desktop) | 25k | Ler a árvore de UI e clicar sem depender de pixels |
| Leitura da tela por visão | [microsoft/OmniParser](https://github.com/microsoft/OmniParser) | 25,6k | Detecta botões/ícones na captura de tela para a IA clicar certo |
| Agente de "computer use" | [simular-ai/Agent-S](https://github.com/simular-ai/Agent-S), [bytedance/UI-TARS-desktop](https://github.com/bytedance/UI-TARS-desktop) (arquivado), [trycua/cua](https://github.com/trycua/cua) | 13k / 39k / 32k | Referência de planner, grounding e sandbox |
| Agente de navegador | [browser-use/browser-use](https://github.com/browser-use/browser-use) | 121k | Tarefas web ficam muito mais confiáveis que clicar por pixel |
| Agente local | [Fosowl/agenticSeek](https://github.com/Fosowl/agenticSeek) | 27,6k | Exemplo de agente 100% local com voz |
| Voz → texto (local) | [SYSTRAN/faster-whisper](https://github.com/SYSTRAN/faster-whisper), [ggml-org/whisper.cpp](https://github.com/ggml-org/whisper.cpp), [alphacep/vosk-api](https://github.com/alphacep/vosk-api) | 26k / 55k / 15k | Reconhecimento offline em PT-BR |
| Pipeline de voz em tempo real | [pipecat-ai/pipecat](https://github.com/pipecat-ai/pipecat) | 17k | Conversa por voz contínua (fala e resposta falada) |
| Assistente pessoal | [leon-ai/leon](https://github.com/leon-ai/leon), [isair/jarvis](https://github.com/isair/jarvis) | 17,7k / 2,4k | Modelo de "skills", wake word, memória |
| Área de trabalho remota | [rustdesk/rustdesk](https://github.com/rustdesk/rustdesk) | 130k | Referência de streaming e relay P2P |
| Tela no navegador via WebRTC | [m1k1o/neko](https://github.com/m1k1o/neko), [H-M-H/Weylus](https://github.com/H-M-H/Weylus) | 22k / 9,8k | Stream com pouco atraso para o celular |
| Rede segura PC↔celular | [tailscale/tailscale](https://github.com/tailscale/tailscale) | 39k | VPN WireGuard sem abrir portas no roteador |
| Agente multi-dispositivo | [nano-muse/nanoMuse](https://github.com/nano-muse/nanoMuse) | 3,6k | Ideia muito parecida (celular + PC); vale estudar |

## 2. Visão geral

```
 ┌──────────── CELULAR (PWA no navegador) ────────────┐
 │  🎤 Voz (Web Speech / ditado)   🖥 Tela ao vivo     │
 │  ⌨ Teclado remoto  🖱 Touchpad   ⚡ Atalhos          │
 └───────────────┬────────────────────────────────────┘
                 │ WebSocket (JSON + frames JPEG)
                 │ token + HTTPS, pela VPN Tailscale (WireGuard)
 ┌───────────────▼──────── PC (serviço em segundo plano) ┐
 │ server.py   autenticação · sessões · confirmação · log │
 │   ├─ intents.py  regras PT-BR rápidas ("abrir chrome") │
 │   ├─ planner.py  agente de IA: vê a tela → age → repete│
 │   └─ tools.py    tela(mss) · mouse/teclado(pyautogui)  │
 │                  shell · apps · processos · mídia      │
 └────────────────────────────────────────────────────────┘
```

**Como um comando passa pelo sistema:**
1. Você fala no celular. O navegador converte a fala em texto (`pt-BR`).
2. O texto vai para o PC por `{"type":"voice","text":"..."}`.
3. `intents.py` tenta uma regra. Se uma regra casar, a ação roda na hora (menos de 100 ms, sem custo).
4. Se nenhuma regra casar, ou se a frase tiver vários passos, o texto vai para o **agente de IA**. O agente tira um screenshot, decide a próxima ação (clicar, digitar, atalho, shell) e repete até terminar. Cada passo aparece ao vivo no celular.
5. Ações perigosas (`shell`, `kill`, `agent`) só rodam depois que você confirma no celular.

## 3. Segurança (leia antes de expor à internet)

Um programa com acesso total ao PC, acessível pela rede, é exatamente o que um invasor quer. Regras do projeto:

- **Nunca abra a porta no roteador.** Use **Tailscale**. Só os seus dispositivos entram na rede, e o tráfego é criptografado.
- Use `tailscale serve --bg 8765`. Ele dá HTTPS (`https://seu-pc.tailnet.ts.net`), que o microfone do navegador exige, e o certificado é automático.
- Ponha `host` em `~/.ponte/config.json` como o IP do Tailscale (`100.x.y.z`). Assim o agente nem escuta na rede local.
- Token aleatório de 192 bits em `~/.ponte/config.json`. Ele vai no `#fragmento` do QR code, então não aparece em logs HTTP. Para trocar, apague o campo `token`.
- Lista `require_confirm`: ações destrutivas pedem confirmação.
- `~/.ponte/audit.log` registra todas as ações.
- Failsafe do pyautogui: levar o mouse ao canto superior esquerdo interrompe a automação.
- Próximos passos: pareamento por QR com chave por dispositivo, 2FA para `shell`, um modo "somente leitura" e o agente de IA numa conta de usuário com menos permissões.

## 4. Roadmap

| Fase | Entrega | Base sugerida |
|---|---|---|
| **0 — MVP (este repo)** | Voz, comandos PT-BR, tela ao vivo, toque e clique, touchpad, teclado, atalhos, agente de IA, confirmação, log, autostart | pyautogui, mss, FastAPI, Claude API |
| 1 — Voz local | STT no PC (o celular manda áudio) com faster-whisper; wake word "Ei Ponte"; resposta falada (TTS) | faster-whisper, openWakeWord, Piper |
| 2 — Precisão | Árvore de acessibilidade (UIA no Windows, AX no macOS) e OmniParser para achar botões pelo nome; tarefas web com browser-use | agent-desktop, OmniParser, browser-use |
| 3 — Stream bom | WebRTC (menos de 100 ms, 30 fps) no lugar de JPEG por WebSocket | aiortc, neko/Weylus como referência |
| 4 — Skills/plugins | Pasta `skills/` com funções Python (ex.: "modo reunião", "backup") e exposição como **servidor MCP**, para Claude Desktop e outros agentes usarem o PC | MCP Python SDK |
| 5 — App nativo | App Flutter/React Native com notificações push, widget e atalho do Siri/Google Assistant ("Ok Google, Ponte abrir Spotify") | Flutter |
| 6 — Multi-PC | Um celular controla vários PCs; relay próprio opcional para quem não usa Tailscale | rustdesk-server como referência |

## 5. Protocolo (WebSocket `/ws?token=...`)

Celular → PC:
```jsonc
{"type":"voice","id":1,"text":"abrir chrome"}
{"type":"action","id":2,"action":"click","params":{"x":0.5,"y":0.3,"button":"left"}}
{"type":"action","id":3,"action":"type","params":{"text":"olá"}}
{"type":"action","id":4,"action":"hotkey","params":{"keys":["ctrl","l"]}}
{"type":"stream","on":true}
{"type":"confirm","ref":"ab12cd34","ok":true}
```
PC → celular: `hello`, `parsed`, `confirm_request`, `agent_step`, `result` (JSON) e frames JPEG (binário).

Ações: `open, type, hotkey, click, click_here, move, scroll, media, lock, kill, sysinfo, processes, shell, agent`.
