"""Cliente assíncrono para envio e recebimento de updates do Telegram."""

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class TelegramEvent:
    """Evento autorizado recebido pelo bot."""

    tipo: str
    dados: dict[str, Any]


class TelegramClient:
    """Envia mensagens e mantém um único consumidor de updates."""

    def __init__(self, token: str, chat_id: str) -> None:
        self._base_url = f"https://api.telegram.org/bot{token}"
        self._chat_id = str(chat_id)
        self._client = httpx.AsyncClient(timeout=30)
        self._eventos: asyncio.Queue[TelegramEvent] = asyncio.Queue()
        self._respostas: asyncio.Queue[str] = asyncio.Queue()
        self._polling_task: asyncio.Task[None] | None = None
        self._offset: int | None = None

    async def enviar_mensagem(
        self, texto: str, reply_markup: dict[str, Any] | None = None
    ) -> int | None:
        dados: dict[str, Any] = {"chat_id": self._chat_id, "text": texto}
        if reply_markup is not None:
            dados["reply_markup"] = reply_markup
        resultado = await self._post("sendMessage", json=dados)
        mensagem = resultado.get("result")
        return mensagem.get("message_id") if isinstance(mensagem, dict) else None

    async def configurar_comandos(self) -> None:
        """Registra os comandos exibidos pelo menu nativo do Telegram."""
        await self._post(
            "setMyCommands",
            json={
                "commands": [
                    {"command": "iniciar", "description": "Iniciar as buscas"},
                    {"command": "parar", "description": "Pausar as buscas"},
                    {
                        "command": "especialidades",
                        "description": "Escolher especialidades",
                    },
                    {"command": "status", "description": "Ver o status do monitor"},
                    {"command": "ajuda", "description": "Mostrar os comandos"},
                ]
            },
        )

    async def enviar_foto(self, caminho_imagem: Path, legenda: str) -> None:
        if not caminho_imagem.exists():
            await self.enviar_mensagem(f"{legenda} (print indisponível)")
            return
        try:
            with caminho_imagem.open("rb") as foto:
                resposta = await self._client.post(
                    f"{self._base_url}/sendPhoto",
                    data={"chat_id": self._chat_id, "caption": legenda},
                    files={"photo": foto},
                )
            self._validar_resposta(resposta, "sendPhoto")
        except (OSError, httpx.HTTPError) as e:
            logger.error("Erro ao enviar foto ao Telegram: %s", e)

    async def iniciar_polling(self) -> None:
        """Inicia o consumidor de updates, caso ainda não esteja ativo."""
        if self._polling_task is None or self._polling_task.done():
            self._polling_task = asyncio.create_task(self._polling())

    async def aguardar_evento(self) -> TelegramEvent:
        """Aguarda um comando ou callback autorizado."""
        return await self._eventos.get()

    async def aguardar_resposta(self) -> str:
        """Aguarda texto comum, usado para responder ao CAPTCHA."""
        return await self._respostas.get()

    def limpar_respostas(self) -> None:
        """Descarta textos antigos antes de solicitar uma nova resposta."""
        while not self._respostas.empty():
            self._respostas.get_nowait()

    async def responder_callback(self, callback_id: str) -> None:
        await self._post("answerCallbackQuery", json={"callback_query_id": callback_id})

    async def editar_mensagem(
        self, message_id: int, texto: str, reply_markup: dict[str, Any] | None = None
    ) -> None:
        dados: dict[str, Any] = {
            "chat_id": self._chat_id,
            "message_id": message_id,
            "text": texto,
        }
        if reply_markup is not None:
            dados["reply_markup"] = reply_markup
        await self._post("editMessageText", json=dados)

    async def _polling(self) -> None:
        while True:
            try:
                resposta = await self._client.get(
                    f"{self._base_url}/getUpdates",
                    params={"offset": self._offset, "timeout": 20},
                )
                dados = self._validar_resposta(resposta, "getUpdates")
                for update in dados.get("result", []):
                    self._offset = update["update_id"] + 1
                    await self._distribuir_update(update)
            except asyncio.CancelledError:
                raise
            except (httpx.HTTPError, KeyError, TypeError) as e:
                logger.error("Erro ao receber updates do Telegram: %s", e)
                await asyncio.sleep(2)

    async def _distribuir_update(self, update: dict[str, Any]) -> None:
        mensagem = update.get("message")
        if isinstance(mensagem, dict):
            chat = mensagem.get("chat", {})
            if str(chat.get("id")) != self._chat_id:
                return
            texto = mensagem.get("text", "")
            if not isinstance(texto, str) or not texto.strip():
                return
            texto = texto.strip()
            if texto.startswith("/"):
                await self._eventos.put(TelegramEvent("comando", {"texto": texto}))
            else:
                await self._respostas.put(texto)
            return

        callback = update.get("callback_query")
        if not isinstance(callback, dict):
            return
        mensagem = callback.get("message", {})
        chat = mensagem.get("chat", {})
        if str(chat.get("id")) != self._chat_id:
            return
        await self._eventos.put(
            TelegramEvent(
                "callback",
                {
                    "id": callback.get("id", ""),
                    "dados": callback.get("data", ""),
                    "message_id": mensagem.get("message_id"),
                },
            )
        )

    async def _post(self, metodo: str, **kwargs: Any) -> dict[str, Any]:
        try:
            resposta = await self._client.post(f"{self._base_url}/{metodo}", **kwargs)
            return self._validar_resposta(resposta, metodo)
        except httpx.HTTPError as e:
            logger.error("Erro ao chamar %s no Telegram: %s", metodo, e)
            return {}

    @staticmethod
    def _validar_resposta(resposta: httpx.Response, metodo: str) -> dict[str, Any]:
        resposta.raise_for_status()
        dados = resposta.json()
        if not isinstance(dados, dict) or not dados.get("ok"):
            raise httpx.HTTPError(f"Resposta inválida em {metodo}: {dados}")
        return dados

    async def fechar(self) -> None:
        if self._polling_task is not None:
            self._polling_task.cancel()
            await asyncio.gather(self._polling_task, return_exceptions=True)
        await self._client.aclose()
