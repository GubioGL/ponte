# Ponte 🌉

**Controle seu computador pelo celular, por voz, de qualquer lugar.**

<img src="docs/celular.png" width="240" align="right">

## 🎯 Objetivo

O Ponte é um framework aberto que liga o seu celular ao seu PC. Um programa fica rodando em segundo plano no computador e pode fazer quase tudo que você faria sentado na frente dele: abrir programas, clicar, digitar, ver a tela e rodar comandos. Pelo celular, você manda o que fazer **falando**, tocando na tela ou digitando.

Para pedidos mais complexos ("abre o YouTube e coloca uma música lo-fi"), um **agente de IA** olha a tela do PC e executa os passos sozinho, mostrando no celular o que está fazendo.

## ⚙️ Como funciona

```
 📱 Celular                                   💻 PC
 ┌───────────────────┐   internet segura     ┌───────────────────────────┐
 │ 🎤 fala / digita  │ ───────────────────►  │ Ponte (em segundo plano)  │
 │ 🖥 vê a tela      │ ◄───────────────────  │  • comandos rápidos       │
 │ 🖱 toca = clique  │      (Tailscale)      │  • agente de IA           │
 └───────────────────┘                       │  • mouse, teclado, tela   │
                                             └───────────────────────────┘
```

1. Você fala no celular, por exemplo **"abrir chrome"**.
2. O celular transforma a fala em texto e envia ao PC.
3. O Ponte entende o comando e executa:
   - **Comandos simples** rodam na hora: abrir programas, pesquisar, digitar, pausar música, volume, fechar janela, bloquear o PC.
   - **Pedidos com vários passos** vão para a IA, que vê a tela, clica e digita até terminar.
4. Na aba **Tela**, você vê o PC ao vivo. Um toque na imagem clica naquele ponto do PC.
5. Ações perigosas (rodar comandos, fechar programas, usar a IA) **pedem confirmação** no celular antes de rodar.

## 📦 Como instalar

**1. No computador.** Precisa do [Python 3.10+](https://www.python.org/downloads/).

Baixe o projeto:
```bash
git clone https://github.com/GubioGL/ponte.git
```
```bash
cd ponte
```
No **Windows** (PowerShell):
```bash
powershell -ExecutionPolicy Bypass -File scripts\instalar_windows.ps1
```
No **Linux / macOS**:
```bash
./scripts/instalar_linux_mac.sh
```
O instalador configura o Ponte para iniciar sozinho junto com o computador.

**2. Conectar o celular**

- **Na mesma rede Wi-Fi:** rode `ponte` no PC e escaneie o QR code com o celular.
- **Pela internet, de qualquer lugar:** instale o [Tailscale](https://tailscale.com/download) no PC e no celular, com a mesma conta. Depois rode no PC:
  ```bash
  tailscale serve --bg 8765
  ```
  No celular, abra `https://<nome-do-pc>.<sua-rede>.ts.net` e use o link com o token mostrado pelo `ponte`.
- No navegador do celular, toque em **"Adicionar à tela inicial"** para usar o Ponte como um aplicativo.

**3. IA (opcional).** Para ativar o agente inteligente, defina a variável `ANTHROPIC_API_KEY` no PC. Sem ela, todo o resto funciona normalmente.

## 🗣 Exemplos de comandos

| Você fala | O PC faz |
|---|---|
| "abrir chrome" | abre o navegador |
| "pesquisar receita de bolo" | pesquisa no Google |
| "digitar bom dia a todos" | digita o texto onde o cursor estiver |
| "pausar música" / "aumentar volume" | controla a mídia |
| "fechar janela" / "trocar janela" | Alt+F4 / Alt+Tab |
| "bloquear o pc" | bloqueia a tela |
| "abre o YouTube e coloca lo-fi" | 🤖 a IA faz os passos sozinha |

## 🔒 Segurança

- Cada PC tem uma senha (token) própria, que só o seu celular conhece.
- Use o Tailscale para acessar pela internet. **Não abra portas no roteador.**
- Ações perigosas pedem confirmação, e tudo fica registrado em `~/.ponte/audit.log`.

## 📁 Estrutura

```
agent/ponte/
  server.py    servidor (conexão com o celular, segurança, transmissão da tela)
  intents.py   comandos de voz em português  ← adicione suas frases aqui
  planner.py   agente de IA
  tools.py     tela, mouse, teclado, programas, terminal
  static/      aplicativo do celular
scripts/       instaladores
docs/          arquitetura, projetos usados como base e roadmap
```

Detalhes técnicos, os projetos open source usados como base e os próximos passos estão em [docs/ARQUITETURA.md](docs/ARQUITETURA.md).
