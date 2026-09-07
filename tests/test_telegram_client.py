import asyncio

from vagas_hspm.telegram_client import TelegramClient


def test_update_autorizado_separa_comando_e_resposta() -> None:
    async def executar() -> None:
        telegram = TelegramClient("token", "123")
        await telegram._distribuir_update(
            {"update_id": 1, "message": {"chat": {"id": 123}, "text": "/parar"}}
        )
        await telegram._distribuir_update(
            {"update_id": 2, "message": {"chat": {"id": 123}, "text": "captcha"}}
        )

        evento = await telegram.aguardar_evento()
        assert evento.tipo == "comando"
        assert evento.dados["texto"] == "/parar"
        assert await telegram.aguardar_resposta() == "captcha"
        await telegram.fechar()

    asyncio.run(executar())


def test_update_de_outro_chat_e_ignorado() -> None:
    async def executar() -> None:
        telegram = TelegramClient("token", "123")
        await telegram._distribuir_update(
            {"update_id": 1, "message": {"chat": {"id": 456}, "text": "/parar"}}
        )
        assert telegram._eventos.empty()
        assert telegram._respostas.empty()
        await telegram.fechar()

    asyncio.run(executar())