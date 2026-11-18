from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import StatusConta
from app.paginacao import Pagina, Paginacao, paginacao
from app.repositories import contas_receber as repo
from app.routers import Respostas
from app.schemas.conta_receber import ContaReceberResposta, PagamentoEntrada
from app.services import contas_receber as service

router = APIRouter(prefix="/contas-receber", tags=["Financeiro"])

_404: Respostas = {404: {"description": "Conta a receber não encontrada."}}


@router.get(
    "",
    response_model=Pagina[ContaReceberResposta],
    summary="Lista contas a receber (por vencimento)",
    description="`status=VENCIDO` retorna as contas PENDENTES cujo vencimento já passou.",
)
def listar(
    status: StatusConta | None = None,
    cliente_id: int | None = None,
    pedido_id: int | None = Query(None, description="Conta gerada por este pedido."),
    p: Paginacao = Depends(paginacao),
    db: Session = Depends(get_db),
):
    return repo.listar(db, p, status=status, cliente_id=cliente_id, pedido_id=pedido_id)


@router.get("/{conta_id}", response_model=ContaReceberResposta, summary="Busca uma conta a receber", responses=_404)
def obter(conta_id: int, db: Session = Depends(get_db)):
    return service.obter(db, conta_id)


@router.post(
    "/{conta_id}/pagamento",
    response_model=ContaReceberResposta,
    summary="Registra o pagamento da conta",
    description="Pagamento integral. Sem corpo, usa a data de hoje.",
    responses={
        **_404,
        400: {"description": "Data de pagamento futura ou anterior à emissão."},
        409: {"description": "A conta já está paga."},
    },
)
def pagar(conta_id: int, dados: PagamentoEntrada | None = None, db: Session = Depends(get_db)):
    return service.registrar_pagamento(db, conta_id, dados.data_pagamento if dados else None)
