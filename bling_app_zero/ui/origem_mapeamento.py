from __future__ import annotations

from io import BytesIO
import pandas as pd
import streamlit as st


# ==========================================================
# HELPERS
# ==========================================================
def _safe_dataframe_preview(df: pd.DataFrame, rows: int = 20):
    if df is None or df.empty:
        return pd.DataFrame()
    return df.head(rows)


def _build_log():
    logs = st.session_state.get("logs", [])
    texto = "\n".join(logs) if logs else "Sem logs"
    return texto


# ==========================================================
# MAIN
# ==========================================================
def render_origem_mapeamento():
    df = st.session_state.get("df_final")

    if df is None or df.empty:
        st.warning("Nenhum dado disponível para mapeamento.")
        return

    operacao = st.session_state.get("operacao_tipo", "")
    operacao_label = st.session_state.get("operacao_label", "")

    if operacao_label:
        st.success(f"Fluxo selecionado: {operacao_label}")
    else:
        st.warning("Nenhuma operação selecionada.")

    st.markdown("### Preview da saída")
    st.dataframe(_safe_dataframe_preview(df), use_container_width=True)

    st.divider()

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("⬅️ Voltar", use_container_width=True, key="btn_voltar_mapeamento"):
            st.session_state["etapa_origem"] = "upload"
            st.rerun()

    with col2:
        try:
            buffer = BytesIO()
            df.to_excel(buffer, index=False)
            buffer.seek(0)

            nome_arquivo = "saida.xlsx"
            if operacao == "cadastro":
                nome_arquivo = "cadastro.xlsx"
            elif operacao == "estoque":
                nome_arquivo = "estoque.xlsx"

            st.download_button(
                "⬇️ Baixar planilha",
                buffer,
                nome_arquivo,
                use_container_width=True,
                key="btn_download_planilha_final",
            )
        except Exception as e:
            st.error(f"Erro ao gerar Excel: {e}")

    with col3:
        st.download_button(
            "📄 Baixar log",
            _build_log(),
            "log.txt",
            use_container_width=True,
            key="btn_download_log_mapeamento",
        )

    st.divider()

    if operacao == "cadastro":
        st.info("Pronto para seguir com o fluxo de cadastro / atualização de produtos.")
    elif operacao == "estoque":
        st.info("Pronto para seguir com o fluxo de atualização de estoque.")
    else:
        st.warning("Operação não identificada.")
