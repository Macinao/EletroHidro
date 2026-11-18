from decimal import Decimal

from tests.conftest import PRODUTO_BASE


def test_criar_produto_nasce_com_estoque_zero(client):
    r = client.post("/produtos", json=PRODUTO_BASE)
    assert r.status_code == 201
    corpo = r.json()
    assert corpo["estoque_atual"] == 0
    assert corpo["ativo"] is True
    assert Decimal(corpo["preco_venda"]) == Decimal("28.90")


def test_sku_duplicado_retorna_409(client, criar_produto):
    criar_produto()
    r = client.post("/produtos", json=PRODUTO_BASE)
    assert r.status_code == 409
    assert "DJ-BIP-32A" in r.json()["detail"]


def test_nao_aceita_estoque_atual_na_criacao(client):
    r = client.post("/produtos", json={**PRODUTO_BASE, "estoque_atual": 99})
    assert r.status_code == 422
    assert r.json()["erros"] == [{"campo": "estoque_atual", "mensagem": "campo não permitido"}]


def test_validacao_retorna_422_em_portugues(client):
    r = client.post("/produtos", json={**PRODUTO_BASE, "preco_venda": "-1", "categoria": "MADEIRA"})
    assert r.status_code == 422
    erros = {e["campo"]: e["mensagem"] for e in r.json()["erros"]}
    assert erros["preco_venda"] == "deve ser maior ou igual a 0"
    assert "ELETRICO" in erros["categoria"]


def test_obter_inexistente_retorna_404(client):
    r = client.get("/produtos/999")
    assert r.status_code == 404
    assert r.json()["detail"] == "Produto não encontrado."


def test_atualizar_parcialmente_mantem_demais_campos(client, criar_produto):
    produto = criar_produto()
    r = client.patch(f"/produtos/{produto['id']}", json={"preco_venda": "31.50"})
    assert r.status_code == 200
    assert Decimal(r.json()["preco_venda"]) == Decimal("31.50")
    assert r.json()["nome"] == PRODUTO_BASE["nome"]


def test_estoque_nao_pode_ser_alterado_via_patch(client, criar_produto):
    produto = criar_produto()
    assert client.patch(f"/produtos/{produto['id']}", json={"estoque_atual": 500}).status_code == 422


def test_deletar_apenas_inativa(client, criar_produto):
    produto = criar_produto()
    assert client.delete(f"/produtos/{produto['id']}").status_code == 204
    assert client.get(f"/produtos/{produto['id']}").json()["ativo"] is False


def test_listagem_com_filtros_e_paginacao(client, criar_produto):
    criar_produto(sku="A1", nome="Cabo Flexível 2,5mm", subcategoria="Cabos")
    criar_produto(sku="A2", nome="Cabo Flexível 4mm", subcategoria="Cabos")
    criar_produto(sku="B1", nome="Tubo PVC 25mm", categoria="HIDRAULICO", subcategoria="Tubos", unidade="M")

    todos = client.get("/produtos").json()
    assert todos["total"] == 3

    pagina = client.get("/produtos", params={"tamanho": 2, "pagina": 2}).json()
    assert pagina["total"] == 3 and len(pagina["itens"]) == 1

    hidraulicos = client.get("/produtos", params={"categoria": "HIDRAULICO"}).json()
    assert [p["sku"] for p in hidraulicos["itens"]] == ["B1"]

    cabos = client.get("/produtos", params={"subcategoria": "cabos", "busca": "4mm"}).json()
    assert [p["sku"] for p in cabos["itens"]] == ["A2"]


def test_tamanho_de_pagina_acima_do_maximo_retorna_422(client):
    assert client.get("/produtos", params={"tamanho": 1000}).status_code == 422
