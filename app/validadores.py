"""Validação dos dígitos verificadores de CPF e CNPJ (recebem só dígitos)."""


def cpf_valido(cpf: str) -> bool:
    if len(cpf) != 11 or not cpf.isdigit() or cpf == cpf[0] * 11:
        return False
    for n in (9, 10):
        soma = sum(int(d) * (n + 1 - i) for i, d in enumerate(cpf[:n]))
        if (soma * 10 % 11) % 10 != int(cpf[n]):
            return False
    return True


def cnpj_valido(cnpj: str) -> bool:
    if len(cnpj) != 14 or not cnpj.isdigit() or cnpj == cnpj[0] * 14:
        return False
    pesos = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    for n in (12, 13):
        soma = sum(int(d) * p for d, p in zip(cnpj[:n], pesos[13 - n :], strict=True))
        resto = soma % 11
        if (0 if resto < 2 else 11 - resto) != int(cnpj[n]):
            return False
    return True
