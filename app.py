from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

from bling_app_zero.ui.app_helpers import (
    garantir_estado_base,
    log_debug,
    render_debug_panel,
)
from bling_app_zero.ui.origem_dados import render_origem_dados
from bling_app_zero.ui.origem_mapeamento import render_origem_mapeamento
from bling_app_zero.ui.preview_final import render_preview_final
from bling_app_zero.ui.send_panel import (
    render_bling_primeiro_acesso,
    render_send_panel,
)
from bling_app_zero.utils.init_app import inicializar_app


# =========================
# CONFIG
# =========================
st.set_page_config(page_title="IA Planilhas Bling", layout="wide")

APP_VERSION = "1.0.29"
VERSION_JSON_PATH = Path(__file__).with_name("version.json")


def _ler_version_json() -> dict:
    try:
        if not VERSION_JSON_PATH.exists():
            return {}

        conteudo = VERSION_JSON_PATH.read_text(encoding="utf-8")
        data = json.loads(conteudo)

        if isinstance(data, dict):
            return data

        return {}
    except Exception as e:
        log_debug(f"Erro ao ler version.json: {e}", "ERROR")
        return {}


def _resolver_app_version() -> str:
    data = _ler_version_json()
    version_json = str(data.get("version") or "").strip()

    if version_json:
        return version_json

    return APP_VERSION


# =========================
# INIT
# =========================
inicializar_app()
garantir_estado_base()


# =========================
# HELPERS
# =========================
ETAPAS_VALIDAS = {"conexao", "origem", "mapeamento", "final", "envio"}


def _safe_df(df) -> bool:
    try:
        return isinstance(df, pd.DataFrame) and len(df.columns) > 0
    except Exception:
        return False


def _safe_df_com_linhas(df) -> bool:
    try:
        return isinstance(df, pd.DataFrame) and not df.empty and len(df.columns) > 0
    except Exception:
        return False


def _normalizar_etapa(valor: object) -> str:
    try:
        etapa_normalizada = str(valor or "conexao").strip().lower()
    except Exception:
        etapa_normalizada = "conexao"

    if etapa_normalizada not in ETAPAS_VALIDAS:
        return "conexao"

    return etapa_normalizada


def _obter_etapa_atual() -> str:
    candidatos = [
        st.session_state.get("etapa_origem"),
        st.session_state.get("etapa"),
        st.session_state.get("etapa_fluxo"),
    ]

    for valor in candidatos:
        etapa_lida = _normalizar_etapa(valor)
        if etapa_lida in ETAPAS_VALIDAS:
            return etapa_lida

    return "conexao"


def _sincronizar_etapa_global(etapa_destino: str) -> str:
    etapa_ok = _normalizar_etapa(etapa_destino)
    st.session_state["etapa_origem"] = etapa_ok
    st.session_state["etapa"] = etapa_ok
    st.session_state["etapa_fluxo"] = etapa_ok
    return etapa_ok


def _ir_para(etapa: str) -> None:
    _sincronizar_etapa_global(etapa)
    st.rerun()


def _obter_df_fluxo():
    df_final = st.session_state.get("df_final")
    df_saida = st.session_state.get("df_saida")

    df_final_valido = _safe_df(df_final)
    df_saida_valido = _safe_df(df_saida)

    if df_final_valido and not df_saida_valido:
        try:
            st.session_state["df_saida"] = df_final.copy()
        except Exception:
            st.session_state["df_saida"] = df_final
        return df_final

    if df_saida_valido and not df_final_valido:
        try:
            st.session_state["df_final"] = df_saida.copy()
        except Exception:
            st.session_state["df_final"] = df_saida
        return df_saida

    if df_final_valido:
        return df_final

    if df_saida_valido:
        return df_saida

    return None


def _garantir_estado_fluxo_inicial() -> None:
    if "bling_primeiro_acesso_decidido" not in st.session_state:
        st.session_state["bling_primeiro_acesso_decidido"] = False

    if "bling_primeiro_acesso_escolha" not in st.session_state:
        st.session_state["bling_primeiro_acesso_escolha"] = ""


def _pode_ir_para_mapeamento() -> bool:
    for chave in [
        "df_saida",
        "df_final",
        "df_precificado",
        "df_calc_precificado",
        "df_origem",
    ]:
        if _safe_df_com_linhas(st.session_state.get(chave)):
            return True

    return False


def _pode_ir_para_final() -> bool:
    return _safe_df_com_linhas(_obter_df_fluxo())


# =========================
# UI BASE
# =========================
VERSAO_EXIBIDA = _resolver_app_version()

st.title("IA Planilhas → Bling")
st.caption(f"Versão: {VERSAO_EXIBIDA}")

render_debug_panel()

if st.session_state.get("_cache_log"):
    st.info(st.session_state.get("_cache_log"))

_garantir_estado_fluxo_inicial()


# =========================
# CONTROLE DE ETAPA
# =========================
etapa = _sincronizar_etapa_global(_obter_etapa_atual())

if etapa not in ETAPAS_VALIDAS:
    log_debug(f"Etapa inválida detectada no app.py: {etapa}", "ERROR")
    _ir_para("conexao")


# =========================
# ETAPA 0 — CONEXÃO
# =========================
if etapa == "conexao":
    render_bling_primeiro_acesso(
        on_skip=lambda: _ir_para("origem"),
        on_continue=lambda: _ir_para("origem"),
    )


# =========================
# ETAPA 1 — ORIGEM
# =========================
elif etapa == "origem":
    render_origem_dados()


# =========================
# ETAPA 2 — MAPEAMENTO
# =========================
elif etapa == "mapeamento":
    if not _pode_ir_para_mapeamento():
        st.warning("⚠️ Carregue os dados na origem antes de acessar o mapeamento.")
        if st.button("⬅️ Voltar para origem", use_container_width=True):
            _ir_para("origem")
        st.stop()

    render_origem_mapeamento()


# =========================
# ETAPA 3 — FINAL
# =========================
elif etapa == "final":
    df_fluxo = _obter_df_fluxo()

    if not _safe_df(df_fluxo):
        log_debug("FINAL sem dados válidos", "ERROR")
        st.warning("⚠️ Nenhum dado disponível.\nVolte para o mapeamento.")
        if st.button("⬅️ Voltar", use_container_width=True):
            _ir_para("mapeamento")
        st.stop()

    render_preview_final()

    st.markdown("---")
    col1, col2 = st.columns(2)

    with col1:
        if st.button("⬅️ Voltar para mapeamento", use_container_width=True):
            _ir_para("mapeamento")

    with col2:
        if st.button("Ir para envio", use_container_width=True, type="primary"):
            _ir_para("envio")


# =========================
# ETAPA 4 — ENVIO
# =========================
elif etapa == "envio":
    df_fluxo = _obter_df_fluxo()

    if not _safe_df(df_fluxo):
        log_debug("ENVIO sem dados válidos", "ERROR")
        st.warning("⚠️ Nenhum dado disponível para envio.")
        if st.button("⬅️ Voltar para final", use_container_width=True):
            _ir_para("final")
        st.stop()

    st.markdown("---")

    if st.button("⬅️ Voltar para final", use_container_width=True):
        _ir_para("final")

    st.markdown("---")
    render_send_panel()


# =========================
# FALLBACK
# =========================
else:
    log_debug(f"Fallback etapa inesperada: {etapa}", "ERROR")
    _ir_para("conexao")
