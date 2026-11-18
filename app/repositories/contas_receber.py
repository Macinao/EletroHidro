from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ContaReceber, Pedido, StatusConta
from app.paginacao import Paginacao, paginar


def listar(
    db: Session,
    p: Paginacao,
    *,
    status: StatusConta | None,
    cliente_id: int | None,
    pedido_id: int | None,
) -> dict[str, Any]:
    consulta = select(ContaReceber).order_by(ContaReceber.data_vencimento, ContaReceber.id)
    hoje = date.today()
    # Mesma regra de ContaReceber.situacao: VENCIDO = PENDENTE com vencimento no passado.
    if status == StatusConta.PAGO:
        consulta = consulta.where(ContaReceber.status == StatusConta.PAGO)
    elif status == StatusConta.PENDENTE:
        consulta = consulta.where(ContaReceber.status == StatusConta.PENDENTE, ContaReceber.data_vencimento >= hoje)
    elif status == StatusConta.VENCIDO:
        consulta = consulta.where(ContaReceber.status == StatusConta.PENDENTE, ContaReceber.data_vencimento < hoje)
    if pedido_id:
        consulta = consulta.where(ContaReceber.pedido_id == pedido_id)
    if cliente_id:
        consulta = consulta.join(Pedido, Pedido.id == ContaReceber.pedido_id).where(Pedido.cliente_id == cliente_id)
    return paginar(db, consulta, p)
