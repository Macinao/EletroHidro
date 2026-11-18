from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import StatusPedido
from app.paginacao import Pagina, Paginacao, paginacao
from app.periodo import Periodo, periodo
from app.repositories import pedidos as repo
from app.routers import Respostas
from app.schemas.pedido import PedidoCriar, PedidoResposta
from app.services import pedidos as service

router = APIRouter(prefix="/pedidos", tags=["Pedidos"])

_404: Respostas = {404: {"description": "Pedido não encontrado."}}
_409: Respostas = {409: {"description": "Transição de status inválida para o estado atual do pedido."}}


@router.post(
    "",
    response_model=PedidoResposta,
    status_code=201,
    summary="Cria um pedido (status ABERTO)",
    description=(
        "O preço de cada item é o preço atual do produto, congelado no pedido. "
        "O estoque ainda **não** é movimentado: isso acontece ao confirmar."
    ),
    responses={
        404: {"description": "Cliente ou produto não encontrado."},
        409: {"description": "Produto inativo."},
    },
)
def criar(dados: PedidoCriar, db: Session = Depends(get_db)):
    return service.criar(db, dados)


@router.get(
    "",
    response_model=Pagina[PedidoResposta],
    summary="Lista pedidos (mais recentes primeiro)",
    responses={400: {"description": "data_inicio posterior a data_fim."}},
)
def listar(
    cliente_id: int | None = None,
    status: StatusPedido | None = None,
    per: Periodo = Depends(periodo),
    p: Paginacao = Depends(paginacao),
    db: Session = Depends(get_db),
):
    return repo.listar(db, p, cliente_id=cliente_id, status=status, data_inicio=per.data_inicio, data_fim=per.data_fim)


@router.get("/{pedido_id}", response_model=PedidoResposta, summary="Busca um pedido", responses=_404)
def obter(pedido_id: int, db: Session = Depends(get_db)):
    return service.obter(db, pedido_id)


@router.post(
    "/{pedido_id}/confirmar",
    response_model=PedidoResposta,
    summary="ABERTO → CONFIRMADO: valida o estoque e baixa os itens",
    description=(
        "Gera uma movimentação de SAÍDA por item, na mesma transação. "
        "Se faltar estoque em qualquer item, nada é alterado (409)."
    ),
    responses={**_404, 409: {"description": "Estoque insuficiente ou pedido fora do status ABERTO."}},
)
def confirmar(pedido_id: int, db: Session = Depends(get_db)):
    return service.confirmar(db, pedido_id)


@router.post(
    "/{pedido_id}/faturar",
    response_model=PedidoResposta,
    summary="CONFIRMADO → FATURADO: gera a conta a receber",
    responses={**_404, **_409},
)
def faturar(
    pedido_id: int,
    dias_vencimento: int = Query(30, ge=0, le=365, description="Prazo, em dias, para o vencimento da conta."),
    db: Session = Depends(get_db),
):
    return service.faturar(db, pedido_id, dias_vencimento)


@router.post(
    "/{pedido_id}/entregar",
    response_model=PedidoResposta,
    summary="FATURADO → ENTREGUE",
    responses={**_404, **_409},
)
def entregar(pedido_id: int, db: Session = Depends(get_db)):
    return service.entregar(db, pedido_id)


@router.post(
    "/{pedido_id}/cancelar",
    response_model=PedidoResposta,
    summary="Cancela um pedido ABERTO ou CONFIRMADO",
    description=(
        "Se estiver CONFIRMADO, o estoque é estornado (ENTRADA por item). Pedidos faturados não podem ser cancelados."
    ),
    responses={**_404, 409: {"description": "Pedido já faturado, entregue ou cancelado."}},
)
def cancelar(pedido_id: int, db: Session = Depends(get_db)):
    return service.cancelar(db, pedido_id)
