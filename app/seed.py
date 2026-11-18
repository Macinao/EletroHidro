"""Dados de demonstração: python -m app.seed  (use --limpar para recomeçar do zero).

O seed NÃO insere pedidos "na marra": ele passa pelos mesmos services da API (criar, confirmar,
faturar, entregar, cancelar, pagar). Assim os dados nascem consistentes (estoque = soma das
movimentações) e o seed também funciona como um teste de ponta a ponta das regras.
Depois, as datas são recuadas para espalhar os pedidos pelos últimos ~6 meses, o que dá
sentido aos relatórios por mês e às contas vencidas. É determinístico (semente fixa).
"""

import argparse
import random
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import func, select, text, update
from sqlalchemy.orm import Session

from app.database import Base, SessionLocal
from app.models import (
    Cliente,
    ContaReceber,
    MovimentacaoEstoque,
    Pedido,
    Produto,
    TipoMovimentacao,
)
from app.schemas.cliente import ClienteCriar
from app.schemas.pedido import ItemCriar, PedidoCriar
from app.services import clientes as clientes_service
from app.services import contas_receber as contas_service
from app.services import estoque
from app.services import pedidos as pedidos_service

# (sku, nome, categoria, subcategoria, unidade, preço, estoque mínimo)
PRODUTOS = [
    ("CAB-FLEX-1.5-AZ", "Cabo Flexível 1,5mm² Azul 750V - Rolo 100m", "ELETRICO", "Fios e Cabos", "RL", "169.90", 10),
    ("CAB-FLEX-2.5-VM", "Cabo Flexível 2,5mm² Vermelho 750V - Rolo 100m", "ELETRICO", "Fios e Cabos", "RL", "279.90", 10),
    ("CAB-FLEX-2.5-PT", "Cabo Flexível 2,5mm² Preto 750V - Rolo 100m", "ELETRICO", "Fios e Cabos", "RL", "279.90", 10),
    ("CAB-FLEX-4-AZ", "Cabo Flexível 4mm² Azul 750V - Rolo 100m", "ELETRICO", "Fios e Cabos", "RL", "449.90", 6),
    ("CAB-FLEX-6-PT", "Cabo Flexível 6mm² Preto 750V - Rolo 100m", "ELETRICO", "Fios e Cabos", "RL", "659.90", 5),
    ("CAB-PP-3X2.5", "Cabo PP 3x2,5mm² 750V (por metro)", "ELETRICO", "Fios e Cabos", "M", "9.80", 100),
    ("DJ-MONO-20A", "Disjuntor Monopolar 20A Curva C", "ELETRICO", "Disjuntores", "UN", "14.90", 40),
    ("DJ-MONO-32A", "Disjuntor Monopolar 32A Curva C", "ELETRICO", "Disjuntores", "UN", "15.90", 40),
    ("DJ-BIP-40A", "Disjuntor Bipolar 40A Curva C", "ELETRICO", "Disjuntores", "UN", "49.90", 20),
    ("DJ-TRI-63A", "Disjuntor Tripolar 63A Curva C", "ELETRICO", "Disjuntores", "UN", "89.90", 10),
    ("DR-25A-30MA", "Interruptor Diferencial Residual DR 25A 30mA", "ELETRICO", "Disjuntores", "UN", "189.00", 8),
    ("DPS-275V-20KA", "Protetor contra Surtos DPS 275V 20kA", "ELETRICO", "Proteção", "UN", "79.90", 8),
    ("TOM-2P-T-10A", "Tomada 2P+T 10A Branca", "ELETRICO", "Tomadas", "UN", "9.50", 50),
    ("TOM-2P-T-20A", "Tomada 2P+T 20A Branca", "ELETRICO", "Tomadas", "UN", "11.90", 50),
    ("INT-SIMP-10A", "Interruptor Simples 10A Branco", "ELETRICO", "Interruptores", "UN", "8.90", 50),
    ("INT-PARAL-10A", "Interruptor Paralelo 10A Branco", "ELETRICO", "Interruptores", "UN", "13.90", 30),
    ("LAMP-LED-9W", "Lâmpada LED Bulbo 9W 6500K", "ELETRICO", "Iluminação", "UN", "8.90", 100),
    ("LAMP-LED-15W", "Lâmpada LED Bulbo 15W 6500K", "ELETRICO", "Iluminação", "UN", "15.90", 60),
    ("FITA-ISOL-19", "Fita Isolante 19mm x 20m", "ELETRICO", "Acessórios", "RL", "6.90", 80),
    ("ELETRODUTO-25", "Eletroduto Corrugado 25mm - Rolo 50m", "ELETRICO", "Eletrodutos", "RL", "89.90", 10),
    ("CAIXA-4X2", "Caixa de Luz 4x2 de Embutir", "ELETRICO", "Eletrodutos", "UN", "3.20", 100),
    ("QD-12-DISJ", "Quadro de Distribuição 12 Disjuntores", "ELETRICO", "Quadros", "UN", "119.90", 6),
    ("TUBO-PVC-25", "Tubo PVC Soldável 25mm - Barra 6m", "HIDRAULICO", "Tubos PVC", "UN", "28.90", 40),
    ("TUBO-PVC-32", "Tubo PVC Soldável 32mm - Barra 6m", "HIDRAULICO", "Tubos PVC", "UN", "49.90", 30),
    ("TUBO-PVC-50", "Tubo PVC Soldável 50mm - Barra 6m", "HIDRAULICO", "Tubos PVC", "UN", "79.90", 20),
    ("TUBO-ESG-100", "Tubo PVC Esgoto 100mm - Barra 6m", "HIDRAULICO", "Tubos PVC", "UN", "118.90", 15),
    ("JOELHO-25-90", "Joelho 90° Soldável 25mm", "HIDRAULICO", "Conexões", "UN", "1.90", 200),
    ("JOELHO-32-90", "Joelho 90° Soldável 32mm", "HIDRAULICO", "Conexões", "UN", "3.40", 150),
    ("TE-25", "Tê Soldável 25mm", "HIDRAULICO", "Conexões", "UN", "2.80", 150),
    ("LUVA-25", "Luva Soldável 25mm", "HIDRAULICO", "Conexões", "UN", "1.50", 200),
    ("LUVA-50", "Luva Soldável 50mm", "HIDRAULICO", "Conexões", "UN", "7.90", 80),
    ("ADAPT-25-3/4", "Adaptador Soldável Curto com Bolsa e Rosca 25mm x 3/4\"", "HIDRAULICO", "Conexões", "UN", "2.40", 150),
    ("REG-GAV-3/4", "Registro de Gaveta Bruto 3/4\"", "HIDRAULICO", "Registros", "UN", "39.90", 20),
    ("REG-ESF-25", "Registro de Esfera PVC Soldável 25mm", "HIDRAULICO", "Registros", "UN", "18.90", 30),
    ("REG-PRES-1/2", "Registro de Pressão 1/2\" Cromado", "HIDRAULICO", "Registros", "UN", "42.90", 15),
    ("TORN-JARD-1/2", "Torneira de Jardim 1/2\" PVC", "HIDRAULICO", "Torneiras", "UN", "14.90", 30),
    ("TORN-LAV-BAIXA", "Torneira de Lavatório Bica Baixa Cromada", "HIDRAULICO", "Torneiras", "UN", "54.90", 15),
    ("CX-AGUA-500L", "Caixa d'Água de Polietileno 500L com Tampa", "HIDRAULICO", "Reservatórios", "UN", "389.90", 5),
    ("TORN-BOIA-3/4", "Torneira de Boia 3/4\"", "HIDRAULICO", "Reservatórios", "UN", "24.90", 20),
    ("FITA-VEDA-18", "Fita Veda Rosca 18mm x 50m", "HIDRAULICO", "Vedação", "RL", "8.90", 60),
    ("COLA-PVC-175G", "Adesivo Plástico para PVC 175g", "HIDRAULICO", "Vedação", "UN", "16.90", 30),
    ("ENGATE-INOX-40", "Engate Flexível Inox 40cm", "HIDRAULICO", "Acabamentos", "UN", "17.90", 30),
]  # fmt: skip

# Produto descontinuado: existe no cadastro, mas está inativo e fora das vendas.
PRODUTO_INATIVO = ("LAMP-FLUOR-20W", "Lâmpada Fluorescente Tubular 20W (descontinuada)", "ELETRICO", "Iluminação", "UN", "7.50", 0)

# Produtos que terminam o seed abaixo do mínimo (alimentam o relatório de reposição).
SKUS_ESTOQUE_BAIXO = ["DJ-MONO-20A", "DJ-MONO-32A", "DJ-TRI-63A", "CAB-FLEX-2.5-VM", "TUBO-PVC-25", "REG-ESF-25", "TORN-LAV-BAIXA"]

# (tipo, documento-base, nome, cidade, uf, contato). Os dígitos verificadores são calculados.
CLIENTES = [
    ("PJ", "112223330001", "Construtora Alvorada Ltda", "Campinas", "SP", "compras@alvorada.example"),
    ("PJ", "224445550001", "Elétrica Brasil Instalações Ltda", "São Paulo", "SP", "(11) 3456-7890"),
    ("PJ", "335556660001", "Hidrotec Engenharia e Saneamento", "Belo Horizonte", "MG", "obras@hidrotec.example"),
    ("PJ", "446667770001", "Condomínio Residencial Parque Verde", "Curitiba", "PR", "sindico@parqueverde.example"),
    ("PJ", "557778880001", "Mega Obras Construções S.A.", "Rio de Janeiro", "RJ", "(21) 2345-6789"),
    ("PJ", "668889990001", "Casa & Cia Materiais de Construção", "Florianópolis", "SC", "contato@casaecia.example"),
    ("PJ", "779990000001", "Instaladora Faísca ME", "Uberlândia", "MG", "(34) 99876-5432"),
    ("PJ", "881001110001", "Grupo Saneare Saneamento", "Ribeirão Preto", "SP", "licitacao@saneare.example"),
    ("PF", "123456789", "João Batista Ferreira", "Santos", "SP", "(13) 98765-4321"),
    ("PF", "987654321", "Maria Aparecida Lopes", "Niterói", "RJ", "maria.lopes@example.com"),
]  # fmt: skip


def _cpf(base9: str) -> str:
    digitos = base9
    for n in (9, 10):
        soma = sum(int(d) * (n + 1 - i) for i, d in enumerate(digitos[:n]))
        digitos += str((soma * 10 % 11) % 10)
    return digitos


def _cnpj(base12: str) -> str:
    pesos = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    digitos = base12
    for n in (12, 13):
        resto = sum(int(d) * p for d, p in zip(digitos[:n], pesos[13 - n :])) % 11
        digitos += str(0 if resto < 2 else 11 - resto)
    return digitos


def _momento(dia: date, rng: random.Random) -> datetime:
    return datetime.combine(dia, time(rng.randint(8, 17), rng.randint(0, 59)), tzinfo=timezone.utc)


def _quantidade(produto: Produto, rng: random.Random) -> int:
    if produto.unidade == "RL":
        return rng.randint(1, 4)
    if produto.unidade == "M":
        return rng.randint(20, 80)
    return rng.randint(2, max(3, min(30, produto.estoque_minimo // 2)))


def _status_por_posicao(total: int) -> list[str]:
    """Pedidos ordenados do mais antigo ao mais recente: o status acompanha a idade."""
    status = ["ENTREGUE"] * total
    for i in (3, 8):  # faturados há muito tempo e nunca pagos: viram contas vencidas
        status[i] = "FATURADO_SEM_PAGAMENTO"
    status[10] = "CANCELADO_CONFIRMADO"  # confirmado (baixou estoque) e depois cancelado (estorno)
    status[17] = "CANCELADO_ABERTO"
    for i in range(18, 24):
        status[i] = "FATURADO"
    for i in range(24, 28):
        status[i] = "CONFIRMADO"
    for i in range(28, total):
        status[i] = "ABERTO"
    return status


def popular(db: Session, hoje: date | None = None, semente: int = 42, total_pedidos: int = 30) -> dict[str, int]:
    if db.scalar(select(func.count()).select_from(Produto)):
        raise RuntimeError("O banco já tem dados. Use `python -m app.seed --limpar` para recomeçar do zero.")
    hoje = hoje or date.today()
    rng = random.Random(semente)

    # --- produtos e clientes ---
    for sku, nome, categoria, subcategoria, unidade, preco, minimo in [*PRODUTOS, PRODUTO_INATIVO]:
        db.add(
            Produto(sku=sku, nome=nome, categoria=categoria, subcategoria=subcategoria, unidade=unidade,
                    preco_venda=preco, estoque_minimo=minimo, ativo=(sku != PRODUTO_INATIVO[0]))
        )  # fmt: skip
    db.commit()
    produtos = list(db.scalars(select(Produto).where(Produto.ativo).order_by(Produto.id)))

    clientes = []
    for tipo, base, nome, cidade, uf, contato in CLIENTES:
        documento = _cnpj(base) if tipo == "PJ" else _cpf(base)
        clientes.append(
            clientes_service.criar(db, ClienteCriar(tipo=tipo, documento=documento, nome=nome, cidade=cidade, uf=uf, contato=contato))
        )  # fmt: skip

    # --- estoque inicial: uma ENTRADA por produto, recuada para ~6 meses atrás ---
    for p in produtos:
        estoque.registrar(db, p.id, TipoMovimentacao.ENTRADA, p.estoque_minimo * 10, "Estoque inicial - inventário de abertura")
    db.execute(update(MovimentacaoEstoque).values(data_hora=_momento(hoje - timedelta(days=185), rng)))
    db.commit()

    # --- pedidos espalhados pelos últimos meses ---
    dias_atras = sorted((max(1, 172 - round(i * 5.86) + rng.randint(-2, 2)) for i in range(total_pedidos)), reverse=True)
    status_finais = _status_por_posicao(total_pedidos)
    pesos_clientes = [8, 6, 5, 4, 3, 3, 2, 2, 2, 1]

    for posicao, (dias, status_final) in enumerate(zip(dias_atras, status_finais)):
        dia = hoje - timedelta(days=dias)
        cliente = rng.choices(clientes, weights=pesos_clientes)[0]
        itens = [ItemCriar(produto_id=p.id, quantidade=_quantidade(p, rng)) for p in rng.sample(produtos, rng.choice([1, 2, 2, 3, 3, 4]))]
        pedido = pedidos_service.criar(db, PedidoCriar(cliente_id=cliente.id, itens=itens))

        if status_final == "CANCELADO_ABERTO":
            pedidos_service.cancelar(db, pedido.id)
        elif status_final != "ABERTO":
            pedidos_service.confirmar(db, pedido.id)
            if status_final == "CANCELADO_CONFIRMADO":
                pedidos_service.cancelar(db, pedido.id)
            elif status_final != "CONFIRMADO":
                pedidos_service.faturar(db, pedido.id, dias_vencimento=rng.choice([15, 28, 30]))
                if status_final in ("ENTREGUE",):
                    pedidos_service.entregar(db, pedido.id)

        # Recua as datas (a API sempre usa "agora"): pedido, movimentações e conta a receber.
        momento = _momento(dia, rng)
        db.execute(update(Pedido).where(Pedido.id == pedido.id).values(data_pedido=momento))
        db.execute(update(MovimentacaoEstoque).where(MovimentacaoEstoque.pedido_id == pedido.id).values(data_hora=momento))
        conta = db.scalar(select(ContaReceber).where(ContaReceber.pedido_id == pedido.id))
        if conta is not None:
            emissao = min(dia + timedelta(days=rng.randint(0, 2)), hoje)
            prazo = (conta.data_vencimento - conta.data_emissao).days
            conta.data_emissao, conta.data_vencimento = emissao, emissao + timedelta(days=prazo)
            db.commit()
            paga = status_final == "ENTREGUE" and rng.random() < 0.7 or status_final == "FATURADO" and posicao % 2 == 0
            data_pagamento = emissao + timedelta(days=rng.randint(3, 40))
            if paga and data_pagamento <= hoje:  # pelo service: aplica as mesmas regras da API
                contas_service.registrar_pagamento(db, conta.id, data_pagamento)
        db.commit()

    # --- contagem física: alguns produtos terminam abaixo do mínimo ---
    por_sku = {p.sku: p for p in produtos}
    for sku in SKUS_ESTOQUE_BAIXO:
        p = db.get(Produto, por_sku[sku].id)
        alvo = rng.choice([0, p.estoque_minimo // 3, p.estoque_minimo // 2])
        estoque.registrar(db, p.id, TipoMovimentacao.AJUSTE, alvo - p.estoque_atual, "Ajuste de inventário (contagem física)")

    return {
        "produtos": db.scalar(select(func.count()).select_from(Produto)),
        "clientes": db.scalar(select(func.count()).select_from(Cliente)),
        "pedidos": db.scalar(select(func.count()).select_from(Pedido)),
        "contas_receber": db.scalar(select(func.count()).select_from(ContaReceber)),
        "movimentacoes": db.scalar(select(func.count()).select_from(MovimentacaoEstoque)),
    }


def limpar(db: Session) -> None:
    tabelas = ", ".join(t.name for t in Base.metadata.sorted_tables)
    db.execute(text(f"TRUNCATE {tabelas} RESTART IDENTITY CASCADE"))
    db.commit()
    db.expunge_all()  # os ids recomeçam em 1: objetos antigos da sessão ficariam "fantasmas" no cache dela


def main() -> None:
    ap = argparse.ArgumentParser(description="Popula o banco com dados de demonstração da EletroHidro.")
    ap.add_argument("--limpar", action="store_true", help="apaga TODOS os dados antes de popular")
    args = ap.parse_args()
    with SessionLocal() as db:
        if args.limpar:
            limpar(db)
        try:
            resumo = popular(db)
        except RuntimeError as erro:
            raise SystemExit(str(erro)) from erro
    print("Seed concluído:", ", ".join(f"{valor} {nome}" for nome, valor in resumo.items()))


if __name__ == "__main__":
    main()
