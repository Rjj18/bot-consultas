"""Cliente assíncrono para o bot do Telegram.

Usa httpx.AsyncClient em vez de requests: chamadas de requests bloqueariam o
event loop inteiro (inclusive o Playwright) enquanto a requisição HTTP roda.
"""

import asyncio
import logging
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)


class TelegramClient:
    """Envia mensagens/fotos e escuta respostas do usuário via long-polling."""

    def __init__(self, token: str, chat_id: str) -> None:
        self._base_url = f"https://api.telegram.org/bot{token}"
        self._chat_id = chat_id
        self._client = httpx.AsyncClient(timeout=10)

    async def enviar_mensagem(self, texto: str) -> None:
        try:
            await self._client.post(
                f"{self._base_url}/sendMessage",
                data={"chat_id": self._chat_id, "text": texto},
            )
        except httpx.HTTPError as e:
            logger.error("Erro ao enviar mensagem ao Telegram: %s", e)

    async def enviar_foto(self, caminho_imagem: Path, legenda: str) -> None:
        if not caminho_imagem.exists():
            await self.enviar_mensagem(f"{legenda} (print indisponível)")
            return
        try:
            with caminho_imagem.open("rb") as foto:
                await self._client.post(
                    f"{self._base_url}/sendPhoto",
                    data={"chat_id": self._chat_id, "caption": legenda},
                    files={"photo": foto},
                )
        except httpx.HTTPError as e:
            logger.error("Erro ao enviar foto ao Telegram: %s", e)

    async def limpar_updates_pendentes(self) -> int | None:
        """Descobre o offset atual para ignorar mensagens antigas no chat."""
        try:
            resp = await self._client.get(f"{self._base_url}/getUpdates")
            dados = resp.json()
            if dados.get("ok") and dados.get("result"):
                return dados["result"][-1]["update_id"] + 1
        except httpx.HTTPError:
            pass
        return None

    async def aguardar_resposta(self, offset: int | None) -> str:
        """Faz long-polling até o usuário responder algo no chat do bot."""
        logger.info("Aguardando resposta no Telegram...")
        while True:
            try:
                resp = await self._client.get(
                    f"{self._base_url}/getUpdates",
                    params={"offset": offset, "timeout": 5},
                )
                dados = resp.json()
                if dados.get("ok") and dados.get("result"):
                    for update in dados["result"]:
                        offset = update["update_id"] + 1
                        mensagem = update.get("message", {}).get("text", "").strip()
                        if mensagem:
                            return mensagem
            except httpx.HTTPError:
                pass
            await asyncio.sleep(2)

    async def fechar(self) -> None:
        await self._client.aclose()
