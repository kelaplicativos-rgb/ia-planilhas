import pandas as pd

from bling_app_zero.core.category_intelligence import apply_category_suggestions, canonicalize_category
from bling_app_zero.core.provisional_category import apply_category_guard_to_payload, is_safe_category_name


def test_recover_real_category_from_ai_column(monkeypatch):
    monkeypatch.setattr(
        'bling_app_zero.core.provisional_category.get_user_rules',
        lambda: {'allow_provisional_category': True, 'provisional_category_name': 'Produtos não classificados'},
    )

    result = apply_category_guard_to_payload(
        {'nome': 'Cartão de Memória 32GB'},
        row={'categoria_sugerida_ia': 'Cartões de memória'},
        meta={},
        category_id_resolver=lambda name: '123' if name == 'Cartões de memória' else '',
    )

    assert result.applied is True
    assert result.provisional is False
    assert result.category_name == 'Cartões de memória'
    assert result.payload['categoria'] == {'id': '123'}


def test_infer_real_category_before_provisional(monkeypatch):
    monkeypatch.setattr(
        'bling_app_zero.core.provisional_category.get_user_rules',
        lambda: {'allow_provisional_category': True, 'provisional_category_name': 'Produtos não classificados'},
    )

    result = apply_category_guard_to_payload(
        {'nome': 'Fone de ouvido Bluetooth sem fio'},
        row={},
        meta={},
        category_id_resolver=lambda name: '321' if name == 'Fones de ouvido' else '',
    )

    assert result.applied is True
    assert result.provisional is False
    assert result.source == 'category_intelligence'
    assert result.category_name == 'Fones de ouvido'
    assert result.payload['categoria'] == {'id': '321'}


def test_replace_existing_provisional_category_with_real_category(monkeypatch):
    monkeypatch.setattr(
        'bling_app_zero.core.provisional_category.get_user_rules',
        lambda: {'allow_provisional_category': True, 'provisional_category_name': 'Produtos não classificados'},
    )

    result = apply_category_guard_to_payload(
        {'nome': 'Fone de ouvido Bluetooth sem fio', 'categoria': {'descricao': 'Produtos não classificados'}},
        row={'Categoria': 'Produtos não classificados'},
        meta={'category': 'Produtos não classificados'},
        category_id_resolver=lambda name: '321' if name == 'Fones de ouvido' else '',
    )

    assert result.applied is True
    assert result.provisional is False
    assert result.source == 'category_intelligence'
    assert result.category_name == 'Fones de ouvido'
    assert result.payload['categoria'] == {'id': '321'}


def test_apply_default_provisional_when_missing(monkeypatch):
    monkeypatch.setattr(
        'bling_app_zero.core.provisional_category.get_user_rules',
        lambda: {},
    )

    result = apply_category_guard_to_payload(
        {'nome': 'Produto sem categoria'},
        row={},
        meta={},
        category_id_resolver=lambda name: '999' if name == 'Produtos não classificados' else '',
    )

    assert result.applied is True
    assert result.provisional is True
    assert result.category_name == 'Produtos não classificados'
    assert result.payload['categoria'] == {'id': '999'}


def test_keep_blockable_only_when_provisional_disabled(monkeypatch):
    monkeypatch.setattr(
        'bling_app_zero.core.provisional_category.get_user_rules',
        lambda: {'allow_provisional_category': False, 'provisional_category_name': 'Produtos não classificados'},
    )

    result = apply_category_guard_to_payload({'nome': 'Produto sem categoria'}, row={}, meta={})

    assert result.applied is False
    assert result.payload == {'nome': 'Produto sem categoria'}
    assert result.reason == 'missing_category_and_provisional_disabled'


def test_product_title_is_not_safe_category():
    title = 'Fone Headset Gamer Lehmox LEF-1051'
    canonical, changed, reason = canonicalize_category(title)

    assert canonical == ''
    assert changed is True
    assert 'nome de produto' in reason or 'catálogo seguro' in reason
    assert is_safe_category_name(title, product_name=title) is False


def test_payload_product_title_category_is_replaced_by_inferred_category(monkeypatch):
    monkeypatch.setattr(
        'bling_app_zero.core.provisional_category.get_user_rules',
        lambda: {'allow_provisional_category': True, 'provisional_category_name': 'Produtos não classificados'},
    )

    result = apply_category_guard_to_payload(
        {
            'nome': 'Fone Headset Gamer Lehmox LEF-1051',
            'categoria': {'descricao': 'Fone Headset Gamer Lehmox LEF-1051'},
        },
        row={'Categoria do produto': 'Fone Headset Gamer Lehmox LEF-1051'},
        meta={'category': 'Fone Headset Gamer Lehmox LEF-1051'},
        category_id_resolver=lambda name: '321' if name == 'Fones de ouvido' else '',
    )

    assert result.applied is True
    assert result.provisional is False
    assert result.category_name == 'Fones de ouvido'
    assert result.payload['categoria'] == {'id': '321'}


def test_dataframe_category_suggestions_do_not_keep_product_title_as_category():
    df = pd.DataFrame(
        [
            {
                'Descrição': 'Tomada Tipo C PD20W Imenso IMS-234B',
                'Categoria do produto': 'Tomada Tipo C PD20W Imenso IMS-234B',
            }
        ]
    )

    result, applied = apply_category_suggestions(df, confidence_min=0.80, keep_helper_columns=True)

    assert applied == 1
    assert result.loc[0, 'Categoria do produto'] == 'Energia e tomadas'
    assert result.loc[0, 'categoria_sugerida_ia'] == 'Energia e tomadas'
