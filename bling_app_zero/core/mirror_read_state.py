from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import pandas as pd

RESPONSIBLE_FILE = 'bling_app_zero/core/mirror_read_state.py'


@dataclass(frozen=True)
class MirrorReadState:
    ok: bool
    total_rows: int
    ready_rows: int
    review_rows: int
    empty_rows: int
    message: str
    responsible_file: str = RESPONSIBLE_FILE

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def summarize_read_state(df: pd.DataFrame, *, review_only: bool = False) -> MirrorReadState:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return MirrorReadState(False, 0, 0, 0, 0, 'Nenhuma linha lida no ciclo monitorado.')
    total = int(len(df))
    empty = 0
    ready = 0
    review = 0
    for _index, row in df.fillna('').iterrows():
        values = [str(value or '').strip() for value in row.tolist()]
        has_content = any(values)
        if not has_content:
            empty += 1
        elif review_only:
            review += 1
        else:
            ready += 1
    return MirrorReadState(True, total, ready, review, empty, f'Resumo local: {ready} pronta(s), {review} em revisão, {empty} vazia(s).')


__all__ = ['MirrorReadState', 'summarize_read_state']
