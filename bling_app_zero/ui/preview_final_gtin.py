from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.utils.gtin import (
    aplicar_validacao_gtin_em_colunas_automaticas,
    contar_gtins_invalidos_df,
    contar_gtins_suspeitos_df,
    encontrar_colunas_gtin,
    gerar_gtins_validos_em_colunas_automaticas,
    resumir_logs_limpeza_gtin,
)


def _limpar_gtins_invalidos_df(df: pd.DataFrame) -> tuple[pd.DataFrame, int, list[str], dict[str, int]]:
    if not isinstance(df, pd.DataFrame):
        return pd.DataFrame(), 0, ["DataFrame inválido para limpeza de GTIN."], {
            "colunas_gtin": 0,
            "invalidos": 0,
            "suspeitos": 0,
            "validos": 0,
            "vazios": 0,
        }

    df_saida, logs = aplicar_validacao_gtin_em_colunas_automaticas(
        df.copy(),
        preservar_coluna_original=False,
    )
    resumo = resumir_logs_limpeza_gtin(logs)
    total_limpos = int(resumo.get("invalidos", 0) or 0) + int(resumo.get("suspeitos", 0) or 0)
    return df_saida.copy().fillna(""), total_limpos, logs, resumo


def render_acoes_gtin(df_final: pd.DataFrame) -> pd.DataFrame:
    colunas_gtin = encontrar_colunas_gtin(df_final)
    if not colunas_gtin:
        return df_final

    st.markdown("### Tratamento de GTIN")

    gtins_invalidos_total = contar_gtins_invalidos_df(df_final)
    gtins_suspeitos = contar_gtins_suspeitos_df(df_final)
    gtins_invalidos_reais = max(int(gtins_invalidos_total) - int(gtins_suspeitos), 0)
    total_pendencias_gtin = int(gtins_invalidos_reais) + int(gtins_suspeitos)

    if total_pendencias_gtin > 0:
        st.warning(
            f"Foram encontrados **{gtins_invalidos_reais} GTIN(s) inválido(s)** e "
            f"**{gtins_suspeitos} GTIN(s) suspeito(s)** no resultado final."
        )
    else:
        st.caption("Nenhum GTIN inválido ou suspeito encontrado no preview final.")

    col1, col2 = st.columns(2)

    with col1:
        if st.button(
            "🧹 Limpar GTINs inválidos/suspeitos",
            use_container_width=True,
            key="btn_limpar_gtins_invalidos_preview",
        ):
            df_limpo, total_limpos, logs_limpeza, resumo_limpeza = _limpar_gtins_invalidos_df(df_final.copy())
            st.session_state["df_final"] = df_limpo.copy()
            st.session_state["gtin_logs_limpeza"] = logs_limpeza
            st.session_state["gtin_resumo_limpeza"] = resumo_limpeza

            if total_limpos > 0:
                st.success(f"{total_limpos} GTIN(s) inválido(s)/suspeito(s) foram limpos e deixados vazios.")
            else:
                st.info("Nenhum GTIN inválido ou suspeito foi encontrado para limpar.")

            st.rerun()

    with col2:
        st.caption("Depois da limpeza, você pode gerar GTINs válidos nos vazios ou seguir para o download.")

    resumo_limpeza = st.session_state.get("gtin_resumo_limpeza", {})
    if resumo_limpeza:
        col_r1, col_r2, col_r3, col_r4, col_r5 = st.columns(5)
        with col_r1:
            st.metric("Colunas GTIN", int(resumo_limpeza.get("colunas_gtin", 0) or 0))
        with col_r2:
            st.metric("Inválidos limpos", int(resumo_limpeza.get("invalidos", 0) or 0))
        with col_r3:
            st.metric("Suspeitos limpos", int(resumo_limpeza.get("suspeitos", 0) or 0))
        with col_r4:
            st.metric("Válidos", int(resumo_limpeza.get("validos", 0) or 0))
        with col_r5:
            st.metric("Vazios", int(resumo_limpeza.get("vazios", 0) or 0))

    st.radio(
        "Deseja gerar GTINs agora ou seguir para o download?",
        options=["Seguir para o download", "Gerar GTINs válidos nos vazios"],
        horizontal=True,
        key="preview_gtin_escolha",
    )

    if st.session_state.get("preview_gtin_escolha") == "Gerar GTINs válidos nos vazios":
        prefixo = st.text_input(
            "Prefixo GTIN",
            value=str(st.session_state.get("gtin_prefixo_geracao", "789") or "789"),
            key="gtin_prefixo_geracao",
        )

        if st.button("⚡ Gerar GTINs válidos", use_container_width=True, key="btn_gerar_gtins_preview"):
            df_gerado, logs = gerar_gtins_validos_em_colunas_automaticas(
                df_final.copy(),
                prefixo=prefixo,
                apenas_vazios=True,
            )
            st.session_state["df_final"] = df_gerado.copy()
            st.session_state["gtin_logs_geracao"] = logs

            total_gerados = 0
            for item in logs:
                texto = str(item)
                if texto.startswith("GTIN gerados:"):
                    try:
                        total_gerados += int(texto.split(":")[-1].strip())
                    except Exception:
                        pass

            if total_gerados > 0:
                st.success(f"{total_gerados} GTIN(s) válido(s) foram gerados nos campos vazios.")
            else:
                st.info("Nenhum GTIN foi gerado porque os campos já estavam preenchidos.")
            st.rerun()

    return st.session_state.get("df_final", df_final)
