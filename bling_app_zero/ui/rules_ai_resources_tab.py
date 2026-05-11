from __future__ import annotations

import streamlit as st

from bling_app_zero.core.ai_resource_rules import (
    AI_RESOURCE_BLOCKED_TERMS,
    AI_RESOURCE_CONTEXT_FILTER_TERMS,
    AI_RESOURCE_DESCRIPTION_SIZE,
    AI_RESOURCE_IMPROVE_CATALOG_TEXT,
    AI_RESOURCE_LIMIT_TITLE_60,
    AI_RESOURCE_MARKETPLACE_TEXT_GUARD,
    AI_RESOURCE_ORTHOGRAPHY_GRAMMAR,
    AI_RESOURCE_OUT_OF_CONTEXT_FILTER,
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
    AI_RESOURCE_ORTHOGRAPHY_GRAMMAR,
    AI_RESOURCE_MARKETPLACE_TEXT_GUARD,
    AI_RESOURCE_OUT_OF_CONTEXT_FILTER,
    AI_RESOURCE_BLOCKED_TERMS,
    AI_RESOURCE_CONTEXT_FILTER_TERMS,
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


def _text_area(label: str, value: str, key: str, help_text: str | None = None) -> str:
    return st.text_area(
        label,
        value=str(value or ''),
        key=key,
        height=104,
        help=help_text,
    )


def _render_catalog_ai_block(updated: dict) -> dict:
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
    updated[AI_RESOURCE_ORTHOGRAPHY_GRAMMAR] = _ai_toggle(
        'Corrigir ortografia e gramática',
        bool(updated.get(AI_RESOURCE_ORTHOGRAPHY_GRAMMAR, False)),
        'resource_ai_orthography_grammar',
        'Quando ligado, a IA pode revisar nome/título e descrição apenas corrigindo escrita, acentos, pontuação e gramática, sem mudar o sentido do produto.',
    )

    if bool(updated.get(AI_RESOURCE_IMPROVE_CATALOG_TEXT, False)) or bool(updated.get(AI_RESOURCE_ORTHOGRAPHY_GRAMMAR, False)):
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
        st.caption('Ligue um recurso de texto para configurar limite de título e tamanho da descrição.')
    return updated


def _render_marketplace_guard_block(updated: dict) -> dict:
    st.markdown('##### Blindagem de texto para marketplaces')
    updated[AI_RESOURCE_MARKETPLACE_TEXT_GUARD] = _ai_toggle(
        'Detectar palavras proibidas/sensíveis',
        bool(updated.get(AI_RESOURCE_MARKETPLACE_TEXT_GUARD, False)),
        'resource_ai_marketplace_text_guard',
        'Analisa nome/título e descrição no preview final e alerta termos que podem causar bloqueio em marketplaces.',
    )
    if bool(updated.get(AI_RESOURCE_MARKETPLACE_TEXT_GUARD, False)):
        updated[AI_RESOURCE_BLOCKED_TERMS] = _text_area(
            'Palavras/frases proibidas ou sensíveis',
            str(updated.get(AI_RESOURCE_BLOCKED_TERMS, '')),
            'resource_ai_blocked_terms_text',
            'Digite uma palavra ou frase por linha. O sistema apenas alerta no preview final; não apaga automaticamente.',
        )

    updated[AI_RESOURCE_OUT_OF_CONTEXT_FILTER] = _ai_toggle(
        'Detectar descrição fora de contexto',
        bool(updated.get(AI_RESOURCE_OUT_OF_CONTEXT_FILTER, False)),
        'resource_ai_out_of_context_filter',
        'Detecta textos de modelo, placeholders e frases de fornecedor que não deveriam ir para o anúncio.',
    )
    if bool(updated.get(AI_RESOURCE_OUT_OF_CONTEXT_FILTER, False)):
        updated[AI_RESOURCE_CONTEXT_FILTER_TERMS] = _text_area(
            'Frases para detectar descrição fora de contexto',
            str(updated.get(AI_RESOURCE_CONTEXT_FILTER_TERMS, '')),
            'resource_ai_context_filter_terms_text',
            'Digite uma frase por linha. Ex: aqui você coloca a descrição, texto exemplo, lorem ipsum.',
        )
    return updated


def render_ai_resources_tab() -> None:
    original = get_ai_resources()
    updated = dict(original)

    st.caption('Recursos com IA ficam separados das blindagens do CSV. A IA sugere, mas o usuário revisa antes de aplicar.')

    if st.session_state.pop('ai_resources_saved_notice', False):
        st.caption('✅ Recursos com IA atualizados.')

    updated = _render_catalog_ai_block(updated)
    st.divider()
    updated = _render_marketplace_guard_block(updated)

    st.caption('Observação fiscal: NCM precisa de revisão humana. O sistema não promete 100% de certeza.')
    st.caption('Blindagem marketplace: por segurança, termos sensíveis e descrições fora de contexto nascem como alerta antes do download, sem apagar texto automaticamente.')

    _save_if_changed(original, updated)
