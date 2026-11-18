"""Modelos ORM (equivalente às @Entity do JPA).

Decisões:
- Enums viram VARCHAR + CHECK (não ENUM nativo do Postgres): adicionar um valor
  novo no futuro é só alterar a constraint, sem o ALTER TYPE chato do Postgres.
- Regras que o banco consegue garantir sozinho ficam no banco (CHECK), como
  "estoque nunca negativo": mesmo um bug na aplicação não corrompe os dados.
- Dinheiro é Numeric(12, 2) (Decimal em Python, igual BigDecimal) — nunca float.
- Quantidades são inteiras (venda por metro/unidade inteira). Se um dia for
  preciso vender 2,5 m, basta trocar para Numeric(12, 3).
"""

import enum
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class CategoriaProduto(enum.StrEnum):
    ELETRICO = "ELETRICO"
    HIDRAULICO = "HIDRAULICO"


class UnidadeProduto(enum.StrEnum):
    UN = "UN"
    M = "M"
    CX = "CX"
    RL = "RL"


class TipoMovimentacao(enum.StrEnum):
    ENTRADA = "ENTRADA"
    SAIDA = "SAIDA"
    AJUSTE = "AJUSTE"


class TipoCliente(enum.StrEnum):
    PF = "PF"
    PJ = "PJ"


class StatusPedido(enum.StrEnum):
    ABERTO = "ABERTO"
    CONFIRMADO = "CONFIRMADO"
    FATURADO = "FATURADO"
    ENTREGUE = "ENTREGUE"
    CANCELADO = "CANCELADO"


class StatusConta(enum.StrEnum):
    PENDENTE = "PENDENTE"
    PAGO = "PAGO"
    VENCIDO = "VENCIDO"


def _enum(classe: type[enum.StrEnum], nome: str) -> Enum:
    """Coluna enum como VARCHAR com CHECK nomeado (ver docstring do módulo)."""
    return Enum(classe, name=nome, native_enum=False, create_constraint=True, length=20)


class Produto(Base):
    __tablename__ = "produtos"
    __table_args__ = (
        CheckConstraint("preco_venda >= 0", name="preco_nao_negativo"),
        CheckConstraint("estoque_atual >= 0", name="estoque_nao_negativo"),
        CheckConstraint("estoque_minimo >= 0", name="estoque_minimo_nao_negativo"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    sku: Mapped[str] = mapped_column(String(30), unique=True)
    nome: Mapped[str] = mapped_column(String(150))
    descricao: Mapped[str | None] = mapped_column(String(500))
    categoria: Mapped[CategoriaProduto] = mapped_column(_enum(CategoriaProduto, "categoria_produto"), index=True)
    subcategoria: Mapped[str] = mapped_column(String(60))
    unidade: Mapped[UnidadeProduto] = mapped_column(_enum(UnidadeProduto, "unidade_produto"))
    preco_venda: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    estoque_atual: Mapped[int] = mapped_column(default=0)
    estoque_minimo: Mapped[int] = mapped_column(default=0)
    ativo: Mapped[bool] = mapped_column(default=True, server_default="true")


class Cliente(Base):
    __tablename__ = "clientes"
    __table_args__ = (
        # documento guarda só dígitos: CPF = 11, CNPJ = 14. (O dígito verificador é validado na API.)
        CheckConstraint(
            "(tipo = 'PF' AND length(documento) = 11) OR (tipo = 'PJ' AND length(documento) = 14)",
            name="documento_compativel_com_tipo",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tipo: Mapped[TipoCliente] = mapped_column(_enum(TipoCliente, "tipo_cliente"))
    documento: Mapped[str] = mapped_column(String(14), unique=True)
    nome: Mapped[str] = mapped_column(String(150))  # nome (PF) ou razão social (PJ)
    cidade: Mapped[str] = mapped_column(String(80))
    uf: Mapped[str] = mapped_column(String(2), index=True)
    contato: Mapped[str | None] = mapped_column(String(120))


class Pedido(Base):
    __tablename__ = "pedidos"

    id: Mapped[int] = mapped_column(primary_key=True)
    cliente_id: Mapped[int] = mapped_column(ForeignKey("clientes.id"), index=True)
    status: Mapped[StatusPedido] = mapped_column(
        _enum(StatusPedido, "status_pedido"), default=StatusPedido.ABERTO, index=True
    )
    data_pedido: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    cliente: Mapped[Cliente] = relationship()
    # cascade = JPA CascadeType.ALL + orphanRemoval: itens nascem/morrem com o pedido.
    itens: Mapped[list["ItemPedido"]] = relationship(
        back_populates="pedido", cascade="all, delete-orphan", order_by="ItemPedido.id"
    )

    @property
    def total(self) -> Decimal:
        """Calculado, não armazenado: o valor do pedido nunca fica dessincronizado dos itens."""
        return sum((item.subtotal for item in self.itens), Decimal("0"))


class ItemPedido(Base):
    __tablename__ = "itens_pedido"
    __table_args__ = (
        UniqueConstraint("pedido_id", "produto_id", name="uq_itens_pedido_pedido_produto"),
        CheckConstraint("quantidade > 0", name="quantidade_positiva"),
        CheckConstraint("preco_unitario >= 0", name="preco_nao_negativo"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    pedido_id: Mapped[int] = mapped_column(ForeignKey("pedidos.id", ondelete="CASCADE"), index=True)
    produto_id: Mapped[int] = mapped_column(ForeignKey("produtos.id"), index=True)
    quantidade: Mapped[int]
    # Preço congelado no momento da venda: mudar o preço do produto depois não altera pedidos antigos.
    preco_unitario: Mapped[Decimal] = mapped_column(Numeric(12, 2))

    pedido: Mapped[Pedido] = relationship(back_populates="itens")
    produto: Mapped[Produto] = relationship()

    @property
    def subtotal(self) -> Decimal:
        return self.preco_unitario * self.quantidade


class MovimentacaoEstoque(Base):
    __tablename__ = "movimentacoes_estoque"
    __table_args__ = (
        # ENTRADA/SAIDA: quantidade > 0 (o tipo já diz o sentido).
        # AJUSTE: quantidade com sinal (+ sobra encontrada, - perda), nunca zero.
        CheckConstraint(
            "quantidade <> 0 AND (tipo = 'AJUSTE' OR quantidade > 0)",
            name="quantidade_valida_para_tipo",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    produto_id: Mapped[int] = mapped_column(ForeignKey("produtos.id"), index=True)
    tipo: Mapped[TipoMovimentacao] = mapped_column(_enum(TipoMovimentacao, "tipo_movimentacao"))
    quantidade: Mapped[int]
    motivo: Mapped[str] = mapped_column(String(200))
    data_hora: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    # Preenchido quando a movimentação nasce de um pedido (saída na confirmação, estorno no cancelamento).
    pedido_id: Mapped[int | None] = mapped_column(ForeignKey("pedidos.id"), index=True)


VALOR_MAXIMO_CONTA = Decimal("9999999999.99")  # maior valor que cabe em NUMERIC(12, 2)


class ContaReceber(Base):
    __tablename__ = "contas_receber"
    __table_args__ = (CheckConstraint("valor > 0", name="valor_positivo"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    # unique: um pedido gera no máximo uma conta (impede faturar duas vezes).
    pedido_id: Mapped[int] = mapped_column(ForeignKey("pedidos.id"), unique=True)
    valor: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    data_emissao: Mapped[date] = mapped_column(Date, server_default=func.current_date())
    data_vencimento: Mapped[date] = mapped_column(Date)
    data_pagamento: Mapped[date | None] = mapped_column(Date)
    status: Mapped[StatusConta] = mapped_column(_enum(StatusConta, "status_conta"), default=StatusConta.PENDENTE)

    pedido: Mapped[Pedido] = relationship()

    @property
    def situacao(self) -> StatusConta:
        """Status que a API mostra. VENCIDO não é gravado: é PENDENTE com vencimento já passado.

        Gravar VENCIDO exigiria um job diário e, até ele rodar, o dado ficaria errado.
        Derivar na leitura é sempre correto (os relatórios SQL usam a mesma regra).
        """
        if self.status == StatusConta.PENDENTE and self.data_vencimento < date.today():
            return StatusConta.VENCIDO
        return self.status
