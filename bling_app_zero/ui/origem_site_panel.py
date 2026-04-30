from bling_app_zero.core.instant_scraper.quality_score import aplicar_score_qualidade, resumo_qualidade, remover_produtos_fracos

# dentro de _render_resultado_final substituir bloco inicial:
    df = _aplicar_auto_merge()
    if not _df_ok(df):
        return

    df = aplicar_score_qualidade(df)
    resumo = resumo_qualidade(df)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total", resumo["total"])
    col2.metric("Bons", resumo["bom"])
    col3.metric("Revisar", resumo["revisar"])
    col4.metric("Fracos", resumo["fraco"])

    if st.button("Remover produtos fracos"):
        df = remover_produtos_fracos(df, score_minimo=50)
        st.session_state["df_origem"] = df

    base = _ordenar_preview(df)
    st.session_state["df_origem"] = base
