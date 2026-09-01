"""Exemplo de testes para as partes que não dependem de browser/rede.

carregar_especialidades e HistoricoBuscas são as peças mais fáceis de testar
isoladamente — não têm I/O de rede nem dependem do Playwright, só do sistema
de arquivos, então rodam rápido e sem mocks complexos.
"""

from pathlib import Path

from vagas_hspm.models import StatusBusca
from vagas_hspm.storage import HistoricoBuscas, carregar_especialidades


def test_carregar_especialidades_ignora_linhas_vazias(tmp_path: Path) -> None:
    arquivo = tmp_path / "especialidades.txt"
    arquivo.write_text("Cardiologia\n\n  \nOrtopedia\n", encoding="utf-8")

    resultado = carregar_especialidades(arquivo)

    assert resultado == ["Cardiologia", "Ortopedia"]


def test_carregar_especialidades_arquivo_inexistente_retorna_lista_vazia(tmp_path: Path) -> None:
    resultado = carregar_especialidades(tmp_path / "nao_existe.txt")

    assert resultado == []


def test_historico_registra_e_cria_cabecalho(tmp_path: Path) -> None:
    caminho = tmp_path / "historico.csv"
    historico = HistoricoBuscas(caminho)

    historico.registrar("Cardiologia", StatusBusca.SEM_VAGA)

    conteudo = caminho.read_text(encoding="utf-8")
    assert "data_hora,especialidade,status" in conteudo
    assert "Cardiologia,SEM_VAGA" in conteudo
