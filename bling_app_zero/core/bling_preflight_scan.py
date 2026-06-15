from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import pandas as pd

from bling_app_zero.core.final_download_resources import MAX_IMAGE_URLS_PER_PRODUCT, image_url_parts
from bling_app_zero.core.operation_contract import OP_ATUALIZACAO_PRECO, OP_CADASTRO, OP_ESTOQUE, normalize_operation
from bling_app_zero.core.text import normalize_key

RESPONSIBLE_FILE = 'bling_app_zero/core/bling_preflight_scan.py'
PENDING_IMAGE_LIMIT = 'PRODUTO_COM_MAIS_DE_6_IMAGENS'
PENDING_REQUIRED_FIELDS = 'CAMPO_OBRIGATORIO'

_CODE_TERMS = ('codigo', 'código', 'sku', 'referencia', 'referência', 'id produto', 'id bling')
_GTIN_TERMS = ('gtin', 'ean', 'codigo de barras', 'código de barras')
_NAME_TERMS = ('nome', 'produto', 'descrição', 'descricao', 'titulo', 'título')
_QTY_TERMS = ('quantidade', 'qtd', 'saldo', 'estoque', 'balanço', 'balanco')
_PRICE_TERMS = ('preco', 'preço', 'valor', 'valor venda', 'preco venda', 'preço venda', 'preco unitario', 'preço unitário')
_IMAGE_TERMS = ('imagem', 'imagens', 'foto', 'fotos', 'url imagem')
_ID_BLING_TERMS = (
    'id',
    'id produto',
    'id_produto',
    'id produto bling',
    'id_produto_bling',
    'id bling',
    'id_bling',
    'codigo bling',
    'código bling',
)


@dataclass(frozen=True)
class BlingPreflightReport:
    operation: str
    total_rows: int
    safe_to_send_rows: int
    blocked_rows: int
    missing_identifier_rows: int
    missing_required_rows: int
    rows_with_images: int
    rows_over_image_limit: int
    estimated_batches: int
    batch_size: int
    block_send: bool
    sendable_index_labels: tuple[Any, ...]
    blocked_index_labels: tuple[Any, ...]
    warnings: tuple[str, ...]
    responsible_file: str = RESPONSIBLE_FILE

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data['sendable_index_labels'] = list(self.sendable_index_labels)
        data['blocked_index_labels'] = list(self.blocked_index_labels)
        data['warnings'] = list(self.warnings)
        return data


def _normalized_columns(df: pd.DataFrame) -> dict[str, str]:
    return {normalize_key(column): str(column) for column in df.columns}


def _find_column(df: pd.DataFrame, terms: tuple[str, ...]) -> str:
    columns = _normalized_columns(df)
    normalized_terms = [normalize_key(term) for term in terms]
    for normalized, original in columns.items():
        if any(term in normalized for term in normalized_terms):
            return original
    return ''


def _filled_mask(df: pd.DataFrame, column: str) -> pd.Series:
    if not column or column not in df.columns:
        return pd.Series([False] * len(df), index=df.index)
    return df[column].fillna('').astype(str).str.strip().ne('')


def _safe_value(row: pd.Series, column: str) -> str:
    if not column or column not in row.index:
        return ''
    value = row.get(column, '')
    if pd.isna(value):
        return ''
    return str(value or '').strip()


def _image_count(value: object) -> int:
    return len(image_url_parts(value))


def _image_count_for_row(row: pd.Series, columns: dict[str, str]) -> int:
    image_column = columns.get('imagem', '')
    if not image_column or image_column not in row.index:
        return 0
    return _image_count(row.get(image_column, ''))


def _image_excess_mask(df: pd.DataFrame, columns: dict[str, str] | None = None) -> pd.Series:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return pd.Series([], dtype=bool)
    columns = columns or _operation_columns(df)
    image_column = columns.get('imagem', '')
    if not image_column or image_column not in df.columns:
        return pd.Series([False] * len(df), index=df.index)
    return df[image_column].fillna('').map(lambda value: _image_count(value) > MAX_IMAGE_URLS_PER_PRODUCT)


def _operation_columns(df: pd.DataFrame) -> dict[str, str]:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return {'codigo': '', 'gtin': '', 'nome': '', 'quantidade': '', 'preco': '', 'imagem': '', 'id_bling': ''}
    return {
        'codigo': _find_column(df, _CODE_TERMS),
        'gtin': _find_column(df, _GTIN_TERMS),
        'nome': _find_column(df, _NAME_TERMS),
        'quantidade': _find_column(df, _QTY_TERMS),
        'preco': _find_column(df, _PRICE_TERMS),
        'imagem': _find_column(df, _IMAGE_TERMS),
        'id_bling': _find_column(df, _ID_BLING_TERMS),
    }


def _required_mask(df: pd.DataFrame, operation: str, columns: dict[str, str] | None = None) -> pd.Series:
    op = normalize_operation(operation)
    if not isinstance(df, pd.DataFrame) or df.empty:
        return pd.Series([], dtype=bool)

    columns = columns or _operation_columns(df)
    has_identifier = _filled_mask(df, columns['codigo']) | _filled_mask(df, columns['gtin']) | _filled_mask(df, columns['id_bling'])
    has_name = _filled_mask(df, columns['nome'])
    has_qty = _filled_mask(df, columns['quantidade'])
    has_price = _filled_mask(df, columns['preco'])

    if op == OP_ESTOQUE:
        return has_identifier & has_qty
    if op == OP_ATUALIZACAO_PRECO:
        return has_identifier & has_price
    return has_identifier | has_name


def _sendable_mask(df: pd.DataFrame, operation: str) -> pd.Series:
    op = normalize_operation(operation)
    if not isinstance(df, pd.DataFrame) or df.empty:
        return pd.Series([], dtype=bool)
    columns = _operation_columns(df)
    required_ok = _required_mask(df, op, columns)
    if op == OP_CADASTRO:
        return required_ok & ~_image_excess_mask(df, columns)
    return required_ok


def pending_reason_for_row(row: pd.Series, operation: str, columns: dict[str, str]) -> str:
    op = normalize_operation(operation)
    image_count = _image_count_for_row(row, columns)
    if op == OP_CADASTRO and image_count > MAX_IMAGE_URLS_PER_PRODUCT:
        return f'{PENDING_IMAGE_LIMIT}: produto tem {image_count} imagens; o Bling aceita no máximo {MAX_IMAGE_URLS_PER_PRODUCT}.'

    has_code = bool(_safe_value(row, columns.get('codigo', '')))
    has_gtin = bool(_safe_value(row, columns.get('gtin', '')))
    has_id_bling = bool(_safe_value(row, columns.get('id_bling', '')))
    has_name = bool(_safe_value(row, columns.get('nome', '')))
    has_qty = bool(_safe_value(row, columns.get('quantidade', '')))
    has_price = bool(_safe_value(row, columns.get('preco', '')))
    has_identifier = has_code or has_gtin or has_id_bling

    if op == OP_ESTOQUE:
        missing: list[str] = []
        if not has_identifier:
            missing.append('ID Bling/SKU/código/GTIN')
        if not has_qty:
            missing.append('quantidade')
        return 'Falta ' + ' e '.join(missing) if missing else ''

    if op == OP_ATUALIZACAO_PRECO:
        missing = []
        if not has_identifier:
            missing.append('ID Bling ou SKU/código/GTIN')
        if not has_price:
            missing.append('preço')
        return 'Falta ' + ' e '.join(missing) if missing else ''

    if not has_identifier and not has_name:
        return 'Falta SKU/código/GTIN ou nome do produto'
    return ''


def _pending_kind_for_row(row: pd.Series, operation: str, columns: dict[str, str]) -> str:
    if normalize_operation(operation) == OP_CADASTRO and _image_count_for_row(row, columns) > MAX_IMAGE_URLS_PER_PRODUCT:
        return PENDING_IMAGE_LIMIT
    return PENDING_REQUIRED_FIELDS


def filter_sendable_dataframe(df: pd.DataFrame, operation: str) -> pd.DataFrame:
    """Mantém apenas linhas que podem ser enviadas com segurança ao Bling."""
    if not isinstance(df, pd.DataFrame) or df.empty:
        return pd.DataFrame()
    mask = _sendable_mask(df, operation)
    if len(mask) != len(df):
        return pd.DataFrame(columns=list(df.columns))
    return df.loc[mask].copy().fillna('')


def build_pending_rows_dataframe(df: pd.DataFrame, operation: str, *, limit: int = 100) -> pd.DataFrame:
    """Monta uma tabela curta com as linhas que foram bloqueadas pela pré-varredura."""
    columns_out = ['linha', 'tipo_pendencia', 'codigo', 'gtin', 'id_bling', 'produto', 'quantidade', 'preco', 'imagens', 'motivo']
    if not isinstance(df, pd.DataFrame) or df.empty:
        return pd.DataFrame(columns=columns_out)

    mask = _sendable_mask(df, operation)
    if len(mask) != len(df):
        return pd.DataFrame(columns=columns_out)

    columns = _operation_columns(df)
    blocked = df.loc[~mask].copy().fillna('')
    rows: list[dict[str, str]] = []
    for position, (index, row) in enumerate(blocked.iterrows(), start=1):
        if position > max(1, int(limit or 100)):
            break
        rows.append(
            {
                'linha': str(int(index) + 1 if isinstance(index, int) else index),
                'tipo_pendencia': _pending_kind_for_row(row, operation, columns),
                'codigo': _safe_value(row, columns['codigo']),
                'gtin': _safe_value(row, columns['gtin']),
                'id_bling': _safe_value(row, columns['id_bling']),
                'produto': _safe_value(row, columns['nome']),
                'quantidade': _safe_value(row, columns['quantidade']),
                'preco': _safe_value(row, columns['preco']),
                'imagens': str(_image_count_for_row(row, columns)),
                'motivo': pending_reason_for_row(row, operation, columns),
            }
        )
    return pd.DataFrame(rows, columns=columns_out)


def build_bling_preflight_report(df: pd.DataFrame, operation: str, *, batch_size: int) -> BlingPreflightReport:
    op = normalize_operation(operation)
    safe_batch = max(1, int(batch_size or 1))
    if not isinstance(df, pd.DataFrame) or df.empty:
        return BlingPreflightReport(
            operation=op,
            total_rows=0,
            safe_to_send_rows=0,
            blocked_rows=0,
            missing_identifier_rows=0,
            missing_required_rows=0,
            rows_with_images=0,
            rows_over_image_limit=0,
            estimated_batches=0,
            batch_size=safe_batch,
            block_send=True,
            sendable_index_labels=tuple(),
            blocked_index_labels=tuple(),
            warnings=('Nenhuma linha encontrada para envio.',),
        )

    total = int(len(df))
    columns = _operation_columns(df)
    has_identifier = _filled_mask(df, columns['codigo']) | _filled_mask(df, columns['gtin']) | _filled_mask(df, columns['id_bling'])
    required_ok = _required_mask(df, op, columns)
    image_excess = _image_excess_mask(df, columns) if op == OP_CADASTRO else pd.Series([False] * len(df), index=df.index)
    sendable = required_ok & ~image_excess

    safe_rows = int(sendable.sum())
    blocked_rows = int(total - safe_rows)
    missing_identifier = int((~has_identifier).sum())
    missing_required = int((~required_ok).sum())
    rows_with_images = int(_filled_mask(df, columns['imagem']).sum()) if columns['imagem'] else 0
    rows_over_image_limit = int(image_excess.sum()) if len(image_excess) == len(df) else 0
    estimated_batches = int((safe_rows + safe_batch - 1) // safe_batch) if safe_rows else 0
    sendable_labels = tuple(df.index[sendable].tolist())
    blocked_labels = tuple(df.index[~sendable].tolist())
    block_send = safe_rows <= 0

    warnings: list[str] = []
    if block_send:
        warnings.append('Envio bloqueado: nenhuma linha tem os campos mínimos para a API do Bling.')
    if total > 300:
        warnings.append('Muitas linhas detectadas; o envio será filtrado, protegido por lotes menores e checkpoint.')
    if rows_over_image_limit:
        warnings.append(f'{rows_over_image_limit} produto(s) ficaram como pendência {PENDING_IMAGE_LIMIT}.')
    if blocked_rows:
        warnings.append(f'{blocked_rows} linha(s) serão mantidas como pendência e não entrarão no lote da API.')
    if missing_identifier:
        warnings.append(f'{missing_identifier} linha(s) sem ID/SKU/código/GTIN; podem virar pendência.')
    if missing_required:
        warnings.append(f'{missing_required} linha(s) não têm os campos mínimos para envio seguro.')
    if op == OP_ATUALIZACAO_PRECO:
        warnings.append('Atualização de preço exige preço e ID Bling ou identificador confiável para localizar o produto antes do PATCH.')
    if op == OP_CADASTRO and rows_with_images > 150:
        warnings.append('Muitas linhas com imagens; comparação/cadastro pode demorar mais.')
    if not warnings:
        warnings.append('Pré-varredura local sem bloqueios críticos.')

    return BlingPreflightReport(
        operation=op,
        total_rows=total,
        safe_to_send_rows=safe_rows,
        blocked_rows=blocked_rows,
        missing_identifier_rows=missing_identifier,
        missing_required_rows=missing_required,
        rows_with_images=rows_with_images,
        rows_over_image_limit=rows_over_image_limit,
        estimated_batches=estimated_batches,
        batch_size=safe_batch,
        block_send=block_send,
        sendable_index_labels=sendable_labels,
        blocked_index_labels=blocked_labels,
        warnings=tuple(warnings),
    )


__all__ = [
    'BlingPreflightReport',
    'PENDING_IMAGE_LIMIT',
    'PENDING_REQUIRED_FIELDS',
    'build_bling_preflight_report',
    'build_pending_rows_dataframe',
    'filter_sendable_dataframe',
    'pending_reason_for_row',
]
