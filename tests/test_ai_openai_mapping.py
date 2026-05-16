from __future__ import annotations

from pathlib import Path

import pandas as pd


def test_openai_mapping_suggester_imports_and_has_validation_rules() -> None:
    import bling_app_zero.ai.ai_openai_mapping_suggester as module

    source = Path('bling_app_zero/ai/ai_openai_mapping_suggester.py').read_text(encoding='utf-8')
    client = Path('bling_app_zero/ai/ai_client.py').read_text(encoding='utf-8')
    panel = Path('bling_app_zero/ui/ai_mapping_apply_panel.py').read_text(encoding='utf-8')

    assert module.MIN_OPENAI_CONFIDENCE == 0.55
    assert 'Não invente coluna de origem' in source
    assert '_sanitize_suggestions' in source
    assert 'source not in source_set' in source
    assert 'target not in target_set' in source
    assert 'local_fallback' in source
    assert "'text': {'format': {'type': 'json_object'}}" in client
    assert 'Responda exclusivamente em JSON válido' in client
    assert 'suggest_mapping_with_openai' in panel
    assert 'OpenAI validada' in panel
    assert 'fallback local validado' in panel


def test_openai_suggestion_sanitizer_rejects_unknown_columns() -> None:
    from bling_app_zero.ai.ai_openai_mapping_suggester import _sanitize_suggestions

    raw = [
        {'target_column': 'Descricao', 'source_column': 'Produto', 'confidence': 0.95, 'reason': 'ok'},
        {'target_column': 'Preco', 'source_column': 'Coluna Inexistente', 'confidence': 0.95, 'reason': 'bad source'},
        {'target_column': 'Campo Inexistente', 'source_column': 'Produto', 'confidence': 0.95, 'reason': 'bad target'},
        {'target_column': 'Estoque', 'source_column': 'Saldo', 'confidence': 0.2, 'reason': 'low confidence'},
    ]
    clean = _sanitize_suggestions(raw, ['Produto', 'Saldo'], ['Descricao', 'Preco', 'Estoque'])

    assert clean[0]['target_column'] == 'Descricao'
    assert clean[0]['source_column'] == 'Produto'
    assert clean[1]['target_column'] == 'Preco'
    assert clean[1]['source_column'] == ''
    assert clean[2]['target_column'] == 'Estoque'
    assert clean[2]['source_column'] == ''
    assert all(item['target_column'] != 'Campo Inexistente' for item in clean)


def test_mapping_suggester_falls_back_when_ai_disabled(monkeypatch) -> None:
    import streamlit as st
    from bling_app_zero.ai.ai_openai_mapping_suggester import suggest_mapping_with_openai

    monkeypatch.setattr(st, 'session_state', {}, raising=False)
    source = pd.DataFrame([{'Produto': 'Cabo USB', 'Valor Venda': '19,90'}])
    target = pd.DataFrame(columns=['Descricao', 'Preco unitario'])

    result = suggest_mapping_with_openai(source, target, operation='cadastro')

    assert result.ok is True
    assert result.task == 'mapping_suggester'
    assert 'suggestions' in result.data
    assert any(item['target_column'] == 'Preco unitario' for item in result.data['suggestions'])
