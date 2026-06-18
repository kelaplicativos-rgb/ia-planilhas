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
BLOCKED_FINAL_CATEGORY_VALUES = {'', 'nan', 'none', 'null', '<na>', 'na', 'n/a', 'sem categoria', 'revisar manualmente'}
FULL_VALIDATION_SESSION_KEYS = (
    'df_final_bling_api',
    'df_final_download_operation',
    'final_download_df_snapshot',
    'df_final_cadastro_preview_rules_applied',
    'df_final_cadastro',
    'df_final_universal',
)


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


def _valid_df(value: object) -> bool:
    return isinstance(value, pd.DataFrame) and not value.empty and len(value.columns) > 0


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


def _category_was_auto_applied() -> bool:
    return bool(st.session_state.get(CATEGORY_DONE_KEY)) and not bool(st.session_state.get(CATEGORY_SKIP_KEY))


def _final_category_issue_rows(df: pd.DataFrame, category_col: str) -> tuple[int, ...]:
    if not isinstance(df, pd.DataFrame) or df.empty or not category_col or category_col not in df.columns:
        return tuple(range(1, int(len(df)) + 1)) if isinstance(df, pd.DataFrame) else tuple()
    bad_rows: list[int] = []
    for pos, value in enumerate(df[category_col].fillna('').astype(str), start=1):
        normalized = ' '.join(str(value or '').strip().lower().split())
        if normalized in BLOCKED_FINAL_CATEGORY_VALUES:
            bad_rows.append(pos)
    return tuple(bad_rows)


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


def _full_validation_dataframe_from_session(df: pd.DataFrame, expected_table: str) -> tuple[pd.DataFrame, str]:
    """Recupera a tabela final completa quando a validação recebe apenas um lote.

    O envio API processa lotes menores, mas a assinatura salva na prévia final é
    da tabela inteira. Sem isso, o último lote de 1 linha é bloqueado como se a
    tabela tivesse mudado. Só trocamos para a tabela completa se ela bater com a
    assinatura final esperada.
    """
    if not _valid_df(df) or not expected_table:
        return df, ''
    input_rows = int(len(df))
    input_columns = [str(col) for col in df.columns]
    for key in FULL_VALIDATION_SESSION_KEYS:
        candidate = st.session_state.get(key)
        if not _valid_df(candidate):
            continue
        candidate_df = candidate.copy().fillna('')
        if int(len(candidate_df)) < input_rows:
            continue
        if [str(col) for col in candidate_df.columns] != input_columns:
            continue
        try:
            candidate_signatures = _table_signatures(candidate_df)
        except Exception:
            continue
        if expected_table in set(candidate_signatures.values()):
            return candidate_df, key
    return df, ''


def validate_before_bling_send(df: pd.DataFrame, operation: object) -> SendGuardResult:
    op = _operation(operation)
    messages: list[str] = []
    expected_table = _expected_table_signature()
    input_rows = int(len(df)) if isinstance(df, pd.DataFrame) else 0
    input_columns = int(len(df.columns)) if isinstance(df, pd.DataFrame) else 0
    validation_df = df
    validation_source_key = ''
    if isinstance(df, pd.DataFrame):
        validation_df, validation_source_key = _full_validation_dataframe_from_session(df, expected_table)
    table_signatures = _table_signatures(validation_df) if isinstance(validation_df, pd.DataFrame) else {'final_download': 'empty'}
    current_table = table_signatures.get('final_download') or next(iter(table_signatures.values()), 'empty')
    category_col = _category_column(validation_df) if isinstance(validation_df, pd.DataFrame) else ''
    category_signatures = _category_signatures(validation_df, category_col) if isinstance(validation_df, pd.DataFrame) else {'category_conference': 'empty'}
    current_category = category_signatures.get('category_conference') or next(iter(category_signatures.values()), 'empty')
    expected_category = str(st.session_state.get(CATEGORY_VALUES_SIGNATURE_KEY) or '')
    auto_category_applied = _category_was_auto_applied()
    category_issue_rows = _final_category_issue_rows(validation_df, category_col) if op == 'cadastro' and isinstance(validation_df, pd.DataFrame) else tuple()
    details: dict[str, Any] = {
        'operation': op,
        'rows': int(len(validation_df)) if isinstance(validation_df, pd.DataFrame) else 0,
        'input_rows': input_rows,
        'input_columns': input_columns,
        'validation_source_key': validation_source_key,
        'validation_uses_full_dataset': bool(validation_source_key),
        'table_signature': current_table,
        'expected_table_signature': expected_table,
        'table_signature_context': 'final_download',
        'table_validation_signature': table_signatures.get('send_validation_v2', current_table),
        'category_column': category_col,
        'category_signature': current_category,
        'expected_category_signature': expected_category,
        'category_signature_context': 'category_conference',
        'category_validation_signature': category_signatures.get('send_validation_v2', current_category),
        'category_decision_done': bool(st.session_state.get(CATEGORY_DONE_KEY)),
        'category_decision_skipped': bool(st.session_state.get(CATEGORY_SKIP_KEY)),
        'auto_category_applied': auto_category_applied,
        'category_required_complete_for_cadastro': op == 'cadastro',
        'category_missing_count': len(category_issue_rows),
        'category_missing_rows_sample': list(category_issue_rows[:50]),
        'responsible_file': RESPONSIBLE_FILE,
    }

    if not isinstance(df, pd.DataFrame) or df.empty:
        return SendGuardResult(False, 'PARAR', ('Nenhuma linha pronta para envio.',), details)
    if expected_table and expected_table not in set(table_signatures.values()):
        messages.append('A tabela atual mudou depois da última prévia. Gere a prévia final novamente.')
    if op == 'cadastro':
        if not category_col:
            messages.append('Cadastro bloqueado: a tabela final não possui coluna de categoria. Nenhum produto será enviado ao Bling sem categoria válida.')
        elif category_issue_rows:
            sample = ', '.join(map(str, list(category_issue_rows[:20])))
            suffix = '...' if len(category_issue_rows) > 20 else ''
            messages.append(f'Cadastro bloqueado: {len(category_issue_rows)} produto(s) estão sem categoria final válida. Linhas: {sample}{suffix}. Corrija antes de enviar ao Bling.')
        if category_col:
            if not _category_decision_done():
                messages.append('Confirme ou pule a conferência de categorias antes do envio.')
            elif expected_category and expected_category not in set(category_signatures.values()):
                messages.append('As categorias mudaram depois da conferência. Confirme novamente.')
            elif not expected_category:
                messages.append('As categorias ainda não têm assinatura de conferência. Confirme novamente.')
    if op == 'atualizacao_preco':
        price_details = price_validation_details(validation_df)
        details['price_columns'] = list(price_details.get('price_columns') or [])
        details['invalid_price_count'] = int(price_details.get('invalid_count') or 0)
        details['invalid_price_rows'] = list(price_details.get('invalid_rows') or [])[:30]
        messages.extend(validate_price_update_values(validation_df, label='Envio de preços'))
        if not _has_column(validation_df, 'Bling preço destino'):
            messages.append('Escolha Preço geral ou Canal de venda antes de enviar preços.')
        elif str(validation_df['Bling preço destino'].fillna('').astype(str).iloc[0]).strip().lower() != 'preço geral':
            if not _non_blank_column(validation_df, 'Bling canal venda id'):
                messages.append('Canal de venda selecionado sem ID.')
    elif op == 'estoque':
        if not _non_blank_column(validation_df, 'Bling depósito id'):
            messages.append('Selecione o depósito antes de atualizar estoque.')
    if messages:
        return SendGuardResult(False, 'PARAR', tuple(messages), details)
    return SendGuardResult(True, 'OK', ('Validação concluída.',), details)


__all__ = ['SendGuardResult', 'validate_before_bling_send']
