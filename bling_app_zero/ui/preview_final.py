from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.ui.app_helpers import (
    safe_df_estrutura,
    voltar_etapa_anterior,
)


def _normalizar_url_imagens(valor) -> str:
    texto = str(valor or "").strip()
    if not texto:
        return ""

    texto = texto.replace("\n", "|").replace("\r", "|")
    texto = texto.replace(";", "|").replace(",", "|")

    partes = [p.strip() for p in texto.split("|") if p.strip()]
    vistos = set()
    urls = []

    for parte in partes:
        if parte not in vistos:
            vistos.add(parte)
            urls.append(parte)

    return "|".join(urls)


def _blindar_coluna_imagens(df: pd.DataFrame) -> pd.DataFrame:
    if not safe_df_estrutura(df):
        return df

    base = df.copy()

    for col in base.columns:
        nome = str(col).strip().lower()
        if nome in {"url imagens", "url imagem", "imagens", "imagem"} or "imagem" in nome:
            base[col] = base[col].apply(_normalizar_url_imagens)

    return base


def render_preview_final() -> None:
    st.subheader("4. Preview Final")
    st.caption("Confira o resultado final antes do download.")

    df_final = st.session_state.get("df_final")

    if not safe_df_estrutura(df_final):
        st.warning("O resultado final ainda não foi gerado.")
        if st.button("⬅️ Voltar para mapeamento", use_container_width=True, key="btn_voltar_preview_sem_df"):
            voltar_etapa_anterior()
        return

    df_final = _blindar_coluna_imagens(df_final)
    st.session_state["df_final"] = df_final

    if df_final.empty:
        st.dataframe(pd.DataFrame(columns=df_final.columns), use_container_width=True)
    else:
        st.dataframe(df_final.head(100), use_container_width=True)

    csv_bytes = df_final.to_csv(index=False).encode("utf-8-sig")

    st.download_button(
        label="📥 Baixar CSV final",
        data=csv_bytes,
        file_name="bling_saida_final.csv",
        mime="text/csv",
        use_container_width=True,
    )

    col1, col2 = st.columns(2)

    with col1:
        if st.button("⬅️ Voltar para mapeamento", use_container_width=True, key="btn_voltar_preview"):
            voltar_etapa_anterior()

    with col2:
        st.button("✅ Finalizado", use_container_width=True, disabled=True, key="btn_finalizado_preview")
