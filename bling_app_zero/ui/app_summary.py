
from __future__ import annotations

import streamlit as st

from bling_app_zero.ui.app_state import get_agent_state_safe
from bling_app_zero.ui.app_text import normalizar_texto


def _label_etapa(etapa: str) -> str:
    mapa = {
        "ia_orquestrador": "IA Orquestrador",
        "origem": "Origem",
        "normalizacao": "Normalização",
        "precificacao": "Precificação",
        "mapeamento": "Mapeamento",
        "validacao": "Validação",
        "final": "Final",
    }
    return mapa.get(normalizar_texto(etapa).lower(), normalizar_texto(etapa) or "-")


def _status_legivel(status: str) -> str:
    mapa = {
        "idle": "Aguardando",
        "base_pronta": "Base pronta",
        "mapeamento_pronto": "Mapeamento pronto",
        "final_pronto": "Final pronto",
        "revisao": "Em revisão",
        "revisao_final": "Revisão final",
        "sucesso": "Concluído",
        "erro": "Erro",
        "validacao_pendente": "Validação pendente",
    }
    return mapa.get(normalizar_texto(status).lower(), normalizar_texto(status) or "-")


def render_resumo_fluxo() -> None:
    state = get_agent_state_safe()

    if state is not None:
        etapa = _label_etapa(getattr(state, "etapa_atual", "ia_orquestrador"))
        operacao = normalizar_texto(getattr(state, "operacao", "")) or "-"
        status = _status_legivel(getattr(state, "status_execucao", "idle"))
        simulacao = "Aprovada" if bool(getattr(state, "simulacao_aprovada", False)) else "Pendente"

        st.caption(
            f"Etapa atual: {etapa} | Operação: {operacao} | Status: {status} | Simulação: {simulacao}"
        )
        return

    etapa = st.session_state.get("etapa", "ia_orquestrador")
    tipo_operacao = st.session_state.get("tipo_operacao", "")

    st.caption(
        f"Etapa atual: {_label_etapa(str(etapa))} | Operação: {tipo_operacao if tipo_operacao else '-'}"
    )

