from __future__ import annotations

from datetime import datetime
from urllib.parse import urlparse

import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.debug import add_debug

RESPONSIBLE_FILE = 'bling_app_zero/ui/guided_login_panel.py'
CONFIG_KEY = 'guided_login_capture_config'
PROMPT_KEY = 'guided_login_capture_prompt'
LAST_PREPARED_KEY = 'guided_login_capture_last_prepared_at'

DEFAULT_LOGIN_URL = 'https://app.obaobamix.com.br/login'


def _normalize_multiline_values(raw: str) -> list[str]:
    values: list[str] = []
    for line in (raw or '').splitlines():
        item = line.strip()
        if item:
            values.append(item)
    return values


def _is_valid_http_url(value: str) -> bool:
    try:
        parsed = urlparse(value.strip())
    except Exception:
        return False
    return parsed.scheme in {'http', 'https'} and bool(parsed.netloc)


def _safe_config(login_url: str, username: str, search_terms: str, notes: str, capture_mode: str) -> dict[str, object]:
    return {
        'login_url': login_url.strip(),
        'domain': urlparse(login_url.strip()).netloc if login_url.strip() else '',
        'username_filled': bool(username.strip()),
        'username_preview': username.strip()[:3] + '***' if username.strip() else '',
        'capture_mode': capture_mode,
        'search_terms': _normalize_multiline_values(search_terms),
        'notes': notes.strip(),
        'prepared_at': datetime.now().isoformat(timespec='seconds'),
        'responsible_file': RESPONSIBLE_FILE,
        'password_saved': False,
        'internal_urls_required': False,
    }


def _build_guided_login_prompt(config: dict[str, object]) -> str:
    terms = config.get('search_terms') or []
    return f'''BLINGCRAWLER LOGIN GUIADO

Acesse o repositório e use como fonte principal:
https://github.com/kelaplicativos-rgb/ia-planilhas/tree/main

Objetivo:
Preparar/validar a captura de produtos em site que exige login guiado, sem misturar com o crawler público atual e sem gravar senha em logs, audit trail ou arquivos.

Site de login:
{config.get('login_url')}

Domínio:
{config.get('domain')}

Modo desejado:
{config.get('capture_mode')}

Usuário preenchido no app:
{config.get('username_filled')}

Senha:
NÃO FOI SALVA E NÃO DEVE SER EXIBIDA EM LOGS.

Termos de busca informados:
{terms}

URLs internas de produto/categoria:
Não solicitadas neste fluxo. O motor autenticado deve descobrir a área de produtos após o login guiado ou seguir as instruções textuais do usuário.

Observações do usuário:
{config.get('notes') or 'Sem observações adicionais.'}

Regras obrigatórias:
- Criar/usar motor independente para captura autenticada.
- Não misturar com o fluxo público de busca por site já existente.
- Não salvar senha no session_state persistente, logs, auditoria, arquivos ou prompt.
- Usar campos type=password na UI.
- Para sites com JavaScript/login, preferir Playwright quando disponível.
- O login deve ser guiado: o usuário informa a URL de login, credenciais e instruções; o sistema prepara a captura.
- Não exigir que o usuário cole URL interna de produto/categoria logo abaixo do login guiado.
- Após autenticar, o motor deve descobrir a navegação de produtos/categorias quando possível.
- Se a autenticação exigir captcha, 2FA ou bloqueio humano, parar e orientar o usuário, sem tentar burlar proteção.
- Para cadastro de produtos, capturar dados completos do produto quando permitido.
- Para atualização de estoque, buscar somente as colunas solicitadas pela planilha modelo.
- Se uma informação solicitada não for encontrada, deixar vazia.
- Imagens no CSV final devem ser separadas por |.
- Download final deve continuar CSV com separador ; e UTF-8-SIG.

Verifique quais arquivos precisam ser criados ou alterados para conectar este painel ao motor de captura autenticada.
Retorne diagnóstico e implementação no padrão arquivo/caminho + código completo quando houver correção.
'''


def _prepare_config(login_url: str, username: str, password: str, search_terms: str, notes: str, capture_mode: str) -> None:
    if not _is_valid_http_url(login_url):
        st.warning('Informe uma URL de login válida, começando com http:// ou https://.')
        return
    if not password.strip():
        st.warning('Informe a senha apenas para esta sessão. Ela não será salva em logs nem no prompt.')
        return

    config = _safe_config(
        login_url=login_url,
        username=username,
        search_terms=search_terms,
        notes=notes,
        capture_mode=capture_mode,
    )
    prompt = _build_guided_login_prompt(config)

    st.session_state[CONFIG_KEY] = config
    st.session_state[PROMPT_KEY] = prompt
    st.session_state[LAST_PREPARED_KEY] = datetime.now().strftime('%d/%m/%Y %H:%M:%S')

    add_debug(
        f'Configuração de login guiado preparada para domínio {config.get("domain")}. Senha não registrada.',
        origin='LOGIN_GUIADO',
    )
    add_audit_event(
        'guided_login_capture_prepared',
        area='LOGIN_GUIADO',
        details={
            'domain': config.get('domain'),
            'capture_mode': capture_mode,
            'has_terms': bool(config.get('search_terms')),
            'has_internal_urls': False,
            'password_saved': False,
            'responsible_file': RESPONSIBLE_FILE,
        },
    )


def _render_safe_summary(config: dict[str, object]) -> None:
    st.markdown('###### Resumo da captura autenticada')
    st.write(f'**Site:** {config.get("domain") or "não informado"}')
    st.write(f'**Modo:** {config.get("capture_mode") or "não informado"}')
    st.write('**Usuário:** preenchido' if config.get('username_filled') else '**Usuário:** não preenchido')
    st.write('**Senha:** não salva')

    terms = config.get('search_terms')
    if isinstance(terms, list) and terms:
        st.write(f'**Termos informados:** {len(terms)}')
    else:
        st.write('**Termos informados:** nenhum — o motor deverá descobrir os produtos após o login.')

    notes = str(config.get('notes') or '').strip()
    if notes:
        st.write(f'**Instruções:** {notes}')


def _render_technical_prompt(prompt: str) -> None:
    show_technical = st.checkbox(
        'Mostrar detalhes técnicos para BLINGFIX',
        value=False,
        key='guided_login_show_technical_prompt',
        help='Opcional. Mostra o prompt técnico sem usar expander aninhado.',
    )
    if not show_technical:
        return

    st.caption('Área técnica. O usuário final não precisa usar este prompt durante o fluxo normal.')
    st.text_area(
        'Prompt técnico oculto',
        value=prompt,
        height=300,
        key='guided_login_prompt_textarea',
    )
    st.download_button(
        '⬇️ Baixar prompt técnico .txt',
        data=prompt.encode('utf-8-sig'),
        file_name='blingcrawler_login_guiado_prompt.txt',
        mime='text/plain',
        use_container_width=True,
        key='download_guided_login_prompt',
    )


def _render_prepared_config() -> None:
    config = st.session_state.get(CONFIG_KEY)
    prompt = st.session_state.get(PROMPT_KEY)
    if not isinstance(config, dict) or not isinstance(prompt, str):
        st.info('Preencha os dados e clique em preparar login guiado.')
        return

    last_prepared = st.session_state.get(LAST_PREPARED_KEY, 'agora')
    st.success(f'Login guiado preparado em {last_prepared}.')
    _render_safe_summary(config)
    st.warning('Motor autenticado preparado para integração. Senha não foi salva. Se houver captcha ou 2FA, a captura deve parar e pedir ação manual.')
    _render_technical_prompt(prompt)


def render_guided_login_panel() -> None:
    st.markdown('##### Login guiado para captura autenticada')
    st.caption('Use quando o fornecedor exigir login antes de buscar produtos. A senha fica apenas no campo seguro da sessão.')

    login_url = st.text_input(
        'URL da tela de login',
        value=DEFAULT_LOGIN_URL,
        placeholder='https://app.obaobamix.com.br/login',
        key='guided_login_url',
    )
    username = st.text_input(
        'Usuário/e-mail de acesso',
        placeholder='seu usuário ou e-mail',
        key='guided_login_username',
    )
    password = st.text_input(
        'Senha da sessão',
        type='password',
        placeholder='não será salva em logs nem no prompt',
        key='guided_login_password_ephemeral',
    )
    capture_mode = st.selectbox(
        'Modo de captura desejado',
        [
            'Cadastro de produtos - capturar dados completos',
            'Atualização de estoque - buscar somente colunas da planilha modelo',
            'Exploração inicial - descobrir categorias/produtos disponíveis',
        ],
        key='guided_login_capture_mode',
    )
    search_terms = st.text_area(
        'Termos para buscar produtos, um por linha',
        placeholder='Opcional. Ex.: controle gamer\ncabo usb\nfone bluetooth',
        height=90,
        key='guided_login_search_terms',
    )
    notes = st.text_area(
        'Instruções do login ou da busca',
        placeholder='Ex.: depois de logar, entrar em Produtos > Catálogo; buscar por SKU; capturar preço e estoque.',
        height=90,
        key='guided_login_notes',
    )

    if st.button('🔐 Preparar login guiado', use_container_width=True, key='prepare_guided_login_capture'):
        _prepare_config(
            login_url=login_url,
            username=username,
            password=password,
            search_terms=search_terms,
            notes=notes,
            capture_mode=capture_mode,
        )

    _render_prepared_config()


__all__ = ['render_guided_login_panel']
