"""Consultas de produto. Funções simples em vez de classes: no Python, um módulo já é o
"singleton" que no Spring seria um @Repository."""

from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import CategoriaProduto, Produto
from app.paginacao import Paginacao, paginar


def listar(
    db: Session,
    p: Paginacao,
    *,
    categoria: CategoriaProduto | None,
    subcategoria: str | None,
    ativo: bool | None,
    busca: str | None,
) -> dict[str, Any]:
    consulta = select(Produto).order_by(Produto.nome, Produto.id)
    if categoria:
        consulta = consulta.where(Produto.categoria == categoria)
    if subcategoria:
        consulta = consulta.where(Produto.subcategoria.ilike(subcategoria))
    if ativo is not None:
        consulta = consulta.where(Produto.ativo == ativo)
    if busca:
        padrao = f"%{busca}%"
        consulta = consulta.where(or_(Produto.nome.ilike(padrao), Produto.sku.ilike(padrao)))
    return paginar(db, consulta, p)
