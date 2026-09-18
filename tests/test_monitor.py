import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, Mock

from vagas_hspm.config import Settings
from vagas_hspm.models import StatusBusca
from vagas_hspm.monitor import (
    MonitorState,
    _aguardar_proxima_busca,
    _ciclo_de_busca,
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


def test_menu_exibe_toggle_de_print() -> None:
    ligado = _teclado_especialidades(["Cardiologia"], {"Cardiologia"}, 0, True)
    desligado = _teclado_especialidades(["Cardiologia"], {"Cardiologia"}, 0, False)

    botoes_ligado = [botao for linha in ligado["inline_keyboard"] for botao in linha]
    botoes_desligado = [botao for linha in desligado["inline_keyboard"] for botao in linha]

    assert {botao["text"] for botao in botoes_ligado} & {"🖼️ Print: ligado"}
    assert {botao["text"] for botao in botoes_desligado} & {"🖼️ Print: desligado"}


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


def test_mapeia_detalhes_apenas_quando_encontra_vaga() -> None:
    async def executar() -> None:
        telegram = AsyncMock()
        historico = Mock()
        estado = MonitorState()
        portal = AsyncMock()
        portal.deslogou_agora.return_value = False
        portal.buscar_especialidade.side_effect = [
            StatusBusca.SEM_VAGA,
            StatusBusca.VAGA_ENCONTRADA,
        ]
        portal.mapear_vagas.return_value = [
            {
                "mes": "setembro",
                "quantidade": "1 vagas",
                "horario": "14:10",
                "medico": "Dr. Teste",
            }
        ]
        portal.capturar_print.return_value = False

        await _ciclo_de_busca(
            portal,
            telegram,
            historico,
            ["Cardiologia", "Ortopedia"],
            estado,
        )

        portal.mapear_vagas.assert_awaited_once_with()
        historico.registrar.assert_any_call("Cardiologia", StatusBusca.SEM_VAGA, 0)
        historico.registrar.assert_any_call("Ortopedia", StatusBusca.VAGA_ENCONTRADA, 1)
        assert any(
            "14:10" in chamada.args[0] for chamada in telegram.enviar_mensagem.await_args_list
        )

    asyncio.run(executar())
