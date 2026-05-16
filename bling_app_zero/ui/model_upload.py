from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any

import pandas as pd
import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.ui.home_shared import preview_df, read_upload_fast

MODEL_SPREADSHEET_TYPES = ['xlsx', 'xls', 'csv', 'xlsm', 'xlsb']

STOCK_REQUIRED_DEPOSIT_TERMS = ['deposito', 'deposito obrigatorio']
STOCK_REQUIRED_BALANCE_TERMS = ['balanco', 'balanco obrigatorio', 'saldo', 'quantidade', 'estoque']
STOCK_IDENTIFIER_TERMS = ['id produto', 'codigo produto', 'codigo', 'gtin', 'descricao produto', 'descricao']
CADASTRO_REQUIRED_TERMS = ['codigo', 'descricao', 'preco']
CADASTRO_STRONG_TERMS = [
    'ncm',
    'marca',
    'categoria',
    'descricao complementar',
    'descricao curta',
    'unidade',
    'gtin ean',
    'url imagens externas',
    'codigo pai',
    'grupo de produtos',
]


@dataclass
class ModelUploadResult:
    cadastro_model_file: Any | None = None
    cadastro_model_df: pd.DataFrame | None = None
    estoque_model_file: Any | None = None
    estoque_model_df: pd.DataFrame | None = None
    model_file: Any | None = None
    model_df: pd.DataFrame | None = None
    attachments: list[Any] | None = None
    ignored_files: list[Any] | None = None


def _normalize_text(value: Any) -> str:
    text = str(value if value is not None else '').strip().lower()
    text = unicodedata.normalize('NFKD', text)
    text = ''.join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r'[^a-z0-9]+', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()


def _file_name(file: Any) -> str:
    return str(getattr(file, 'name', 'arquivo')).strip()


def _file_ext(file: Any) -> str:
    name = _file_name(file).lower()
    return name.rsplit('.', 1)[-1] if '.' in name else ''


def _file_audit_info(file: Any) -> dict[str, Any]:
    return {
        'name': _file_name(file),
        'extension': _file_ext(file),
        'size': getattr(file, 'size', None),
        'type': getattr(file, 'type', None),
    }


def _df_audit_info(df: pd.DataFrame | None) -> dict[str, Any]:
    if not isinstance(df, pd.DataFrame):
        return {'valid': False}
    return {
        'valid': True,
        'rows': int(len(df)),
        'columns_count': int(len(df.columns)),
        'columns': [str(column) for column in list(df.columns)[:80]],
    }


def _safe_read(file: Any) -> pd.DataFrame | None:
    try:
        df = read_upload_fast(file)
        add_audit_event(
            'model_file_read',
            area='MODELO',
            details={'file': _file_audit_info(file), 'dataframe': _df_audit_info(df)},
        )
        return df
    except Exception as exc:
        add_audit_event(
            'model_file_read_failed',
            area='MODELO',
            status='ERRO',
            details={'file': _file_audit_info(file), 'error': str(exc)},
        )
        return None


def _columns(df: pd.DataFrame | None) -> list[str]:
    if not isinstance(df, pd.DataFrame):
        return []
    return [_normalize_text(column) for column in df.columns]


def _column_text(df: pd.DataFrame | None) -> str:
    return ' '.join(_columns(df))


def _has_any_column(df: pd.DataFrame | None, terms: list[str]) -> bool:
    columns = _columns(df)
    normalized_terms = [_normalize_text(term) for term in terms]
    return any(any(term and term in column for column in columns) for term in normalized_terms)


def _has_all_column_groups(df: pd.DataFrame | None, terms: list[str]) -> bool:
    columns = _columns(df)
    normalized_terms = [_normalize_text(term) for term in terms]
    return all(any(term and term in column for column in columns) for term in normalized_terms)


def _official_stock_model(file: Any, df: pd.DataFrame | None) -> bool:
    """Reconhece os modelos oficiais de saldo/estoque do Bling.

    Os modelos oficiais de estoque têm colunas como Depósito e Balanço/Saldo.
    Mesmo quando também possuem GTIN, descrição e preço unitário, eles não devem
    ser tratados como cadastro de produto.
    """
    name = _normalize_text(_file_name(file))
    columns = _column_text(df)
    if not columns:
        return False

    has_deposit = _has_any_column(df, STOCK_REQUIRED_DEPOSIT_TERMS)
    has_balance = _has_any_column(df, STOCK_REQUIRED_BALANCE_TERMS)
    has_identifier = _has_any_column(df, STOCK_IDENTIFIER_TERMS)
    name_says_stock = any(term in name for term in ['saldo estoque', 'saldo', 'estoque'])

    if has_deposit and has_balance:
        return True
    if name_says_stock and has_balance and has_identifier:
        return True
    return False


def _official_cadastro_model(file: Any, df: pd.DataFrame | None) -> bool:
    """Reconhece os modelos oficiais de cadastro/produtos do Bling.

    O modelo de cadastro pode ter uma coluna "Estoque", mas não tem o par
    obrigatorio "Deposito" + "Balanco". Por isso ele deve ser classificado como
    cadastro quando aparecer com colunas fortes de produto.
    """
    if _official_stock_model(file, df):
        return False

    name = _normalize_text(_file_name(file))
    columns = _column_text(df)
    if not columns:
        return False

    name_says_product = any(term in name for term in ['produto', 'produtos', 'cadastro', 'modelo', 'bling', 'magalu', 'marketplace', 'marketplaces'])
    has_required_base = _has_all_column_groups(df, CADASTRO_REQUIRED_TERMS)
    has_product_taxonomy = _has_any_column(df, ['ncm', 'marca', 'categoria'])
    has_product_extra = _has_any_column(df, ['descricao complementar', 'descricao curta', 'url imagens externas', 'gtin ean'])

    return has_required_base and (name_says_product or has_product_taxonomy or has_product_extra)


def _score_cadastro_model(file: Any, df: pd.DataFrame | None) -> int:
    if _official_stock_model(file, df):
        return 0

    name = _normalize_text(_file_name(file))
    columns = _column_text(df)
    score = 0
    if _official_cadastro_model(file, df):
        score += 180
    if any(term in name for term in ['modelo', 'bling', 'cadastro', 'produto', 'produtos', 'layout', 'importacao', 'magalu', 'marketplace', 'marketplaces']):
        score += 35
    if any(term in columns for term in ['gtin', 'ean', 'preco', 'descricao', 'ncm', 'marca', 'categoria', 'sku', 'titulo']):
        score += 70
    if any(term in columns for term in CADASTRO_STRONG_TERMS):
        score += 35
    if any(term in columns for term in ['deposito', 'balanco', 'saldo estoque']):
        score -= 120
    return score


def _score_estoque_model(file: Any, df: pd.DataFrame | None) -> int:
    name = _normalize_text(_file_name(file))
    columns = _column_text(df)
    score = 0
    if _official_stock_model(file, df):
        score += 180
    else:
        if _official_cadastro_model(file, df):
            return 0
        if any(term in name for term in ['estoque', 'saldo']):
            score += 35
        if any(term in columns for term in ['deposito', 'balanco', 'saldo']):
            score += 80
        if any(term in columns for term in ['id produto', 'codigo produto', 'descricao produto']):
            score += 25
    return score


def _pick_cadastro(loaded: list[tuple[Any, pd.DataFrame | None]]) -> tuple[Any | None, pd.DataFrame | None]:
    candidates = [item for item in loaded if not _official_stock_model(item[0], item[1])]
    if not candidates:
        return None, None
    file, df = max(candidates, key=lambda item: _score_cadastro_model(item[0], item[1]))
    if _score_cadastro_model(file, df) < 45:
        return None, None
    return file, df


def _pick_generic_cadastro_contract(loaded: list[tuple[Any, pd.DataFrame | None]]) -> tuple[Any | None, pd.DataFrame | None]:
    """Fallback para modelos de marketplace que não parecem Bling.

    Quando o usuário está no fluxo de cadastro e anexou uma planilha modelo de
    marketplace, como Magalu, Mercado Livre ou outro canal, ela deve virar
    contrato do arquivo final mesmo sem colunas oficiais do Bling.
    """
    candidates: list[tuple[Any, pd.DataFrame]] = []
    for file, df in loaded:
        if _official_stock_model(file, df):
            continue
        if isinstance(df, pd.DataFrame) and len(df.columns):
            candidates.append((file, df.copy().fillna('')))
    if not candidates:
        return None, None
    return candidates[0]


def _pick_estoque(loaded: list[tuple[Any, pd.DataFrame | None]], used_file: Any | None) -> tuple[Any | None, pd.DataFrame | None]:
    candidates = [item for item in loaded if item[0] is not used_file]
    if not candidates:
        return None, None
    file, df = max(candidates, key=lambda item: _score_estoque_model(item[0], item[1]))
    if _score_estoque_model(file, df) < 45:
        return None, None
    return file, df


def _detected_message(cadastro_df: pd.DataFrame | None, estoque_df: pd.DataFrame | None) -> str:
    if isinstance(estoque_df, pd.DataFrame) and not isinstance(cadastro_df, pd.DataFrame):
        return 'Modelo de estoque reconhecido automaticamente. Próximo fluxo: atualizar estoque.'
    if isinstance(cadastro_df, pd.DataFrame) and not isinstance(estoque_df, pd.DataFrame):
        return 'Modelo de cadastro/marketplace reconhecido automaticamente. Próximo fluxo: cadastrar produtos.'
    if isinstance(cadastro_df, pd.DataFrame) and isinstance(estoque_df, pd.DataFrame):
        return 'Modelos de cadastro e estoque reconhecidos.'
    return 'Arquivo recebido. Confira se é um modelo de importação válido.'


def _render_detected_summary(
    supported_files: list[Any],
    cadastro_file: Any | None,
    estoque_file: Any | None,
    cadastro_df: pd.DataFrame | None,
    estoque_df: pd.DataFrame | None,
) -> None:
    if not supported_files:
        return
    st.success(_detected_message(cadastro_df, estoque_df))
    if isinstance(cadastro_df, pd.DataFrame) or isinstance(estoque_df, pd.DataFrame):
        with st.expander('Conferir modelos detectados', expanded=False):
            if isinstance(cadastro_df, pd.DataFrame):
                st.caption(f'Cadastro/marketplace: {_file_name(cadastro_file)}' if cadastro_file else 'Cadastro/marketplace detectado')
                preview_df('Cadastro/marketplace', cadastro_df)
            if isinstance(estoque_df, pd.DataFrame):
                st.caption(f'Estoque: {_file_name(estoque_file)}' if estoque_file else 'Estoque detectado')
                preview_df('Estoque', estoque_df)


def render_model_upload_box(
    title: str,
    operation: str,
    key: str,
    required_model: bool = False,
    caption: str | None = None,
) -> ModelUploadResult:
    files = st.file_uploader(
        'Enviar modelos de importação',
        type=None,
        accept_multiple_files=True,
        key=key,
        help='Envie o modelo de cadastro, marketplace, estoque ou ambos.',
        label_visibility='collapsed',
    )

    if not files:
        return ModelUploadResult(attachments=[], ignored_files=[])

    selected_files = list(files)
    supported_files = [file for file in selected_files if _file_ext(file) in MODEL_SPREADSHEET_TYPES]
    ignored_files = [file for file in selected_files if _file_ext(file) not in MODEL_SPREADSHEET_TYPES]
    add_audit_event(
        'model_upload_received',
        area='MODELO',
        details={
            'title': title,
            'operation': operation,
            'key': key,
            'required_model': required_model,
            'caption': caption,
            'file_count': len(selected_files),
            'supported_count': len(supported_files),
            'ignored_count': len(ignored_files),
            'files': [_file_audit_info(file) for file in selected_files],
            'ignored_files': [_file_audit_info(file) for file in ignored_files],
        },
    )

    if not supported_files:
        add_audit_event(
            'model_upload_without_supported_files',
            area='MODELO',
            status='BLOQUEADO',
            details={'files': [_file_audit_info(file) for file in selected_files]},
        )
        st.warning('Nenhuma planilha compatível encontrada.')
        return ModelUploadResult(attachments=[], ignored_files=ignored_files)

    loaded = [(file, _safe_read(file)) for file in supported_files]
    cadastro_file, cadastro_df = _pick_cadastro(loaded)
    if str(operation or '').strip().lower() == 'cadastro' and not isinstance(cadastro_df, pd.DataFrame):
        cadastro_file, cadastro_df = _pick_generic_cadastro_contract(loaded)
    estoque_file, estoque_df = _pick_estoque(loaded, cadastro_file)

    if isinstance(estoque_df, pd.DataFrame) and not isinstance(cadastro_df, pd.DataFrame):
        operation = 'estoque'
    elif isinstance(cadastro_df, pd.DataFrame) and not isinstance(estoque_df, pd.DataFrame):
        operation = 'cadastro'

    model_file, model_df = (estoque_file, estoque_df) if operation == 'estoque' else (cadastro_file, cadastro_df)
    add_audit_event(
        'model_upload_classified',
        area='MODELO',
        details={
            'operation': operation,
            'cadastro_file': _file_audit_info(cadastro_file) if cadastro_file else None,
            'estoque_file': _file_audit_info(estoque_file) if estoque_file else None,
            'selected_model_file': _file_audit_info(model_file) if model_file else None,
            'cadastro_df': _df_audit_info(cadastro_df),
            'estoque_df': _df_audit_info(estoque_df),
            'selected_df': _df_audit_info(model_df),
        },
    )
    _render_detected_summary(supported_files, cadastro_file, estoque_file, cadastro_df, estoque_df)

    return ModelUploadResult(
        cadastro_model_file=cadastro_file,
        cadastro_model_df=cadastro_df,
        estoque_model_file=estoque_file,
        estoque_model_df=estoque_df,
        model_file=model_file,
        model_df=model_df,
        attachments=supported_files,
        ignored_files=ignored_files,
    )