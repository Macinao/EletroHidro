import pytest

from app.validadores import cnpj_valido, cpf_valido


@pytest.mark.parametrize("cpf", ["52998224725", "11144477735"])
def test_cpf_valido(cpf):
    assert cpf_valido(cpf)


@pytest.mark.parametrize("cpf", ["52998224724", "11111111111", "123", "5299822472a"])
def test_cpf_invalido(cpf):
    assert not cpf_valido(cpf)


@pytest.mark.parametrize("cnpj", ["11222333000181", "11444777000161"])
def test_cnpj_valido(cnpj):
    assert cnpj_valido(cnpj)


@pytest.mark.parametrize("cnpj", ["11222333000180", "00000000000000", "123"])
def test_cnpj_invalido(cnpj):
    assert not cnpj_valido(cnpj)
