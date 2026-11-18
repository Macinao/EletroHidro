from datetime import date, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import MovimentacaoEstoque, TipoMovimentacao
from app.paginacao import Paginacao, paginar


def listar(
    db: Session,
    p: Paginacao,
    *,
    produto_id: int | None,
    tipo: TipoMovimentacao | None,
    data_inicio: date | None,
    data_fim: date | None,
) -> dict[str, Any]:
    consulta = select(MovimentacaoEstoque).order_by(MovimentacaoEstoque.data_hora.desc(), MovimentacaoEstoque.id.desc())
    if produto_id:
        consulta = consulta.where(MovimentacaoEstoque.produto_id == produto_id)
    if tipo:
        consulta = consulta.where(MovimentacaoEstoque.tipo == tipo)
    if data_inicio:
        consulta = consulta.where(MovimentacaoEstoque.data_hora >= data_inicio)
    if data_fim:  # inclusivo: vai até o fim do dia
        consulta = consulta.where(MovimentacaoEstoque.data_hora < data_fim + timedelta(days=1))
    return paginar(db, consulta, p)
