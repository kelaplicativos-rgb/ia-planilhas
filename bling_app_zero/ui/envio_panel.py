import time
import traceback
import streamlit as st


def render_send_panel():

    st.subheader("Envio por API")

    # =========================
    # VALIDAÇÃO
    # =========================
    if "df_final" not in st.session_state or st.session_state["df_final"] is None:
        st.warning("Gere a planilha primeiro na aba Origem dos dados")
        return

    df = st.session_state["df_final"]

    if df.empty:
        st.warning("DataFrame vazio. Nada para enviar.")
        return

    # =========================
    # INFO
    # =========================
    st.info(f"{len(df)} registros prontos para envio")

    # =========================
    # BOTÃO DE ENVIO
    # =========================
    if st.button("Enviar para o Bling", width="stretch"):

        progress_bar = st.progress(0)
        status_text = st.empty()

        total = len(df)

        try:
            for i, row in df.iterrows():

                # 🔥 AQUI ENTRA SUA API FUTURA
                # Exemplo simulado:
                time.sleep(0.02)

                progresso = int((i + 1) / total * 100)
                progress_bar.progress(progresso)
                status_text.text(f"Enviando {i+1}/{total}")

            st.success("Envio concluído com sucesso")

        except Exception as e:
            st.error(f"Erro no envio: {e}")
            st.text(traceback.format_exc())
