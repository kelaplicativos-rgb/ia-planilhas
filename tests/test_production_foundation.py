from __future__ import annotations

import importlib
from pathlib import Path


def test_production_modules_import() -> None:
    modules = [
        'bling_app_zero.production.production_config',
        'bling_app_zero.production.user_context',
        'bling_app_zero.production.persistent_credits',
        'bling_app_zero.production.payments',
        'bling_app_zero.ui.production_sidebar',
    ]
    for module_name in modules:
        importlib.import_module(module_name)


def test_production_schema_contains_required_tables() -> None:
    schema = Path('bling_app_zero/production/database_schema.sql').read_text(encoding='utf-8')
    for table in [
        'app_users',
        'credit_wallets',
        'credit_transactions',
        'mapping_jobs',
        'payments',
        'uploaded_files',
        'audit_logs',
    ]:
        assert f'create table if not exists {table}' in schema
    assert 'unique (user_id, mapping_signature)' in schema


def test_checkout_contract_does_not_credit_without_webhook(monkeypatch) -> None:
    st = importlib.import_module('streamlit')
    user_context = importlib.import_module('bling_app_zero.production.user_context')
    payments = importlib.import_module('bling_app_zero.production.payments')
    monkeypatch.setattr(st, 'session_state', {}, raising=False)

    result_without_user = payments.create_checkout('Teste rápido')
    assert result_without_user.ok is False

    user_context.set_demo_user()
    result = payments.create_checkout('Teste rápido')
    assert result.ok is False
    assert 'webhook' in result.message.lower()
    assert result.payload['credits'] == 10


def test_production_sidebar_is_plugged() -> None:
    sidebar = Path('bling_app_zero/ui/sidebar_tools.py').read_text(encoding='utf-8')
    production_sidebar = Path('bling_app_zero/ui/production_sidebar.py').read_text(encoding='utf-8')

    assert 'Produção MapeiaAI' in sidebar
    assert 'render_production_sidebar' in sidebar
    assert 'Modo produção' in production_sidebar
    assert 'Entrar como demo' in production_sidebar
