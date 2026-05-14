from __future__ import annotations

import pandas as pd

from bling_app_zero.core.final_download_resources import (
    clean_invalid_gtin_resource,
    fallback_code_from_row,
    normalize_image_separator_resource,
    unique_product_codes_resource,
)


def test_final_resource_normalizes_images_with_pipe() -> None:
    df = pd.DataFrame(
        [
            {'URL Imagens Externas': 'https://a.com/1.jpg, https://a.com/2.jpg; https://a.com/1.jpg'},
        ]
    )

    result = normalize_image_separator_resource(df)

    assert result.df['URL Imagens Externas'].tolist() == ['https://a.com/1.jpg|https://a.com/2.jpg']


def test_final_resource_cleans_invalid_gtin() -> None:
    df = pd.DataFrame(
        [
            {'GTIN/EAN': '123'},
            {'GTIN/EAN': '7891234567895'},
        ]
    )

    result = clean_invalid_gtin_resource(df)

    assert result.df['GTIN/EAN'].tolist() == ['', '7891234567895']


def test_final_resource_uses_gtin_as_code_fallback() -> None:
    df = pd.DataFrame([{'GTIN/EAN': '7891234567895', 'Código': ''}])

    assert fallback_code_from_row(df, 0) == '7891234567895'


def test_final_resource_generates_unique_product_codes() -> None:
    df = pd.DataFrame(
        [
            {'Descrição': 'Produto Teste', 'Código': ''},
            {'Descrição': 'Produto Teste', 'Código': ''},
        ]
    )

    result = unique_product_codes_resource(df)

    assert result.df['Código'].tolist() == ['auto-produtoteste-1', 'auto-produtoteste-2']
