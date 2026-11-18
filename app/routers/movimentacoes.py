from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import TipoMovimentacao
from app.paginacao import Pagina, Paginacao, paginacao
from app.periodo import Periodo, periodo
from app.repositories import movimentacoes as repo
from app.schemas.movimentacao import MovimentacaoCriar, MovimentacaoResposta
from app.services import estoque

router = APIRouter(prefix="/movimentacoes", tags=["Movimentações de estoque"])


@router.post(
    "",
    response_model=MovimentacaoResposta,
    status_code=201,
    summary="Registra uma movimentação e atualiza o estoque",
    description=(
        "- **ENTRADA** soma e **SAIDA** subtrai (quantidade sempre positiva).\n"
        "- **AJUSTE** soma a quantidade informada, que pode ser negativa (correção de inventário).\n\n"
        "O estoque nunca fica negativo: nesse caso a resposta é 409 e nada é gravado."
    ),
    responses={
        404: {"description": "Produto não encontrado."},
        409: {"description": "Estoque insuficiente."},
    },
)
def registrar(dados: MovimentacaoCriar, db: Session = Depends(get_db)):
    return estoque.registrar(db, dados.produto_id, dados.tipo, dados.quantidade, dados.motivo)


@router.get(
    "",
    response_model=Pagina[MovimentacaoResposta],
    summary="Lista movimentações (mais recentes primeiro)",
    responses={400: {"description": "data_inicio posterior a data_fim."}},
)
def listar(
    produto_id: int | None = None,
    tipo: TipoMovimentacao | None = None,
    per: Periodo = Depends(periodo),
    p: Paginacao = Depends(paginacao),
    db: Session = Depends(get_db),
):
    return repo.listar(db, p, produto_id=produto_id, tipo=tipo, data_inicio=per.data_inicio, data_fim=per.data_fim)
