from __future__ import annotations

import re
from difflib import SequenceMatcher

import pandas as pd

from bling_app_zero.ai.ai_schema import AIResult
from bling_app_zero.core.column_contract import infer_kind
from bling_app_zero.core.smart_column_profiler import profile_as_mapping
from bling_app_zero.core.text import normalize_key

DESCRIPTION_KINDS = {'descricao', 'descricao_curta', 'descricao_complementar', 'nome_apoio'}
PRICE_KINDS = {'preco_unitario', 'preco_custo'}
CODE_KINDS = {'codigo', 'id_produto'}
URL_KINDS = {'url', 'imagem'}

TARGET_ALIASES = {
    'descricao': ('descricao', 'descrição', 'nome produto', 'titulo', 'título', 'produto'),
    'descricao_complementar': ('descricao complementar', 'descrição complementar', 'descricao completa', 'descrição completa', 'descricao longa', 'descrição longa', 'informacoes adicionais', 'informações adicionais'),
    'descricao_curta': ('descricao curta', 'descrição curta', 'resumo', 'nome curto'),
    'preco_unitario': ('preco', 'preço', 'valor venda', 'preco venda', 'preço venda', 'valor unitario', 'valor unitário'),
    'preco_custo': ('custo', 'preco custo', 'preço custo', 'preco compra', 'preço compra', 'valor compra'),
    'estoque': ('estoque', 'saldo', 'quantidade', 'qtd'),
    'codigo': ('codigo', 'código', 'sku', 'referencia', 'referência', 'cod produto'),
    'gtin': ('gtin', 'ean', 'codigo barras', 'código barras', 'barcode'),
    'ncm': ('ncm', 'classificacao fiscal', 'classificação fiscal', 'codigo ncm', 'código ncm'),
    'marca': ('marca', 'fabricante', 'brand'),
    'fornecedor': ('fornecedor', 'supplier'),
    'categoria': ('categoria', 'departamento', 'grupo', 'familia', 'família', 'breadcrumb'),
    'imagem': ('imagem', 'foto', 'url imagem', 'imagens'),
    'url': ('url', 'link', 'pagina', 'página', 'link externo'),
}


def _compact(value: object) -> str:
    return re.sub(r'[^a-z0-9]+', '', normalize_key(value))


def _target_kind(column: str) -> str:
    kind = infer_kind(column)
    if kind != 'custom':
        return kind
    key = normalize_key(column)
    for alias_kind, aliases in TARGET_ALIASES.items():
        if any(normalize_key(alias) in key or key in normalize_key(alias) for alias in aliases):
            return alias_kind
    return 'custom'


def _header_similarity(source: str, target: str, target_kind: str) -> float:
    source_key = normalize_key(source)
    target_key = normalize_key(target)
    if not source_key or not target_key:
        return 0.0
    if _compact(source_key) == _compact(target_key):
        return 1.0
    if source_key in target_key or target_key in source_key:
        return 0.86
    source_kind = infer_kind(source)
    if source_kind == target_kind and source_kind != 'custom':
        return 0.88
    aliases = TARGET_ALIASES.get(target_kind, ())
    if any(normalize_key(alias) in source_key for alias in aliases):
        return 0.84
    return round(SequenceMatcher(None, source_key, target_key).ratio(), 3)


def _kind_compatible(target_kind: str, source_kind: str) -> bool:
    if target_kind == source_kind and target_kind != 'custom':
        return True
    groups = [DESCRIPTION_KINDS, PRICE_KINDS, CODE_KINDS | {'gtin'}, URL_KINDS, {'ncm'}, {'marca'}, {'categoria'}, {'fornecedor'}, {'estoque'}]
    return any(target_kind in group and source_kind in group for group in groups)


def _content_score(target_kind: str, source_profile: dict[str, object]) -> tuple[float, str]:
    source_kind = str(source_profile.get('kind') or '')
    content_kind = str(source_profile.get('content_kind') or '')
    confidence = float(source_profile.get('confidence') or 0)
    text = float(source_profile.get('text') or 0)
    numeric = float(source_profile.get('numeric') or 0)
    integer = float(source_profile.get('integer') or 0)
    price = float(source_profile.get('price') or 0)
    gtin = float(source_profile.get('gtin') or 0)
    url = float(source_profile.get('url') or 0)
    image = float(source_profile.get('image') or 0)
    breadcrumb = float(source_profile.get('breadcrumb') or 0)
    avg_len = float(source_profile.get('avg_len') or 0)
    unique = float(source_profile.get('unique') or 0)

    if _kind_compatible(target_kind, source_kind):
        return max(0.76, min(0.99, confidence or 0.80)), f'conteúdo identificado como {source_kind}'

    if target_kind in DESCRIPTION_KINDS:
        score = text * 0.65 + min(avg_len, 90) / 300
        if url >= 0.25 or price >= 0.25 or gtin >= 0.40:
            score -= 0.40
        return max(0.0, min(0.95, score)), 'amostras parecem texto de produto'
    if target_kind in PRICE_KINDS:
        return max(price, numeric * 0.55), 'amostras parecem valores/preços'
    if target_kind == 'estoque':
        score = integer if price < 0.25 and avg_len <= 10 else 0.0
        return score, 'amostras parecem saldo/quantidade inteira'
    if target_kind == 'gtin':
        return gtin, 'amostras parecem GTIN/EAN'
    if target_kind == 'ncm':
        ncm_hint = 0.92 if source_kind == 'ncm' or content_kind == 'ncm' else 0.0
        return ncm_hint, 'amostras/cabeçalho parecem NCM/classificação fiscal'
    if target_kind == 'imagem':
        return image, 'amostras parecem URLs de imagens'
    if target_kind == 'url':
        return url, 'amostras parecem links/URLs'
    if target_kind == 'marca':
        score = text * 0.55 + (0.25 if avg_len <= 45 and url == 0 and price == 0 else -0.20)
        return max(0.0, min(0.90, score)), 'amostras parecem marca/fabricante'
    if target_kind == 'fornecedor':
        score = text * 0.55 + (0.25 if avg_len <= 70 and url == 0 and unique <= 0.85 else 0.0)
        return max(0.0, min(0.88, score)), 'amostras parecem fornecedor'
    if target_kind == 'categoria':
        score = max(breadcrumb, text * 0.45 + (0.20 if avg_len <= 110 else -0.20))
        return max(0.0, min(0.88, score)), 'amostras parecem categoria/departamento'
    if target_kind in CODE_KINDS:
        score = max(numeric * 0.55, 0.72 if source_kind in CODE_KINDS else 0.0)
        if gtin >= 0.55 or price >= 0.35 or url >= 0.30:
            score -= 0.40
        return max(0.0, min(0.86, score)), 'amostras parecem código/SKU'
    return 0.0, 'sem leitura semântica suficiente'


def _score_source_for_target(source: str, target: str, profile: dict[str, object]) -> tuple[float, str]:
    target_kind = _target_kind(target)
    if target_kind == 'custom':
        exact = _compact(source) == _compact(target)
        return (1.0 if exact else 0.0), 'campo customizado exige cabeçalho idêntico'

    if bool(profile.get('header_conflict')) and float(profile.get('confidence') or 0) >= 0.70:
        source_kind = str(profile.get('kind') or '')
        if not _kind_compatible(target_kind, source_kind):
            return 0.0, str(profile.get('warning') or 'conteúdo conflita com o destino')

    header = _header_similarity(source, target, target_kind)
    content, reason = _content_score(target_kind, profile)
    combined = (header * 0.38) + (content * 0.62)
    if header >= 0.90 and content >= 0.35:
        combined = max(combined, 0.84)
    if content >= 0.88 and header >= 0.25:
        combined = max(combined, 0.82)
    return round(max(0.0, min(1.0, combined)), 3), f'cabeçalho {header:.2f}; {reason} ({content:.2f})'


def suggest_mapping(source_df: pd.DataFrame, target_df: pd.DataFrame) -> AIResult:
    source_columns = [str(column) for column in source_df.columns] if isinstance(source_df, pd.DataFrame) else []
    target_columns = [str(column) for column in target_df.columns] if isinstance(target_df, pd.DataFrame) else []
    profiles = {source: profile_as_mapping(source_df, source) for source in source_columns}

    suggestions: list[dict[str, object]] = []
    mapping: dict[str, str] = {}
    used_sources: set[str] = set()

    for target in target_columns:
        ranked = []
        for source in source_columns:
            if source in used_sources:
                continue
            score, reason = _score_source_for_target(source, target, profiles[source])
            ranked.append({'source_column': source, 'score': score, 'reason': reason, 'detected_kind': profiles[source].get('kind', '')})
        ranked = sorted(ranked, key=lambda item: float(item['score']), reverse=True)
        best = ranked[0] if ranked else {'source_column': '', 'score': 0.0, 'reason': 'sem colunas de origem'}
        confidence = float(best.get('score') or 0)
        source = str(best.get('source_column') or '') if confidence >= 0.62 else ''
        if source:
            mapping[target] = source
            used_sources.add(source)
        suggestions.append(
            {
                'target_column': target,
                'source_column': source,
                'confidence': confidence if source else 0.0,
                'reason': best.get('reason') if source else 'sem correspondência segura pelo conteúdo das linhas',
                'alternatives': ranked[:3],
                'engine': 'semantic_content_local',
            }
        )

    return AIResult(
        ok=True,
        task='mapping_suggester',
        message=f'{len(mapping)} campo(s) sugerido(s) por leitura inteligente do conteúdo das linhas.',
        data={'mapping': mapping, 'suggestions': suggestions, 'engine': 'semantic_content_local'},
    )


__all__ = ['suggest_mapping']
