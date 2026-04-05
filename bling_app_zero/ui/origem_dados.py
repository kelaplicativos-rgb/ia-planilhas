# 🔥 BLOQUEIO NORMAL (já existente)
if pendencias_gtin:
    st.error("Não foi possível liberar o download porque ainda existem pendências.")

    # =========================
    # NOVO BOTÃO 🔥
    # =========================
    if st.button("⚠️ Forçar limpeza e liberar download"):
        st.warning("Download liberado manualmente. GTINs inválidos permanecerão vazios.")

        st.session_state["forcar_download"] = True

# =========================
# LIBERAÇÃO FINAL
# =========================

liberar_download = not pendencias_gtin or st.session_state.get("forcar_download", False)

if liberar_download:
    st.success("Download liberado.")

    # botão de download (mantém o seu atual)
    st.download_button(
        label="📥 Baixar planilha final",
        data=arquivo_excel,
        file_name="bling_importacao.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
