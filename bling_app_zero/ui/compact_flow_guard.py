from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.ui.app_core_config import ETAPAS_ORDEM


LEGACY_TO_COMPACT = {
    "precificacao": "mapeamento",
    "final": "preview_final",
    "envio": "preview_final",
}


def _is_df(value: object) -> bool:
    return isinstance(value, pd.DataFrame) and len(value.columns) > 0 and not value.empty


def _compact_stage(stage: object) -> str:
    raw = str(stage or "origem").strip()
    raw = LEGACY_TO_COMPACT.get(raw, raw)
    return raw if raw in ETAPAS_ORDEM else "origem"


def _maxima_permitida() -> str:
    if _is_df(st.session_state.get("df_mapeado")):
        return "preview_final"
    if _is_df(st.session_state.get("df_origem")):
        return "mapeamento"
    return "origem"


def normalize_compact_flow_state() -> None:
    """Mantém sessões antigas compatíveis com o wizard compacto.

    O app já não usa mais a etapa obrigatória de precificação. Esta guarda evita
    que query params, session_state ou chaves antigas levem o usuário para telas
    removidas ou bloqueiem a navegação após deploy no Streamlit Cloud.
    """

    maxima = _maxima_permitida()
    st.session_state["wizard_etapa_maxima"] = maxima

    atual = _compact_stage(st.session_state.get("wizard_etapa_atual", "origem"))
    legado = _compact_stage(st.session_state.get("etapa", atual))

    alvo = legado if legado in ETAPAS_ORDEM else atual

    if ETAPAS_ORDEM.index(alvo) > ETAPAS_ORDEM.index(maxima):
        alvo = maxima

    st.session_state["wizard_etapa_atual"] = alvo
    st.session_state["etapa"] = alvo

    try:
        etapa_url = st.query_params.get("etapa", "")
        if isinstance(etapa_url, list):
            etapa_url = etapa_url[0] if etapa_url else ""
        etapa_url = _compact_stage(etapa_url)
        if etapa_url != st.query_params.get("etapa", ""):
            st.query_params["etapa"] = alvo
        elif ETAPAS_ORDEM.index(etapa_url) > ETAPAS_ORDEM.index(maxima):
            st.query_params["etapa"] = alvo
    except Exception:
        pass

    if _is_df(st.session_state.get("df_final")) and not _is_df(st.session_state.get("df_mapeado")):
        st.session_state["df_mapeado"] = st.session_state.get("df_final")
