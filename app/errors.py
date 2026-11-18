"""Erros de negócio e seus handlers HTTP.

Equivalente ao @ControllerAdvice + @ExceptionHandler do Spring: os services lançam
exceções de domínio (sem saber nada de HTTP) e este módulo as converte em resposta.
"""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError


class ErroDeNegocio(Exception):
    status_code = 400


class RequisicaoInvalida(ErroDeNegocio):
    status_code = 400


class NaoEncontrado(ErroDeNegocio):
    status_code = 404


class Conflito(ErroDeNegocio):
    status_code = 409


class ConsultaInvalida(ErroDeNegocio):
    """Pergunta/consulta da IA que não pode ser atendida (rejeitada, recusada, falhou ou estourou o tempo)."""

    status_code = 422


class FalhaExterna(ErroDeNegocio):
    """Falha em serviço externo (API da Anthropic)."""

    status_code = 502


class ServicoIndisponivel(ErroDeNegocio):
    """Recurso opcional não configurado (ex.: IA sem ANTHROPIC_API_KEY)."""

    status_code = 503


def violou(erro: IntegrityError, constraint: str) -> bool:
    """True se o erro do banco foi causado exatamente por essa constraint (psycopg 3)."""
    diag = getattr(erro.orig, "diag", None)
    return getattr(diag, "constraint_name", None) == constraint


# Mensagens padrão do Pydantic são em inglês; traduzimos as mais comuns.
_MENSAGENS = {
    "missing": "campo obrigatório",
    "extra_forbidden": "campo não permitido",
    "greater_than": "deve ser maior que {gt}",
    "greater_than_equal": "deve ser maior ou igual a {ge}",
    "less_than_equal": "deve ser menor ou igual a {le}",
    "string_too_short": "deve ter ao menos {min_length} caractere(s)",
    "string_too_long": "deve ter no máximo {max_length} caracteres",
    "enum": "valor inválido; permitidos: {expected}",
    "int_parsing": "deve ser um número inteiro",
    "decimal_parsing": "deve ser um número decimal",
    "decimal_max_places": "no máximo {decimal_places} casas decimais",
    "decimal_max_digits": "no máximo {max_digits} dígitos",
    "bool_parsing": "deve ser verdadeiro ou falso",
    "string_type": "deve ser um texto",
    "date_parsing": "data inválida (use AAAA-MM-DD)",
    "date_from_datetime_parsing": "data inválida (use AAAA-MM-DD)",
    "json_invalid": "JSON inválido",
}


def _traduzir(erro: dict) -> dict[str, str]:
    modelo = _MENSAGENS.get(erro["type"])
    mensagem = modelo.format(**erro.get("ctx", {})) if modelo else erro["msg"].removeprefix("Value error, ")
    return {"campo": ".".join(str(parte) for parte in erro["loc"][1:]), "mensagem": mensagem}


def registrar_handlers(app: FastAPI) -> None:
    @app.exception_handler(ErroDeNegocio)
    async def _erro_de_negocio(_: Request, exc: ErroDeNegocio) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": str(exc)})

    @app.exception_handler(RequestValidationError)
    async def _validacao(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={"detail": "Dados inválidos.", "erros": [_traduzir(e) for e in exc.errors()]},
        )
