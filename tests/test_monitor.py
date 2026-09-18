import asyncio
from pathlib import Path
from unittest.mock import AsyncMock

from vagas_hspm.config import Settings
from vagas_hspm.monitor import (
    MonitorState,
    _aguardar_proxima_busca,
    _processar_eventos,
    _teclado_especialidades,
)
from vagas_hspm.telegram_client import TelegramEvent


def test_monitor_state_pausa_e_retomada() -> None:
    estado = MonitorState(["Cardiologia"])
    assert estado.ativo
    assert estado.filtrar(["Cardiologia", "Ortopedia"]) == ["Cardiologia"]

    estado.parar()
    assert not estado.ativo
    assert not estado.ativo_event.is_set()

    estado.iniciar()
    assert estado.ativo
    assert estado.ativo_event.is_set()
    assert estado.acordar_event.is_set()


def test_iniciar_acorda_busca_e_intervalo_continua_recorrente() -> None:
    async def executar() -> None:
        estado = MonitorState(ativo=False)
        tarefa = asyncio.create_task(_aguardar_proxima_busca(estado, 60))
        await asyncio.sleep(0)
        estado.iniciar()
        await asyncio.wait_for(tarefa, timeout=0.1)

        estado.acordar_event.clear()
        await asyncio.wait_for(_aguardar_proxima_busca(estado, 0.01), timeout=0.1)

    asyncio.run(executar())


def test_menu_tem_botoes_e_paginacao() -> None:
    especialidades = [f"Especialidade {numero}" for numero in range(16)]
    teclado = _teclado_especialidades(especialidades, set(especialidades), 1)
    botoes = [botao for linha in teclado["inline_keyboard"] for botao in linha]

    assert any(botao["callback_data"] == "esp:p:0" for botao in botoes)
    assert any(botao["callback_data"] == "esp:t:14" for botao in botoes)
    assert any(botao["callback_data"] == "esp:c" for botao in botoes)


def test_status_envia_print_da_pagina_atual() -> None:
    async def executar() -> None:
        telegram = AsyncMock()
        evento_consumido = asyncio.Event()

        async def aguardar_evento() -> TelegramEvent:
            if not evento_consumido.is_set():
                evento_consumido.set()
                return TelegramEvent("comando", {"texto": "/status"})
            await asyncio.sleep(3600)
            raise AssertionError("aguardar_evento deveria ser cancelado")

        telegram.aguardar_evento = aguardar_evento
        portal = AsyncMock()
        portal.capturar_print.return_value = True
        estado = MonitorState()
        settings = Settings(
            url_agendamento="https://example.test", telegram_token="token", chat_id="123"
        )
        tarefa = asyncio.create_task(_processar_eventos(telegram, portal, settings, estado))

        await asyncio.wait_for(evento_consumido.wait(), timeout=0.1)
        await asyncio.sleep(0)
        tarefa.cancel()
        await asyncio.wait_for(asyncio.gather(tarefa, return_exceptions=True), timeout=0.1)

        portal.capturar_print.assert_awaited_once_with(Path("print_status.png"))
        telegram.enviar_foto.assert_awaited_once_with(
            Path("print_status.png"), "ℹ️ Monitoramento ativa."
        )
        telegram.enviar_mensagem.assert_not_awaited()

    asyncio.run(executar())
