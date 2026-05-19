from __future__ import annotations

import importlib

import pandas as pd


def test_ai_disabled_without_key(monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    module = importlib.import_module('bling_app_zero.core.ai_mapping_assistant')

    assert module.ai_mapping_enabled() is False

    result = module.apply_ai_mapping_assist(
        pd.DataFrame({'Produto': ['Mouse Gamer'], 'Preco': ['99,90']}),
        ['Descrição', 'Preço unitário'],
        {},
    )

    assert result.enabled is False
    assert result.applied == 0
    assert 'OPENAI_API_KEY' in result.reason


def test_ai_enabled_with_owner_env_key(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'sk-test-owner-key')
    module = importlib.import_module('bling_app_zero.core.ai_mapping_assistant')

    assert module.ai_mapping_enabled() is True


def test_ai_does_not_call_when_no_uncertain_targets(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'sk-test-owner-key')
    module = importlib.import_module('bling_app_zero.core.ai_mapping_assistant')

    called = {'value': False}

    def fake_call_openai(payload):
        called['value'] = True
        return {'Descrição': 'Produto'}

    monkeypatch.setattr(module, '_call_openai', fake_call_openai)
    df = pd.DataFrame({'Produto': ['Mouse Gamer']})
    result = module.apply_ai_mapping_assist(df, ['Produto'], {'Produto': 'Produto'}, only_uncertain=True)

    assert result.enabled is True
    assert result.applied == 0
    assert called['value'] is False


def test_ai_accepts_valid_suggestion(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'sk-test-owner-key')
    module = importlib.import_module('bling_app_zero.core.ai_mapping_assistant')

    monkeypatch.setattr(module, '_call_openai', lambda payload: {'Descrição': 'Produto'})
    df = pd.DataFrame({'Produto': ['Mouse Gamer RGB'], 'Preco': ['99,90']})
    result = module.apply_ai_mapping_assist(df, ['Descrição'], {}, only_uncertain=True)

    assert result.enabled is True
    assert result.applied == 1
    assert result.suggestions == {'Descrição': 'Produto'}


def test_ai_rejects_invented_source_column(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'sk-test-owner-key')
    module = importlib.import_module('bling_app_zero.core.ai_mapping_assistant')

    monkeypatch.setattr(module, '_call_openai', lambda payload: {'Descrição': 'Coluna Inventada'})
    df = pd.DataFrame({'Produto': ['Mouse Gamer RGB']})
    result = module.apply_ai_mapping_assist(df, ['Descrição'], {}, only_uncertain=True)

    assert result.enabled is True
    assert result.applied == 0
    assert result.suggestions == {}


def test_ai_session_limit_blocks_after_limit(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'sk-test-owner-key')
    module = importlib.import_module('bling_app_zero.core.ai_mapping_assistant')

    monkeypatch.setattr(module, 'ai_mapping_remaining_session_calls', lambda: 0)
    df = pd.DataFrame({'Produto': ['Mouse Gamer RGB']})
    result = module.apply_ai_mapping_assist(df, ['Descrição'], {}, only_uncertain=True)

    assert result.enabled is False
    assert result.applied == 0
    assert 'limite' in result.reason.lower()
