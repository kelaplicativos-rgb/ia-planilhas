import time
import traceback
import streamlit as st


def render_send_panel() -> None:
    st.subheader("Envio por API")

    if "df_final" not in st.session_state or st.session_state["df_final"] is None:
        st.warning("Gere a planilha primeiro na aba Origem dos dados.")
        return

    df = st.session_state["df_final"]

    if df is None or df.empty:
        st.warning("Não há dados para enviar.")
        return

    st.info(f"{len(df)} registro(s) prontos para envio.")

    if st.button("Enviar para o Bling", width="stretch"):
        barra = st.progress(0)
        status = st.empty()

        total = len(df)

        try:
            for i, _ in df.iterrows():
                # Trocar depois pela integração real da API
                time.sleep(0.02)

                progresso = int(((i + 1) / total) * 100)
                barra.progress(progresso)
                status.text(f"Enviando {i + 1}/{total}")

            st.success("Envio concluído com sucesso.")
        except Exception as e:
            st.error(f"Erro no envio: {e}")
            st.text(traceback.format_exc())
