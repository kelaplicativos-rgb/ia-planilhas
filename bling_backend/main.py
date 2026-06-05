from __future__ import annotations

import base64
import secrets
from urllib.parse import urlencode

import requests
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from bling_backend.config import load_config
from bling_backend.token_store import clear_token, load_token, save_token

app = FastAPI(title='MapeiaAI Bling OAuth Backend', version='1.1.0')
_STATE_COOKIE = 'bling_oauth_state'


def _basic_auth_header(client_id: str, client_secret: str) -> str:
    raw = f'{client_id}:{client_secret}'.encode('utf-8')
    return 'Basic ' + base64.b64encode(raw).decode('ascii')


def _html_message(title: str, message: str, link: str = '/') -> HTMLResponse:
    return HTMLResponse(
        f'''
<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>
    body {{ font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background:#f8fafc; color:#0f172a; padding:24px; }}
    .card {{ max-width:620px; margin:48px auto; background:white; border:1px solid #e2e8f0; border-radius:18px; padding:24px; box-shadow:0 12px 30px rgba(15,23,42,.08); }}
    .ok {{ color:#166534; }}
    .warn {{ color:#9a3412; }}
    a {{ display:block; text-align:center; margin-top:18px; padding:12px 14px; border-radius:12px; background:#2563eb; color:white; text-decoration:none; font-weight:800; }}
  </style>
</head>
<body>
  <main class="card">
    <h1>{title}</h1>
    <p>{message}</p>
    <a href="{link}">Voltar para o sistema</a>
  </main>
</body>
</html>
'''
    )


def _require_backend_secret(request: Request) -> None:
    config = load_config()
    expected = str(config.backend_shared_secret or '').strip()
    provided = str(request.headers.get('X-Backend-Secret') or '').strip()
    if not expected:
        raise HTTPException(status_code=403, detail='BLING_BACKEND_SHARED_SECRET não configurado no backend.')
    if not secrets.compare_digest(provided, expected):
        raise HTTPException(status_code=403, detail='Segredo inválido.')


@app.get('/health')
def health() -> dict[str, object]:
    config = load_config()
    token = load_token()
    return {
        'ok': True,
        'oauth_ready': config.ready,
        'connected': bool(token.get('access_token')),
        'redirect_uri': config.redirect_uri,
        'token_bridge_ready': bool(config.backend_shared_secret),
    }


@app.get('/auth/bling/start')
def start_auth() -> RedirectResponse:
    config = load_config()
    if not config.client_id:
        raise HTTPException(status_code=500, detail='BLING_CLIENT_ID não configurado.')
    state = secrets.token_urlsafe(32)
    params = {
        'response_type': 'code',
        'client_id': config.client_id,
        'state': state,
        'redirect_uri': config.redirect_uri,
    }
    response = RedirectResponse(f'{config.authorize_url}?{urlencode(params)}', status_code=302)
    response.set_cookie(_STATE_COOKIE, state, httponly=True, secure=True, samesite='lax', max_age=900)
    return response


@app.get('/auth/bling/callback')
def callback(request: Request, code: str | None = None, state: str | None = None, error: str | None = None) -> HTMLResponse | RedirectResponse:
    config = load_config()
    if error:
        return _html_message('Bling não autorizou', f'Erro retornado pelo Bling: {error}', config.frontend_return_url)
    if not code:
        return _html_message('Código ausente', 'O Bling voltou sem código de autorização.', config.frontend_return_url)
    expected_state = request.cookies.get(_STATE_COOKIE, '')
    if expected_state and state != expected_state:
        return _html_message('Sessão inválida', 'A sessão de segurança do OAuth não confere. Gere o link novamente.', config.frontend_return_url)
    if not config.ready:
        return _html_message('OAuth incompleto', 'Configure CLIENT_ID, CLIENT_SECRET e REDIRECT_URI do Bling no backend.', config.frontend_return_url)

    payload = {'grant_type': 'authorization_code', 'code': code, 'redirect_uri': config.redirect_uri}
    headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/x-www-form-urlencoded',
        'Authorization': _basic_auth_header(config.client_id, config.client_secret),
    }
    try:
        response = requests.post(config.token_url, data=payload, headers=headers, timeout=30)
    except Exception as exc:
        return _html_message('Falha ao conectar', f'Erro de comunicação com o Bling: {exc}', config.frontend_return_url)
    if response.status_code >= 400:
        return _html_message('Falha ao gerar token', f'HTTP {response.status_code}: {response.text[:300]}', config.frontend_return_url)

    save_token(response.json())
    final = RedirectResponse(config.frontend_return_url, status_code=302)
    final.delete_cookie(_STATE_COOKIE)
    return final


@app.get('/auth/bling/status')
def status() -> dict[str, object]:
    config = load_config()
    token = load_token()
    return {
        'connected': bool(token.get('access_token')),
        'saved_at': token.get('saved_at', ''),
        'expires_at': token.get('expires_at', ''),
        'token_bridge_ready': bool(config.backend_shared_secret),
    }


@app.get('/auth/bling/token')
def token_bridge(request: Request) -> dict[str, object]:
    _require_backend_secret(request)
    token = load_token()
    if not token.get('access_token'):
        raise HTTPException(status_code=404, detail='Token Bling não encontrado no backend.')
    return {'connected': True, 'token': token}


@app.post('/auth/bling/disconnect')
def disconnect() -> dict[str, object]:
    clear_token()
    return {'connected': False}
