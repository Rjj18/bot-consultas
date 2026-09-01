"""Configuração da aplicação, validada a partir de variáveis de ambiente."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuração validada na inicialização — falha cedo se faltar algo essencial.

    Os nomes dos campos são casados automaticamente (case-insensitive) com as
    variáveis de ambiente equivalentes: url_agendamento <-> URL_AGENDAMENTO.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    url_agendamento: str
    telegram_token: str
    chat_id: str
    cdp_url: str = "http://localhost:9222"

    # Opcionais: só usados se o login exigir preencher CPF/senha explicitamente.
    cpf: str | None = None
    senha: str | None = None

    tempo_espera_minutos: int = 5
    arquivo_especialidades: Path = Path("especialidades.txt")
    arquivo_historico: Path = Path("historico_buscas.csv")
