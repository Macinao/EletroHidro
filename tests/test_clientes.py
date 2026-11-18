from app.models import Pedido
from tests.conftest import CLIENTE_BASE, CNPJ_VALIDO, CPF_VALIDO


def test_criar_cliente_grava_documento_sem_mascara(client):
    r = client.post("/clientes", json=CLIENTE_BASE)
    assert r.status_code == 201
    assert r.json()["documento"] == "11222333000181"


def test_cliente_pf_com_cpf(client):
    r = client.post("/clientes", json={**CLIENTE_BASE, "tipo": "PF", "documento": CPF_VALIDO, "nome": "Maria Souza"})
    assert r.status_code == 201


def test_cpf_invalido_retorna_422(client):
    r = client.post("/clientes", json={**CLIENTE_BASE, "tipo": "PF", "documento": "111.111.111-11"})
    assert r.status_code == 422
    assert r.json()["erros"][0]["mensagem"] == "CPF inválido."


def test_cnpj_em_cliente_pf_retorna_422(client):
    r = client.post("/clientes", json={**CLIENTE_BASE, "tipo": "PF", "documento": CNPJ_VALIDO})
    assert r.status_code == 422


def test_uf_invalida_retorna_422(client):
    r = client.post("/clientes", json={**CLIENTE_BASE, "uf": "XX"})
    assert r.status_code == 422
    assert r.json()["erros"][0] == {"campo": "uf", "mensagem": "UF inválida."}


def test_documento_duplicado_retorna_409(client, criar_cliente):
    criar_cliente()
    assert client.post("/clientes", json=CLIENTE_BASE).status_code == 409


def test_filtrar_por_uf_e_tipo(client, criar_cliente):
    criar_cliente()
    criar_cliente(tipo="PF", documento=CPF_VALIDO, nome="Maria Souza", uf="MG")
    assert client.get("/clientes", params={"uf": "mg"}).json()["total"] == 1
    assert client.get("/clientes", params={"tipo": "PJ"}).json()["itens"][0]["uf"] == "SP"


def test_atualizar_cliente_nao_altera_documento(client, criar_cliente):
    cliente = criar_cliente()
    assert client.patch(f"/clientes/{cliente['id']}", json={"cidade": "Santos"}).json()["cidade"] == "Santos"
    assert client.patch(f"/clientes/{cliente['id']}", json={"documento": "x"}).status_code == 422


def test_excluir_cliente_sem_pedidos(client, criar_cliente):
    cliente = criar_cliente()
    assert client.delete(f"/clientes/{cliente['id']}").status_code == 204
    assert client.get(f"/clientes/{cliente['id']}").status_code == 404


def test_excluir_cliente_com_pedido_retorna_409(client, sessao, criar_cliente):
    cliente = criar_cliente()
    sessao.add(Pedido(cliente_id=cliente["id"]))
    sessao.commit()
    r = client.delete(f"/clientes/{cliente['id']}")
    assert r.status_code == 409
    assert client.get(f"/clientes/{cliente['id']}").status_code == 200  # nada foi apagado
