from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import pandas as pd

RESPONSIBLE_FILE = 'bling_app_zero/core/final_video_link_guard.py'

VIDEO_HOST_TERMS = (
    'youtube.com',
    'youtu.be',
    'vimeo.com',
    'tiktok.com',
    'instagram.com/reel',
    'instagram.com/p/',
    'facebook.com/watch',
    'fb.watch',
    'dailymotion.com',
    'kwai.com',
)
VIDEO_EXTENSIONS = (
    '.mp4', '.mov', '.avi', '.mkv', '.webm', '.m4v', '.3gp', '.wmv', '.flv', '.m3u8'
)
VIDEO_COLUMN_TERMS = (
    'video', 'vídeo', 'videos', 'vídeos', 'url video', 'url vídeo', 'link video', 'link vídeo'
)
MEDIA_COLUMN_TERMS = (
    'imagem', 'imagens', 'image', 'images', 'foto', 'fotos', 'midia', 'mídia', 'media', 'url imagens'
)
URL_RE = re.compile(r'https?://[^\s|;,"\'<>)]+' , flags=re.IGNORECASE)
SPLIT_RE = re.compile(r'\s*\|\s*|\s*[\n\r,;]+\s*')


@dataclass(frozen=True)
class VideoLinkGuardResult:
    df: pd.DataFrame
    changed: int = 0
    video_links_removed: int = 0
    columns: tuple[str, ...] = ()
    message: str = ''


def _safe_text(value: Any) -> str:
    try:
        if pd.isna(value):
            return ''
    except Exception:
        pass
    return str(value if value is not None else '').strip()


def _norm(value: Any) -> str:
    text = _safe_text(value).lower()
    for old, new in {
        'í': 'i', 'é': 'e', 'ê': 'e', 'ã': 'a', 'á': 'a', 'à': 'a', 'â': 'a',
        'ô': 'o', 'ó': 'o', 'õ': 'o', 'ú': 'u', 'ç': 'c',
    }.items():
        text = text.replace(old, new)
    return ' '.join(re.sub(r'[^a-z0-9]+', ' ', text).split())


def looks_like_video_column(column: object) -> bool:
    key = _norm(column)
    return any(_norm(term) in key for term in VIDEO_COLUMN_TERMS)


def looks_like_media_column(column: object) -> bool:
    key = _norm(column)
    return any(_norm(term) in key for term in MEDIA_COLUMN_TERMS) or looks_like_video_column(column)


def is_video_link(value: Any) -> bool:
    text = _safe_text(value).lower().strip('"\'[]()')
    if not text.startswith(('http://', 'https://')):
        return False
    parsed = urlparse(text)
    host_path = f'{parsed.netloc}{parsed.path}'.lower()
    if any(term in host_path for term in VIDEO_HOST_TERMS):
        return True
    clean_path = parsed.path.lower().split('?', 1)[0].split('#', 1)[0]
    return clean_path.endswith(VIDEO_EXTENSIONS)


def _split_urlish_parts(value: Any) -> list[str]:
    text = _safe_text(value)
    if not text:
        return []
    return [part.strip().strip('"\'[]()') for part in SPLIT_RE.split(text) if part.strip()]


def _clean_media_cell(value: Any) -> tuple[str, int]:
    parts = _split_urlish_parts(value)
    if not parts:
        return _safe_text(value), 0
    kept: list[str] = []
    removed = 0
    for part in parts:
        if is_video_link(part):
            removed += 1
            continue
        kept.append(part)
    if removed:
        return '|'.join(kept), removed
    return _safe_text(value), 0


def _clean_text_cell(value: Any) -> tuple[str, int]:
    text = _safe_text(value)
    if not text:
        return '', 0
    removed = 0

    def repl(match: re.Match[str]) -> str:
        nonlocal removed
        url = match.group(0).strip()
        if is_video_link(url):
            removed += 1
            return ''
        return url

    cleaned = URL_RE.sub(repl, text)
    cleaned = re.sub(r'\s{2,}', ' ', cleaned).strip(' |,;')
    return cleaned, removed


def apply_video_link_guard_resource(df: pd.DataFrame | None) -> VideoLinkGuardResult:
    out = df.copy().fillna('') if isinstance(df, pd.DataFrame) else pd.DataFrame()
    if out.empty:
        return VideoLinkGuardResult(out, message='Sem dados para validar links de vídeo.')

    changed = 0
    removed = 0
    touched_columns: list[str] = []

    for column in list(out.columns):
        column_name = str(column)
        before = out[column].fillna('').astype(str).tolist()
        new_values: list[str] = []
        column_removed = 0

        if looks_like_video_column(column_name):
            for value in before:
                text = _safe_text(value)
                if text:
                    urls = URL_RE.findall(text)
                    column_removed += max(1, sum(1 for url in urls if is_video_link(url)))
                new_values.append('')
        elif looks_like_media_column(column_name):
            for value in before:
                cleaned, count = _clean_media_cell(value)
                column_removed += count
                new_values.append(cleaned)
        else:
            for value in before:
                cleaned, count = _clean_text_cell(value)
                column_removed += count
                new_values.append(cleaned)

        if column_removed:
            out[column] = new_values
            after = out[column].fillna('').astype(str).tolist()
            changed += sum(1 for old, new in zip(before, after) if old != new)
            removed += column_removed
            touched_columns.append(column_name)

    return VideoLinkGuardResult(
        out.copy().fillna(''),
        changed=changed,
        video_links_removed=removed,
        columns=tuple(touched_columns),
        message=f'{removed} link(s) de vídeo removido(s) em {changed} célula(s).',
    )


__all__ = [
    'RESPONSIBLE_FILE',
    'VIDEO_EXTENSIONS',
    'VIDEO_HOST_TERMS',
    'VideoLinkGuardResult',
    'apply_video_link_guard_resource',
    'is_video_link',
    'looks_like_media_column',
    'looks_like_video_column',
]
