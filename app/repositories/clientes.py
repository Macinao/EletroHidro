from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import Cliente, TipoCliente
from app.paginacao import Paginacao, paginar


def listar(
    db: Session, p: Paginacao, *, tipo: TipoCliente | None, uf: str | None, busca: str | None
) -> dict[str, Any]:
    consulta = select(Cliente).order_by(Cliente.nome, Cliente.id)
    if tipo:
        consulta = consulta.where(Cliente.tipo == tipo)
    if uf:
        consulta = consulta.where(Cliente.uf == uf.upper())
    if busca:
        padrao = f"%{busca}%"
        consulta = consulta.where(or_(Cliente.nome.ilike(padrao), Cliente.documento.like(padrao)))
    return paginar(db, consulta, p)
