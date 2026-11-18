"""Relatórios em SQL escrito à mão (text()), sem ORM.

Conceitos que valem para todas as consultas:

* VENDA EFETIVADA = pedido FATURADO ou ENTREGUE. Pedidos ABERTOS, CONFIRMADOS (ainda não
  faturados) e CANCELADOS não entram no faturamento.
* O PERÍODO refere-se à data de faturamento (contas_receber.data_emissao), não à data de criação do pedido.
* Parâmetros SEMPRE vão como bind (:nome), nunca concatenados no texto: é isso que
  protege contra SQL injection (equivale ao PreparedStatement do JDBC).
* Filtro opcional: `CAST(:x AS tipo) IS NULL OR coluna = :x`. Param nulo = sem filtro.
  O CAST é necessário porque o PostgreSQL não consegue deduzir o tipo de um parâmetro
  nulo usado apenas em `IS NULL`.
"""

from datetime import date
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


def _executar(db: Session, sql: str, **parametros: Any) -> list[dict[str, Any]]:
    return [dict(linha) for linha in db.execute(text(sql), parametros).mappings()]


def produtos_mais_vendidos(
    db: Session, data_inicio: date | None, data_fim: date | None, categoria: str | None, limite: int
) -> list[dict[str, Any]]:
    return _executar(
        db,
        """
        SELECT p.id                                AS produto_id,
               p.sku,
               p.nome,
               p.categoria,
               SUM(i.quantidade)                   AS quantidade_vendida,
               SUM(i.quantidade * i.preco_unitario) AS faturamento
          FROM itens_pedido i
          JOIN pedidos ped        ON ped.id = i.pedido_id
          JOIN contas_receber c   ON c.pedido_id = ped.id
          JOIN produtos p         ON p.id = i.produto_id
         WHERE ped.status IN ('FATURADO', 'ENTREGUE')
           AND (CAST(:data_inicio AS date) IS NULL OR c.data_emissao >= :data_inicio)
           AND (CAST(:data_fim    AS date) IS NULL OR c.data_emissao <= :data_fim)
           AND (CAST(:categoria AS varchar) IS NULL OR p.categoria = :categoria)
         GROUP BY p.id, p.sku, p.nome, p.categoria
         ORDER BY quantidade_vendida DESC, faturamento DESC, p.id
         LIMIT :limite
        """,
        data_inicio=data_inicio,
        data_fim=data_fim,
        categoria=categoria,
        limite=limite,
    )


def faturamento_por_categoria_e_mes(db: Session, data_inicio: date | None, data_fim: date | None) -> list[dict[str, Any]]:
    return _executar(
        db,
        """
        SELECT to_char(c.data_emissao, 'YYYY-MM')   AS mes,
               p.categoria,
               SUM(i.quantidade * i.preco_unitario) AS faturamento,
               COUNT(DISTINCT ped.id)               AS qtd_pedidos
          FROM itens_pedido i
          JOIN pedidos ped        ON ped.id = i.pedido_id
          JOIN contas_receber c   ON c.pedido_id = ped.id
          JOIN produtos p         ON p.id = i.produto_id
         WHERE ped.status IN ('FATURADO', 'ENTREGUE')
           AND (CAST(:data_inicio AS date) IS NULL OR c.data_emissao >= :data_inicio)
           AND (CAST(:data_fim    AS date) IS NULL OR c.data_emissao <= :data_fim)
         GROUP BY mes, p.categoria
         ORDER BY mes, p.categoria
        """,
        data_inicio=data_inicio,
        data_fim=data_fim,
    )


def ranking_clientes(
    db: Session, data_inicio: date | None, data_fim: date | None, uf: str | None, limite: int
) -> list[dict[str, Any]]:
    # RANK() é uma window function: numera as linhas já agrupadas (empates dividem a posição).
    # Ela é calculada ANTES do LIMIT, então o ranking não depende do tamanho da página.
    return _executar(
        db,
        """
        SELECT RANK() OVER (ORDER BY SUM(c.valor) DESC) AS posicao,
               cl.id                                    AS cliente_id,
               cl.nome,
               cl.cidade,
               cl.uf,
               COUNT(*)                                 AS qtd_pedidos,
               SUM(c.valor)                             AS faturamento
          FROM pedidos ped
          JOIN clientes cl        ON cl.id = ped.cliente_id
          JOIN contas_receber c   ON c.pedido_id = ped.id
         WHERE ped.status IN ('FATURADO', 'ENTREGUE')
           AND (CAST(:data_inicio AS date) IS NULL OR c.data_emissao >= :data_inicio)
           AND (CAST(:data_fim    AS date) IS NULL OR c.data_emissao <= :data_fim)
           AND (CAST(:uf AS varchar) IS NULL OR cl.uf = :uf)
         GROUP BY cl.id, cl.nome, cl.cidade, cl.uf
         ORDER BY faturamento DESC, cl.id
         LIMIT :limite
        """,
        data_inicio=data_inicio,
        data_fim=data_fim,
        uf=uf,
        limite=limite,
    )


def estoque_abaixo_do_minimo(
    db: Session, categoria: str | None, subcategoria: str | None, limite: int
) -> list[dict[str, Any]]:
    return _executar(
        db,
        """
        SELECT id                           AS produto_id,
               sku,
               nome,
               categoria,
               subcategoria,
               estoque_atual,
               estoque_minimo,
               estoque_minimo - estoque_atual AS falta
          FROM produtos
         WHERE ativo
           AND estoque_atual < estoque_minimo
           AND (CAST(:categoria    AS varchar) IS NULL OR categoria = :categoria)
           AND (CAST(:subcategoria AS varchar) IS NULL OR subcategoria ILIKE :subcategoria)
         ORDER BY falta DESC, nome
         LIMIT :limite
        """,
        categoria=categoria,
        subcategoria=subcategoria,
        limite=limite,
    )


def contas_vencidas_por_cliente(db: Session, data_referencia: date, limite: int) -> list[dict[str, Any]]:
    return _executar(
        db,
        """
        SELECT cl.id                                   AS cliente_id,
               cl.nome,
               cl.uf,
               COUNT(*)                                AS qtd_contas,
               SUM(c.valor)                            AS total_vencido,
               MIN(c.data_vencimento)                  AS vencimento_mais_antigo,
               CAST(:data_referencia AS date) - MIN(c.data_vencimento) AS dias_atraso_maximo
          FROM contas_receber c
          JOIN pedidos ped   ON ped.id = c.pedido_id
          JOIN clientes cl   ON cl.id = ped.cliente_id
         WHERE c.status = 'PENDENTE'
           AND c.data_vencimento < :data_referencia
         GROUP BY cl.id, cl.nome, cl.uf
         ORDER BY total_vencido DESC, cl.id
         LIMIT :limite
        """,
        data_referencia=data_referencia,
        limite=limite,
    )
