"""Persistência simples em arquivo: histórico em CSV e lista de especialidades."""

import csv
import json
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


def carregar_selecionadas(caminho: Path, especialidades: list[str]) -> list[str]:
    """Carrega a seleção persistida, mantendo apenas itens da lista-base."""
    if not caminho.exists():
        return []

    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        logger.warning("Não foi possível ler a seleção de especialidades: %s", e)
        return []

    if not isinstance(dados, list) or not all(isinstance(item, str) for item in dados):
        logger.warning("Arquivo de seleção inválido; usando todas as especialidades.")
        return []

    disponiveis = set(especialidades)
    return list(dict.fromkeys(item for item in dados if item in disponiveis))


def salvar_selecionadas(caminho: Path, selecionadas: list[str], especialidades: list[str]) -> None:
    """Salva uma seleção deduplicada e limitada à lista-base."""
    disponiveis = set(especialidades)
    valores = list(dict.fromkeys(item for item in selecionadas if item in disponiveis))
    try:
        caminho.write_text(
            json.dumps(valores, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    except OSError as e:
        logger.error("Erro ao salvar seleção de especialidades: %s", e)
