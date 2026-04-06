import time
import traceback
import streamlit as st


def render_send_panel():

    st.subheader("Envio por API")

    if "df_final" not in st.session_state or st.session_state["df_final"] is None:
        st.warning("Gere a planilha primeiro")
        return

    df = st.session_state["df_final"]

    if df.empty:
        st.warning("Nada para enviar")
        return

    st.info(f"{len(df)} registros prontos")

    if st.button("Enviar para o Bling", width="stretch"):

        progress = st.progress(0)
        status = st.empty()

        total = len(df)

        try:
            for i, _ in df.iterrows():

                # SIMULAÇÃO (trocar depois pela API real)
                time.sleep(0.02)

                pct = int((i + 1) / total * 100)
                progress.progress(pct)
                status.text(f"Enviando {i+1}/{total}")

            st.success("Envio concluído")

        except Exception as e:
            st.error(f"Erro: {e}")
            st.text(traceback.format_exc())
