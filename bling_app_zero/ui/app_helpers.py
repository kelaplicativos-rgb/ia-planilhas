
from __future__ import annotations

import streamlit as st
import pandas as pd
from datetime import datetime


# ============================================================
# LOG
# ============================================================

def log_debug(msg: str, nivel: str = "INFO") -> None:
    try:
        ts = datetime.now().strftime("%H:%M:%S")
        linha = f"[{ts}] [{nivel}] {msg}"

        if "logs" not in st.session_state:
            st.session_state["logs"] = []

        st.session_state["logs"].append(linha)

        # mantém só últimos 200 logs
        st.session_state["logs"] = st.session_state["logs"][-200:]

    except Exception:
        pass


# ============================================================
# ETAPAS (FLUXO GLOBAL)
# ============================================================

def sincronizar_etapa_global(etapa: str) -> None:
    """
    Controla qual etapa do fluxo está ativa.
    """
    try:
        st.session_state["etapa_fluxo"] = etapa
        log_debug(f"[ETAPA] Mudando para: {etapa}")
        st.rerun()
    except Exception as e:
        log_debug(f"[ERRO ETAPA] {e}", "ERROR")


def ir_para_etapa(etapa: str) -> None:
    """
    Alias moderno usado pelo ia_panel
    """
    sincronizar_etapa_global(etapa)


def voltar_para_etapa(etapa: str) -> None:
    """
    Compatibilidade com fluxo antigo
    """
    sincronizar_etapa_global(etapa)


# ============================================================
# DATAFRAME HELPERS
# ============================================================

def safe_df_dados(df) -> bool:
    """
    Valida se é um DataFrame utilizável
    """
    try:
        return isinstance(df, pd.DataFrame) and not df.empty
    except Exception:
        return False


def limpar_df(df: pd.DataFrame | None) -> pd.DataFrame | None:
    try:
        if not safe_df_dados(df):
            return None

        df = df.copy()

        # remove colunas totalmente vazias
        df = df.dropna(axis=1, how="all")

        # remove linhas totalmente vazias
        df = df.dropna(axis=0, how="all")

        return df

    except Exception as e:
        log_debug(f"[ERRO limpar_df] {e}", "ERROR")
        return df


def garantir_df_session(chave: str, df: pd.DataFrame | None) -> None:
    try:
        if safe_df_dados(df):
            st.session_state[chave] = df.copy()
    except Exception:
        st.session_state[chave] = df


# ============================================================
# RESUMO DE FLUXO (UI)
# ============================================================

def render_resumo_fluxo() -> None:
    try:
        etapa = st.session_state.get("etapa_fluxo", "ia")
        operacao = st.session_state.get("tipo_operacao_bling", "-")
        origem = st.session_state.get("origem_tipo", "-")

        mapa_operacao = {
            "cadastro": "Cadastro",
            "estoque": "Estoque",
        }

        mapa_origem = {
            "site": "Site",
            "planilha": "Planilha",
            "xml": "XML",
        }

        st.caption(
            f"Fluxo: {mapa_operacao.get(operacao, operacao)} → "
            f"{mapa_origem.get(origem, origem)} → "
            f"Etapa: {etapa}"
        )

    except Exception:
        pass


# ============================================================
# RESET GLOBAL (IMPORTANTE)
# ============================================================

def resetar_fluxo_completo() -> None:
    try:
        keys = list(st.session_state.keys())

        for k in keys:
            if k not in ["logs"]:
                del st.session_state[k]

        st.session_state["etapa_fluxo"] = "ia"

        log_debug("[RESET] Fluxo reiniciado")

        st.rerun()

    except Exception as e:
        log_debug(f"[ERRO RESET] {e}", "ERROR")
