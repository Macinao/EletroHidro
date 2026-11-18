from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.errors import Conflito, NaoEncontrado, violou
from app.models import Cliente
from app.schemas.cliente import ClienteAtualizar, ClienteCriar


def criar(db: Session, dados: ClienteCriar) -> Cliente:
    cliente = Cliente(**dados.model_dump())
    db.add(cliente)
    try:
        db.commit()
    except IntegrityError as erro:
        db.rollback()
        if violou(erro, "uq_clientes_documento"):
            raise Conflito("Já existe um cliente com esse documento.") from erro
        raise
    return cliente


def obter(db: Session, cliente_id: int) -> Cliente:
    cliente = db.get(Cliente, cliente_id)
    if cliente is None:
        raise NaoEncontrado("Cliente não encontrado.")
    return cliente


def atualizar(db: Session, cliente_id: int, dados: ClienteAtualizar) -> Cliente:
    cliente = obter(db, cliente_id)
    for campo, valor in dados.model_dump(exclude_none=True).items():
        setattr(cliente, campo, valor)
    db.commit()
    return cliente


def remover(db: Session, cliente_id: int) -> None:
    db.delete(obter(db, cliente_id))
    try:
        db.commit()
    except IntegrityError as erro:
        db.rollback()
        if violou(erro, "fk_pedidos_cliente_id"):
            raise Conflito("Não é possível excluir: o cliente possui pedidos.") from erro
        raise
