from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

try:
    from bling_app_zero.ui.app_helpers import (
        garantir_estado_base,
        log_debug,
        render_debug_panel,
        render_preview_final,
    )
except ImportError:
    from bling_app_zero.ui.app_helpers import (
        garantir_estado_base,
        log_debug,
        render_preview_final,
    )

    def render_debug_panel():
        return None

from bling_app_zero.ui.origem_dados import render_origem_dados
from bling_app_zero.ui.origem_mapeamento import render_origem_mapeamento
from bling_app_zero.ui.send_panel import render_send_panel
from bling_app_zero.utils.init_app import inicializar_app


# =========================
# CONFIG
# =========================
st.set_page_config(page_title="IA Planilhas Bling", layout="wide")

APP_VERSION = "1.0.27"
APP_CHANGELOG_TITULO = "Sistema de versionamento automático"
APP_CHANGELOG_DESCRICAO = "Sincronização automática com version.json + histórico de mudanças."


# =========================
# VERSIONAMENTO AUTOMÁTICO
# =========================
def _agora_iso() -> str:
    try:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return ""


def _carregar_json(caminho: Path) -> dict:
    try:
        if not caminho.exists():
            return {}
        return json.loads(caminho.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _salvar_json(caminho: Path, data: dict):
    try:
        caminho.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception:
        pass


def _sync_version():
    try:
        path = Path("version.json")
        data = _carregar_json(path)

        versao_atual = str(data.get("version") or "")
        historico = data.get("history") or []

        if not isinstance(historico, list):
            historico = []

        if versao_atual != APP_VERSION:
            historico.append({
                "version": APP_VERSION,
                "date": _agora_iso(),
                "title": APP_CHANGELOG_TITULO,
                "description": APP_CHANGELOG_DESCRICAO,
            })

        novo = {
            "version": APP_VERSION,
            "updated_at": _agora_iso(),
            "last_title": APP_CHANGELOG_TITULO,
            "last_description": APP_CHANGELOG_DESCRICAO,
            "history": historico,
        }

        _salvar_json(path, novo)

    except Exception:
        pass


# 🔥 EXECUTA AUTOMÁTICO
_sync_version()


# =========================
# INICIALIZAÇÃO
# =========================
inicializar_app()
garantir_estado_base()


# =========================
# HELPERS DE ETAPA
# =========================
ETAPAS_VALIDAS = {"origem", "mapeamento", "final", "envio"}


def _safe_df(df) -> bool:
    try:
        return isinstance(df, pd.DataFrame) and len(df.columns) > 0
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


def _ir_para(etapa: str):
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


# =========================
# UI
# =========================
st.title("IA Planilhas → Bling")
st.caption(f"Versão: {APP_VERSION}")

if st.session_state.get("_cache_log"):
    st.info(st.session_state.get("_cache_log"))


# =========================
# CONTROLE DE ETAPA
# =========================
etapa = _sincronizar_etapa_global(_obter_etapa_atual())

if etapa not in ETAPAS_VALIDAS:
    log_debug(f"Etapa inválida detectada no app.py: {etapa}", "ERROR")
    _ir_para("origem")


# =========================
# ETAPA 1 — ORIGEM
# =========================
if etapa == "origem":
    render_origem_dados()


# =========================
# ETAPA 2 — MAPEAMENTO
# =========================
elif etapa == "mapeamento":
    render_origem_mapeamento()


# =========================
# ETAPA 3 — FINAL
# =========================
elif etapa == "final":
    df_fluxo = _obter_df_fluxo()

    if not _safe_df(df_fluxo):
        log_debug("FINAL sem dados válidos", "ERROR")
        st.warning("⚠️ Nenhum dado disponível. Volte para o mapeamento.")

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
        if st.button("🚀 Ir para envio", use_container_width=True, type="primary"):
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
    _ir_para("origem")


# =========================
# DEBUG
# =========================
render_debug_panel()
