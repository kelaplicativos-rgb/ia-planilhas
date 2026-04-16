
from __future__ import annotations

from datetime import datetime
import re
import unicodedata
from typing import Any

import pandas as pd
import streamlit as st


# ============================================================
# LOG / DEBUG
# ============================================================

def _agora_str() -> str:
    return datetime.now().strftime("%d/%m/%Y %H:%M:%S")


def inicializar_debug() -> None:
    if "debug_logs" not in st.session_state:
        st.session_state["debug_logs"] = []


def log_debug(mensagem: str, nivel: str = "INFO") -> None:
    inicializar_debug()
    linha = f"[{_agora_str()}] [{str(nivel).upper()}] {mensagem}"
    st.session_state["debug_logs"].append(linha)


def obter_logs_texto() -> str:
    inicializar_debug()
    return "\n".join(st.session_state.get("debug_logs", []))


def limpar_logs() -> None:
    st.session_state["debug_logs"] = []


def render_debug_panel(titulo: str = "Debug do sistema") -> None:
    inicializar_debug()

    with st.expander(titulo, expanded=False):
        logs = st.session_state.get("debug_logs", [])

        if logs:
            st.text_area(
                "Logs",
                value="\n".join(logs[-500:]),
                height=250,
                key="debug_logs_area",
            )

            col1, col2 = st.columns(2)

            with col1:
                st.download_button(
                    "⬇️ Baixar log TXT",
                    data=obter_logs_texto().encode("utf-8"),
                    file_name="debug_ia_planilhas.txt",
                    mime="text/plain",
                    use_container_width=True,
                )

            with col2:
                if st.button("Limpar log", use_container_width=True):
                    limpar_logs()
                    st.rerun()
        else:
            st.caption("Nenhum log registrado até agora.")


# ============================================================
# HELPERS DE TEXTO
# ============================================================

def _valor_vazio(valor: Any) -> bool:
    if valor is None:
        return True

    texto = str(valor).strip()
    return texto == "" or texto.lower() in {"nan", "none", "nat", ""}


def normalizar_texto(valor: Any) -> str:
    if _valor_vazio(valor):
        return ""
    return str(valor).strip()


def _remover_acentos(texto: str) -> str:
    texto_nfkd = unicodedata.normalize("NFKD", texto)
    return "".join(ch for ch in texto_nfkd if not unicodedata.combining(ch))


def normalizar_coluna_busca(valor: Any) -> str:
    texto = normalizar_texto(valor).lower()
    texto = _remover_acentos(texto)
    texto = re.sub(r"[_\-/().]+", " ", texto)
    texto = re.sub(r"\s+", " ", texto)
    return texto.strip()


def safe_lower(valor: Any) -> str:
    return normalizar_texto(valor).lower()


# ============================================================
# DATAFRAME / ESTADO
# ============================================================

def safe_df(df: Any) -> pd.DataFrame:
    if isinstance(df, pd.DataFrame):
        return df.copy()
    return pd.DataFrame()


def safe_df_dados(df: Any) -> bool:
    return isinstance(df, pd.DataFrame) and not df.empty and len(df.columns) > 0


def safe_df_estrutura(df: Any) -> bool:
    return isinstance(df, pd.DataFrame) and len(df.columns) > 0


def garantir_dataframe(df: Any) -> pd.DataFrame:
    if isinstance(df, pd.DataFrame):
        return df.copy()
    return pd.DataFrame()


# ============================================================
# AGENT MEMORY SAFE
# ============================================================

def _agent_state_disponivel() -> bool:
    try:
        import bling_app_zero.agent.agent_memory  # noqa: F401
        return True
    except Exception:
        return False


def get_agent_state_safe():
    if not _agent_state_disponivel():
        return None

    try:
        from bling_app_zero.agent.agent_memory import get_agent_state
        return get_agent_state()
    except Exception:
        return None


def _safe_save_agent_state(state) -> None:
    if state is None:
        return

    try:
        from bling_app_zero.agent.agent_memory import save_agent_state
        save_agent_state(state)
    except Exception:
        pass


def _safe_set_agent_stage(etapa: str) -> None:
    state = get_agent_state_safe()
    if state is None:
        return

    etapa_limpa = normalizar_texto(etapa) or "origem"
    state.etapa_atual = etapa_limpa

    if etapa_limpa == "preview_final":
        state.status_execucao = "final_pronto"
    elif etapa_limpa == "mapeamento":
        state.status_execucao = "mapeamento_pronto"
    elif etapa_limpa == "precificacao":
        if normalizar_texto(getattr(state, "status_execucao", "")) == "":
            state.status_execucao = "base_pronta"
    elif etapa_limpa == "origem":
        if normalizar_texto(getattr(state, "status_execucao", "")) == "":
            state.status_execucao = "idle"

    _safe_save_agent_state(state)


# ============================================================
# NAVEGAÇÃO / ETAPAS
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


def sincronizar_etapa_global(etapa: str) -> None:
    etapa_limpa = _normalizar_etapa_fluxo(etapa)

    st.session_state["etapa"] = etapa_limpa
    st.session_state["etapa_origem"] = etapa_limpa
    st.session_state["etapa_fluxo"] = etapa_limpa

    _safe_set_agent_stage(etapa_limpa)


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


# ============================================================
# LIMPEZA DE FLUXO
# ============================================================

def _limpar_chaves_estado(chaves: list[str]) -> None:
    for chave

