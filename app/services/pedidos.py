"""Ciclo de vida do pedido: ABERTO → CONFIRMADO → FATURADO → ENTREGUE (ou CANCELADO).

Cada transição é UMA transação (`with transacao(db)`): ou tudo acontece (status, movimentações
de estoque, conta a receber) ou nada acontece.
"""

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import transacao
from app.errors import Conflito, NaoEncontrado
from app.models import (
    Cliente,
    ContaReceber,
    ItemPedido,
    Pedido,
    Produto,
    StatusPedido,
    TipoMovimentacao,
)
from app.schemas.pedido import PedidoCriar
from app.services import estoque


def criar(db: Session, dados: PedidoCriar) -> Pedido:
    if db.get(Cliente, dados.cliente_id) is None:
        raise NaoEncontrado("Cliente não encontrado.")

    ids = [item.produto_id for item in dados.itens]
    produtos = {p.id: p for p in db.scalars(select(Produto).where(Produto.id.in_(ids)))}
    ausentes = sorted(set(ids) - produtos.keys())
    if ausentes:
        raise NaoEncontrado(f"Produto(s) não encontrado(s): {', '.join(map(str, ausentes))}.")
    inativos = [p.sku for p in produtos.values() if not p.ativo]
    if inativos:
        raise Conflito(f"Produto(s) inativo(s): {', '.join(sorted(inativos))}.")

    pedido = Pedido(
        cliente_id=dados.cliente_id,
        itens=[
            # Preço congelado agora; o estoque só é verificado ao CONFIRMAR.
            ItemPedido(
                produto_id=i.produto_id, quantidade=i.quantidade, preco_unitario=produtos[i.produto_id].preco_venda
            )
            for i in dados.itens
        ],
    )
    with transacao(db):
        db.add(pedido)
    return pedido


def obter(db: Session, pedido_id: int) -> Pedido:
    pedido = db.get(Pedido, pedido_id)
    if pedido is None:
        raise NaoEncontrado("Pedido não encontrado.")
    return pedido


def _travar(db: Session, pedido_id: int) -> Pedido:
    """Carrega o pedido com FOR UPDATE: duas transições simultâneas do mesmo pedido
    (ex.: confirmar duas vezes) são serializadas, e a segunda vê o status já alterado."""
    pedido = db.get(Pedido, pedido_id, with_for_update=True)
    if pedido is None:
        raise NaoEncontrado("Pedido não encontrado.")
    return pedido


def _exigir_status(pedido: Pedido, esperado: StatusPedido, acao: str) -> None:
    if pedido.status != esperado:
        raise Conflito(
            f"Não é possível {acao} o pedido {pedido.id}: ele está {pedido.status} e precisa estar {esperado}."
        )


def _itens_em_ordem(pedido: Pedido) -> list[ItemPedido]:
    # Sempre travamos os produtos em ordem crescente de id: dois pedidos que compartilham
    # produtos nunca se travam em ordem inversa (evita deadlock).
    return sorted(pedido.itens, key=lambda item: item.produto_id)


def confirmar(db: Session, pedido_id: int) -> Pedido:
    with transacao(db):
        pedido = _travar(db, pedido_id)
        _exigir_status(pedido, StatusPedido.ABERTO, "confirmar")
        for item in _itens_em_ordem(pedido):
            # Se faltar estoque em QUALQUER item, lança Conflito e o rollback desfaz os anteriores.
            estoque.aplicar_movimentacao(
                db, item.produto_id, TipoMovimentacao.SAIDA, item.quantidade, f"Venda - pedido #{pedido.id}", pedido.id
            )
        pedido.status = StatusPedido.CONFIRMADO
    return pedido


def faturar(db: Session, pedido_id: int, dias_vencimento: int) -> Pedido:
    with transacao(db):
        pedido = _travar(db, pedido_id)
        _exigir_status(pedido, StatusPedido.CONFIRMADO, "faturar")
        if pedido.total <= 0:
            raise Conflito("Pedido com valor total zero não pode ser faturado.")
        hoje = date.today()
        db.add(
            ContaReceber(
                pedido_id=pedido.id,
                valor=pedido.total,
                data_emissao=hoje,
                data_vencimento=hoje + timedelta(days=dias_vencimento),
            )
        )
        pedido.status = StatusPedido.FATURADO
    return pedido


def entregar(db: Session, pedido_id: int) -> Pedido:
    with transacao(db):
        pedido = _travar(db, pedido_id)
        _exigir_status(pedido, StatusPedido.FATURADO, "entregar")
        pedido.status = StatusPedido.ENTREGUE
    return pedido


def cancelar(db: Session, pedido_id: int) -> Pedido:
    with transacao(db):
        pedido = _travar(db, pedido_id)
        if pedido.status == StatusPedido.CONFIRMADO:
            # O estoque já foi baixado: devolve cada item com uma ENTRADA rastreável ao pedido.
            for item in _itens_em_ordem(pedido):
                estoque.aplicar_movimentacao(
                    db,
                    item.produto_id,
                    TipoMovimentacao.ENTRADA,
                    item.quantidade,
                    f"Estorno - pedido #{pedido.id}",
                    pedido.id,
                )
        elif pedido.status != StatusPedido.ABERTO:
            # FATURADO/ENTREGUE exigiriam cancelar a conta a receber e a entrega: fora do escopo.
            raise Conflito(f"Não é possível cancelar o pedido {pedido.id}: ele está {pedido.status}.")
        pedido.status = StatusPedido.CANCELADO
    return pedido
