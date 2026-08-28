# Bot de Agendamento HSPM 🤖🏥

Um script de automação em Python desenvolvido para monitorar e buscar vagas de consultas médicas no portal do Hospital do Servidor Público Municipal (HSPM). O bot utiliza Playwright para interagir com a interface web e envia notificações em tempo real via Telegram caso encontre horários disponíveis.

Para contornar os sistemas de CAPTCHA do portal, o projeto adota uma arquitetura híbrida: o robô roda isolado em um contêiner Docker, mas se acopla a uma instância física do Google Chrome na máquina hospedeira através da porta de depuração (CDP).

## 🛠️ Tecnologias Utilizadas

* **Python 3.11**
* **Playwright** (Automação web)
* **Docker** (Containerização)
* **API do Telegram** (Notificações e Alertas)

## ⚙️ Pré-requisitos

Antes de iniciar, certifique-se de ter instalado em sua máquina:
* [Docker](https://docs.docker.com/get-docker/)
* Google Chrome ou Chromium
* Um bot configurado no Telegram (com Token e Chat ID)

## 📝 Configuração

1. Clone este repositório para a sua máquina.
2. Na raiz do projeto, crie um arquivo chamado `.env` e preencha com as suas credenciais:

```env
URL_AGENDAMENTO=[https://hspmagendamentoportal.hspm.sp.gov.br/NovoAgendamento](https://hspmagendamentoportal.hspm.sp.gov.br/NovoAgendamento)
TELEGRAM_TOKEN=seu_token_do_telegram_aqui
CHAT_ID=seu_chat_id_aqui