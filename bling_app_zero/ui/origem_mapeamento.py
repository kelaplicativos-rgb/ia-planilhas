from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

import pandas as pd
import streamlit as st


def _safe_dataframe_preview(df: pd.DataFrame, rows: int = 20) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return pd.DataFrame()
    try:
        return df.head(rows).copy()
    except Exception:
        return pd.DataFrame()


def _safe_validation_result(
    resultado: Any,
) -> tuple[list[str], list[str]]:
    if isinstance(resultado, tuple) and len(resultado) >= 2:
        erros = resultado[0] if isinstance(resultado[0], list) else []
        avisos = resultado[1] if isinstance(resultado[1], list) else []
        return erros, avisos
    return [], []


def _build_log_text(
    *,
    modo: str,
    arquivo_saida: str,
    origem_hash: str,
    logs_gtin: list[str] | None,
    erros: list[str] | None,
    avisos: list[str] | None,
) -> str:
    linhas: list[str] = []

    linhas.append("LOG DE PROCESSAMENTO")
    linhas.append("=" * 60)
    linhas.append(f"Data/Hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    linhas.append(f"Modo: {modo}")
    linhas.append(f"Arquivo de saída: {arquivo_saida}")
    linhas.append(f"Hash da origem: {origem_hash}")
    linhas.append("")

    logs_globais = st.session_state.get("logs", [])
    if isinstance(logs_globais, list) and logs_globais:
        linhas.append("LOGS GERAIS")
        linhas.append("-" * 60)
        for item in logs_globais:
            try:
                texto = str(item).strip()
            except Exception:
                texto = ""
            if texto:
                linhas.append(texto)
        linhas.append("")

    if erros:
        linhas.append("ERROS DE VALIDAÇÃO")
        linhas.append("-" * 60)
        for item in erros:
            linhas.append(f"- {item}")
        linhas.append("")

    if avisos:
        linhas.append("AVISOS DE VALIDAÇÃO")
        linhas.append("-" * 60)
        for item in avisos:
            linhas.append(f"- {item}")
        linhas.append("")

    if logs_gtin:
        linhas.append("LOGS DE LIMPEZA / VALIDAÇÃO GTIN/EAN")
        linhas.append("-" * 60)
        for item in logs_gtin:
            linhas.append(f"- {item}")
        linhas.append("")

    if len(linhas) <= 6:
        linhas.append("Nenhum log disponível.")

    return "\n".join(linhas)


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
    validar_saida_bling: Callable[..., Any],
    aplicar_limpeza_gtin_ean_df_saida: Callable[..., Any],
    exportar_df_exato_para_excel_bytes: Callable[..., bytes],
    log_func: Callable[[str], None],
) -> None:
    """
    Módulo extraído do fluxo de origem/mapeamento.

    Objetivo:
    - centralizar preview, mapeamento, validação e download;
    - manter o fluxo da home/origem dos dados;
    - não alterar layout/campos fora do necessário.
    """

    if not isinstance(df_origem, pd.DataFrame) or df_origem.empty:
        st.warning("A origem não possui dados válidos para mapear.")
        return

    if not isinstance(colunas_modelo_ativas, list) or not colunas_modelo_ativas:
        st.warning("O modelo ativo não possui colunas para mapear.")
        return

    st.markdown("### Preview da origem")
    st.dataframe(_safe_dataframe_preview(df_origem, 10), width="stretch")

    try:
        mapeamento_manual = render_mapeamento_manual(
            df_origem=df_origem,
            colunas_destino=colunas_modelo_ativas,
            state_key=state_key,
        )
    except TypeError:
        try:
            mapeamento_manual = render_mapeamento_manual(
                df_origem=df_origem,
                colunas_modelo_ativas=colunas_modelo_ativas,
                state_key=state_key,
            )
        except Exception as e:
            st.error(f"Erro ao renderizar o mapeamento manual: {e}")
            log_func(f"Erro ao renderizar o mapeamento manual: {e}")
            return
    except Exception as e:
        st.error(f"Erro ao renderizar o mapeamento manual: {e}")
        log_func(f"Erro ao renderizar o mapeamento manual: {e}")
        return

    if not isinstance(mapeamento_manual, dict):
        mapeamento_manual = {}

    calculadora_cfg: Any = {}
    try:
        calculadora_cfg = render_calculadora(
            df_origem=df_origem,
            colunas_destino_ativas=colunas_modelo_ativas,
            modo=modo,
        )
    except TypeError:
        try:
            calculadora_cfg = render_calculadora(
                df_origem=df_origem,
                colunas_modelo_ativas=colunas_modelo_ativas,
                modo=modo,
            )
        except Exception:
            calculadora_cfg = {}
    except Exception:
        calculadora_cfg = {}

    estoque_cfg: Any = None
    if str(modo).lower() == "estoque":
        try:
            estoque_cfg = render_campos_fixos_estoque(colunas_modelo_ativas)
        except TypeError:
            try:
                estoque_cfg = render_campos_fixos_estoque(
                    colunas_modelo_ativas=colunas_modelo_ativas
                )
            except Exception:
                estoque_cfg = {}
        except Exception:
            estoque_cfg = {}

    st.divider()
    st.markdown("### Preview do que será baixado")

    try:
        df_preview_saida = montar_df_saida_exato_modelo(
            df_origem=df_origem,
            colunas_modelo=colunas_modelo_ativas,
            mapeamento_manual=mapeamento_manual,
            calculadora_cfg=calculadora_cfg,
            estoque_cfg=estoque_cfg,
            modo=modo,
        )
    except TypeError:
        try:
            df_preview_saida = montar_df_saida_exato_modelo(
                df_origem=df_origem,
                colunas_modelo_ativas=colunas_modelo_ativas,
                mapeamento_manual=mapeamento_manual,
                calculadora_cfg=calculadora_cfg,
                estoque_cfg=estoque_cfg,
                modo=modo,
            )
        except Exception as e:
            st.error(f"Erro ao montar o preview final: {e}")
            log_func(f"Erro ao montar o preview final: {e}")
            return
    except Exception as e:
        st.error(f"Erro ao montar o preview final: {e}")
        log_func(f"Erro ao montar o preview final: {e}")
        return

    if not isinstance(df_preview_saida, pd.DataFrame):
        st.error("A montagem do preview final não retornou uma planilha válida.")
        return

    erros_preview, avisos_preview = _safe_validation_result(
        validar_saida_bling(df_preview_saida, modo)
    )
    st.session_state["validacao_erros_saida"] = erros_preview
    st.session_state["validacao_avisos_saida"] = avisos_preview

    st.dataframe(_safe_dataframe_preview(df_preview_saida, 20), width="stretch")

    if erros_preview:
        st.error("Pendências antes do download:\n\n- " + "\n- ".join(erros_preview))
    elif avisos_preview:
        st.warning("Avisos encontrados:\n\n- " + "\n- ".join(avisos_preview))
    else:
        st.success("Preview válido para gerar o arquivo final.")

    c1, c2, c3 = st.columns(3)
    with c1:
        gerar_preview_final = st.button("Gerar preview final", width="stretch")
    with c2:
        limpar_gtin = st.button("Limpar GTIN/EAN inválido", width="stretch")
    with c3:
        limpar_mapeamento = st.button("Limpar mapeamento", width="stretch")

    if limpar_mapeamento:
        st.session_state[state_key] = {}
        st.session_state.pop("df_saida", None)
        st.session_state.pop("df_saida_preview_hash", None)
        st.session_state.pop("excel_saida_bytes", None)
        st.session_state.pop("excel_saida_nome", None)
        st.session_state.pop("logs_gtin_saida", None)
        st.session_state.pop("log_processamento_texto", None)
        st.session_state.pop("log_processamento_nome", None)
        st.rerun()

    if gerar_preview_final or limpar_gtin:
        try:
            df_saida_final = montar_df_saida_exato_modelo(
                df_origem=df_origem,
                colunas_modelo=colunas_modelo_ativas,
                mapeamento_manual=mapeamento_manual,
                calculadora_cfg=calculadora_cfg,
                estoque_cfg=estoque_cfg,
                modo=modo,
            )
        except TypeError:
            try:
                df_saida_final = montar_df_saida_exato_modelo(
                    df_origem=df_origem,
                    colunas_modelo_ativas=colunas_modelo_ativas,
                    mapeamento_manual=mapeamento_manual,
                    calculadora_cfg=calculadora_cfg,
                    estoque_cfg=estoque_cfg,
                    modo=modo,
                )
            except Exception as e:
                st.error(f"Erro ao gerar a saída final: {e}")
                log_func(f"Erro ao gerar a saída final: {e}")
                return
        except Exception as e:
            st.error(f"Erro ao gerar a saída final: {e}")
            log_func(f"Erro ao gerar a saída final: {e}")
            return

        logs_gtin: list[str] = []
        total_limpados = 0

        try:
            resultado_limpeza = aplicar_limpeza_gtin_ean_df_saida(df_saida_final)
            if isinstance(resultado_limpeza, tuple):
                if len(resultado_limpeza) >= 1 and isinstance(resultado_limpeza[0], pd.DataFrame):
                    df_saida_final = resultado_limpeza[0]
                if len(resultado_limpeza) >= 2 and isinstance(resultado_limpeza[1], int):
                    total_limpados = resultado_limpeza[1]
                if len(resultado_limpeza) >= 3 and isinstance(resultado_limpeza[2], list):
                    logs_gtin = resultado_limpeza[2]
            elif isinstance(resultado_limpeza, pd.DataFrame):
                df_saida_final = resultado_limpeza
        except Exception as e:
            st.error(f"Erro ao aplicar limpeza de GTIN/EAN: {e}")
            log_func(f"Erro ao aplicar limpeza de GTIN/EAN: {e}")
            return

        erros_finais, avisos_finais = _safe_validation_result(
            validar_saida_bling(df_saida_final, modo)
        )

        st.session_state["validacao_erros_saida"] = erros_finais
        st.session_state["validacao_avisos_saida"] = avisos_finais
        st.session_state["logs_gtin_saida"] = logs_gtin

        log_texto = _build_log_text(
            modo=modo,
            arquivo_saida=arquivo_saida,
            origem_hash=origem_hash,
            logs_gtin=logs_gtin,
            erros=erros_finais,
            avisos=avisos_finais,
        )
        st.session_state["log_processamento_texto"] = log_texto
        st.session_state["log_processamento_nome"] = (
            f"log_processamento_{str(modo).lower()}.txt"
        )

        if erros_finais:
            st.error("Ainda existem pendências antes do download.")
            return

        try:
            excel_bytes = exportar_df_exato_para_excel_bytes(df_saida_final)
        except Exception as e:
            st.error(f"Erro ao gerar o Excel final: {e}")
            log_func(f"Erro ao gerar o Excel final: {e}")
            return

        st.session_state["df_saida"] = df_saida_final.copy()
        st.session_state["df_saida_preview_hash"] = origem_hash
        st.session_state["excel_saida_bytes"] = excel_bytes
        st.session_state["excel_saida_nome"] = arquivo_saida

        if limpar_gtin:
            if total_limpados > 0:
                st.success(
                    f"Limpeza concluída.\n\n{total_limpados} GTIN/EAN inválido(s) foram deixados em branco."
                )
            else:
                st.success("Limpeza concluída. Nenhum GTIN/EAN inválido foi encontrado.")
        else:
            if total_limpados > 0:
                st.success(
                    f"Preview final gerado com sucesso.\n\n{total_limpados} GTIN/EAN inválido(s) foram deixados em branco."
                )
            else:
                st.success("Preview final gerado com sucesso.")

    logs_gtin_saida = st.session_state.get("logs_gtin_saida", [])
    if isinstance(logs_gtin_saida, list) and logs_gtin_saida:
        st.caption("Validação de GTIN/EAN aplicada na saída:")
        for item in logs_gtin_saida:
            st.caption(f"- {item}")

    df_saida_state = st.session_state.get("df_saida")
    df_saida_hash = st.session_state.get("df_saida_preview_hash")
    excel_saida_bytes = st.session_state.get("excel_saida_bytes")
    excel_saida_nome = st.session_state.get("excel_saida_nome", arquivo_saida)
    log_processamento_texto = st.session_state.get("log_processamento_texto", "")
    log_processamento_nome = st.session_state.get(
        "log_processamento_nome",
        f"log_processamento_{str(modo).lower()}.txt",
    )

    if (
        isinstance(df_saida_state, pd.DataFrame)
        and not df_saida_state.empty
        and df_saida_hash == origem_hash
        and excel_saida_bytes
    ):
        st.divider()
        st.markdown("### Preview final validado para download")
        st.caption(f"{len(df_saida_state)} linhas × {len(df_saida_state.columns)} colunas")
        st.dataframe(_safe_dataframe_preview(df_saida_state, 50), width="stretch")

        d1, d2 = st.columns(2)

        with d1:
            st.download_button(
                label=f"Baixar arquivo de {config.get('label', 'saída')}",
                data=excel_saida_bytes,
                file_name=excel_saida_nome,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                width="stretch",
            )

        with d2:
            st.download_button(
                label="Baixar log do processamento",
                data=str(log_processamento_texto).encode("utf-8"),
                file_name=log_processamento_nome,
                mime="text/plain",
                width="stretch",
                )
