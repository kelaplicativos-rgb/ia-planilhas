from __future__ import annotations

import re
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


# Termos de produto principal. Eles são avaliados antes de cabo/USB para evitar
# erro como: "Fone Tipo C" -> cabo, ou "Carregador Tipo C" -> cabo.
FONE_TERMS = ('fone de ouvido', 'fone intra auricular', 'fone bluetooth', 'headset', 'headphone', 'earphone', 'earbuds')
MICROPHONE_TERMS = ('microfone', 'microfone sem fio', 'lapela', 'microfone lapela')
CHARGER_TERMS = ('carregador turbo', 'carregador de tomada', 'fonte carregador', 'tomada usb', 'carregador veicular', 'adaptador de tomada')
POWER_BANK_TERMS = ('power bank', 'carregador portatil', 'bateria externa')
RADIO_MAIN_TERMS = ('radio portatil', 'radio am fm', 'radio am e fm', 'antena telescopica')
SPEAKER_MAIN_TERMS = ('caixa de som', 'caixa amplificada', 'speaker', 'boombox')


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


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def _title_starts_as(text: str, terms: tuple[str, ...]) -> bool:
    return any(text.startswith(term) for term in terms)


def _looks_like_power_bank(full: str) -> bool:
    return _contains_any(full, POWER_BANK_TERMS) or bool(re.search(r'\b\d{4,6}\s?mah\b', full))


def _looks_like_wall_or_vehicle_charger(full: str) -> bool:
    return _contains_any(full, CHARGER_TERMS) or bool(re.search(r'\b(?:20w|25w|30w|33w|45w|65w)\b', full))


def _principal_is_cable(title: str, description: str) -> bool:
    text = normalize_text(f'{title} {description}')
    if re.search(r'^(?:cabo|kit cabo|extensor cabo|cabo adaptador)\b', title):
        return True
    if re.search(r'\bproduto principal\s*:?\s*cabo\b', text):
        return True
    if re.search(r'\bcabo\s+(?:de\s+)?(?:rede|rj45|cat5e|cat6|cat6a|cat7|usb|tipo c|type c|lightning|iphone|v8|micro usb|hdmi|vga|displayport|forca|energia|p2|p10|rca|xlr|audio|auxiliar)\b', text):
        return True
    return False


def _principal_is_not_cable(full: str, title: str, description: str) -> bool:
    # USB/Tipo C, entrada USB ou cabo incluso são recursos comuns de fone,
    # carregador, rádio e caixa. Nesses casos não podem transformar o produto em cabo.
    if _contains_any(full, FONE_TERMS + MICROPHONE_TERMS + SPEAKER_MAIN_TERMS + RADIO_MAIN_TERMS):
        return True
    if _looks_like_wall_or_vehicle_charger(full) and not _principal_is_cable(title, description):
        return True
    return False


def _force_from_evidence(description: str, title: str, context: str) -> tuple[str, float, str]:
    full = normalize_text(f'{description} {title} {context}')
    title_only = normalize_text(title)
    desc_first = normalize_text(f'{description} {context}')

    # 1) Power bank precisa vencer carregador genérico.
    if _looks_like_power_bank(full):
        if not any(token in full for token in ('carregador de tomada', 'fonte carregador', 'tomada usb', 'carregador veicular')):
            return 'Power banks', 0.97, 'produto principal é power bank/bateria externa, antes de carregador genérico'

    # 2) Produto principal de áudio antes de cabo/USB/Tipo C.
    if _contains_any(full, FONE_TERMS):
        if not (title_only.startswith('cabo') and _contains_any(full, ('p2', 'p10', 'rca', 'xlr', 'audio', 'auxiliar'))):
            return 'Fones de ouvido', 0.96, 'produto principal é fone/headset; USB/Tipo C é recurso/conexão'
    if _contains_any(full, MICROPHONE_TERMS):
        if not (title_only.startswith('cabo') and _contains_any(full, ('p2', 'p10', 'xlr', 'audio', 'auxiliar'))):
            return 'Microfones', 0.95, 'produto principal é microfone; cabo/conexão é acessório ou interface'

    # 3) Carregador de tomada/veicular/fonte antes de cabo. Power bank já foi tratado.
    if _looks_like_wall_or_vehicle_charger(full) and not _looks_like_power_bank(full):
        if not title_only.startswith('cabo'):
            return 'Carregadores para celular', 0.94, 'produto principal é carregador/fonte/tomada; USB/Tipo C é porta/conexão'

    # 4) Rádio x caixa de som: produto principal pela descrição, depois título.
    if _contains_any(desc_first, RADIO_MAIN_TERMS):
        if not _contains_any(desc_first, SPEAKER_MAIN_TERMS):
            return 'Rádios AM e FM', 0.96, 'descrição indica rádio como produto principal'
    if _contains_any(desc_first, SPEAKER_MAIN_TERMS):
        return 'Caixas de som', 0.95, 'descrição indica caixa de som como produto principal'
    if title_only.startswith('radio') or title_only.startswith('mini radio'):
        return 'Rádios AM e FM', 0.93, 'título indica rádio como produto principal'

    # 5) Cabos técnicos somente quando o produto principal for cabo.
    principal_cable = _principal_is_cable(title_only, desc_first)
    if principal_cable and not _principal_is_not_cable(full, title_only, desc_first):
        if any(token in full for token in ('rj45', 'cat5e', 'cat6', 'cat6a', 'cat7', 'ethernet', 'patch cord', 'lan ', ' utp', 'rede internet')):
            return 'Cabos de rede', 0.97, 'produto principal é cabo de rede por evidência RJ45/CAT/Ethernet/LAN'
        if any(token in full for token in ('usb c', 'usb-c', 'tipo c', 'type c', 'micro usb', 'lightning', 'iphone', 'android', 'cabo de dados', 'v8')):
            return 'Cabos USB e dados', 0.96, 'produto principal é cabo USB/dados por evidência Tipo C/Lightning/Micro USB'
        if any(token in full for token in ('cabo de forca', 'forca tripolar', 'cabo energia', 'alimentacao ac', '10a', '20a')):
            return 'Cabos de energia', 0.95, 'produto principal é cabo de força/energia'
        if any(token in full for token in ('p2', 'p10', 'rca', 'xlr', 'auxiliar', 'audio estereo')):
            return 'Cabos de áudio', 0.95, 'produto principal é cabo de áudio'
        if any(token in full for token in ('hdmi', 'vga', 'displayport', 'cabo av')):
            return 'Cabos HDMI e vídeo', 0.94, 'produto principal é cabo de vídeo/HDMI'

    # 6) Antenas técnicas: não deixar como Antenas genérico quando há subtipo.
    if 'antena' in full:
        if any(token in full for token in ('wifi', 'wi fi', 'wireless', 'roteador', 'rp sma', 'sma ', 'dbi', '2 4ghz', '5ghz')):
            return 'Antenas Wi-Fi', 0.96, 'evidência antena Wi-Fi/roteador/dBi/SMA'
        if any(token in full for token in ('tv digital', 'televisao', 'hdtv', 'uhf', 'vhf', 'sinal digital')):
            return 'Antenas para TV', 0.95, 'evidência antena TV/digital/UHF/VHF'

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
