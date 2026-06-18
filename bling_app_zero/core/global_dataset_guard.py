from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Iterable, Sequence

import pandas as pd

RESPONSIBLE_FILE = 'bling_app_zero/core/global_dataset_guard.py'
SIGNATURE_VERSION = 'global-dataset-v1'

# Chaves literais compartilhadas por UI/guardas sem criar import circular.
FINAL_DOWNLOAD_SIGNATURE_KEY = 'final_download_signature'
GLOBAL_LIVE_DATASET_SIGNATURE_KEY = 'global_live_dataset_signature_v1'
GLOBAL_FINAL_DATASET_SIGNATURE_KEY = 'global_final_dataset_signature_v1'
GLOBAL_DECISION_DATASET_SIGNATURE_KEY = 'global_decision_dataset_signature_v1'

_KIND_PATTERNS: dict[str, tuple[str, ...]] = {
    'nome': (
        'descricao', 'descrição', 'nome', 'nome produto', 'nome do produto', 'produto', 'titulo', 'título',
        'description', 'name',
    ),
    'sku': ('sku', 'codigo', 'código', 'codigo produto', 'código produto', 'referencia', 'referência', 'ref'),
    'ean': ('gtin', 'ean', 'codigo de barras', 'código de barras', 'barcode'),
    'categoria': ('categoria', 'category', 'nome da categoria', 'categoria produto', 'categoria do produto'),
    'preco': (
        'preco', 'preço', 'preco unitario', 'preço unitário', 'valor', 'valor venda', 'preco venda',
        'preço venda', 'price',
    ),
    'estoque': ('estoque', 'saldo', 'quantidade', 'qtd', 'balanco', 'balanço', 'stock'),
    'url': ('url', 'link', 'pagina', 'página', 'url produto', 'url do produto'),
    'imagem': ('imagem', 'imagens', 'image', 'images', 'foto', 'fotos'),
    'fornecedor': ('fornecedor', 'origem', 'loja', 'site'),
}

_PRIORITY_KINDS: tuple[str, ...] = ('nome', 'sku', 'ean', 'categoria', 'preco', 'estoque', 'url', 'imagem', 'fornecedor')


@dataclass(frozen=True)
class DatasetSignature:
    signature: str
    rows: int
    columns: int
    fields: tuple[str, ...]
    mode: str
    responsible_file: str = RESPONSIBLE_FILE

    def to_dict(self) -> dict[str, Any]:
        return {
            'signature': self.signature,
            'rows': self.rows,
            'columns': self.columns,
            'fields': list(self.fields),
            'mode': self.mode,
            'responsible_file': self.responsible_file,
        }


def normalize_text(value: object) -> str:
    text = '' if value is None else str(value)
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')
    text = text.lower().replace('&', ' e ').replace('/', ' ')
    text = re.sub(r'[^a-z0-9]+', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()


def _stable_cell(value: object) -> str:
    if value is None:
        return ''
    try:
        if pd.isna(value):
            return ''
    except Exception:
        pass
    text = str(value).replace('\r', ' ').replace('\n', ' ').replace('\ufeff', '').strip()
    return re.sub(r'\s+', ' ', text)


def _valid_df(df: object) -> bool:
    return isinstance(df, pd.DataFrame) and not df.empty and len(df.columns) > 0


def _column_score(column_norm: str, pattern_norm: str) -> int:
    if not column_norm or not pattern_norm:
        return 0
    if column_norm == pattern_norm:
        return 100
    if pattern_norm in column_norm:
        return 80 + min(19, len(pattern_norm))
    tokens = set(column_norm.split())
    pattern_tokens = set(pattern_norm.split())
    if pattern_tokens and pattern_tokens.issubset(tokens):
        return 70 + min(19, len(pattern_tokens))
    return 0


def detect_dataset_columns(df: pd.DataFrame) -> dict[str, str]:
    """Detecta colunas por significado, independente do nome exato do modelo.

    Exemplo: Categoria, Nome da categoria e category viram o mesmo campo lógico.
    """
    if not _valid_df(df):
        return {}
    normalized_columns = [(str(col), normalize_text(col)) for col in df.columns]
    detected: dict[str, str] = {}
    used_columns: set[str] = set()
    for kind in _PRIORITY_KINDS:
        best_col = ''
        best_score = 0
        for original, col_norm in normalized_columns:
            if original in used_columns:
                continue
            for pattern in _KIND_PATTERNS.get(kind, ()):  # pragma: no branch - tuple pequena
                score = _column_score(col_norm, normalize_text(pattern))
                if score > best_score:
                    best_col = original
                    best_score = score
        if best_col and best_score >= 80:
            detected[kind] = best_col
            used_columns.add(best_col)
    return detected


def _hash_json_rows(rows: Iterable[dict[str, str]], *, header: dict[str, Any]) -> str:
    digest = hashlib.sha256()
    digest.update(json.dumps(header, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8'))
    digest.update(b'\n')
    for row in rows:
        digest.update(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8'))
        digest.update(b'\n')
    return digest.hexdigest()


def dataframe_table_signature(df: pd.DataFrame, *, context: str = '') -> str:
    """Assinatura integral da tabela: todas as linhas, todas as colunas, sem amostra.

    Use para cache de preview/download/envio. Qualquer célula alterada muda a assinatura.
    """
    if not _valid_df(df):
        return f'{SIGNATURE_VERSION}:table:empty'
    columns = [str(col).replace('\ufeff', '').strip() for col in df.columns]
    header = {
        'version': SIGNATURE_VERSION,
        'mode': 'table',
        'context': str(context or ''),
        'rows': int(len(df)),
        'columns': columns,
    }

    def iter_rows() -> Iterable[dict[str, str]]:
        safe = df.fillna('')
        for _, row in safe.iterrows():
            yield {str(col): _stable_cell(row.get(col, '')) for col in df.columns}

    digest = _hash_json_rows(iter_rows(), header=header)
    return f'{SIGNATURE_VERSION}:table:{len(df)}x{len(df.columns)}:{digest}'


def dataframe_identity_signature(df: pd.DataFrame, *, context: str = '') -> DatasetSignature:
    """Assinatura de identidade do produto, estável entre origem e modelo final.

    Usa campos lógicos como nome, SKU, EAN, categoria, preço e estoque quando existem.
    Não depende do nome literal da coluna, mas considera todos os registros.
    """
    if not _valid_df(df):
        return DatasetSignature(f'{SIGNATURE_VERSION}:identity:empty', 0, 0, tuple(), 'identity')
    detected = detect_dataset_columns(df)
    if detected:
        fields = tuple(kind for kind in _PRIORITY_KINDS if kind in detected)
    else:
        fields = tuple(str(col) for col in df.columns)
    header = {
        'version': SIGNATURE_VERSION,
        'mode': 'identity',
        'context': str(context or ''),
        'rows': int(len(df)),
        'columns': int(len(df.columns)),
        'fields': fields,
    }

    def iter_rows() -> Iterable[dict[str, str]]:
        safe = df.fillna('')
        for _, row in safe.iterrows():
            if detected:
                yield {kind: _stable_cell(row.get(detected[kind], '')) for kind in fields}
            else:
                yield {normalize_text(col): _stable_cell(row.get(col, '')) for col in df.columns}

    digest = _hash_json_rows(iter_rows(), header=header)
    signature = f'{SIGNATURE_VERSION}:identity:{len(df)}x{len(df.columns)}:{digest}'
    return DatasetSignature(signature, int(len(df)), int(len(df.columns)), fields, 'identity')


def category_values_signature(df: pd.DataFrame, category_column: str | None = None, *, context: str = '') -> str:
    """Assina todos os valores da categoria, sem depender do nome literal da coluna."""
    if not _valid_df(df):
        return f'{SIGNATURE_VERSION}:category:empty'
    col = category_column
    if not col or col not in df.columns:
        col = detect_dataset_columns(df).get('categoria')
    if not col or col not in df.columns:
        return f'{SIGNATURE_VERSION}:category:{len(df)}:no-category-column'
    header = {'version': SIGNATURE_VERSION, 'mode': 'category', 'context': str(context or ''), 'rows': int(len(df))}

    def iter_rows() -> Iterable[dict[str, str]]:
        for value in df[col].fillna('').astype(str):
            yield {'categoria': _stable_cell(value)}

    digest = _hash_json_rows(iter_rows(), header=header)
    return f'{SIGNATURE_VERSION}:category:{len(df)}:{digest}'


def signatures_match(left: object, right: object) -> bool:
    return bool(str(left or '').strip()) and str(left or '').strip() == str(right or '').strip()


__all__ = [
    'DatasetSignature',
    'FINAL_DOWNLOAD_SIGNATURE_KEY',
    'GLOBAL_DECISION_DATASET_SIGNATURE_KEY',
    'GLOBAL_FINAL_DATASET_SIGNATURE_KEY',
    'GLOBAL_LIVE_DATASET_SIGNATURE_KEY',
    'category_values_signature',
    'dataframe_identity_signature',
    'dataframe_table_signature',
    'detect_dataset_columns',
    'normalize_text',
    'signatures_match',
]
