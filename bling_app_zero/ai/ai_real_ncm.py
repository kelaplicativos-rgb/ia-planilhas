from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from bling_app_zero.core.text import clean_cell, normalize_key


@dataclass(frozen=True)
class NCMSuggestion:
    row_index: int
    product_name: str
    suggested_ncm: str
    confidence: str
    reason: str


NCM_RULES: tuple[tuple[tuple[str, ...], str, str], ...] = (
    (('cabo', 'usb', 'hdmi', 'adaptador', 'carregador', 'fonte'), '85444200', 'acessório/cabo elétrico ou eletrônico'),
    (('fone', 'headset', 'caixa de som', 'alto falante', 'speaker'), '85183000', 'áudio/fone ou alto-falante'),
    (('teclado', 'mouse', 'controle gamer', 'joystick'), '8471605', 'periférico de informática'),
    (('camera', 'câmera', 'webcam', 'filmadora'), '85258029', 'câmera ou equipamento de captura de imagem'),
    (('smartwatch', 'relogio inteligente', 'relógio inteligente'), '85176259', 'dispositivo eletrônico de comunicação'),
    (('pelicula', 'película', 'capa', 'case'), '39269090', 'acessório plástico'),
)


def _columns(df: pd.DataFrame | None) -> list[str]:
    return [str(column) for column in df.columns] if isinstance(df, pd.DataFrame) else []


def _key(value: object) -> str:
    return normalize_key(str(value or '')).replace(' ', '_')


def _compact(value: object) -> str:
    return ' '.join(clean_cell(value).split())


def _is_ncm_col(column: object) -> bool:
    key = _key(column)
    return key == 'ncm' or 'codigo_ncm' in key or 'classificacao_fiscal' in key or 'classificação_fiscal' in key


def _is_name_col(column: object) -> bool:
    key = _key(column)
    return key in {'nome', 'produto', 'titulo', 'título', 'descricao', 'descrição'} or key.startswith('nome_') or key.startswith('produto_')


def _best_col(df: pd.DataFrame, predicate) -> str:
    for column in _columns(df):
        if predicate(column):
            return column
    return ''


def _valid_ncm(value: object) -> str:
    digits = ''.join(ch for ch in str(value or '') if ch.isdigit())
    return digits if len(digits) in {7, 8} else ''


def _suggest_for_name(name: str) -> tuple[str, str, str]:
    normalized = normalize_key(name)
    for terms, ncm, reason in NCM_RULES:
        if any(normalize_key(term) in normalized for term in terms):
            return ncm, 'média', reason
    return '', '', ''


def build_ncm_suggestions(df_final_universal: pd.DataFrame | None) -> list[NCMSuggestion]:
    if not isinstance(df_final_universal, pd.DataFrame) or df_final_universal.empty:
        return []
    ncm_col = _best_col(df_final_universal, _is_ncm_col)
    name_col = _best_col(df_final_universal, _is_name_col)
    if not ncm_col or not name_col:
        return []

    suggestions: list[NCMSuggestion] = []
    for index, row in df_final_universal.iterrows():
        current_ncm = _valid_ncm(row.get(ncm_col, ''))
        if current_ncm:
            continue
        name = _compact(row.get(name_col, ''))
        if not name:
            continue
        ncm, confidence, reason = _suggest_for_name(name)
        if ncm:
            suggestions.append(NCMSuggestion(int(index), name[:120], ncm, confidence, reason))
    return suggestions


def apply_reviewed_ncms(df_final_universal: pd.DataFrame | None, reviewed: dict[int, str]) -> pd.DataFrame:
    if not isinstance(df_final_universal, pd.DataFrame) or df_final_universal.empty:
        return pd.DataFrame()
    out = df_final_universal.copy().fillna('')
    ncm_col = _best_col(out, _is_ncm_col)
    if not ncm_col:
        return out
    for row_index, ncm in reviewed.items():
        safe = _valid_ncm(ncm)
        if safe and row_index in out.index:
            out.at[row_index, ncm_col] = safe
    return out.fillna('')


__all__ = ['NCMSuggestion', 'apply_reviewed_ncms', 'build_ncm_suggestions']