from __future__ import annotations

import base64
import hmac
import logging
import secrets
from html import escape
from urllib.parse import urlencode

import requests
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from bling_backend.config import load_config
from bling_backend.token_store import clear_token, load_token, save_token

app = FastAPI(title='MapeiaAI Bling OAuth Backend', version='1.1.2')
_STATE_COOKIE = 'bling_oauth_state'
_LOG = logging.getLogger('bling_backend.oauth')


def _basic_auth_header(client_id: str, client_secret: str) -> str:
    raw = f'{client_id}:{client_secret}'.encode('utf-8')
    return 'Basic ' + base64.b64encode(raw).decode('ascii')


def _safe_text(value: object, default: str = '-') -> str:
    text = str(value if value is not None else default).strip()
    return escape(text or default)


def _html_message(title: str, message: str, link: str = '/', details: dict[str, object] | None = None):
    safe_title = _safe_text(title)
    safe_message = _safe_text(message)
    safe_link = _safe_text(link or '/')
    details_html = ''

    if details:
        rows = []
        for key, value in details.items():
            rows.append(
                '<tr>'
                f'<th style="text-align:left;padding:8px;border-bottom:1px solid #fed7aa;color:#7c2d12;vertical-align:top;">{_safe_text(key)}</th>'
                f'<td style="padding:8px;border-bottom:1px solid #fed7aa;word-break:break-word;">{_safe_text(value)}</td>'
                '</tr>'
            )
        details_html = f'''
    <section style="margin-top:18px;background:#fff7ed;border:1px solid #fdba74;border-radius:14px;padding:14px;">
      <h2 style="font-size:16px;margin:0 0 10px;color:#9a3412;">Diagnóstico OAuth</h2>
      <table style="width:100%;border-collapse:collapse;font-size:14px;">{''.join(rows)}</table>
    </section>
'''

    html = f'''
<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{safe_title}</title>
</head>
<body style="font-family:Arial,sans-serif;background:#f8fafc;color:#0f172a;padding:24px;">
  <main style="max-width:720px;margin:48px auto;background:white;border:1px solid #e2e8f0;border-radius:18px;padding:24px;box-shadow:0 10px 30px rgba(15,23,42,.06);">
    <div style="background:#fff7ed;border:1px solid #fdba74;border-radius:14px;padding:14px;margin-bottom:18px;color:#7c2d12;">
      <strong>Atenção:</strong> o retorno do Bling não concluiu a autorização.
    </div>
    <h1 style="margin:0 0 12px;">{safe_title}</h1>
    <p style="line-height:1.5;">{safe_message}</p>
    {details_html}
    <a href="{safe_link}" style="display:block;text-align:center;margin-top:18px;padding:12px 14px;border-radius:12px;background:#2563eb;color:white;text-decoration:none;font-weight:800;">Voltar para o sistema</a>
  </main>
</body>
</html>
'''
    return HTMLResponse(html)


def _oauth_diagnostics(request: Request, extra: dict[str, object] | None = None) -> dict[str, object]:
    config = load_config()
    query_params = dict(request.query_params)
    query_params.pop('code', None)

    diagnostics: dict[str, object] = {
        'url_recebida': str(request.url),
        'rota': request.url.path,
        'query_params_sem_code': query_params or '-',
        'state_recebido': query_params.get('state') or '-',
        'cookie_state_presente': bool(request.cookies.get(_STATE_COOKIE)),
        'redirect_uri_configurada': config.redirect_uri or '-',
        'frontend_return_url': config.frontend_return_url or '-',
        'client_id_configurado': bool(config.client_id),
        'client_secret_configurado': bool(config.client_secret),
        'oauth_pronto': config.ready,
    }
    if extra:
        diagnostics.update(extra)
    return diagnostics


def _require_backend_secret(request: Request) -> None:
    config = load_config()
    expected = str(config.backend_shared_secret or '').strip()
    provided = str(request.headers.get('X-Backend-Secret') or '').strip()
    if not expected:
        raise HTTPException(status_code=403, detail='BLING_BACKEND_SHARED_SECRET não configurado no backend.')
    if not hmac.compare_digest(provided, expected):
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
        'frontend_return_url': config.frontend_return_url,
        'authorize_url': config.authorize_url,
        'token_bridge_ready': bool(config.backend_shared_secret),
    }


@app.get('/auth/bling/start')
def start_auth():
    config = load_config()
    if not config.client_id:
        raise HTTPException(status_code=500, detail='BLING_CLIENT_ID não configurado.')
    if not config.redirect_uri:
        raise HTTPException(status_code=500, detail='BLING_REDIRECT_URI não configurado.')

    state = secrets.token_urlsafe(32)
    params = {
        'response_type': 'code',
        'client_id': config.client_id,
        'state': state,
        'redirect_uri': config.redirect_uri,
    }
    redirect_to = f'{config.authorize_url}?{urlencode(params)}'
    _LOG.info('Iniciando OAuth Bling. redirect_uri=%s authorize_url=%s', config.redirect_uri, config.authorize_url)
    response = RedirectResponse(redirect_to, status_code=302)
    response.set_cookie(_STATE_COOKIE, state, httponly=True, secure=True, samesite='lax', max_age=900)
    return response


@app.get('/auth/bling/callback')
def callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
):
    config = load_config()

    if error:
        details = _oauth_diagnostics(
            request,
            {
                'error': error,
                'error_description': error_description or '-',
                'acao_recomendada': 'Confira se a URL de redirecionamento cadastrada no app do Bling é idêntica à redirect_uri_configurada.',
            },
        )
        _LOG.warning('Bling retornou erro OAuth: %s | details=%s', error, details)
        return _html_message(
            'Bling não autorizou',
            f'Erro retornado pelo Bling: {error_description or error}',
            config.frontend_return_url,
            details,
        )

    if not code:
        details = _oauth_diagnostics(
            request,
            {
                'motivo_provavel': 'O callback foi aberto sem passar pelo botão de autorização ou o Bling recusou/invalidou o redirect sem enviar code.',
                'acao_recomendada': 'Volte ao sistema, clique em Conectar com Bling novamente e confirme no Bling se a URL de redirecionamento é exatamente a mesma exibida aqui.',
            },
        )
        _LOG.warning('Callback Bling sem code. details=%s', details)
        return _html_message(
            'Código ausente',
            'O Bling voltou sem o código de autorização. Sem esse code o backend não consegue gerar o token.',
            config.frontend_return_url,
            details,
        )

    expected_state = request.cookies.get(_STATE_COOKIE, '')
    if expected_state and state != expected_state:
        details = _oauth_diagnostics(
            request,
            {
                'state_esperado_cookie': 'presente, mas diferente do state recebido',
                'acao_recomendada': 'Gere um novo link pelo botão Conectar com Bling. Não reutilize abas antigas do OAuth.',
            },
        )
        _LOG.warning('State OAuth inválido. details=%s', details)
        return _html_message(
            'Sessão inválida',
            'A sessão de segurança do OAuth não confere. Gere o link novamente pelo sistema.',
            config.frontend_return_url,
            details,
        )

    if not config.ready:
        details = _oauth_diagnostics(
            request, {'acao_recomendada': 'Configure CLIENT_ID, CLIENT_SECRET e REDIRECT_URI no backend Render.'}
        )
        return _html_message(
            'OAuth incompleto',
            'Configure CLIENT_ID, CLIENT_SECRET e REDIRECT_URI do Bling no backend.',
            config.frontend_return_url,
            details,
        )

    payload = {'grant_type': 'authorization_code', 'code': code, 'redirect_uri': config.redirect_uri}
    headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/x-www-form-urlencoded',
        'Authorization': _basic_auth_header(config.client_id, config.client_secret),
    }
    try:
        response = requests.post(config.token_url, data=payload, headers=headers, timeout=30)
    except Exception as exc:
        details = _oauth_diagnostics(request, {'erro_comunicacao': exc})
        _LOG.exception('Falha de comunicação com Bling no token exchange.')
        return _html_message('Falha ao conectar', f'Erro de comunicação com o Bling: {exc}', config.frontend_return_url, details)

    if response.status_code >= 400:
        details = _oauth_diagnostics(
            request,
            {
                'http_status': response.status_code,
                'resposta_bling': response.text[:1000],
                'acao_recomendada': 'Verifique client_id, client_secret e se o redirect_uri usado no token é idêntico ao usado na autorização.',
            },
        )
        _LOG.warning('Falha ao trocar code por token. status=%s body=%s', response.status_code, response.text[:1000])
        return _html_message(
            'Falha ao gerar token',
            f'O Bling recusou a troca do código por token. HTTP {response.status_code}.',
            config.frontend_return_url,
            details,
        )

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
        'redirect_uri': config.redirect_uri,
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
