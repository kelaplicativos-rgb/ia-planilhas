from __future__ import annotations

import unittest

import pandas as pd

from bling_app_zero.core.validators import validate_final_df


class TestValidacoesFluxo(unittest.TestCase):
    def test_validacao_cadastro_aprova_nome_e_preco_preenchidos(self) -> None:
        df = pd.DataFrame({'Descrição': ['Produto Teste'], 'Preço de venda': ['10,90']})

        errors = validate_final_df(df, 'cadastro')

        self.assertEqual(errors, [])

    def test_validacao_cadastro_avisa_falta_nome_e_preco(self) -> None:
        df = pd.DataFrame({'Código': ['P001']})

        errors = validate_final_df(df, 'cadastro')

        self.assertTrue(any('nome ou descrição' in error for error in errors))
        self.assertTrue(any('preço ou valor' in error for error in errors))

    def test_validacao_estoque_aprova_codigo_e_saldo(self) -> None:
        df = pd.DataFrame({'Código': ['P001'], 'Balanço (OBRIGATÓRIO)': ['7']})

        errors = validate_final_df(df, 'estoque')

        self.assertEqual(errors, [])

    def test_validacao_estoque_avisa_falta_codigo_e_saldo(self) -> None:
        df = pd.DataFrame({'Descrição': ['Produto Teste']})

        errors = validate_final_df(df, 'estoque')

        self.assertTrue(any('código' in error.lower() for error in errors))
        self.assertTrue(any('saldo' in error.lower() or 'quantidade' in error.lower() for error in errors))

    def test_validacao_df_vazio(self) -> None:
        errors = validate_final_df(pd.DataFrame(), 'cadastro')

        self.assertTrue(errors)
        self.assertIn('vazio', errors[0].lower())


if __name__ == '__main__':
    unittest.main()
