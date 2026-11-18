from functools import lru_cache

import anthropic
from fastapi import APIRouter, Depends
from sqlalchemy import Engine

from app.config import Settings, get_settings
from app.errors import ServicoIndisponivel
from app.repositories.leitura import engine_somente_leitura
from app.schemas.ia import PerguntaIA, RespostaIA
from app.services import ia

router = APIRouter(prefix="/ia", tags=["IA"])


@lru_cache
def _criar_cliente(api_key: str) -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=api_key, timeout=60.0)  # um cliente (e pool HTTP) por chave, reaproveitado


def get_cliente_ia(settings: Settings = Depends(get_settings)) -> anthropic.Anthropic:
    """Dependência: os testes a substituem por um mock (dependency_overrides), então nunca chamam a API real."""
    if not settings.anthropic_api_key:
        raise ServicoIndisponivel(
            "O recurso de IA está desativado: defina a variável de ambiente ANTHROPIC_API_KEY. "
            "O restante da API funciona normalmente."
        )
    return _criar_cliente(settings.anthropic_api_key)


def get_engine_leitura(settings: Settings = Depends(get_settings)) -> Engine:
    if not settings.database_url_readonly:
        raise ServicoIndisponivel(
            "O recurso de IA exige o usuário somente leitura do banco: defina DATABASE_URL_READONLY."
        )
    return engine_somente_leitura(settings.database_url_readonly)


@router.post(
    "/perguntar",
    response_model=RespostaIA,
    summary="Responde uma pergunta em português consultando o banco (via IA)",
    description=(
        "O Claude converte a pergunta em **um único SELECT**, que é validado (parser SQL, lista de tabelas "
        "permitidas, LIMIT máximo) e executado com um **usuário PostgreSQL somente leitura**, em transação "
        "READ ONLY e com tempo limite. Retorna a consulta executada e o resultado."
    ),
    responses={
        422: {"description": "Consulta rejeitada, recusada pelo modelo, com erro de execução ou estourou o tempo."},
        502: {"description": "Falha ao falar com a API da Anthropic."},
        503: {"description": "IA não configurada (ANTHROPIC_API_KEY ou DATABASE_URL_READONLY ausentes)."},
    },
)
def perguntar(
    dados: PerguntaIA,
    cliente: anthropic.Anthropic = Depends(get_cliente_ia),
    engine: Engine = Depends(get_engine_leitura),
    settings: Settings = Depends(get_settings),
):
    return ia.perguntar(cliente, engine, settings, dados.pergunta)
