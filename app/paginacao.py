"""Paginação comum às listagens (equivalente ao Pageable/Page do Spring Data)."""

from typing import Any, NamedTuple

from fastapi import Query
from pydantic import BaseModel, Field
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session


class Paginacao(NamedTuple):
    pagina: int
    tamanho: int


def paginacao(
    pagina: int = Query(1, ge=1, le=1_000_000, description="Número da página, começando em 1."),
    tamanho: int = Query(20, ge=1, le=100, description="Itens por página (máximo 100)."),
) -> Paginacao:
    """Dependência do FastAPI: lê ?pagina=&tamanho= da URL."""
    return Paginacao(pagina, tamanho)


class Pagina[T](BaseModel):
    itens: list[T]
    total: int = Field(examples=[43], description="Total de registros que atendem aos filtros.")
    pagina: int = Field(examples=[1])
    tamanho: int = Field(examples=[20])


def paginar(db: Session, consulta: Select, p: Paginacao) -> dict[str, Any]:
    """Executa a consulta paginada e devolve o dict que o response_model Pagina[...] valida."""
    total = db.scalar(select(func.count()).select_from(consulta.order_by(None).subquery()))
    itens = db.scalars(consulta.limit(p.tamanho).offset((p.pagina - 1) * p.tamanho)).all()
    return {"itens": itens, "total": total, "pagina": p.pagina, "tamanho": p.tamanho}
