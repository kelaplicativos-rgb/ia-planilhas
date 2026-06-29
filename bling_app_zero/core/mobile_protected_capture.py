from __future__ import annotations

import io
import os
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urljoin, urlparse, urlunparse

import httpx
import pandas as pd
from bs4 import BeautifulSoup

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.html_product_extractor import clean_text, normalize_key, read_html_product_text

RESPONSIBLE_FILE = 'bling_app_zero/core/mobile_protected_capture.py'
USER_AGENT = 'Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Mobile Safari/537.36'
BLOCKED_STATUS_CODES = {401, 403, 407, 423, 429}
LOGIN_WORD_RE = re.compile(r'\b(login|entrar|acessar|senha|password|usuario|usuário|e-mail|email)\b', re.I)
NEXT_TEXT_RE = re.compile(r'\b(proxima|próxima|proximo|próximo|next|avancar|avançar)\b|[›»]', re.I)
PRODUCT_HINT_RE = re.compile(r'\b(produto|produtos|sku|estoque|preço|preco|valor|marca|modelo)\b', re.I)
KEY_PRIORITY = (
    'sku', 'codigo produto', 'código produto', 'codigo', 'código', 'id produto', 'gtin', 'ean', 'url'
)


@dataclass
class MobileCaptureResult:
    status: str
    message: str
    df: pd.DataFrame = field(default_factory=pd.DataFrame)
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.status == 'ok' and isinstance(self.df, pd.DataFrame) and not self.df.empty

    @property
    def should_try_public_engine(self) -> bool:
        return self.status in {'blocked_direct_capture', 'http_error', 'empty'}


def _valid_url(url: str) -> bool:
    parsed = urlparse(str(url or '').strip())
    return parsed.scheme in {'http', 'https'} and bool(parsed.netloc)


def _get_secret(name: str) -> str:
    value = str(os.environ.get(name) or '').strip()
    if value:
        return value
    try:
        import streamlit as st
        return str(st.secrets.get(name, '') or '').strip()
    except Exception:
        return ''


def _remote_endpoint() -> str:
    return _get_secret('MAPEIAAI_MOBILE_CAPTURE_ENDPOINT') or _get_secret('MAPEIAAI_REMOTE_BROWSER_ENDPOINT')


def _remote_token() -> str:
    return _get_secret('MAPEIAAI_MOBILE_CAPTURE_TOKEN') or _get_secret('MAPEIAAI_REMOTE_BROWSER_TOKEN')


def _default_headers(*, accept_json: bool = False) -> dict[str, str]:
    return {
        'User-Agent': USER_AGENT,
        'Accept': 'application/json' if accept_json else 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
        'Cache-Control': 'no-cache',
        'Pragma': 'no-cache',
        'Upgrade-Insecure-Requests': '1',
    }


def _host(url: str) -> str:
    return urlparse(str(url or '')).netloc or 'site informado'


def _looks_like_login_html(html: str) -> bool:
    text = clean_text(BeautifulSoup(html or '', 'html.parser').get_text(' ', strip=True))
    low = str(html or '').lower()
    has_password = 'type="password"' in low or "type='password'" in low or 'type=password' in low
    has_form = '<form' in low
    has_product_hint = bool(PRODUCT_HINT_RE.search(text))
    return bool(has_password or (has_form and LOGIN_WORD_RE.search(text) and not has_product_hint))


def _blocked_message(url: str, status_code: int | str) -> str:
    return f'O site {_host(url)} bloqueou a captura direta ({status_code}). Vou tentar a busca pública inteligente do MapeiaAI automaticamente.'


def _http_error_message(url: str, status_code: int | str) -> str:
    return f'O site {_host(url)} respondeu HTTP {status_code}. Vou encaminhar para a busca pública inteligente do MapeiaAI.'


def _start_url_variants(url: str) -> list[str]:
    parsed = urlparse(str(url or '').strip())
    if not parsed.scheme or not parsed.netloc:
        return []
    variants: list[str] = []

    def add(candidate) -> None:
        text = str(candidate or '').strip()
        if text and text not in variants:
            variants.append(text)

    add(urlunparse(parsed))
    host = parsed.netloc
    alt_host = host[4:] if host.startswith('www.') else f'www.{host}'
    add(urlunparse(parsed._replace(netloc=alt_host)))
    if not parsed.path or parsed.path == '':
        add(urlunparse(parsed._replace(path='/')))
        add(urlunparse(parsed._replace(netloc=alt_host, path='/')))
    return variants[:4]


def _key_column(df: pd.DataFrame) -> str:
    if not isinstance(df, pd.DataFrame) or len(df.columns) == 0:
        return ''
    normalized = {normalize_key(column): column for column in map(str, df.columns)}
    for key in KEY_PRIORITY:
        wanted = normalize_key(key)
        if wanted in normalized:
            return str(normalized[wanted])
    for key in KEY_PRIORITY:
        wanted = normalize_key(key)
        for column in map(str, df.columns):
            if wanted and wanted in normalize_key(column):
                return column
    return ''


def _merge_frames(frames: list[pd.DataFrame]) -> pd.DataFrame:
    valid = [frame.copy().fillna('').astype(str) for frame in frames if isinstance(frame, pd.DataFrame) and not frame.empty and len(frame.columns)]
    if not valid:
        return pd.DataFrame()
    merged = pd.concat(valid, ignore_index=True, sort=False).fillna('').astype(str)
    key_col = _key_column(merged)
    before = int(len(merged))
    if key_col:
        non_empty = merged[key_col].map(lambda value: bool(clean_text(value)))
        with_key = merged[non_empty].drop_duplicates(subset=[key_col], keep='first')
        without_key = merged[~non_empty]
        merged = pd.concat([with_key, without_key], ignore_index=True, sort=False).fillna('').astype(str)
    add_audit_event(
        'mobile_capture_frames_merged',
        area='ORIGEM',
        status='OK',
        details={
            'frames': len(valid),
            'rows_before_dedupe': before,
            'rows_after_dedupe': int(len(merged)),
            'key_column': key_col,
            'responsible_file': RESPONSIBLE_FILE,
        },
    )
    return merged.reset_index(drop=True)


def _same_origin(base_url: str, candidate_url: str) -> bool:
    base = urlparse(base_url)
    candidate = urlparse(candidate_url)
    return candidate.scheme in {'http', 'https'} and candidate.netloc == base.netloc


def _candidate_page_urls(html: str, current_url: str) -> list[str]:
    soup = BeautifulSoup(html or '', 'html.parser')
    urls: list[str] = []
    for link in soup.find_all('a', href=True):
        href = clean_text(link.get('href'))
        if not href or href.startswith(('#', 'javascript:', 'mailto:', 'tel:')):
            continue
        absolute = urljoin(current_url, href)
        if not _same_origin(current_url, absolute):
            continue
        text = clean_text(link.get_text(' ', strip=True))
        rel = ' '.join(link.get('rel') or []) if isinstance(link.get('rel'), list) else clean_text(link.get('rel'))
        query = urlparse(absolute).query.lower()
        if rel.lower() == 'next' or NEXT_TEXT_RE.search(text) or 'page=' in query or 'pagina=' in query or 'p=' in query:
            if absolute not in urls:
                urls.append(absolute)
    return urls[:40]


def _read_html_to_frame(html: str) -> pd.DataFrame:
    try:
        df = read_html_product_text(html or '')
    except Exception:
        return pd.DataFrame()
    return df.fillna('').astype(str) if isinstance(df, pd.DataFrame) else pd.DataFrame()


def _frame_from_remote_payload(payload: Any) -> pd.DataFrame:
    if isinstance(payload, list):
        return pd.DataFrame(payload).fillna('').astype(str)
    if not isinstance(payload, dict):
        return pd.DataFrame()
    rows = payload.get('rows') or payload.get('data') or payload.get('produtos') or payload.get('products')
    if isinstance(rows, list):
        return pd.DataFrame(rows).fillna('').astype(str)
    csv_text = payload.get('csv') or payload.get('table_csv')
    if isinstance(csv_text, str) and csv_text.strip():
        sep = ';' if csv_text[:4096].count(';') >= csv_text[:4096].count(',') else ','
        try:
            return pd.read_csv(io.StringIO(csv_text), sep=sep, dtype=str).fillna('').astype(str)
        except Exception:
            return pd.DataFrame()
    html = payload.get('html')
    if isinstance(html, str) and html.strip():
        return _read_html_to_frame(html)
    html_parts = payload.get('html_parts')
    if isinstance(html_parts, list):
        return _merge_frames([_read_html_to_frame(str(part or '')) for part in html_parts])
    return pd.DataFrame()


def _remote_capture(url: str, max_pages: int) -> MobileCaptureResult | None:
    endpoint = _remote_endpoint()
    if not endpoint:
        return None
    headers = _default_headers(accept_json=True)
    token = _remote_token()
    if token:
        headers['Authorization'] = f'Bearer {token}'
    try:
        with httpx.Client(timeout=180, follow_redirects=True, headers=headers) as client:
            response = client.post(endpoint, json={'url': url, 'max_pages': max_pages, 'format': 'mhtml'})
            if response.status_code in BLOCKED_STATUS_CODES:
                return MobileCaptureResult('remote_blocked', 'O navegador seguro remoto não conseguiu abrir esse site agora.', details={'status_code': response.status_code, 'remote': True})
            response.raise_for_status()
            payload = response.json()
    except Exception as exc:
        add_audit_event(
            'mobile_capture_remote_failed',
            area='ORIGEM',
            status='AVISO',
            details={'error': str(exc)[:220], 'responsible_file': RESPONSIBLE_FILE},
        )
        return MobileCaptureResult('remote_error', 'O navegador seguro não respondeu. Vou tentar outro caminho de captura.', details={'error': str(exc)[:220]})
    df = _frame_from_remote_payload(payload)
    if isinstance(df, pd.DataFrame) and not df.empty:
        return MobileCaptureResult('ok', 'Captura mobile concluída pelo navegador seguro.', df=df, details={'remote': True, 'rows': int(len(df))})
    return MobileCaptureResult('empty', 'O navegador seguro abriu o site, mas não retornou produtos em tabela.', details={'remote': True})


def _direct_public_capture(url: str, max_pages: int) -> MobileCaptureResult:
    frames: list[pd.DataFrame] = []
    seen_urls: set[str] = set()
    queue: list[str] = _start_url_variants(url) or [url]
    fetched = 0
    attempts = 0
    blocked: list[dict[str, object]] = []
    try:
        with httpx.Client(timeout=35, follow_redirects=True, headers=_default_headers()) as client:
            while queue and fetched < max(1, min(int(max_pages or 1), 500)):
                current = queue.pop(0)
                if current in seen_urls:
                    continue
                seen_urls.add(current)
                attempts += 1
                response = client.get(current)
                if response.status_code in BLOCKED_STATUS_CODES:
                    blocked.append({'url': current, 'status_code': response.status_code})
                    add_audit_event(
                        'mobile_capture_direct_blocked_by_site',
                        area='ORIGEM',
                        status='AVISO',
                        details={'url_host': _host(current), 'status_code': int(response.status_code), 'attempts': attempts, 'responsible_file': RESPONSIBLE_FILE},
                    )
                    continue
                if response.status_code >= 400:
                    return MobileCaptureResult('http_error', _http_error_message(current, response.status_code), details={'status_code': response.status_code, 'pages_checked': fetched, 'attempts': attempts})
                html = response.text or ''
                fetched += 1
                if fetched == 1 and _looks_like_login_html(html):
                    return MobileCaptureResult(
                        'needs_secure_browser',
                        'Este site parece exigir login. Vou tentar o navegador seguro ou a busca pública inteligente.',
                        details={'pages_checked': fetched, 'requires_login': True, 'attempts': attempts},
                    )
                frame = _read_html_to_frame(html)
                if isinstance(frame, pd.DataFrame) and not frame.empty:
                    frame = frame.copy().fillna('').astype(str)
                    if 'Página origem' not in frame.columns:
                        frame['Página origem'] = str(fetched)
                    if 'URL origem' not in frame.columns:
                        frame['URL origem'] = current
                    frames.append(frame)
                for candidate in _candidate_page_urls(html, current):
                    if candidate not in seen_urls and candidate not in queue:
                        queue.append(candidate)
    except httpx.HTTPError as exc:
        return MobileCaptureResult('network_error', f'Não consegui acessar o site pelo modo mobile. Vou tentar a busca pública inteligente.', details={'error': str(exc)[:220], 'pages_checked': fetched, 'attempts': attempts})
    except Exception as exc:
        return MobileCaptureResult('error', 'Não consegui capturar direto no modo mobile. Vou tentar a busca pública inteligente.', details={'error': str(exc)[:220], 'pages_checked': fetched, 'attempts': attempts})

    merged = _merge_frames(frames)
    if isinstance(merged, pd.DataFrame) and not merged.empty:
        return MobileCaptureResult('ok', 'Captura mobile concluída dentro do sistema.', df=merged, details={'pages_checked': fetched, 'rows': int(len(merged)), 'remote': False, 'attempts': attempts})
    if blocked:
        first = blocked[0]
        return MobileCaptureResult(
            'blocked_direct_capture',
            _blocked_message(str(first.get('url') or url), first.get('status_code') or 'bloqueio'),
            details={'blocked': blocked[:5], 'pages_checked': fetched, 'attempts': attempts, 'fallback': 'public_site_engine'},
        )
    return MobileCaptureResult('empty', 'O site foi acessado, mas não encontrei uma tabela/lista de produtos aproveitável. Vou tentar a busca pública inteligente.', details={'pages_checked': fetched, 'attempts': attempts, 'fallback': 'public_site_engine'})


def capture_url_on_mobile(url: str, max_pages: int = 80) -> MobileCaptureResult:
    clean_url = clean_text(url)
    if not _valid_url(clean_url):
        return MobileCaptureResult('invalid_url', 'Informe um site começando com http:// ou https://.')

    remote = _remote_capture(clean_url, max_pages=max_pages)
    if remote is not None and remote.ok:
        add_audit_event('mobile_capture_remote_loaded', area='ORIGEM', status='OK', details={'rows': int(len(remote.df)), 'responsible_file': RESPONSIBLE_FILE})
        return remote

    direct = _direct_public_capture(clean_url, max_pages=max_pages)
    if direct.ok:
        add_audit_event('mobile_capture_direct_loaded', area='ORIGEM', status='OK', details={'rows': int(len(direct.df)), **direct.details, 'responsible_file': RESPONSIBLE_FILE})
        return direct

    if direct.status == 'needs_secure_browser' and not _remote_endpoint():
        add_audit_event('mobile_capture_secure_browser_missing', area='ORIGEM', status='AVISO', details={'url_host': urlparse(clean_url).netloc, 'responsible_file': RESPONSIBLE_FILE})
    return remote if remote is not None and remote.status not in {'remote_error', 'remote_blocked'} and not direct.should_try_public_engine else direct


__all__ = ['MobileCaptureResult', 'capture_url_on_mobile']
