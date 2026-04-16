
from __future__ import annotations

import streamlit as st

from bling_app_zero.ui.app_dataframe import *
from bling_app_zero.ui.app_debug import *
from bling_app_zero.ui.app_exports import *
from bling_app_zero.ui.app_formatters import *
from bling_app_zero.ui.app_models import *
from bling_app_zero.ui.app_state import *
from bling_app_zero.ui.app_summary import *
from bling_app_zero.ui.app_text import *
from bling_app_zero.ui.app_validators import *


# ============================================================
# COMPATIBILIDADE DE NAVEGAÇÃO / TOPO
# ============================================================

ETAPAS_VALIDAS = [
    "origem",
    "precificacao",
    "mapeamento",
    "preview_final",
]

MAPA_ETAPA_ANTERIOR = {
    "origem": "origem",
    "precificacao": "origem",
    "mapeamento": "precificacao",
    "preview_final": "mapeamento",
}

MAPA_LABEL_ETAPA = {
    "origem": "Origem",
    "precificacao": "Precificação",
    "mapeamento": "Mapeamento",
    "preview_final": "Preview final",
}


def _normalizar_etapa_fluxo(etapa: str | None) -> str:
    etapa_limpa = normalizar_texto(etapa).lower()
    if etapa_limpa in ETAPAS_VALIDAS:
        return etapa_limpa
    return "origem"


def _set_query_param_etapa(etapa: str) -> None:
    etapa = _normalizar_etapa_fluxo(etapa)

    try:
        st.query_params["etapa"] = etapa
        return
    except Exception:
        pass

    try:
        st.experimental_set_query_params(etapa=etapa)
    except Exception:
        pass


def _get_query_param_etapa() -> str:
    try:
        valor = st.query_params.get("etapa", "")
        if isinstance(valor, list):
            valor = valor[0] if valor else ""
        return _normalizar_etapa_fluxo(str(valor))
    except Exception:
        pass

    try:
        params = st.experimental_get_query_params()
        valor = params.get("etapa", [""])
        if isinstance(valor, list):
            valor = valor[0] if valor else ""
        return _normalizar_etapa_fluxo(str(valor))
    except Exception:
        return "origem"


def _garantir_etapa_historico() -> None:
    if "etapa_historico" not in st.session_state or not isinstance(
        st.session_state.get("etapa_historico"),
        list,
    ):
        st.session_state["etapa_historico"] = []


def _registrar_historico_etapa(etapa_anterior: str, etapa_nova: str) -> None:
    _garantir_etapa_historico()

    etapa_anterior = _normalizar_etapa_fluxo(etapa_anterior)
    etapa_nova = _normalizar_etapa_fluxo(etapa_nova)

    if etapa_anterior == etapa_nova:
        return

    historico = st.session_state["etapa_historico"]

    if not historico or historico[-1] != etapa_anterior:
        historico.append(etapa_anterior)

    st.session_state["etapa_historico"] = historico[-20:]


def get_etapa() -> str:
    etapa = st.session_state.get("etapa", "")
    return _normalizar_etapa_fluxo(str(etapa))


def set_etapa(etapa: str, registrar_historico: bool = True) -> None:
    etapa_nova = _normalizar_etapa_fluxo(etapa)
    etapa_atual = get_etapa()

    if registrar_historico:
        _registrar_historico_etapa(etapa_atual, etapa_nova)

    sincronizar_etapa_global(etapa_nova)
    _set_query_param_etapa(etapa_nova)


def sincronizar_etapa_da_url() -> None:
    etapa_url = _get_query_param_etapa()
    etapa_state = get_etapa()

    if not etapa_state or etapa_state not in ETAPAS_VALIDAS:
        sincronizar_etapa_global(etapa_url)
        return

    if etapa_url != etapa_state:
        sincronizar_etapa_global(etapa_url)


def ir_para_etapa(etapa: str) -> None:
    etapa_nova = _normalizar_etapa_fluxo(etapa)
    set_etapa(etapa_nova, registrar_historico=True)
    st.rerun()


def voltar_para_etapa(etapa: str) -> None:
    etapa_nova = _normalizar_etapa_fluxo(etapa)
    set_etapa(etapa_nova, registrar_historico=False)
    st.rerun()


def voltar_etapa_anterior() -> None:
    _garantir_etapa_historico()

    historico = st.session_state.get("etapa_historico", [])
    etapa_atual = get_etapa()

    if historico:
        etapa_destino = _normalizar_etapa_fluxo(historico.pop())
        st.session_state["etapa_historico"] = historico
    else:
        etapa_destino = MAPA_ETAPA_ANTERIOR.get(etapa_atual, "origem")

    set_etapa(etapa_destino, registrar_historico=False)
    st.rerun()


def render_topo_navegacao() -> None:
    etapa_atual = get_etapa()

    colunas = st.columns(len(ETAPAS_VALIDAS))
    for idx, etapa in enumerate(ETAPAS_VALIDAS):
        label = MAPA_LABEL_ETAPA.get(etapa, etapa.title())
        ativo = etapa == etapa_atual
        texto = f"➡️ {label}" if ativo else label

        with colunas[idx]:
            if st.button(
                texto,
                key=f"topo_nav_{etapa}",
                use_container_width=True,
                disabled=False,
            ):
                ir_para_etapa(etapa)


# ============================================================
# COMPATIBILIDADE EXTRA DE ESTADO
# ============================================================

def limpar_estado_fluxo() -> None:
    """
    Sobrescreve a função base para também limpar o histórico de navegação
    e manter a URL coerente com o fluxo atual.
    """
    _limpar_chaves_estado(
        [
            "df_origem",
            "df_normalizado",
            "df_precificado",
            "df_mapeado",
            "df_saida",
            "df_final",
            "df_calc_precificado",
            "df_preview_mapeamento",
            "df_modelo",
            "origem_upload_nome",
            "origem_upload_bytes",
            "origem_upload_tipo",
            "origem_upload_ext",
            "modelo_upload_nome",
            "modelo_upload_bytes",
            "modelo_upload_tipo",
            "modelo_upload_ext",
            "site_fornecedor_url",
            "site_fornecedor_diagnostico",
            "site_busca_diagnostico_df",
            "site_busca_diagnostico_total_descobertos",
            "site_busca_diagnostico_total_validos",
            "site_busca_diagnostico_total_rejeitados",
            "pricing_df_preview",
            "mapping_manual",
            "mapping_sugerido",
            "etapa_historico",
        ]
    )

    for chave in [
        "mapping_origem",
        "mapping_origem_rascunho",
        "mapping_origem_defaults",
    ]:
        st.session_state[chave] = {}

    for chave in [
        "ia_plano_preview",
        "ia_erro_execucao",
    ]:
        st.session_state[chave] = ""

    try:
        from bling_app_zero.ui.app_state import _agent_state_disponivel  # type: ignore
        if _agent_state_disponivel():
            try:
                from bling_app_zero.agent.agent_memory import reset_agent_state

                reset_agent_state(
                    preserve_dataframe_keys=False,
                    preserve_operacao=False,
                    preserve_deposito=False,
                )
            except Exception:
                pass
    except Exception:
        pass

    sincronizar_etapa_global("origem")
    _set_query_param_etapa("origem")


# ============================================================
# RESUMO VISUAL EXTRA
# ============================================================

def render_topo_status_fluxo() -> None:
    etapa = get_etapa()
    operacao = normalizar_texto(st.session_state.get("tipo_operacao", "")) or "-"
    origem_ok = "Sim" if safe_df_dados(st.session_state.get("df_origem")) else "Não"
    modelo_ok = "Sim" if safe_df_estrutura(st.session_state.get("df_modelo")) else "Não"
    final_ok = "Sim" if safe_df_estrutura(st.session_state.get("df_final")) else "Não"

    st.caption(
        " | ".join(
            [
                f"Etapa: {MAPA_LABEL_ETAPA.get(etapa, etapa)}",
                f"Operação: {operacao}",
                f"Origem: {origem_ok}",
                f"Modelo: {modelo_ok}",
                f"Final: {final_ok}",
            ]
        )
    )
