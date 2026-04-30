# AUTO MERGE INTEGRATION
from bling_app_zero.core.instant_scraper.auto_merge import auto_merge_produtos

# dentro de _render_resultado_final adicionar antes de mostrar:
    df_visual = st.session_state.get("df_origem")
    df_sitemap = st.session_state.get("sitemap_df")

    if _df_ok(df_visual) and _df_ok(df_sitemap):
        merged = auto_merge_produtos(("sitemap", df_sitemap), ("visual", df_visual))
        st.session_state["df_origem"] = merged
        st.info(f"Auto merge aplicado: {len(merged)} produtos combinados")
