from __future__ import annotations

import re
import unicodedata
from typing import Any

import pandas as pd
import requests
import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.bling_token_store import load_token

RESPONSIBLE_FILE = 'bling_app_zero/ui/bling_price_channel_selector.py'
API_BASE_DEFAULT = 'https://api.bling.com.br/Api/v3'
PRICE_TARGET_MODE_KEY = 'bling_price_target_mode'
PRICE_CHANNEL_ID_KEY = 'bling_price_channel_id'
PRICE_CHANNEL_NAME_KEY = 'bling_price_channel_name'
PRICE_CHANNEL_OPTIONS_KEY = 'bling_price_channel_options'
PRICE_GENERAL_VALUE = 'geral'
PRICE_CHANNEL_VALUE = 'canal'
LOOKUP_TIMEOUT = 15
ACTIVE_STATUS_VALUES = {'a', 'ativo', 'ativa', 'active', 'enabled', 'habilitado', 'habilitada', '1', 'true', 'sim', 'yes'}
INACTIVE_STATUS_VALUES = {'i', 'inativo', 'inativa', 'inactive', 'disabled', 'desabilitado', 'desabilitada', '0', 'false', 'nao', 'não', 'no'}
STATUS_KEYS = ('situacao', 'situação', 'status', 'ativo', 'ativa', 'active', 'enabled', 'habilitado', 'habilitada', 'isActive')


def _secret(name: str, default: str = '') -> str:
    try:
        bling = st.secrets.get('bling', {})
        value = bling.get(name, default) if hasattr(bling, 'get') else default
        return str(value or default).strip()
    except Exception:
        return default


def _api_base_url() -> str:
    configured = _secret('api_base_url', API_BASE_DEFAULT) or API_BASE_DEFAULT
    configured = configured.replace('https://www.bling.com.br/Api/v3', API_BASE_DEFAULT)
    configured = configured.replace('http://www.bling.com.br/Api/v3', API_BASE_DEFAULT)
    return configured.rstrip('/')


def _url(path: str) -> str:
    if str(path or '').startswith(('http://', 'https://')):
        return str(path)
    return _api_base_url() + '/' + str(path or '').lstrip('/')


def _headers(token: dict[str, Any]) -> dict[str, str]:
    return {'Accept': 'application/json', 'Authorization': f"Bearer {token.get('access_token')}"}


def _extract_items(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ('data', 'dados', 'items', 'result', 'results', 'lojas', 'canais'):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        if isinstance(value, dict):
            nested = _extract_items(value)
            if nested:
                return nested
    return [payload] if payload.get('id') or payload.get('idLoja') or payload.get('idCanal') else []


def _normalize_sort_text(value: object) -> str:
    text = str(value or '').strip().casefold()
    text = ''.join(char for char in unicodedata.normalize('NFKD', text) if not unicodedata.combining(char))
    text = re.sub(r'[^a-z0-9]+', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()


def _status_value(item: dict[str, Any], nested: dict[str, Any] | None = None) -> str:
    nested = nested or {}
    for source in (item, nested):
        for key in STATUS_KEYS:
            if key in source and source.get(key) not in (None, ''):
                return _normalize_sort_text(source.get(key))
    return ''


def _is_active_channel(item: dict[str, Any]) -> bool:
    status = str(item.get('status') or '').strip()
    if not status:
        return True
    if status in INACTIVE_STATUS_VALUES:
        return False
    if status in ACTIVE_STATUS_VALUES:
        return True
    return True


def _normalize_channel_item(item: dict[str, Any]) -> dict[str, str] | None:
    nested = item.get('loja') if isinstance(item.get('loja'), dict) else item.get('canal') if isinstance(item.get('canal'), dict) else {}
    channel_id = str(item.get('id') or item.get('idLoja') or item.get('idCanal') or item.get('codigo') or nested.get('id') or nested.get('idLoja') or '').strip()
    name = str(item.get('descricao') or item.get('nome') or item.get('name') or item.get('description') or nested.get('descricao') or nested.get('nome') or '').strip()
    if not channel_id and not name:
        return None
    return {'id': channel_id, 'nome': name or channel_id, 'status': _status_value(item, nested)}


def _unique_options(items: list[dict[str, str]]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in items:
        channel_id = str(item.get('id') or '').strip()
        name = str(item.get('nome') or '').strip()
        key = (channel_id or name).lower()
        if key and key not in seen:
            out.append({'id': channel_id, 'nome': name or channel_id, 'status': str(item.get('status') or '').strip()})
            seen.add(key)
    return sorted(out, key=lambda option: (_normalize_sort_text(option.get('nome')), _normalize_sort_text(option.get('id'))))


def _option_has_valid_id(item: dict[str, str]) -> bool:
    channel_id = str(item.get('id') or '').strip()
    return bool(channel_id) and channel_id.lower() not in {'sem id', 'none', 'nan', 'null'}


def _filter_active_options(options: list[dict[str, str]]) -> tuple[list[dict[str, str]], int, bool]:
    has_status = any(str(item.get('status') or '').strip() for item in options)
    if not has_status:
        return options, 0, False
    active = [item for item in options if _is_active_channel(item)]
    return active, max(0, len(options) - len(active)), True


def load_price_channels(*, force: bool = False) -> list[dict[str, str]]:
    cached = st.session_state.get(PRICE_CHANNEL_OPTIONS_KEY)
    if not force and isinstance(cached, list) and cached:
        return [item for item in cached if isinstance(item, dict) and _option_has_valid_id(item)]

    token, _meta = load_token()
    if not isinstance(token, dict) or not token.get('access_token'):
        add_audit_event('bling_price_channels_not_loaded_no_token', area='BLING_ENVIO', status='AVISO', details={'responsible_file': RESPONSIBLE_FILE})
        return []

    paths = [
        _secret('price_channels_path', ''),
        _secret('stores_path', ''),
        '/lojas',
        '/lojas-virtuais',
        '/canais-venda',
        '/integracoes',
        '/marketplaces',
    ]
    found: list[dict[str, str]] = []
    errors: list[str] = []
    for path in [path for path in paths if str(path or '').strip()]:
        try:
            response = requests.get(_url(path), headers=_headers(token), timeout=LOOKUP_TIMEOUT)
            if response.status_code >= 400:
                errors.append(f'{path}: HTTP {response.status_code}')
                continue
            for item in _extract_items(response.json() if str(response.text or '').strip() else {}):
                normalized = _normalize_channel_item(item)
                if normalized:
                    found.append(normalized)
            options = [item for item in _unique_options(found) if _option_has_valid_id(item)]
            options, inactive_count, status_filter_applied = _filter_active_options(options)
            if options:
                st.session_state[PRICE_CHANNEL_OPTIONS_KEY] = options
                add_audit_event(
                    'bling_price_channels_loaded',
                    area='BLING_ENVIO',
                    status='OK',
                    details={
                        'path': path,
                        'count': len(options),
                        'inactive_ignored': inactive_count,
                        'status_filter_applied': status_filter_applied,
                        'order': 'alphabetical_by_name',
                        'api_base': _api_base_url(),
                        'responsible_file': RESPONSIBLE_FILE,
                    },
                )
                return options
        except Exception as exc:
            errors.append(f'{path}: {str(exc)[:160]}')
    add_audit_event('bling_price_channels_load_failed', area='BLING_ENVIO', status='AVISO', details={'errors': errors[:8], 'api_base': _api_base_url(), 'responsible_file': RESPONSIBLE_FILE})
    return []


def _is_price_operation(operation: object) -> bool:
    text = str(operation or '').strip().lower()
    return text == 'atualizacao_preco' or 'preco' in text or 'price' in text


def _inject_price_target_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy().fillna('')
    mode = str(st.session_state.get(PRICE_TARGET_MODE_KEY) or PRICE_GENERAL_VALUE)
    channel_id = str(st.session_state.get(PRICE_CHANNEL_ID_KEY) or '').strip()
    channel_name = str(st.session_state.get(PRICE_CHANNEL_NAME_KEY) or '').strip()
    if mode == PRICE_CHANNEL_VALUE and not channel_id:
        mode = PRICE_GENERAL_VALUE
        st.session_state[PRICE_TARGET_MODE_KEY] = PRICE_GENERAL_VALUE
    out['Bling preço destino'] = 'Preço geral' if mode == PRICE_GENERAL_VALUE else 'Canal de venda'
    out['Bling canal venda id'] = '' if mode == PRICE_GENERAL_VALUE else channel_id
    out['Bling canal venda nome'] = '' if mode == PRICE_GENERAL_VALUE else channel_name
    return out


def render_price_channel_selector(download_df: pd.DataFrame, operation: str) -> pd.DataFrame | None:
    if not _is_price_operation(operation):
        return download_df
    st.markdown('### Destino do preço no Bling')
    st.caption('Escolha onde o preço calculado será aplicado antes do envio.')

    current_mode = str(st.session_state.get(PRICE_TARGET_MODE_KEY) or PRICE_GENERAL_VALUE)
    mode_label = st.radio(
        'Onde atualizar o preço?',
        ['Preço geral do produto', 'Preço de uma loja/canal de venda'],
        index=1 if current_mode == PRICE_CHANNEL_VALUE else 0,
        horizontal=False,
        key='bling_price_target_mode_radio',
    )
    mode = PRICE_CHANNEL_VALUE if 'loja' in mode_label.lower() or 'canal' in mode_label.lower() else PRICE_GENERAL_VALUE
    st.session_state[PRICE_TARGET_MODE_KEY] = mode

    if mode == PRICE_GENERAL_VALUE:
        st.session_state.pop(PRICE_CHANNEL_ID_KEY, None)
        st.session_state.pop(PRICE_CHANNEL_NAME_KEY, None)
        st.info('O preço calculado será aplicado no preço geral do produto no Bling.')
        add_audit_event('bling_price_target_general_selected', area='BLING_ENVIO', status='OK', details={'responsible_file': RESPONSIBLE_FILE})
        return _inject_price_target_columns(download_df)

    options = load_price_channels()
    if st.button('Atualizar lista de lojas/canais do Bling', use_container_width=True, key='bling_price_reload_channels'):
        options = load_price_channels(force=True)
        st.rerun()

    if not options:
        manual_id = st.text_input('ID da loja/canal no Bling', value=str(st.session_state.get(PRICE_CHANNEL_ID_KEY) or ''), key='bling_price_manual_channel_id')
        manual_name = st.text_input('Nome da loja/canal', value=str(st.session_state.get(PRICE_CHANNEL_NAME_KEY) or ''), key='bling_price_manual_channel_name')
        if not str(manual_id or '').strip():
            st.warning('Não encontrei lojas/canais com ID válido. Informe o ID do canal ou selecione Preço geral para continuar.')
            return None
        st.session_state[PRICE_CHANNEL_ID_KEY] = str(manual_id).strip()
        st.session_state[PRICE_CHANNEL_NAME_KEY] = str(manual_name or manual_id).strip()
        return _inject_price_target_columns(download_df)

    labels = [f"{item.get('nome') or 'Sem nome'} · ID {item.get('id')}" for item in options]
    current_id = str(st.session_state.get(PRICE_CHANNEL_ID_KEY) or '')
    index = 0
    for pos, item in enumerate(options):
        if current_id and str(item.get('id') or '') == current_id:
            index = pos
            break
    selected_label = st.selectbox('Loja/canal que receberá o preço calculado', labels, index=index, key='bling_price_channel_select')
    selected = options[labels.index(selected_label)]
    selected_id = str(selected.get('id') or '').strip()
    if not selected_id:
        st.warning('O canal selecionado não trouxe ID válido. Atualize a lista ou use Preço geral.')
        return None
    st.session_state[PRICE_CHANNEL_ID_KEY] = selected_id
    st.session_state[PRICE_CHANNEL_NAME_KEY] = str(selected.get('nome') or selected_id).strip()
    st.success(f"Preço será atualizado no canal: {st.session_state[PRICE_CHANNEL_NAME_KEY]}.")
    add_audit_event('bling_price_channel_selected', area='BLING_ENVIO', status='OK', details={'channel_id': st.session_state[PRICE_CHANNEL_ID_KEY], 'channel_name': st.session_state[PRICE_CHANNEL_NAME_KEY], 'responsible_file': RESPONSIBLE_FILE})
    return _inject_price_target_columns(download_df)


__all__ = ['PRICE_CHANNEL_ID_KEY', 'PRICE_CHANNEL_NAME_KEY', 'PRICE_TARGET_MODE_KEY', 'load_price_channels', 'render_price_channel_selector']
