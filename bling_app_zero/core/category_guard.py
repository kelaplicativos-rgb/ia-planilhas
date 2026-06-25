from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import pandas as pd

from bling_app_zero.core.category_intelligence import PROVISIONAL_CATEGORY, canonicalize_category, normalize_text

FAMILIES = {'Power banks','Fontes','Adaptadores','Rádios AM e FM','Caixas de som','Fones de ouvido','Microfones','Mouses','Máquinas para corte de cabelo','Pen drives','Cartões de memória','Carregadores para celular','Pilhas e baterias','Cabos de rede','Cabos USB e dados','Cabos de energia','Cabos de áudio','Cabos HDMI e vídeo','Conversores','Controles para televisão','Redes e internet','Antenas Wi-Fi','Antenas para TV','Telefones fixos'}
GENERIC = {'','nan','none','null','<na>','na','n/a','sem categoria','revisar manualmente','revisao manual','diversos','geral','outros','informatica','produtos nao classificados'}

@dataclass(frozen=True)
class CategoryDecision:
    accepted_category: str
    suggested_category: str
    confidence: float
    status: str
    reason: str


def _has(text: str, *patterns: str) -> bool:
    return any(re.search(p, text) for p in patterns)


def infer_category_by_evidence(title: object, description: object = '', context: object = '') -> CategoryDecision:
    t = normalize_text(title)
    x = normalize_text(f'{title or ""} {description or ""} {context or ""}')
    cat = ''
    if _has(x, r'\bpower bank\b', r'\bcarregador portatil\b', r'\bbateria externa\b') and not _has(x, r'\bcarregador de pilhas\b'):
        cat = 'Power banks'
    elif _has(x, r'\bfonte\b.*\bnotebook\b', r'\bcarregador\b.*\bnotebook\b', r'\bfonte universal\b'):
        cat = 'Fontes'
    elif _has(x, r'\badaptador de fone\b', r'\badaptador usb c\b', r'\badaptador tipo c\b', r'\bconversor tipo c\b'):
        cat = 'Adaptadores'
    elif _has(x, r'\bradio\b', r'\bam fm\b', r'\bam e fm\b', r'\bantena telescopica\b') and not _has(x, r'\bcaixa de som\b'):
        cat = 'Rádios AM e FM'
    elif _has(x, r'\bcaixa de som\b', r'\bcaixa amplificada\b', r'\bspeaker\b'):
        cat = 'Caixas de som'
    elif _has(x, r'\bfone\b', r'\bfone de ouvido\b', r'\bheadset\b', r'\bheadphone\b') and not _has(t, r'^cabo\b', r'^adaptador\b'):
        cat = 'Fones de ouvido'
    elif _has(x, r'\bmicrofone\b', r'\blapela\b') and not _has(x, r'\bcaixa de som\b', r'\bfone\b.*\bmicrofone\b'):
        cat = 'Microfones'
    elif _has(x, r'\bmouse\b', r'\bmouses\b', r'\bmouse sem fio\b', r'\bmouse bt\b') and not _has(x, r'\bwahl\b', r'\bbarbeador\b', r'\bcabelo\b'):
        cat = 'Mouses'
    elif _has(x, r'\bmaquina de corte\b', r'\bmaquina de cortar\b', r'\baparador\b', r'\bbarbeador\b', r'\bwahl\b', r'\beasycut\b') and not _has(x, r'\bmouse\b'):
        cat = 'Máquinas para corte de cabelo'
    elif _has(x, r'\bpen drive\b', r'\bpendrive\b', r'\bflash drive\b', r'\bcruzer blade\b'):
        cat = 'Pen drives'
    elif _has(x, r'\bcartao de memoria\b', r'\bmicrosd\b', r'\bsd card\b', r'\bhm\s?-?m\d+\b', r'\bka\s?-?m\d+\b') and not _has(x, r'\bpen drive\b', r'\bpendrive\b'):
        cat = 'Cartões de memória'
    elif _has(x, r'\bcarregador de pilhas\b', r'\bpilhas\b', r'\bpilha\b') and not _has(x, r'\bpower bank\b'):
        cat = 'Pilhas e baterias'
    elif _has(x, r'\bcarregador turbo\b', r'\bcarregador de tomada\b', r'\bfonte carregador\b', r'\btomada usb\b') and not t.startswith('cabo'):
        cat = 'Carregadores para celular'
    elif t.startswith('cabo') and _has(x, r'\brj\s?45\b', r'\bcabo de rede\b', r'\bcat\s?(5e|6|6a|7)\b', r'\bethernet\b'):
        cat = 'Cabos de rede'
    elif t.startswith('cabo') and _has(x, r'\busb\b', r'\btipo c\b', r'\blightning\b', r'\bv8\b', r'\bcabo de dados\b'):
        cat = 'Cabos USB e dados'
    elif t.startswith('cabo') and _has(x, r'\bp2\b', r'\bp10\b', r'\brca\b', r'\bxlr\b', r'\baudio\b', r'\bauxiliar\b'):
        cat = 'Cabos de áudio'
    elif t.startswith('cabo') and _has(x, r'\bforca\b', r'\benergia\b', r'\btripolar\b', r'\b10a\b', r'\b20a\b'):
        cat = 'Cabos de energia'
    elif t.startswith(('cabo', 'adaptador')) and _has(x, r'\bhdmi\b', r'\bvga\b', r'\bal\s?vga\b', r'\bhd03\b'):
        cat = 'Cabos HDMI e vídeo'
    elif _has(x, r'\bconversor\b', r'\breceptor\b', r'\bgravador digital\b', r'\btv box\b', r'\bmcd\s?-?\d+\b', r'\bmta\s?-?\d+\b', r'\bmtv\s?-?\d+\b') and not t.startswith('controle'):
        cat = 'Conversores'
    elif _has(x, r'\bcontrole remoto\b', r'\bcontrole para tv\b', r'\bcontrole tv\b') or (t.startswith('controle') and _has(x, r'\btv\b', r'\baoc\b', r'\bcce\b', r'\bphilco\b')):
        cat = 'Controles para televisão'
    elif _has(x, r'\brepetidor\b', r'\broteador\b', r'\bwifi\b', r'\bwireless\b') and not _has(x, r'\bantena\b.*\btv\b'):
        cat = 'Redes e internet'
    elif _has(x, r'\bantena\b.*\bwifi\b', r'\bantena\b.*\bwireless\b', r'\bantena\b.*\bdbi\b'):
        cat = 'Antenas Wi-Fi'
    elif _has(x, r'\bantena\b.*\btv\b', r'\bantena digital\b', r'\bantena\b.*\buhf\b'):
        cat = 'Antenas para TV'
    elif _has(x, r'\btelefone fixo\b', r'\binterfone\b', r'\bporteiro\b', r'\bvideo porteiro\b'):
        cat = 'Telefones fixos'
    if not cat:
        return CategoryDecision(PROVISIONAL_CATEGORY, '', 0.0, 'LOW_CONFIDENCE', 'sem evidência forte de categoria')
    return CategoryDecision(cat, cat, 0.95, 'CATEGORY_EVIDENCE', f'evidência forte de {cat}')


def validate_category(title: object, description: object = '', current_category: object = '', context: object = '') -> CategoryDecision:
    current = str(current_category or '').strip()
    current_canonical, _changed, _reason = canonicalize_category(current)
    inferred = infer_category_by_evidence(title, description, context)
    if inferred.status == 'LOW_CONFIDENCE':
        if current_canonical and normalize_text(current_canonical) not in GENERIC:
            return CategoryDecision(current_canonical, inferred.suggested_category, inferred.confidence, 'CATEGORY_OK', 'categoria mantida')
        return inferred
    if current_canonical == inferred.suggested_category:
        return CategoryDecision(current_canonical, inferred.suggested_category, inferred.confidence, 'CATEGORY_OK', 'categoria confirmada')
    if normalize_text(current) in GENERIC or not current_canonical or current_canonical in FAMILIES:
        status = 'CATEGORY_FORCED' if normalize_text(current) in GENERIC or not current_canonical else 'CATEGORY_BLOCKED'
        return CategoryDecision(inferred.suggested_category, inferred.suggested_category, inferred.confidence, status, f'categoria corrigida: {current_canonical or current} -> {inferred.suggested_category}')
    return CategoryDecision(current_canonical or current, inferred.suggested_category, inferred.confidence, 'CATEGORY_OK', 'categoria mantida')


def audit_category_mismatch(df: Any) -> list[dict[str, Any]]:
    return [] if not isinstance(df, pd.DataFrame) else []

__all__ = ['CategoryDecision', 'validate_category', 'infer_category_by_evidence', 'audit_category_mismatch']
