import streamlit as st
from datetime import datetime

# =========================
# 🧠 INICIALIZA LOG
# =========================
def iniciar_log():
    if "log" not in st.session_state:
        st.session_state.log = []


# =========================
# 📝 ADICIONAR LOG
# =========================
def log(msg):
    agora = datetime.now().strftime("%H:%M:%S")
    linha = f"[{agora}] {msg}"

    st.session_state.log.append(linha)


# =========================
# 📥 DOWNLOAD LOG
# =========================
def botao_download_log():
    if "log" not in st.session_state or not st.session_state.log:
        return

    conteudo = "\n".join(st.session_state.log)

    st.download_button(
        label="⬇️ Baixar LOG",
        data=conteudo,
        file_name="log_processamento.txt",
        mime="text/plain"
    )


# =========================
# 👁️ MOSTRAR LOG (OPCIONAL)
# =========================
def mostrar_log():
    if "log" in st.session_state and st.session_state.log:
        st.text_area("📜 Log do processamento", "\n".join(st.session_state.log), height=200)
