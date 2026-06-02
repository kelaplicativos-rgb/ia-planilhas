from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from urllib.parse import urljoin, urlparse

import pandas as pd

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.engines.fast_site_scraper.http_client import fetch_live, fetch_many_live
from bling_app_zero.engines.fast_site_scraper.url_discovery import norm_url, split_urls

RESPONSIBLE_FILE = 'bling_app_zero/agents/api_finder.py'
API_HINT_RE = re.compile(r'''(?P<url>(?:https?:)?//[^"'\s<>]+|/[^"'\s<>]*(?:api|produto|product|catalog|estoque|stock|json)[^"'\s<>]*)''', re.I)
JSON_KEYS = ('products', 'produtos', 'items', 'data', 'results', 'rows', 'records')
MAX_API_CANDIDATES_TO_CONFIRM = 6


@dataclass(frozen=True)
class ApiCandidate:
    url: str
    score: int
    reason: str
    content_type: str = ''
    json_confirmed: bool = False


@dataclass(frozen=True)
class ApiFinderResult:
    found: bool
    platform: str
    candidates: list[ApiCandidate]
    best_url: str = ''
    message: str = ''


def _root(url: str) -> str:
    parsed = urlparse(url)
    return f'{parsed.scheme}://{parsed.netloc}' if parsed.scheme and parsed.netloc else ''


def _score_url(url: str, platform: str) -> tuple[int, str]:
    low = url.lower()
    score = 0
    reasons: list[str] = []
    for token, points in (
        ('api', 35),
        ('products.json', 34),
        ('produtos.json', 34),
        ('products', 25),
        ('produtos', 25),
        ('product', 22),
        ('produto', 22),
        ('catalog', 18),
        ('catalogo', 18),
        ('estoque', 16),
        ('stock', 16),
        ('.json', 16),
        ('graphql', 14),
    ):
        if token in low:
            score += points
            reasons.append(token)
    if low.endswith('.xml') or 'sitemap' in low:
        score -= 30
        reasons.append('xml_penalty')
    if platform in {'stoqui', 'mega_center'} and any(token in low for token in ('stoqui', 'product', 'produto', 'api')):
        score += 20
        reasons.append('platform_hint')
    if any(bad in low for bad in ('facebook', 'instagram', 'whatsapp', 'checkout', 'carrinho', 'login')):
        score -= 50
        reasons.append('blocked_hint')
    return score, ', '.join(reasons) or 'sinal fraco'


def _candidate_urls(start_url: str, html: str, platform: str) -> list[ApiCandidate]:
    root = _root(start_url)
    found: dict[str, ApiCandidate] = {}
    seeds = [
        '/api/products',
        '/api/produtos',
        '/api/catalog/products',
        '/api/catalogo/produtos',
        '/products.json',
        '/produtos.json',
        '/catalog/products.json',
        '/catalogo/produtos.json',
        '/api/v1/products',
        '/api/v1/produtos',
        '/api/v2/products',
        '/api/v2/produtos',
    ]
    for seed in seeds:
        absolute = norm_url(urljoin(root + '/', seed.lstrip('/')))
        score, reason = _score_url(absolute, platform)
        found[absolute] = ApiCandidate(absolute, score, f'endpoint padrão: {reason}')

    for match in API_HINT_RE.finditer(html or ''):
        raw = match.group('url')
        if raw.startswith('//'):
            raw = 'https:' + raw
        absolute = norm_url(urljoin(start_url, raw))
        if not absolute:
            continue
        score, reason = _score_url(absolute, platform)
        if score <= 0:
            continue
        current = found.get(absolute)
        candidate = ApiCandidate(absolute, score, f'descoberto no HTML/JS: {reason}')
        if current is None or candidate.score > current.score:
            found[absolute] = candidate
    return sorted(found.values(), key=lambda item: item.score, reverse=True)[:25]


def _json_payload(raw: str) -> object | None:
    text = str(raw or '').strip()
    if not text:
        return None
    if not (text.startswith('{') or text.startswith('[')):
        return None
    try:
        return json.loads(text)
    except Exception:
        return None


def _extract_rows_from_payload(payload: object, max_items: int = 500) -> list[dict[str, object]]:
    data = payload
    for key in JSON_KEYS:
        if isinstance(data, dict) and isinstance(data.get(key), list):
            data = data[key]
            break
    if isinstance(data, dict):
        nested_lists = [value for value in data.values() if isinstance(value, list)]
        if nested_lists:
            data = max(nested_lists, key=len)
    if not isinstance(data, list):
        return []
    rows: list[dict[str, object]] = []
    for item in data[:max_items]:
        if isinstance(item, dict):
            rows.append(item)
    return rows


def _confirm_json_candidate(candidate: ApiCandidate, raw: str, max_items: int = 3) -> ApiCandidate:
    payload = _json_payload(raw)
    if payload is None:
        return candidate
    rows = _extract_rows_from_payload(payload, max_items=max_items)
    bonus = 80 if rows else 35
    reason = f'{candidate.reason}; JSON confirmado' + (f' com {len(rows)} registro(s) de amostra' if rows else '')
    return ApiCandidate(
        url=candidate.url,
        score=candidate.score + bonus,
        reason=reason,
        content_type='json',
        json_confirmed=True,
    )


def _confirm_candidates(candidates: list[ApiCandidate]) -> list[ApiCandidate]:
    top = candidates[:MAX_API_CANDIDATES_TO_CONFIRM]
    if not top:
        return []
    fetched = fetch_many_live([candidate.url for candidate in top], timeout=3, workers=min(6, len(top)))
    confirmed: list[ApiCandidate] = []
    by_url = {candidate.url: candidate for candidate in top}
    for url, raw in fetched.items():
        candidate = by_url.get(url)
        if candidate is None:
            continue
        confirmed.append(_confirm_json_candidate(candidate, raw))
    for candidate in top:
        if candidate.url not in fetched:
            confirmed.append(candidate)
    return confirmed


def find_site_api(raw_urls: str, platform: str = 'generico') -> ApiFinderResult:
    starts = [norm_url(url) for url in split_urls(raw_urls) if norm_url(url)]
    if not starts:
        return ApiFinderResult(False, platform, [], message='Nenhuma URL válida para procurar API interna.')

    all_candidates: dict[str, ApiCandidate] = {}
    for start in starts[:3]:
        html = fetch_live(start, timeout=4)
        for candidate in _candidate_urls(start, html, platform):
            current = all_candidates.get(candidate.url)
            if current is None or candidate.score > current.score:
                all_candidates[candidate.url] = candidate

    raw_candidates = sorted(all_candidates.values(), key=lambda item: item.score, reverse=True)[:12]
    confirmed = _confirm_candidates(raw_candidates)

    candidates = sorted(confirmed, key=lambda item: (item.json_confirmed, item.score), reverse=True)[:20]
    best_candidate = candidates[0] if candidates and candidates[0].json_confirmed and candidates[0].score >= 70 else None
    best = best_candidate.url if best_candidate else ''
    result = ApiFinderResult(
        found=bool(best),
        platform=platform,
        candidates=candidates,
        best_url=best,
        message='API JSON interna confirmada.' if best else 'Nenhuma API JSON confiável encontrada; usar scraper seguro.',
    )
    add_audit_event(
        'api_finder_finished',
        area='SITE',
        step='entrada',
        status='OK' if result.found else 'INFO',
        details={
            'platform': platform,
            'found': result.found,
            'best_url': result.best_url,
            'confirmed_candidates': sum(1 for item in result.candidates if item.json_confirmed),
            'candidates': [asdict(item) for item in result.candidates[:10]],
            'responsible_file': RESPONSIBLE_FILE,
        },
    )
    return result


def try_read_api_table(result: ApiFinderResult, max_items: int = 500) -> pd.DataFrame:
    if not result.found or not result.best_url:
        return pd.DataFrame()
    raw = fetch_live(result.best_url, timeout=5)
    payload = _json_payload(raw)
    if payload is None:
        return pd.DataFrame()
    rows = _extract_rows_from_payload(payload, max_items=max_items)
    return pd.DataFrame(rows).fillna('') if rows else pd.DataFrame()


__all__ = ['ApiCandidate', 'ApiFinderResult', 'find_site_api', 'try_read_api_table']
