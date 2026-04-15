
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

from bling_app_zero.ui.app_helpers import (
    garantir_estado_base,
    obter_etapa_global,
    render_debug_panel,
    safe_df_dados,
    safe_df_estrutura,
    sincronizar_etapa_global,
)
from bling_app_zero.ui.origem_dados import render_origem_dados
from bling_app_zero.ui.origem_mapeamento import render_origem_mapeamento
from bling_app_zero.ui.origem_precificacao import render_origem_precificacao
from bling_app_zero.ui.preview_final import render_preview_final
from bling_app_zero.utils.init_app import inicializar_app

# =========================
# CONFIG
# =========================
st.set_page_config(
    page_title="IA Planilhas",
    layout="wide",
)

APP_VERSION = "1.0.45"
VERSION_JSON_PATH = Path(__file__).with_name("version.json")

ETAPAS_VALIDAS = {"origem", "precificacao", "mapeamento", "final"}


# =========================
# HELPERS BÁSICOS
# =========================
def _safe_now_str() -> str:
    try:
        return pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return ""


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
        etapa = str(valor or "origem").strip().lower()
    except Exception:
        etapa = "origem"

    if etapa not in ETAPAS_VALIDAS:
        return "origem"
    return etapa


def _ir_para(etapa: str) -> None:
    sincronizar_etapa_global(_normalizar_etapa(etapa))
    st.rerun()


# =========================
# VERSIONAMENTO
# =========================
def _ler_version_json() -> dict:
    try:
        if not VERSION_JSON_PATH.exists():
            return {}
        bruto = VERSION_JSON_PATH.read_text(encoding="utf-8")
        data = json.loads(bruto)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _salvar_version_json(data: dict) -> bool:
    try:
        VERSION_JSON_PATH.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return True
    except Exception:
        return False


def _sincronizar_version_json_com_app() -> dict:
    atual = _ler_version_json()
    history = atual.get("history", [])
    if not isinstance(history, list):
        history = []

    version_json = str(atual.get("version") or "").strip()
    if version_json == APP_VERSION:
        return atual or {
            "version": APP_VERSION,
            "updated_at": _safe_now_str(),
            "last_title": "Resgate de layout estável",
            "last_description": "App.py simplificado para evitar conflito visual com o wizard da origem.",
            "history": history,
        }

    novo_registro = {
        "version": APP_VERSION,
        "date": _safe_now_str(),
        "title": "Resgate de layout estável",
        "description": "App.py simplificado para evitar conflito visual com o wizard da origem.",
    }

    if not any(
        isinstance(item, dict)
        and str(item.get("version") or "").strip() == APP_VERSION
        for item in history
    ):
        history.append(novo_registro)

    novo = {
        "version": APP_VERSION,
        "updated_at": _safe_now_str(),
        "last_title": "Resgate de layout estável",
        "last_description": "App.py simplificado para evitar conflito visual com o wizard da origem.",
        "history": history,
    }
    _salvar_version_json(novo)
    return novo


def _resolver_app_version_exibida(version_data: dict) -> str:
    try:
        version_json = str((version_data or {}).get("version") or "").strip()
        if version_json:
            return version_json
    except Exception:
        pass
    return APP_VERSION


# =========================
# FLUXO GLOBAL
# =========================
def _obter_df_fluxo():
    for chave in [
        "df_final",
        "df_saida",
        "df_preview_mapeamento",
        "df_precificado",
        "df_calc_precificado",
        "df_origem",
    ]:
        df = st.session_state.get(chave)
        if _safe_df(df):
            return df
    return None


def _pode_ir_para_precificacao() -> bool:
    df_origem = st.session_state.get("df_origem")
    return _safe_df_com_linhas(df_origem)


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
    df_final = _obter_df_fluxo()
    return _safe_df_com_linhas(df_final)


def _resolver_autoetapa() -> str:
    etapa_atual = _normalizar_etapa(obter_etapa_global())

    if etapa_atual == "precificacao" and not _pode_ir_para_precificacao():
        return "origem"

    if etapa_atual == "mapeamento" and not _pode_ir_para_mapeamento():
        return "origem"

    if etapa_atual == "final" and not _pode_ir_para_final():
        return "origem"

    return etapa_atual


# =========================
# UI BASE
# =========================
def _render_topo(version_data: dict) -> None:
    versao_exibida = _resolver_app_version_exibida(version_data)
    st.title("IA Planilhas")
    st.caption(f"Versão: {versao_exibida}")


def _render_nav_precificacao() -> None:
    st.markdown("---")
    col1, col2 = st.columns(2, gap="small")

    with col1:
        if st.button(
            "⬅️ Voltar para origem",
            use_container_width=True,
            key="app_btn_voltar_precificacao",
        ):
            _ir_para("origem")

    with col2:
        if st.button(
            "Continuar ➜",
            use_container_width=True,
            key="app_btn_continuar_precificacao",
            type="primary",
            disabled=not _pode_ir_para_mapeamento(),
        ):
            _ir_para("mapeamento")


def _render_nav_mapeamento() -> None:
    st.markdown("---")
    col1, col2 = st.columns(2, gap="small")

    with col1:
        if st.button(
            "⬅️ Voltar para precificação",
            use_container_width=True,
            key="app_btn_voltar_mapeamento",
        ):
            _ir_para("precificacao")

    with col2:
        if st.button(
            "Continuar ➜",
            use_container_width=True,
            key="app_btn_continuar_mapeamento",
            type="primary",
            disabled=not _pode_ir_para_final(),
        ):
            _ir_para("final")


def _render_nav_final() -> None:
    st.markdown("---")
    if st.button(
        "⬅️ Voltar para mapeamento",
        use_container_width=True,
        key="app_btn_voltar_final",
    ):
        _ir_para("mapeamento")


def _render_etapa(etapa_atual: str) -> None:
    if etapa_atual == "origem":
        render_origem_dados()
        return

    if etapa_atual == "precificacao":
        if not _pode_ir_para_precificacao():
            st.warning("⚠️ Carregue a base na origem antes de acessar a precificação.")
            if st.button("⬅️ Voltar para origem", use_container_width=True):
                _ir_para("origem")
            st.stop()

        render_origem_precificacao()
        _render_nav_precificacao()
        return

    if etapa_atual == "mapeamento":
        if not _pode_ir_para_mapeamento():
            st.warning("⚠️ Carregue os dados antes de acessar o mapeamento.")
            if st.button("⬅️ Voltar para origem", use_container_width=True):
                _ir_para("origem")
            st.stop()

        render_origem_mapeamento()
        _render_nav_mapeamento()
        return

    if etapa_atual == "final":
        df_fluxo = _obter_df_fluxo()
        if not _safe_df(df_fluxo):
            st.warning("⚠️ Nenhum dado disponível para a etapa final.")
            if st.button("⬅️ Voltar para mapeamento", use_container_width=True):
                _ir_para("mapeamento")
            st.stop()

        render_preview_final()
        _render_nav_final()
        return

    _ir_para("origem")


# =========================
# INIT
# =========================
inicializar_app()
garantir_estado_base()

VERSION_DATA = _sincronizar_version_json_com_app()

etapa_atual = _resolver_autoetapa()
sincronizar_etapa_global(etapa_atual)

_render_topo(VERSION_DATA)
_render_etapa(etapa_atual)

with st.expander("Debug", expanded=False):
    render_debug_panel()
