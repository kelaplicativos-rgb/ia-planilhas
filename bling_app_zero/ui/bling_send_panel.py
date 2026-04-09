from __future__ import annotations

import time
import streamlit as st
import pandas as pd

from bling_app_zero.core.bling_api import BlingAPIClient
from bling_app_zero.ui.origem_dados_estado import safe_df_dados


# =========================
# HELPERS
# =========================
def _get_df_saida():
    df = st.session_state.get("df_saida")

    if safe_df_dados(df):
        return df.copy()

    return None


def _log(msg: str):
    logs = st.session_state.get("_bling_logs", [])
    logs.append(msg)
    st.session_state["_bling_logs"] = logs


def _render_logs():
    logs = st.session_state.get("_bling_logs", [])
    if logs:
        st.markdown("### 📋 Log de envio")
        for l in logs[-50:]:
            st.write(l)


# =========================
# ENVIO NORMAL
# =========================
def _enviar_normal(df: pd.DataFrame, deposito: str):
    client = BlingAPIClient()

    progresso = st.progress(0)
    total = len(df)

    ok_count = 0
    erro_count = 0

    for i, row in df.iterrows():
        codigo = str(row.get("codigo") or "").strip()

        if not codigo:
            erro_count += 1
            continue

        ok, resp = client.upsert_product(row.to_dict())

        if ok:
            ok_count += 1
            _log(f"✅ Produto enviado: {codigo}")
        else:
            erro_count += 1
            _log(f"❌ Erro produto {codigo}: {resp}")

        # estoque
        estoque = row.get("estoque", 0)

        client.update_stock(
            codigo=codigo,
            estoque=float(estoque or 0),
            deposito_id=deposito,
        )

        progresso.progress((i + 1) / total)

    return ok_count, erro_count


# =========================
# ENVIO TURBO
# =========================
def _enviar_turbo(df: pd.DataFrame, deposito: str):
    client = BlingAPIClient()

    progresso = st.progress(0)
    total = len(df)

    ok_count = 0
    erro_count = 0

    # 🔥 TURBO: sem delay + sem logs pesados
    for i, row in df.iterrows():
        codigo = str(row.get("codigo") or "").strip()

        if not codigo:
            erro_count += 1
            continue

        ok, _ = client.upsert_product(row.to_dict())

        if ok:
            ok_count += 1
        else:
            erro_count += 1

        estoque = row.get("estoque", 0)

        client.update_stock(
            codigo=codigo,
            estoque=float(estoque or 0),
            deposito_id=deposito,
        )

        progresso.progress((i + 1) / total)

    return ok_count, erro_count


# =========================
# UI PRINCIPAL
# =========================
def render_send_panel():
    st.subheader("🚀 Enviar para Bling")

    df = _get_df_saida()

    if df is None:
        st.warning("⚠️ Nenhum dado pronto para envio.")
        return

    col1, col2 = st.columns(2)

    with col1:
        modo = st.radio(
            "Modo de envio",
            ["Normal", "Turbo"],
            horizontal=True,
        )

    with col2:
        deposito = st.text_input("Depósito (ID)", value="")

    if st.button("🚀 Enviar agora", use_container_width=True):
        st.session_state["_bling_logs"] = []

        inicio = time.time()

        if modo == "Turbo":
            ok, erro = _enviar_turbo(df, deposito)
        else:
            ok, erro = _enviar_normal(df, deposito)

        tempo = round(time.time() - inicio, 2)

        st.success(
            f"✅ Enviado com sucesso: {ok} | ❌ Erros: {erro} | ⏱️ {tempo}s"
        )

    _render_logs()
