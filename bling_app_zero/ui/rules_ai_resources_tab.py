from __future__ import annotations

import streamlit as st

from bling_app_zero.core.ai_resource_rules import (
    AI_RESOURCE_IMPROVE_CATALOG_TEXT,
    AI_RESOURCE_SUGGEST_NCM,
    get_ai_resources,
    set_ai_resources,
)

WATCHED_AI_RESOURCES = [AI_RESOURCE_SUGGEST_NCM, AI_RESOURCE_IMPROVE_CATALOG_TEXT]


def _bool_label(value: bool) -> str:
    return 'Sim' if value else 'Não'


def _ai_toggle(label: str, value: bool, key: str, help_text: str | None = None) -> bool:
    return st.toggle(
        f'{label}: {_bool_label(value)}',
        value=value,
        key=key,
        help=help_text,
    )


def _save_if_changed(original: dict[str, bool], updated: dict[str, bool]) -> None:
    changed = any(bool(original.get(key, False)) != bool(updated.get(key, False)) for key in WATCHED_AI_RESOURCES)
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

    st.caption('Observação fiscal: NCM precisa de revisão humana. O sistema não promete 100% de certeza.')

    _save_if_changed(original, updated)
