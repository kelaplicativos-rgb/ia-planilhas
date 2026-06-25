from __future__ import annotations

from typing import Any

import pandas as pd

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.category_intelligence import (
    PROVISIONAL_CATEGORY,
    REVIEW_CATEGORY,
    apply_category_suggestions,
    classify_dataframe,
    detect_category_column,
    ensure_category_column,
    normalize_text,
    suggest_category_for_product,
)

RESPONSIBLE_FILE = 'bling_app_zero/core/category_finalizer.py'
CATEGORY_CONFIDENCE_MIN = 0.80

FINAL_CATEGORY_BLOCKLIST = {
    '',
    'nan',
    'none',
    'null',
    '<na>',
    'na',
    'n/a',
    'sem categoria',
    'revisar manualmente',
    'revisao manual',
}

OLD_CATEGORY_ALIASES = {
    'microfone': 'Microfones',
    'microfones': 'Microfones',
    'radios am fm': 'Rádios AM e FM',
    'radios am e fm': 'Rádios AM e FM',
    'radio am fm': 'Rádios AM e FM',
    'radio am e fm': 'Rádios AM e FM',
    'power bank': 'Power banks',
    'power banks': 'Power banks',
}

DESCRIPTION_COLS = (
    'Descrição do Produto no Fornecedor', 'Descrição completa', 'Descricao completa',
    'Descrição Complementar', 'Descrição complementar', 'Descricao Complementar', 'Descricao complementar',
    'Descrição Curta', 'Descricao Curta', 'Informações Adicionais', 'Informacoes Adicionais',
    'Características', 'Característica', 'Ficha técnica', 'Ficha tecnica', 'Observações', 'Observacoes',
)
TITLE_COLS = ('Descrição', 'Descricao', 'Nome', 'Nome do produto', 'Produto', 'Título', 'Titulo', 'name', 'nome')
CONTEXT_COLS = ('Categoria origem', 'Grupo de produtos', 'Link Externo', 'URL', 'url', 'Marca', 'Código', 'SKU')


def _filled(value: object) -> bool:
    try:
        if value is None or pd.isna(value):
            return False
    except Exception:
        pass
    return str(value).strip() != ''


def _join_row(row: pd.Series, columns: tuple[str, ...]) -> str:
    values: list[str] = []
    for col in columns:
        if col in row.index and _filled(row.get(col)):
            values.append(str(row.get(col)))
    return normalize_text(' '.join(values))


def _current_category_bad(value: object) -> bool:
    norm = normalize_text(value)
    if norm in FINAL_CATEGORY_BLOCKLIST:
        return True
    if norm in {'cabos', 'antenas', 'diversos', 'geral', 'outros', 'informatica'}:
        return True
    return False


def _force_from_evidence(description: str, title: str, context: str) -> tuple[str, float, str]:
    full = normalize_text(f'{description} {title} {context}')
    title_only = normalize_text(title)
    desc_first = normalize_text(f'{description} {context}')

    # Power bank precisa vencer a regra genérica de carregador.
    if any(token in full for token in ('power bank', 'carregador portatil', 'bateria externa')) or bool(__import__('re').search(r'\b\d{4,6}\s?mah\b', full)):
        if not any(token in full for token in ('carregador de tomada', 'fonte carregador', 'tomada usb', 'carregador veicular')):
            return 'Power banks', 0.97, 'evidência forte de power bank/bateria externa antes de carregador genérico'

    # Cabos técnicos: nunca deixar como Cabos genérico quando há subtipo.
    if 'cabo' in full:
        if any(token in full for token in ('rj45', 'cat5e', 'cat6', 'cat6a', 'cat7', 'ethernet', 'patch cord', 'lan ', ' utp', 'rede internet')):
            return 'Cabos de rede', 0.97, 'evidência RJ45/CAT/Ethernet/LAN'
        if any(token in full for token in ('usb c', 'usb-c', 'tipo c', 'type c', 'micro usb', 'lightning', 'iphone', 'android', 'cabo de dados')):
            return 'Cabos USB e dados', 0.96, 'evidência USB/tipo C/lightning/dados'
        if any(token in full for token in ('cabo de forca', 'forca tripolar', 'cabo energia', 'alimentacao ac', '10a', '20a')):
            return 'Cabos de energia', 0.95, 'evidência cabo de força/energia'
        if any(token in full for token in ('p2', 'p10', 'rca', 'xlr', 'auxiliar', 'audio estereo')):
            return 'Cabos de áudio', 0.95, 'evidência cabo de áudio'
        if any(token in full for token in ('hdmi', 'vga', 'displayport', 'cabo av')):
            return 'Cabos HDMI e vídeo', 0.94, 'evidência cabo de vídeo/HDMI'

    # Antenas técnicas: nunca deixar como Antenas genérico quando há subtipo.
    if 'antena' in full:
        if any(token in full for token in ('wifi', 'wi fi', 'wireless', 'roteador', 'rp sma', 'sma ', 'dbi', '2 4ghz', '5ghz')):
            return 'Antenas Wi-Fi', 0.96, 'evidência antena Wi-Fi/roteador/dBi/SMA'
        if any(token in full for token in ('tv digital', 'televisao', 'hdtv', 'uhf', 'vhf', 'sinal digital')):
            return 'Antenas para TV', 0.95, 'evidência antena TV/digital/UHF/VHF'

    # Rádio x caixa de som: produto principal pela descrição, depois título.
    if any(token in desc_first for token in ('radio portatil', 'radio am fm', 'radio am e fm', 'antena telescopica')):
        if not any(token in desc_first for token in ('caixa de som', 'caixa amplificada', 'speaker')):
            return 'Rádios AM e FM', 0.96, 'descrição indica rádio como produto principal'
    if any(token in desc_first for token in ('caixa de som', 'caixa amplificada', 'speaker', 'boombox')):
        return 'Caixas de som', 0.95, 'descrição indica caixa de som como produto principal'
    if title_only.startswith('radio') or title_only.startswith('mini radio'):
        return 'Rádios AM e FM', 0.93, 'título indica rádio como produto principal'

    if any(token in full for token in ('fone de ouvido', 'fone intra auricular', 'headset', 'headphone', 'earphone', 'earbuds')):
        return 'Fones de ouvido', 0.95, 'evidência fone/headset'
    if any(token in full for token in ('microfone', 'microfone sem fio', 'lapela')):
        return 'Microfones', 0.94, 'evidência microfone'
    if any(token in full for token in ('carregador turbo', 'carregador de tomada', 'fonte carregador', 'tomada usb', 'carregador veicular', '20w', '30w')) and 'power bank' not in full:
        return 'Carregadores para celular', 0.92, 'evidência carregador/fonte/tomada'

    return '', 0.0, ''


def finalize_categories_for_output(
    df: pd.DataFrame,
    *,
    context: str = 'final_output',
    confidence_min: float = CATEGORY_CONFIDENCE_MIN,
    fallback_unclassified: bool = True,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Aplica a última trava de categoria antes de CSV/API.

    Esta função não confia em estado intermediário. Ela relê descrição completa,
    descrição complementar, curta, ficha técnica, título e contexto, corrige a
    categoria final e evita saída com categorias genéricas ou vazias.
    """
    if not isinstance(df, pd.DataFrame) or df.empty:
        return df, {'rows': 0, 'applied': 0, 'forced': 0, 'fallback': 0, 'context': context}

    result, category_col = ensure_category_column(df.copy().fillna(''), preferred='Categoria do produto')
    analyzed, stats = classify_dataframe(result)
    corrected, applied = apply_category_suggestions(
        analyzed,
        confidence_min=confidence_min,
        keep_helper_columns=False,
        fallback_unclassified=fallback_unclassified,
    )
    corrected, category_col = ensure_category_column(corrected.fillna(''), preferred='Categoria do produto')

    forced = 0
    fallback = 0
    alias_fixed = 0
    reasons: list[dict[str, Any]] = []

    for idx, row in corrected.iterrows():
        current = str(corrected.at[idx, category_col]).strip()
        norm_current = normalize_text(current)
        if norm_current in OLD_CATEGORY_ALIASES:
            fixed = OLD_CATEGORY_ALIASES[norm_current]
            if fixed != current:
                corrected.at[idx, category_col] = fixed
                current = fixed
                norm_current = normalize_text(fixed)
                alias_fixed += 1

        description = _join_row(row, DESCRIPTION_COLS)
        title = _join_row(row, TITLE_COLS)
        context_text = _join_row(row, CONTEXT_COLS)
        forced_category, confidence, reason = _force_from_evidence(description, title, context_text)

        if forced_category and (forced_category != current or _current_category_bad(current)):
            corrected.at[idx, category_col] = forced_category
            forced += 1
            if len(reasons) < 60:
                reasons.append({'row': int(idx) + 1, 'from': current, 'to': forced_category, 'confidence': confidence, 'reason': reason})
            continue

        if _current_category_bad(current):
            suggestion = suggest_category_for_product(title, description=description, current_category='')
            if suggestion.category and suggestion.category != REVIEW_CATEGORY and suggestion.confidence >= confidence_min:
                corrected.at[idx, category_col] = suggestion.category
                forced += 1
                if len(reasons) < 60:
                    reasons.append({'row': int(idx) + 1, 'from': current, 'to': suggestion.category, 'confidence': suggestion.confidence, 'reason': suggestion.reason})
            elif fallback_unclassified:
                corrected.at[idx, category_col] = PROVISIONAL_CATEGORY
                fallback += 1

    final_empty = 0
    for idx, value in corrected[category_col].fillna('').astype(str).items():
        if _current_category_bad(value):
            corrected.at[idx, category_col] = PROVISIONAL_CATEGORY
            final_empty += 1

    report = {
        'rows': int(len(corrected)),
        'category_column': category_col,
        'applied': int(applied),
        'forced': int(forced),
        'alias_fixed': int(alias_fixed),
        'fallback_unclassified': int(fallback + final_empty),
        'stats': dict(stats or {}),
        'context': context,
        'sample_reasons': reasons,
        'responsible_file': RESPONSIBLE_FILE,
    }
    try:
        add_audit_event('category_finalizer_applied', area='CATEGORIAS', status='OK', details=report)
    except Exception:
        pass
    return corrected, report


__all__ = ['finalize_categories_for_output']
