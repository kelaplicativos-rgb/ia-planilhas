from bling_app_zero.core.provisional_category import apply_category_guard_to_payload


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
