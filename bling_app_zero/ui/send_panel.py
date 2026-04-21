from __future__ import annotations

import json
import time

import pandas as pd
import streamlit as st

from bling_app_zero.core.bling_auth import (
    BlingAuthManager,
    obter_resumo_conexao,
    render_conectar_bling,
)
from bling_app_zero.ui.app_helpers import (
    blindar_df_para_bling,
    log_debug,
    normalizar_texto,
    safe_df_estrutura,
    validar_df_para_download,
)


# =========================
# HELPERS
# =========================

def _safe_str(value) -> str:
    try:
        return str(value or "").strip()
    except Exception:
        return ""


def _resolver_user_key() -> str:
    try:
        qp_user = st.query_params.get("bi")
        if isinstance(qp_user, list):
            qp_user = qp_user[0] if qp_user else ""
        return _safe_str(qp_user) or "default"
    except Exception:
        return "default"


def _safe_import_bling_sync():
    try:
        from bling_app_zero.services.bling import bling_sync
        return bling_sync
    except Exception:
        return None


def _obter_df_final() -> pd.DataFrame:
    df = st.session_state.get("df_final")
    if safe_df_estrutura(df):
        return df.copy()
    return pd.DataFrame()


def _obter_tipo_operacao() -> str:
    return normalizar_texto(st.session_state.get("tipo_operacao") or "cadastro") or "cadastro"


def _obter_deposito_nome() -> str:
    return str(st.session_state.get("deposito_nome", "") or "").strip()


def _download_confirmado() -> bool:
    return bool(st.session_state.get("preview_download_realizado", False))


# =========================
# ENVIO COM PROGRESSO REAL
# =========================

def _enviar_com_progresso(df_final, tipo_operacao, deposito_nome):
    bling_sync = _safe_import_bling_sync()

    total = len(df_final)

    progress_bar = st.progress(0)
    status_text = st.empty()
    log_area = st.empty()

    col1, col2, col3 = st.columns(3)
    metric_criados = col1.empty()
    metric_atualizados = col2.empty()
    metric_erros = col3.empty()

    criados = 0
    atualizados = 0
    erros = 0
    logs = []

    resultados = []

    for i, row in df_final.iterrows():
        progresso = int((i + 1) / total * 100)

        progress_bar.progress(progresso)
        status_text.write(f"🔄 Enviando {i+1}/{total}")

        try:
            if hasattr(bling_sync, "sincronizar_produtos_bling"):
                resultado = bling_sync.sincronizar_produtos_bling(
                    df_final=pd.DataFrame([row]),
                    tipo_operacao=tipo_operacao,
                    deposito_nome=deposito_nome,
                    dry_run=False,
                )

                if resultado.get("ok"):
                    criados += resultado.get("total_criados", 0)
                    atualizados += resultado.get("total_atualizados", 0)
                else:
                    erros += 1

                logs.append(f"✔️ {row.get('Código','')}")

        except Exception as e:
            erros += 1
            logs.append(f"❌ ERRO: {str(e)}")

        metric_criados.metric("Criados", criados)
        metric_atualizados.metric("Atualizados", atualizados)
        metric_erros.metric("Erros", erros)

        log_area.code("\n".join(logs[-10:]))

        time.sleep(0.2)  # evita limite API

    return {
        "ok": erros == 0,
        "total": total,
        "criados": criados,
        "atualizados": atualizados,
        "erros": erros,
    }


# =========================
# UI PRINCIPAL
# =========================

def render_send_panel(*args, **kwargs):
    st.markdown("### 🚀 Envio para o Bling")

    user_key = _resolver_user_key()
    auth = BlingAuthManager(user_key=user_key)

    if not auth.is_configured():
        st.warning("Configure o Bling no secrets.toml")
        return

    df_final = _obter_df_final()
    tipo_operacao = _obter_tipo_operacao()
    deposito_nome = _obter_deposito_nome()

    if safe_df_estrutura(df_final):
        df_final = blindar_df_para_bling(
            df=df_final,
            tipo_operacao_bling=tipo_operacao,
            deposito_nome=deposito_nome,
        )
        st.session_state["df_final"] = df_final

    conectado = auth.get_connection_status().get("connected")

    if not conectado:
        st.warning("🔌 Conecte sua conta do Bling")
        render_conectar_bling()
        return

    if not safe_df_estrutura(df_final):
        st.warning("⚠️ Nenhum dado para envio")
        return

    if not _download_confirmado():
        st.warning("⚠️ Confirme o download primeiro")
        return

    st.success(f"📦 {len(df_final)} produtos prontos para envio")

    if st.button("🚀 Iniciar envio REAL", use_container_width=True):
        log_debug("INICIO ENVIO REAL", nivel="INFO")

        resultado = _enviar_com_progresso(
            df_final,
            tipo_operacao,
            deposito_nome
        )

        st.markdown("### 📊 Resultado Final")

        if resultado["ok"]:
            st.success(f"✅ Enviado com sucesso: {resultado['criados']} produtos")
        else:
            st.error(f"❌ Erros: {resultado['erros']}")

        st.json(resultado)
