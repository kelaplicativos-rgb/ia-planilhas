from __future__ import annotations

import pandas as pd

from bling_app_zero.core.bling_preflight_scan import (
    PENDING_IMAGE_LIMIT,
    build_bling_preflight_report,
    build_pending_rows_dataframe,
    filter_sendable_dataframe,
)
from bling_app_zero.core.final_download_resources import (
    clean_invalid_gtin_resource,
    fallback_code_from_row,
    limit_bling_images_resource,
    normalize_image_separator_resource,
    unique_product_codes_resource,
)
from bling_app_zero.core.final_output_rule_engine import apply_final_output_rules


def test_final_resource_normalizes_images_with_pipe() -> None:
    df = pd.DataFrame(
        [
            {'URL Imagens Externas': 'https://a.com/1.jpg, https://a.com/2.jpg; https://a.com/1.jpg'},
        ]
    )

    result = normalize_image_separator_resource(df)

    assert result.df['URL Imagens Externas'].tolist() == ['https://a.com/1.jpg|https://a.com/2.jpg']


def test_final_resource_limit_images_is_separate_from_separator() -> None:
    urls = ', '.join(f'https://a.com/{index}.jpg' for index in range(1, 9))
    df = pd.DataFrame([{'URL Imagens Externas': urls}])

    separated = normalize_image_separator_resource(df)
    limited = limit_bling_images_resource(separated.df)

    assert len(separated.df['URL Imagens Externas'].iloc[0].split('|')) == 8
    assert len(limited.df['URL Imagens Externas'].iloc[0].split('|')) == 6


def test_final_output_rules_apply_image_limit_before_download_or_api() -> None:
    urls = '|'.join(f'https://a.com/{index}.jpg' for index in range(1, 9))
    df = pd.DataFrame([{'Descrição': 'Produto Teste', 'Preço': '10', 'URL Imagens Externas': urls}])

    fixed_df, report = apply_final_output_rules(df, context='download')

    assert report.rows_over_image_limit_before == 1
    assert report.rows_over_image_limit_after == 0
    assert report.rows_limited == 1
    assert len(fixed_df['URL Imagens Externas'].iloc[0].split('|')) == 6


def test_api_preflight_separates_product_over_image_limit() -> None:
    urls = '|'.join(f'https://a.com/{index}.jpg' for index in range(1, 9))
    df = pd.DataFrame([{'Descrição': 'Produto Teste', 'Preço': '10', 'URL Imagens Externas': urls}])

    report = build_bling_preflight_report(df, 'cadastro', batch_size=10).to_dict()
    pending = build_pending_rows_dataframe(df, 'cadastro')
    sendable = filter_sendable_dataframe(df, 'cadastro')

    assert report['rows_over_image_limit'] == 1
    assert report['safe_to_send_rows'] == 0
    assert pending['tipo_pendencia'].tolist() == [PENDING_IMAGE_LIMIT]
    assert sendable.empty


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
