"""Filtros e casos de borda que os demais arquivos não exercitavam (achados da análise de cobertura)."""

import logging
from datetime import date, timedelta

from app.config import Settings
from app.routers.ia import get_cliente_ia
from tests.conftest import CLIENTE_BASE, CPF_VALIDO


def test_filtro_busca_de_clientes_por_nome_e_por_documento(client, criar_cliente):
    criar_cliente()
    criar_cliente(tipo="PF", documento=CPF_VALIDO, nome="Maria Souza", uf="MG")

    assert [c["nome"] for c in client.get("/clientes", params={"busca": "souza"}).json()["itens"]] == ["Maria Souza"]
    assert client.get("/clientes", params={"busca": "11222333"}).json()["total"] == 1  # trecho do CNPJ
    assert client.get("/clientes", params={"busca": "inexistente"}).json()["total"] == 0


def test_filtro_ativo_de_produtos(client, criar_produto):
    criar_produto(sku="ATIVO")
    inativo = criar_produto(sku="INATIVO")
    client.delete(f"/produtos/{inativo['id']}")

    assert [p["sku"] for p in client.get("/produtos", params={"ativo": "true"}).json()["itens"]] == ["ATIVO"]
    assert [p["sku"] for p in client.get("/produtos", params={"ativo": "false"}).json()["itens"]] == ["INATIVO"]


def test_data_fim_e_inclusiva_nas_listagens(client, criar_cliente, criar_produto):
    cliente = criar_cliente()
    produto = criar_produto(estoque=10)
    client.post(
        "/pedidos", json={"cliente_id": cliente["id"], "itens": [{"produto_id": produto["id"], "quantidade": 1}]}
    )
    hoje, ontem = date.today().isoformat(), (date.today() - timedelta(days=1)).isoformat()

    assert client.get("/pedidos", params={"data_fim": hoje}).json()["total"] == 1  # o dia inteiro de hoje entra
    assert client.get("/pedidos", params={"data_fim": ontem}).json()["total"] == 0
    assert client.get("/movimentacoes", params={"data_fim": hoje}).json()["total"] == 1
    assert client.get("/movimentacoes", params={"data_fim": ontem}).json()["total"] == 0


def test_pedido_de_valor_zero_nao_pode_ser_faturado(client, criar_cliente, criar_produto):
    """Brinde (preço 0) é permitido no cadastro, mas a conta a receber exige valor > 0 (CHECK do banco):
    sem a checagem no service, o erro viraria um 500."""
    cliente = criar_cliente()
    brinde = criar_produto(sku="BRINDE", preco_venda="0.00", estoque=5)
    pedido = client.post(
        "/pedidos", json={"cliente_id": cliente["id"], "itens": [{"produto_id": brinde["id"], "quantidade": 1}]}
    ).json()
    client.post(f"/pedidos/{pedido['id']}/confirmar")

    r = client.post(f"/pedidos/{pedido['id']}/faturar")

    assert r.status_code == 409 and "valor total zero" in r.json()["detail"]
    assert client.get(f"/pedidos/{pedido['id']}").json()["status"] == "CONFIRMADO"
    assert client.get("/contas-receber").json()["total"] == 0


def test_cnpj_invalido_em_cliente_pj(client):
    r = client.post("/clientes", json={**CLIENTE_BASE, "documento": "11.222.333/0001-80"})
    assert r.status_code == 422
    assert r.json()["erros"] == [{"campo": "documento", "mensagem": "CNPJ inválido."}]


def test_modelo_que_devolve_texto_vazio_vira_502(client, ia_fake):
    ia_fake.responder("   ")
    r = client.post("/ia/perguntar", json={"pergunta": "Quantos produtos existem?"})
    assert r.status_code == 502 and "nenhuma consulta" in r.json()["detail"]


def test_dependencia_real_cria_o_cliente_da_anthropic_quando_ha_chave():
    """Sem rede: só constrói o objeto (e reaproveita o mesmo cliente para a mesma chave)."""
    import anthropic

    settings = Settings(database_url="x", anthropic_api_key="chave-falsa")
    cliente = get_cliente_ia(settings)
    assert isinstance(cliente, anthropic.Anthropic) and get_cliente_ia(settings) is cliente


def test_consulta_da_ia_fica_registrada_no_log_de_auditoria(client, ia_fake, caplog):
    ia_fake.responder("SELECT 1 AS um")
    pergunta = "Quantos produtos existem?"

    client.post("/ia/perguntar", json={"pergunta": pergunta})

    registros = [r for r in caplog.records if r.name == "app.services.ia" and r.levelno == logging.INFO]
    assert (
        len(registros) == 1 and pergunta in registros[0].getMessage() and "SELECT 1 AS um" in registros[0].getMessage()
    )
