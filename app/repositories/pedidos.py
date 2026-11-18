from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Pedido, StatusPedido
from app.paginacao import Paginacao, paginar
from app.periodo import fim_do_dia, inicio_do_dia


def listar(
    db: Session,
    p: Paginacao,
    *,
    cliente_id: int | None,
    status: StatusPedido | None,
    data_inicio: date | None,
    data_fim: date | None,
) -> dict[str, Any]:
    # selectinload carrega os itens de todos os pedidos da página em UMA consulta extra
    # (evita o N+1 clássico, equivalente ao JOIN FETCH / @EntityGraph do JPA).
    consulta = select(Pedido).options(selectinload(Pedido.itens)).order_by(Pedido.data_pedido.desc(), Pedido.id.desc())
    if cliente_id:
        consulta = consulta.where(Pedido.cliente_id == cliente_id)
    if status:
        consulta = consulta.where(Pedido.status == status)
    if data_inicio:
        consulta = consulta.where(Pedido.data_pedido >= inicio_do_dia(data_inicio))
    if data_fim:
        consulta = consulta.where(Pedido.data_pedido <= fim_do_dia(data_fim))
    return paginar(db, consulta, p)
