"""Persistência simples em arquivo: histórico em CSV e lista de especialidades."""

import csv
import logging
from datetime import datetime
from pathlib import Path

from .models import StatusBusca

logger = logging.getLogger(__name__)


class HistoricoBuscas:
    """Registra cada busca (especialidade + resultado) em um CSV local."""

    def __init__(self, caminho: Path) -> None:
        self._caminho = caminho

    def registrar(self, especialidade: str, status: StatusBusca) -> None:
        arquivo_existe = self._caminho.exists()
        try:
            with self._caminho.open(mode="a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                if not arquivo_existe:
                    writer.writerow(["data_hora", "especialidade", "status"])
                writer.writerow(
                    [datetime.now().isoformat(timespec="seconds"), especialidade, status.value]
                )
        except OSError as e:
            logger.error("Erro ao salvar histórico em CSV: %s", e)


def carregar_especialidades(caminho: Path) -> list[str]:
    """Lê o arquivo de especialidades (uma por linha), ignorando linhas vazias."""
    if not caminho.exists():
        logger.error("Arquivo '%s' não encontrado.", caminho)
        return []
    linhas = caminho.read_text(encoding="utf-8").splitlines()
    return [linha.strip() for linha in linhas if linha.strip()]
