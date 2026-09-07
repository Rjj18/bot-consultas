"""Estruturas de dados do domínio da aplicação."""

from enum import StrEnum


class StatusBusca(StrEnum):
    """Resultado possível de uma busca por vaga em uma especialidade."""

    SEM_VAGA = "SEM_VAGA"
    VAGA_ENCONTRADA = "VAGA_ENCONTRADA"
