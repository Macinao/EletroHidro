from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import TipoCliente
from app.paginacao import Pagina, Paginacao, paginacao
from app.repositories import clientes as repo
from app.schemas.cliente import ClienteAtualizar, ClienteCriar, ClienteResposta
from app.services import clientes as service

router = APIRouter(prefix="/clientes", tags=["Clientes"])

_404 = {404: {"description": "Cliente não encontrado."}}


@router.post(
    "",
    response_model=ClienteResposta,
    status_code=201,
    summary="Cadastra um cliente (PF ou PJ)",
    description="O CPF/CNPJ é validado (dígitos verificadores) e gravado sem máscara.",
    responses={409: {"description": "Já existe um cliente com esse documento."}},
)
def criar(dados: ClienteCriar, db: Session = Depends(get_db)):
    return service.criar(db, dados)


@router.get("", response_model=Pagina[ClienteResposta], summary="Lista clientes (paginado, com filtros)")
def listar(
    tipo: TipoCliente | None = None,
    uf: str | None = Query(None, min_length=2, max_length=2, examples=["SP"]),
    busca: str | None = Query(None, description="Trecho do nome/razão social ou do documento."),
    p: Paginacao = Depends(paginacao),
    db: Session = Depends(get_db),
):
    return repo.listar(db, p, tipo=tipo, uf=uf, busca=busca)


@router.get("/{cliente_id}", response_model=ClienteResposta, summary="Busca um cliente", responses=_404)
def obter(cliente_id: int, db: Session = Depends(get_db)):
    return service.obter(db, cliente_id)


@router.patch("/{cliente_id}", response_model=ClienteResposta, summary="Atualiza dados do cliente", responses=_404)
def atualizar(cliente_id: int, dados: ClienteAtualizar, db: Session = Depends(get_db)):
    return service.atualizar(db, cliente_id, dados)


@router.delete(
    "/{cliente_id}",
    status_code=204,
    summary="Exclui o cliente",
    responses={**_404, 409: {"description": "O cliente possui pedidos."}},
)
def remover(cliente_id: int, db: Session = Depends(get_db)) -> None:
    service.remover(db, cliente_id)
