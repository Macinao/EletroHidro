"""Configuração por variáveis de ambiente.

Equivalente ao application.properties + @ConfigurationProperties do Spring:
o pydantic-settings lê o .env / variáveis do SO, converte e valida os tipos.
Se DATABASE_URL faltar, a aplicação falha ao iniciar (fail-fast), não em runtime.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str


@lru_cache
def get_settings() -> Settings:
    # lru_cache = singleton simples (no Spring, o container de beans faz isso).
    return Settings()
