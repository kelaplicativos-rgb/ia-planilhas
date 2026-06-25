from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable, Sequence

import pandas as pd

from bling_app_zero.core.category_intelligence import (
    DEFAULT_CATEGORY_CATALOG,
    PROVISIONAL_CATEGORY,
    canonicalize_category,
    normalize_text,
)

RESPONSIBLE_FILE = 'bling_app_zero/core/category_guard.py'

GENERIC_OR_INVALID_CATEGORIES = {
    '', 'nan', 'none', 'null', '<na>', 'na', 'n/a',
    'sem categoria', 'revisar manualmente', 'revisao manual',
    'diversos', 'geral', 'outros', 'informatica',
    'produtos nao classificados', 'produto nao classificado',
    'nao classificados', 'nao classificado',
}

CATEGORY_FAMILIES = {
    'Fones de ouvido', 'Carregadores para celular', 'Controles para televisão',
    'Caixas de som', 'Máquinas para corte de cabelo', 'Cabos de rede',
    'Cabos USB e dados', 'Cabos de energia', 'Cabos de áudio',
    'Cabos HDMI e vídeo', 'Mouses', 'Pen drives', 'Pilhas e baterias',
    'Cartões de memória', 'Antenas para TV', 'Antenas Wi-Fi', 'Fontes',
    'Rádios AM e FM', 'Calculadoras', 'Conversores', 'Câmeras',
    'Telefones fixos', 'Adaptadores', 'Power banks', 'Microfones',
    'Redes e internet',
}


@dataclass(frozen=True)
class CategoryDecision:
    accepted_category: str
    suggested_category: str
    confidence: float
    status: str
    reason: str


@dataclass(frozen=True)
class GuardRule:
    category: str
    confidence: float
    reason: str
    positives: tuple[str, ...]
    negatives: tuple[str, ...] = ()
    title_bonus: tuple[str, ...] = ()


def _hits(text: str, patterns: Iterable[str]) -> list[str]:
    return [pattern for pattern in patterns if re.search(pattern, text)]


def _title_score(title: str, patterns: Sequence[str]) -> int:
    return sum(1 for pattern in patterns if title and re.search(pattern, title))


def _canonical(value: object) -> str:
    canonical, _changed, _reason = canonicalize_category(value, DEFAULT_CATEGORY_CATALOG)
    return canonical


def _current_is_generic(value: object) -> bool:
    return normalize_text(value) in GENERIC_OR_INVALID_CATEGORIES


RULES: tuple[GuardRule, ...] = (
    GuardRule('Mouses', 0.95, 'produto principal é mouse', (r'\bmouse\b', r'\bmouses\b', r'\bmouse gamer\b', r'\bmouse sem fio\b', r'\bmouse bt\b', r'\bdpi\b.*\bmouse\b'), (r'\bmaquina de corte\b', r'\bbarbeador\b', r'\baparador\b', r'\bcabelo\b', r'\bwahl\b'), (r'^mouse\b',)),
    GuardRule('Máquinas para corte de cabelo', 0.95, 'produto principal é máquina/aparador de cabelo', (r'\bmaquina de corte\b', r'\bcortador de cabelo\b', r'\bmaquina de cortar\b', r'\baparador\b', r'\bbarbeador\b', r'\bwahl\b', r'\beasycut\b'), (r'\bmouse\b', r'\bdpi\b'), (r'^(?:maquina|aparador|barbeador|wahl)\b',)),
    GuardRule('Pen drives', 0.95, 'produto principal é pen drive/USB flash', (r'\bpen drive\b', r'\bpendrive\b', r'\bflash drive\b', r'\busb flash\b', r'\bcruzer blade\b'), (r'\bcartao de memoria\b', r'\bmicrosd\b', r'\bsd card\b'), (r'^(?:pen drive|pendrive)\b',)),
    GuardRule('Cartões de memória', 0.95, 'produto principal é cartão de memória/micro SD', (r'\bcartao de memoria\b', r'\bcartoes de memoria\b', r'\bmicro\s?sd\b', r'\bmicrosd\b', r'\bsd card\b', r'\bka\s?m\d+\b', r'\bhm\s?m\d+\b'), (r'\bpen drive\b', r'\bpendrive\b', r'\bcruzer blade\b'), (r'^cartao de memoria\b', r'^micro\s?sd\b')),
    GuardRule('Carregadores para celular', 0.94, 'produto principal é carregador/fonte de celular', (r'\bcarregador turbo\b', r'\bcarregador de tomada\b', r'\bfonte carregador\b', r'\btomada usb\b', r'\bcarregador veicular\b', r'\bcarregador tipo c\b', r'\b(?:20w|25w|30w|33w|45w|65w)\b'), (r'\bcabo\b', r'\bpower bank\b', r'\bnotebook\b', r'\bcarregador de pilhas\b'), (r'^carregador\b', r'^fonte carregador\b')),
    GuardRule('Pilhas e baterias', 0.94, 'produto principal é pilha/bateria ou carregador de pilhas', (r'\bpilha\b', r'\bpilhas\b', r'\bbateria recarregavel\b', r'\bbaterias recarregaveis\b', r'\bcarregador de pilhas\b', r'\baa\b', r'\baaa\b', r'\bcr2032\b', r'\blr44\b'), (r'\bpower bank\b', r'\bcarregador de tomada\b'), (r'^pilha\b', r'^pilhas\b', r'^carregador de pilhas\b')),
    GuardRule('Cabos de rede', 0.97, 'produto principal é cabo de rede/RJ45/Ethernet', (r'\bcabo\b.*\brj\s?45\b', r'\bcabo de rede\b', r'\bpatch cord\b', r'\bcat\s?(?:5e|6|6a|7)\b', r'\bethernet\b', r'\blan\b', r'\butp\b'), (r'\busb\b', r'\bhdmi\b', r'\bp2\b'), (r'^cabo de rede\b',)),
    GuardRule('Cabos USB e dados', 0.96, 'produto principal é cabo USB/dados de celular', (r'\bcabo\b.*\busb\b', r'\bcabo usb\b', r'\bcabo de dados\b', r'\bcabo\b.*\btipo c\b', r'\bcabo\b.*\btype c\b', r'\bcabo\b.*\blightning\b', r'\bcabo\b.*\bmicro usb\b', r'\bcabo\b.*\bv8\b'), (r'\bcarregador\b', r'\bfonte\b', r'\btomada\b'), (r'^cabo\b', r'^kit cabo\b')),
    GuardRule('Cabos de energia', 0.95, 'produto principal é cabo de força/energia', (r'\bcabo de forca\b', r'\bcabo energia\b', r'\bforca tripolar\b', r'\balimentacao ac\b', r'\bcabo\b.*\b(?:10a|20a)\b'), (r'\busb\b', r'\bhdmi\b', r'\brj45\b'), (r'^cabo\b',)),
    GuardRule('Cabos de áudio', 0.95, 'produto principal é cabo de áudio', (r'\bcabo\b.*\bp2\b', r'\bcabo\b.*\bp10\b', r'\bcabo\b.*\brca\b', r'\bcabo\b.*\bxlr\b', r'\bcabo\b.*\bauxiliar\b', r'\bcabo\b.*\baudio\b'), (r'\bfone\b', r'\bmicrofone\b', r'\brj45\b'), (r'^cabo\b',)),
    GuardRule('Cabos HDMI e vídeo', 0.95, 'produto principal é cabo/adaptador HDMI/VGA/vídeo', (r'\bcabo\b.*\bhdmi\b', r'\bcabo hdmi\b', r'\bcabo\b.*\bvga\b', r'\badaptador\b.*\bvga\b', r'\badaptador\b.*\bhdmi\b', r'\bal\s?vga\b', r'\bhd03\b'), (r'\bfone\b', r'\bmouse\b'), (r'^cabo\b', r'^adaptador\b')),
    GuardRule('Conversores', 0.95, 'produto principal é conversor/receptor/gravador digital', (r'\bconversor\b', r'\breceptor\b', r'\bgravador digital\b', r'\btv box\b', r'\bmcd\s?-?\d+\b', r'\bmta\s?-?\d+\b', r'\bmtv\s?-?\d+\b'), (r'\bcontrole remoto\b', r'\bcabo\b', r'\bantena\b'), (r'^(?:conversor|receptor|tv box)\b',)),
    GuardRule('Controles para televisão', 0.94, 'produto principal é controle remoto para TV', (r'\bcontrole remoto\b', r'\bcontrole para tv\b', r'\bcontrole tv\b', r'\bcontrole\b.*\b(?:aoc|cce|philco|samsung|lg|tcl|sony|tv)\b'), (r'\bconversor\b', r'\breceptor\b', r'\bcabo\b', r'\bantena\b'), (r'^controle\b',)),
    GuardRule('Antenas Wi-Fi', 0.95, 'produto principal é antena Wi-Fi/rede', (r'\bantena\b.*\bwifi\b', r'\bantena\b.*\bwi fi\b', r'\bantena\b.*\bwireless\b', r'\bantena\b.*\bsma\b', r'\bantena\b.*\bdbi\b', r'\bantena\b.*\bghz\b'), (r'\btv\b', r'\btelevisao\b', r'\buhf\b', r'\bvhf\b'), (r'^antena\b',)),
    GuardRule('Antenas para TV', 0.95, 'produto principal é antena de TV/digital', (r'\bantena\b.*\btv\b', r'\bantena\b.*\btelevisao\b', r'\bantena digital\b', r'\bantena\b.*\buhf\b', r'\bantena\b.*\bvhf\b', r'\bantena\b.*\bhdtv\b'), (r'\bwifi\b', r'\bwireless\b', r'\bsma\b', r'\bghz\b'), (r'^antena\b',)),
    GuardRule('Redes e internet', 0.93, 'produto principal é rede/Wi-Fi/internet', (r'\brepetidor\b', r'\broteador\b', r'\bwifi\b', r'\bwi fi\b', r'\bwireless\b', r'\brj45\b', r'\bethernet\b', r'\bcabo de rede\b'), (r'\bantena\b.*\btv\b', r'\bcontrole remoto\b'), (r'^(?:repetidor|roteador)\b',)),
    GuardRule('Telefones fixos', 0.92, 'produto principal é telefone/interfone/porteiro', (r'\btelefone fixo\b', r'\binterfone\b', r'\bporteiro\b', r'\bvideo porteiro\b', r'\bporteiro eletronico\b'), (r'\bcelular\b', r'\bsmartphone\b'), (r'^(?:telefone|interfone|porteiro|video porteiro)\b',)),
)


def infer_category_by_evidence(title: object, description: object = '', context: object = '') -> CategoryDecision:
    title_text = normalize_text(title)
    full = normalize_text(f'{title or ""} {description or ""} {context or ""}')
    if not full:
        return CategoryDecision(PROVISIONAL_CATEGORY, '', 0.0, 'LOW_CONFIDENCE', 'sem texto para validar categoria')

    best: tuple[GuardRule | None, int, int, list[str], list[str]] = (None, -999, 0, [], [])
    for rule in RULES:
        positives = _hits(full, rule.positives)
        negatives = _hits(full, rule.negatives)
        bonus = _title_score(title_text, rule.title_bonus)
        score = len(positives) + bonus - (2 * len(negatives))
        if positives and score > best[1]:
            best = (rule, score, bonus, positives, negatives)

    rule, score, bonus, positives, negatives = best
    if not rule or score <= 0:
        return CategoryDecision(PROVISIONAL_CATEGORY, '', 0.0, 'LOW_CONFIDENCE', 'sem evidência forte de categoria')

    confidence = max(0.0, min(1.0, rule.confidence + (0.02 * min(bonus, 2)) - (0.05 * len(negatives))))
    if confidence < 0.80:
        return CategoryDecision(PROVISIONAL_CATEGORY, rule.category, confidence, 'LOW_CONFIDENCE', f'evidência fraca para {rule.category}')

    evidence = ', '.join(positives[:4])
    blocked = f'; negativos: {", ".join(negatives[:3])}' if negatives else ''
    return CategoryDecision(rule.category, rule.category, confidence, 'CATEGORY_EVIDENCE', f'{rule.reason}; evidências: {evidence}{blocked}')


def validate_category(title: object, description: object = '', current_category: object = '', context: object = '') -> CategoryDecision:
    current = str(current_category or '').strip()
    current_canonical = _canonical(current)
    inferred = infer_category_by_evidence(title, description=description, context=context)

    if inferred.status == 'LOW_CONFIDENCE':
        if current_canonical and not _current_is_generic(current_canonical):
            return CategoryDecision(current_canonical, inferred.suggested_category, inferred.confidence, 'CATEGORY_OK', 'categoria mantida; sem evidência forte para trocar')
        return inferred

    suggested = inferred.suggested_category
    if current_canonical == suggested:
        return CategoryDecision(current_canonical, suggested, inferred.confidence, 'CATEGORY_OK', 'categoria confirmada por evidência')

    if _current_is_generic(current) or not current_canonical:
        return CategoryDecision(suggested, suggested, inferred.confidence, 'CATEGORY_FORCED', f'categoria vazia/genérica corrigida: {inferred.reason}')

    if current_canonical in CATEGORY_FAMILIES and current_canonical != suggested:
        return CategoryDecision(suggested, suggested, inferred.confidence, 'CATEGORY_BLOCKED', f'categoria incompatível: {current_canonical} -> {suggested}; {inferred.reason}')

    if suggested in CATEGORY_FAMILIES and inferred.confidence >= 0.92:
        return CategoryDecision(suggested, suggested, inferred.confidence, 'CATEGORY_FORCED', f'evidência forte substituiu categoria atual: {current_canonical or current}; {inferred.reason}')

    return CategoryDecision(current_canonical or current, suggested, inferred.confidence, 'CATEGORY_OK', 'categoria mantida; diferença não foi bloqueante')


def _first_existing(row: pd.Series, candidates: Sequence[str]) -> object:
    for candidate in candidates:
        if candidate in row.index:
            value = row.get(candidate)
            try:
                if value is not None and not pd.isna(value) and str(value).strip():
                    return value
            except Exception:
                if value is not None and str(value).strip():
                    return value
    return ''


def audit_category_mismatch(df: pd.DataFrame) -> list[dict[str, Any]]:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return []

    rows: list[dict[str, Any]] = []
    for idx, row in df.fillna('').iterrows():
        title = _first_existing(row, ('Descrição', 'Descricao', 'Título', 'Titulo', 'Nome', 'Nome do produto', 'Produto', 'name', 'nome'))
        description = ' '.join(
            str(_first_existing(row, (col,)))
            for col in (
                'Descrição Curta', 'Descricao Curta', 'Descrição complementar', 'Descricao complementar',
                'Descrição completa', 'Descricao completa', 'Ficha técnica', 'Ficha tecnica',
                'Características', 'Característica',
            )
            if col in row.index and str(row.get(col, '')).strip()
        )
        current = _first_existing(row, ('Categoria do produto', 'Categoria', 'categoria', 'category', 'Nome da categoria'))
        sku = _first_existing(row, ('SKU', 'sku', 'Código', 'Codigo', 'codigo', 'GTIN/EAN', 'EAN'))
        decision = validate_category(title, description=description, current_category=current)
        if decision.status in {'CATEGORY_BLOCKED', 'CATEGORY_FORCED', 'LOW_CONFIDENCE'} and str(decision.accepted_category or '').strip() != str(current or '').strip():
            rows.append({
                'linha': int(idx) + 1,
                'sku': str(sku or ''),
                'produto': str(title or ''),
                'categoria_atual': str(current or ''),
                'categoria_corrigida': decision.accepted_category,
                'categoria_sugerida': decision.suggested_category,
                'status': decision.status,
                'confianca': round(float(decision.confidence or 0), 3),
                'motivo': decision.reason,
            })
    return rows


__all__ = ['CategoryDecision', 'validate_category', 'infer_category_by_evidence', 'audit_category_mismatch']
