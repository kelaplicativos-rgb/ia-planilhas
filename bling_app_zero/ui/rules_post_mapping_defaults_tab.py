from __future__ import annotations

from typing import Any

import streamlit as st

from bling_app_zero.core.post_mapping_defaults import DEFAULT_POST_MAPPING_CONFIG, POST_MAPPING_DEFAULTS_SESSION_KEY


def _text(value: object, fallback: str = '') -> str:
    text = str(value if value is not None else '').strip()
    return text if text else fallback


def get_post_mapping_defaults_config() -> dict[str, Any]:
    raw = st.session_state.get(POST_MAPPING_DEFAULTS_SESSION_KEY)
    config = dict(DEFAULT_POST_MAPPING_CONFIG)
    if isinstance(raw, dict):
        for key in config:
            if key in raw:
                config[key] = raw[key]
    config['enabled'] = bool(config.get('enabled', True))
    config['short_description_from_complement'] = bool(config.get('short_description_from_complement', True))
    for key, fallback in DEFAULT_POST_MAPPING_CONFIG.items():
        if isinstance(fallback, str):
            config[key] = _text(config.get(key), fallback)
    st.session_state[POST_MAPPING_DEFAULTS_SESSION_KEY] = config
    return config


def set_post_mapping_defaults_config(config: dict[str, Any]) -> dict[str, Any]:
    current = dict(DEFAULT_POST_MAPPING_CONFIG)
    if isinstance(config, dict):
        for key in current:
            if key in config:
                current[key] = config[key]
    current['enabled'] = bool(current.get('enabled', True))
    current['short_description_from_complement'] = bool(current.get('short_description_from_complement', True))
    for key, fallback in DEFAULT_POST_MAPPING_CONFIG.items():
        if isinstance(fallback, str):
            current[key] = _text(current.get(key), fallback)
    st.session_state[POST_MAPPING_DEFAULTS_SESSION_KEY] = current
    return current


def _text_input(config: dict[str, Any], key: str, label: str) -> None:
    config[key] = st.text_input(
        label,
        value=_text(config.get(key), str(DEFAULT_POST_MAPPING_CONFIG.get(key, ''))),
        key=f'post_mapping_default_{key}',
    )


def _reset_to_system_defaults() -> None:
    st.session_state[POST_MAPPING_DEFAULTS_SESSION_KEY] = dict(DEFAULT_POST_MAPPING_CONFIG)
    st.success('Padrões finais restaurados.')
    st.rerun()


def _render_default_editor(config: dict[str, Any]) -> None:
    st.caption('Valores aplicados apenas se a coluna existir e estiver vazia.')
    _text_input(config, 'category_default', 'Categoria')
    _text_input(config, 'clone_parent_default', 'Clonar dados do pai')
    _text_input(config, 'product_condition_default', 'Condição do produto')
    _text_input(config, 'description_complement_default', 'Descrição Complementar')
    _text_input(config, 'free_shipping_default', 'Frete Grátis')
    _text_input(config, 'additional_info_default', 'Informações Adicionais')
    _text_input(config, 'box_items_default', 'Itens p/ caixa')
    _text_input(config, 'situation_default', 'Situação')
    _text_input(config, 'unit_default', 'Unidade')
    _text_input(config, 'measure_unit_name_default', 'Unidade de medida')
    _text_input(config, 'video_default', 'Vídeo')
    _text_input(config, 'volumes_default', 'Volumes')
    if st.button('Restaurar padrões do sistema', use_container_width=True, key='post_mapping_restore_defaults'):
        _reset_to_system_defaults()


def render_post_mapping_defaults_tab() -> None:
    st.divider()
    st.markdown('##### Padrões finais pós-mapeamento')
    st.caption('Recomendado manter ligado. Completa somente campos vazios após o mapeamento manual.')

    config = get_post_mapping_defaults_config()
    config['enabled'] = st.checkbox(
        'Ativar padrões finais',
        value=bool(config.get('enabled', True)),
        key='post_mapping_defaults_enabled',
        help='Quando ligado, o sistema completa apenas colunas existentes e vazias no CSV final.',
    )
    config['short_description_from_complement'] = st.checkbox(
        'Descrição curta usa descrição complementar quando estiver vazia',
        value=bool(config.get('short_description_from_complement', True)),
        key='post_mapping_short_from_complement',
    )

    status = 'Ativo' if config['enabled'] else 'Desativado'
    st.caption(f'Status: {status} · Não sobrescreve valores preenchidos.')
    show_editor = st.checkbox(
        'Editar valores padrão',
        value=False,
        key='show_post_mapping_defaults_editor',
    )
    if show_editor:
        _render_default_editor(config)
    set_post_mapping_defaults_config(config)


__all__ = [
    'get_post_mapping_defaults_config',
    'render_post_mapping_defaults_tab',
    'set_post_mapping_defaults_config',
]
