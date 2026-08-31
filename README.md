# Bot de Agendamento HSPM 🤖🏥

Um script de automação em Python desenvolvido para monitorar e buscar vagas de consultas médicas em múltiplas especialidades no portal do Hospital do Servidor Público Municipal (HSPM). O bot utiliza Playwright para interagir com a interface web, faz login automático com suas credenciais e envia notificações em tempo real via Telegram caso encontre horários disponíveis.

## 🛠️ Tecnologias Utilizadas

* **Python 3.11**
* **Playwright** (Automação web e navegação)
* **Docker** (Containerização)
* **API do Telegram** (Notificações e Alertas)
* **Requests** (Comunicação com Telegram)

## ⚙️ Pré-requisitos

Antes de iniciar, certifique-se de ter instalado em sua máquina:
* [Docker](https://docs.docker.com/get-docker/)
* Um bot configurado no Telegram (com Token e Chat ID)
* Acesso ao portal de agendamento do HSPM

## 📝 Configuração

### 1. Clone este repositório para a sua máquina

```bash
git clone https://github.com/Rjj18/bot-consultas.git
cd bot-consultas
```

### 2. Configure as variáveis de ambiente

Na raiz do projeto, crie um arquivo chamado `.env` e preencha com as suas credenciais:

```env
URL_AGENDAMENTO=https://hspmagendamentoportal.hspm.sp.gov.br/NovoAgendamento
CPF=seu_cpf_aqui
SENHA=sua_senha_aqui
TELEGRAM_TOKEN=seu_token_do_telegram_aqui
CHAT_ID=seu_chat_id_aqui
```

### 3. Variáveis de Ambiente Explicadas

| Variável | Descrição | Exemplo |
|----------|-----------|---------|
| `URL_AGENDAMENTO` | URL do portal de agendamento do HSPM | `https://hspmagendamentoportal.hspm.sp.gov.br/NovoAgendamento` |
| `CPF` | Seu CPF para login | `12345678910` |
| `SENHA` | Sua senha para login | `sua_senha_segura` |
| `TELEGRAM_TOKEN` | Token do bot Telegram | `123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11` |
| `CHAT_ID` | Seu ID de chat no Telegram | `987654321` |

## 🚀 Como Usar

### Construir a Imagem Docker

```bash
sudo docker build -t bot-consultas .
```

### Executar o Bot com Docker

```bash
sudo docker run --rm -it \
  --env-file .env \
  -v "$PWD":/app \
  bot-consultas
```

### Executar Diretamente no Python

Se preferir executar sem Docker:

```bash
pip install -r requirements.txt
python main.py
```

### Iniciar o Navegador com Remote Debugging

Antes de executar o bot, é necessário iniciar o Google Chrome em modo de debugging para que o Playwright possa se conectar:

```bash
google-chrome --remote-debugging-port=9222 --user-data-dir="/tmp/chrome_dev_sessao"
```

Após iniciar o Chrome com este comando, execute o bot em outro terminal:

```bash
sudo docker run --rm -it --network host --env-file .env -v "$PWD":/app robo-hspm-mvp
```

## 📋 Funcionalidades

- ✅ **Monitoramento Automático**: Verifica periodicamente vagas em múltiplas especialidades
- ✅ **Autenticação Automática**: Faz login com CPF e senha automaticamente
- ✅ **Notificações em Tempo Real**: Envia alertas via Telegram quando uma vaga é encontrada
- ✅ **Capturas de Tela**: Registra automaticamente a tela quando uma vaga é disponibilizada
- ✅ **Logs Detalhados**: Mantém um histórico completo das operações
- ✅ **Múltiplas Especialidades**: Monitora várias especialidades médicas simultaneamente
- ✅ **Recuperação de Sessão**: Detecta quando a sessão expira e solicita novo CAPTCHA via Telegram
- ✅ **Histórico em CSV**: Registra automaticamente cada busca e resultado em arquivo CSV

## 🔄 Atualizações Recentes

### v1.1.0
- ✨ **CAPTCHA via Telegram**: O bot agora solicita o CAPTCHA através do Telegram quando a sessão expira
- 📝 **Registro em CSV**: Todas as buscas são registradas em `historico_buscas.csv` para análise posterior
- 📂 **Especialidades Dinâmicas**: Carregamento de especialidades a partir do arquivo `especialidades.txt`
- 🔄 **Detecção de Deslogin**: O bot identifica automaticamente quando foi deslogado e reinicia o fluxo
- 🐳 **Suporte a Chrome Remoto**: Integração com Chrome rodando em debugging mode via CDP (Chrome DevTools Protocol)
- 🛡️ **Tratamento de Erros Robusto**: Melhorias significativas no tratamento de exceções e recuperação de falhas

## 🎯 Especialidades Monitoradas

O bot atualmente monitora as seguintes especialidades:

- Clínica Médica
- Dermatologia
- Nutrição - Dietética
- Odontologia - Dentística
- Otorrinolaringologia
- Urologia

Para adicionar ou remover especialidades, edite a lista `ESPECIALIDADES` no arquivo `main.py`.

## 📱 Configurar Bot do Telegram

1. Abra o Telegram e procure por `@BotFather`
2. Inicie uma conversa e use o comando `/newbot`
3. Siga as instruções para criar seu bot
4. Copie o token fornecido e adicione ao arquivo `.env`
5. Para obter seu `CHAT_ID`, envie uma mensagem para seu bot e acesse: `https://api.telegram.org/botSEU_TOKEN/getUpdates`

## ⚙️ Tempo de Espera

Por padrão, o bot verifica vagas a cada 5 minutos. Para alterar este intervalo, edite a variável `TEMPO_ESPERA_MINUTOS` no arquivo `main.py`.

## 📝 Logs

Os logs da aplicação são exibidos no console com timestamp e nível de severidade (INFO, ERROR, WARNING).

## ⚠️ Avisos Importantes

- **Segurança**: Nunca compartilhe seu arquivo `.env` ou suas credenciais com outras pessoas
- **Responsabilidade**: Use este bot de forma responsável e em conformidade com os termos de serviço do HSPM
- **Manutenção**: O bot pode necessitar de ajustes se o portal do HSPM sofrer atualizações em sua interface

## 📄 Licença

Este projeto é fornecido como está, sem garantias de nenhum tipo.