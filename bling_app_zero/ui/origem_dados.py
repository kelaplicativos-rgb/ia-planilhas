
# 🔥 VERSÃO UNIFICADA SITE + AUTOMAÇÃO

def _render_origem_site() -> None:
    st.markdown("### 🌐 Busca no site do fornecedor")

    url_site = st.text_input(
        "URL base do fornecedor",
        key="site_fornecedor_url",
    )

    if not url_site:
        st.info("Informe a URL para iniciar a busca.")
        return

    col1, col2 = st.columns(2)

    with col1:
        if st.button("✨ Varrer site inteiro com GPT", use_container_width=True):
            if not buscar_produtos_site_com_gpt:
                st.error("Módulo de busca por site indisponível.")
                return

            df_site = buscar_produtos_site_com_gpt(base_url=url_site)

            if not safe_df_dados(df_site):
                st.error("Nenhum produto encontrado.")
                return

            st.session_state["df_origem"] = df_site
            st.session_state["origem_upload_tipo"] = "site_gpt"
            st.session_state["origem_upload_nome"] = f"varredura_site_{url_site}"

            st.success(f"{len(df_site)} produtos encontrados")
            _preview_dataframe(df_site, "Preview do site")

    with col2:
        if st.button("⚡ Monitorar automaticamente", use_container_width=True):
            st.session_state["site_auto_loop_ativo"] = True
            st.session_state["site_auto_status"] = "ativo"
            st.success("Monitoramento ativado")

    # 🔥 AUTOMAÇÃO AGORA FICA AQUI
    if st.session_state.get("origem_upload_tipo") == "site_gpt":
        st.markdown("---")
        with st.expander("⚙️ Automação do site", expanded=True):

            col1, col2, col3 = st.columns(3)

            with col1:
                if st.button("▶️ Executar agora", use_container_width=True):
                    df_site = buscar_produtos_site_com_gpt(base_url=url_site)

                    if safe_df_dados(df_site):
                        st.session_state["df_origem"] = df_site
                        st.success(f"{len(df_site)} produtos atualizados")
                        st.rerun()

            with col2:
                if st.button("🟢 Ativar loop", use_container_width=True):
                    st.session_state["site_auto_loop_ativo"] = True
                    st.success("Loop ativado")

            with col3:
                if st.button("⏹️ Parar loop", use_container_width=True):
                    st.session_state["site_auto_loop_ativo"] = False
                    st.info("Loop parado")
