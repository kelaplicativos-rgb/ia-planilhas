from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.ui.app_helpers import log_debug
from bling_app_zero.ui.preview_final_data import zerar_colunas_video
from bling_app_zero.utils.gtin import contar_gtins_invalidos_df, contar_gtins_suspeitos_df


def _csv_bling_bytes(df: pd.DataFrame) -> bytes:
    """Gera CSV no padrão de importação do Bling.

    BLINGFIX MEGA CENTER FLUXO FINAL CSV:
    - separador ponto e vírgula;
    - UTF-8 com BOM para abrir corretamente no Excel;
    - sem índice artificial;
    - colunas de vídeo zeradas antes do download.
    """
    if not isinstance(df, pd.DataFrame):
        df = pd.DataFrame()

    base = df.copy().fillna("")
    if len(base.columns) > 0:
        base = zerar_colunas_video(base).fillna("")

    return base.to_csv(index=False, sep=";").encode("utf-8-sig")


def render_preview_dataframe(df_final: pd.DataFrame) -> None:
    st.markdown("### Preview final")

    df_final = zerar_colunas_video(df_final)

    if df_final.empty:
        st.dataframe(pd.DataFrame(columns=df_final.columns), use_container_width=True)
        return

    st.dataframe(df_final.head(80), use_container_width=True)
    with st.expander("Ver preview ampliado", expanded=False):
        st.dataframe(df_final.head(250), use_container_width=True)


def render_download(df_final: pd.DataFrame, validacao_ok: bool) -> None:
    st.markdown("### Download da planilha padrão Bling")

    df_final = zerar_colunas_video(df_final)
    csv_bytes = _csv_bling_bytes(df_final)

    gtins_invalidos_total = contar_gtins_invalidos_df(df_final)
    gtins_suspeitos = contar_gtins_suspeitos_df(df_final)
    gtins_invalidos_reais = max(int(gtins_invalidos_total) - int(gtins_suspeitos), 0)

    download_liberado = bool(validacao_ok)

    st.caption("CSV padrão Bling: separador ;, UTF-8-SIG e sem coluna de índice.")

    st.download_button(
        label="📥 Baixar CSV final",
        data=csv_bytes,
        file_name="bling_saida_final.csv",
        mime="text/csv",
        use_container_width=True,
        disabled=not download_liberado,
        key="btn_download_csv_final_preview",
    )

    if download_liberado:
        if gtins_invalidos_reais > 0 or gtins_suspeitos > 0:
            st.info(
                f"O download está liberado. Ainda existem {gtins_invalidos_reais} GTIN(s) inválido(s) "
                f"e {gtins_suspeitos} GTIN(s) suspeito(s), mas essa correção ficou centralizada na etapa anterior."
            )

        if st.session_state.get("preview_download_realizado", False):
            st.success("Download já confirmado. Conexão e envio ao Bling liberados.")
        elif st.button(
            "✅ Já baixei / seguir para conexão e envio",
            use_container_width=True,
            key="btn_confirmar_download_preview",
        ):
            st.session_state["preview_download_realizado"] = True
            log_debug("Usuário confirmou a etapa de download e avançou para conexão/envio.", nivel="INFO")
            st.rerun()
    else:
        st.info("Ajuste a validação principal antes de liberar o download e o envio.")

