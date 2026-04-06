from __future__ import annotations

from datetime import datetime
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
    return "\n".join(logs) if logs else "Sem logs"


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

    # ==========================================================
    # HEADER FLUXO
    # ==========================================================
    if operacao_label:
        st.success(f"Fluxo selecionado: {operacao_label}")
    else:
        st.warning("Nenhuma operação selecionada")

    st.divider()

    # ==========================================================
    # PREVIEW
    # ==========================================================
    st.markdown("### Pré-visualização dos dados finais")
    st.dataframe(_safe_dataframe_preview(df), use_container_width=True)

    st.divider()

    # ==========================================================
    # AÇÕES
    # ==========================================================
    col1, col2, col3 = st.columns(3)

    # =========================
    # VOLTAR
    # =========================
    with col1:
        if st.button("⬅️ Voltar", use_container_width=True):
            st.session_state["etapa_origem"] = "upload"
            st.rerun()

    # =========================
    # DOWNLOAD
    # =========================
    with col2:
        try:
            from io import BytesIO

            buffer = BytesIO()
            df.to_excel(buffer, index=False)
            buffer.seek(0)

            st.download_button(
                "⬇️ Baixar planilha",
                buffer,
                "saida.xlsx",
                use_container_width=True,
            )
        except Exception as e:
            st.error(f"Erro ao gerar Excel: {e}")

    # =========================
    # LOG
    # =========================
    with col3:
        st.download_button(
            "📄 Baixar log",
            _build_log(),
            "log.txt",
            use_container_width=True,
        )

    st.divider()

    # ==========================================================
    # PRÓXIMO PASSO (FLUXO)
    # ==========================================================
    st.markdown("### Próxima etapa")

    if operacao == "cadastro":
        st.info("Pronto para gerar planilha de CADASTRO para o Bling")

    elif operacao == "estoque":
        st.info("Pronto para gerar planilha de ESTOQUE para o Bling")

    else:
        st.warning("Selecione uma operação na etapa anterior")

    if st.button("🚀 Gerar saída final", use_container_width=True):
        try:
            # 🔥 aqui futuramente entra geração real Bling
            st.success("Fluxo pronto — integração final preparada")
        except Exception as e:
            st.error(f"Erro na geração final: {e}")
