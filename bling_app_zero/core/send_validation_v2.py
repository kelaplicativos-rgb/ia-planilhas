from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd
import streamlit as st

from bling_app_zero.core.global_dataset_guard import FINAL_DOWNLOAD_SIGNATURE_KEY, GLOBAL_FINAL_DATASET_SIGNATURE_KEY, category_values_signature, dataframe_table_signature
from bling_app_zero.core.validators import price_validation_details, validate_price_update_values

RESPONSIBLE_FILE = 'bling_app_zero/core/send_validation_v2.py'
CATEGORY_DONE_KEY = 'category_conference_confirmed_v1'
CATEGORY_SKIP_KEY = 'category_conference_skipped_v1'
CATEGORY_VALUES_SIGNATURE_KEY = 'category_conference_values_signature_v1'


@dataclass(frozen=True)
class SendGuardResult:
    ok: bool
    status: str
    messages: tuple[str, ...]
    details: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {'ok': self.ok, 'status': self.status, 'messages': list(self.messages), 'details': dict(self.details)}


def _operation(value: object) -> str:
    text = str(value or '').strip().lower()
    if 'estoque' in text or 'saldo' in text or 'stock' in text:
        return 'estoque'
    if 'preco' in text or 'preço' in text or 'price' in text:
        return 'atualizacao_preco'
    return 'cadastro'


def _category_column(df: pd.DataFrame) -> str:
    names = {'categoria', 'category', 'nome da categoria', 'categoria do produto'}
    for col in df.columns:
        if str(col or '').strip().lower() in names:
            return str(col)
    return ''


def _has_column(df: pd.DataFrame, name: str) -> bool:
    wanted = str(name or '').strip().lower()
    return any(str(col or '').strip().lower() == wanted for col in df.columns)


def _non_blank_column(df: pd.DataFrame, name: str) -> bool:
    for col in df.columns:
        if str(col or '').strip().lower() == str(name or '').strip().lower():
            return bool(df[col].fillna('').astype(str).str.strip().ne('').any())
    return False


def _category_decision_done() -> bool:
    return bool(st.session_state.get(CATEGORY_DONE_KEY) or st.session_state.get(CATEGORY_SKIP_KEY))


def _expected_table_signature() -> str:
    return str(st.session_state.get(FINAL_DOWNLOAD_SIGNATURE_KEY) or st.session_state.get(GLOBAL_FINAL_DATASET_SIGNATURE_KEY) or '').strip()


def validate_before_bling_send(df: pd.DataFrame, operation: object) -> SendGuardResult:
    op = _operation(operation)
    messages: list[str] = []
    expected_table = _expected_table_signature()
    current_table = dataframe_table_signature(df, context='send_validation_v2') if isinstance(df, pd.DataFrame) else 'empty'
    category_col = _category_column(df) if isinstance(df, pd.DataFrame) else ''
    current_category = category_values_signature(df, category_col, context='send_validation_v2') if isinstance(df, pd.DataFrame) else 'empty'
    expected_category = str(st.session_state.get(CATEGORY_VALUES_SIGNATURE_KEY) or '')
    details: dict[str, Any] = {
        'operation': op,
        'rows': int(len(df)) if isinstance(df, pd.DataFrame) else 0,
        'table_signature': current_table,
        'expected_table_signature': expected_table,
        'category_signature': current_category,
        'expected_category_signature': expected_category,
        'category_decision_done': bool(st.session_state.get(CATEGORY_DONE_KEY)),
        'category_decision_skipped': bool(st.session_state.get(CATEGORY_SKIP_KEY)),
        'responsible_file': RESPONSIBLE_FILE,
    }

    if not isinstance(df, pd.DataFrame) or df.empty:
        return SendGuardResult(False, 'PARAR', ('Nenhuma linha pronta para envio.',), details)
    if expected_table and expected_table != current_table:
        messages.append('A tabela atual mudou depois da última prévia. Gere a prévia final novamente.')
    if op == 'cadastro' and category_col:
        if not _category_decision_done():
            messages.append('Confirme ou pule a conferência de categorias antes do envio.')
        elif not expected_category or expected_category != current_category:
            messages.append('As categorias mudaram depois da conferência. Confirme novamente.')
    if op == 'atualizacao_preco':
        price_details = price_validation_details(df)
        details['price_columns'] = list(price_details.get('price_columns') or [])
        details['invalid_price_count'] = int(price_details.get('invalid_count') or 0)
        details['invalid_price_rows'] = list(price_details.get('invalid_rows') or [])[:30]
        messages.extend(validate_price_update_values(df, label='Envio de preços'))
        if not _has_column(df, 'Bling preço destino'):
            messages.append('Escolha Preço geral ou Canal de venda antes de enviar preços.')
        elif str(df['Bling preço destino'].fillna('').astype(str).iloc[0]).strip().lower() != 'preço geral':
            if not _non_blank_column(df, 'Bling canal venda id'):
                messages.append('Canal de venda selecionado sem ID.')
    elif op == 'estoque':
        if not _non_blank_column(df, 'Bling depósito id'):
            messages.append('Selecione o depósito antes de atualizar estoque.')
    if messages:
        return SendGuardResult(False, 'PARAR', tuple(messages), details)
    return SendGuardResult(True, 'OK', ('Validação concluída.',), details)


__all__ = ['SendGuardResult', 'validate_before_bling_send']
