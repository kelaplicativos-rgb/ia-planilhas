from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class BlingOAuthConfig:
    client_id: str
    client_secret: str
    redirect_uri: str
    authorize_url: str = 'https://www.bling.com.br/Api/v3/oauth/authorize'
    token_url: str = 'https://www.bling.com.br/Api/v3/oauth/token'
    frontend_return_url: str = 'https://ia-planilhas.streamlit.app/'

    @property
    def ready(self) -> bool:
        return bool(self.client_id and self.client_secret and self.redirect_uri)


def _env(*names: str, default: str = '') -> str:
    for name in names:
        value = os.getenv(name)
        if value:
            return value.strip()
    return default.strip()


def load_config() -> BlingOAuthConfig:
    return BlingOAuthConfig(
        client_id=_env('BLING_CLIENT_ID', 'BLING_OAUTH_CLIENT_ID', 'client_id'),
        client_secret=_env('BLING_CLIENT_SECRET', 'BLING_OAUTH_CLIENT_SECRET', 'client_secret'),
        redirect_uri=_env('BLING_REDIRECT_URI', 'BLING_CALLBACK_URL', 'redirect_uri'),
        authorize_url=_env('BLING_AUTHORIZE_URL', 'BLING_OAUTH_AUTHORIZE_URL', default='https://www.bling.com.br/Api/v3/oauth/authorize'),
        token_url=_env('BLING_TOKEN_URL', 'BLING_OAUTH_TOKEN_URL', default='https://www.bling.com.br/Api/v3/oauth/token'),
        frontend_return_url=_env('FRONTEND_RETURN_URL', 'STREAMLIT_RETURN_URL', default='https://ia-planilhas.streamlit.app/'),
    )
