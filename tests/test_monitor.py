from vagas_hspm.monitor import MonitorState, _teclado_especialidades


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


def test_menu_tem_botoes_e_paginacao() -> None:
    especialidades = [f"Especialidade {numero}" for numero in range(16)]
    teclado = _teclado_especialidades(especialidades, set(especialidades), 1)
    botoes = [botao for linha in teclado["inline_keyboard"] for botao in linha]

    assert any(botao["callback_data"] == "esp:p:0" for botao in botoes)
    assert any(botao["callback_data"] == "esp:t:14" for botao in botoes)
    assert any(botao["callback_data"] == "esp:c" for botao in botoes)