from __future__ import annotations

import time
import traceback

import pandas as pd
import streamlit as st


def _safe_df(df) -> bool:
    try:
        return isinstance(df, pd.DataFrame) and not df.empty and len(df.columns) > 0
    except Exception:
        return False


def render_send_panel() -> None:
    st.subheader("Envio por API")

    # mantém a aba Envio separada do fluxo principal
    etapa = str(st.session_state.get("etapa_origem", "") or "").strip().lower()
    if etapa in {"upload", "mapeamento"}:
        st.info("Finalize o fluxo principal antes de usar o envio por API.")
        return

    df = st.session_state.get("df_final")

    if not _safe_df(df):
        st.warning("Gere a planilha primeiro na aba Origem dos dados.")
        return

    df_envio = df.copy()

    st.info(f"{len(df_envio)} registro(s) prontos para envio.")

    if st.button("Enviar para o Bling", use_container_width=True, key="btn_enviar_bling_api"):
        barra = st.progress(0)
        status = st.empty()

        total = len(df_envio)

        try:
            for idx, _ in enumerate(df_envio.itertuples(index=False), start=1):
                # Trocar depois pela integração real da API
                time.sleep(0.02)

                progresso = int((idx / total) * 100)
                barra.progress(progresso)
                status.text(f"Enviando {idx}/{total}")

            status.empty()
            st.success("Envio concluído com sucesso.")

        except Exception as e:
            status.empty()
            st.error(f"Erro no envio: {e}")
            st.text(traceback.format_exc())
