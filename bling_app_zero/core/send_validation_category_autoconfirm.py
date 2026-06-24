from __future__ import annotations

from typing import Any

import streamlit as st

CATEGORY_DONE_KEY = 'category_conference_confirmed_v1'
CATEGORY_SKIP_KEY = 'category_conference_skipped_v1'
CATEGORY_VALUES_SIGNATURE_KEY = 'category_conference_values_signature_v1'


def auto_confirm_resolved_categories(category_signature: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    """Confirma categorias quando a coluna final já não possui pendência.

    Use somente depois de validar que category_missing_count == 0.
    Não cria categoria nova; apenas sincroniza o estado de conferência para não
    travar o lote por falta de clique manual.
    """
    st.session_state[CATEGORY_DONE_KEY] = True
    st.session_state[CATEGORY_SKIP_KEY] = False
    st.session_state[CATEGORY_VALUES_SIGNATURE_KEY] = str(category_signature or '')
    result = dict(details or {})
    result['category_decision_done'] = True
    result['category_decision_skipped'] = False
    result['auto_category_applied'] = True
    result['expected_category_signature'] = str(category_signature or '')
    result['category_guard_decision'] = 'categorias_resolvidas_auto_confirmadas'
    return result


__all__ = ['auto_confirm_resolved_categories']
