from datetime import date, timedelta

import pytest
from sqlalchemy import text


@pytest.fixture
def conta(client, criar_cliente, criar_produto) -> dict:
    """Uma conta a receber PENDENTE (pedido já faturado), vencendo em 30 dias."""
    cliente = criar_cliente()
    produto = criar_produto(estoque=10, preco_venda="50.00")
    pedido = client.post(
        "/pedidos", json={"cliente_id": cliente["id"], "itens": [{"produto_id": produto["id"], "quantidade": 2}]}
    ).json()
    client.post(f"/pedidos/{pedido['id']}/confirmar")
    client.post(f"/pedidos/{pedido['id']}/faturar")
    return client.get("/contas-receber", params={"pedido_id": pedido["id"]}).json()["itens"][0]


def test_registrar_pagamento_sem_corpo_usa_hoje(client, conta):
    r = client.post(f"/contas-receber/{conta['id']}/pagamento")
    assert r.status_code == 200
    assert r.json()["status"] == "PAGO"
    assert r.json()["data_pagamento"] == date.today().isoformat()


def test_pagar_conta_ja_paga_retorna_409(client, conta):
    client.post(f"/contas-receber/{conta['id']}/pagamento")
    r = client.post(f"/contas-receber/{conta['id']}/pagamento")
    assert r.status_code == 409 and "já foi paga" in r.json()["detail"]


def test_data_de_pagamento_invalida_retorna_400(client, conta):
    futura = (date.today() + timedelta(days=1)).isoformat()
    antiga = (date.today() - timedelta(days=1)).isoformat()
    assert client.post(f"/contas-receber/{conta['id']}/pagamento", json={"data_pagamento": futura}).status_code == 400
    assert client.post(f"/contas-receber/{conta['id']}/pagamento", json={"data_pagamento": antiga}).status_code == 400
    assert client.get(f"/contas-receber/{conta['id']}").json()["status"] == "PENDENTE"  # nada foi gravado


def test_conta_inexistente_retorna_404(client):
    assert client.get("/contas-receber/999").status_code == 404
    assert client.post("/contas-receber/999/pagamento").status_code == 404


def test_conta_pendente_com_vencimento_passado_aparece_como_vencida(client, sessao, conta):
    sessao.execute(
        text("UPDATE contas_receber SET data_vencimento = :d WHERE id = :id"),
        {"d": date.today() - timedelta(days=5), "id": conta["id"]},
    )
    sessao.commit()

    assert client.get(f"/contas-receber/{conta['id']}").json()["status"] == "VENCIDO"
    assert client.get("/contas-receber", params={"status": "VENCIDO"}).json()["total"] == 1
    assert client.get("/contas-receber", params={"status": "PENDENTE"}).json()["total"] == 0

    # Pagar uma conta vencida é permitido e ela deixa de ser vencida.
    assert client.post(f"/contas-receber/{conta['id']}/pagamento").json()["status"] == "PAGO"
    assert client.get("/contas-receber", params={"status": "VENCIDO"}).json()["total"] == 0
    assert client.get("/contas-receber", params={"status": "PAGO"}).json()["total"] == 1


def test_filtrar_contas_por_cliente(client, conta):
    pedido = client.get(f"/pedidos/{conta['pedido_id']}").json()
    assert client.get("/contas-receber", params={"cliente_id": pedido["cliente_id"]}).json()["total"] == 1
    assert client.get("/contas-receber", params={"cliente_id": 999}).json()["total"] == 0
