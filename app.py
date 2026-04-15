
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from bling_app_zero.ui.app_helpers import (
    garantir_estado_base,
    obter_etapa_global,
    render_debug_panel,
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

APP_VERSION = "1.0.48"
VERSION_JSON_PATH = Path(__file__).with_name("version.json")

ETAPAS_VALIDAS = {"origem", "precificacao", "mapeamento", "final"}
ETAPAS_CONFIG = [
    {"key": "origem", "ordem": 1, "titulo": "Origem"},
    {"key": "precificacao", "ordem": 2, "titulo": "Precificação"},
    {"key": "mapeamento", "ordem": 3, "titulo": "Mapeamento"},
    {"key": "final", "ordem": 4, "titulo": "Final"},
]


# =========================
# HELPERS BÁSICOS
# =========================
def _safe_now_str() -> str:
    try:
        return pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return ""


def _safe_df(df: Any) -> bool:
    try:
        return isinstance(df, pd.DataFrame) and len(df.columns) > 0
    except Exception:
        return False


def _safe_df_com_linhas(df: Any) -> bool:
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


def _copiar_df(df: Any) -> Any:
    try:
        return df.copy()
    except Exception:
        return df


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
            "last_title": "Coerência de fluxo reforçada",
            "last_description": "Estados e etapa final alinhados.",
            "history": history,
        }

    novo_registro = {
        "version": APP_VERSION,
        "date": _safe_now_str(),
        "title": "Coerência de fluxo reforçada",
        "description": "Estados e etapa final alinhados.",
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
        "last_title": "Coerência de fluxo reforçada",
        "last_description": "Estados e etapa final alinhados.",
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
def _obter_df_fluxo() -> pd.DataFrame | None:
    for chave in [
        "df_final",
        "df_preview_mapeamento",
        "df_saida",
        "df_precificado",
        "df_calc_precificado",
        "df_origem",
    ]:
        df = st.session_state.get(chave)
        if _safe_df(df):
            return df
    return None


def _tem_origem_valida() -> bool:
    df_origem = st.session_state.get("df_origem")
    if _safe_df_com_linhas(df_origem):
        return True

    for chave in ["df_saida", "df_final", "df_precificado", "df_calc_precificado"]:
        df = st.session_state.get(chave)
        if _safe_df_com_linhas(df):
            st.session_state["df_origem"] = _copiar_df(df)
            return True

    return False


def _tem_dados_precificados_ou_preparados() -> bool:
    for chave in [
        "df_precificado",
        "df_calc_precificado",
        "df_saida",
        "df_final",
    ]:
        if _safe_df_com_linhas(st.session_state.get(chave)):
            return True
    return False


def _tem_dados_mapeados_ou_finais() -> bool:
    for chave in [
        "df_preview_mapeamento",
        "df_final",
    ]:
        if _safe_df_com_linhas(st.session_state.get(chave)):
            return True
    return False


def _pode_ir_para_precificacao() -> bool:
    return _tem_origem_valida()


def _pode_ir_para_mapeamento() -> bool:
    if _tem_dados_precificados_ou_preparados():
        return True
    return _tem_origem_valida()


def _pode_ir_para_final() -> bool:
    return _tem_dados_mapeados_ou_finais()


def _resolver_autoetapa() -> str:
    etapa_atual = _normalizar_etapa(obter_etapa_global())

    if etapa_atual == "final":
        if _pode_ir_para_final():
            return "final"
        if _pode_ir_para_mapeamento():
            return "mapeamento"
        if _pode_ir_para_precificacao():
            return "precificacao"
        return "origem"

    if etapa_atual == "mapeamento":
        if _pode_ir_para_mapeamento():
            return "mapeamento"
        if _pode_ir_para_precificacao():
            return "precificacao"
        return "origem"

    if etapa_atual == "precificacao":
        if _pode_ir_para_precificacao():
            return "precificacao"
        return "origem"

    return "origem"


# =========================
# UI BASE
# =========================
def _inject_layout_css() -> None:
    st.markdown(
        """
        <style>
            .main .block-container {
                padding-top: 1rem;
                padding-bottom: 2rem;
            }

            .ia-topbar {
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: .75rem;
                margin-bottom: 1rem;
                padding: .85rem 1rem;
                border: 1px solid rgba(120, 120, 120, 0.18);
                border-radius: 16px;
                background: rgba(255, 255, 255, 0.02);
            }

            .ia-topbar__title {
                font-size: 1.05rem;
                font-weight: 700;
                line-height: 1.2;
                margin: 0;
            }

            .ia-topbar__version {
                font-size: .86rem;
                opacity: .82;
                white-space: nowrap;
            }

            .ia-progress {
                display: flex;
                flex-wrap: wrap;
                gap: .5rem;
                margin-bottom: 1rem;
            }

            .ia-pill {
                border: 1px solid rgba(120, 120, 120, 0.18);
                border-radius: 999px;
                padding: .45rem .8rem;
                font-size: .9rem;
                opacity: .82;
            }

            .ia-pill--active {
                border-color: rgba(255, 255, 255, 0.28);
                font-weight: 700;
                opacity: 1;
            }

            .ia-stage-shell {
                margin-top: .25rem;
            }

            .ia-nav-wrap {
                margin-top: 1rem;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_topbar(version_data: dict) -> None:
    versao_exibida = _resolver_app_version_exibida(version_data)
    st.markdown(
        f"""
        <div class="ia-topbar">
            <div class="ia-topbar__title">IA Planilhas</div>
            <div class="ia-topbar__version">v{versao_exibida}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_progress(etapa_atual: str) -> None:
    partes = []
    for item in ETAPAS_CONFIG:
        classe = "ia-pill ia-pill--active" if item["key"] == etapa_atual else "ia-pill"
        partes.append(
            f'<div class="{classe}">{item["ordem"]}. {item["titulo"]}</div>'
        )

    st.markdown(
        f'<div class="ia-progress">{"".join(partes)}</div>',
        unsafe_allow_html=True,
    )


def _etapa_tem_navegacao_interna(etapa_atual: str) -> bool:
    return etapa_atual in {"precificacao"}


def _render_nav(etapa_atual: str) -> None:
    if etapa_atual == "origem":
        return

    if _etapa_tem_navegacao_interna(etapa_atual):
        return

    st.markdown('<div class="ia-nav-wrap">', unsafe_allow_html=True)
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

    st.markdown("</div>", unsafe_allow_html=True)


def _render_etapa(etapa_atual: str) -> None:
    st.markdown('<div class="ia-stage-shell">', unsafe_allow_html=True)

    if etapa_atual == "origem":
        render_origem_dados()
        st.markdown("</div>", unsafe_allow_html=True)
        return

    if etapa_atual == "precificacao":
        render_origem_precificacao()
        st.markdown("</div>", unsafe_allow_html=True)
        return

    if etapa_atual == "mapeamento":
        render_origem_mapeamento()
        st.markdown("</div>", unsafe_allow_html=True)
        return

    render_preview_final()
    st.markdown("</div>", unsafe_allow_html=True)


# =========================
# INIT
# =========================
inicializar_app()
garantir_estado_base()

VERSION_DATA = _sincronizar_version_json_com_app()

_inject_layout_css()

etapa_atual = _resolver_autoetapa()
sincronizar_etapa_global(etapa_atual)

_render_topbar(VERSION_DATA)
_render_progress(etapa_atual)
_render_etapa(etapa_atual)
_render_nav(etapa_atual)

with st.expander("Debug", expanded=False):
    render_debug_panel()
