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

# Termos de produto principal. A ordem na decisão é intencional:
# power bank -> rádio/caixa -> fone -> microfone -> carregador -> cabo.
# Isso evita transformar recurso/conexão em categoria principal.
FONE_PATTERNS = (
    r'\bfone\b', r'\bfone de ouvido\b', r'\bfone gamer\b', r'\bfone bluetooth\b',
    r'\bfone bt\b', r'\bfone com fio\b', r'\bheadset\b', r'\bheadphone\b',
    r'\bearphone\b', r'\bearbuds\b', r'\bintra auricular\b',
)
MICROPHONE_PATTERNS = (r'\bmicrofone\b', r'\bmicrofone sem fio\b', r'\blapela\b', r'\bmicrofone lapela\b')
CHARGER_PATTERNS = (
    r'\bcarregador turbo\b', r'\bcarregador de tomada\b', r'\bfonte carregador\b',
    r'\btomada usb\b', r'\bcarregador veicular\b', r'\badaptador de tomada\b',
)
POWER_BANK_PATTERNS = (r'\bpower bank\b', r'\bcarregador portatil\b', r'\bbateria externa\b')
BATTERY_ONLY_PATTERNS = (
    r'\bpilha(?:s)?\b', r'\baa\b', r'\baaa\b', r'\bbateria recarregavel\b',
    r'\bbaterias recarregaveis\b', r'\bbateria 9v\b', r'\bcr2032\b', r'\blr44\b',
)
RADIO_MAIN_PATTERNS = (
    r'\bradio portatil\b', r'\bradio am fm\b', r'\bradio am e fm\b',
    r'\bantena telescopica\b', r'\btoca cd\b',
)
SPEAKER_MAIN_PATTERNS = (r'\bcaixa de som\b', r'\bcaixa amplificada\b', r'\bspeaker\b', r'\bboombox\b')


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


def _has_pattern(text: str, patterns: tuple[str, ...]) -> bool:
    return any(re.search(pattern, text) for pattern in patterns)


def _starts_with_pattern(text: str, patterns: tuple[str, ...]) -> bool:
    return any(re.search(r'^' + pattern.lstrip('\\b'), text) for pattern in patterns)


def _has_mah(text: str) -> bool:
    return bool(re.search(r'\b\d{3,6}\s?mah\b', text))


def _looks_like_battery_only(full: str) -> bool:
    return _has_pattern(full, BATTERY_ONLY_PATTERNS)


def _looks_like_power_bank(full: str) -> bool:
    # mAh sozinho não basta. Pilha AA/AAA 2700mAh continua Pilhas e baterias.
    return _has_pattern(full, POWER_BANK_PATTERNS) and not _looks_like_battery_only(full)


def _looks_like_wall_or_vehicle_charger(full: str) -> bool:
    return _has_pattern(full, CHARGER_PATTERNS) or bool(re.search(r'\b(?:20w|25w|30w|33w|45w|65w)\b', full))


def _principal_is_cable(title: str, description: str) -> bool:
    text = normalize_text(f'{title} {description}')
    if re.search(r'^(?:cabo|kit cabo|extensor cabo|cabo adaptador)\b', title):
        return True
    if re.search(r'\bproduto principal\s*:?\s*cabo\b', text):
        return True
    # Fora do título, só considerar cabo principal quando a palavra cabo aparece
    # grudada a um subtipo técnico claro; não por USB/Tipo C solto.
    return bool(re.search(
        r'\bcabo\s+(?:de\s+)?(?:rede|rj\s?45|cat5e|cat6|cat6a|cat7|usb|tipo c|type c|lightning|iphone|v8|micro usb|hdmi|vga|displayport|forca|energia|p2|p10|rca|xlr|audio|auxiliar)\b',
        text,
    ))


def _principal_is_not_cable(full: str, title: str, description: str) -> bool:
    # USB/Tipo C, entrada USB ou cabo incluso são recursos comuns de fone,
    # carregador, rádio e caixa. Nesses casos não podem transformar o produto em cabo.
    if _has_pattern(full, FONE_PATTERNS + MICROPHONE_PATTERNS + SPEAKER_MAIN_PATTERNS + RADIO_MAIN_PATTERNS):
        return True
    if _looks_like_wall_or_vehicle_charger(full) and not _principal_is_cable(title, description):
        return True
    return False


def _force_from_evidence(description: str, title: str, context: str) -> tuple[str, float, str]:
    full = normalize_text(f'{description} {title} {context}')
    title_only = normalize_text(title)
    desc_first = normalize_text(f'{description} {context}')

    # 1) Power bank precisa vencer carregador genérico, mas mAh sozinho não basta.
    if _looks_like_power_bank(full):
        if not _has_pattern(full, (r'\bcarregador de tomada\b', r'\bfonte carregador\b', r'\btomada usb\b', r'\bcarregador veicular\b')):
            extra = ' com mAh' if _has_mah(full) else ''
            return 'Power banks', 0.97, f'produto principal é power bank/bateria externa{extra}, antes de carregador genérico'

    # 2) Rádio e caixa antes de fone/microfone, porque podem ter entrada de fone
    # ou microfone incluso sem mudar o produto principal.
    if _has_pattern(desc_first, RADIO_MAIN_PATTERNS):
        if not _has_pattern(desc_first, SPEAKER_MAIN_PATTERNS):
            return 'Rádios AM e FM', 0.96, 'descrição indica rádio como produto principal'
    if title_only.startswith('radio') or title_only.startswith('mini radio'):
        return 'Rádios AM e FM', 0.94, 'título indica rádio como produto principal'
    if _has_pattern(desc_first, SPEAKER_MAIN_PATTERNS) or _has_pattern(title_only, SPEAKER_MAIN_PATTERNS):
        return 'Caixas de som', 0.95, 'produto principal é caixa de som; microfone/rádio pode ser recurso'

    # 3) Produto principal de áudio antes de cabo/USB/Tipo C.
    if _has_pattern(full, FONE_PATTERNS):
        if not (title_only.startswith('cabo') and _has_pattern(full, (r'\bp2\b', r'\bp10\b', r'\brca\b', r'\bxlr\b', r'\baudio\b', r'\bauxiliar\b'))):
            return 'Fones de ouvido', 0.96, 'produto principal é fone/headset; USB/Tipo C é recurso/conexão'
    if _has_pattern(full, MICROPHONE_PATTERNS):
        if not (title_only.startswith('cabo') and _has_pattern(full, (r'\bp2\b', r'\bp10\b', r'\bxlr\b', r'\baudio\b', r'\bauxiliar\b'))):
            return 'Microfones', 0.95, 'produto principal é microfone; cabo/conexão é acessório ou interface'

    # 4) Carregador de tomada/veicular/fonte antes de cabo. Power bank já foi tratado.
    if _looks_like_wall_or_vehicle_charger(full) and not _looks_like_power_bank(full):
        if not title_only.startswith('cabo'):
            return 'Carregadores para celular', 0.94, 'produto principal é carregador/fonte/tomada; USB/Tipo C é porta/conexão'

    # 5) Cabos técnicos somente quando o produto principal for cabo.
    principal_cable = _principal_is_cable(title_only, desc_first)
    if principal_cable and not _principal_is_not_cable(full, title_only, desc_first):
        if _has_pattern(full, (r'\brj\s?45\b', r'\bcat5e\b', r'\bcat6\b', r'\bcat6a\b', r'\bcat7\b', r'\bethernet\b', r'\bpatch cord\b', r'\blan\b', r'\butp\b', r'\brede internet\b')):
            return 'Cabos de rede', 0.97, 'produto principal é cabo de rede por evidência RJ45/CAT/Ethernet/LAN'
        if _has_pattern(full, (r'\busb c\b', r'\busb\s?c\b', r'\btipo c\b', r'\btype c\b', r'\bmicro usb\b', r'\blightning\b', r'\biphone\b', r'\bandroid\b', r'\bcabo de dados\b', r'\bv8\b')):
            return 'Cabos USB e dados', 0.96, 'produto principal é cabo USB/dados por evidência Tipo C/Lightning/Micro USB'
        if _has_pattern(full, (r'\bcabo de forca\b', r'\bforca tripolar\b', r'\bcabo energia\b', r'\balimentacao ac\b', r'\b10a\b', r'\b20a\b')):
            return 'Cabos de energia', 0.95, 'produto principal é cabo de força/energia'
        if _has_pattern(full, (r'\bp2\b', r'\bp10\b', r'\brca\b', r'\bxlr\b', r'\bauxiliar\b', r'\baudio estereo\b')):
            return 'Cabos de áudio', 0.95, 'produto principal é cabo de áudio'
        if _has_pattern(full, (r'\bhdmi\b', r'\bvga\b', r'\bdisplayport\b', r'\bcabo av\b')):
            return 'Cabos HDMI e vídeo', 0.94, 'produto principal é cabo de vídeo/HDMI'

    # 6) Antenas técnicas: não deixar como Antenas genérico quando há subtipo.
    if re.search(r'\bantena\b', full):
        if _has_pattern(full, (r'\bwifi\b', r'\bwi fi\b', r'\bwireless\b', r'\broteador\b', r'\brp sma\b', r'\bsma\b', r'\bdbi\b', r'\b2 4ghz\b', r'\b5ghz\b')):
            return 'Antenas Wi-Fi', 0.96, 'evidência antena Wi-Fi/roteador/dBi/SMA'
        if _has_pattern(full, (r'\btv digital\b', r'\btelevisao\b', r'\bhdtv\b', r'\buhf\b', r'\bvhf\b', r'\bsinal digital\b')):
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
