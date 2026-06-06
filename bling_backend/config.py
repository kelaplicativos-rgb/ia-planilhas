from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class BlingOAuthConfig:
    client_id: str
    client_secret: str
    redirect_uri: str
    authorize_url: str = 'https://api.bling.com.br/Api/v3/oauth/authorize'
    token_url: str = 'https://api.bling.com.br/Api/v3/oauth/token'
    frontend_return_url: str = 'https://ia-planilhas.streamlit.app/'
    backend_shared_secret: str = ''

    @property
    def ready(self) -> bool:
        return bool(self.client_id and self.client_secret and self.redirect_uri)


def _env(*names: str, default: str = '') -> str:
    for name in names:
        value = os.getenv(name)
        if value:
            return value.strip()
    return default.strip()


def _normalize_bling_url(value: str, fallback: str) -> str:
    text = str(value or fallback or '').strip()
    if text.startswith('https://www.bling.com.br/Api/v3'):
        text = text.replace('https://www.bling.com.br/Api/v3', 'https://api.bling.com.br/Api/v3', 1)
    return text or fallback


def load_config() -> BlingOAuthConfig:
    authorize_url = _env('BLING_AUTHORIZE_URL', 'BLING_OAUTH_AUTHORIZE_URL', default='https://api.bling.com.br/Api/v3/oauth/authorize')
    token_url = _env('BLING_TOKEN_URL', 'BLING_OAUTH_TOKEN_URL', default='https://api.bling.com.br/Api/v3/oauth/token')
    return BlingOAuthConfig(
        client_id=_env('BLING_CLIENT_ID', 'BLING_OAUTH_CLIENT_ID', 'client_id'),
        client_secret=_env('BLING_CLIENT_SECRET', 'BLING_OAUTH_CLIENT_SECRET', 'client_secret'),
        redirect_uri=_env('BLING_REDIRECT_URI', 'BLING_CALLBACK_URL', 'redirect_uri'),
        authorize_url=_normalize_bling_url(authorize_url, 'https://api.bling.com.br/Api/v3/oauth/authorize'),
        token_url=_normalize_bling_url(token_url, 'https://api.bling.com.br/Api/v3/oauth/token'),
        frontend_return_url=_env('FRONTEND_RETURN_URL', 'STREAMLIT_RETURN_URL', default='https://ia-planilhas.streamlit.app/'),
        backend_shared_secret=_env('BLING_BACKEND_SHARED_SECRET', 'BACKEND_SHARED_SECRET', 'backend_shared_secret'),
    )
