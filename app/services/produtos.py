"""Regras de produto. O service decide quando commitar (não há @Transactional)."""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.errors import Conflito, NaoEncontrado, violou
from app.models import Produto
from app.schemas.produto import ProdutoAtualizar, ProdutoCriar


def criar(db: Session, dados: ProdutoCriar) -> Produto:
    produto = Produto(**dados.model_dump())  # estoque_atual nasce 0 (default do modelo)
    db.add(produto)
    try:
        db.commit()
    except IntegrityError as erro:
        db.rollback()
        # Confiamos na UNIQUE do banco (vale mesmo com requisições simultâneas)
        # em vez de "consultar antes e inserir depois", que tem condição de corrida.
        if violou(erro, "uq_produtos_sku"):
            raise Conflito(f"Já existe um produto com o SKU {dados.sku}.") from erro
        raise
    return produto


def obter(db: Session, produto_id: int) -> Produto:
    produto = db.get(Produto, produto_id)
    if produto is None:
        raise NaoEncontrado("Produto não encontrado.")
    return produto


def atualizar(db: Session, produto_id: int, dados: ProdutoAtualizar) -> Produto:
    produto = obter(db, produto_id)
    for campo, valor in dados.model_dump(exclude_none=True).items():
        setattr(produto, campo, valor)
    db.commit()
    return produto


def inativar(db: Session, produto_id: int) -> None:
    """Exclusão lógica: produtos já vendidos continuam referenciados por pedidos antigos."""
    obter(db, produto_id).ativo = False
    db.commit()
