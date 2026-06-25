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
STRICT_KINDS = {'ncm', 'gtin', 'codigo', 'id_produto', 'estoque', 'preco_unitario', 'preco_custo'}

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


def _kind_group(kind: str) -> set[str]:
    groups = [DESCRIPTION_KINDS, PRICE_KINDS, CODE_KINDS, URL_KINDS, {'gtin'}, {'ncm'}, {'marca'}, {'categoria'}, {'fornecedor'}, {'estoque'}]
    for group in groups:
        if kind in group:
            return set(group)
    return {kind}


def _kind_compatible(target_kind: str, source_kind: str) -> bool:
    if target_kind == source_kind and target_kind != 'custom':
        return True
    if not target_kind or not source_kind or target_kind == 'custom' or source_kind == 'custom':
        return False
    return bool(_kind_group(target_kind) & _kind_group(source_kind))


def _header_similarity(source: str, target: str, target_kind: str) -> float:
    source_key = normalize_key(source)
    target_key = normalize_key(target)
    if not source_key or not target_key:
        return 0.0
    if _compact(source_key) == _compact(target_key):
        return 1.0
    if source_key in target_key or target_key in source_key:
        return 0.88
    source_kind = infer_kind(source)
    if _kind_compatible(target_kind, source_kind):
        return 0.86
    aliases = TARGET_ALIASES.get(target_kind, ())
    if any(normalize_key(alias) in source_key for alias in aliases):
        return 0.84
    return round(SequenceMatcher(None, source_key, target_key).ratio(), 3)


def _header_confirms_target(source: str, target: str, target_kind: str, profile: dict[str, object]) -> tuple[bool, float, str]:
    if target_kind == 'custom':
        exact = _compact(source) == _compact(target)
        return exact, 1.0 if exact else 0.0, 'campo customizado exige cabeçalho idêntico'
    header_kind = str(profile.get('header_kind') or infer_kind(source) or '')
    similarity = _header_similarity(source, target, target_kind)
    if _kind_compatible(target_kind, header_kind):
        return True, max(0.86, similarity), f'cabeçalho confirma {header_kind}'
    if similarity >= 0.82:
        return True, similarity, 'cabeçalho semelhante ao destino'
    return False, similarity, f'cabeçalho não confirma {target_kind}'


def _content_validation(target_kind: str, profile: dict[str, object]) -> tuple[bool, float, str]:
    if not bool(profile.get('has_values')):
        return False, 0.0, 'sem conteúdo preenchido para validar'
    content_kind = str(profile.get('content_kind') or '')
    effective_kind = str(profile.get('kind') or '')
    confidence = float(profile.get('confidence') or 0)
    text = float(profile.get('text') or 0)
    numeric = float(profile.get('numeric') or 0)
    integer = float(profile.get('integer') or 0)
    price = float(profile.get('price') or 0)
    gtin = float(profile.get('gtin') or 0)
    ncm = float(profile.get('ncm') or 0)
    url = float(profile.get('url') or 0)
    image = float(profile.get('image') or 0)
    breadcrumb = float(profile.get('breadcrumb') or 0)
    avg_len = float(profile.get('avg_len') or 0)
    unique = float(profile.get('unique') or 0)

    if _kind_compatible(target_kind, content_kind) or _kind_compatible(target_kind, effective_kind):
        return True, max(0.70, min(0.99, confidence or 0.80)), f'conteúdo valida {content_kind or effective_kind}'

    if target_kind in DESCRIPTION_KINDS:
        if text >= 0.45 and price < 0.25 and gtin < 0.35 and ncm < 0.35 and url < 0.20 and image < 0.20:
            score = min(0.95, 0.55 + text * 0.25 + min(avg_len, 120) / 500)
            return True, score, 'conteúdo textual compatível com descrição/título'
        return False, 0.0, 'conteúdo não valida descrição'
    if target_kind in PRICE_KINDS:
        if price >= 0.45 or numeric >= 0.80:
            return True, max(price, numeric * 0.75), 'conteúdo valida preço/valor'
        return False, 0.0, 'conteúdo não valida preço'
    if target_kind == 'estoque':
        if integer >= 0.70 and price < 0.25 and avg_len <= 10:
            return True, min(0.94, 0.55 + integer * 0.35), 'conteúdo valida estoque/saldo inteiro'
        return False, 0.0, 'conteúdo não valida estoque'
    if target_kind == 'gtin':
        if gtin >= 0.55:
            return True, min(0.99, 0.70 + gtin * 0.25), 'conteúdo valida GTIN/EAN'
        return False, 0.0, 'conteúdo não valida GTIN/EAN'
    if target_kind == 'ncm':
        if ncm >= 0.55:
            return True, min(0.99, 0.70 + ncm * 0.25), 'conteúdo valida NCM'
        return False, 0.0, 'conteúdo não valida NCM'
    if target_kind == 'imagem':
        if image >= 0.30:
            return True, min(0.98, 0.65 + image * 0.30), 'conteúdo valida URL de imagem'
        return False, 0.0, 'conteúdo não valida imagem'
    if target_kind == 'url':
        if url >= 0.60:
            return True, min(0.97, 0.60 + url * 0.30), 'conteúdo valida URL/link'
        return False, 0.0, 'conteúdo não valida URL'
    if target_kind == 'marca':
        if text >= 0.40 and avg_len <= 45 and price < 0.10 and url < 0.10 and image < 0.10:
            return True, min(0.88, 0.50 + text * 0.25 + (0.10 if unique <= 0.85 else 0.0)), 'conteúdo valida marca/fabricante'
        return False, 0.0, 'conteúdo não valida marca'
    if target_kind == 'fornecedor':
        if text >= 0.40 and avg_len <= 80 and price < 0.10 and url < 0.10 and image < 0.10:
            return True, min(0.88, 0.50 + text * 0.25 + (0.10 if unique <= 0.90 else 0.0)), 'conteúdo valida fornecedor'
        return False, 0.0, 'conteúdo não valida fornecedor'
    if target_kind == 'categoria':
        if breadcrumb >= 0.25 or (text >= 0.45 and avg_len <= 110 and price < 0.10 and url < 0.10 and image < 0.10):
            return True, min(0.88, max(breadcrumb, text * 0.45 + 0.20)), 'conteúdo valida categoria/departamento'
        return False, 0.0, 'conteúdo não valida categoria'
    if target_kind in CODE_KINDS:
        if price >= 0.35 or gtin >= 0.55 or ncm >= 0.55 or url >= 0.30 or image >= 0.30:
            return False, 0.0, 'conteúdo conflita com código/SKU'
        if numeric >= 0.40 or text >= 0.20:
            return True, min(0.86, 0.45 + max(numeric, text * 0.60) * 0.35), 'conteúdo valida código/SKU'
        return False, 0.0, 'conteúdo não valida código/SKU'
    return False, 0.0, 'sem validação de conteúdo para o destino'


def _score_source_for_target(source: str, target: str, profile: dict[str, object]) -> tuple[float, str]:
    target_kind = _target_kind(target)
    header_ok, header_score, header_reason = _header_confirms_target(source, target, target_kind, profile)
    if not header_ok:
        return 0.0, header_reason
    content_ok, content_score, content_reason = _content_validation(target_kind, profile)
    if not content_ok:
        return 0.0, f'{header_reason}; bloqueado: {content_reason}'
    if bool(profile.get('header_conflict')) and float(profile.get('confidence') or 0) >= 0.70:
        content_kind = str(profile.get('content_kind') or '')
        if not _kind_compatible(target_kind, content_kind):
            return 0.0, str(profile.get('warning') or 'cabeçalho e conteúdo conflitam')
    final = round(min(1.0, max(0.0, (header_score * 0.60) + (content_score * 0.40))), 3)
    if target_kind in STRICT_KINDS and header_score < 0.82:
        return 0.0, f'{header_reason}; campo crítico exige cabeçalho claro'
    return final, f'{header_reason}; {content_reason}'


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
            ranked.append({'source_column': source, 'score': score, 'reason': reason, 'detected_kind': profiles[source].get('kind', ''), 'header_kind': profiles[source].get('header_kind', ''), 'content_kind': profiles[source].get('content_kind', '')})
        ranked = sorted(ranked, key=lambda item: float(item['score']), reverse=True)
        best = ranked[0] if ranked else {'source_column': '', 'score': 0.0, 'reason': 'sem colunas de origem'}
        confidence = float(best.get('score') or 0)
        source = str(best.get('source_column') or '') if confidence >= 0.70 else ''
        if source:
            mapping[target] = source
            used_sources.add(source)
        suggestions.append(
            {
                'target_column': target,
                'source_column': source,
                'confidence': confidence if source else 0.0,
                'reason': best.get('reason') if source else 'sem correspondência segura: cabeçalho não confirmou ou conteúdo não validou',
                'alternatives': ranked[:3],
                'engine': 'header_confirmed_content_validated',
            }
        )

    return AIResult(
        ok=True,
        task='mapping_suggester',
        message=f'{len(mapping)} campo(s) sugerido(s) por cabeçalho confirmado e conteúdo validado.',
        data={'mapping': mapping, 'suggestions': suggestions, 'engine': 'header_confirmed_content_validated'},
    )


__all__ = ['suggest_mapping']
