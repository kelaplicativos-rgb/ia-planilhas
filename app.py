
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
from bling_app_zero.ui.origem_precificacao import render_origem_precificacao
from bling_app_zero.ui.origem_mapeamento import render_origem_mapeamento
from bling_app_zero.ui.preview_final import render_preview_final
from bling_app_zero.utils.init_app import inicializar_app


st.set_page_config(page_title="IA Planilhas", layout="wide")

APP_VERSION = "1.0.42"
VERSION_JSON_PATH = Path(__file__).with_name("version.json")

ETAPAS_VALIDAS = {"origem", "precificacao", "mapeamento", "final"}
ETAPAS_CONFIG = [
    {"key": "origem", "ordem": 1, "titulo": "Origem"},
    {"key": "precificacao", "ordem": 2, "titulo": "Precificação"},
    {"key": "mapeamento", "ordem": 3, "titulo": "Mapeamento"},
    {"key": "final", "ordem": 4, "titulo": "Final"},
]


# =========================================================
# VERSIONAMENTO
# =========================================================
def _safe_now_str() -> str:
    try:
        return pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return ""


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
            "last_title": "Fluxo com precificação separada",
            "last_description": "Origem, precificação, mapeamento e final em etapas distintas.",
            "history": history,
        }

    novo_registro = {
        "version": APP_VERSION,
        "date": _safe_now_str(),
        "title": "Fluxo com precificação separada",
        "description": "Origem, precificação, mapeamento e final em etapas distintas.",
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
        "last_title": "Fluxo com precificação separada",
        "last_description": "Origem, precificação, mapeamento e final em etapas distintas.",
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


# =========================================================
# HELPERS DE FLUXO
# =========================================================
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
        etapa_normalizada = str(valor or "origem").strip().lower()
    except Exception:
        etapa_normalizada = "origem"

    if etapa_normalizada not in ETAPAS_VALIDAS:
        return "origem"
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
    return "origem"


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
    for chave in ["df_final", "df_saida", "df_precificado", "df_calc_precificado", "df_origem"]:
        df = st.session_state.get(chave)
        if _safe_df(df):
            return df
    return None


def _pode_ir_para_precificacao() -> bool:
    return _safe_df_com_linhas(st.session_state.get("df_origem"))


def _pode_ir_para_mapeamento() -> bool:
    for chave in ["df_saida", "df_final", "df_precificado", "df_calc_precificado", "df_origem"]:
        if _safe_df_com_linhas(st.session_state.get(chave)):
            return True
    return False


def _pode_ir_para_final() -> bool:
    return _safe_df_com_linhas(_obter_df_fluxo())


def _resolver_autoetapa() -> str:
    etapa_atual = _obter_etapa_atual()

    if etapa_atual == "precificacao" and not _pode_ir_para_precificacao():
        return "origem"

    if etapa_atual == "mapeamento" and not _pode_ir_para_mapeamento():
        return "origem"

    if etapa_atual == "final" and not _pode_ir_para_final():
        return "origem"

    return etapa_atual


# =========================================================
# LAYOUT
# =========================================================
def _inject_layout_css() -> None:
    st.markdown(
        """
        <style>
            .block-container {
                max-width: 760px;
                padding-top: 0.65rem;
                padding-bottom: 2rem;
            }

            [data-testid="stHeader"] {
                background: transparent;
            }

            .ia-top {
                display: flex;
                align-items: center;
                justify-content: space-between;
                margin-bottom: 0.70rem;
            }

            .ia-logo {
                font-size: 0.95rem;
                font-weight: 800;
                color: #0A2259;
            }

            .ia-version {
                font-size: 0.78rem;
                opacity: 0.7;
            }

            .ia-progress {
                display: flex;
                gap: 8px;
                margin: 0.35rem 0 1rem 0;
                flex-wrap: wrap;
            }

            .ia-progress-pill {
                flex: 1 1 120px;
                border-radius: 999px;
                padding: 10px 12px;
                text-align: center;
                font-size: 0.84rem;
                font-weight: 700;
                background: #F1F4F9;
                color: #667085;
                border: 1px solid #E4E7EC;
            }

            .ia-progress-pill.active {
                background: #0A2259;
                color: white;
                border-color: #0A2259;
            }

            .stButton > button,
            .stDownloadButton > button {
                min-height: 54px;
                border-radius: 18px;
                font-weight: 700;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_topbar(version_data: dict) -> None:
    versao_exibida = _resolver_app_version_exibida(version_data)
    st.markdown(
        f"""
        <div class="ia-top">
            <div class="ia-logo">IA Planilhas</div>
            <div class="ia-version">v{versao_exibida}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_progress(etapa_atual: str) -> None:
    partes = []
    for item in ETAPAS_CONFIG:
        classe = "ia-progress-pill active" if item["key"] == etapa_atual else "ia-progress-pill"
        partes.append(f'<div class="{classe}">{item["ordem"]}. {item["titulo"]}</div>')

    st.markdown(
        f'<div class="ia-progress">{"".join(partes)}</div>',
        unsafe_allow_html=True,
    )


def _render_nav(etapa_atual: str) -> None:
    if etapa_atual == "origem":
        return

    col1, col2 = st.columns(2, gap="small")

    with col1:
        if st.button(
            "⬅️ Voltar",
            use_container_width=True,
            key=f"app_btn_voltar_{etapa_atual}",
        ):
            if etapa_atual == "precificacao":
                _ir_para("origem")
            elif etapa_atual == "mapeamento":
                _ir_para("precificacao")
            elif etapa_atual == "final":
                _ir_para("mapeamento")

    with col2:
        if etapa_atual == "precificacao":
            if st.button(
                "Continuar ➜",
                use_container_width=True,
                key="app_btn_continuar_precificacao",
                disabled=not _pode_ir_para_mapeamento(),
            ):
                _ir_para("mapeamento")

        elif etapa_atual == "mapeamento":
            if st.button(
                "Continuar ➜",
                use_container_width=True,
                key="app_btn_continuar_mapeamento",
                disabled=not _pode_ir_para_final(),
            ):
                _ir_para("final")


def _render_etapa(etapa_atual: str) -> None:
    if etapa_atual == "origem":
        render_origem_dados()
        return
    if etapa_atual == "precificacao":
        render_origem_precificacao()
        return
    if etapa_atual == "mapeamento":
        render_origem_mapeamento()
        return
    render_preview_final()


# =========================================================
# EXECUÇÃO
# =========================================================
inicializar_app()
garantir_estado_base()

VERSION_DATA = _sincronizar_version_json_com_app()
_inject_layout_css()

etapa_atual = _resolver_autoetapa()
_sincronizar_etapa_global(etapa_atual)

_render_topbar(VERSION_DATA)
_render_progress(etapa_atual)
_render_etapa(etapa_atual)
_render_nav(etapa_atual)

with st.expander("Debug", expanded=False):
    render_debug_panel()

