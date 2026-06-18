from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from difflib import get_close_matches
from typing import Iterable, Sequence

import pandas as pd

RESPONSIBLE_FILE = 'bling_app_zero/core/category_intelligence.py'

DEFAULT_CATEGORY_CATALOG: tuple[str, ...] = (
    'Fones de ouvido', 'Carregadores para celular', 'Controles para televisão', 'Caixas de som',
    'Máquinas para corte de cabelo', 'Cabos de rede', 'Capas para celulares', 'Suportes',
    'Mouses', 'Cabos', 'Chips', 'Pen drives', 'Pilhas e baterias', 'Controles gamer',
    'Cartões de memória', 'Projetores', 'Antenas', 'Assistência', 'Game sticks', 'Barbeadores',
    'Fontes', 'Rádios AM/FM', 'Celulares', 'Smartwatches', 'Teclados', 'Calculadoras',
    'Conversores', 'Câmeras', 'Telefones fixos', 'Óculos', 'Adaptadores', 'DVD', 'Ferramentas',
    'Guarda-chuvas', 'Lanternas', 'Películas', 'Power banks', 'Microfones', 'Iluminação',
    'Games e consoles', 'Redes e internet', 'Cartuchos e impressão', 'Relógios', 'Energia e tomadas',
    'Eletrodomésticos', 'Utilidades diversas', 'Cuidados pessoais', 'Tablets', 'Brinquedos e utilidades',
    'TV Box e streaming', 'Informática e peças', 'Logística e embalagem',
)

BLOCKED_GENERIC_CATEGORIES = {'informatica', 'mais vendidos'}

CATEGORY_ALIASES = {
    'fone de ouvido': 'Fones de ouvido', 'fones de ouvido': 'Fones de ouvido',
    'carregador celular': 'Carregadores para celular', 'carregadores': 'Carregadores para celular',
    'controle para televisao': 'Controles para televisão', 'controles para televisao': 'Controles para televisão',
    'caixa de som': 'Caixas de som', 'caixas de som': 'Caixas de som',
    'maquina para corte de cabelo': 'Máquinas para corte de cabelo', 'maquinas para corte de cabelo': 'Máquinas para corte de cabelo',
    'capas para celulares': 'Capas para celulares', 'capas para celular': 'Capas para celulares',
    'suporte': 'Suportes', 'suportes': 'Suportes', 'mouse': 'Mouses', 'mouses': 'Mouses',
    'pen drive': 'Pen drives', 'pendrive': 'Pen drives', 'pen drives': 'Pen drives',
    'pilha bateria': 'Pilhas e baterias', 'pilhas e baterias': 'Pilhas e baterias',
    'cartao de memoria': 'Cartões de memória', 'cartoes de memoria': 'Cartões de memória',
    'radio am fm': 'Rádios AM/FM', 'radios am fm': 'Rádios AM/FM',
    'smartwatch': 'Smartwatches', 'smartwatches': 'Smartwatches',
    'calculadora': 'Calculadoras', 'conversor': 'Conversores', 'camera': 'Câmeras', 'cameras': 'Câmeras',
    'telefone fixo': 'Telefones fixos', 'adaptador': 'Adaptadores', 'adaptadores': 'Adaptadores',
    'dvd': 'DVD', 'guarda chuva': 'Guarda-chuvas', 'power bank': 'Power banks', 'informatica e pecas': 'Informática e peças',
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
        'adaptaroes': 'adaptadores', 'adptador': 'adaptador', 'adapitador': 'adaptador',
        'fome de ouvido': 'fone de ouvido', 'fone ouvido': 'fone de ouvido',
        'carregador celuar': 'carregador celular', 'pen driver': 'pen drive',
        'radio am/fm': 'radio am fm', 'maquina corte': 'maquina de corte', 'marina de corte': 'maquina de corte',
        'heaset': 'headset', 'headfone': 'headphone', 'bombox': 'boombox', 'flashlinght': 'flashlight',
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
    return raw, False, 'categoria não reconhecida no catálogo'


def _classify_text(text: str) -> tuple[str, float, str]:
    if _has(text, (r'\btroca\b', r'\bconserto\b', r'\bformatacao\b', r'\bconfiguracao\b', r'\borcament\w*\b', r'\breparo\b', r'\btirar senha\b')):
        return 'Assistência', 0.97, 'serviço/orçamento/reparo'
    if _has(text, (r'\bcontrole\b', r'\bjoystick\b')):
        if _has(text, (r'\btv\b', r'\btelevisao\b', r'\bphilco\b', r'\bsamsung\b', r'\baoc\b', r'\breceptor\b', r'\buniversal\b', r'\bremoto\b')):
            return 'Controles para televisão', 0.94, 'controle remoto TV/box'
        return 'Controles gamer', 0.88, 'controle para jogo'
    if _has(text, (r'\bcapa(?:s)?\b', r'\bcapinha\b', r'\bcase\b', r'\btampa traseira\b')):
        if _has(text, (r'\bcase para hd\b', r'\bcapa para notebook\b', r'\bcapa para piscina\b')):
            return 'Utilidades diversas', 0.78, 'capa/utilidade fora celular'
        return 'Capas para celulares', 0.92, 'capa/acessório de celular'
    rules: tuple[tuple[str, float, str, tuple[str, ...]], ...] = (
        ('Rádios AM/FM', 0.93, 'rádio/transmissor FM', (r'\bradio\b', r'\bam fm\b', r'\btransmissor fm\b', r'\bmp3 player\b')),
        ('Fones de ouvido', 0.94, 'fone/headset', (r'\bfones?\b', r'\bheadset\b', r'\bheadphone(?:s)?\b', r'\bearbuds?\b', r'\bearphones?\b')),
        ('Caixas de som', 0.92, 'caixa de som/alto-falante', (r'\bcaixa de som\b', r'\bcaixa bluetooth\b', r'\bcaixinha\b', r'\bspeaker\b', r'\bboombox\b', r'\bsoundbar\b')),
        ('Microfones', 0.93, 'microfone/megafone', (r'\bmicrofone(?:s)?\b', r'\bmegafone\b')),
        ('Películas', 0.96, 'película/proteção de tela', (r'\bpelicula(?:s)?\b', r'\bhydrogel\b', r'\bvidro temperado\b', r'\bprivacidade\b')),
        ('Game sticks', 0.95, 'game stick', (r'\bgame stick\b',)),
        ('Mouses', 0.94, 'mouse/mousepad', (r'\bmouse(?:s)?\b', r'\bmousepad\b')),
        ('Teclados', 0.94, 'teclado', (r'\bteclado(?:s)?\b', r'\bkeyboard\b')),
        ('Suportes', 0.91, 'suporte/tripé', (r'\bsuporte(?:s)?\b', r'\btripe(?:s)?\b', r'\bpedestal\b', r'\bpau de selfie\b', r'\bporta celular\b')),
        ('Smartwatches', 0.90, 'smartwatch/pulseira', (r'\bsmart watch\b', r'\bsmartwatch\b', r'\bwatch\b', r'\bmi band\b', r'\brelogio inteligente\b')),
        ('Tablets', 0.90, 'tablet', (r'\btablet(?:s)?\b',)),
        ('Telefones fixos', 0.90, 'telefone/interfone', (r'\btelefone sem fio\b', r'\btelefone com fio\b', r'\btelefone fixo\b', r'\binterfone\b', r'\bramal\b')),
        ('Chips', 0.93, 'chip', (r'\bchip(?:s)?\b',)),
        ('Celulares', 0.90, 'celular/smartphone', (r'\bcelular(?:es)?\b', r'\bsmartphone(?:s)?\b')),
        ('Barbeadores', 0.90, 'barbeador/aparador', (r'\bbarbeador\b', r'\baparador de barba\b', r'\baparador nasal\b')),
        ('Máquinas para corte de cabelo', 0.88, 'máquina de corte/acabamento', (r'\bmaquina\b.*\b(cabelo|corte|acabamento|tosa)\b', r'\bclipper\b', r'\bkemei\b', r'\bwahl\b')),
        ('Cuidados pessoais', 0.86, 'beleza/cuidados pessoais', (r'\bsecador\b', r'\bchapinha\b', r'\bescova secadora\b', r'\bdepilador\b', r'\bmassageador\b')),
        ('Eletrodomésticos', 0.86, 'eletrodoméstico', (r'\bventilador\b', r'\bliquidificador\b', r'\bchaleira\b', r'\baspirador\b', r'\bclimatizador\b')),
        ('Power banks', 0.96, 'bateria externa/carregador portátil', (r'\bpower bank\b', r'\bcarregador portatil\b', r'\bbateria externa\b')),
        ('Cartões de memória', 0.94, 'cartão/memory card', (r'\bcartao de memoria\b', r'\bmemory card\b', r'\bmicrosd\b', r'\bsd card\b')),
        ('Pen drives', 0.94, 'armazenamento USB', (r'\bpen drive\b', r'\bpendrive\b')),
        ('Pilhas e baterias', 0.90, 'pilha/bateria', (r'\bpilha(?:s)?\b', r'\bbateria(?:s)?\b', r'\bcr2032\b', r'\b2032\b')),
        ('Energia e tomadas', 0.88, 'tomada/extensão/filtro de linha', (r'\bfiltro de linha\b', r'\bextensao\b', r'\bestabilizador\b', r'\btomada\b')),
        ('Carregadores para celular', 0.91, 'carregador/tomada de celular', (r'\bcarregador(?:es)?\b', r'\btipo c\b', r'\btomada usb\b', r'\btomada veicular\b', r'\bcarregamento\b')),
        ('Fontes', 0.88, 'fonte de alimentação', (r'\bfonte\b', r'\balimentacao\b')),
        ('Cabos de rede', 0.95, 'cabo de rede', (r'\bcabo de rede\b', r'\bpatch cord\b', r'\brj45\b', r'\butp\b')),
        ('Conversores', 0.90, 'conversor de sinal', (r'\bconversor\b', r'\bav2hdmi\b', r'\bvga para hdmi\b')),
        ('Adaptadores', 0.91, 'adaptador/hub/divisor', (r'\badaptador\b', r'\bhub\b', r'\bemenda\b', r'\bdivisor\b')),
        ('Cabos', 0.88, 'cabo/conexão', (r'\bcabo(?:s)?\b', r'\botg\b', r'\bhdmi\b', r'\busb\b', r'\bp2\b', r'\brca\b', r'\blightning\b', r'\bextensor\b')),
        ('Câmeras', 0.90, 'câmera/webcam', (r'\bcamera(?:s)?\b', r'\bwebcam\b')),
        ('Redes e internet', 0.88, 'roteador/repetidor/wifi', (r'\broteador\b', r'\brepetidor\b', r'\bwifi\b', r'\bwi fi\b', r'\bmodem\b', r'\bswitch\b')),
        ('TV Box e streaming', 0.86, 'streaming/assistente', (r'\btv box\b', r'\bfire tv\b', r'\bchromecast\b', r'\balexa\b', r'\becho pop\b')),
        ('Informática e peças', 0.86, 'peça/acessório de informática', (r'\bssd\b', r'\bhd interno\b', r'\bcooler\b', r'\bpasta termica\b', r'\bplaca de captura\b', r'\bnotebook\b')),
        ('Cartuchos e impressão', 0.90, 'cartucho/impressão', (r'\bcartucho\b', r'\bepson\b', r'\bhp colorido\b', r'\bhp preto\b', r'\btoner\b')),
        ('Games e consoles', 0.88, 'console/jogos', (r'\bvideo game\b', r'\bvideogame\b', r'\bplaystation\b', r'\bxbox\b', r'\bkinect\b', r'\bconsole\b', r'\bmini game\b', r'\bps2\b')),
        ('Antenas', 0.90, 'antena', (r'\bantena(?:s)?\b',)), ('Projetores', 0.90, 'projetor', (r'\bprojetor(?:es)?\b',)),
        ('Calculadoras', 0.88, 'calculadora/balança', (r'\bcalculadora(?:s)?\b', r'\bbalanca\b')), ('DVD', 0.86, 'DVD/player', (r'\bdvd\b',)),
        ('Óculos', 0.86, 'óculos', (r'\boculos\b',)), ('Guarda-chuvas', 0.90, 'guarda-chuva/sombrinha', (r'\bguarda chuva\b', r'\bsombrinha\b')),
        ('Lanternas', 0.90, 'lanterna', (r'\blanterna\b', r'\bflashlight\b')), ('Ferramentas', 0.84, 'ferramenta', (r'\bferramenta(?:s)?\b', r'\bchave\b', r'\balicate\b')),
        ('Brinquedos e utilidades', 0.82, 'brinquedo/utilidade', (r'\blousa digital\b', r'\blousa magica\b', r'\bpop it\b', r'\bbrinquedo\b', r'\banti stress\b')),
        ('Iluminação', 0.88, 'luz/LED/efeito', (r'\bring light\b', r'\bfita de led\b', r'\bled\b', r'\bluminaria\b', r'\blampada\b', r'\bjogo de luz\b', r'\blaser\b')),
        ('Relógios', 0.86, 'relógio/cronômetro', (r'\brelogio\b', r'\bdespertador\b', r'\bcronometro\b')),
        ('Logística e embalagem', 0.80, 'frete/embalagem', (r'\bembalagem\b', r'\bfrete\b', r'\bjadlog\b', r'\buber\b')),
        ('Utilidades diversas', 0.75, 'utilidade diversa', (r'\bcaneta touch\b', r'\bcopo\b', r'\bbone\b', r'\bcarteira\b', r'\bdiferenca\b')),
    )
    for category, confidence, reason, patterns in rules:
        if _has(text, patterns):
            return category, confidence, reason
    return 'REVISAR MANUALMENTE', 0.0, 'sem regra segura'


def suggest_category_for_product(product_name: object, description: object = '', current_category: object = '', category_catalog: Sequence[str] = DEFAULT_CATEGORY_CATALOG) -> CategorySuggestion:
    current_canonical, changed_by_alias, alias_reason = canonicalize_category(current_category, category_catalog)
    text = f'{normalize_text(product_name)} {normalize_text(description)}'.strip()
    classified, confidence, reason = _classify_text(text) if text else ('REVISAR MANUALMENTE', 0.0, 'nome vazio')
    if classified != 'REVISAR MANUALMENTE':
        category = classified
    elif current_canonical:
        category = current_canonical
        confidence = 0.82 if changed_by_alias else 0.72
        reason = alias_reason
    else:
        category = 'REVISAR MANUALMENTE'
    current_norm = normalize_text(str(current_category or ''))
    category_norm = normalize_text(category)
    if category == 'REVISAR MANUALMENTE':
        action = 'REVISAR'
    elif not current_norm:
        action = 'CRIAR/VINCULAR CATEGORIA'
    elif current_norm != category_norm or changed_by_alias:
        action = 'CORRIGIR CATEGORIA'
    else:
        action = 'MANTER'
    if current_norm in BLOCKED_GENERIC_CATEGORIES and category == 'REVISAR MANUALMENTE':
        reason = 'categoria genérica bloqueada; produto precisa de categoria específica'
    return CategorySuggestion(category, float(confidence), reason, action)


def classify_dataframe(df: pd.DataFrame, category_catalog: Sequence[str] = DEFAULT_CATEGORY_CATALOG) -> tuple[pd.DataFrame, dict[str, int]]:
    if df is None or df.empty:
        return pd.DataFrame(), {}
    result, category_col = ensure_category_column(df)
    name_col = detect_product_name_column(result)
    desc_col = detect_product_description_column(result)
    if desc_col == name_col:
        desc_col = None
    if not name_col:
        result['categoria_atual_ia'] = result[category_col].fillna('').astype(str).str.strip()
        result['categoria_sugerida_ia'] = 'REVISAR MANUALMENTE'
        result['acao_categoria_ia'] = 'REVISAR'
        result['confianca_categoria_ia'] = 0.0
        result['motivo_categoria_ia'] = 'coluna de nome não encontrada'
        return result, {'total': int(len(result)), 'revisar': int(len(result))}
    suggestions = [
        suggest_category_for_product(row.get(name_col, ''), row.get(desc_col, '') if desc_col else '', row.get(category_col, ''), category_catalog)
        for _, row in result.iterrows()
    ]
    result['categoria_atual_ia'] = result[category_col].fillna('').astype(str).str.strip()
    result['categoria_sugerida_ia'] = [item.category for item in suggestions]
    result['acao_categoria_ia'] = [item.action for item in suggestions]
    result['confianca_categoria_ia'] = [round(float(item.confidence), 2) for item in suggestions]
    result['motivo_categoria_ia'] = [item.reason for item in suggestions]
    return result, {
        'total': int(len(result)),
        'sem_categoria': int((~result[category_col].apply(_is_filled)).sum()),
        'manter': int((result['acao_categoria_ia'] == 'MANTER').sum()),
        'corrigir': int((result['acao_categoria_ia'] == 'CORRIGIR CATEGORIA').sum()),
        'criar_vincular': int((result['acao_categoria_ia'] == 'CRIAR/VINCULAR CATEGORIA').sum()),
        'revisar': int((result['acao_categoria_ia'] == 'REVISAR').sum()),
    }


def apply_category_suggestions(df: pd.DataFrame, confidence_min: float = 0.80, only_missing: bool = False, keep_helper_columns: bool = False) -> tuple[pd.DataFrame, int]:
    if df is None or df.empty:
        return pd.DataFrame(), 0
    result, category_col = ensure_category_column(df)
    if 'categoria_sugerida_ia' not in result.columns:
        result, _ = classify_dataframe(result)
    applied = 0
    for idx, row in result.iterrows():
        suggested = str(row.get('categoria_sugerida_ia', '') or '').strip()
        confidence = float(row.get('confianca_categoria_ia', 0) or 0)
        current = str(row.get(category_col, '') or '').strip()
        if not suggested or suggested == 'REVISAR MANUALMENTE' or confidence < confidence_min:
            continue
        if only_missing and current:
            continue
        if normalize_text(current) != normalize_text(suggested) or current != suggested:
            result.at[idx, category_col] = suggested
            applied += 1
    if not keep_helper_columns:
        result = result.drop(columns=[col for col in HELPER_COLUMNS if col in result.columns])
    return result, applied


def analyze_and_apply_safe_categories(df: pd.DataFrame, confidence_min: float = 0.80, category_catalog: Sequence[str] = DEFAULT_CATEGORY_CATALOG) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, int], int]:
    analyzed, stats = classify_dataframe(df, category_catalog=category_catalog)
    applied, applied_count = apply_category_suggestions(analyzed, confidence_min=confidence_min, keep_helper_columns=False)
    stats = dict(stats or {})
    stats['aplicadas'] = int(applied_count)
    return applied, analyzed, stats, int(applied_count)


__all__ = [
    'DEFAULT_CATEGORY_CATALOG', 'CategorySuggestion', 'analyze_and_apply_safe_categories', 'apply_category_suggestions',
    'canonicalize_category', 'classify_dataframe', 'detect_category_column', 'detect_product_description_column',
    'detect_product_name_column', 'ensure_category_column', 'normalize_text', 'suggest_category_for_product',
]
