from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd
import streamlit as st

from bling_app_zero.core.validators import price_validation_details, validate_price_update_values

RESPONSIBLE_FILE = 'bling_app_zero/core/bling_api_send_guard.py'
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
        return {
            'ok': self.ok,
            'status': self.status,
            'messages': list(self.messages),
            'details': dict(self.details),
        }


def _operation(value: object) -> str:
    text = str(value or '').strip().lower()
    if 'estoque' in text or 'saldo' in text or 'stock' in text:
        return 'estoque'
    if 'preco' in text or 'preço' in text or 'price' in text:
        return 'atualizacao_preco'
    if 'cadastro' in text or 'produto' in text:
        return 'cadastro'
    return text or 'cadastro'


def _has_column(df: pd.DataFrame, name: str) -> bool:
    wanted = str(name or '').strip().lower()
    return any(str(col or '').strip().lower() == wanted for col in df.columns)


def _non_blank_column(df: pd.DataFrame, name: str) -> bool:
    for col in df.columns:
        if str(col or '').strip().lower() == str(name or '').strip().lower():
            return bool(df[col].fillna('').astype(str).str.strip().ne('').any())
    return False


def _category_column(df: pd.DataFrame) -> str:
    names = {'categoria', 'category', 'nome da categoria', 'categoria do produto'}
    for col in df.columns:
        if str(col or '').strip().lower() in names:
            return str(col)
    return ''


def _has_category_column(df: pd.DataFrame) -> bool:
    return bool(_category_column(df))


def _category_values_signature(df: pd.DataFrame) -> str:
    """Assina somente os valores, não o nome da coluna."""
    if not isinstance(df, pd.DataFrame) or df.empty:
        return 'empty'
    category_col = _category_column(df)
    if not category_col:
        return f'{len(df)}:no-category-column'
    values = df[category_col].fillna('').astype(str).str.strip()
    sample = pd.util.hash_pandas_object(values, index=True).sum()
    return f'{len(df)}:{sample}'


def _category_conference_decided() -> bool:
    return bool(st.session_state.get(CATEGORY_DONE_KEY) or st.session_state.get(CATEGORY_SKIP_KEY))


def validate_before_bling_send(df: pd.DataFrame, operation: object) -> SendGuardResult:
    op = _operation(operation)
    messages: list[str] = []
    current_category_signature = _category_values_signature(df) if isinstance(df, pd.DataFrame) else 'empty'
    expected_category_signature = str(st.session_state.get(CATEGORY_VALUES_SIGNATURE_KEY) or '')
    details: dict[str, Any] = {
        'operation': op,
        'rows': int(len(df)) if isinstance(df, pd.DataFrame) else 0,
        'category_conference_done': bool(st.session_state.get(CATEGORY_DONE_KEY)),
        'category_conference_skipped': bool(st.session_state.get(CATEGORY_SKIP_KEY)),
        'category_values_signature': current_category_signature,
        'expected_category_values_signature': expected_category_signature,
        'responsible_file': RESPONSIBLE_FILE,
    }

    if not isinstance(df, pd.DataFrame) or df.empty:
        return SendGuardResult(False, 'BLOQUEADO', ('Nenhuma linha pronta para envio ao Bling.',), details)

    if op == 'cadastro' and _has_category_column(df):
        if not _category_conference_decided():
            messages.append('Envio bloqueado: aplique a Conferência inteligente de categorias ou use “Pular sem alterar categorias”. Isso evita enviar categoria antiga/cache para o Bling.')
        elif not expected_category_signature or expected_category_signature != current_category_signature:
            messages.append('Envio bloqueado: as categorias atuais não batem com a última conferência aplicada/pulada. Volte em Regras e IA e confirme novamente para evitar envio de cache antigo.')

    if op == 'atualizacao_preco':
        price_details = price_validation_details(df)
        details['price_columns'] = list(price_details.get('price_columns') or [])
        details['invalid_price_count'] = int(price_details.get('invalid_count') or 0)
        details['invalid_price_rows'] = list(price_details.get('invalid_rows') or [])[:30]
        messages.extend(validate_price_update_values(df, label='Envio de preços bloqueado'))

        if not _has_column(df, 'Bling preço destino'):
            messages.append('Escolha Preço geral ou Canal de venda antes de enviar preços ao Bling.')
        elif str(df['Bling preço destino'].fillna('').astype(str).iloc[0]).strip().lower() != 'preço geral':
            if not _non_blank_column(df, 'Bling canal venda id'):
                messages.append('Canal de venda selecionado sem ID do canal. Selecione a loja/canal correto.')
    elif op == 'estoque':
        if not _non_blank_column(df, 'Bling depósito id'):
            messages.append('Selecione o depósito do Bling antes de atualizar estoque.')

    if messages:
        return SendGuardResult(False, 'BLOQUEADO', tuple(messages), details)
    return SendGuardResult(True, 'OK', ('Envio liberado pela validação de destino e conteúdo.',), details)


__all__ = ['SendGuardResult', 'validate_before_bling_send']
