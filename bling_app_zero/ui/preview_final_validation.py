from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.ui.app_helpers import log_debug, validar_df_para_download
from bling_app_zero.ui.preview_final_data import garantir_df_final_canonico, montar_resumo
from bling_app_zero.ui.preview_final_state import obter_deposito_nome_persistido
from bling_app_zero.utils.gtin import contar_gtins_invalidos_df, contar_gtins_suspeitos_df


def render_resumo_validacao(df_final: pd.DataFrame, tipo_operacao: str) -> tuple[bool, list[str]]:
    df_final = garantir_df_final_canonico(
        df=df_final,
        tipo_operacao=tipo_operacao,
        deposito_nome=obter_deposito_nome_persistido(),
    )
    resumo = montar_resumo(df_final)
    valido, erros = validar_df_para_download(df_final, tipo_operacao)
    st.session_state["preview_validacao_ok"] = bool(valido)
    st.session_state["preview_validacao_erros"] = list(erros)

    st.markdown("### Validação do resultado final")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Linhas", resumo["linhas"])
    with c2:
        st.metric("Colunas", resumo["colunas"])
    with c3:
        st.metric("Com código", resumo["codigo_ok"])
    with c4:
        st.metric("Com descrição", resumo["descricao_ok"])

    c5, c6, c7 = st.columns(3)
    with c5:
        st.metric("Com preço", resumo["preco_ok"])
    with c6:
        st.metric("Com GTIN", resumo["gtin_ok"])
    with c7:
        st.metric("Validação", "OK" if valido else "Ajustes pendentes")

    gtins_invalidos_total = contar_gtins_invalidos_df(df_final)
    gtins_suspeitos = contar_gtins_suspeitos_df(df_final)
    gtins_invalidos_reais = max(int(gtins_invalidos_total) - int(gtins_suspeitos), 0)

    st.session_state["preview_validacao_ok"] = bool(valido)
    st.session_state["preview_validacao_erros"] = list(erros)

    if erros:
        st.error("Existem pendências obrigatórias antes do download e do envio.")
        for erro in erros:
            st.write(f"- {erro}")
        log_debug(f"Validação final com pendências: {' | '.join(erros)}", nivel="ERRO")
    else:
        st.success("A planilha final passou na validação principal.")
        log_debug("Validação final aprovada.", nivel="INFO")

    if gtins_invalidos_reais > 0 or gtins_suspeitos > 0:
        mensagem_gtin = (
            f"Existem {gtins_invalidos_reais} GTIN(s) inválido(s) e "
            f"{gtins_suspeitos} GTIN(s) suspeito(s). "
            "Corrija na etapa anterior se desejar. O preview final não bloqueia mais o download por GTIN."
        )
        st.warning(mensagem_gtin)
        log_debug(mensagem_gtin, nivel="AVISO")

    return valido, erros


def render_colunas_detectadas_sync(df_final: pd.DataFrame) -> None:
    resumo = montar_resumo(df_final)

    with st.expander("Colunas que o envio vai usar", expanded=False):
        c1, c2 = st.columns(2)
        with c1:
            st.write(f"**Código detectado:** {resumo['codigo_col'] or 'não encontrado'}")
            st.write(f"**Descrição detectada:** {resumo['descricao_col'] or 'não encontrada'}")
        with c2:
            st.write(f"**Preço detectado:** {resumo['preco_col'] or 'não encontrado'}")
            st.write(f"**GTIN detectado:** {resumo['gtin_col'] or 'não encontrado'}")

        if not resumo["codigo_col"] or not resumo["descricao_col"]:
            st.warning(
                "O sincronizador do Bling pode falhar no envio se código ou descrição não forem detectados corretamente."
            )
