from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from difflib import get_close_matches
from typing import Iterable, Sequence

import pandas as pd


RESPONSIBLE_FILE = 'bling_app_zero/core/category_intelligence.py'

DEFAULT_CATEGORY_CATALOG: tuple[str, ...] = (
    'Fones de ouvido',
    'Carregadores para celular',
    'Controles para televisão',
    'Caixas de som',
    'Máquinas para corte de cabelo',
    'Cabos de rede',
    'Capas para celulares',
    'Suportes',
    'Mouses',
    'Cabos',
    'Chips',
    'Pen drives',
    'Pilhas e baterias',
    'Controles gamer',
    'Cartões de memória',
    'Projetores',
    'Antenas',
    'Assistência',
    'Game sticks',
    'Barbeadores',
    'Fontes',
    'Rádios AM e FM',
    'Celulares',
    'Smartwatches',
    'Teclados',
    'Calculadoras',
    'Conversores',
    'Câmeras',
    'Telefones fixos',
    'Óculos',
    'Adaptadores',
    'DVD',
    'Ferramentas',
    'Guarda-chuvas',
    'Lanternas',
    'Películas',
    'Power banks',
    'Microfones',
    'Iluminação',
    'Games e consoles',
    'Redes e internet',
    'Cartuchos e impressão',
    'Relógios',
    'Energia e tomadas',
    'Eletrodomésticos',
    'Utilidades diversas',
    'Cuidados pessoais',
    'Tablets',
    'Brinquedos e utilidades',
    'TV Box e streaming',
    'Informática e peças',
    'Logística e embalagem',
)

BLOCKED_GENERIC_CATEGORIES = {
    'informatica',
    'mais vendidos',
    'alimentos',
    'geral',
    'diversos',
    'outros',
    'sem categoria',
    'sem classificacao',
    'produtos nao classificados',
    'revisar manualmente',
}

CATEGORY_ALIASES = {
    'fone de ouvido': 'Fones de ouvido',
    'fones de ouvido': 'Fones de ouvido',
    'fone': 'Fones de ouvido',
    'headset': 'Fones de ouvido',
    'headsets': 'Fones de ouvido',
    'carregador celular': 'Carregadores para celular',
    'carregadores': 'Carregadores para celular',
    'carregadores para celular': 'Carregadores para celular',
    'controle para televisao': 'Controles para televisão',
    'controles para televisao': 'Controles para televisão',
    'controle remoto': 'Controles para televisão',
    'controles remotos': 'Controles para televisão',
    'caixa de som': 'Caixas de som',
    'caixas de som': 'Caixas de som',
    'maquinas para corte de cabelo': 'Máquinas para corte de cabelo',
    'maquina para corte de cabelo': 'Máquinas para corte de cabelo',
    'maquina de aparar pelo': 'Máquinas para corte de cabelo',
    'capas para celulares': 'Capas para celulares',
    'capas para celular': 'Capas para celulares',
    'suporte': 'Suportes',
    'suportes': 'Suportes',
    'mouse': 'Mouses',
    'mouses': 'Mouses',
    'pen drive': 'Pen drives',
    'pendrive': 'Pen drives',
    'pen drives': 'Pen drives',
    'pilha bateria': 'Pilhas e baterias',
    'pilha baterias': 'Pilhas e baterias',
    'pilhas e baterias': 'Pilhas e baterias',
    'controles gamer': 'Controles gamer',
    'cartao de memoria': 'Cartões de memória',
    'cartoes de memoria': 'Cartões de memória',
    'game sticks': 'Game sticks',
    'game stick': 'Game sticks',
    'radio am fm': 'Rádios AM e FM',
    'radios am fm': 'Rádios AM e FM',
    'radios am e fm': 'Rádios AM e FM',
    'radio am e fm': 'Rádios AM e FM',
    'radios am': 'Rádios AM e FM',
    'radio am': 'Rádios AM e FM',
    'radio': 'Rádios AM e FM',
    'radios': 'Rádios AM e FM',
    'smartwatch': 'Smartwatches',
    'smartwatches': 'Smartwatches',
    'calculadora': 'Calculadoras',
    'calculadoras': 'Calculadoras',
    'conversor': 'Conversores',
    'conversores': 'Conversores',
    'camera': 'Câmeras',
    'cameras': 'Câmeras',
    'telefone fixo': 'Telefones fixos',
    'telefones fixos': 'Telefones fixos',
    'adaptador': 'Adaptadores',
    'adaptadores': 'Adaptadores',
    'dvd': 'DVD',
    'guarda chuva': 'Guarda-chuvas',
    'guarda chuvas': 'Guarda-chuvas',
    'power bank': 'Power banks',
    'power banks': 'Power banks',
    'tomadas': 'Energia e tomadas',
    'tomada': 'Energia e tomadas',
    'informatica e pecas': 'Informática e peças',
}

PRODUCT_NAME_COLUMNS = ('Descrição', 'Descricao', 'Nome', 'Nome do produto', 'Produto', 'Título', 'Titulo', 'name', 'nome')
PRODUCT_DESCRIPTION_COLUMNS = ('Descrição Curta', 'Descricao Curta', 'Descrição complementar', 'Descricao complementar', 'Características', 'Ficha técnica', 'description', 'descricao')
CATEGORY_COLUMNS = ('Categoria', 'Categoria do produto', 'Categoria Produto', 'Nome da categoria', 'category', 'categoria')
HELPER_COLUMNS = ('categoria_atual_ia', 'categoria_sugerida_ia', 'acao_categoria_ia', 'confianca_categoria_ia', 'motivo_categoria_ia')


@dataclass(frozen=True)
class CategorySuggestion:
    category: str
    confidence: float
    reason: str
    action: str


def normalize_text(value: object) -> str:
    text = '' if value is None else str(value)
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')
    text = text.lower().replace('&', ' e ').replace('/', ' ')
    replacements = {
        'adaptaroes': 'adaptadores',
        'adptador': 'adaptador',
        'adapitador': 'adaptador',
        'fome de ouvido': 'fone de ouvido',
        'fone ouvido': 'fone de ouvido',
        'carregador celuar': 'carregador celular',
        'cabos usb': 'cabo usb',
        'pen driver': 'pen drive',
        'radios am/fm': 'radio am fm',
        'radio am/fm': 'radio am fm',
        'maquina corte': 'maquina de corte',
        'marina de corte': 'maquina de corte',
        'heaset': 'headset',
        'headfone': 'headphone',
        'bombox': 'boombox',
        'flashlinght': 'flashlight',
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    text = re.sub(r'[^a-z0-9]+', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()


def _has(text: str, patterns: Iterable[str]) -> bool:
    return any(re.search(pattern, text) for pattern in patterns)


def _is_filled(value: object) -> bool:
    if value is None:
        return False
    try:
        if pd.isna(value):
            return False
    except Exception:
        pass
    return str(value).strip() != ''


def _find_column(columns: Sequence[str], candidates: Sequence[str]) -> str | None:
    exact = {normalize_text(col): col for col in columns}
    for candidate in candidates:
        found = exact.get(normalize_text(candidate))
        if found:
            return found
    for col in columns:
        col_norm = normalize_text(col)
        for candidate in candidates:
            cand_norm = normalize_text(candidate)
            if cand_norm and cand_norm in col_norm:
                return col
    return None


def detect_product_name_column(df: pd.DataFrame) -> str | None:
    return _find_column(list(df.columns), PRODUCT_NAME_COLUMNS)


def detect_product_description_column(df: pd.DataFrame) -> str | None:
    return _find_column(list(df.columns), PRODUCT_DESCRIPTION_COLUMNS)


def detect_category_column(df: pd.DataFrame) -> str | None:
    return _find_column(list(df.columns), CATEGORY_COLUMNS)


def ensure_category_column(df: pd.DataFrame, preferred: str = 'Categoria') -> tuple[pd.DataFrame, str]:
    result = df.copy()
    category_col = detect_category_column(result)
    if category_col:
        return result, category_col
    result[preferred] = ''
    return result, preferred


def looks_like_product_title(value: object) -> bool:
    raw = str(value or '').strip()
    norm = normalize_text(raw)
    if not norm:
        return False
    words = norm.split()
    if len(words) >= 7:
        return True
    if len(raw) > 50 and len(words) >= 4:
        return True
    if re.search(r'\b[A-Z]{2,}[- ]?\d{2,}[A-Z0-9-]*\b', raw):
        return True
    if re.search(r'\b[A-Z]{1,4}-\d{2,}[A-Z0-9-]*\b', raw):
        return True
    tech_units = (r'\b\d+\s?(?:gb|mah|w|v|hz|mm|cm|pol|hd|uhd|4k)\b', r'\b(?:wifi|wi fi|bluetooth|usb|tipo c|bt|pd\d+)\b')
    if len(words) >= 4 and _has(norm, tech_units):
        return True
    product_nouns = (
        r'\bfone\b', r'\bheadset\b', r'\bmicrofone\b', r'\bcamera\b', r'\btomada\b',
        r'\bfilmadora\b', r'\bmaquina\b', r'\bluminaria\b', r'\bfita\b', r'\bsensor\b',
    )
    if len(words) >= 5 and _has(norm, product_nouns):
        return True
    return False


def canonicalize_category(value: object, catalog: Sequence[str] = DEFAULT_CATEGORY_CATALOG) -> tuple[str, bool, str]:
    raw = str(value or '').strip()
    norm = normalize_text(raw)
    if not norm:
        return '', False, 'categoria vazia'
    if norm in BLOCKED_GENERIC_CATEGORIES:
        return '', True, f'categoria genérica/removida: {raw}'
    alias = CATEGORY_ALIASES.get(norm)
    if alias:
        return alias, alias != raw, 'padronização de plural/ortografia'
    normalized_catalog = {normalize_text(item): str(item).strip() for item in catalog if str(item).strip()}
    if norm in normalized_catalog:
        canonical = normalized_catalog[norm]
        return canonical, canonical != raw, 'padronização de escrita'
    matches = get_close_matches(norm, list(normalized_catalog.keys()), n=1, cutoff=0.88)
    if matches:
        canonical = normalized_catalog[matches[0]]
        return canonical, canonical != raw, 'correção por similaridade'
    if looks_like_product_title(raw):
        return '', True, f'bloqueado: categoria parece nome de produto: {raw[:80]}'
    return '', True, f'categoria fora do catálogo seguro: {raw[:80]}'


def _classify_text(text: str) -> tuple[str, float, str]:
    if _has(text, (r'\bcontrole\b', r'\bjoystick\b')):
        if _has(text, (r'\btv\b', r'\btelevisao\b', r'\bphilco\b', r'\bsamsung\b', r'\baoc\b', r'\breceptor\b', r'\buniversal\b', r'\bremoto\b')):
            return 'Controles para televisão', 0.94, 'controle remoto TV/box'
        return 'Controles gamer', 0.88, 'controle para jogo'
    if _has(text, (r'\bcabo de rede\b', r'\bpatch cord\b', r'\brj45\b', r'\butp\b')):
        return 'Cabos de rede', 0.95, 'cabo de rede'
    if _has(text, (r'\bcabo(?:s)?\b', r'\blightning\b')) and _has(text, (r'\btipo c\b', r'\biphone\b', r'\busb\b', r'\blightning\b')):
        return 'Cabos', 0.94, 'cabo de celular/dados'
    if _has(text, (r'\bcarregador(?:es)?\b', r'\btomada usb\b', r'\btomada veicular\b', r'\bcarregamento\b')):
        return 'Carregadores para celular', 0.91, 'carregador/tomada de celular'
    if _has(text, (r'\bporteiro\b', r'\bvideo porteiro\b', r'\bporteiro eletronico\b')):
        return 'Telefones fixos', 0.88, 'telefone/interfone/porteiro'
    if _has(text, (r'\bcapa(?:s)?\b', r'\bcapinha\b', r'\bcase\b', r'\btampa traseira\b')):
        if _has(text, (r'\bcase para hd\b', r'\bcapa para notebook\b', r'\bcapa para piscina\b')):
            return 'Utilidades diversas', 0.78, 'capa/utilidade fora celular'
        return 'Capas para celulares', 0.92, 'capa/acessório de celular'

    rules: tuple[tuple[str, float, str, tuple[str, ...]], ...] = (
        ('Rádios AM e FM', 0.93, 'rádio/transmissor FM', (r'\bradio\b', r'\bam fm\b', r'\btransmissor fm\b', r'\bmp3 player\b')),
        ('Fones de ouvido', 0.94, 'fone/headset', (r'\bfones?\b', r'\bheadset\b', r'\bheadphone(?:s)?\b', r'\bearbuds?\b', r'\bearphones?\b')),
        ('Caixas de som', 0.93, 'caixa de som/speaker', (r'\bcaixa de som\b', r'\bspeaker\b', r'\bboombox\b', r'\bbluetooth speaker\b')),
        ('Máquinas para corte de cabelo', 0.93, 'máquina/barbeador', (r'\bmaquina de corte\b', r'\bbarbeador\b', r'\baparador\b', r'\btrimmer\b')),
        ('Mouses', 0.90, 'mouse', (r'\bmouse\b',)),
        ('Teclados', 0.90, 'teclado', (r'\bteclado\b', r'\bkeyboard\b')),
        ('Calculadoras', 0.95, 'calculadora', (r'\bcalculadora\b',)),
        ('Conversores', 0.90, 'conversor/adaptador sinal', (r'\bconversor\b', r'\badaptador hdmi\b', r'\bhdmi para\b')),
        ('Câmeras', 0.90, 'câmera/webcam', (r'\bcamera\b', r'\bwebcam\b', r'\bcam\b')),
        ('Celulares', 0.90, 'celular/smartphone', (r'\bcelular\b', r'\bsmartphone\b', r'\btelefone celular\b')),
        ('Smartwatches', 0.90, 'relógio inteligente', (r'\bsmartwatch\b', r'\bsmart watch\b', r'\brelogio inteligente\b')),
        ('Antenas', 0.88, 'antena', (r'\bantena\b',)),
        ('Chips', 0.88, 'chip/sim card', (r'\bchip\b', r'\bsim card\b')),
        ('Cartões de memória', 0.92, 'cartão de memória', (r'\bcartao de memoria\b', r'\bmemory card\b', r'\bmicrosd\b', r'\bsd card\b')),
        ('Pen drives', 0.92, 'pen drive', (r'\bpen drive\b', r'\bpendrive\b', r'\bflash drive\b')),
        ('Pilhas e baterias', 0.88, 'pilha/bateria', (r'\bpilha\b', r'\bbateria\b', r'\bbattery\b')),
        ('Power banks', 0.91, 'power bank', (r'\bpower bank\b', r'\bcarregador portatil\b')),
        ('Projetores', 0.90, 'projetor', (r'\bprojetor\b', r'\bprojector\b')),
        ('Microfones', 0.90, 'microfone', (r'\bmicrofone\b', r'\bmicrophone\b', r'\bmic\b')),
        ('Fontes', 0.86, 'fonte/adaptador de energia', (r'\bfonte\b', r'\badaptador de energia\b')),
        ('Energia e tomadas', 0.85, 'tomada/filtro/energia', (r'\btomada\b', r'\bfiltro de linha\b', r'\bextensao\b', r'\benergia\b')),
        ('Ferramentas', 0.82, 'ferramenta', (r'\bchave\b', r'\balicate\b', r'\bkit ferramenta\b', r'\bferro de solda\b')),
        ('Guarda-chuvas', 0.92, 'guarda-chuva', (r'\bguarda chuva\b', r'\bguarda chuvas\b')),
        ('Lanternas', 0.88, 'lanterna/iluminação portátil', (r'\blanterna\b', r'\bflashlight\b')),
        ('DVD', 0.86, 'dvd/player', (r'\bdvd\b', r'\bplayer dvd\b')),
        ('Adaptadores', 0.84, 'adaptador genérico', (r'\badaptador\b', r'\badapter\b')),
        ('Suportes', 0.82, 'suporte/base', (r'\bsuporte\b', r'\bholder\b', r'\bbase para\b')),
        ('Assistência', 0.78, 'serviço/reparo', (r'\btroca de\b', r'\bservico\b', r'\breparo\b', r'\bconserto\b')),
    )
    for category, confidence, reason, patterns in rules:
        if _has(text, patterns):
            return category, confidence, reason
    return '', 0.0, 'sem regra segura'


def _row_text(row: pd.Series, columns: Sequence[str]) -> str:
    parts = []
    for col in columns:
        if col and col in row.index and _is_filled(row[col]):
            parts.append(str(row[col]))
    return normalize_text(' '.join(parts))


def suggest_category_for_product(name: object, *, description: object = '', current_category: object = '') -> CategorySuggestion:
    canonical, changed, reason = canonicalize_category(current_category)
    if canonical:
        return CategorySuggestion(canonical, 1.0 if not changed else 0.96, reason, 'CORRIGIR' if changed else 'MANTER')

    name_text = normalize_text(name)
    category, confidence, why = _classify_text(name_text)
    if category:
        return CategorySuggestion(category, confidence, f'{why} pelo nome', 'CRIAR/VINCULAR')

    desc_text = normalize_text(description)
    category, confidence, why = _classify_text(desc_text)
    if category:
        return CategorySuggestion(category, max(0.50, confidence - 0.06), f'{why} pela descrição complementar', 'CRIAR/VINCULAR')

    all_text = normalize_text(f'{name or ""} {description or ""}')
    category, confidence, why = _classify_text(all_text)
    if category:
        return CategorySuggestion(category, max(0.50, confidence - 0.10), f'{why} por fallback controlado', 'CRIAR/VINCULAR')
    return CategorySuggestion('REVISAR MANUALMENTE', 0.0, 'não foi possível inferir categoria segura', 'REVISAR')


def suggest_category_for_row(row: pd.Series, *, name_col: str | None, desc_col: str | None) -> CategorySuggestion:
    current_col = None
    for candidate in CATEGORY_COLUMNS:
        if candidate in row.index:
            current_col = candidate
            break
    current = row.get(current_col, '') if current_col else ''
    name_value = row.get(name_col, '') if name_col and name_col in row.index else ''
    desc_value = row.get(desc_col, '') if desc_col and desc_col in row.index else ''
    suggestion = suggest_category_for_product(name_value, description=desc_value, current_category=current)
    if suggestion.category != 'REVISAR MANUALMENTE':
        return suggestion

    all_text = _row_text(row, [name_col, desc_col, 'Descrição', 'Descricao', 'Nome', 'Produto', 'Título', 'Titulo'])
    category, confidence, why = _classify_text(all_text)
    if category:
        return CategorySuggestion(category, max(0.50, confidence - 0.10), f'{why} por fallback controlado', 'CRIAR/VINCULAR')
    return suggestion


def classify_dataframe(df: pd.DataFrame, *, category_catalog: Sequence[str] = DEFAULT_CATEGORY_CATALOG) -> tuple[pd.DataFrame, dict[str, int]]:
    result, category_col = ensure_category_column(df)
    name_col = detect_product_name_column(result)
    desc_col = detect_product_description_column(result)
    suggestions: list[CategorySuggestion] = []
    for _, row in result.iterrows():
        suggestion = suggest_category_for_row(row, name_col=name_col, desc_col=desc_col)
        if suggestion.category not in {'', 'REVISAR MANUALMENTE'}:
            canonical, changed, reason = canonicalize_category(suggestion.category, category_catalog)
            if canonical:
                suggestion = CategorySuggestion(canonical, min(1.0, suggestion.confidence), reason if changed else suggestion.reason, suggestion.action)
            else:
                suggestion = CategorySuggestion('REVISAR MANUALMENTE', 0.0, reason, 'REVISAR')
        suggestions.append(suggestion)

    result['categoria_atual_ia'] = result[category_col].astype(str)
    result['categoria_sugerida_ia'] = [item.category for item in suggestions]
    result['acao_categoria_ia'] = [item.action for item in suggestions]
    result['confianca_categoria_ia'] = [round(float(item.confidence), 3) for item in suggestions]
    result['motivo_categoria_ia'] = [item.reason for item in suggestions]

    stats = {
        'total': int(len(result)),
        'sem_categoria': int((result[category_col].astype(str).str.strip() == '').sum()),
        'corrigir': int((result['acao_categoria_ia'] == 'CORRIGIR').sum()),
        'criar_vincular': int((result['acao_categoria_ia'] == 'CRIAR/VINCULAR').sum()),
        'revisar': int((result['acao_categoria_ia'] == 'REVISAR').sum()),
    }
    return result, stats


def apply_category_suggestions(df: pd.DataFrame, *, confidence_min: float = 0.80, keep_helper_columns: bool = False) -> tuple[pd.DataFrame, int]:
    result = df.copy()
    result, category_col = ensure_category_column(result)
    if 'categoria_sugerida_ia' not in result.columns:
        analyzed, _stats = classify_dataframe(result)
        result = analyzed
        category_col = detect_category_column(result) or category_col
    applied = 0
    for idx, row in result.iterrows():
        suggestion = str(row.get('categoria_sugerida_ia', '')).strip()
        confidence = float(row.get('confianca_categoria_ia', 0) or 0)
        if suggestion and suggestion != 'REVISAR MANUALMENTE' and confidence >= confidence_min:
            if str(result.at[idx, category_col]).strip() != suggestion:
                result.at[idx, category_col] = suggestion
                applied += 1
    if not keep_helper_columns:
        result = result.drop(columns=[col for col in HELPER_COLUMNS if col in result.columns], errors='ignore')
    return result, applied


__all__ = [
    'DEFAULT_CATEGORY_CATALOG',
    'CategorySuggestion',
    'apply_category_suggestions',
    'canonicalize_category',
    'classify_dataframe',
    'detect_category_column',
    'detect_product_description_column',
    'detect_product_name_column',
    'ensure_category_column',
    'looks_like_product_title',
    'normalize_text',
    'suggest_category_for_product',
    'suggest_category_for_row',
]
