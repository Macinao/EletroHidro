"""Configuração por variáveis de ambiente.

Equivalente ao application.properties + @ConfigurationProperties do Spring:
o pydantic-settings lê o .env / variáveis do SO, converte e valida os tipos.
Se DATABASE_URL faltar, a aplicação falha ao iniciar (fail-fast), não em runtime.
"""

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str

    # --- IA (opcionais: sem a chave, só o endpoint /ia/perguntar fica indisponível) ---
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-opus-5-5"
    # Usuário SOMENTE LEITURA do PostgreSQL, usado apenas para executar o SQL gerado pela IA.
    database_url_readonly: str | None = None
    ia_max_linhas: int = Field(100, ge=1, le=1000)
    ia_timeout_segundos: int = Field(5, ge=1, le=30)

    @field_validator("anthropic_api_key", "database_url_readonly")
    @classmethod
    def _vazio_vira_none(cls, valor: str | None) -> str | None:
        # No docker compose uma variável não definida chega como "" (string vazia).
        return (valor or "").strip() or None


@lru_cache
def get_settings() -> Settings:
    # lru_cache = singleton simples (no Spring, o container de beans faz isso).
    # O mypy não enxerga que o pydantic-settings preenche os campos a partir do ambiente (.env / variáveis).
    return Settings()  # type: ignore[call-arg]
