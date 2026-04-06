from __future__ import annotations

from typing import Any, Callable

import pandas as pd
import streamlit as st


def render_origem_mapeamento(
    *,
    df_origem: pd.DataFrame,
    colunas_modelo_ativas: list[str],
    modo: str,
    arquivo_saida: str,
    origem_hash: str,
    config: dict[str, Any],
    state_key: str,
    render_mapeamento_manual: Callable[..., dict[str, str]],
    render_calculadora: Callable[..., Any],
    render_campos_fixos_estoque: Callable[..., Any],
    montar_df_saida_exato_modelo: Callable[..., pd.DataFrame],
    validar_saida_bling: Callable[..., tuple[list[str], list[str]]],
    aplicar_limpeza_gtin_ean_df_saida: Callable[..., tuple[pd.DataFrame, int, list[str]]],
    exportar_df_exato_para_excel_bytes: Callable[[pd.DataFrame], bytes],
    log_func: Callable[[str], None],
) -> None:
    """
    Bloco modularizado do fluxo de mapeamento/preview/download da origem.

    Objetivo:
    - manter o mesmo comportamento visual e funcional do fluxo atual;
    - apenas retirar de origem_dados.py o trecho de mapeamento final;
    - não alterar campos, textos ou layout base.
    """

    if df_origem is None or df_origem.empty:
        st.warning("A origem foi lida, mas não possui dados para processar.")
        return

    st.subheader("Preview da origem")
    st.dataframe(df_origem.head(10), width="stretch")

    mapeamento_manual = render_mapeamento_manual(
        df_origem=df_origem,
        colunas_destino=colunas_modelo_ativas,
        state_key=state_key,
    )

    calculadora_cfg = render_calculadora(
        df_origem=df_origem,
        colunas_destino_ativas=colunas_modelo_ativas,
        modo=modo,
    )

    estoque_cfg = None
    if modo == "estoque":
        estoque_cfg = render_campos_fixos_estoque(colunas_modelo_ativas)

    st.divider()
    st.subheader("Preview do que será baixado")

    try:
        df_preview_saida = montar_df_saida_exato_modelo(
            df_origem=df_origem,
            colunas_modelo=colunas_modelo_ativas,
            mapeamento_manual=mapeamento_manual,
            calculadora_cfg=calculadora_cfg,
            estoque_cfg=estoque_cfg,
            modo=modo,
        )
    except Exception as e:
        st.error(f"Erro ao montar preview da saída: {e}")
        log_func(f"Erro ao montar preview da saída: {e}")
        return

    erros_preview, avisos_preview = validar_saida_bling(df_preview_saida, modo)
    st.session_state["validacao_erros_saida"] = erros_preview
    st.session_state["validacao_avisos_saida"] = avisos_preview

    st.dataframe(df_preview_saida.head(20), width="stretch")

    if erros_preview:
        st.error("Pendências antes do download:\n\n- " + "\n- ".join(erros_preview))
    elif avisos_preview:
        st.warning("Avisos:\n\n- " + "\n- ".join(avisos_preview))
    else:
        st.success("Preview válido para gerar o arquivo final.")

    b1, b2, b3 = st.columns(3)

    with b1:
        if st.button("Gerar preview final", width="stretch"):
            try:
                df_saida_final = montar_df_saida_exato_modelo(
                    df_origem=df_origem,
                    colunas_modelo=colunas_modelo_ativas,
                    mapeamento_manual=mapeamento_manual,
                    calculadora_cfg=calculadora_cfg,
                    estoque_cfg=estoque_cfg,
                    modo=modo,
                )

                df_saida_final, total_limpados, logs_gtin = aplicar_limpeza_gtin_ean_df_saida(
                    df_saida_final
                )

                erros_final, avisos_final = validar_saida_bling(df_saida_final, modo)
                st.session_state["validacao_erros_saida"] = erros_final
                st.session_state["validacao_avisos_saida"] = avisos_final
                st.session_state["logs_gtin_saida"] = logs_gtin

                if erros_final:
                    st.error("Não foi possível liberar o download porque ainda existem pendências.")
                    return

                excel_bytes = exportar_df_exato_para_excel_bytes(df_saida_final)

                st.session_state["df_saida"] = df_saida_final.copy()
                st.session_state["df_saida_preview_hash"] = origem_hash
                st.session_state["excel_saida_bytes"] = excel_bytes
                st.session_state["excel_saida_nome"] = arquivo_saida

                if total_limpados > 0:
                    st.success(
                        f"Preview final gerado com sucesso. "
                        f"{total_limpados} GTIN/EAN inválido(s) foram deixados em branco."
                    )
                else:
                    st.success("Preview final gerado com sucesso. Revise abaixo antes de baixar.")

            except Exception as e:
                st.error(f"Erro ao gerar preview final: {e}")
                log_func(f"Erro ao gerar preview final: {e}")

    with b2:
        if st.button("Limpar GTIN/EAN inválido", width="stretch"):
            try:
                df_saida_limpa = montar_df_saida_exato_modelo(
                    df_origem=df_origem,
                    colunas_modelo=colunas_modelo_ativas,
                    mapeamento_manual=mapeamento_manual,
                    calculadora_cfg=calculadora_cfg,
                    estoque_cfg=estoque_cfg,
                    modo=modo,
                )

                df_saida_limpa, total_limpados, logs_gtin = aplicar_limpeza_gtin_ean_df_saida(
                    df_saida_limpa
                )

                erros_final, avisos_final = validar_saida_bling(df_saida_limpa, modo)
                st.session_state["validacao_erros_saida"] = erros_final
                st.session_state["validacao_avisos_saida"] = avisos_final
                st.session_state["logs_gtin_saida"] = logs_gtin

                if erros_final:
                    st.error("A limpeza foi aplicada, mas ainda existem pendências antes do download.")
                    return

                excel_bytes = exportar_df_exato_para_excel_bytes(df_saida_limpa)

                st.session_state["df_saida"] = df_saida_limpa.copy()
                st.session_state["df_saida_preview_hash"] = origem_hash
                st.session_state["excel_saida_bytes"] = excel_bytes
                st.session_state["excel_saida_nome"] = arquivo_saida

                if total_limpados > 0:
                    st.success(
                        f"Limpeza concluída. "
                        f"{total_limpados} GTIN/EAN inválido(s) foram deixados em branco."
                    )
                else:
                    st.success("Limpeza concluída. Nenhum GTIN/EAN inválido foi encontrado para zerar.")

            except Exception as e:
                st.error(f"Erro ao limpar GTIN/EAN inválido: {e}")
                log_func(f"Erro ao limpar GTIN/EAN inválido: {e}")

    with b3:
        if st.button("Limpar mapeamento", width="stretch"):
            st.session_state[state_key] = {}
            st.session_state.pop("df_saida", None)
            st.session_state.pop("df_saida_preview_hash", None)
            st.session_state.pop("excel_saida_bytes", None)
            st.session_state.pop("excel_saida_nome", None)
            st.session_state.pop("logs_gtin_saida", None)
            st.rerun()

    logs_gtin_saida = st.session_state.get("logs_gtin_saida", [])
    if logs_gtin_saida:
        st.caption("Validação de GTIN/EAN aplicada no arquivo final:")
        for linha in logs_gtin_saida:
            st.caption(f"- {linha}")

    df_saida_state = st.session_state.get("df_saida")
    df_saida_hash = st.session_state.get("df_saida_preview_hash")
    excel_saida_bytes = st.session_state.get("excel_saida_bytes")
    excel_saida_nome = st.session_state.get("excel_saida_nome", arquivo_saida)

    if (
        isinstance(df_saida_state, pd.DataFrame)
        and not df_saida_state.empty
        and df_saida_hash == origem_hash
        and excel_saida_bytes
    ):
        st.divider()
        st.subheader("Preview final validado para download")
        st.caption(f"{len(df_saida_state)} linhas × {len(df_saida_state.columns)} colunas")
        st.dataframe(df_saida_state.head(50), width="stretch")

        st.download_button(
            f"Baixar arquivo de {config['label']}",
            data=excel_saida_bytes,
            file_name=excel_saida_nome,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            width="stretch",
        )
