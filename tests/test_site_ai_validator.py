from __future__ import annotations

import pandas as pd

from bling_app_zero.agents.site_ai_validator import evaluate_site_dataframe


def test_validator_usa_nome_do_produto_quando_descricao_esta_vazia() -> None:
    df = pd.DataFrame([
        {
            'URL': 'https://www.atacadum.com.br/smartwatch-d20-atualizacao-2021',
            'ID Produto': '579028',
            'Nome do Produto': 'Smartwatch D20 Atualização 2021',
            'Preço de Compra*': '99,90',
            'descricao': '',
        },
        {
            'URL': 'https://www.atacadum.com.br/relogio-smartwatch/modelo-x',
            'ID Produto': '1954667',
            'Nome do Produto': 'Relógio Smartwatch Modelo X',
            'Preço de Compra*': '149,90',
            'descricao': '',
        },
    ])

    quality = evaluate_site_dataframe(df, operation='universal')

    assert quality.rows == 2
    assert quality.missing_description == 0
    assert quality.good_rows == 2
    assert not any('sem descrição' in warning for warning in quality.warnings)


def test_validator_nao_trata_id_produto_como_descricao() -> None:
    df = pd.DataFrame([
        {
            'URL': 'https://www.atacadum.com.br/produto-sem-nome',
            'ID Produto': '579028',
            'Preço de Compra*': '99,90',
        }
    ])

    quality = evaluate_site_dataframe(df, operation='universal')

    assert quality.missing_description == 1
    assert quality.good_rows == 0
