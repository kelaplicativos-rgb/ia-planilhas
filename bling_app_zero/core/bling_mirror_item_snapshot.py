from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from typing import Any

import pandas as pd

RESPONSIBLE_FILE = 'bling_app_zero/core/bling_mirror_item_snapshot.py'
IDENTITY_COLUMNS = ('id', 'id produto', 'id_produto', 'id_bling', 'codigo', 'código', 'sku', 'gtin', 'ean', 'url')
QUANTITY_COLUMNS = ('estoque', 'quantidade', 'saldo', 'balanco', 'balanço', 'qtd', 'qtde')
NAME_COLUMNS = ('nome', 'produto', 'descricao', 'descrição', 'titulo', 'título')
PRICE_COLUMNS = ('preco', 'preço', 'valor', 'valor unitario', 'valor unitário')
MAX_SNAPSHOT_ITEMS = 1500


@dataclass(frozen=True)
class MirrorItemSnapshot:
    ok: bool
    total_rows: int
    items_total: int
    missing_identity: int
    items: tuple[dict[str, Any], ...]
    responsible_file: str = RESPONSIBLE_FILE

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data['items'] = [dict(item) for item in self.items]
        return data


def _norm(value: object) -> str:
    text = str(value or '').strip().lower()
    replacements = {
        'ã': 'a', 'á': 'a', 'à': 'a', 'â': 'a',
        'é': 'e', 'ê': 'e', 'í': 'i',
        'ó': 'o', 'ô': 'o', 'õ': 'o', 'ú': 'u',
        'ç': 'c',
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return ' '.join(text.replace('_', ' ').replace('-', ' ').split())


def _column_index(columns: list[str]) -> dict[str, str]:
    return {_norm(column): column for column in columns}


def _first_value(row: pd.Series, wanted: tuple[str, ...], index: dict[str, str]) -> str:
    for name in wanted:
        column = index.get(_norm(name))
        if column is not None:
            value = str(row.get(column, '') or '').strip()
            if value:
                return value
    return ''


def _signature(identity: str, quantity: str, name: str, price: str) -> str:
    raw = '|'.join([identity.strip().lower(), quantity.strip().lower(), name.strip().lower(), price.strip().lower()])
    return hashlib.sha1(raw.encode('utf-8', errors='ignore')).hexdigest()


def build_item_snapshot(df: pd.DataFrame, *, limit: int = MAX_SNAPSHOT_ITEMS) -> MirrorItemSnapshot:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return MirrorItemSnapshot(False, 0, 0, 0, tuple())
    columns = [str(column) for column in df.columns]
    index = _column_index(columns)
    items: list[dict[str, Any]] = []
    missing = 0
    max_items = max(1, min(int(limit or MAX_SNAPSHOT_ITEMS), MAX_SNAPSHOT_ITEMS))
    for row_number, (_idx, row) in enumerate(df.fillna('').iterrows(), start=1):
        identity = _first_value(row, IDENTITY_COLUMNS, index)
        if not identity:
            missing += 1
            continue
        quantity = _first_value(row, QUANTITY_COLUMNS, index)
        name = _first_value(row, NAME_COLUMNS, index)
        price = _first_value(row, PRICE_COLUMNS, index)
        item = {
            'row_number': row_number,
            'identity': identity,
            'quantity': quantity,
            'name': name[:180],
            'price': price,
            'signature': _signature(identity, quantity, name, price),
        }
        items.append(item)
        if len(items) >= max_items:
            break
    return MirrorItemSnapshot(
        ok=bool(items),
        total_rows=int(len(df)),
        items_total=len(items),
        missing_identity=missing,
        items=tuple(items),
    )


__all__ = ['MAX_SNAPSHOT_ITEMS', 'MirrorItemSnapshot', 'build_item_snapshot']
