from datetime import date, timedelta
from decimal import Decimal


def _novo_pedido(client, cliente, *itens: tuple[dict, int]) -> dict:
    corpo = {"cliente_id": cliente["id"], "itens": [{"produto_id": p["id"], "quantidade": q} for p, q in itens]}
    resposta = client.post("/pedidos", json=corpo)
    assert resposta.status_code == 201, resposta.text
    return resposta.json()


def _acao(client, pedido: dict, acao: str, **params):
    return client.post(f"/pedidos/{pedido['id']}/{acao}", params=params)


def _estoque(client, produto: dict) -> int:
    return client.get(f"/produtos/{produto['id']}").json()["estoque_atual"]


def _movimentacoes_do_pedido(client, pedido: dict, produto: dict) -> list[dict]:
    itens = client.get("/movimentacoes", params={"produto_id": produto["id"]}).json()["itens"]
    return [m for m in itens if m["pedido_id"] == pedido["id"]]


# ---------- criação ----------


def test_criar_pedido_congela_preco_e_calcula_total(client, criar_cliente, criar_produto):
    cliente = criar_cliente()
    produto = criar_produto(estoque=100, preco_venda="10.50")
    pedido = _novo_pedido(client, cliente, (produto, 3))

    assert pedido["status"] == "ABERTO"
    assert Decimal(pedido["total"]) == Decimal("31.50")

    client.patch(f"/produtos/{produto['id']}", json={"preco_venda": "99.00"})  # reajuste posterior
    reaberto = client.get(f"/pedidos/{pedido['id']}").json()
    assert Decimal(reaberto["itens"][0]["preco_unitario"]) == Decimal("10.50")
    assert _estoque(client, produto) == 100  # criar não mexe no estoque


def test_criar_pedido_validacoes(client, criar_cliente, criar_produto):
    cliente = criar_cliente()
    produto = criar_produto()
    item = {"produto_id": produto["id"], "quantidade": 1}

    assert client.post("/pedidos", json={"cliente_id": cliente["id"], "itens": []}).status_code == 422
    assert client.post("/pedidos", json={"cliente_id": cliente["id"], "itens": [{**item, "quantidade": 0}]}).status_code == 422
    repetido = client.post("/pedidos", json={"cliente_id": cliente["id"], "itens": [item, item]})
    assert repetido.status_code == 422 and repetido.json()["erros"][0]["campo"] == "itens"
    assert client.post("/pedidos", json={"cliente_id": 999, "itens": [item]}).status_code == 404
    assert client.post("/pedidos", json={"cliente_id": cliente["id"], "itens": [{**item, "produto_id": 999}]}).status_code == 404

    client.delete(f"/produtos/{produto['id']}")  # inativa
    r = client.post("/pedidos", json={"cliente_id": cliente["id"], "itens": [item]})
    assert r.status_code == 409 and "inativo" in r.json()["detail"]


# ---------- confirmar ----------


def test_confirmar_baixa_estoque_e_registra_saidas(client, criar_cliente, criar_produto):
    cliente = criar_cliente()
    a = criar_produto(sku="A", estoque=10)
    b = criar_produto(sku="B", estoque=5)
    pedido = _novo_pedido(client, cliente, (a, 4), (b, 5))

    r = _acao(client, pedido, "confirmar")
    assert r.status_code == 200 and r.json()["status"] == "CONFIRMADO"
    assert _estoque(client, a) == 6
    assert _estoque(client, b) == 0  # saldo exatamente zerado é permitido
    mov = _movimentacoes_do_pedido(client, pedido, a)
    assert [(m["tipo"], m["quantidade"]) for m in mov] == [("SAIDA", 4)]


def test_confirmar_sem_estoque_em_um_item_nao_altera_nada(client, criar_cliente, criar_produto):
    """Atomicidade: o item A tem estoque, o B não. A não pode ter sido baixado."""
    cliente = criar_cliente()
    a = criar_produto(sku="A", estoque=10)
    b = criar_produto(sku="B", estoque=1)
    pedido = _novo_pedido(client, cliente, (a, 4), (b, 2))

    r = _acao(client, pedido, "confirmar")
    assert r.status_code == 409 and "Estoque insuficiente" in r.json()["detail"]
    assert _estoque(client, a) == 10
    assert _estoque(client, b) == 1
    assert _movimentacoes_do_pedido(client, pedido, a) == []
    assert client.get(f"/pedidos/{pedido['id']}").json()["status"] == "ABERTO"


def test_confirmar_duas_vezes_retorna_409_e_baixa_uma_vez(client, criar_cliente, criar_produto):
    cliente = criar_cliente()
    produto = criar_produto(estoque=10)
    pedido = _novo_pedido(client, cliente, (produto, 4))
    assert _acao(client, pedido, "confirmar").status_code == 200
    assert _acao(client, pedido, "confirmar").status_code == 409
    assert _estoque(client, produto) == 6


# ---------- cancelar ----------


def test_cancelar_pedido_aberto_nao_mexe_no_estoque(client, criar_cliente, criar_produto):
    cliente = criar_cliente()
    produto = criar_produto(estoque=10)
    pedido = _novo_pedido(client, cliente, (produto, 4))
    r = _acao(client, pedido, "cancelar")
    assert r.status_code == 200 and r.json()["status"] == "CANCELADO"
    assert _estoque(client, produto) == 10
    assert _movimentacoes_do_pedido(client, pedido, produto) == []


def test_cancelar_pedido_confirmado_estorna_o_estoque(client, criar_cliente, criar_produto):
    cliente = criar_cliente()
    produto = criar_produto(estoque=10)
    pedido = _novo_pedido(client, cliente, (produto, 4))
    _acao(client, pedido, "confirmar")
    assert _estoque(client, produto) == 6

    assert _acao(client, pedido, "cancelar").json()["status"] == "CANCELADO"
    assert _estoque(client, produto) == 10
    tipos = sorted(m["tipo"] for m in _movimentacoes_do_pedido(client, pedido, produto))
    assert tipos == ["ENTRADA", "SAIDA"]


def test_nao_cancela_pedido_cancelado_nem_faturado(client, criar_cliente, criar_produto):
    cliente = criar_cliente()
    produto = criar_produto(estoque=10)
    cancelado = _novo_pedido(client, cliente, (produto, 1))
    _acao(client, cancelado, "cancelar")
    assert _acao(client, cancelado, "cancelar").status_code == 409

    faturado = _novo_pedido(client, cliente, (produto, 1))
    _acao(client, faturado, "confirmar")
    _acao(client, faturado, "faturar")
    assert _acao(client, faturado, "cancelar").status_code == 409
    assert _estoque(client, produto) == 9  # sem estorno indevido


# ---------- faturar / entregar ----------


def test_faturar_gera_conta_a_receber(client, criar_cliente, criar_produto):
    cliente = criar_cliente()
    produto = criar_produto(estoque=10, preco_venda="25.00")
    pedido = _novo_pedido(client, cliente, (produto, 4))
    _acao(client, pedido, "confirmar")

    r = _acao(client, pedido, "faturar", dias_vencimento=15)
    assert r.status_code == 200 and r.json()["status"] == "FATURADO"

    contas = client.get("/contas-receber", params={"pedido_id": pedido["id"]}).json()["itens"]
    assert len(contas) == 1
    conta = contas[0]
    assert Decimal(conta["valor"]) == Decimal("100.00")
    assert conta["status"] == "PENDENTE"
    assert conta["data_vencimento"] == (date.today() + timedelta(days=15)).isoformat()


def test_faturar_exige_pedido_confirmado(client, criar_cliente, criar_produto):
    cliente = criar_cliente()
    produto = criar_produto(estoque=10)
    pedido = _novo_pedido(client, cliente, (produto, 1))
    assert _acao(client, pedido, "faturar").status_code == 409  # ainda ABERTO
    assert client.get("/contas-receber").json()["total"] == 0


def test_faturar_duas_vezes_gera_uma_unica_conta(client, criar_cliente, criar_produto):
    cliente = criar_cliente()
    produto = criar_produto(estoque=10)
    pedido = _novo_pedido(client, cliente, (produto, 1))
    _acao(client, pedido, "confirmar")
    assert _acao(client, pedido, "faturar").status_code == 200
    assert _acao(client, pedido, "faturar").status_code == 409
    assert client.get("/contas-receber").json()["total"] == 1


def test_fluxo_completo_ate_entregue(client, criar_cliente, criar_produto):
    cliente = criar_cliente()
    produto = criar_produto(estoque=10)
    pedido = _novo_pedido(client, cliente, (produto, 2))
    assert _acao(client, pedido, "entregar").status_code == 409  # não pode pular etapas
    for acao, esperado in [("confirmar", "CONFIRMADO"), ("faturar", "FATURADO"), ("entregar", "ENTREGUE")]:
        r = _acao(client, pedido, acao)
        assert r.status_code == 200 and r.json()["status"] == esperado
    assert _acao(client, pedido, "cancelar").status_code == 409


def test_acoes_em_pedido_inexistente_retornam_404(client):
    for acao in ["confirmar", "faturar", "entregar", "cancelar"]:
        assert client.post(f"/pedidos/999/{acao}").status_code == 404
    assert client.get("/pedidos/999").status_code == 404


# ---------- listagem ----------


def test_listar_pedidos_com_filtros(client, criar_cliente, criar_produto):
    c1 = criar_cliente()
    c2 = criar_cliente(documento="11.444.777/0001-61", nome="Outra Ltda")
    produto = criar_produto(estoque=50)
    p1 = _novo_pedido(client, c1, (produto, 1))
    _novo_pedido(client, c2, (produto, 1))
    _acao(client, p1, "confirmar")

    assert client.get("/pedidos").json()["total"] == 2
    por_cliente = client.get("/pedidos", params={"cliente_id": c2["id"]}).json()
    assert por_cliente["total"] == 1 and por_cliente["itens"][0]["status"] == "ABERTO"
    confirmados = client.get("/pedidos", params={"status": "CONFIRMADO"}).json()
    assert [p["id"] for p in confirmados["itens"]] == [p1["id"]]
    assert client.get("/pedidos", params={"data_inicio": "2999-01-01"}).json()["total"] == 0
    assert client.get("/pedidos", params={"data_inicio": "2025-02-01", "data_fim": "2025-01-01"}).status_code == 400
