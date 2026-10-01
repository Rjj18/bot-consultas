"""Ponto de entrada: `uv run python -m vagas_hspm`."""

import asyncio
import logging

from .config import Settings
from .monitor import monitorar_vagas

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def main() -> None:
    settings = Settings()
    try:
        asyncio.run(monitorar_vagas(settings))
    except KeyboardInterrupt:
        logging.info("Encerramento solicitado pelo usuário.")


if __name__ == "__main__":
    main()
