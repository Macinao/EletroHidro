"""Erros de negócio e seus handlers HTTP.

Equivalente ao @ControllerAdvice + @ExceptionHandler do Spring: os services lançam
exceções de domínio (sem saber nada de HTTP) e este módulo as converte em resposta.
"""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy.exc import DataError, IntegrityError
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class ErroDeNegocio(Exception):
    status_code = 400


class RequisicaoInvalida(ErroDeNegocio):
    status_code = 400


class NaoEncontrado(ErroDeNegocio):
    status_code = 404


class Conflito(ErroDeNegocio):
    status_code = 409


class DadosInvalidos(ErroDeNegocio):
    """Dados bem formados que violam um limite do negócio (ex.: total do pedido grande demais)."""

    status_code = 422


class ConsultaInvalida(ErroDeNegocio):
    """Pergunta/consulta da IA que não pode ser atendida (rejeitada, recusada, falhou ou estourou o tempo)."""

    status_code = 422


class FalhaExterna(ErroDeNegocio):
    """Falha em serviço externo (API da Anthropic)."""

    status_code = 502


class ServicoIndisponivel(ErroDeNegocio):
    """Recurso opcional não configurado (ex.: IA sem ANTHROPIC_API_KEY)."""

    status_code = 503


# --- Formato dos corpos de erro (documentados no Swagger: é o que a API realmente devolve) ---


class Erro(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"detail": "Produto não encontrado."}]})

    detail: str


class ErroDeCampo(BaseModel):
    campo: str
    mensagem: str


class ErroValidacao(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "detail": "Dados inválidos.",
                    "erros": [{"campo": "preco_venda", "mensagem": "deve ser maior ou igual a 0"}],
                }
            ]
        }
    )

    detail: str
    erros: list[ErroDeCampo]


def violou(erro: IntegrityError, constraint: str) -> bool:
    """True se o erro do banco foi causado exatamente por essa constraint (psycopg 3)."""
    diag = getattr(erro.orig, "diag", None)
    return getattr(diag, "constraint_name", None) == constraint


# Mensagens padrão do Pydantic são em inglês; traduzimos todas as que a API pode produzir.
# Tipo não mapeado vira "valor inválido": nenhuma mensagem em inglês chega ao cliente.
_MENSAGENS = {
    "missing": "campo obrigatório",
    "extra_forbidden": "campo não permitido",
    "greater_than": "deve ser maior que {gt}",
    "greater_than_equal": "deve ser maior ou igual a {ge}",
    "less_than": "deve ser menor que {lt}",
    "less_than_equal": "deve ser menor ou igual a {le}",
    "string_type": "deve ser um texto",
    "string_too_short": "deve ter ao menos {min_length} caractere(s)",
    "string_too_long": "deve ter no máximo {max_length} caracteres",
    "list_type": "deve ser uma lista",
    "too_short": "deve ter ao menos {min_length} item(ns)",
    "too_long": "deve ter no máximo {max_length} item(ns)",
    "enum": "valor inválido; permitidos: {expected}",
    "int_type": "deve ser um número inteiro",
    "int_parsing": "deve ser um número inteiro",
    "int_from_float": "deve ser um número inteiro",
    "decimal_type": "deve ser um número decimal",
    "decimal_parsing": "deve ser um número decimal",
    "decimal_max_places": "no máximo {decimal_places} casas decimais",
    "decimal_max_digits": "no máximo {max_digits} dígitos",
    "decimal_whole_digits": "no máximo {whole_digits} dígitos antes da vírgula",
    "bool_type": "deve ser verdadeiro ou falso",
    "bool_parsing": "deve ser verdadeiro ou falso",
    "date_type": "data inválida (use AAAA-MM-DD)",
    "date_parsing": "data inválida (use AAAA-MM-DD)",
    "date_from_datetime_parsing": "data inválida (use AAAA-MM-DD)",
    "model_attributes_type": "deve ser um objeto JSON",
    "model_type": "deve ser um objeto JSON",
    "dict_type": "deve ser um objeto JSON",
    "json_invalid": "JSON inválido",
}


def _traduzir(erro: dict) -> dict[str, str]:
    tipo = erro["type"]
    # O Pydantic lista opções como "'A' or 'B'"; trocamos o "or".
    ctx = {k: v.replace(" or ", " ou ") if isinstance(v, str) else v for k, v in (erro.get("ctx") or {}).items()}
    if tipo == "value_error":  # nossos validadores já escrevem em português
        mensagem = erro["msg"].removeprefix("Value error, ")
    else:
        try:
            mensagem = _MENSAGENS[tipo].format(**ctx)
        except (KeyError, IndexError):  # tipo desconhecido (ou ctx inesperado): nunca deixa vazar inglês
            mensagem = "valor inválido"
    campo = ".".join(str(parte) for parte in erro["loc"][1:]) or "corpo"
    return {"campo": campo, "mensagem": mensagem}


# Erros gerados pelo próprio framework (rota inexistente, método errado, corpo ilegível) vêm em inglês.
_ERROS_DO_FRAMEWORK = {
    "Not Found": "Recurso não encontrado.",
    "Method Not Allowed": "Método não permitido para este recurso.",
    "There was an error parsing the body": "Não foi possível ler o corpo da requisição: envie um JSON válido em UTF-8.",
}


def registrar_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def _erro_http_do_framework(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        detalhe = _ERROS_DO_FRAMEWORK.get(str(exc.detail), exc.detail)
        return JSONResponse(status_code=exc.status_code, content={"detail": detalhe}, headers=exc.headers)

    @app.exception_handler(ErroDeNegocio)
    async def _erro_de_negocio(_: Request, exc: ErroDeNegocio) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": str(exc)})

    @app.exception_handler(RequestValidationError)
    async def _validacao(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={"detail": "Dados inválidos.", "erros": [_traduzir(e) for e in exc.errors()]},
        )

    @app.exception_handler(DataError)
    async def _fora_do_intervalo(_: Request, exc: DataError) -> JSONResponse:
        # Rede de segurança: um valor que passou pela validação mas não cabe na coluna do banco
        # (ex.: id acima do maior INTEGER) viraria 500. O log guarda o detalhe técnico.
        logger.warning("Valor rejeitado pelo banco: %s", exc.orig)
        return JSONResponse(status_code=422, content={"detail": "Valor fora do intervalo suportado."})

    @app.exception_handler(Exception)
    async def _erro_interno(_: Request, exc: Exception) -> JSONResponse:
        # Erro inesperado: resposta em português; o traceback continua no log do servidor.
        return JSONResponse(status_code=500, content={"detail": "Erro interno do servidor."})
