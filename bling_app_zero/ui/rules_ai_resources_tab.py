from __future__ import annotations

import streamlit as st

from bling_app_zero.core.ai_resource_rules import (
    AI_RESOURCE_DESCRIPTION_SIZE,
    AI_RESOURCE_IMPROVE_CATALOG_TEXT,
    AI_RESOURCE_LIMIT_TITLE_60,
    AI_RESOURCE_SUGGEST_NCM,
    DESCRIPTION_SIZE_OPTIONS,
    get_ai_resources,
    set_ai_resources,
)

WATCHED_AI_RESOURCES = [
    AI_RESOURCE_SUGGEST_NCM,
    AI_RESOURCE_IMPROVE_CATALOG_TEXT,
    AI_RESOURCE_LIMIT_TITLE_60,
    AI_RESOURCE_DESCRIPTION_SIZE,
]

DESCRIPTION_LABELS = {
    'pequena': 'Pequena',
    'media': 'Média',
    'grande': 'Grande',
}


def _bool_label(value: bool) -> str:
    return 'Sim' if value else 'Não'


def _ai_toggle(label: str, value: bool, key: str, help_text: str | None = None) -> bool:
    return st.toggle(
        f'{label}: {_bool_label(value)}',
        value=value,
        key=key,
        help=help_text,
    )


def _description_size_selector(current: str) -> str:
    options = list(DESCRIPTION_SIZE_OPTIONS)
    index = options.index(current) if current in options else options.index('media')
    selected_label = st.selectbox(
        'Tamanho da descrição gerada pela IA',
        [DESCRIPTION_LABELS[value] for value in options],
        index=index,
        key='resource_ai_description_size',
        help='Controla o tamanho das descrições sugeridas pela IA quando o recurso de texto estiver ligado.',
    )
    reverse = {label: value for value, label in DESCRIPTION_LABELS.items()}
    return reverse.get(str(selected_label), 'media')


def _save_if_changed(original: dict, updated: dict) -> None:
    changed = any(original.get(key) != updated.get(key) for key in WATCHED_AI_RESOURCES)
    if changed:
        set_ai_resources(updated)
        st.session_state['ai_resources_saved_notice'] = True
        st.rerun()


def render_ai_resources_tab() -> None:
    original = get_ai_resources()
    updated = dict(original)

    st.caption('Recursos com IA ficam separados das blindagens do CSV. A IA sugere, mas o usuário revisa antes de aplicar.')

    if st.session_state.pop('ai_resources_saved_notice', False):
        st.caption('✅ Recursos com IA atualizados.')

    updated[AI_RESOURCE_SUGGEST_NCM] = _ai_toggle(
        'Sugerir NCM com IA para revisão',
        bool(updated.get(AI_RESOURCE_SUGGEST_NCM, False)),
        'resource_ai_suggest_ncm',
        'Quando ligado, libera apoio da IA para sugerir NCM por grupos de produtos. Não aplica automaticamente: revise antes de usar.',
    )
    updated[AI_RESOURCE_IMPROVE_CATALOG_TEXT] = _ai_toggle(
        'Melhorar títulos e descrições com IA',
        bool(updated.get(AI_RESOURCE_IMPROVE_CATALOG_TEXT, False)),
        'resource_ai_improve_catalog_text',
        'Quando ligado, permite usar IA para melhorar títulos e descrições no preview final, sempre com confirmação antes de aplicar.',
    )

    if bool(updated.get(AI_RESOURCE_IMPROVE_CATALOG_TEXT, False)):
        updated[AI_RESOURCE_LIMIT_TITLE_60] = _ai_toggle(
            'Limitar título a 60 caracteres',
            bool(updated.get(AI_RESOURCE_LIMIT_TITLE_60, True)),
            'resource_ai_limit_title_60',
            'O Bling trabalha melhor com títulos curtos. Quando ligado, sugestões de título da IA são cortadas em até 60 caracteres.',
        )
        updated[AI_RESOURCE_DESCRIPTION_SIZE] = _description_size_selector(
            str(updated.get(AI_RESOURCE_DESCRIPTION_SIZE, 'media'))
        )
    else:
        st.caption('Ligue “Melhorar títulos e descrições com IA” para configurar limite de título e tamanho da descrição.')

    st.caption('Observação fiscal: NCM precisa de revisão humana. O sistema não promete 100% de certeza.')

    _save_if_changed(original, updated)
