"""Tipos numéricos das entradas da API, validados na fronteira (antes de chegar ao banco).

- strict=True: em JSON só aceita número inteiro de verdade. Sem isso o Pydantic converte em silêncio
  `true` em 1 e `"5"` em 5 (um cliente com bug registraria movimentações sem perceber).
- Limites: as colunas são INTEGER no PostgreSQL. Sem um teto, um número gigante passaria pela
  validação e estouraria no banco (erro 500). Os limites também aparecem no Swagger.
"""

from typing import Annotated

from pydantic import Field

MAIOR_INTEGER = 2_147_483_647  # maior valor de uma coluna INTEGER do PostgreSQL
LIMITE_QUANTIDADE = 1_000_000  # teto de negócio por item/movimentação

Id = Annotated[int, Field(strict=True, ge=1, le=MAIOR_INTEGER)]
Quantidade = Annotated[int, Field(strict=True, gt=0, le=LIMITE_QUANTIDADE)]
QuantidadeComSinal = Annotated[int, Field(strict=True, ge=-LIMITE_QUANTIDADE, le=LIMITE_QUANTIDADE)]
EstoqueMinimo = Annotated[int, Field(strict=True, ge=0, le=LIMITE_QUANTIDADE)]
