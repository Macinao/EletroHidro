from datetime import date

from sqlalchemy.orm import Session

from app.database import transacao
from app.errors import Conflito, NaoEncontrado, RequisicaoInvalida
from app.models import ContaReceber, StatusConta


def obter(db: Session, conta_id: int) -> ContaReceber:
    conta = db.get(ContaReceber, conta_id)
    if conta is None:
        raise NaoEncontrado("Conta a receber não encontrada.")
    return conta


def registrar_pagamento(db: Session, conta_id: int, data_pagamento: date | None) -> ContaReceber:
    with transacao(db):
        conta = db.get(ContaReceber, conta_id, with_for_update=True)  # evita pagamento duplicado simultâneo
        if conta is None:
            raise NaoEncontrado("Conta a receber não encontrada.")
        if conta.status == StatusConta.PAGO:
            raise Conflito(f"A conta {conta.id} já foi paga em {conta.data_pagamento:%d/%m/%Y}.")

        data = data_pagamento or date.today()
        if data > date.today():
            raise RequisicaoInvalida("A data do pagamento não pode ser futura.")
        if data < conta.data_emissao:
            raise RequisicaoInvalida("A data do pagamento não pode ser anterior à emissão da conta.")

        conta.status = StatusConta.PAGO
        conta.data_pagamento = data
    return conta
