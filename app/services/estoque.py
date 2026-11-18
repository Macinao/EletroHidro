"""Regra central do estoque: todo saldo muda por aqui, sempre com uma movimentação registrada."""

from sqlalchemy.orm import Session

from app.database import transacao
from app.errors import Conflito, NaoEncontrado
from app.models import MovimentacaoEstoque, Produto, TipoMovimentacao


def aplicar_movimentacao(
    db: Session,
    produto_id: int,
    tipo: TipoMovimentacao,
    quantidade: int,
    motivo: str,
    pedido_id: int | None = None,
) -> MovimentacaoEstoque:
    """Atualiza o saldo e registra a movimentação, SEM commitar.

    Não commita de propósito: a confirmação de pedido (fase 3) chama isto para vários
    itens e precisa que tudo ocorra na mesma transação (ou tudo, ou nada).
    """
    # SELECT ... FOR UPDATE: trava a linha do produto até o commit. Duas saídas simultâneas
    # são serializadas e a segunda enxerga o saldo já descontado. Equivale ao
    # @Lock(LockModeType.PESSIMISTIC_WRITE) do JPA.
    produto = db.get(Produto, produto_id, with_for_update=True)
    if produto is None:
        raise NaoEncontrado("Produto não encontrado.")

    variacao = -quantidade if tipo == TipoMovimentacao.SAIDA else quantidade
    novo_saldo = produto.estoque_atual + variacao
    if novo_saldo < 0:
        raise Conflito(
            f"Estoque insuficiente para {produto.sku}: saldo atual {produto.estoque_atual}, "
            f"movimentação de {variacao:+d}."
        )

    produto.estoque_atual = novo_saldo
    movimentacao = MovimentacaoEstoque(
        produto_id=produto_id, tipo=tipo, quantidade=quantidade, motivo=motivo, pedido_id=pedido_id
    )
    db.add(movimentacao)
    db.flush()  # já preenche id e data_hora
    return movimentacao


def registrar(db: Session, produto_id: int, tipo: TipoMovimentacao, quantidade: int, motivo: str) -> MovimentacaoEstoque:
    """Movimentação manual (via API): uma transação por chamada."""
    with transacao(db):
        return aplicar_movimentacao(db, produto_id, tipo, quantidade, motivo)
