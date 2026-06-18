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

# As assinaturas globais incluem o campo "context" no hash. A prévia/download
# salva a tabela com context='final_download' e a conferência de categorias salva
# categorias com context='category_conference'. Se a validação recalcular tudo com
# context='send_validation_v2', o hash muda mesmo quando a tabela é idêntica.
# Por isso a guarda compara contra os contextos oficiais de origem da assinatura
# e mantém o contexto local apenas como diagnóstico.
TABLE_SIGNATURE_CONTEXTS = ('final_download', 'send_validation_v2', '')
CATEGORY_SIGNATURE_CONTEXTS = ('category_conference', 'send_validation_v2', '')


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


def _signature_context_label(context: str) -> str:
    return context or 'default'


def _table_signatures(df: pd.DataFrame) -> dict[str, str]:
    return {
        _signature_context_label(context): dataframe_table_signature(df, context=context)
        for context in TABLE_SIGNATURE_CONTEXTS
    }


def _category_signatures(df: pd.DataFrame, category_col: str) -> dict[str, str]:
    return {
        _signature_context_label(context): category_values_signature(df, category_col, context=context)
        for context in CATEGORY_SIGNATURE_CONTEXTS
    }


def validate_before_bling_send(df: pd.DataFrame, operation: object) -> SendGuardResult:
    op = _operation(operation)
    messages: list[str] = []
    expected_table = _expected_table_signature()
    table_signatures = _table_signatures(df) if isinstance(df, pd.DataFrame) else {'final_download': 'empty'}
    current_table = table_signatures.get('final_download') or next(iter(table_signatures.values()), 'empty')
    category_col = _category_column(df) if isinstance(df, pd.DataFrame) else ''
    category_signatures = _category_signatures(df, category_col) if isinstance(df, pd.DataFrame) else {'category_conference': 'empty'}
    current_category = category_signatures.get('category_conference') or next(iter(category_signatures.values()), 'empty')
    expected_category = str(st.session_state.get(CATEGORY_VALUES_SIGNATURE_KEY) or '')
    details: dict[str, Any] = {
        'operation': op,
        'rows': int(len(df)) if isinstance(df, pd.DataFrame) else 0,
        'table_signature': current_table,
        'expected_table_signature': expected_table,
        'table_signature_context': 'final_download',
        'table_validation_signature': table_signatures.get('send_validation_v2', current_table),
        'category_signature': current_category,
        'expected_category_signature': expected_category,
        'category_signature_context': 'category_conference',
        'category_validation_signature': category_signatures.get('send_validation_v2', current_category),
        'category_decision_done': bool(st.session_state.get(CATEGORY_DONE_KEY)),
        'category_decision_skipped': bool(st.session_state.get(CATEGORY_SKIP_KEY)),
        'responsible_file': RESPONSIBLE_FILE,
    }

    if not isinstance(df, pd.DataFrame) or df.empty:
        return SendGuardResult(False, 'PARAR', ('Nenhuma linha pronta para envio.',), details)
    if expected_table and expected_table not in set(table_signatures.values()):
        messages.append('A tabela atual mudou depois da última prévia. Gere a prévia final novamente.')
    if op == 'cadastro' and category_col:
        if not _category_decision_done():
            messages.append('Confirme ou pule a conferência de categorias antes do envio.')
        elif expected_category and expected_category not in set(category_signatures.values()):
            messages.append('As categorias mudaram depois da conferência. Confirme novamente.')
        elif not expected_category:
            messages.append('As categorias ainda não têm assinatura de conferência. Confirme novamente.')
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
