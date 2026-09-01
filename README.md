# Bot de Agendamento HSPM 🤖🏥

**Descrição curta (PT):** Um bot Python para monitoramento de vagas de consultas e envio de alertas via Telegram.

**Short description (EN):** A Python bot to monitor medical appointment openings and send alerts via Telegram.

Automação em Python que monitora vagas de consultas médicas em múltiplas
especialidades no portal do Hospital do Servidor Público Municipal (HSPM).
Usa Playwright para controlar uma sessão do Chrome já logada, e envia
alertas em tempo real via Telegram quando encontra horários disponíveis.

## 🛠️ Stack

* **Python 3.13**
* **uv** — gerenciador de dependências e ambiente (substitui pip/venv/Poetry)
* **Playwright** — automação web via CDP (Chrome DevTools Protocol)
* **httpx** — cliente HTTP assíncrono (integração com a API do Telegram)
* **pydantic-settings** — validação de configuração via variáveis de ambiente
* **Docker / Dev Containers** — ambiente de desenvolvimento containerizado
* **ruff** — lint e formatação
* **pytest** — testes automatizados
* **pre-commit** — checagens automáticas antes de cada commit

## 📁 Estrutura do projeto

```
vagas-hspm/
├── .devcontainer/
│   └── devcontainer.json
├── .github/
│   └── workflows/
│       └── ci.yml
├── src/
│   └── vagas_hspm/
│       ├── __init__.py
│       ├── __main__.py         # ponto de entrada
│       ├── config.py           # Settings (pydantic-settings)
│       ├── models.py           # StatusBusca (enum)
│       ├── telegram_client.py  # cliente assíncrono do bot do Telegram
│       ├── storage.py          # histórico CSV + leitura de especialidades
│       ├── browser.py          # automação da página (Playwright)
│       └── monitor.py          # orquestração do loop principal
├── tests/
│   └── test_storage.py
├── especialidades.txt          # lista monitorada, uma especialidade por linha
├── .env.example
├── .gitignore
├── .pre-commit-config.yaml
├── Dockerfile
├── pyproject.toml
└── README.md
```

## ⚙️ Pré-requisitos

* [Docker](https://docs.docker.com/get-docker/) instalado, com seu usuário
  no grupo `docker` (para rodar sem `sudo` — necessário para o Dev Container)
* [VS Code](https://code.visualstudio.com/) com a extensão **Dev Containers**
* Google Chrome instalado na máquina host
* Um bot configurado no Telegram (Token e Chat ID)
* Acesso ao portal de agendamento do HSPM

> **Nota de rede:** o container roda com `--network host`, então funciona de
> forma nativa e completa apenas em **Linux**. Em Mac/Windows (Docker
> Desktop) a configuração de rede precisa de ajuste (`host.docker.internal`
> em vez de `localhost` para o CDP).

## 📝 Configuração inicial

### 1. Clonar o repositório

```bash
git clone https://github.com/Rjj18/bot-consultas.git
cd bot-consultas
```

### 2. Configurar variáveis de ambiente

Copie `.env.example` para `.env` e preencha:

```bash
cp .env.example .env
```

| Variável | Descrição | Obrigatória |
|---|---|---|
| `URL_AGENDAMENTO` | URL do portal de agendamento do HSPM | Sim |
| `TELEGRAM_TOKEN` | Token do bot do Telegram | Sim |
| `CHAT_ID` | ID do chat no Telegram para onde os alertas vão | Sim |
| `CPF` | CPF para login automático | Não — só se quiser login automático |
| `SENHA` | Senha para login automático | Não — só se quiser login automático |
| `CDP_URL` | Endereço do Chrome com debug remoto | Não — padrão `http://localhost:9222` |
| `TEMPO_ESPERA_MINUTOS` | Intervalo entre varreduras | Não — padrão `5` |

### 3. Definir as especialidades monitoradas

Edite `especialidades.txt` — uma especialidade por linha:

```
Clínica Médica
Dermatologia
Nutrição - Dietética
Odontologia - Dentística
Otorrinolaringologia
Urologia
```

O bot recarrega esse arquivo a cada ciclo — dá para editar com o bot já
rodando, sem precisar reiniciar.

## 🚀 Como rodar

### 1. Abrir o Chrome com debug remoto (na máquina host, fora do container)

```bash
google-chrome --remote-debugging-port=9222 --user-data-dir="/tmp/chrome_dev_sessao"
```

Deixe essa janela aberta e faça login manualmente no portal do HSPM nela —
é essa sessão que o Playwright vai controlar.

### 2. Abrir o projeto no Dev Container

No VS Code: `Ctrl+Shift+P` → **Dev Containers: Reopen in Container**.

Isso builda a imagem a partir do `Dockerfile` e roda automaticamente
`uv sync` (via `postCreateCommand`), instalando todas as dependências.

### 3. Rodar o bot

No terminal integrado do VS Code (já dentro do container):

```bash
uv run python -m vagas_hspm
```

Se tudo estiver certo, você recebe a mensagem "🤖 Robô iniciado!" no
Telegram configurado.

## 🔄 Fluxo de desenvolvimento

```bash
uv run pre-commit install   # uma vez, após clonar — ativa os hooks de commit
uv run ruff check .         # lint
uv run ruff format .        # formatação
uv run mypy src              # checagem de tipos
uv run pytest                # testes
```

O `pre-commit` já roda lint e formatação automaticamente antes de cada
`git commit`. O CI (`.github/workflows/ci.yml`) roda a mesma suíte completa
a cada push/pull request.

> Alterou o `Dockerfile` ou o `devcontainer.json`? Rode **Dev Containers:
> Rebuild Container**. Alterou qualquer outro arquivo (`.env`, `.py`,
> `especialidades.txt`)? Só salvar e rodar de novo — não precisa de rebuild.

## 📋 Funcionalidades

- ✅ Monitoramento automático e periódico de múltiplas especialidades
- ✅ Detecção de sessão expirada com recuperação de CAPTCHA via Telegram
- ✅ Login automático com CPF e senha (opcional)
- ✅ Alertas em tempo real no Telegram, com print da tela quando encontra vaga
- ✅ Histórico de buscas em CSV (`historico_buscas.csv`)
- ✅ Lista de especialidades editável em runtime, sem reiniciar o bot
- ✅ Configuração validada na inicialização (falha cedo se faltar algo)

## 📱 Configurar o bot do Telegram

1. No Telegram, procure `@BotFather` e use `/newbot`.
2. Copie o token gerado para `TELEGRAM_TOKEN` no `.env`.
3. Envie uma mensagem qualquer para o seu bot.
4. Acesse `https://api.telegram.org/bot<SEU_TOKEN>/getUpdates` e copie o
   `chat.id` da resposta para `CHAT_ID` no `.env`.

## ⚠️ Avisos importantes

- **Segurança**: nunca compartilhe o `.env` ou suas credenciais. Ele já está
  no `.gitignore` e nunca deve ser commitado.
- **Sessão do Chrome**: o `connect_over_cdp` depende do Chrome permanecer
  aberto com debug remoto durante toda a execução do bot.
- **Responsabilidade**: use este bot de forma responsável e em conformidade
  com os termos de uso do portal do HSPM.
- **Manutenção**: seletores de página (`browser.py`) podem quebrar se o
  portal do HSPM mudar sua interface.

## 📄 Licença

Este projeto é fornecido como está, sem garantias de nenhum tipo.
